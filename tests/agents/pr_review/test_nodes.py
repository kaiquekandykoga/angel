import logging

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.agents._shared import Review
from nishikihebi.agents.pr_review.nodes import fetch_pull_requests, review_pull_requests
from nishikihebi.agents.pr_review.prompts import REVIEW_SYSTEM_PROMPT
from nishikihebi.agents.pr_review.state import PullRequestContext
from nishikihebi.clients.github import Comment, PullRequest

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"
LABEL = "nishikihebi"
LABEL_COLOR = "f709c2"


def test_fetch_pull_requests_logs_start_per_repository_and_summary(
    fake_github, caplog
):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"pull_requests": [], "reviews": []})

    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any("fetch" in r.message.lower() for r in info_records)
    summary = info_records[-1]
    assert summary.context["repositories_scanned"] == 1
    assert summary.context["items_scanned"] == 1
    assert summary.context["items_due_for_review"] == 1
    assert any(r.context.get("repository") == "org/a" for r in debug_records)
    assert any(
        r.context.get("selected") is True
        and r.context.get("reason") == "never reviewed"
        for r in debug_records
    )


def test_fetch_pull_requests_includes_pr_with_no_comments(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [])]}


def test_fetch_pull_requests_includes_pr_with_only_other_author_comments(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    other_comment = Comment("someone-else", "hi", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [other_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [other_comment])]}


def test_fetch_pull_requests_includes_pr_with_newer_head_commit(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-02T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [review_comment])]}


def test_fetch_pull_requests_excludes_pr_unchanged_since_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_excludes_pr_with_head_commit_equal_to_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_covers_every_repository_of_the_installation(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {
        "pull_requests": [
            PullRequestContext(pr_a, []),
            PullRequestContext(pr_b, []),
        ]
    }


def test_fetch_pull_requests_excludes_unlabeled_pr_never_reviewed(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_excludes_labeled_pr_not_due_for_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(REVIEWER_LOGIN, "reviewed", "2026-08-02T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.commit_dates = {"sha-a": "2026-08-01T00:00:00Z"}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": []})

    assert result == {"pull_requests": []}


def test_fetch_pull_requests_calls_ensure_label_once_per_repository(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"pull_requests": [], "reviews": []})

    assert fake_github.ensure_label_calls == [
        ("org/a", LABEL, LABEL_COLOR),
        ("org/b", LABEL, LABEL_COLOR),
    ]
    assert fake_github.call_log == [
        ("ensure_label", "org/a"),
        ("list_open_pull_requests", "org/a"),
        ("ensure_label", "org/b"),
        ("list_open_pull_requests", "org/b"),
    ]


def test_review_pull_requests_logs_start_per_item_and_end(
    fake_client, fake_github, caplog
):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    fake_github.diffs = {pr_a: "diff a"}
    node = review_pull_requests(fake_github, fake_client)

    node({"pull_requests": [PullRequestContext(pr_a, [])], "reviews": []})

    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any("reviewing 1" in r.message for r in info_records)
    assert any(
        getattr(r, "context", {}).get("repository") == "org/a"
        and getattr(r, "context", {}).get("number") == 1
        for r in info_records
    )
    assert any(
        "diff_size" in getattr(r, "context", {})
        and "prompt_message_count" in getattr(r, "context", {})
        for r in debug_records
    )
    assert info_records[-1].context["count"] == 1


def test_review_pull_requests_returns_one_review_per_pull_request(
    fake_client, fake_github
):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.diffs = {pr_a: "diff a", pr_b: "diff b"}
    node = review_pull_requests(fake_github, fake_client)

    result = node(
        {
            "pull_requests": [
                PullRequestContext(pr_a, []),
                PullRequestContext(pr_b, []),
            ],
            "reviews": [],
        }
    )

    assert result == {
        "reviews": [
            Review(pr_a, fake_client.reply),
            Review(pr_b, fake_client.reply),
        ]
    }


def test_review_pull_requests_sends_title_body_comments_and_diff(
    fake_client, fake_github
):
    pr_a = PullRequest("org/a", 1, "pr a", "the pr description", "sha-a")
    fake_github.diffs = {pr_a: "diff --git a/x b/x"}
    comments = [
        Comment("alice", "please add tests", "2026-08-01T00:00:00Z"),
        Comment("kandy-nishikihebi[bot]", "looks fine", "2026-08-02T00:00:00Z"),
    ]
    node = review_pull_requests(fake_github, fake_client)

    node({"pull_requests": [PullRequestContext(pr_a, comments)], "reviews": []})

    sent = fake_client.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == REVIEW_SYSTEM_PROMPT
    assert isinstance(sent[1], HumanMessage)
    content = sent[1].content
    assert "diff --git a/x b/x" in content
    assert "org/a" in content
    assert "1" in content
    assert "pr a" in content
    assert "the pr description" in content
    assert "@alice: please add tests" in content
    assert "@kandy-nishikihebi[bot]: looks fine" in content


def test_review_pull_requests_renders_no_comments_fallback(fake_client, fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.diffs = {pr_a: "diff a"}
    node = review_pull_requests(fake_github, fake_client)

    node({"pull_requests": [PullRequestContext(pr_a, [])], "reviews": []})

    sent = fake_client.calls[-1]
    assert "(none)" in sent[1].content
