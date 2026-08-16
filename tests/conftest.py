from collections.abc import Sequence

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from nishikihebi.clients.github import Comment, Issue, PullRequest


@pytest.fixture(autouse=True)
def _run_in_tmp_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class FakeClient:
    def __init__(self, reply: str = "fake reply") -> None:
        self.reply = reply
        self.calls: list[Sequence[BaseMessage]] = []

    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.calls.append(list(messages))
        return AIMessage(content=self.reply)


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


class FakeGitHubClient:
    def __init__(self) -> None:
        self.pull_requests: dict[str, list[PullRequest]] = {}
        self.diffs: dict[PullRequest, str] = {}
        self.issues: dict[str, list[Issue]] = {}
        self.comments: dict[PullRequest | Issue, list[Comment]] = {}
        self.posted_comments: list[tuple[PullRequest | Issue, str]] = []
        self.labels: dict[PullRequest | Issue, set[str]] = {}
        self.ensure_label_calls: list[tuple[str, str, str]] = []
        self.call_log: list[tuple[str, str]] = []

    def list_repositories(self) -> list[str]:
        return sorted({*self.pull_requests, *self.issues})

    def label(self, target: PullRequest | Issue, label: str) -> None:
        self.labels.setdefault(target, set()).add(label)

    def ensure_label(self, repository: str, label: str, color: str) -> None:
        self.ensure_label_calls.append((repository, label, color))
        self.call_log.append(("ensure_label", repository))

    def list_open_pull_requests(self, repository: str, label: str) -> list[PullRequest]:
        self.call_log.append(("list_open_pull_requests", repository))
        return [
            pull_request
            for pull_request in self.pull_requests.get(repository, [])
            if label in self.labels.get(pull_request, set())
        ]

    def fetch_diff(self, pull_request: PullRequest) -> str:
        return self.diffs.get(pull_request, "")

    def list_open_issues(self, repository: str, label: str) -> list[Issue]:
        self.call_log.append(("list_open_issues", repository))
        return [
            issue
            for issue in self.issues.get(repository, [])
            if label in self.labels.get(issue, set())
        ]

    def list_comments(self, target: PullRequest | Issue) -> list[Comment]:
        return self.comments.get(target, [])

    def post_comment(self, target: PullRequest | Issue, body: str) -> None:
        self.posted_comments.append((target, body))


@pytest.fixture
def fake_github() -> FakeGitHubClient:
    return FakeGitHubClient()


@pytest.fixture
def scripted_input():
    def factory(*lines: str):
        inputs = iter(lines)

        def input_fn(_prompt: str = "") -> str:
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError from None

        return input_fn

    return factory
