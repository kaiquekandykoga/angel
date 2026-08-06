import json

import httpx
import pytest

from nishikihebi.github_client import (
    HttpGitHubClient,
    MissingGitHubTokenError,
    PullRequest,
    build_github_client,
)


def test_list_labeled_pull_requests_filters_by_label_and_excludes_non_prs():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        return httpx.Response(
            200,
            json=[
                {"number": 1, "title": "a pr", "pull_request": {}},
                {"number": 2, "title": "an issue"},
            ],
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")
    )

    pull_requests = client.list_labeled_pull_requests(
        "kaiquekandykoga/nishikihebi", "nishikihebi"
    )

    assert pull_requests == [PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr")]
    assert captured["url"].path == "/repos/kaiquekandykoga/nishikihebi/issues"
    assert captured["url"].params["state"] == "open"
    assert captured["url"].params["labels"] == "nishikihebi"


def test_fetch_diff_requests_diff_accept_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, text="diff --git a/x b/x")

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")
    )

    diff = client.fetch_diff(PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr"))

    assert diff == "diff --git a/x b/x"
    assert captured["request"].url.path == "/repos/kaiquekandykoga/nishikihebi/pulls/1"
    assert captured["request"].headers["accept"] == "application/vnd.github.diff"


def test_post_comment_sends_body_to_issue_comments_endpoint():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(201, json={})

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")
    )

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr")
    client.post_comment(pull_request, "great work")

    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path == "/repos/kaiquekandykoga/nishikihebi/issues/1/comments"
    assert json.loads(request.content) == {"body": "great work"}


def test_build_github_client_raises_when_token_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(MissingGitHubTokenError, match="GITHUB_TOKEN"):
        build_github_client()


def test_build_github_client_constructs_http_client_with_auth_header(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    client = build_github_client()

    assert isinstance(client, HttpGitHubClient)
    assert client.http_client.headers["authorization"] == "Bearer test-token"
    assert client.http_client.headers["x-github-api-version"] == "2022-11-28"
