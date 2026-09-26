"""
mcp_fs_server/config.py

Resolves the FS server's workspace root at startup. This is
deliberately NOT hardcoded and NOT defaulted to cwd silently — every
tool call is scoped to this one directory for the lifetime of the
process, so getting it wrong silently would be a real security bug,
not just an inconvenience.

Resolution order:
  1. --workspace / -w CLI argument
  2. FS_SERVER_WORKSPACE environment variable
  3. neither set -> raise, refuse to start

Kept separate from server.py so it can be unit tested without
spinning up the MCP server itself.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


class WorkspaceNotConfiguredError(RuntimeError):
    """Raised when no workspace root was supplied via CLI arg or env var."""


def resolve_workspace_root(argv: list[str] | None = None) -> Path:
    """
    Determine the workspace root for this server process.

    Args:
        argv: Optional explicit argv list (for testing). Defaults to
            parsing sys.argv via argparse's normal behavior.

    Raises:
        WorkspaceNotConfiguredError: if no workspace was supplied.
        NotADirectoryError: if the resolved path doesn't exist or
            isn't a directory.
    """
    parser = argparse.ArgumentParser(
        prog="mcp-fs-server",
        description="MCP server exposing sandboxed filesystem tools.",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        dest="workspace",
        default=None,
        help="Root directory this server is allowed to touch. "
        "Falls back to FS_SERVER_WORKSPACE env var if omitted.",
    )
    args = parser.parse_args(args=argv)

    raw = args.workspace or os.environ.get("FS_SERVER_WORKSPACE")
    if not raw:
        raise WorkspaceNotConfiguredError(
            "No workspace root configured. Pass --workspace <path> or "
            "set the FS_SERVER_WORKSPACE environment variable."
        )

    workspace_root = Path(raw).expanduser().resolve()
    if not workspace_root.is_dir():
        raise NotADirectoryError(f"Workspace root does not exist: {workspace_root}")

    return workspace_root
