"""
mcp_fs_server/config.py

Resolves the FS server's workspace root at startup.

Resolution order:
  1. --workspace / -w CLI argument
  2. FS_SERVER_WORKSPACE environment variable
  3. Built-in initial workspace path

The resolved workspace is fixed for the lifetime of the process, so
every filesystem operation remains scoped to the same directory.

Kept separate from server.py so it can be unit tested without
spinning up the MCP server itself.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path


logger = logging.getLogger(__name__)

INITIAL_WORKSPACE_PATH = Path(
    r"G:\__TESSERACT_AI\mini mcp servers\mini-mcp-servers"
)


class WorkspaceNotConfiguredError(RuntimeError):
    """Raised when no workspace root is configured."""


def resolve_workspace_root(argv: list[str] | None = None) -> Path:
    """
    Determine the workspace root for this server process.

    Resolution order:
        1. --workspace / -w CLI argument
        2. FS_SERVER_WORKSPACE environment variable
        3. INITIAL_WORKSPACE_PATH

    Args:
        argv: Optional explicit argv list for testing.
            If None, argparse reads the normal command-line arguments.

    Raises:
        NotADirectoryError: If the resolved workspace does not exist
            or is not a directory.

    Returns:
        The resolved workspace root.
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
        help=(
            "Root directory this server is allowed to touch. "
            "Falls back to FS_SERVER_WORKSPACE, then the initial "
            "workspace path."
        ),
    )

    args = parser.parse_args(args=argv)

    if args.workspace:
        raw_workspace = args.workspace
        source = "CLI argument"

    elif env_workspace := os.environ.get("FS_SERVER_WORKSPACE"):
        raw_workspace = env_workspace
        source = "FS_SERVER_WORKSPACE environment variable"

    else:
        raw_workspace = str(INITIAL_WORKSPACE_PATH)
        source = "initial workspace path"

    workspace_root = Path(raw_workspace).expanduser().resolve()

    if not workspace_root.is_dir():
        raise NotADirectoryError(
            f"Workspace root does not exist or is not a directory: "
            f"{workspace_root}"
        )

    logger.info(
        "Workspace root resolved from %s: %s",
        source, 
        workspace_root,
    )

    return workspace_root