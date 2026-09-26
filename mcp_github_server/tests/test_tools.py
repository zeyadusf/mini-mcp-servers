"""
mcp_github_server/tests/test_tools.py

Coverage for mcp_github_server/tools.py using httpx.MockTransport —
no real network calls, no token required. Each test builds a client
with a handler that asserts the request shape and returns a canned
GitHub-style response.
"""

import httpx
import pytest

from mcp_github_server.tools import (
    API_BASE_URL,
    GitHubAPIError,
    add_comment,
    create_issue,
    get_repo_info,
    list_issues,
    search_repos,
)


def client_with(handler) -> httpx.Client:
    return httpx.Client(base_url=API_BASE_URL, transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------
# search_repos
# ---------------------------------------------------------------------


def test_search_repos_returns_simplified_results():
    def handler(request):
        assert request.url.path == "/search/repositories"
        assert request.url.params["q"] == "mcp"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "zeyadusf/mini-mcp-servers",
                        "description": "learning project",
                        "stargazers_count": 3,
                        "html_url": "https://github.com/zeyadusf/mini-mcp-servers",
                    }
                ]
            },
        )

    result = search_repos(client_with(handler), "mcp")

    assert result == [
        {
            "full_name": "zeyadusf/mini-mcp-servers",
            "description": "learning project",
            "stars": 3,
            "url": "https://github.com/zeyadusf/mini-mcp-servers",
        }
    ]


# ---------------------------------------------------------------------
# get_repo_info
# ---------------------------------------------------------------------


def test_get_repo_info_returns_simplified_dict():
    def handler(request):
        assert request.url.path == "/repos/zeyadusf/mini-mcp-servers"
        return httpx.Response(
            200,
            json={
                "full_name": "zeyadusf/mini-mcp-servers",
                "description": "learning project",
                "stargazers_count": 3,
                "forks_count": 1,
                "open_issues_count": 2,
                "default_branch": "main",
                "html_url": "https://github.com/zeyadusf/mini-mcp-servers",
            },
        )

    result = get_repo_info(client_with(handler), "zeyadusf", "mini-mcp-servers")

    assert result["default_branch"] == "main"
    assert result["open_issues"] == 2


def test_get_repo_info_not_found_raises():
    def handler(request):
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(GitHubAPIError) as exc_info:
        get_repo_info(client_with(handler), "nobody", "nothing")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------
# list_issues
# ---------------------------------------------------------------------


def test_list_issues_filters_out_pull_requests():
    def handler(request):
        assert request.url.params["state"] == "open"
        return httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "Real issue",
                    "state": "open",
                    "html_url": "https://github.com/x/y/issues/1",
                },
                {
                    "number": 2,
                    "title": "Actually a PR",
                    "state": "open",
                    "html_url": "https://github.com/x/y/pull/2",
                    "pull_request": {"url": "..."},
                },
            ],
        )

    result = list_issues(client_with(handler), "x", "y")

    assert len(result) == 1
    assert result[0]["number"] == 1


# ---------------------------------------------------------------------
# create_issue
# ---------------------------------------------------------------------


def test_create_issue_sends_title_and_body():
    captured = {}

    def handler(request):
        import json as _json

        captured["payload"] = _json.loads(request.content)
        return httpx.Response(
            201,
            json={"number": 42, "html_url": "https://github.com/x/y/issues/42"},
        )

    result = create_issue(
        client_with(handler), "x", "y", "Bug found", body="details here"
    )

    assert captured["payload"] == {"title": "Bug found", "body": "details here"}
    assert result == {"number": 42, "url": "https://github.com/x/y/issues/42"}


def test_create_issue_omits_body_when_not_given():
    captured = {}

    def handler(request):
        import json as _json

        captured["payload"] = _json.loads(request.content)
        return httpx.Response(
            201, json={"number": 1, "html_url": "https://github.com/x/y/issues/1"}
        )

    create_issue(client_with(handler), "x", "y", "Title only")

    assert captured["payload"] == {"title": "Title only"}


# ---------------------------------------------------------------------
# add_comment
# ---------------------------------------------------------------------


def test_add_comment_posts_to_correct_issue():
    def handler(request):
        assert request.url.path == "/repos/x/y/issues/7/comments"
        return httpx.Response(
            201,
            json={"id": 999, "html_url": "https://github.com/x/y/issues/7#comment-999"},
        )

    result = add_comment(client_with(handler), "x", "y", 7, "nice work")

    assert result["id"] == 999


# ---------------------------------------------------------------------
# Error translation (shared _request path)
# ---------------------------------------------------------------------


def test_error_message_extracted_from_github_json_body():
    def handler(request):
        return httpx.Response(422, json={"message": "Validation Failed"})

    with pytest.raises(GitHubAPIError) as exc_info:
        create_issue(client_with(handler), "x", "y", "bad title")

    assert "Validation Failed" in str(exc_info.value)
    assert exc_info.value.status_code == 422


def test_error_falls_back_to_raw_text_when_not_json():
    def handler(request):
        return httpx.Response(500, text="internal server error")

    with pytest.raises(GitHubAPIError) as exc_info:
        get_repo_info(client_with(handler), "x", "y")

    assert exc_info.value.status_code == 500
