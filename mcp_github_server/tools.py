"""
mcp_github_server/tools.py

Pure implementation functions for the GitHub server's tools, kept
independent of the MCP protocol layer (server.py) — same split as
mcp_fs_server/tools.py, for the same reason: testable directly, no
MCP client/server needed.

Every function takes an httpx.Client explicitly (built once in
server.py, reused across calls) rather than constructing its own —
that's what makes these testable with httpx.MockTransport instead of
hitting real GitHub.
"""

from __future__ import annotations

from typing import Any

import httpx

from mcp_github_server.config import API_BASE_URL


class GitHubAPIError(Exception):
    """Raised when GitHub's API returns an error response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"GitHub API error {status_code}: {message}")


def build_client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=15.0,
    )


def _request(client: httpx.Client, method: str, url: str, **kwargs: Any) -> Any:
    """Shared request/error-translation path for every tool below.

    Deliberately no retry/backoff here (per project ADR: let rate-limit
    and transient errors fail with a clear message rather than hide
    them behind internal retries — the calling agent decides whether
    to retry).
    """
    response = client.request(method, url, **kwargs)
    if response.is_error:
        message = response.text
        try:
            message = response.json().get("message", message)
        except ValueError:
            # Response body wasn't JSON; keep the raw text as the message.
            pass
        raise GitHubAPIError(response.status_code, message)
    if response.status_code == 204:
        return None
    return response.json()


# ---------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------


def search_repos(client: httpx.Client, query: str, limit: int = 10) -> list[dict]:
    """Search public repositories matching `query`."""
    data = _request(
        client, "GET", "/search/repositories", params={"q": query, "per_page": limit}
    )
    return [
        {
            "full_name": item["full_name"],
            "description": item["description"],
            "stars": item["stargazers_count"],
            "url": item["html_url"],
        }
        for item in data["items"]
    ]


def get_repo_info(client: httpx.Client, owner: str, repo: str) -> dict:
    """Get details for a single repository."""
    data = _request(client, "GET", f"/repos/{owner}/{repo}")
    return {
        "full_name": data["full_name"],
        "description": data["description"],
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "open_issues": data["open_issues_count"],
        "default_branch": data["default_branch"],
        "url": data["html_url"],
    }


def list_issues(
    client: httpx.Client, owner: str, repo: str, state: str = "open", limit: int = 10
) -> list[dict]:
    """List issues for a repository. state: 'open' | 'closed' | 'all'."""
    data = _request(
        client,
        "GET",
        f"/repos/{owner}/{repo}/issues",
        params={"state": state, "per_page": limit},
    )
    # GitHub's issues endpoint also returns PRs; filter them out since
    # this tool is documented as issues-only.
    return [
        {
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "url": item["html_url"],
        }
        for item in data
        if "pull_request" not in item
    ]


# ---------------------------------------------------------------------
# Destructive tools
# ---------------------------------------------------------------------


def create_issue(
    client: httpx.Client, owner: str, repo: str, title: str, body: str | None = None
) -> dict:
    """Create a new issue."""
    payload: dict[str, Any] = {"title": title}
    if body is not None:
        payload["body"] = body
    data = _request(client, "POST", f"/repos/{owner}/{repo}/issues", json=payload)
    return {"number": data["number"], "url": data["html_url"]}


def add_comment(
    client: httpx.Client, owner: str, repo: str, issue_number: int, body: str
) -> dict:
    """Add a comment to an existing issue (or PR, GitHub treats PRs as issues here)."""
    data = _request(
        client,
        "POST",
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        json={"body": body},
    )
    return {"id": data["id"], "url": data["html_url"]}
