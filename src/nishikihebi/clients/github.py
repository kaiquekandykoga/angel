import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, Protocol

import httpx
import jwt

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


class MissingGitHubCredentialsError(RuntimeError):
    pass


GITHUB_BASE_URL = "https://api.github.com"


class InstallationTokenProvider:
    def __init__(
        self,
        http_client: httpx.Client,
        app_id: str,
        private_key: str,
        now: Callable[[], int] = lambda: int(time.time()),
    ) -> None:
        self.http_client = http_client
        self.app_id = app_id
        self.private_key = private_key
        self.now = now
        self.tokens: dict[str, str] = {}

    def __call__(self, repository: str) -> str:
        if repository in self.tokens:
            return self.tokens[repository]

        now = self.now()
        jwt_token = jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self.app_id},
            self.private_key,
            algorithm="RS256",
        )
        headers = {"Authorization": f"Bearer {jwt_token}"}

        installation_response = self.http_client.get(
            f"/repos/{repository}/installation", headers=headers
        )
        installation_response.raise_for_status()
        installation_id = installation_response.json()["id"]

        token_response = self.http_client.post(
            f"/app/installations/{installation_id}/access_tokens", headers=headers
        )
        token_response.raise_for_status()
        token = token_response.json()["token"]

        self.tokens[repository] = token
        return token


class HttpGitHubClient:
    def __init__(
        self, http_client: httpx.Client, token_for: Callable[[str], str]
    ) -> None:
        self.http_client = http_client
        self.token_for = token_for

    def _auth_header(self, repository: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_for(repository)}"}

    def list_labeled_pull_requests(
        self, repository: str, label: str
    ) -> list[PullRequest]:
        response = self.http_client.get(
            f"/repos/{repository}/issues",
            params={"state": "open", "labels": label},
            headers=self._auth_header(repository),
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
            headers={
                "Accept": "application/vnd.github.diff",
                **self._auth_header(pull_request.repository),
            },
        )
        response.raise_for_status()
        return response.text

    def post_comment(self, pull_request: PullRequest, body: str) -> None:
        response = self.http_client.post(
            f"/repos/{pull_request.repository}/issues/{pull_request.number}/comments",
            json={"body": body},
            headers=self._auth_header(pull_request.repository),
        )
        response.raise_for_status()


def build_github_client() -> GitHubClient:
    app_id = load_env_var("NISHIKIHEBI_GITHUB_APP_ID")
    private_key_path = load_env_var("NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH")
    if not app_id or not private_key_path:
        missing = [
            name
            for name, value in (
                ("NISHIKIHEBI_GITHUB_APP_ID", app_id),
                ("NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH", private_key_path),
            )
            if not value
        ]
        raise MissingGitHubCredentialsError(
            " ".join(f"{name} environment variable is not set." for name in missing)
        )

    private_key = Path(private_key_path).expanduser().read_text()

    http_client = httpx.Client(
        base_url=GITHUB_BASE_URL,
        headers={"X-GitHub-Api-Version": "2022-11-28"},
    )
    return HttpGitHubClient(
        http_client, InstallationTokenProvider(http_client, app_id, private_key)
    )
