from nishikihebi.clients.github import Comment, PullRequest
from nishikihebi.nodes.github.fetch_pull_requests import fetch_pull_requests
from nishikihebi.states.github import PullRequestContext

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"


def test_fetch_pull_requests_includes_pr_with_no_comments(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [])]}


def test_fetch_pull_requests_includes_pr_with_only_other_author_comments(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    other_comment = Comment("someone-else", "hi", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [other_comment]}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [other_comment])]}


def test_fetch_pull_requests_includes_pr_with_newer_head_commit(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-02T00:00:00Z"}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [review_comment])]}


def test_fetch_pull_requests_excludes_pr_unchanged_since_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_excludes_pr_with_head_commit_equal_to_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_covers_every_repository_of_the_installation(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {
        "pull_requests": [
            PullRequestContext(pr_a, []),
            PullRequestContext(pr_b, []),
        ]
    }
