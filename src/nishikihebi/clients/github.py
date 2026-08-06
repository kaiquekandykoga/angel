from typing import NamedTuple, Protocol

import httpx

from nishikihebi.env import load_env_var


class PullRequest(NamedTuple):
    repository: str
    number: int
    title: str


class GitHubClient(Protocol):
    def list_labeled_pull_requests(
        self, repository: str, label: str
    ) -> list[PullRequest]: ...
    def fetch_diff(self, pull_request: PullRequest) -> str: ...
    def post_comment(self, pull_request: PullRequest, body: str) -> None: ...


class MissingGitHubTokenError(RuntimeError):
    pass


GITHUB_BASE_URL = "https://api.github.com"


class HttpGitHubClient:
    def __init__(self, http_client: httpx.Client) -> None:
        self.http_client = http_client

    def list_labeled_pull_requests(
        self, repository: str, label: str
    ) -> list[PullRequest]:
        response = self.http_client.get(
            f"/repos/{repository}/issues",
            params={"state": "open", "labels": label},
        )
        response.raise_for_status()
        return [
            PullRequest(repository, item["number"], item["title"])
            for item in response.json()
            if "pull_request" in item
        ]

    def fetch_diff(self, pull_request: PullRequest) -> str:
        response = self.http_client.get(
            f"/repos/{pull_request.repository}/pulls/{pull_request.number}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        response.raise_for_status()
        return response.text

    def post_comment(self, pull_request: PullRequest, body: str) -> None:
        response = self.http_client.post(
            f"/repos/{pull_request.repository}/issues/{pull_request.number}/comments",
            json={"body": body},
        )
        response.raise_for_status()


def build_github_client() -> GitHubClient:
    token = load_env_var("NISHIKIHEBI_GITHUB_TOKEN")
    if not token:
        raise MissingGitHubTokenError(
            "NISHIKIHEBI_GITHUB_TOKEN environment variable is not set."
        )

    http_client = httpx.Client(
        base_url=GITHUB_BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    return HttpGitHubClient(http_client)
