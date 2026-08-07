import logging

from nishikihebi.clients.github import Issue, PullRequest
from nishikihebi.nodes.github.post_review_comments import post_review_comments
from nishikihebi.states.github import IssueContext, PullRequestContext, Review


def test_post_review_comments_logs_count_per_comment_and_posted(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    node = post_review_comments(fake_github)

    node(
        {
            "pull_requests": [PullRequestContext(pr_a, [])],
            "reviews": [Review(pr_a, "review a")],
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
        }
    )

    assert result == {}
    assert fake_github.posted_comments == [(pr_a, "review a"), (pr_b, "review b")]


def test_post_review_comments_posts_comment_for_issue_target(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    node = post_review_comments(fake_github)

    result = node(
        {
            "issues": [IssueContext(issue_a, [])],
            "reviews": [Review(issue_a, "review a")],
        }
    )

    assert result == {}
    assert fake_github.posted_comments == [(issue_a, "review a")]
