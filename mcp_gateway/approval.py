"""
mcp_gateway/approval.py

The actual HITL gate: a blocking terminal prompt, with a per-tool
preview renderer so the person approving sees a readable summary
instead of raw JSON args.

Deliberately impure (input()/print()) and NOT unit tested directly —
same split as server.py/downstream.py elsewhere in this project: this
is I/O wiring, policy.py carries the testable decision logic.

Adding a new destructive tool to a server never requires touching this
file: a tool with no specific renderer just gets the generic
key=value fallback. Add a renderer here only when the generic fallback
genuinely isn't readable enough.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp_gateway.registry import RegisteredTool

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


@_renderer("fs", "write_file")
def _preview_write_file(args: dict[str, Any]) -> str:
    content = str(args.get("content", ""))
    if len(content) > 300:
        content = content[:300] + "... (truncated)"
    return f"path: {args.get('path')}\n---\n{content}"


@_renderer("fs", "edit_file")
def _preview_edit_file(args: dict[str, Any]) -> str:
    return (
        f"path: {args.get('path')}\n"
        f"- {args.get('old_string')}\n"
        f"+ {args.get('new_string')}"
    )


@_renderer("github", "create_issue")
def _preview_create_issue(args: dict[str, Any]) -> str:
    return (
        f"repo: {args.get('owner')}/{args.get('repo')}\n"
        f"title: {args.get('title')}\n"
        f"body: {args.get('body') or '(none)'}"
    )


@_renderer("github", "add_comment")
def _preview_add_comment(args: dict[str, Any]) -> str:
    return (
        f"repo: {args.get('owner')}/{args.get('repo')}#{args.get('issue_number')}\n"
        f"comment: {args.get('body')}"
    )


def _render_preview(registered: RegisteredTool, arguments: dict[str, Any]) -> str:
    renderer = _PREVIEW_RENDERERS.get(
        (registered.server.name, registered.original_name)
    )
    if renderer is not None:
        return renderer(arguments)
    args_str = (
        "\n".join(f"  {k}: {v}" for k, v in arguments.items()) or "  (no arguments)"
    )
    return args_str


def request_approval(registered: RegisteredTool, arguments: dict[str, Any]) -> bool:
    """Blocking y/n prompt on stdin/stdout. Returns True iff approved."""
    print("\n" + "=" * 60)
    print(f"APPROVAL REQUIRED: {registered.namespaced_name}")
    print("-" * 60)
    print(_render_preview(registered, arguments))
    print("=" * 60)
    answer = input("Approve? (y/n): ").strip().lower()
    return answer == "y"
