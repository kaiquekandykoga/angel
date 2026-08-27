import logging

from langchain_core.messages import AIMessage

from nishikihebi.agents._shared import Review, review_marker
from nishikihebi.agents.pr_review.graph import build_pr_review_graph
from nishikihebi.agents.pr_review.prompts import REVIEW_LENSES
from nishikihebi.clients.github import Comment, PullRequest

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"
LABEL = "nishikihebi"

DEFAULT_REVIEW_BODY = (
    "\n\n".join(f"**{lens.capitalize()}:** fake summary" for lens, _ in REVIEW_LENSES)
    + "\n\n"
    + "\n\n".join(
        f"### {lens.capitalize()}\n\n"
        "**[minor] fake finding**\nfake detail"
        for lens, _ in REVIEW_LENSES
    )
)


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
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    fake_github.pull_requests = {"monalisa/hello-world": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    fake_github.label(pr_a, LABEL)
    graph = build_pr_review_graph(
        fake_client,
        fake_github,
        reviewer_login=REVIEWER_LOGIN,
    )

    result = graph.invoke({"pull_requests": [], "reviews": []})

    expected_body = f"{DEFAULT_REVIEW_BODY}\n\n{review_marker('sha-a')}"
    assert result["reviews"] == [Review(pr_a, expected_body)]
    assert fake_github.posted_comments == [(pr_a, expected_body)]
    assert "diff a" in fake_client.calls[-1][-1].content


def test_graph_posts_no_comment_for_already_reviewed_unchanged_pull_request(
    fake_client, fake_github
):
    pr_a = PullRequest("monalisa/hello-world", 1, "pr a", "body a", "sha-a")
    review_comment_created_at = "2026-08-02T00:00:00Z"
    fake_github.pull_requests = {"monalisa/hello-world": [pr_a]}
    fake_github.comments = {
        pr_a: [
            Comment(
                REVIEWER_LOGIN,
                f"reviewed\n\n{review_marker('sha-a')}",
                review_comment_created_at,
            )
        ]
    }
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


def test_graph_nodes_carry_a_retry_policy(fake_client, fake_github):
    graph = build_pr_review_graph(
        fake_client, fake_github, reviewer_login=REVIEWER_LOGIN
    )

    for name in ("fetch_pull_requests", "review_pull_requests", "post_review_comments"):
        retry_policy = graph.nodes[name].retry_policy
        assert retry_policy is not None
        assert retry_policy[0].max_attempts == 3


def test_graph_isolates_a_review_failure_and_posts_the_rest(fake_github):
    pull_requests = [
        PullRequest("org/a", n, f"pr {n}", "body", f"sha-{n}") for n in range(1, 6)
    ]
    fake_github.pull_requests = {"org/a": pull_requests}
    for pr in pull_requests:
        fake_github.label(pr, LABEL)
        fake_github.diffs[pr] = f"diff {pr.number}"

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

    graph = build_pr_review_graph(
        RaisingOnThirdClient(), fake_github, reviewer_login=REVIEWER_LOGIN
    )

    result = graph.invoke({"pull_requests": [], "reviews": [], "failures": []})

    assert len(fake_github.posted_comments) == 4
    assert len(result["failures"]) == 1


def test_graph_isolates_a_structured_output_failure_and_posts_the_other(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.diffs = {pr_a: "diff a", pr_b: "diff b"}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)

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

    graph = build_pr_review_graph(
        RaisingOnSecondClient(), fake_github, reviewer_login=REVIEWER_LOGIN
    )

    result = graph.invoke({"pull_requests": [], "reviews": [], "failures": []})

    assert len(result["reviews"]) == 1
    assert len(result["failures"]) == 1
    assert {pr for pr, _ in fake_github.posted_comments} == {pr_b}
