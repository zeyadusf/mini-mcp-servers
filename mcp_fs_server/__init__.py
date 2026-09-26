"""
mcp_fs_server

Standalone MCP server exposing sandboxed filesystem tools
(list_directory, read_file, write_file, edit_file). Built on
mcp_sandbox_core for all path-boundary and sensitivity enforcement.

Run standalone (never import this into another process directly —
launch it as its own process, same as the Gateway will):

    uv run mcp dev mcp_fs_server/server.py -- --workspace /path/to/sandbox
"""
