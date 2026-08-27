import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from angel.agents._shared import (
    Finding,
    IssueReviewOutput,
    ItemFailure,
    Review,
    Severity,
    render_issue_review,
)
from angel.agents.issue_review.nodes import fetch_issues, review_issues
from angel.agents.issue_review.prompts import REVIEW_SYSTEM_PROMPT
from angel.agents.issue_review.state import IssueContext
from angel.clients.github import Comment, Issue

REVIEWER_LOGIN = "kandy-angel[bot]"
LABEL = "angel"
LABEL_COLOR = "f709c2"

DEFAULT_REVIEW_BODY = render_issue_review(
    IssueReviewOutput(
        summary="fake summary",
        findings=[
            Finding(severity=Severity.MINOR, title="fake finding", detail="fake detail")
        ],
    )
)


def test_fetch_issues_logs_start_per_repository_and_summary(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="angel")
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"issues": [], "reviews": [], "failures": []})

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

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {"issues": [IssueContext(issue, [])], "failures": []}


def test_fetch_issues_includes_issue_updated_after_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-02T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {
        "issues": [IssueContext(issue, [review_comment])],
        "failures": [],
    }


def test_fetch_issues_excludes_issue_updated_at_equal_to_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {"issues": [], "failures": []}


def test_fetch_issues_excludes_issue_updated_before_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {"issues": [], "failures": []}


def test_fetch_issues_other_author_comments_do_not_count_as_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    other_comment = Comment("someone-else", "hi", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [other_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {
        "issues": [IssueContext(issue, [other_comment])],
        "failures": [],
    }


def test_fetch_issues_covers_every_repository_of_the_installation(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    fake_github.label(issue_a, LABEL)
    fake_github.label(issue_b, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {
        "issues": [IssueContext(issue_a, []), IssueContext(issue_b, [])],
        "failures": [],
    }


def test_fetch_issues_excludes_unlabeled_issue_never_reviewed(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {"issues": [], "failures": []}


def test_fetch_issues_excludes_labeled_issue_not_due_for_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    fake_github.label(issue, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result == {"issues": [], "failures": []}


def test_fetch_issues_calls_ensure_label_once_per_repository(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    fake_github.label(issue_a, LABEL)
    fake_github.label(issue_b, LABEL)
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"issues": [], "reviews": [], "failures": []})

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
    caplog.set_level(logging.DEBUG, logger="angel")
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    node = review_issues(fake_client)

    node({"issues": [IssueContext(issue_a, [])], "reviews": [], "failures": []})

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


def test_review_issues_logs_finding_count_and_severity_counts(caplog):
    caplog.set_level(logging.DEBUG, logger="angel")
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")

    class ScriptedClient:
        def complete(self, messages):
            return AIMessage(content="ok")

        def complete_structured(self, messages, schema):
            return schema(
                summary="summary",
                findings=[
                    Finding(severity=Severity.BLOCKER, title="a", detail="a detail"),
                    Finding(severity=Severity.BLOCKER, title="b", detail="b detail"),
                    Finding(severity=Severity.NIT, title="c", detail="c detail"),
                ],
            )

    node = review_issues(ScriptedClient())

    node({"issues": [IssueContext(issue_a, [])], "reviews": [], "failures": []})

    produced = next(
        r
        for r in caplog.records
        if r.levelname == "DEBUG" and r.message == "review produced"
    )
    assert produced.context["finding_count"] == 3
    assert produced.context["severity_counts"] == {"blocker": 2, "nit": 1}


def test_review_issues_returns_one_review_per_issue(fake_client):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    node = review_issues(fake_client)

    result = node(
        {
            "issues": [IssueContext(issue_a, []), IssueContext(issue_b, [])],
            "reviews": [],
            "failures": [],
        }
    )

    assert result == {
        "reviews": [
            Review(issue_a, DEFAULT_REVIEW_BODY),
            Review(issue_b, DEFAULT_REVIEW_BODY),
        ],
        "failures": [],
    }


def test_review_issues_sends_title_body_and_comments(fake_client):
    issue_a = Issue(
        "org/a", 1, "issue a", "the body of the issue", "2026-08-01T00:00:00Z"
    )
    comments = [
        Comment("alice", "can you clarify?", "2026-08-01T00:00:00Z"),
        Comment("kandy-angel[bot]", "looks reasonable", "2026-08-02T00:00:00Z"),
    ]
    node = review_issues(fake_client)

    node({"issues": [IssueContext(issue_a, comments)], "reviews": [], "failures": []})

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
    assert "@kandy-angel[bot]: looks reasonable" in content


def test_review_issues_renders_no_comments_fallback(fake_client):
    issue_a = Issue("org/a", 1, "issue a", "body", "2026-08-01T00:00:00Z")
    node = review_issues(fake_client)

    node({"issues": [IssueContext(issue_a, [])], "reviews": [], "failures": []})

    sent = fake_client.calls[-1]
    assert "(none)" in sent[1].content


def test_fetch_issues_isolates_item_failure_within_a_repository(fake_github):
    issue_1 = Issue("org/a", 1, "issue 1", "body", "2026-08-01T00:00:00Z")
    issue_2 = Issue("org/a", 2, "issue 2", "body", "2026-08-01T00:00:00Z")
    issue_3 = Issue("org/a", 3, "issue 3", "body", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_1, issue_2, issue_3]}
    for issue in (issue_1, issue_2, issue_3):
        fake_github.label(issue, LABEL)
    original_list_comments = fake_github.list_comments

    def list_comments(target):
        if target == issue_2:
            raise RuntimeError("boom")
        return original_list_comments(target)

    fake_github.list_comments = list_comments
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result["issues"] == [
        IssueContext(issue_1, []),
        IssueContext(issue_3, []),
    ]
    assert result["failures"] == [
        ItemFailure(
            repository="org/a",
            number=2,
            stage="fetch_issues",
            error_type="RuntimeError",
            error="boom",
        )
    ]


def test_fetch_issues_isolates_repository_failure(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    fake_github.label(issue_a, LABEL)
    fake_github.label(issue_b, LABEL)
    original_list_open_issues = fake_github.list_open_issues

    def list_open_issues(repository, label):
        if repository == "org/a":
            raise RuntimeError("repo boom")
        return original_list_open_issues(repository, label)

    fake_github.list_open_issues = list_open_issues
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"issues": [], "reviews": [], "failures": []})

    assert result["issues"] == [IssueContext(issue_b, [])]
    assert result["failures"] == [
        ItemFailure(
            repository="org/a",
            number=0,
            stage="fetch_issues",
            error_type="RuntimeError",
            error="repo boom",
        )
    ]


def test_fetch_issues_logs_failure_at_warning(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="angel")
    issue = Issue("org/a", 1, "issue a", "body", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.label(issue, LABEL)

    def list_comments(target):
        raise RuntimeError("boom")

    fake_github.list_comments = list_comments
    node = fetch_issues(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"issues": [], "reviews": [], "failures": []})

    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_records) == 1
    assert warning_records[0].context["repository"] == "org/a"
    assert warning_records[0].context["number"] == 1
    assert warning_records[0].context["error"] == "boom"


def test_review_issues_isolates_item_failure(fake_client):
    issue_1 = Issue("org/a", 1, "issue 1", "body", "2026-08-01T00:00:00Z")
    issue_2 = Issue("org/a", 2, "issue 2", "body", "2026-08-01T00:00:00Z")
    issue_3 = Issue("org/a", 3, "issue 3", "body", "2026-08-01T00:00:00Z")
    issue_4 = Issue("org/a", 4, "issue 4", "body", "2026-08-01T00:00:00Z")
    issue_5 = Issue("org/a", 5, "issue 5", "body", "2026-08-01T00:00:00Z")

    class RaisingOnThirdClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            return AIMessage(content="ok")

        def complete_structured(self, messages, schema):
            self.calls += 1
            if self.calls == 3:
                raise RuntimeError("model boom")
            return schema(summary="ok", findings=[])

    client = RaisingOnThirdClient()
    node = review_issues(client)

    result = node(
        {
            "issues": [
                IssueContext(issue, [])
                for issue in (issue_1, issue_2, issue_3, issue_4, issue_5)
            ],
            "reviews": [],
            "failures": [],
        }
    )

    assert len(result["reviews"]) == 4
    assert result["failures"] == [
        ItemFailure(
            repository="org/a",
            number=3,
            stage="review_issues",
            error_type="RuntimeError",
            error="model boom",
        )
    ]


def test_review_issues_logs_failure_at_warning(caplog):
    caplog.set_level(logging.DEBUG, logger="angel")
    issue_a = Issue("org/a", 1, "issue a", "body", "2026-08-01T00:00:00Z")

    class RaisingClient:
        def complete(self, messages):
            return AIMessage(content="ok")

        def complete_structured(self, messages, schema):
            raise RuntimeError("model boom")

    node = review_issues(RaisingClient())

    node({"issues": [IssueContext(issue_a, [])], "reviews": [], "failures": []})

    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_records) == 1
    assert warning_records[0].context["repository"] == "org/a"
    assert warning_records[0].context["number"] == 1
    assert warning_records[0].context["error"] == "model boom"
