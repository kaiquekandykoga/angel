from nishikihebi.clients.github import Issue
from nishikihebi.graphs.issue_review import build_issue_review_graph
from nishikihebi.state import Review


def test_graph_posts_one_comment_per_labeled_issue(fake_client, fake_github):
    issue_a = Issue("kaiquekandykoga/nishikihebi", 1, "issue a", "body a")
    fake_github.issues = {"kaiquekandykoga/nishikihebi": [issue_a]}
    graph = build_issue_review_graph(
        fake_client,
        fake_github,
        repositories=("kaiquekandykoga/nishikihebi",),
        label="nishikihebi",
    )

    result = graph.invoke({"issues": [], "reviews": []})

    assert result["reviews"] == [Review(issue_a, fake_client.reply)]
    assert fake_github.posted_comments == [(issue_a, fake_client.reply)]
    assert "body a" in fake_client.calls[-1][-1].content


def test_graph_covers_multiple_repositories(fake_client, fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a")
    issue_b = Issue("org/b", 2, "issue b", "body b")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    graph = build_issue_review_graph(
        fake_client, fake_github, repositories=("org/a", "org/b"), label="nishikihebi"
    )

    result = graph.invoke({"issues": [], "reviews": []})

    assert {review.target for review in result["reviews"]} == {issue_a, issue_b}
    assert {target for target, _ in fake_github.posted_comments} == {issue_a, issue_b}
