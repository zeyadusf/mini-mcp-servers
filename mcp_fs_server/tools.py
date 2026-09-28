"""
mcp_fs_server/tools.py

Pure implementation functions for the FS server's tools, kept
independent of the MCP protocol layer (server.py) so they can be unit
tested directly without spinning up a server or an MCP client.

Every function here takes workspace_root explicitly (no module-level
global) and delegates all boundary/sensitivity checks to
mcp_sandbox_core — this module never touches a path without going
through it first.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_sandbox_core import atomic_write, resolve_in_workspace, safe_open

# Cap on how much a single read_file call will return, to avoid
# blowing up the model's context window on a huge file. Chosen as a
# round number comfortably under typical tool-result limits; revisit
# if real usage needs range-based reads instead.
MAX_READ_CHARS = 200_000


class FileTooLargeError(Exception):
    """Raised when a file exceeds MAX_READ_CHARS."""


class EditNotUniqueError(Exception):
    """Raised when old_string matches zero or multiple times in the file."""


def list_directory(
    workspace_root: Path, path: str = ".", show_hidden: bool = False
) -> list[dict[str, Any]]:
    """
    List the contents of a directory inside the workspace.

    Returns a list of {"name", "type", "size"} dicts, sorted directories
    first then files, both alphabetically. Dotfiles/dotdirs are
    excluded unless show_hidden=True.
    """
    full_path = resolve_in_workspace(workspace_root, path)
    if not full_path.is_dir():
        raise NotADirectoryError(f"'{path}' is not a directory.")

    entries: list[dict[str, Any]] = []
    for entry in full_path.iterdir():
        if not show_hidden and entry.name.startswith("."):
            continue
        entries.append(
            {
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            }
        )

    entries.sort(key=lambda e: (e["type"] != "directory", e["name"].lower()))
    return entries


def read_file(workspace_root: Path, path: str) -> str:
    """
    Read a text file's full content.

    Raises:
        FileTooLargeError: if the file exceeds MAX_READ_CHARS.
        (plus everything safe_open can raise: PathEscapesWorkspaceError,
        SensitiveFileBlocked, FileNotFoundInWorkspace)
    """
    with safe_open(workspace_root, path, "r") as f:
        content = f.read()

    if len(content) > MAX_READ_CHARS:
        raise FileTooLargeError(
            f"'{path}' is {len(content)} chars, exceeds the "
            f"{MAX_READ_CHARS}-char read limit."
        )
    return content


def write_file(workspace_root: Path, path: str, content: str) -> dict[str, Any]:
    """
    Create or fully overwrite a file with `content`.

    Unlike mcp_sandbox_core.file_ops (which deliberately never creates
    parent directories, to keep tool side effects honest), THIS tool
    layer does create missing parent directories — and reports it —
    because refusing to write into a not-yet-created subdirectory is
    rarely what an agent actually wants. That decision lives here, not
    in the shared sandbox library, per file_ops.py's own docstring.
    """
    full_path = resolve_in_workspace(workspace_root, path)

    created_directories = False
    if not full_path.parent.exists():
        full_path.parent.mkdir(parents=True)
        created_directories = True

    atomic_write(full_path, content, workspace_root)

    return {
        "path": path,
        "bytes_written": len(content.encode("utf-8")),
        "created_directories": created_directories,
    }


def edit_file(
    workspace_root: Path, path: str, old_string: str, new_string: str
) -> dict[str, Any]:
    """
    Replace exactly one occurrence of old_string with new_string in an
    existing file. Deliberately unambiguous, same convention as this
    environment's own str_replace tool: old_string must match exactly
    once, or the edit is rejected outright rather than guessing.

    Raises:
        EditNotUniqueError: if old_string matches zero or 2+ times.
        (plus everything safe_open/atomic_write can raise)
    """
    with safe_open(workspace_root, path, "r") as f:
        content = f.read()

    occurrences = content.count(old_string)
    if occurrences == 0:
        raise EditNotUniqueError(f"old_string not found in '{path}'.")
    if occurrences > 1:
        raise EditNotUniqueError(
            f"old_string matches {occurrences} times in '{path}'; "
            "must match exactly once. Add more surrounding context."
        )

    new_content = content.replace(old_string, new_string, 1)
    full_path = resolve_in_workspace(workspace_root, path)
    atomic_write(full_path, new_content, workspace_root)

    return {"path": path, "replacements": 1}
