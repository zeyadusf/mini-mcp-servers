"""
mcp-sandbox-core/path_guard.py

Utilities for safely resolving paths inside the user's workspace.

This module ensures that file operations cannot escape the configured
workspace directory through path traversal, absolute paths, or symlinks.

This module is pure path-resolution logic only — it never touches the
filesystem beyond resolve(), and never opens files. See file_ops.py
for sandboxed file I/O.
"""

from pathlib import Path

from mcp_sandbox_core.sandbox_exception import PathEscapesWorkspaceError


def resolve_in_workspace(workspace_root: Path, user_path: str | Path) -> Path:
    """
    Resolve a user-supplied path and ensure it remains inside
    the configured workspace.

    Args:
        workspace_root: The root workspace directory.
        user_path: Relative path supplied by the user.

    Returns:
        A resolved absolute Path inside the workspace.

    Raises:
        PathEscapesWorkspaceError:
            If the path escapes the workspace or an absolute path
            is supplied.
    """
    workspace_root = workspace_root.resolve()
    # Normalize input.
    user_path = Path(user_path)

    # Absolute paths are never allowed.
    if user_path.is_absolute():
        raise PathEscapesWorkspaceError("Absolute paths are not allowed.")

    # Resolve against the workspace.
    candidate = (workspace_root / user_path).resolve(strict=False)

    # Ensure the resolved path is still inside the workspace.
    if not candidate.is_relative_to(workspace_root):
        raise PathEscapesWorkspaceError("Path escapes the workspace.")

    return candidate
