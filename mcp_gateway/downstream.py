"""
mcp_gateway/downstream.py

Connects to each configured downstream MCP server as a subprocess (the
Gateway acting as an MCP *client*), and keeps every connection alive
for the Gateway process's lifetime via a shared AsyncExitStack owned
by the caller (server.py).

Design decision: graceful degradation. connect_downstream() never
raises for a single server's connection failure — it logs and returns
None. connect_all() drops failed servers and continues with whatever
connected successfully. A bad/misconfigured downstream server (e.g.
GITHUB_TOKEN not set) must not take the whole Gateway down; the
person just won't see that server's tools, with a clear log line
explaining why.

Design decision: sequential connection, not concurrent (asyncio.gather).
Simpler to reason about and debug for a learning project; startup time
for 2-3 local subprocesses is not a real concern here.
"""

from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

from mcp_gateway.config import ServerConfig

logger = logging.getLogger(__name__)


@dataclass
class DownstreamServer:
    name: str
    session: ClientSession
    tools: list[Tool]


async def connect_downstream(
    config: ServerConfig, stack: AsyncExitStack
) -> DownstreamServer | None:
    """
    Launch one downstream server as a subprocess and connect to it.

    `stack` is entered into, not closed here — the connection (and the
    subprocess) stays alive as long as `stack` is open, i.e. for the
    Gateway's whole run. Returns None on any failure; never raises.
    """
    params = StdioServerParameters(
        command=config.command, args=config.args, env=os.environ.copy()
    )
    try:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        result = await session.list_tools()
    except Exception:
        logger.exception(
            "Failed to connect to downstream server '%s' (command: %s %s) — "
            "skipping it, its tools will not be available.",
            config.name,
            config.command,
            " ".join(config.args),
        )
        return None

    logger.info(
        "Connected to '%s': %d tool(s) discovered.", config.name, len(result.tools)
    )
    return DownstreamServer(name=config.name, session=session, tools=result.tools)


async def connect_all(
    configs: list[ServerConfig], stack: AsyncExitStack
) -> list[DownstreamServer]:
    """
    Connect to every configured server. Failures are logged and
    skipped (see module docstring). Raises only if EVERY server
    failed — a Gateway with zero working downstream servers has
    nothing to serve and should not start.
    """
    connected = []
    for config in configs:
        server = await connect_downstream(config, stack)
        if server is not None:
            connected.append(server)

    if not connected:
        raise RuntimeError(
            "No downstream servers connected successfully — Gateway has nothing to serve."
        )
    return connected
