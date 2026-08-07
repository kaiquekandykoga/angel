from nishikihebi.clients.github import Issue
from nishikihebi.nodes.github.fetch_issues import fetch_issues


def test_fetch_issues_concatenates_across_repositories(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a")
    issue_b = Issue("org/b", 2, "issue b", "body b")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    node = fetch_issues(fake_github, ["org/a", "org/b"], "nishikihebi")

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [issue_a, issue_b]}
