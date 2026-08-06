from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.clients.github import PullRequest
from nishikihebi.nodes.review_pull_requests import (
    REVIEW_SYSTEM_PROMPT,
    review_pull_requests,
)
from nishikihebi.state import Review


def test_review_pull_requests_returns_one_review_per_pull_request(
    fake_client, fake_github
):
    pr_a = PullRequest("org/a", 1, "pr a")
    pr_b = PullRequest("org/b", 2, "pr b")
    fake_github.diffs = {pr_a: "diff a", pr_b: "diff b"}
    node = review_pull_requests(fake_github, fake_client)

    result = node({"pull_requests": [pr_a, pr_b], "reviews": []})

    assert result == {
        "reviews": [
            Review(pr_a, fake_client.reply),
            Review(pr_b, fake_client.reply),
        ]
    }


def test_review_pull_requests_sends_diff_and_system_prompt(fake_client, fake_github):
    pr_a = PullRequest("org/a", 1, "pr a")
    fake_github.diffs = {pr_a: "diff --git a/x b/x"}
    node = review_pull_requests(fake_github, fake_client)

    node({"pull_requests": [pr_a], "reviews": []})

    sent = fake_client.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == REVIEW_SYSTEM_PROMPT
    assert isinstance(sent[1], HumanMessage)
    assert "diff --git a/x b/x" in sent[1].content
    assert "org/a" in sent[1].content
    assert "1" in sent[1].content
    assert "pr a" in sent[1].content
