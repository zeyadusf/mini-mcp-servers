"""
mcp_gateway/tests/test_policy.py

Coverage for mcp_gateway/policy.py — pure decision logic, no terminal
interaction involved (that's approval.py, verified live instead).
"""

from mcp.types import Tool, ToolAnnotations
from mcp import ClientSession
from unittest.mock import Mock

from mcp_gateway.downstream import DownstreamServer
from mcp_gateway.policy import needs_approval
from mcp_gateway.registry import RegisteredTool


def make_registered(annotations: ToolAnnotations | None) -> RegisteredTool:
    tool = Tool(
        name="some_tool",
        description="desc",
        inputSchema={"type": "object"},
        annotations=annotations,
    )
    server = DownstreamServer(name="fs", session=Mock(spec=ClientSession), tools=[tool])
    return RegisteredTool(
        namespaced_name="fs__some_tool",
        original_name="some_tool",
        server=server,
        tool=tool,
    )


def test_destructive_hint_true_requires_approval():
    registered = make_registered(ToolAnnotations(destructiveHint=True))

    assert needs_approval(registered) is True


def test_destructive_hint_false_does_not_require_approval():
    registered = make_registered(
        ToolAnnotations(destructiveHint=False, readOnlyHint=True)
    )

    assert needs_approval(registered) is False


def test_no_annotations_does_not_require_approval():
    registered = make_registered(None)

    assert needs_approval(registered) is False


def test_annotations_without_destructive_hint_set_does_not_require_approval():
    """ToolAnnotations with no destructiveHint field set at all — its
    default is None/falsy, must not be treated as True."""
    registered = make_registered(ToolAnnotations(title="Some tool"))

    assert needs_approval(registered) is False
