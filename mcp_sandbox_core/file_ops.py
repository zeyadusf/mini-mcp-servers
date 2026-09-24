"""
mcp-sandbox-core/file_ops.py

Centralized, sandboxed file I/O.

safe_open() combines path validation with consistent error translation
for read/append/write operations. It does NOT create parent directories
or otherwise mutate the filesystem beyond what open() itself does —
any side effects (like directory creation) are the caller's
responsibility to perform and log explicitly. A silent auto-mkdir here
would make tools like write_file lie about their own side_effects
metadata, so that logic stays out of this file on purpose.

atomic_write() is a separate primitive for atomic overwrite via a temp
file + os.replace, since that doesn't fit the open()-context-manager
shape at all. It operates on an already-resolved, already-trusted Path
— the caller must have run resolve_in_workspace() first.

Both safe_open() and atomic_write() also enforce the content-class
denylist from sensitive_files.py (secrets, credentials, private keys),
checked right after path_guard's boundary check and before any actual
open()/write happens — this keeps the ordering (boundary check, then
sensitivity check) guaranteed by construction, since both checks live
in the same gate instead of being called separately by each tool.
"""

import contextlib
import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import IO

from mcp_sandbox_core.path_guard import resolve_in_workspace
from mcp_sandbox_core.sandbox_exception import (
    FileNotFoundInWorkspace,
    SensitiveFileBlocked,
)
from mcp_sandbox_core.sensitive_files import Action, check


@contextlib.contextmanager
def safe_open(
    workspace_root: Path,
    user_path: str | Path,
    mode: str = "r",
    encoding: str | None = "utf-8",
) -> Generator[IO, None, None]:
    """
    Resolve `user_path` inside `workspace_root` and open it safely.

    Raises:
        PathEscapesWorkspaceError: propagated from resolve_in_workspace.
        SensitiveFileBlocked: if the resolved path matches a denylisted
            pattern for the action implied by `mode` (read vs write).
        FileNotFoundInWorkspace: if opening for read and the file doesn't exist.

    Note: does not create parent directories. If a caller needs to write
    into a possibly-missing directory and wants to report that as a
    side effect, it must create the directory itself before calling this.
    """
    full_path = resolve_in_workspace(workspace_root, user_path)

    normalized_mode = mode.replace("b", "").replace("t", "")
    is_read_mode = normalized_mode.startswith("r") and "+" not in normalized_mode
    action: Action = "read" if is_read_mode else "write"

    sf_result = check(full_path, action, workspace_root)
    if not sf_result.allowed:
        raise SensitiveFileBlocked(
            f"'{user_path}' matches a blocked pattern ({sf_result.matched_pattern})."
        )

    if is_read_mode and not full_path.is_file():
        raise FileNotFoundInWorkspace(f"'{user_path}' not found in workspace.")

    if "b" in mode:
        encoding = None

    with open(full_path, mode, encoding=encoding) as f:
        yield f


def atomic_write(full_path: Path, content: str, workspace_root: Path) -> None:
    """
    Atomically overwrite full_path with content via a temp file + os.replace.

    full_path must already be a resolved, validated Path (the caller
    already ran it through resolve_in_workspace). This function does
    not perform path *boundary* validation itself since it never
    touches raw user input — but it still needs `workspace_root` to
    run the sensitive_files check, since that check needs the path
    relative to the workspace root, not just the absolute path.

    Raises:
        SensitiveFileBlocked: if full_path matches a denylisted pattern.
    """
    sf_result = check(full_path, "write", workspace_root)
    if not sf_result.allowed:
        raise SensitiveFileBlocked(
            f"'{full_path}' matches a blocked pattern ({sf_result.matched_pattern})."
        )

    fd, tmp_path = tempfile.mkstemp(dir=full_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, full_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
