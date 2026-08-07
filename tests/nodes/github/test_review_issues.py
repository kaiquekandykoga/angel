from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.clients.github import Comment, Issue
from nishikihebi.nodes.github.review_issues import REVIEW_SYSTEM_PROMPT, review_issues
from nishikihebi.states.github import IssueContext, Review


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
