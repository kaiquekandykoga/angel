from nishikihebi.clients.github import PullRequest
from nishikihebi.graphs.pr_review import build_pr_review_graph
from nishikihebi.state import Review


def test_graph_posts_one_comment_per_labeled_pull_request(fake_client, fake_github):
    pr_a = PullRequest("kaiquekandykoga/nishikihebi", 1, "pr a")
    fake_github.pull_requests = {"kaiquekandykoga/nishikihebi": [pr_a]}
    fake_github.diffs = {pr_a: "diff a"}
    graph = build_pr_review_graph(
        fake_client,
        fake_github,
        repositories=("kaiquekandykoga/nishikihebi",),
        label="nishikihebi",
    )

    result = graph.invoke({"pull_requests": [], "reviews": []})

    assert result["reviews"] == [Review(pr_a, fake_client.reply)]
    assert fake_github.posted_comments == [(pr_a, fake_client.reply)]
    assert "diff a" in fake_client.calls[-1][-1].content


def test_graph_covers_multiple_repositories(fake_client, fake_github):
    pr_a = PullRequest("org/a", 1, "pr a")
    pr_b = PullRequest("org/b", 2, "pr b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.diffs = {pr_a: "diff a", pr_b: "diff b"}
    graph = build_pr_review_graph(
        fake_client, fake_github, repositories=("org/a", "org/b"), label="nishikihebi"
    )

    result = graph.invoke({"pull_requests": [], "reviews": []})

    assert {review.target for review in result["reviews"]} == {pr_a, pr_b}
    assert {pr for pr, _ in fake_github.posted_comments} == {pr_a, pr_b}
