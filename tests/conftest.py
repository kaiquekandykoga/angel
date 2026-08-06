from collections.abc import Sequence

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from nishikihebi.clients.github import PullRequest


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
        self.posted_comments: list[tuple[PullRequest, str]] = []

    def list_labeled_pull_requests(
        self, repository: str, label: str
    ) -> list[PullRequest]:
        return self.pull_requests.get(repository, [])

    def fetch_diff(self, pull_request: PullRequest) -> str:
        return self.diffs.get(pull_request, "")

    def post_comment(self, pull_request: PullRequest, body: str) -> None:
        self.posted_comments.append((pull_request, body))


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
