"""
mcp_gateway/approval.py

The HITL gate, implemented with MCP *elicitation*: the Gateway asks the
Host (VS Code, Claude Desktop, ...) to show the approval dialog, and the
answer comes back over the same JSON-RPC channel.

Why not input()/print(): the Gateway talks to the Host over stdio, so
stdout IS the protocol wire and stdin IS the Host's request stream.
Printing a prompt corrupts the JSON-RPC stream ("Failed to parse
message") and input() blocks forever waiting on a pipe nobody types
into. Nothing in this package may write to stdout or read from stdin.

Fail closed: if the Host doesn't support elicitation, or the elicitation
request errors out, the call is DENIED. There is no fallback to a
terminal prompt and no auto-approve.

Adding a new destructive tool to a server never requires touching this
file: a tool with no specific renderer just gets the generic
key: value fallback. Add a renderer only when that isn't readable enough.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from mcp import types
from mcp.server.session import ServerSession

from mcp_gateway.registry import RegisteredTool

logger = logging.getLogger(__name__)

_MAX_FIELD_CHARS = 300

_PREVIEW_RENDERERS: dict[tuple[str, str], Callable[[dict[str, Any]], str]] = {}


def _renderer(
    server_name: str, tool_name: str
) -> Callable[[Callable[[dict[str, Any]], str]], Callable[[dict[str, Any]], str]]:
    def decorator(
        fn: Callable[[dict[str, Any]], str],
    ) -> Callable[[dict[str, Any]], str]:
        _PREVIEW_RENDERERS[(server_name, tool_name)] = fn
        return fn

    return decorator


def _truncate(value: Any, limit: int = _MAX_FIELD_CHARS) -> str:
    text = str(value)
    if len(text) > limit:
        return text[:limit] + f"... (truncated, {len(text)} chars total)"
    return text


@_renderer("fs", "write_file")
def _preview_write_file(args: dict[str, Any]) -> str:
    return f"path: {args.get('path')}\n---\n{_truncate(args.get('content', ''))}"


@_renderer("fs", "edit_file")
def _preview_edit_file(args: dict[str, Any]) -> str:
    return (
        f"path: {args.get('path')}\n"
        f"- {_truncate(args.get('old_string'))}\n"
        f"+ {_truncate(args.get('new_string'))}"
    )


@_renderer("github", "create_issue")
def _preview_create_issue(args: dict[str, Any]) -> str:
    return (
        f"repo: {args.get('owner')}/{args.get('repo')}\n"
        f"title: {args.get('title')}\n"
        f"body: {_truncate(args.get('body') or '(none)')}"
    )


@_renderer("github", "add_comment")
def _preview_add_comment(args: dict[str, Any]) -> str:
    return (
        f"repo: {args.get('owner')}/{args.get('repo')}#{args.get('issue_number')}\n"
        f"comment: {_truncate(args.get('body'))}"
    )


def _render_preview(registered: RegisteredTool, arguments: dict[str, Any]) -> str:
    renderer = _PREVIEW_RENDERERS.get(
        (registered.server.name, registered.original_name)
    )
    if renderer is not None:
        return renderer(arguments)
    return (
        "\n".join(f"  {k}: {_truncate(v)}" for k, v in arguments.items())
        or "  (no arguments)"
    )


def _client_supports_elicitation(session: ServerSession) -> bool:
    return session.check_client_capability(
        types.ClientCapabilities(elicitation=types.ElicitationCapability())
    )


async def request_approval(
    session: ServerSession,
    registered: RegisteredTool,
    arguments: dict[str, Any],
    related_request_id: types.RequestId | None = None,
) -> bool:
    """Ask the Host to show an approve/deny dialog. True iff approved."""
    if not _client_supports_elicitation(session):
        logger.warning(
            "Host does not support elicitation — denying '%s' (fail closed).",
            registered.namespaced_name,
        )
        return False

    message = (
        f"Approval required: {registered.namespaced_name}\n\n"
        f"{_render_preview(registered, arguments)}"
    )
    schema: types.ElicitRequestedSchema = {
        "type": "object",
        "properties": {
            "approve": {
                "type": "boolean",
                "title": "Approve this action",
                "default": False,
            }
        },
        "required": ["approve"],
    }

    try:
        # `elicit_form` is the current name; `elicit` is its deprecated alias.
        result = await session.elicit_form(
            message=message,
            requestedSchema=schema,
            related_request_id=related_request_id,
        )
    except Exception:
        logger.exception(
            "Elicitation failed for '%s' — denying (fail closed).",
            registered.namespaced_name,
        )
        return False

    return (
        result.action == "accept"
        and result.content is not None
        and result.content.get("approve") is True
    )