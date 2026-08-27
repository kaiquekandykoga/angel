import logging

import pytest
from pydantic import ValidationError

from angel.agents._shared import (
    Finding,
    IssueReviewOutput,
    ItemFailure,
    Review,
    Severity,
    last_review_at,
    post_review_comments,
    render_comments,
    render_issue_review,
    review_marker,
    reviewed_sha,
)
from angel.agents.issue_review.state import IssueContext
from angel.agents.pr_review.state import PullRequestContext
from angel.clients.github import Comment, Issue, PullRequest


def test_last_review_at_returns_none_when_reviewer_never_commented():
    comments = [Comment("someone-else", "hi", "2026-08-01T00:00:00Z")]

    assert last_review_at(comments, "kandy-angel[bot]") is None


def test_last_review_at_returns_most_recent_reviewer_comment():
    comments = [
        Comment("kandy-angel[bot]", "first", "2026-08-01T00:00:00Z"),
        Comment("someone-else", "hi", "2026-08-02T00:00:00Z"),
        Comment("kandy-angel[bot]", "second", "2026-08-03T00:00:00Z"),
    ]

    assert last_review_at(comments, "kandy-angel[bot]") == "2026-08-03T00:00:00Z"


def test_review_marker_renders_sha():
    assert review_marker("abc123") == "<!-- angel: sha=abc123 -->"


def test_reviewed_sha_round_trips_through_review_marker():
    comments = [
        Comment("kandy-angel[bot]", review_marker("abc"), "2026-08-01T00:00:00Z")
    ]

    assert reviewed_sha(comments, "kandy-angel[bot]") == "abc"


def test_reviewed_sha_returns_none_when_no_bot_comment():
    comments = [Comment("someone-else", review_marker("abc"), "2026-08-01T00:00:00Z")]

    assert reviewed_sha(comments, "kandy-angel[bot]") is None


def test_reviewed_sha_returns_none_when_bot_commented_without_marker():
    comments = [Comment("kandy-angel[bot]", "looks good", "2026-08-01T00:00:00Z")]

    assert reviewed_sha(comments, "kandy-angel[bot]") is None


def test_reviewed_sha_uses_most_recent_bot_comment_with_a_marker():
    comments = [
        Comment(
            "kandy-angel[bot]",
            f"first\n\n{review_marker('old-sha')}",
            "2026-08-01T00:00:00Z",
        ),
        Comment("someone-else", "hi", "2026-08-02T00:00:00Z"),
        Comment(
            "kandy-angel[bot]",
            f"second\n\n{review_marker('new-sha')}",
            "2026-08-03T00:00:00Z",
        ),
    ]

    assert reviewed_sha(comments, "kandy-angel[bot]") == "new-sha"


def test_reviewed_sha_ignores_markers_from_other_authors():
    comments = [
        Comment(
            "someone-else",
            review_marker("attacker-sha"),
            "2026-08-05T00:00:00Z",
        ),
        Comment(
            "kandy-angel[bot]",
            f"reviewed\n\n{review_marker('real-sha')}",
            "2026-08-01T00:00:00Z",
        ),
    ]

    assert reviewed_sha(comments, "kandy-angel[bot]") == "real-sha"


def test_reviewed_sha_uses_last_marker_in_a_single_comment_body():
    comments = [
        Comment(
            "kandy-angel[bot]",
            f"quoting {review_marker('quoted')} in the middle\n\n"
            f"{review_marker('real')}",
            "2026-08-01T00:00:00Z",
        ),
    ]

    assert reviewed_sha(comments, "kandy-angel[bot]") == "real"


def test_render_comments_formats_author_and_body():
    comments = [
        Comment("alice", "looks good", "2026-08-01T00:00:00Z"),
        Comment("bob", "needs work", "2026-08-02T00:00:00Z"),
    ]

    assert render_comments(comments) == "@alice: looks good\n\n@bob: needs work"


def test_render_comments_falls_back_when_empty():
    assert render_comments([]) == "(none)"


def test_post_review_comments_logs_count_per_comment_and_posted(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="angel")
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    node = post_review_comments(fake_github)

    node(
        {
            "pull_requests": [PullRequestContext(pr_a, [])],
            "reviews": [Review(pr_a, "review a")],
            "failures": [],
        }
    )

    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any("posting 1" in r.message for r in info_records)
    assert any(
        getattr(r, "context", {}).get("repository") == "org/a"
        and getattr(r, "context", {}).get("number") == 1
        and "body_length" in r.context
        for r in debug_records
    )
    assert any("posted org/a#1" in r.message for r in info_records)


def test_post_review_comments_posts_one_comment_per_review(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    node = post_review_comments(fake_github)

    result = node(
        {
            "pull_requests": [
                PullRequestContext(pr_a, []),
                PullRequestContext(pr_b, []),
            ],
            "reviews": [Review(pr_a, "review a"), Review(pr_b, "review b")],
            "failures": [],
        }
    )

    assert result == {"failures": []}
    assert fake_github.posted_comments == [(pr_a, "review a"), (pr_b, "review b")]


def test_post_review_comments_posts_comment_for_issue_target(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    node = post_review_comments(fake_github)

    result = node(
        {
            "issues": [IssueContext(issue_a, [])],
            "reviews": [Review(issue_a, "review a")],
            "failures": [],
        }
    )

    assert result == {"failures": []}
    assert fake_github.posted_comments == [(issue_a, "review a")]


def test_post_review_comments_isolates_a_failing_post(fake_github):
    pull_requests = [
        PullRequest(f"org/{i}", i, f"pr {i}", "body", f"sha-{i}") for i in range(5)
    ]
    reviews = [Review(pr, f"review {pr.number}") for pr in pull_requests]
    failing_pr = pull_requests[2]
    error = ValueError("boom")
    original_post_comment = fake_github.post_comment

    def post_comment(target, body):
        if target == failing_pr:
            raise error
        original_post_comment(target, body)

    fake_github.post_comment = post_comment
    node = post_review_comments(fake_github)

    result = node(
        {
            "pull_requests": [PullRequestContext(pr, []) for pr in pull_requests],
            "reviews": reviews,
            "failures": [],
        }
    )

    assert fake_github.posted_comments == [
        (pr, f"review {pr.number}") for pr in pull_requests if pr != failing_pr
    ]
    assert result == {
        "failures": [
            ItemFailure(
                repository="org/2",
                number=2,
                stage="post_review_comments",
                error_type="ValueError",
                error="boom",
            )
        ]
    }


def test_post_review_comments_logs_failure_at_warning(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="angel")
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    error = RuntimeError("nope")

    def post_comment(target, body):
        raise error

    fake_github.post_comment = post_comment
    node = post_review_comments(fake_github)

    node(
        {
            "pull_requests": [PullRequestContext(pr_a, [])],
            "reviews": [Review(pr_a, "review a")],
            "failures": [],
        }
    )

    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        r.context["repository"] == "org/a"
        and r.context["number"] == 1
        and r.context["error"] == "nope"
        for r in warning_records
    )


def test_render_issue_review_with_criteria_and_approach():
    output = IssueReviewOutput(
        summary="Reasonable issue.",
        findings=[
            Finding(
                severity=Severity.MINOR,
                title="Vague title",
                detail="Could be more specific.",
            )
        ],
        acceptance_criteria=["Does X", "Does Y"],
        suggested_approach="Start by refactoring the parser.",
    )

    assert render_issue_review(output) == (
        "Reasonable issue.\n\n"
        "### Findings\n\n"
        "**[minor] Vague title**\n"
        "Could be more specific.\n\n"
        "### Acceptance criteria\n\n"
        "- Does X\n"
        "- Does Y\n\n"
        "### Suggested approach\n\n"
        "Start by refactoring the parser."
    )


def test_render_issue_review_without_criteria_or_approach():
    output = IssueReviewOutput(summary="Fine.", findings=[])

    assert render_issue_review(output) == "Fine.\n\nNo findings."


def test_finding_rejects_unknown_severity():
    with pytest.raises(ValidationError):
        Finding.model_validate({"severity": "critical", "title": "t", "detail": "d"})


def test_finding_rejects_extra_field():
    with pytest.raises(ValidationError):
        Finding.model_validate(
            {
                "severity": Severity.MINOR,
                "title": "t",
                "detail": "d",
                "unexpected": "nope",
            }
        )
