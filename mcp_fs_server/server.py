"""
mcp_fs_server/server.py

MCP server exposing sandboxed filesystem tools over stdio. Thin
wiring layer only — all real logic lives in tools.py, all
boundary/sensitivity enforcement lives in mcp_sandbox_core. This file
just: resolves the workspace root at startup, registers each tool
with the MCP SDK, translates our internal exceptions into whatever
shape the SDK expects, and runs the stdio transport.

This server is designed to run standalone — test it directly with
the MCP Inspector before wiring it into the Gateway:

    uv run mcp dev mcp_fs_server/server.py -- --workspace /path/to/sandbox

or with the env var instead of the flag:

    FS_SERVER_WORKSPACE=/path/to/sandbox uv run mcp dev mcp_fs_server/server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_fs_server import tools
from mcp_fs_server.config import resolve_workspace_root

mcp = FastMCP("mini-mcp-fs-server")

# Resolved once at import/startup time. A single server process is
# scoped to one workspace for its whole lifetime — not per-call.
WORKSPACE_ROOT = resolve_workspace_root()


@mcp.tool(
    annotations=ToolAnnotations(
        title="List directory",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def list_directory(path: str = ".", show_hidden: bool = False) -> list[dict]:
    """List files and subdirectories at `path` (relative to the workspace root)."""
    return tools.list_directory(WORKSPACE_ROOT, path, show_hidden)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Read file",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def read_file(path: str) -> str:
    """Read and return the full text content of `path`."""
    return tools.read_file(WORKSPACE_ROOT, path)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Write file",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def write_file(path: str, content: str) -> dict:
    """Create or fully overwrite `path` with `content`."""
    return tools.write_file(WORKSPACE_ROOT, path, content)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Edit file",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
)
def edit_file(path: str, old_string: str, new_string: str) -> dict:
    """
    Replace exactly one occurrence of old_string with new_string in
    an existing file. old_string must be unique within the file —
    include enough surrounding context if it isn't.
    """
    return tools.edit_file(WORKSPACE_ROOT, path, old_string, new_string)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
