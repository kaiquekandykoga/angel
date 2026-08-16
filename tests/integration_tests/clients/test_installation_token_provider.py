from collections.abc import Callable
from typing import Any

import httpx
import jwt
import respx

from nishikihebi.clients.github import GITHUB_BASE_URL, InstallationTokenProvider


def test_returns_installation_access_token_for_repository(rsa_key_pair):
    private_key, _public_key = rsa_key_pair
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/repos/kaiquekandykoga/nishikihebi/installation":
            return httpx.Response(200, json={"id": 123})
        if request.url.path == "/app/installations/123/access_tokens":
            return httpx.Response(201, json={"token": "installation-token"})
        raise AssertionError(f"unexpected request: {request.url.path}")

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    )
    provider = InstallationTokenProvider(
        http_client, app_id="app-1", private_key=private_key
    )

    token = provider("kaiquekandykoga/nishikihebi")

    assert token == "installation-token"
    assert [request.url.path for request in requests] == [
        "/repos/kaiquekandykoga/nishikihebi/installation",
        "/app/installations/123/access_tokens",
    ]
    for request in requests:
        auth_header = request.headers["authorization"]
        assert auth_header.startswith("Bearer ")
        jwt_token = auth_header.removeprefix("Bearer ")
        claims = jwt.decode(jwt_token, _public_key, algorithms=["RS256"])
        assert claims["iss"] == "app-1"
        assert claims["exp"] - claims["iat"] <= 600


def test_list_repositories_spans_every_installation(rsa_key_pair):
    private_key, _public_key = rsa_key_pair
    repositories_by_token = {
        "token-1": ["kaiquekandykoga/nishikihebi", "kaiquekandykoga/a"],
        "token-2": ["someone-else/b"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/app/installations":
            return httpx.Response(200, json=[{"id": 1}, {"id": 2}])
        if request.url.path == "/app/installations/1/access_tokens":
            return httpx.Response(201, json={"token": "token-1"})
        if request.url.path == "/app/installations/2/access_tokens":
            return httpx.Response(201, json={"token": "token-2"})
        if request.url.path == "/installation/repositories":
            token = request.headers["authorization"].removeprefix("Bearer ")
            return httpx.Response(
                200,
                json={
                    "repositories": [
                        {"full_name": full_name}
                        for full_name in repositories_by_token[token]
                    ]
                },
            )
        raise AssertionError(f"unexpected request: {request.url.path}")

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    )
    provider = InstallationTokenProvider(
        http_client, app_id="app-1", private_key=private_key
    )

    repositories = provider.list_repositories()

    assert repositories == [
        "kaiquekandykoga/nishikihebi",
        "kaiquekandykoga/a",
        "someone-else/b",
    ]


def test_list_repositories_caches_the_token_of_each_repository(
    rsa_key_pair, respx_mock: respx.MockRouter, load_fixture: Callable[[str], Any]
):
    private_key, _public_key = rsa_key_pair
    respx_mock.get(f"{GITHUB_BASE_URL}/app/installations").mock(
        return_value=httpx.Response(200, json=load_fixture("github/installations.json"))
    )
    respx_mock.post(
        f"{GITHUB_BASE_URL}/app/installations/91733042/access_tokens"
    ).mock(
        return_value=httpx.Response(201, json=load_fixture("github/access_token.json"))
    )
    respx_mock.get(f"{GITHUB_BASE_URL}/installation/repositories").mock(
        return_value=httpx.Response(
            200, json=load_fixture("github/installation_repositories_page1.json")
        )
    )

    provider = InstallationTokenProvider(
        httpx.Client(base_url=GITHUB_BASE_URL), app_id="app-1", private_key=private_key
    )

    provider.list_repositories()
    request_count_after_listing = len(respx_mock.calls)

    token = provider("kaiquekandykoga/nishikihebi")
    assert token == "ghs_REDACTEDINSTALLATIONTOKEN0000000000"
    assert len(respx_mock.calls) == request_count_after_listing


def test_caches_installation_token_per_repository(
    rsa_key_pair, respx_mock: respx.MockRouter, load_fixture: Callable[[str], Any]
):
    private_key, _public_key = rsa_key_pair
    installation = load_fixture("github/installations.json")[0]

    respx_mock.get(
        f"{GITHUB_BASE_URL}/repos/kaiquekandykoga/nishikihebi/installation"
    ).mock(return_value=httpx.Response(200, json=installation))
    respx_mock.post(
        f"{GITHUB_BASE_URL}/app/installations/91733042/access_tokens"
    ).mock(
        return_value=httpx.Response(201, json=load_fixture("github/access_token.json"))
    )

    provider = InstallationTokenProvider(
        httpx.Client(base_url=GITHUB_BASE_URL), app_id="app-1", private_key=private_key
    )

    first = provider("kaiquekandykoga/nishikihebi")
    request_count_after_first_call = len(respx_mock.calls)
    second = provider("kaiquekandykoga/nishikihebi")

    assert first == second == "ghs_REDACTEDINSTALLATIONTOKEN0000000000"
    assert len(respx_mock.calls) == request_count_after_first_call


def test_list_repositories_follows_link_header_pagination(
    rsa_key_pair, respx_mock: respx.MockRouter, load_fixture: Callable[[str], Any]
):
    private_key, _public_key = rsa_key_pair

    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(
                200, json=load_fixture("github/installation_repositories_page2.json")
            )
        return httpx.Response(
            200,
            json=load_fixture("github/installation_repositories_page1.json"),
            headers={
                "Link": (
                    "<https://api.github.com/installation/repositories"
                    '?per_page=100&page=2>; rel="next"'
                )
            },
        )

    respx_mock.get(f"{GITHUB_BASE_URL}/app/installations").mock(
        return_value=httpx.Response(200, json=load_fixture("github/installations.json"))
    )
    respx_mock.post(
        f"{GITHUB_BASE_URL}/app/installations/91733042/access_tokens"
    ).mock(
        return_value=httpx.Response(201, json=load_fixture("github/access_token.json"))
    )
    respx_mock.get(f"{GITHUB_BASE_URL}/installation/repositories").mock(
        side_effect=responder
    )

    provider = InstallationTokenProvider(
        httpx.Client(base_url=GITHUB_BASE_URL), app_id="app-1", private_key=private_key
    )

    repositories = provider.list_repositories()

    assert set(repositories) == {
        "kaiquekandykoga/nishikihebi",
        "kaiquekandykoga/dotfiles",
    }


def test_list_repositories_follows_link_header_pagination_across_installations(
    rsa_key_pair, respx_mock: respx.MockRouter, load_fixture: Callable[[str], Any]
):
    private_key, _public_key = rsa_key_pair
    repositories_by_installation = {
        91733042: "kaiquekandykoga/nishikihebi",
        91733099: "kaiquekandykoga/dotfiles",
    }

    def installations_responder(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(
                200, json=load_fixture("github/installations_page2.json")
            )
        return httpx.Response(
            200,
            json=load_fixture("github/installations_page1.json"),
            headers={
                "Link": (
                    "<https://api.github.com/app/installations"
                    '?per_page=100&page=2>; rel="next"'
                )
            },
        )

    def repositories_responder(request: httpx.Request) -> httpx.Response:
        token = request.headers["authorization"].removeprefix("Bearer ")
        installation_id = int(token.removeprefix("token-for-"))
        return httpx.Response(
            200,
            json={
                "repositories": [
                    {"full_name": repositories_by_installation[installation_id]}
                ]
            },
        )

    respx_mock.get(f"{GITHUB_BASE_URL}/app/installations").mock(
        side_effect=installations_responder
    )
    respx_mock.post(f"{GITHUB_BASE_URL}/app/installations/91733042/access_tokens").mock(
        return_value=httpx.Response(201, json={"token": "token-for-91733042"})
    )
    respx_mock.post(f"{GITHUB_BASE_URL}/app/installations/91733099/access_tokens").mock(
        return_value=httpx.Response(201, json={"token": "token-for-91733099"})
    )
    respx_mock.get(f"{GITHUB_BASE_URL}/installation/repositories").mock(
        side_effect=repositories_responder
    )

    provider = InstallationTokenProvider(
        httpx.Client(base_url=GITHUB_BASE_URL), app_id="app-1", private_key=private_key
    )

    repositories = provider.list_repositories()

    assert set(repositories) == {
        "kaiquekandykoga/nishikihebi",
        "kaiquekandykoga/dotfiles",
    }
