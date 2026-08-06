from nishikihebi.clients.github import PullRequest
from nishikihebi.nodes.fetch_pull_requests import fetch_pull_requests


def test_fetch_pull_requests_concatenates_across_repositories(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a")
    pr_b = PullRequest("org/b", 2, "pr b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    node = fetch_pull_requests(fake_github, ["org/a", "org/b"], "nishikihebi")

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [pr_a, pr_b]}
