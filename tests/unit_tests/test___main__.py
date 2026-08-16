import logging
import re

import pytest

import nishikihebi.__main__
from nishikihebi.clients.github import (
    DryRunGitHubClient,
    Issue,
    MissingGitHubCredentialsError,
    PullRequest,
)
from nishikihebi.clients.llm import MissingApiKeyError


def test_main_exits_when_api_key_missing(monkeypatch):
    message = "NISHIKIHEBI_NVIDIA_API_KEY environment variable is not set."

    def raise_missing_api_key():
        raise MissingApiKeyError(message)

    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", raise_missing_api_key)

    with pytest.raises(SystemExit, match=re.escape(message)):
        nishikihebi.__main__.main(["chat"])


def test_main_logs_the_command_being_run(monkeypatch, caplog, fake_client):
    caplog.set_level(logging.INFO, logger="nishikihebi")
    ran = {}

    def fake_run(session):
        ran["session"] = session

    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(nishikihebi.__main__.repl, "run", fake_run)

    nishikihebi.__main__.main(["chat"])

    messages = [record.message for record in caplog.records]
    assert any("chat" in message for message in messages)


def test_main_runs_chat_flow_without_needing_a_github_token(monkeypatch, fake_client):
    def raise_missing_github_token():
        raise MissingGitHubCredentialsError(
            "NISHIKIHEBI_GITHUB_APP_ID environment variable is not set."
        )

    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", raise_missing_github_token
    )
    ran = {}

    def fake_run(session):
        ran["session"] = session

    monkeypatch.setattr(nishikihebi.__main__.repl, "run", fake_run)

    nishikihebi.__main__.main(["chat"])

    assert "session" in ran


def test_main_runs_pr_review_flow_and_prints_one_line_per_pr(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "nishikihebi")
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    nishikihebi.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert "kaiquekandykoga/nishikihebi" in out
    assert "1" in out


def test_main_reports_when_there_is_nothing_to_review_for_pr_review(
    monkeypatch, capsys, fake_client, fake_github
):
    fake_github.pull_requests = {}
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    nishikihebi.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert "No pull requests to review" in out
    assert fake_github.posted_comments == []


def test_main_exits_nonzero_when_a_pull_request_review_fails(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "kaiquekandykoga/nishikihebi"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "nishikihebi")
    calls = {"count": 0}
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        nishikihebi.__main__.main(["pr_review"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    assert out.count("Commented on") == 4
    assert f"{repository}#3" not in out


def test_main_exits_nonzero_when_an_issue_review_fails(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "kaiquekandykoga/nishikihebi"
    issues = [
        Issue(
            repository,
            number,
            f"issue {number}",
            f"body {number}",
            "2026-08-01T00:00:00Z",
        )
        for number in range(1, 6)
    ]
    fake_github.issues = {repository: issues}
    for issue in issues:
        fake_github.label(issue, "nishikihebi")
    calls = {"count": 0}
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        nishikihebi.__main__.main(["issue_review"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    assert out.count("Commented on") == 4
    assert f"{repository}#3" not in out


def test_main_exits_nonzero_when_every_pull_request_fails_with_none_reviewed(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "kaiquekandykoga/nishikihebi"
    pr = PullRequest(repository, 1, "pr", "body", "sha-1")
    fake_github.pull_requests = {repository: [pr]}
    fake_github.label(pr, "nishikihebi")

    def raise_on_list_comments(target):
        raise RuntimeError("github exploded")

    monkeypatch.setattr(fake_github, "list_comments", raise_on_list_comments)
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        nishikihebi.__main__.main(["pr_review"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    assert "No pull requests to review" in out


def test_main_prints_a_readable_failure_summary_to_stderr(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "kaiquekandykoga/nishikihebi"
    pr = PullRequest(repository, 1, "pr", "body", "sha-1")
    fake_github.pull_requests = {repository: [pr]}
    fake_github.diffs = {pr: "diff"}
    fake_github.label(pr, "nishikihebi")

    def raise_llm_error(messages, schema):
        raise RuntimeError("llm exploded")

    monkeypatch.setattr(fake_client, "complete_structured", raise_llm_error)
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit):
        nishikihebi.__main__.main(["pr_review"])

    captured = capsys.readouterr()
    assert captured.out == "No pull requests to review\n"
    assert f"{repository}#1" in captured.err
    assert "review_pull_requests" in captured.err
    assert "RuntimeError" in captured.err
    assert "llm exploded" in captured.err


def test_main_does_not_double_count_a_post_stage_failure_in_the_summary(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "kaiquekandykoga/nishikihebi"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "nishikihebi")
    original_post_comment = fake_github.post_comment

    def flaky_post_comment(target, body):
        if target.number == 3:
            raise RuntimeError("github exploded")
        original_post_comment(target, body)

    monkeypatch.setattr(fake_github, "post_comment", flaky_post_comment)
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit, match=re.escape("1 of 5 items failed")):
        nishikihebi.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert out.count("Commented on") == 5
    assert len(fake_github.posted_comments) == 4


def test_main_counts_each_item_once_across_review_and_post_failures(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "kaiquekandykoga/nishikihebi"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "nishikihebi")
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        if "Pull request #2" in messages[1].content:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    original_post_comment = fake_github.post_comment

    def flaky_post_comment(target, body):
        if target.number == 4:
            raise RuntimeError("github exploded")
        original_post_comment(target, body)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(fake_github, "post_comment", flaky_post_comment)
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit, match=re.escape("2 of 5 items failed")):
        nishikihebi.__main__.main(["pr_review"])


def test_main_exits_when_github_token_missing_for_pr_review(monkeypatch, fake_client):
    message = "NISHIKIHEBI_GITHUB_APP_ID environment variable is not set."
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)

    def raise_missing_github_token():
        raise MissingGitHubCredentialsError(message)

    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", raise_missing_github_token
    )

    with pytest.raises(SystemExit, match=re.escape(message)):
        nishikihebi.__main__.main(["pr_review"])


def test_main_runs_issue_review_flow_and_prints_one_line_per_issue(
    monkeypatch, capsys, fake_client, fake_github
):
    issue_a = Issue(
        "kaiquekandykoga/nishikihebi", 1, "issue a", "body a", "2026-08-01T00:00:00Z"
    )
    fake_github.issues = {"kaiquekandykoga/nishikihebi": [issue_a]}
    fake_github.label(issue_a, "nishikihebi")
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    nishikihebi.__main__.main(["issue_review"])

    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert "kaiquekandykoga/nishikihebi" in out
    assert "1" in out


def test_main_reports_when_there_is_nothing_to_review_for_issue_review(
    monkeypatch, capsys, fake_client, fake_github
):
    fake_github.issues = {}
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    nishikihebi.__main__.main(["issue_review"])

    out = capsys.readouterr().out
    assert "No issues to review" in out
    assert fake_github.posted_comments == []


def test_main_exits_when_github_token_missing_for_issue_review(
    monkeypatch, fake_client
):
    message = "NISHIKIHEBI_GITHUB_APP_ID environment variable is not set."
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)

    def raise_missing_github_token():
        raise MissingGitHubCredentialsError(message)

    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", raise_missing_github_token
    )

    with pytest.raises(SystemExit, match=re.escape(message)):
        nishikihebi.__main__.main(["issue_review"])


def test_main_dry_run_wraps_github_client_and_prints_review_body_for_pr_review(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "nishikihebi")
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = nishikihebi.__main__.build_pr_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(nishikihebi.__main__, "build_pr_review_graph", spy)

    nishikihebi.__main__.main(["pr_review", "--dry-run"])

    assert isinstance(captured["github"], DryRunGitHubClient)
    out = capsys.readouterr().out
    assert "--- kaiquekandykoga/nishikihebi#1 ---" in out
    assert "fake summary" in out
    assert "Commented on" not in out
    assert fake_github.posted_comments == []


def test_main_dry_run_before_command_parses_the_same_as_after(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "nishikihebi")
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = nishikihebi.__main__.build_pr_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(nishikihebi.__main__, "build_pr_review_graph", spy)

    nishikihebi.__main__.main(["--dry-run", "pr_review"])

    assert isinstance(captured["github"], DryRunGitHubClient)
    out = capsys.readouterr().out
    assert "--- kaiquekandykoga/nishikihebi#1 ---" in out
    assert "Commented on" not in out


def test_main_dry_run_wraps_github_client_and_prints_review_body_for_issue_review(
    monkeypatch, capsys, fake_client, fake_github
):
    issue_a = Issue(
        "kaiquekandykoga/nishikihebi", 1, "issue a", "body a", "2026-08-01T00:00:00Z"
    )
    fake_github.issues = {"kaiquekandykoga/nishikihebi": [issue_a]}
    fake_github.label(issue_a, "nishikihebi")
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = nishikihebi.__main__.build_issue_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(nishikihebi.__main__, "build_issue_review_graph", spy)

    nishikihebi.__main__.main(["issue_review", "--dry-run"])

    assert isinstance(captured["github"], DryRunGitHubClient)
    out = capsys.readouterr().out
    assert "--- kaiquekandykoga/nishikihebi#1 ---" in out
    assert "Commented on" not in out
    assert fake_github.posted_comments == []


def test_main_non_dry_run_passes_the_raw_github_client_through(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "nishikihebi")
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = nishikihebi.__main__.build_pr_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(nishikihebi.__main__, "build_pr_review_graph", spy)

    nishikihebi.__main__.main(["pr_review"])

    assert captured["github"] is fake_github
    out = capsys.readouterr().out
    assert "Commented on kaiquekandykoga/nishikihebi#1" in out


def test_main_dry_run_reports_when_there_is_nothing_to_review(
    monkeypatch, capsys, fake_client, fake_github
):
    fake_github.pull_requests = {}
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    nishikihebi.__main__.main(["pr_review", "--dry-run"])

    out = capsys.readouterr().out
    assert "No pull requests to review" in out


def test_main_dry_run_still_exits_nonzero_when_a_pull_request_review_fails(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "kaiquekandykoga/nishikihebi"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "nishikihebi")
    calls = {"count": 0}
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        nishikihebi.__main__.main(["pr_review", "--dry-run"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    assert out.count("---") == 8
    assert "Commented on" not in out
    assert f"{repository}#3" not in out


def test_main_exits_when_dry_run_is_used_with_chat():
    with pytest.raises(SystemExit, match="--dry-run is not valid for chat"):
        nishikihebi.__main__.main(["chat", "--dry-run"])


def test_main_exits_on_unknown_flag():
    with pytest.raises(SystemExit, match="Unknown command: pr_review --bogus"):
        nishikihebi.__main__.main(["pr_review", "--bogus"])


def test_main_exits_when_two_commands_given():
    with pytest.raises(
        SystemExit, match="Unknown command: pr_review issue_review"
    ):
        nishikihebi.__main__.main(["pr_review", "issue_review"])


def test_main_logs_dry_run_flag(monkeypatch, caplog, fake_client, fake_github):
    caplog.set_level(logging.INFO, logger="nishikihebi")
    fake_github.pull_requests = {}
    monkeypatch.setattr(nishikihebi.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        nishikihebi.__main__, "build_github_client", lambda: fake_github
    )

    nishikihebi.__main__.main(["pr_review", "--dry-run"])

    records = [
        record
        for record in caplog.records
        if getattr(record, "context", {}).get("command") == "pr_review"
    ]
    assert any(record.context["dry_run"] is True for record in records)


def test_main_exits_on_unknown_command():
    with pytest.raises(SystemExit, match="Unknown command: bogus"):
        nishikihebi.__main__.main(["bogus"])


def test_main_exits_when_no_command_given():
    with pytest.raises(
        SystemExit, match="Valid commands: chat, pr_review, issue_review"
    ):
        nishikihebi.__main__.main([])


def test_main_exits_when_too_many_arguments_given():
    with pytest.raises(SystemExit, match="Unknown command"):
        nishikihebi.__main__.main(["chat", "pr_review"])
