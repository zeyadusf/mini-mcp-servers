"""
mcp_gateway

The Gateway: aggregates every downstream MCP server listed in
gateway_config.yaml into one MCP server exposed to the Host, with
tool names namespaced as "{server}__{tool}". No approval/policy
enforcement yet (Phase 5).

Run standalone:

    uv run python -m mcp_gateway.server
"""
