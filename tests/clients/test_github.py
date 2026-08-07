import json

import httpx
import pytest

from nishikihebi.clients.github import (
    HttpGitHubClient,
    Issue,
    MissingGitHubCredentialsError,
    PullRequest,
    build_github_client,
)


def token_for(repository: str) -> str:
    return f"token-for-{repository}"


def test_list_labeled_pull_requests_filters_by_label_and_excludes_non_prs():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["request"] = request
        return httpx.Response(
            200,
            json=[
                {"number": 1, "title": "a pr", "pull_request": {}},
                {"number": 2, "title": "an issue"},
            ],
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_for,
    )

    pull_requests = client.list_labeled_pull_requests(
        "kaiquekandykoga/nishikihebi", "nishikihebi"
    )

    assert pull_requests == [PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr")]
    assert captured["url"].path == "/repos/kaiquekandykoga/nishikihebi/issues"
    assert captured["url"].params["state"] == "open"
    assert captured["url"].params["labels"] == "nishikihebi"
    assert (
        captured["request"].headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_list_labeled_issues_filters_by_label_and_excludes_pull_requests():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["request"] = request
        return httpx.Response(
            200,
            json=[
                {"number": 1, "title": "a pr", "body": "pr body", "pull_request": {}},
                {"number": 2, "title": "an issue", "body": "issue body"},
            ],
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_for,
    )

    issues = client.list_labeled_issues("kaiquekandykoga/nishikihebi", "nishikihebi")

    assert issues == [
        Issue("kaiquekandykoga/nishikihebi", 2, "an issue", "issue body")
    ]
    assert captured["url"].path == "/repos/kaiquekandykoga/nishikihebi/issues"
    assert captured["url"].params["state"] == "open"
    assert captured["url"].params["labels"] == "nishikihebi"
    assert (
        captured["request"].headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_fetch_diff_requests_diff_accept_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, text="diff --git a/x b/x")

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_for,
    )

    diff = client.fetch_diff(PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr"))

    assert diff == "diff --git a/x b/x"
    assert captured["request"].url.path == "/repos/kaiquekandykoga/nishikihebi/pulls/1"
    assert captured["request"].headers["accept"] == "application/vnd.github.diff"
    assert (
        captured["request"].headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_post_comment_sends_body_to_issue_comments_endpoint():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(201, json={})

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_for,
    )

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr")
    client.post_comment(pull_request, "great work")

    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path == "/repos/kaiquekandykoga/nishikihebi/issues/1/comments"
    assert json.loads(request.content) == {"body": "great work"}
    expected_auth = "Bearer token-for-kaiquekandykoga/nishikihebi"
    assert request.headers["authorization"] == expected_auth


def test_build_github_client_raises_when_app_id_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("NISHIKIHEBI_GITHUB_APP_ID", raising=False)
    monkeypatch.setenv("NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH", str(tmp_path / "key.pem"))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(
        MissingGitHubCredentialsError, match="NISHIKIHEBI_GITHUB_APP_ID"
    ):
        build_github_client()


def test_build_github_client_raises_when_private_key_path_missing(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("NISHIKIHEBI_GITHUB_APP_ID", "app-1")
    monkeypatch.delenv("NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(
        MissingGitHubCredentialsError, match="NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH"
    ):
        build_github_client()


def test_build_github_client_constructs_http_client_with_api_version_header(
    monkeypatch, tmp_path, rsa_key_pair
):
    private_key, _public_key = rsa_key_pair
    key_path = tmp_path / "key.pem"
    key_path.write_text(private_key)
    monkeypatch.setenv("NISHIKIHEBI_GITHUB_APP_ID", "app-1")
    monkeypatch.setenv("NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH", str(key_path))

    client = build_github_client()

    assert isinstance(client, HttpGitHubClient)
    assert client.http_client.headers["x-github-api-version"] == "2022-11-28"
    assert "authorization" not in client.http_client.headers
