import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx

from nishikihebi.clients.github import (
    GITHUB_BASE_URL,
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


@pytest.fixture
def client() -> HttpGitHubClient:
    return HttpGitHubClient(httpx.Client(base_url=GITHUB_BASE_URL), token_provider)


def test_list_repositories_comes_from_the_token_provider(respx_mock: respx.MockRouter):
    client = HttpGitHubClient(
        httpx.Client(base_url=GITHUB_BASE_URL), FakeTokenProvider(["org/a", "org/b"])
    )

    assert client.list_repositories() == ["org/a", "org/b"]


def test_list_open_pull_requests_maps_number_title_body_and_head_sha(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    route = respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/pulls"
    ).mock(
        return_value=httpx.Response(200, json=load_fixture("github/pulls_page1.json"))
    )

    pull_requests = client.list_open_pull_requests(
        "kaiquekandykoga/nishikihebi", "nishikihebi"
    )

    assert PullRequest(
        "kaiquekandykoga/nishikihebi",
        41,
        "Paginate every GitHub list call",
        'Follows the `Link: rel="next"` header on every list endpoint.',
        "9f1b0c4bd2a54a1e6e2b7dbb1a0dd4b13ec2f0a1",
    ) in pull_requests
    request = route.calls.last.request
    assert request.url.params["state"] == "open"
    assert request.url.params["per_page"] == "100"
    assert (
        request.headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_list_open_pull_requests_drops_prs_without_the_label(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    respx_mock.get(f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/pulls").mock(
        return_value=httpx.Response(200, json=load_fixture("github/pulls_page1.json"))
    )

    pull_requests = client.list_open_pull_requests(
        "kaiquekandykoga/nishikihebi", "nishikihebi"
    )

    assert [pull_request.number for pull_request in pull_requests] == [41]


def test_list_open_issues_excludes_pull_requests_and_maps_updated_at(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    route = respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/issues"
    ).mock(return_value=httpx.Response(200, json=load_fixture("github/issues.json")))

    issues = client.list_open_issues("kaiquekandykoga/nishikihebi", "nishikihebi")

    assert issues == [
        Issue(
            "kaiquekandykoga/nishikihebi",
            38,
            "Add a LICENSE",
            "",
            "2026-08-13T15:22:47Z",
        )
    ]
    request = route.calls.last.request
    assert request.url.params["state"] == "open"
    assert request.url.params["per_page"] == "100"
    assert request.url.params["labels"] == "nishikihebi"
    assert (
        request.headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_list_comments_maps_login_body_and_created_at(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    route = respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/issues/41/comments"
    ).mock(
        return_value=httpx.Response(
            200, json=load_fixture("github/comments_page1.json")
        )
    )

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 41, "a pr", "", "sha")
    comments = client.list_comments(pull_request)

    assert comments == [
        Comment("kaiquekandykoga", "Ready for a look.", "2026-08-14T11:04:02Z"),
        Comment("octocat", "", "2026-08-14T12:20:35Z"),
    ]
    request = route.calls.last.request
    assert request.url.params["per_page"] == "100"
    assert (
        request.headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_fetch_diff_requests_diff_accept_header(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    diff_text = load_fixture("github/pull_request.diff")
    route = respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/pulls/41"
    ).mock(return_value=httpx.Response(200, text=diff_text))

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 41, "a pr", "", "sha")
    diff = client.fetch_diff(pull_request)

    assert diff == diff_text
    request = route.calls.last.request
    assert request.headers["accept"] == "application/vnd.github.diff"
    assert (
        request.headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_post_comment_sends_body_to_issue_comments_endpoint(
    respx_mock: respx.MockRouter, client: HttpGitHubClient
):
    route = respx_mock.post(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/issues/41/comments"
    ).mock(return_value=httpx.Response(201, json={}))

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 41, "a pr", "", "sha")
    client.post_comment(pull_request, "great work")

    request = route.calls.last.request
    assert json.loads(request.content) == {"body": "great work"}
    assert (
        request.headers["authorization"]
        == "Bearer token-for-kaiquekandykoga/nishikihebi"
    )


def test_ensure_label_does_not_post_when_label_already_exists(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    get_route = respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/labels/nishikihebi"
    ).mock(return_value=httpx.Response(200, json=load_fixture("github/label.json")))

    client.ensure_label("kaiquekandykoga/nishikihebi", "nishikihebi", "f709c2")

    assert get_route.call_count == 1


def test_ensure_label_creates_label_when_missing(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    get_route = respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/labels/nishikihebi"
    ).mock(
        return_value=httpx.Response(
            404, json=load_fixture("github/label_not_found.json")
        )
    )
    post_route = respx_mock.post(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/labels"
    ).mock(return_value=httpx.Response(201, json=load_fixture("github/label.json")))

    client.ensure_label("kaiquekandykoga/nishikihebi", "nishikihebi", "f709c2")

    assert get_route.call_count == 1
    assert json.loads(post_route.calls.last.request.content) == {
        "name": "nishikihebi",
        "color": "f709c2",
    }


def test_list_open_pull_requests_follows_link_header_pagination(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=load_fixture("github/pulls_page2.json"))
        return httpx.Response(
            200,
            json=load_fixture("github/pulls_page1.json"),
            headers={
                "Link": (
                    "<https://api.github.com/repos/kaiquekandykoga/nishikihebi/pulls"
                    '?state=open&per_page=100&page=2>; rel="next"'
                )
            },
        )

    respx_mock.get(f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/pulls").mock(
        side_effect=responder
    )

    pull_requests = client.list_open_pull_requests(
        "kaiquekandykoga/nishikihebi", "nishikihebi"
    )

    assert {pull_request.number for pull_request in pull_requests} == {41, 12}


def test_list_comments_follows_link_header_pagination(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=load_fixture("github/comments_page2.json"))
        return httpx.Response(
            200,
            json=load_fixture("github/comments_page1.json"),
            headers={
                "Link": (
                    "<https://api.github.com/repos/kaiquekandykoga/nishikihebi/"
                    'issues/41/comments?per_page=100&page=2>; rel="next"'
                )
            },
        )

    respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/issues/41/comments"
    ).mock(side_effect=responder)

    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 41, "a pr", "", "sha")
    comments = client.list_comments(pull_request)

    assert {comment.author for comment in comments} == {
        "kaiquekandykoga",
        "octocat",
        "kandy-nishikihebi[bot]",
    }


def test_list_open_issues_follows_link_header_pagination(
    respx_mock: respx.MockRouter,
    load_fixture: Callable[[str], Any],
    client: HttpGitHubClient,
):
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=load_fixture("github/issues_page2.json"))
        return httpx.Response(
            200,
            json=load_fixture("github/issues_page1.json"),
            headers={
                "Link": (
                    "<https://api.github.com/repos/kaiquekandykoga/nishikihebi/issues"
                    '?state=open&per_page=100&labels=nishikihebi&page=2>; rel="next"'
                )
            },
        )

    respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/issues"
    ).mock(side_effect=responder)

    issues = client.list_open_issues("kaiquekandykoga/nishikihebi", "nishikihebi")

    assert [issue.number for issue in issues] == [38]


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
