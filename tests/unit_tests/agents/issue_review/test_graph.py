import logging

from langchain_core.messages import AIMessage

from angel.agents._shared import (
    Finding,
    IssueReviewOutput,
    Review,
    Severity,
    render_issue_review,
)
from angel.agents.issue_review.graph import build_issue_review_graph
from angel.clients.github import Comment, Issue

REVIEWER_LOGIN = "kandy-angel[bot]"
LABEL = "angel"

DEFAULT_REVIEW_BODY = render_issue_review(
    IssueReviewOutput(
        summary="fake summary",
        findings=[
            Finding(severity=Severity.MINOR, title="fake finding", detail="fake detail")
        ],
    )
)


def test_build_issue_review_graph_logs_wiring_and_ready(
    fake_client, fake_github, caplog
):
    caplog.set_level(logging.DEBUG, logger="angel")

    build_issue_review_graph(
        fake_client, fake_github, reviewer_login=REVIEWER_LOGIN, label=LABEL
    )

    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any(
        getattr(r, "context", {}).get("reviewer_login") == REVIEWER_LOGIN
        and getattr(r, "context", {}).get("label") == LABEL
        for r in debug_records
    )
    assert any(r.levelname == "INFO" for r in caplog.records)


def test_graph_posts_comment_for_never_reviewed_issue(fake_client, fake_github):
    issue_a = Issue(
        "monalisa/hello-world", 1, "issue a", "body a", "2026-08-01T00:00:00Z"
    )
    fake_github.issues = {"monalisa/hello-world": [issue_a]}
    fake_github.label(issue_a, LABEL)
    graph = build_issue_review_graph(
        fake_client,
        fake_github,
        reviewer_login=REVIEWER_LOGIN,
    )

    result = graph.invoke({"issues": [], "reviews": []})

    assert result["reviews"] == [Review(issue_a, DEFAULT_REVIEW_BODY)]
    assert fake_github.posted_comments == [(issue_a, DEFAULT_REVIEW_BODY)]
    assert "body a" in fake_client.calls[-1][-1].content


def test_graph_posts_no_comment_for_already_reviewed_unchanged_issue(
    fake_client, fake_github
):
    issue_a = Issue(
        "monalisa/hello-world", 1, "issue a", "body a", "2026-08-01T00:00:00Z"
    )
    fake_github.issues = {"monalisa/hello-world": [issue_a]}
    fake_github.comments = {
        issue_a: [Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")]
    }
    fake_github.label(issue_a, LABEL)
    graph = build_issue_review_graph(
        fake_client,
        fake_github,
        reviewer_login=REVIEWER_LOGIN,
    )

    result = graph.invoke({"issues": [], "reviews": []})

    assert result["reviews"] == []
    assert fake_github.posted_comments == []


def test_graph_covers_every_repository_of_the_installation(fake_client, fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    fake_github.label(issue_a, LABEL)
    fake_github.label(issue_b, LABEL)
    graph = build_issue_review_graph(
        fake_client,
        fake_github,
        reviewer_login=REVIEWER_LOGIN,
    )

    result = graph.invoke({"issues": [], "reviews": []})

    assert {review.target for review in result["reviews"]} == {issue_a, issue_b}
    assert {target for target, _ in fake_github.posted_comments} == {issue_a, issue_b}


def test_graph_nodes_carry_a_retry_policy(fake_client, fake_github):
    graph = build_issue_review_graph(
        fake_client, fake_github, reviewer_login=REVIEWER_LOGIN
    )

    for name in ("fetch_issues", "review_issues", "post_review_comments"):
        retry_policy = graph.nodes[name].retry_policy
        assert retry_policy is not None
        assert retry_policy[0].max_attempts == 3


def test_graph_isolates_a_review_failure_and_posts_the_rest(fake_github):
    issues = [
        Issue("org/a", n, f"issue {n}", "body", "2026-08-01T00:00:00Z")
        for n in range(1, 6)
    ]
    fake_github.issues = {"org/a": issues}
    for issue in issues:
        fake_github.label(issue, LABEL)

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

    graph = build_issue_review_graph(
        RaisingOnThirdClient(), fake_github, reviewer_login=REVIEWER_LOGIN
    )

    result = graph.invoke({"issues": [], "reviews": [], "failures": []})

    assert len(fake_github.posted_comments) == 4
    assert len(result["failures"]) == 1


def test_graph_isolates_a_structured_output_failure_and_posts_the_other(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    fake_github.label(issue_a, LABEL)
    fake_github.label(issue_b, LABEL)

    class RaisingOnSecondClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            return AIMessage(content="ok")

        def complete_structured(self, messages, schema):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("schema boom")
            return schema(summary="ok", findings=[])

    graph = build_issue_review_graph(
        RaisingOnSecondClient(), fake_github, reviewer_login=REVIEWER_LOGIN
    )

    result = graph.invoke({"issues": [], "reviews": [], "failures": []})

    assert len(result["reviews"]) == 1
    assert len(result["failures"]) == 1
    assert {issue for issue, _ in fake_github.posted_comments} == {issue_a}
