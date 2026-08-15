import logging

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.agents._shared import Review
from nishikihebi.agents.issue_review.nodes import fetch_issues, review_issues
from nishikihebi.agents.issue_review.prompts import REVIEW_SYSTEM_PROMPT
from nishikihebi.agents.issue_review.state import IssueContext
from nishikihebi.clients.github import Comment, Issue

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


def test_review_issues_logs_start_per_item_and_end(fake_client, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    node = review_issues(fake_client)

    node({"issues": [IssueContext(issue_a, [])], "reviews": []})

    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any("reviewing 1" in r.message for r in info_records)
    assert any(
        getattr(r, "context", {}).get("repository") == "org/a"
        and getattr(r, "context", {}).get("number") == 1
        for r in info_records
    )
    assert any("review" in getattr(r, "context", {}) for r in debug_records)
    assert info_records[-1].context["count"] == 1


def test_review_issues_returns_one_review_per_issue(fake_client):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    node = review_issues(fake_client)

    result = node(
        {
            "issues": [IssueContext(issue_a, []), IssueContext(issue_b, [])],
            "reviews": [],
        }
    )

    assert result == {
        "reviews": [
            Review(issue_a, fake_client.reply),
            Review(issue_b, fake_client.reply),
        ]
    }


def test_review_issues_sends_title_body_and_comments(fake_client):
    issue_a = Issue(
        "org/a", 1, "issue a", "the body of the issue", "2026-08-01T00:00:00Z"
    )
    comments = [
        Comment("alice", "can you clarify?", "2026-08-01T00:00:00Z"),
        Comment("kandy-nishikihebi[bot]", "looks reasonable", "2026-08-02T00:00:00Z"),
    ]
    node = review_issues(fake_client)

    node({"issues": [IssueContext(issue_a, comments)], "reviews": []})

    sent = fake_client.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == REVIEW_SYSTEM_PROMPT
    assert isinstance(sent[1], HumanMessage)
    content = sent[1].content
    assert "the body of the issue" in content
    assert "org/a" in content
    assert "1" in content
    assert "issue a" in content
    assert "@alice: can you clarify?" in content
    assert "@kandy-nishikihebi[bot]: looks reasonable" in content


def test_review_issues_renders_no_comments_fallback(fake_client):
    issue_a = Issue("org/a", 1, "issue a", "body", "2026-08-01T00:00:00Z")
    node = review_issues(fake_client)

    node({"issues": [IssueContext(issue_a, [])], "reviews": []})

    sent = fake_client.calls[-1]
    assert "(none)" in sent[1].content
