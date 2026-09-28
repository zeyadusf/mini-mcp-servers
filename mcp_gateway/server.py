"""
mcp_gateway/server.py

The Gateway itself: an MCP server (talks to the Host over stdio) that
is ALSO an MCP client to every downstream server (talks to each one
over its own stdio subprocess). This is why it uses the low-level
`mcp.server.Server` API rather than FastMCP — FastMCP's decorator
style assumes a static, known-at-import-time set of tools; here the
tool set is only known after connecting to whatever servers the
config lists, so `list_tools`/`call_tool` have to be dynamic handlers
that read from the ToolRegistry built at startup.

No approval/policy enforcement yet — that's Phase 5. This phase is
aggregation and routing only: prove the Host -> Gateway -> downstream
-> Gateway -> Host round trip works end to end.

Run standalone:

    uv run python -m mcp_gateway.server
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_gateway.approval import request_approval
from mcp_gateway.config import load_gateway_config
from mcp_gateway.downstream import connect_all
from mcp_gateway.policy import needs_approval
from mcp_gateway.registry import ToolRegistry, UnknownToolError, build_registry

logging.basicConfig(
    level=logging.INFO, stream=None
)  # stderr by default — stdout is the MCP wire
logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent / "gateway_config.yaml"

app = Server("mini-mcp-gateway")

# Set once at startup by main(). Not per-call state — the registry is
# built once when the Gateway connects to its downstream servers, and
# is read-only for the rest of the process's life.
_registry: ToolRegistry | None = None


def _get_registry() -> ToolRegistry:
    if _registry is None:
        raise RuntimeError(
            "Gateway registry accessed before startup completed — this is a bug, "
            "not a runtime condition the Host can trigger."
        )
    return _registry


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    registry = _get_registry()
    return [
        types.Tool(
            name=rt.namespaced_name,
            description=rt.tool.description,
            inputSchema=rt.tool.inputSchema,
            annotations=rt.tool.annotations,
        )
        for rt in registry.all_tools()
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:
    registry = _get_registry()
    try:
        registered = registry.resolve(name)
    except UnknownToolError as e:
        return [types.TextContent(type="text", text=f"ERROR: {e}")]

    logger.info(
    "Tool call received: %s | arguments=%s",
    name,
    arguments,
)
    if needs_approval(registered) and not request_approval(registered, arguments):
        # Declined, not failed: this goes back to the model as a normal
        # tool result (not an exception), same as any other tool
        # outcome — the model can react (rephrase, ask the user, give
        # up on this step) instead of the whole turn erroring out.
        return [
            types.TextContent(
                type="text", text=f"Tool call '{name}' was declined by the user."
            )
        ]

    result = await registered.server.session.call_tool(
        registered.original_name, arguments
    )
    logger.info(
    "Tool '%s' completed successfully",
    name,)
    return result.content


async def _run(config_path: Path) -> None:
    global _registry

    configs = load_gateway_config(config_path)
    async with AsyncExitStack() as stack:
        servers = await connect_all(configs, stack)
        _registry = build_registry(servers)
        logger.info(
            "Gateway ready: %d tool(s) across %d server(s).",
            len(_registry.all_tools()),
            len(servers),
        )

        async with stdio_server() as (read, write):
            await app.run(read, write, app.create_initialization_options())


def main() -> None:
    config_path = Path(os.environ.get("GATEWAY_CONFIG_PATH", DEFAULT_CONFIG_PATH))
    asyncio.run(_run(config_path))


if __name__ == "__main__":
    main()
