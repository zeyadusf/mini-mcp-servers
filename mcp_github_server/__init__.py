"""
mcp_github_server

Standalone MCP server exposing GitHub API tools (search_repos,
get_repo_info, list_issues, create_issue, add_comment). Requires
GITHUB_TOKEN in the environment.

Run standalone:

    GITHUB_TOKEN=ghp_xxx uv run mcp dev mcp_github_server/server.py
"""
