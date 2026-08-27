import logging
import re
import time

import pytest
from langchain_core.messages import AIMessage

import angel.__main__
import angel.clients.llm
from angel.clients.github import (
    DryRunGitHubClient,
    Issue,
    MissingGitHubCredentialsError,
    PullRequest,
)
from angel.clients.llm import InvalidMaxCompletionTokensError, MissingApiKeyError


def test_main_exits_when_api_key_missing(monkeypatch):
    message = "ANGEL_NVIDIA_API_KEY environment variable is not set."

    def raise_missing_api_key():
        raise MissingApiKeyError(message)

    monkeypatch.setattr(angel.__main__, "build_llm_client", raise_missing_api_key)

    with pytest.raises(SystemExit, match=re.escape(message)):
        angel.__main__.main(["chat"])


def test_main_exits_when_max_completion_tokens_invalid(monkeypatch):
    message = (
        "ANGEL_NVIDIA_MAX_COMPLETION_TOKENS must be a positive integer, "
        "got 'not-a-number'."
    )

    def raise_invalid_max_completion_tokens():
        raise InvalidMaxCompletionTokensError(message)

    monkeypatch.setattr(
        angel.__main__, "build_llm_client", raise_invalid_max_completion_tokens
    )

    with pytest.raises(SystemExit, match=re.escape(message)):
        angel.__main__.main(["chat"])


def test_main_logs_the_command_being_run(monkeypatch, caplog, fake_client):
    caplog.set_level(logging.INFO, logger="angel")
    ran = {}

    def fake_run(session):
        ran["session"] = session

    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(angel.__main__.repl, "run", fake_run)

    angel.__main__.main(["chat"])

    messages = [record.message for record in caplog.records]
    assert any("chat" in message for message in messages)


def test_main_runs_chat_flow_without_needing_a_github_token(monkeypatch, fake_client):
    def raise_missing_github_token():
        raise MissingGitHubCredentialsError(
            "ANGEL_GITHUB_APP_ID environment variable is not set."
        )

    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", raise_missing_github_token
    )
    ran = {}

    def fake_run(session):
        ran["session"] = session

    monkeypatch.setattr(angel.__main__.repl, "run", fake_run)

    angel.__main__.main(["chat"])

    assert "session" in ran


def test_main_runs_pr_review_flow_and_prints_one_line_per_pr(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"monalisa/hello-world": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "angel")
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert "monalisa/hello-world" in out
    assert "1" in out


def test_main_reports_when_there_is_nothing_to_review_for_pr_review(
    monkeypatch, capsys, fake_client, fake_github
):
    fake_github.pull_requests = {}
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert "No pull requests to review" in out
    assert fake_github.posted_comments == []


def test_main_exits_nonzero_when_a_pull_request_review_fails(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "angel")
    calls = {"count": 0}
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        angel.__main__.main(["pr_review"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    assert out.count("Commented on") == 4
    assert f"{repository}#1" not in out


def test_main_exits_nonzero_when_an_issue_review_fails(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
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
        fake_github.label(issue, "angel")
    calls = {"count": 0}
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        angel.__main__.main(["issue_review"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    assert out.count("Commented on") == 4
    assert f"{repository}#3" not in out


def test_main_exits_nonzero_when_every_pull_request_fails_with_none_reviewed(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
    pr = PullRequest(repository, 1, "pr", "body", "sha-1")
    fake_github.pull_requests = {repository: [pr]}
    fake_github.label(pr, "angel")

    def raise_on_list_comments(target):
        raise RuntimeError("github exploded")

    monkeypatch.setattr(fake_github, "list_comments", raise_on_list_comments)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        angel.__main__.main(["pr_review"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    assert "No pull requests to review" in out


def test_main_prints_a_readable_failure_summary_to_stderr(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
    pr = PullRequest(repository, 1, "pr", "body", "sha-1")
    fake_github.pull_requests = {repository: [pr]}
    fake_github.diffs = {pr: "diff"}
    fake_github.label(pr, "angel")

    def raise_llm_error(messages, schema):
        raise RuntimeError("llm exploded")

    monkeypatch.setattr(fake_client, "complete_structured", raise_llm_error)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit):
        angel.__main__.main(["pr_review"])

    captured = capsys.readouterr()
    assert "No pull requests to review" in captured.out
    assert f"{repository}#1" in captured.err
    assert "review_pull_requests" in captured.err
    assert "RuntimeError" in captured.err
    assert "llm exploded" in captured.err


def test_main_does_not_double_count_a_post_stage_failure_in_the_summary(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "angel")
    original_post_comment = fake_github.post_comment

    def flaky_post_comment(target, body):
        if target.number == 3:
            raise RuntimeError("github exploded")
        original_post_comment(target, body)

    monkeypatch.setattr(fake_github, "post_comment", flaky_post_comment)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit, match=re.escape("1 of 5 items failed")):
        angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert out.count("Commented on") == 5
    assert len(fake_github.posted_comments) == 4


def test_main_counts_each_item_once_across_review_and_post_failures(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "angel")
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
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit, match=re.escape("2 of 5 items failed")):
        angel.__main__.main(["pr_review"])


def test_main_exits_when_github_token_missing_for_pr_review(monkeypatch, fake_client):
    message = "ANGEL_GITHUB_APP_ID environment variable is not set."
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)

    def raise_missing_github_token():
        raise MissingGitHubCredentialsError(message)

    monkeypatch.setattr(
        angel.__main__, "build_github_client", raise_missing_github_token
    )

    with pytest.raises(SystemExit, match=re.escape(message)):
        angel.__main__.main(["pr_review"])


def test_main_runs_issue_review_flow_and_prints_one_line_per_issue(
    monkeypatch, capsys, fake_client, fake_github
):
    issue_a = Issue(
        "monalisa/hello-world", 1, "issue a", "body a", "2026-08-01T00:00:00Z"
    )
    fake_github.issues = {"monalisa/hello-world": [issue_a]}
    fake_github.label(issue_a, "angel")
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    angel.__main__.main(["issue_review"])

    out = capsys.readouterr().out
    assert "monalisa/hello-world" in out
    assert "1" in out


def test_main_reports_when_there_is_nothing_to_review_for_issue_review(
    monkeypatch, capsys, fake_client, fake_github
):
    fake_github.issues = {}
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    angel.__main__.main(["issue_review"])

    out = capsys.readouterr().out
    assert "No issues to review" in out
    assert fake_github.posted_comments == []


def test_main_exits_when_github_token_missing_for_issue_review(
    monkeypatch, fake_client
):
    message = "ANGEL_GITHUB_APP_ID environment variable is not set."
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)

    def raise_missing_github_token():
        raise MissingGitHubCredentialsError(message)

    monkeypatch.setattr(
        angel.__main__, "build_github_client", raise_missing_github_token
    )

    with pytest.raises(SystemExit, match=re.escape(message)):
        angel.__main__.main(["issue_review"])


def test_main_dry_run_wraps_github_client_and_prints_review_body_for_pr_review(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"monalisa/hello-world": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "angel")
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = angel.__main__.build_pr_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(angel.__main__, "build_pr_review_graph", spy)

    angel.__main__.main(["pr_review", "--dry-run"])

    assert isinstance(captured["github"], DryRunGitHubClient)
    out = capsys.readouterr().out
    assert "monalisa/hello-world#1" in out.splitlines()
    assert "fake summary" in out
    assert "Commented on" not in out
    assert fake_github.posted_comments == []


def test_main_dry_run_before_command_parses_the_same_as_after(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"monalisa/hello-world": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "angel")
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = angel.__main__.build_pr_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(angel.__main__, "build_pr_review_graph", spy)

    angel.__main__.main(["--dry-run", "pr_review"])

    assert isinstance(captured["github"], DryRunGitHubClient)
    out = capsys.readouterr().out
    assert "monalisa/hello-world#1" in out.splitlines()
    assert "Commented on" not in out


def test_main_dry_run_wraps_github_client_and_prints_review_body_for_issue_review(
    monkeypatch, capsys, fake_client, fake_github
):
    issue_a = Issue(
        "monalisa/hello-world", 1, "issue a", "body a", "2026-08-01T00:00:00Z"
    )
    fake_github.issues = {"monalisa/hello-world": [issue_a]}
    fake_github.label(issue_a, "angel")
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = angel.__main__.build_issue_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(angel.__main__, "build_issue_review_graph", spy)

    angel.__main__.main(["issue_review", "--dry-run"])

    assert isinstance(captured["github"], DryRunGitHubClient)
    out = capsys.readouterr().out
    assert "monalisa/hello-world#1" in out.splitlines()
    assert "Commented on" not in out
    assert fake_github.posted_comments == []


def test_main_non_dry_run_passes_the_raw_github_client_through(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"monalisa/hello-world": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, "angel")
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )
    captured = {}
    original_build = angel.__main__.build_pr_review_graph

    def spy(client, github):
        captured["github"] = github
        return original_build(client, github)

    monkeypatch.setattr(angel.__main__, "build_pr_review_graph", spy)

    angel.__main__.main(["pr_review"])

    assert captured["github"] is fake_github
    out = capsys.readouterr().out
    assert "Commented on monalisa/hello-world#1" in out


def test_main_dry_run_reports_when_there_is_nothing_to_review(
    monkeypatch, capsys, fake_client, fake_github
):
    fake_github.pull_requests = {}
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    angel.__main__.main(["pr_review", "--dry-run"])

    out = capsys.readouterr().out
    assert "No pull requests to review" in out


def test_main_dry_run_still_exits_nonzero_when_a_pull_request_review_fails(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "angel")
    calls = {"count": 0}
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit) as excinfo:
        angel.__main__.main(["pr_review", "--dry-run"])

    assert excinfo.value.code != 0
    out = capsys.readouterr().out
    target_lines = [
        line for line in out.splitlines() if line.startswith(f"{repository}#")
    ]
    assert len(target_lines) == 4
    assert "Commented on" not in out
    assert f"{repository}#1" not in out


def test_main_exits_when_dry_run_is_used_with_chat():
    with pytest.raises(SystemExit, match="--dry-run is not valid for chat"):
        angel.__main__.main(["chat", "--dry-run"])


def test_main_exits_on_unknown_flag():
    with pytest.raises(SystemExit, match="Unknown command: pr_review --bogus"):
        angel.__main__.main(["pr_review", "--bogus"])


def test_main_exits_when_two_commands_given():
    with pytest.raises(
        SystemExit, match="Unknown command: pr_review issue_review"
    ):
        angel.__main__.main(["pr_review", "issue_review"])


def test_main_logs_dry_run_flag(monkeypatch, caplog, fake_client, fake_github):
    caplog.set_level(logging.INFO, logger="angel")
    fake_github.pull_requests = {}
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    angel.__main__.main(["pr_review", "--dry-run"])

    records = [
        record
        for record in caplog.records
        if getattr(record, "context", {}).get("command") == "pr_review"
    ]
    assert any(record.context["dry_run"] is True for record in records)


def test_main_exits_on_unknown_command():
    with pytest.raises(SystemExit, match="Unknown command: bogus"):
        angel.__main__.main(["bogus"])


def test_main_no_args_matches_top_level_help(capsys):
    with pytest.raises(SystemExit):
        angel.__main__.main(["--help"])
    from_flag = capsys.readouterr().out

    with pytest.raises(SystemExit) as excinfo:
        angel.__main__.main([])
    from_no_args = capsys.readouterr().out

    assert excinfo.value.code == 0
    assert from_flag == from_no_args


def test_main_no_args_builds_nothing(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise AssertionError("should not be called")

    monkeypatch.setattr(angel.__main__, "build_llm_client", fail)
    monkeypatch.setattr(angel.__main__, "build_github_client", fail)
    monkeypatch.setattr(angel.__main__, "configure_logging", fail)

    with pytest.raises(SystemExit):
        angel.__main__.main([])


def test_main_exits_when_only_a_flag_given():
    with pytest.raises(SystemExit, match="Unknown command: --dry-run"):
        angel.__main__.main(["--dry-run"])


def test_main_exits_when_too_many_arguments_given():
    with pytest.raises(SystemExit, match="Unknown command"):
        angel.__main__.main(["chat", "pr_review"])


def test_main_pr_review_help_exits_zero_and_mentions_dry_run(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise AssertionError("should not be called")

    monkeypatch.setattr(angel.__main__, "build_llm_client", fail)
    monkeypatch.setattr(angel.__main__, "build_github_client", fail)
    monkeypatch.setattr(angel.__main__, "configure_logging", fail)

    with pytest.raises(SystemExit) as excinfo:
        angel.__main__.main(["pr_review", "--help"])

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--dry-run" in out
    assert "Print each review to stdout and make zero GitHub writes" in out


def test_main_help_pr_review_matches_pr_review_help(capsys):
    with pytest.raises(SystemExit):
        angel.__main__.main(["pr_review", "--help"])
    from_flag = capsys.readouterr().out

    with pytest.raises(SystemExit):
        angel.__main__.main(["help", "pr_review"])
    from_help_command = capsys.readouterr().out

    assert from_flag == from_help_command


def test_main_top_level_help_lists_all_commands(capsys):
    with pytest.raises(SystemExit) as excinfo:
        angel.__main__.main(["--help"])

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "chat" in out
    assert "pr_review" in out
    assert "issue_review" in out


def test_main_bare_help_matches_top_level_help(capsys):
    with pytest.raises(SystemExit):
        angel.__main__.main(["--help"])
    from_flag = capsys.readouterr().out

    with pytest.raises(SystemExit):
        angel.__main__.main(["help"])
    from_help_command = capsys.readouterr().out

    assert from_flag == from_help_command


def test_main_help_with_unknown_command_exits_one():
    with pytest.raises(SystemExit, match="Unknown command: help bogus"):
        angel.__main__.main(["help", "bogus"])


def test_main_exits_when_dry_run_before_chat_is_also_rejected():
    with pytest.raises(SystemExit, match="--dry-run is not valid for chat"):
        angel.__main__.main(["--dry-run", "chat"])


def _label_and_diff(fake_github, pr):
    fake_github.pull_requests = {pr.repository: [pr]}
    fake_github.diffs = {pr: "diff a"}
    fake_github.label(pr, "angel")


def test_main_prints_run_reviews_usage_sections_in_order(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    _label_and_diff(fake_github, pr_a)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert out.index("Run") < out.index("Reviews") < out.index("Usage")


def test_main_usage_section_reports_the_tally(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    _label_and_diff(fake_github, pr_a)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )
    original_complete_structured = fake_client.complete_structured
    calls = {"count": 0}

    def instrumented(messages, schema):
        result = original_complete_structured(messages, schema)
        calls["count"] += 1
        if calls["count"] == 1:
            reply = AIMessage(
                content="",
                usage_metadata={
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                    "input_token_details": {},
                    "output_token_details": {},
                },
            )
            angel.clients.llm.log_model_call_completed(
                time.monotonic(), call="test", reply=reply
            )
        return result

    monkeypatch.setattr(fake_client, "complete_structured", instrumented)

    angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert "input_tokens" in out
    assert "100" in out
    assert "output_tokens" in out
    assert "20" in out
    assert "total_tokens" in out
    assert "120" in out
    assert "duration_ms" in out


def test_main_prints_usage_section_before_exiting_on_failure(
    monkeypatch, capsys, fake_client, fake_github
):
    repository = "monalisa/hello-world"
    pull_requests = [
        PullRequest(
            repository, number, f"pr {number}", f"body {number}", f"sha-{number}"
        )
        for number in range(1, 6)
    ]
    fake_github.pull_requests = {repository: pull_requests}
    fake_github.diffs = {pr: f"diff {pr.number}" for pr in pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, "angel")
    calls = {"count": 0}
    original_complete_structured = fake_client.complete_structured

    def flaky_complete_structured(messages, schema):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("llm exploded")
        return original_complete_structured(messages, schema)

    monkeypatch.setattr(fake_client, "complete_structured", flaky_complete_structured)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )

    with pytest.raises(SystemExit):
        angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert "Usage" in out
    assert "calls" in out


def test_main_colors_output_when_angel_color_is_always(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    _label_and_diff(fake_github, pr_a)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("ANGEL_COLOR", "always")

    angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert "\x1b" in out
    stripped = re.sub(r"\x1b\[[0-9;]*m", "", out)
    assert "Commented on monalisa/hello-world#1" in stripped
    assert stripped.index("Run") < stripped.index("Reviews") < stripped.index("Usage")


def test_main_does_not_color_output_when_angel_color_is_never(
    monkeypatch, capsys, fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    _label_and_diff(fake_github, pr_a)
    monkeypatch.setattr(angel.__main__, "build_llm_client", lambda: fake_client)
    monkeypatch.setattr(
        angel.__main__, "build_github_client", lambda: fake_github
    )
    monkeypatch.setenv("ANGEL_COLOR", "never")

    angel.__main__.main(["pr_review"])

    out = capsys.readouterr().out
    assert "\x1b" not in out
