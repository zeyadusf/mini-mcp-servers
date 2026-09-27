"""
mcp_gateway/registry.py

Aggregates tools from every connected downstream server into one
namespaced registry, and resolves a namespaced tool call back to the
(server, original tool name) that must actually handle it.

Namespacing: "{server_name}__{tool_name}" — double underscore, not a
dot. MCP hosts (Claude Desktop specifically) validate tool names
against ^[a-zA-Z0-9_]{1,64}$, which rejects dots; underscore is the
only separator that's safe everywhere. See project ADR log.

Pure Python, no MCP protocol or subprocess involved — deliberately
kept that way so this is unit-testable with plain fake objects (see
tests/test_registry.py), same split-for-testability pattern used in
every other package in this project.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcp.types import Tool

from mcp_gateway.downstream import DownstreamServer

SEPARATOR = "__"


@dataclass
class RegisteredTool:
    namespaced_name: str
    original_name: str
    server: DownstreamServer
    tool: Tool  # original Tool definition — schema, description, annotations


class DuplicateToolError(Exception):
    """Raised if namespacing still produces a collision (should only
    happen if two servers share a name — config.py should already have
    rejected that, so this is a defense-in-depth check)."""


class UnknownToolError(KeyError):
    """Raised when the Host calls a tool name the registry doesn't have."""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register_server(self, server: DownstreamServer) -> None:
        for tool in server.tools:
            namespaced = f"{server.name}{SEPARATOR}{tool.name}"
            if namespaced in self._tools:
                raise DuplicateToolError(
                    f"Tool name collision after namespacing: '{namespaced}'"
                )
            self._tools[namespaced] = RegisteredTool(
                namespaced_name=namespaced,
                original_name=tool.name,
                server=server,
                tool=tool,
            )

    def all_tools(self) -> list[RegisteredTool]:
        return list(self._tools.values())

    def resolve(self, namespaced_name: str) -> RegisteredTool:
        try:
            return self._tools[namespaced_name]
        except KeyError:
            raise UnknownToolError(f"Unknown tool: '{namespaced_name}'") from None


def build_registry(servers: list[DownstreamServer]) -> ToolRegistry:
    registry = ToolRegistry()
    for server in servers:
        registry.register_server(server)
    return registry
