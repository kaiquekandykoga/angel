from nishikihebi.clients.github import Issue, PullRequest
from nishikihebi.nodes.post_review_comments import post_review_comments
from nishikihebi.state import Review


def test_post_review_comments_posts_one_comment_per_review(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a")
    pr_b = PullRequest("org/b", 2, "pr b")
    node = post_review_comments(fake_github)

    result = node(
        {
            "pull_requests": [pr_a, pr_b],
            "reviews": [Review(pr_a, "review a"), Review(pr_b, "review b")],
        }
    )

    assert result == {}
    assert fake_github.posted_comments == [(pr_a, "review a"), (pr_b, "review b")]


def test_post_review_comments_posts_comment_for_issue_target(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a")
    node = post_review_comments(fake_github)

    result = node({"issues": [issue_a], "reviews": [Review(issue_a, "review a")]})

    assert result == {}
    assert fake_github.posted_comments == [(issue_a, "review a")]
