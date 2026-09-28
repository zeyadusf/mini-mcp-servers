"""
mcp_github_server/config.py

Resolves the GitHub auth token at startup. Same philosophy as
mcp_fs_server/config.py: refuse to start rather than silently run
unauthenticated (unauthenticated GitHub API calls are heavily rate
limited and create_issue/add_comment need a token regardless).

Resolution: GITHUB_TOKEN environment variable only, for now — no CLI
flag, since a token has no sane non-secret way to pass via argv
(shell history). If a --token flag is wanted later, it should read
from a file path, not the raw value.
"""

from __future__ import annotations

import os

from .env import GITHUB_TOKEN

API_BASE_URL = "https://api.github.com"


class GitHubTokenNotConfiguredError(RuntimeError):
    """Raised when GITHUB_TOKEN is not set."""


def resolve_github_token() -> str:

    token = GITHUB_TOKEN or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubTokenNotConfiguredError(
            "GITHUB_TOKEN environment variable is not set. "
            "Create a personal access token and export it before starting this server."
        )
    return token
