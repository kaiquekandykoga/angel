import re

import pytest

import nishikihebi.__main__
from nishikihebi.github_client import MissingGitHubTokenError, PullRequest
from nishikihebi.llm_client import MissingApiKeyError


def test_main_exits_when_api_key_missing(monkeypatch):
    message = "NVIDIA_API_KEY environment variable is not set."

    def raise_missing_api_key():
        raise MissingApiKeyError(message)

    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", raise_missing_api_key)

    with pytest.raises(SystemExit, match=re.escape(message)):
        nishikihebi.__main__.main(["chat"])


def test_main_runs_chat_flow_without_needing_a_github_token(monkeypatch, fake_client):
    def raise_missing_github_token():
        raise MissingGitHubTokenError("GITHUB_TOKEN environment variable is not set.")

    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", raise_missing_github_token
    )
    ran = {}

    def fake_run(session):
        ran["session"] = session

    monkeypatch.setattr(nishikihebi.__main__.cli, "run", fake_run)

    nishikihebi.__main__.main(["chat"])

    assert "session" in ran


def test_main_runs_pr_review_flow_and_prints_one_line_per_pr(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a")
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    nishikihebi.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert "kaiquekandykoga/nishikihebi" in out
    assert "1" in out


def test_main_exits_when_github_token_missing_for_pr_review(monkeypatch, fake_client):
    message = "GITHUB_TOKEN environment variable is not set."
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)

    def raise_missing_github_token():
        raise MissingGitHubTokenError(message)

    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", raise_missing_github_token
    )

    with pytest.raises(SystemExit, match=re.escape(message)):
        nishikihebi.__main__.main(["pr_review"])


def test_main_exits_on_unknown_command():
    with pytest.raises(SystemExit, match="Unknown command: bogus"):
        nishikihebi.__main__.main(["bogus"])


def test_main_exits_when_no_command_given():
    with pytest.raises(SystemExit, match="Valid commands: chat, pr_review"):
        nishikihebi.__main__.main([])


def test_main_exits_when_too_many_arguments_given():
    with pytest.raises(SystemExit, match="Unknown command"):
        nishikihebi.__main__.main(["chat", "pr_review"])
