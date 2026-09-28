"""
mcp_gateway/policy.py

Pure decision logic: does calling this tool require human approval
before the Gateway forwards it downstream? Kept separate from
approval.py (the actual blocking prompt) so the decision itself is
unit-testable without any terminal interaction — same split used
everywhere else in this project (tools.py vs server.py).

Decision rule: a tool needs approval iff its MCP annotations declare
destructiveHint=True. Both of our own servers (fs, github) set this
explicitly on every write/create/comment tool. A tool with no
annotations at all is treated as NOT requiring approval — a server
that doesn't bother declaring annotations shouldn't have every one of
its tools silently blocked; annotation hygiene is that server's
responsibility, not something the Gateway can fix by guessing.
"""

from __future__ import annotations

from mcp_gateway.registry import RegisteredTool


def needs_approval(registered: RegisteredTool) -> bool:
    annotations = registered.tool.annotations
    if annotations is None:
        return False
    return bool(annotations.destructiveHint)
