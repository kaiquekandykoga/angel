import logging

from angel.clients.github import (
    Comment,
    DryRunGitHubClient,
    Issue,
    PullRequest,
)


class SpyGitHubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def list_repositories(self) -> list[str]:
        self.calls.append(("list_repositories", ()))
        return ["org/repo"]

    def ensure_label(self, repository: str, label: str, color: str) -> None:
        self.calls.append(("ensure_label", (repository, label, color)))

    def list_open_pull_requests(
        self, repository: str, label: str
    ) -> list[PullRequest]:
        self.calls.append(("list_open_pull_requests", (repository, label)))
        return [PullRequest(repository, 1, "title", "body", "sha")]

    def fetch_diff(self, pull_request: PullRequest) -> str:
        self.calls.append(("fetch_diff", (pull_request,)))
        return "diff"

    def list_open_issues(self, repository: str, label: str) -> list[Issue]:
        self.calls.append(("list_open_issues", (repository, label)))
        return [Issue(repository, 2, "title", "body", "2024-01-01T00:00:00Z")]

    def list_comments(self, target: PullRequest | Issue) -> list[Comment]:
        self.calls.append(("list_comments", (target,)))
        return [Comment("author", "body", "2024-01-01T00:00:00Z")]

    def post_comment(self, target: PullRequest | Issue, body: str) -> None:
        self.calls.append(("post_comment", (target, body)))


def test_list_repositories_forwards_and_returns():
    inner = SpyGitHubClient()
    client = DryRunGitHubClient(inner)

    result = client.list_repositories()

    assert result == ["org/repo"]
    assert inner.calls == [("list_repositories", ())]


def test_list_open_pull_requests_forwards_and_returns():
    inner = SpyGitHubClient()
    client = DryRunGitHubClient(inner)

    result = client.list_open_pull_requests("org/repo", "review")

    assert result == [PullRequest("org/repo", 1, "title", "body", "sha")]
    assert inner.calls == [("list_open_pull_requests", ("org/repo", "review"))]


def test_fetch_diff_forwards_and_returns():
    inner = SpyGitHubClient()
    client = DryRunGitHubClient(inner)
    pull_request = PullRequest("org/repo", 1, "title", "body", "sha")

    result = client.fetch_diff(pull_request)

    assert result == "diff"
    assert inner.calls == [("fetch_diff", (pull_request,))]


def test_list_open_issues_forwards_and_returns():
    inner = SpyGitHubClient()
    client = DryRunGitHubClient(inner)

    result = client.list_open_issues("org/repo", "bug")

    assert result == [Issue("org/repo", 2, "title", "body", "2024-01-01T00:00:00Z")]
    assert inner.calls == [("list_open_issues", ("org/repo", "bug"))]


def test_list_comments_forwards_and_returns():
    inner = SpyGitHubClient()
    client = DryRunGitHubClient(inner)
    target = Issue("org/repo", 2, "title", "body", "2024-01-01T00:00:00Z")

    result = client.list_comments(target)

    assert result == [Comment("author", "body", "2024-01-01T00:00:00Z")]
    assert inner.calls == [("list_comments", (target,))]


def test_ensure_label_skips_inner_call_and_logs(caplog):
    inner = SpyGitHubClient()
    client = DryRunGitHubClient(inner)

    with caplog.at_level(logging.INFO):
        client.ensure_label("org/repo", "bug", "ff0000")

    assert inner.calls == []
    record = caplog.records[0]
    assert record.message == "dry run: skipping ensure_label"
    assert record.context == {
        "dry_run": True,
        "repository": "org/repo",
        "label": "bug",
    }


def test_post_comment_skips_inner_call_and_logs(caplog):
    inner = SpyGitHubClient()
    client = DryRunGitHubClient(inner)
    target = PullRequest("org/repo", 1, "title", "body", "sha")

    with caplog.at_level(logging.INFO):
        client.post_comment(target, "hello world")

    assert inner.calls == []
    record = caplog.records[0]
    assert record.message == "dry run: skipping post_comment"
    assert record.context == {
        "dry_run": True,
        "repository": "org/repo",
        "number": 1,
        "body_length": len("hello world"),
    }
