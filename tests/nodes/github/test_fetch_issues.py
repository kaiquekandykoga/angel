import logging

from nishikihebi.clients.github import Comment, Issue
from nishikihebi.nodes.github.fetch_issues import fetch_issues
from nishikihebi.states.github import IssueContext

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"
LABEL = "nishikihebi"
LABEL_COLOR = "f709c2"


def test_fetch_issues_logs_start_per_repository_and_summary(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"issues": [], "reviews": []})

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


def test_fetch_issues_includes_issue_with_no_reviewer_comment(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [IssueContext(issue, [])]}


def test_fetch_issues_includes_issue_updated_after_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-02T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [IssueContext(issue, [review_comment])]}


def test_fetch_issues_excludes_issue_updated_at_equal_to_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": []}


def test_fetch_issues_excludes_issue_updated_before_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": []}


def test_fetch_issues_other_author_comments_do_not_count_as_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    other_comment = Comment("someone-else", "hi", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [other_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [IssueContext(issue, [other_comment])]}


def test_fetch_issues_covers_every_repository_of_the_installation(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    fake_github.label(issue_a, LABEL)
    fake_github.label(issue_b, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [IssueContext(issue_a, []), IssueContext(issue_b, [])]}


def test_fetch_issues_excludes_unlabeled_issue_never_reviewed(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": []}


def test_fetch_issues_excludes_labeled_issue_not_due_for_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": []}


def test_fetch_issues_calls_ensure_label_once_per_repository(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    fake_github.label(issue_a, LABEL)
    fake_github.label(issue_b, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"issues": [], "reviews": []})

    assert fake_github.ensure_label_calls == [
        ("org/a", LABEL, LABEL_COLOR),
        ("org/b", LABEL, LABEL_COLOR),
    ]
    assert fake_github.call_log == [
        ("ensure_label", "org/a"),
        ("list_open_issues", "org/a"),
        ("ensure_label", "org/b"),
        ("list_open_issues", "org/b"),
    ]
