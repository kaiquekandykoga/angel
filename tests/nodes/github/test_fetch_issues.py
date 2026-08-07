from nishikihebi.clients.github import Comment, Issue
from nishikihebi.nodes.github.fetch_issues import fetch_issues
from nishikihebi.states.github import IssueContext

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"


def test_fetch_issues_includes_issue_with_no_reviewer_comment(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [IssueContext(issue, [])]}


def test_fetch_issues_includes_issue_updated_after_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-02T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [IssueContext(issue, [review_comment])]}


def test_fetch_issues_excludes_issue_updated_at_equal_to_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": []}


def test_fetch_issues_excludes_issue_updated_before_last_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [review_comment]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": []}


def test_fetch_issues_other_author_comments_do_not_count_as_review(fake_github):
    issue = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    other_comment = Comment("someone-else", "hi", "2026-08-02T00:00:00Z")
    fake_github.issues = {"org/a": [issue]}
    fake_github.comments = {issue: [other_comment]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN)

    result = node({"issues": [], "reviews": []})

    assert result == {"issues": [IssueContext(issue, [other_comment])]}


def test_fetch_issues_covers_every_repository_of_the_installation(fake_github):
    issue_a = Issue("org/a", 1, "issue a", "body a", "2026-08-01T00:00:00Z")
    issue_b = Issue("org/b", 2, "issue b", "body b", "2026-08-01T00:00:00Z")
    fake_github.issues = {"org/a": [issue_a], "org/b": [issue_b]}
    node = fetch_issues(fake_github, REVIEWER_LOGIN)

    result = node({"issues": [], "reviews": []})

    assert result == {
        "issues": [IssueContext(issue_a, []), IssueContext(issue_b, [])]
    }
