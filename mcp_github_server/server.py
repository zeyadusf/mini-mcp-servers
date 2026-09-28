"""
mcp_github_server/server.py

MCP server exposing GitHub API tools over stdio. Thin wiring layer
only — same split as mcp_fs_server: real logic in tools.py, HTTP
client built once at startup and reused across calls.

Test standalone with MCP Inspector before wiring into the Gateway:

    GITHUB_TOKEN=ghp_xxx uv run mcp dev mcp_github_server/server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_github_server import tools
from mcp_github_server.config import resolve_github_token

mcp = FastMCP("mini-mcp-github-server")

_TOKEN = resolve_github_token()
_CLIENT = tools.build_client(_TOKEN)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Search repositories",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=True,
    )
)
def search_repos(query: str, limit: int = 10) -> list[dict]:
    """Search public GitHub repositories matching `query`."""
    return tools.search_repos(_CLIENT, query, limit)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get repository info",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=True,
    )
)
def get_repo_info(owner: str, repo: str) -> dict:
    """Get details for a single repository (owner/repo)."""
    return tools.get_repo_info(_CLIENT, owner, repo)


@mcp.tool(
    annotations=ToolAnnotations(
        title="List issues",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=True,
    )
)
def list_issues(
    owner: str, repo: str, state: str = "open", limit: int = 10
) -> list[dict]:
    """List issues for a repository. state: 'open' | 'closed' | 'all'."""
    return tools.list_issues(_CLIENT, owner, repo, state, limit)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Create issue",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    )
)
def create_issue(owner: str, repo: str, title: str, body: str | None = None) -> dict:
    """Create a new issue in owner/repo."""
    return tools.create_issue(_CLIENT, owner, repo, title, body)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Add comment",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    )
)
def add_comment(owner: str, repo: str, issue_number: int, body: str) -> dict:
    """Add a comment to an existing issue or PR."""
    return tools.add_comment(_CLIENT, owner, repo, issue_number, body)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
