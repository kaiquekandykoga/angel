import logging

from nishikihebi.clients.github import Comment, PullRequest
from nishikihebi.graphs.github.pr_review import build_pr_review_graph
from nishikihebi.states.github import Review

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"
LABEL = "nishikihebi"


def test_build_pr_review_graph_logs_wiring_and_ready(fake_client, fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")

    build_pr_review_graph(
        fake_client, fake_github, reviewer_login=REVIEWER_LOGIN, label=LABEL
    )

    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any(
        getattr(r, "context", {}).get("reviewer_login") == REVIEWER_LOGIN
        and getattr(r, "context", {}).get("label") == LABEL
        for r in debug_records
    )
    assert any(r.levelname == "INFO" for r in caplog.records)


def test_graph_posts_comment_for_never_reviewed_pull_request(fake_client, fake_github):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, LABEL)
    graph = build_pr_review_graph(
        fake_client,
        fake_github,
        reviewer_login=REVIEWER_LOGIN,
    )

    result = graph.invoke({"pull_requests": [], "reviews": []})

    assert result["reviews"] == [Review(pr_a, fake_client.reply)]
    assert fake_github.posted_comments == [(pr_a, fake_client.reply)]
    assert "diff a" in fake_client.calls[-1][-1].content


def test_graph_posts_no_comment_for_already_reviewed_unchanged_pull_request(
    fake_client, fake_github
):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a", "body a", "sha-a")
    review_comment_created_at = "2026-08-02T00:00:00Z"
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.comments = {
        pr_a: [Comment(REVIEWER_LOGIN, "reviewed", review_comment_created_at)]
    }
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    fake_github.label(pr_a, LABEL)
    graph = build_pr_review_graph(
        fake_client,
        fake_github,
        reviewer_login=REVIEWER_LOGIN,
    )

    result = graph.invoke({"pull_requests": [], "reviews": []})

    assert result["reviews"] == []
    assert fake_github.posted_comments == []


def test_graph_covers_every_repository_of_the_installation(fake_client, fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.diffs = {pr_a: "diff a", pr_b: "diff b"}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    graph = build_pr_review_graph(
        fake_client,
        fake_github,
        reviewer_login=REVIEWER_LOGIN,
    )

    result = graph.invoke({"pull_requests": [], "reviews": []})

    assert {review.target for review in result["reviews"]} == {pr_a, pr_b}
    assert {pr for pr, _ in fake_github.posted_comments} == {pr_a, pr_b}
