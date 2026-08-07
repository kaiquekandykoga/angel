from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.clients.github import Comment, PullRequest
from nishikihebi.nodes.github.review_pull_requests import (
    REVIEW_SYSTEM_PROMPT,
    review_pull_requests,
)
from nishikihebi.states.github import PullRequestContext, Review


def test_review_pull_requests_returns_one_review_per_pull_request(
    fake_client, fake_github
):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.diffs = {pr_a: "diff a", pr_b: "diff b"}
    node = review_pull_requests(fake_github, fake_client)

    result = node(
        {
            "pull_requests": [
                PullRequestContext(pr_a, []),
                PullRequestContext(pr_b, []),
            ],
            "reviews": [],
        }
    )

    assert result == {
        "reviews": [
            Review(pr_a, fake_client.reply),
            Review(pr_b, fake_client.reply),
        ]
    }


def test_review_pull_requests_sends_title_body_comments_and_diff(
    fake_client, fake_github
):
    pr_a = PullRequest("org/a", 1, "pr a", "the pr description", "sha-a")
    fake_github.diffs = {pr_a: "diff --git a/x b/x"}
    comments = [
        Comment("alice", "please add tests", "2026-08-01T00:00:00Z"),
        Comment("kandy-nishikihebi[bot]", "looks fine", "2026-08-02T00:00:00Z"),
    ]
    node = review_pull_requests(fake_github, fake_client)

    node({"pull_requests": [PullRequestContext(pr_a, comments)], "reviews": []})

    sent = fake_client.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == REVIEW_SYSTEM_PROMPT
    assert isinstance(sent[1], HumanMessage)
    content = sent[1].content
    assert "diff --git a/x b/x" in content
    assert "org/a" in content
    assert "1" in content
    assert "pr a" in content
    assert "the pr description" in content
    assert "@alice: please add tests" in content
    assert "@kandy-nishikihebi[bot]: looks fine" in content


def test_review_pull_requests_renders_no_comments_fallback(fake_client, fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.diffs = {pr_a: "diff a"}
    node = review_pull_requests(fake_github, fake_client)

    node({"pull_requests": [PullRequestContext(pr_a, [])], "reviews": []})

    sent = fake_client.calls[-1]
    assert "(none)" in sent[1].content
