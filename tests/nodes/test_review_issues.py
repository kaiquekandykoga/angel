from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.clients.github import Issue
from nishikihebi.nodes.review_issues import REVIEW_SYSTEM_PROMPT, review_issues
from nishikihebi.state import Review


def test_review_issues_returns_one_review_per_issue(fake_client):
    issue_a = Issue("org/a", 1, "issue a", "body a")
    issue_b = Issue("org/b", 2, "issue b", "body b")
    node = review_issues(fake_client)

    result = node({"issues": [issue_a, issue_b], "reviews": []})

    assert result == {
        "reviews": [
            Review(issue_a, fake_client.reply),
            Review(issue_b, fake_client.reply),
        ]
    }


def test_review_issues_sends_body_and_system_prompt(fake_client):
    issue_a = Issue("org/a", 1, "issue a", "the body of the issue")
    node = review_issues(fake_client)

    node({"issues": [issue_a], "reviews": []})

    sent = fake_client.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == REVIEW_SYSTEM_PROMPT
    assert isinstance(sent[1], HumanMessage)
    assert "the body of the issue" in sent[1].content
    assert "org/a" in sent[1].content
    assert "1" in sent[1].content
    assert "issue a" in sent[1].content
