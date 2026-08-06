import httpx
import jwt

from nishikihebi.clients.github import InstallationTokenProvider


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


def test_caches_installation_token_per_repository(rsa_key_pair):
    private_key, _public_key = rsa_key_pair
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/repos/kaiquekandykoga/nishikihebi/installation":
            return httpx.Response(200, json={"id": 123})
        return httpx.Response(201, json={"token": "installation-token"})

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    )
    provider = InstallationTokenProvider(
        http_client, app_id="app-1", private_key=private_key
    )

    first = provider("kaiquekandykoga/nishikihebi")
    request_count_after_first_call = len(requests)
    second = provider("kaiquekandykoga/nishikihebi")

    assert first == second
    assert len(requests) == request_count_after_first_call
