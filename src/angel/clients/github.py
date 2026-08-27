import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple, Protocol

import httpx
import jwt

from angel.env import load_env_var
from angel.logs import get_logger

log = get_logger(__name__)


def _get_all(
    http_client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    key: str | None = None,
) -> list[Any]:
    items: list[Any] = []
    while True:
        response = http_client.get(url, params=params, headers=headers)
        response.raise_for_status()
        items.extend(response.json()[key] if key else response.json())
        next_link = response.links.get("next")
        if not next_link:
            return items
        url = next_link["url"]
        params = None


class PullRequest(NamedTuple):
    repository: str
    number: int
    title: str
    body: str
    head_sha: str


class Issue(NamedTuple):
    repository: str
    number: int
    title: str
    body: str
    updated_at: str


class Comment(NamedTuple):
    author: str
    body: str
    created_at: str


class GitHubClient(Protocol):
    def list_repositories(self) -> list[str]: ...
    def ensure_label(self, repository: str, label: str, color: str) -> None: ...
    def list_open_pull_requests(
        self, repository: str, label: str
    ) -> list[PullRequest]: ...
    def fetch_diff(self, pull_request: PullRequest) -> str: ...
    def list_open_issues(self, repository: str, label: str) -> list[Issue]: ...
    def list_comments(self, target: PullRequest | Issue) -> list[Comment]: ...
    def post_comment(self, target: PullRequest | Issue, body: str) -> None: ...


class TokenProvider(Protocol):
    def __call__(self, repository: str) -> str: ...
    def list_repositories(self) -> list[str]: ...


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

    def _jwt_header(self) -> dict[str, str]:
        now = self.now()
        jwt_token = jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self.app_id},
            self.private_key,
            algorithm="RS256",
        )
        return {"Authorization": f"Bearer {jwt_token}"}

    def _create_token(self, installation_id: int, headers: dict[str, str]) -> str:
        response = self.http_client.post(
            f"/app/installations/{installation_id}/access_tokens", headers=headers
        )
        response.raise_for_status()
        return response.json()["token"]

    def __call__(self, repository: str) -> str:
        if repository in self.tokens:
            return self.tokens[repository]

        headers = self._jwt_header()

        installation_response = self.http_client.get(
            f"/repos/{repository}/installation", headers=headers
        )
        installation_response.raise_for_status()
        installation_id = installation_response.json()["id"]

        token = self._create_token(installation_id, headers)
        self.tokens[repository] = token
        return token

    def list_repositories(self) -> list[str]:
        headers = self._jwt_header()
        installations = _get_all(
            self.http_client,
            "/app/installations",
            params={"per_page": 100},
            headers=headers,
        )

        repositories = []
        for installation in installations:
            token = self._create_token(installation["id"], headers)
            for repository in _get_all(
                self.http_client,
                "/installation/repositories",
                params={"per_page": 100},
                headers={"Authorization": f"Bearer {token}"},
                key="repositories",
            ):
                self.tokens[repository["full_name"]] = token
                repositories.append(repository["full_name"])
        return repositories


class HttpGitHubClient:
    def __init__(
        self, http_client: httpx.Client, token_provider: TokenProvider
    ) -> None:
        self.http_client = http_client
        self.token_provider = token_provider

    def _auth_header(self, repository: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_provider(repository)}"}

    def list_repositories(self) -> list[str]:
        return self.token_provider.list_repositories()

    def ensure_label(self, repository: str, label: str, color: str) -> None:
        response = self.http_client.get(
            f"/repos/{repository}/labels/{label}",
            headers=self._auth_header(repository),
        )
        if response.status_code == 404:
            create_response = self.http_client.post(
                f"/repos/{repository}/labels",
                json={"name": label, "color": color},
                headers=self._auth_header(repository),
            )
            create_response.raise_for_status()
            return
        response.raise_for_status()

    def list_open_pull_requests(self, repository: str, label: str) -> list[PullRequest]:
        items = _get_all(
            self.http_client,
            f"/repos/{repository}/pulls",
            params={"state": "open", "per_page": 100},
            headers=self._auth_header(repository),
        )
        return [
            PullRequest(
                repository,
                item["number"],
                item["title"],
                item["body"] or "",
                item["head"]["sha"],
            )
            for item in items
            if label in {item_label["name"] for item_label in item["labels"]}
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

    def list_open_issues(self, repository: str, label: str) -> list[Issue]:
        items = _get_all(
            self.http_client,
            f"/repos/{repository}/issues",
            params={"state": "open", "per_page": 100, "labels": label},
            headers=self._auth_header(repository),
        )
        return [
            Issue(
                repository,
                item["number"],
                item["title"],
                item["body"] or "",
                item["updated_at"],
            )
            for item in items
            if "pull_request" not in item
        ]

    def list_comments(self, target: PullRequest | Issue) -> list[Comment]:
        items = _get_all(
            self.http_client,
            f"/repos/{target.repository}/issues/{target.number}/comments",
            params={"per_page": 100},
            headers=self._auth_header(target.repository),
        )
        return [
            Comment(item["user"]["login"], item["body"] or "", item["created_at"])
            for item in items
        ]

    def post_comment(self, target: PullRequest | Issue, body: str) -> None:
        response = self.http_client.post(
            f"/repos/{target.repository}/issues/{target.number}/comments",
            json={"body": body},
            headers=self._auth_header(target.repository),
        )
        response.raise_for_status()


class DryRunGitHubClient:
    def __init__(self, inner: GitHubClient) -> None:
        self.inner = inner

    def list_repositories(self) -> list[str]:
        return self.inner.list_repositories()

    def ensure_label(self, repository: str, label: str, color: str) -> None:
        log.info(
            "dry run: skipping ensure_label",
            dry_run=True,
            repository=repository,
            label=label,
        )

    def list_open_pull_requests(self, repository: str, label: str) -> list[PullRequest]:
        return self.inner.list_open_pull_requests(repository, label)

    def fetch_diff(self, pull_request: PullRequest) -> str:
        return self.inner.fetch_diff(pull_request)

    def list_open_issues(self, repository: str, label: str) -> list[Issue]:
        return self.inner.list_open_issues(repository, label)

    def list_comments(self, target: PullRequest | Issue) -> list[Comment]:
        return self.inner.list_comments(target)

    def post_comment(self, target: PullRequest | Issue, body: str) -> None:
        log.info(
            "dry run: skipping post_comment",
            dry_run=True,
            repository=target.repository,
            number=target.number,
            body_length=len(body),
        )


def build_github_client() -> GitHubClient:
    app_id = load_env_var("ANGEL_GITHUB_APP_ID")
    private_key_path = load_env_var("ANGEL_GITHUB_PRIVATE_KEY_PATH")
    if not app_id or not private_key_path:
        missing = [
            name
            for name, value in (
                ("ANGEL_GITHUB_APP_ID", app_id),
                ("ANGEL_GITHUB_PRIVATE_KEY_PATH", private_key_path),
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
