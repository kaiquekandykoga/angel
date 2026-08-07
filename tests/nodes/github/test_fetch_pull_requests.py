import logging

from nishikihebi.clients.github import Comment, PullRequest
from nishikihebi.nodes.github.fetch_pull_requests import fetch_pull_requests
from nishikihebi.states.github import PullRequestContext

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"
LABEL = "nishikihebi"
LABEL_COLOR = "f709c2"


def test_fetch_pull_requests_logs_start_per_repository_and_summary(
    fake_github, caplog
):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"pull_requests": [], "reviews": []})

    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any("fetch" in r.message.lower() for r in info_records)
    summary = info_records[-1]
    assert summary.context["repositories_scanned"] == 1
    assert summary.context["items_scanned"] == 1
    assert summary.context["items_due_for_review"] == 1
    assert any(r.context.get("repository") == "org/a" for r in debug_records)
    assert any(
        r.context.get("selected") is True
        and r.context.get("reason") == "never reviewed"
        for r in debug_records
    )


def test_fetch_pull_requests_includes_pr_with_no_comments(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [])]}


def test_fetch_pull_requests_includes_pr_with_only_other_author_comments(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    other_comment = Comment("someone-else", "hi", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [other_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [other_comment])]}


def test_fetch_pull_requests_includes_pr_with_newer_head_commit(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-02T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [review_comment])]}


def test_fetch_pull_requests_excludes_pr_unchanged_since_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_excludes_pr_with_head_commit_equal_to_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_covers_every_repository_of_the_installation(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {
        "pull_requests": [
            PullRequestContext(pr_a, []),
            PullRequestContext(pr_b, []),
        ]
    }


def test_fetch_pull_requests_excludes_unlabeled_pr_never_reviewed(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_excludes_labeled_pr_not_due_for_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_calls_ensure_label_once_per_repository(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"pull_requests": [], "reviews": []})

    assert fake_github.ensure_label_calls == [
        ("org/a", LABEL, LABEL_COLOR),
        ("org/b", LABEL, LABEL_COLOR),
    ]
    assert fake_github.call_log == [
        ("ensure_label", "org/a"),
        ("list_open_pull_requests", "org/a"),
        ("ensure_label", "org/b"),
        ("list_open_pull_requests", "org/b"),
    ]
