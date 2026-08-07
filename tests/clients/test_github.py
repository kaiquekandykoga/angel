import json

import httpx
import pytest

from nishikihebi.clients.github import (
    Comment,
    HttpGitHubClient,
    Issue,
    MissingGitHubCredentialsError,
    PullRequest,
    build_github_client,
)


class FakeTokenProvider:
    def __init__(self, repositories: list[str] | None = None) -> None:
        self.repositories = repositories or []

    def __call__(self, repository: str) -> str:
        return f"token-for-{repository}"

    def list_repositories(self) -> list[str]:
        return self.repositories


token_provider = FakeTokenProvider()


def test_list_repositories_comes_from_the_token_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url.path}")

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        FakeTokenProvider(["org/a", "org/b"]),
    )

    assert client.list_repositories() == ["org/a", "org/b"]


def test_list_open_pull_requests_maps_head_sha_and_null_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["request"] = request
        return httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "a pr",
                    "body": None,
                    "head": {"sha": "abc123"},
                    "labels": [{"name": "nishikihebi"}],
                }
            ],
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_provider,
    )

    pull_requests = client.list_open_pull_requests(
        "kaiquekandykoga/nishikihebi", "nishikihebi"
    )

    assert pull_requests == [
        PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr", "", "abc123")
    ]
    assert captured["url"].path == "/repos/kaiquekandykoga/nishikihebi/pulls"
    assert captured["url"].params["state"] == "open"
    assert captured["url"].params["per_page"] == "100"
    assert (
        captured["request"].headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_list_open_pull_requests_drops_prs_without_the_label():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "labeled",
                    "body": None,
                    "head": {"sha": "abc123"},
                    "labels": [{"name": "nishikihebi"}],
                },
                {
                    "number": 2,
                    "title": "unlabeled",
                    "body": None,
                    "head": {"sha": "def456"},
                    "labels": [{"name": "other"}],
                },
            ],
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_provider,
    )

    pull_requests = client.list_open_pull_requests(
        "kaiquekandykoga/nishikihebi", "nishikihebi"
    )

    assert pull_requests == [
        PullRequest("kaiquekandykoga/nishikihebi", 1, "labeled", "", "abc123")
    ]


def test_list_open_issues_excludes_pull_requests_and_maps_updated_at():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["request"] = request
        return httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "a pr",
                    "body": "pr body",
                    "updated_at": "2026-08-01T00:00:00Z",
                    "pull_request": {},
                },
                {
                    "number": 2,
                    "title": "an issue",
                    "body": "issue body",
                    "updated_at": "2026-08-02T00:00:00Z",
                },
            ],
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_provider,
    )

    issues = client.list_open_issues("kaiquekandykoga/nishikihebi", "nishikihebi")

    assert issues == [
        Issue(
            "kaiquekandykoga/nishikihebi",
            2,
            "an issue",
            "issue body",
            "2026-08-02T00:00:00Z",
        )
    ]
    assert captured["url"].path == "/repos/kaiquekandykoga/nishikihebi/issues"
    assert captured["url"].params["state"] == "open"
    assert captured["url"].params["per_page"] == "100"
    assert captured["url"].params["labels"] == "nishikihebi"
    assert (
        captured["request"].headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_fetch_commit_date_returns_committer_date():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200, json={"commit": {"committer": {"date": "2026-08-03T00:00:00Z"}}}
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_provider,
    )

    date = client.fetch_commit_date("kaiquekandykoga/nishikihebi", "abc123")

    assert date == "2026-08-03T00:00:00Z"
    assert (
        captured["request"].url.path
        == "/repos/kaiquekandykoga/nishikihebi/commits/abc123"
    )
    assert (
        captured["request"].headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_list_comments_maps_login_body_and_created_at():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["request"] = request
        return httpx.Response(
            200,
            json=[
                {
                    "user": {"login": "kandy-nishikihebi[bot]"},
                    "body": None,
                    "created_at": "2026-08-04T00:00:00Z",
                }
            ],
        )

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_provider,
    )

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr", "", "abc123")
    comments = client.list_comments(pull_request)

    assert comments == [Comment("kandy-nishikihebi[bot]", "", "2026-08-04T00:00:00Z")]
    assert (
        captured["url"].path
        == "/repos/kaiquekandykoga/nishikihebi/issues/1/comments"
    )
    assert captured["url"].params["per_page"] == "100"
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
        token_provider,
    )

    diff = client.fetch_diff(
        PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr", "", "abc123")
    )

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
        token_provider,
    )

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr", "", "abc123")
    client.post_comment(pull_request, "great work")

    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path == "/repos/kaiquekandykoga/nishikihebi/issues/1/comments"
    assert json.loads(request.content) == {"body": "great work"}
    expected_auth = "Bearer token-for-kaiquekandykoga/nishikihebi"
    assert request.headers["authorization"] == expected_auth


def test_ensure_label_does_not_post_when_label_already_exists():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"name": "nishikihebi"})

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_provider,
    )

    client.ensure_label("kaiquekandykoga/nishikihebi", "nishikihebi", "f709c2")

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert (
        requests[0].url.path
        == "/repos/kaiquekandykoga/nishikihebi/labels/nishikihebi"
    )


def test_ensure_label_creates_label_when_missing():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(201, json={"name": "nishikihebi"})

    client = HttpGitHubClient(
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        token_provider,
    )

    client.ensure_label("kaiquekandykoga/nishikihebi", "nishikihebi", "f709c2")

    assert [request.method for request in requests] == ["GET", "POST"]
    assert requests[1].url.path == "/repos/kaiquekandykoga/nishikihebi/labels"
    assert json.loads(requests[1].content) == {
        "name": "nishikihebi",
        "color": "f709c2",
    }


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
