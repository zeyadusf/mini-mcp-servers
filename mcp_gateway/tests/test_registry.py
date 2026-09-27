"""
mcp_gateway/tests/test_registry.py

Coverage for mcp_gateway/registry.py using fake DownstreamServer/Tool
objects — no real subprocess or MCP session involved, since
registry.py is deliberately pure Python (see its module docstring).
"""

import pytest
from unittest.mock import Mock
from mcp import ClientSession
from mcp.types import Tool


from mcp_gateway.downstream import DownstreamServer
from mcp_gateway.registry import (
    DuplicateToolError,
    UnknownToolError,
    build_registry,
)


def fake_tool(name: str) -> Tool:
    return Tool(
        name=name, description=f"desc for {name}", inputSchema={"type": "object"}
    )


def fake_server(name: str, tool_names: list[str]) -> DownstreamServer:
    return DownstreamServer(
        name=name,
        session=Mock(spec=ClientSession),
        tools=[fake_tool(t) for t in tool_names],
    )


def test_namespaces_tools_with_double_underscore():
    servers = [fake_server("fs", ["read_file", "write_file"])]

    registry = build_registry(servers)

    names = {rt.namespaced_name for rt in registry.all_tools()}
    assert names == {"fs__read_file", "fs__write_file"}


def test_same_tool_name_on_different_servers_does_not_collide():
    servers = [
        fake_server("rag", ["search"]),
        fake_server("research", ["search"]),
    ]

    registry = build_registry(servers)

    names = {rt.namespaced_name for rt in registry.all_tools()}
    assert names == {"rag__search", "research__search"}


def test_resolve_returns_correct_server_and_original_name():
    servers = [fake_server("github", ["create_issue"])]
    registry = build_registry(servers)

    resolved = registry.resolve("github__create_issue")

    assert resolved.server.name == "github"
    assert resolved.original_name == "create_issue"


def test_resolve_unknown_tool_raises():
    registry = build_registry([fake_server("fs", ["read_file"])])

    with pytest.raises(UnknownToolError):
        registry.resolve("fs__does_not_exist")


def test_duplicate_server_name_registration_raises():
    """Defense-in-depth: config.py should already reject duplicate
    server names, but the registry must not silently merge tools from
    two servers that ended up with the same name."""
    from mcp_gateway.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register_server(fake_server("fs", ["read_file"]))

    with pytest.raises(DuplicateToolError):
        registry.register_server(fake_server("fs", ["read_file"]))
