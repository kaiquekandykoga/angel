import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nishikihebi.agents._shared import ItemFailure, Review, review_marker
from nishikihebi.agents.pr_review.nodes import fetch_pull_requests, review_pull_requests
from nishikihebi.agents.pr_review.prompts import REVIEW_SYSTEM_PROMPT
from nishikihebi.agents.pr_review.state import PullRequestContext
from nishikihebi.clients.github import Comment, PullRequest

REVIEWER_LOGIN = "kandy-nishikihebi[bot]"
LABEL = "nishikihebi"
LABEL_COLOR = "f709c2"


def test_fetch_pull_requests_logs_start_per_repository_and_summary(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"pull_requests": [], "reviews": [], "failures": []})

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

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {"pull_requests": [PullRequestContext(pr, [])], "failures": []}


def test_fetch_pull_requests_includes_pr_with_only_other_author_comments(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    other_comment = Comment("someone-else", "hi", "2026-08-01T00:00:00Z")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [other_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {
        "pull_requests": [PullRequestContext(pr, [other_comment])],
        "failures": [],
    }


def test_fetch_pull_requests_includes_pr_with_new_head_sha(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-b")
    review_comment = Comment(
        REVIEWER_LOGIN, f"reviewed\n\n{review_marker('sha-a')}", "2026-08-01T00:00:00Z"
    )
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {
        "pull_requests": [PullRequestContext(pr, [review_comment])],
        "failures": [],
    }


def test_fetch_pull_requests_excludes_pr_with_head_sha_already_reviewed(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(
        REVIEWER_LOGIN, f"reviewed\n\n{review_marker('sha-a')}", "2026-08-01T00:00:00Z"
    )
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {"pull_requests": [], "failures": []}


def test_fetch_pull_requests_includes_pr_when_bot_comment_predates_markers(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(
        REVIEWER_LOGIN, "reviewed, no marker", "2026-08-01T00:00:00Z"
    )
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {
        "pull_requests": [PullRequestContext(pr, [review_comment])],
        "failures": [],
    }


def test_fetch_pull_requests_reports_selection_reasons(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    never_reviewed = PullRequest("org/a", 1, "pr 1", "body", "sha-1")
    no_recorded_head = PullRequest("org/a", 2, "pr 2", "body", "sha-2")
    new_head = PullRequest("org/a", 3, "pr 3", "body", "sha-3-new")
    up_to_date = PullRequest("org/a", 4, "pr 4", "body", "sha-4")
    fake_github.pull_requests = {
        "org/a": [never_reviewed, no_recorded_head, new_head, up_to_date]
    }
    fake_github.comments = {
        no_recorded_head: [
            Comment(REVIEWER_LOGIN, "reviewed, no marker", "2026-08-01T00:00:00Z")
        ],
        new_head: [
            Comment(
                REVIEWER_LOGIN,
                f"reviewed\n\n{review_marker('sha-3-old')}",
                "2026-08-01T00:00:00Z",
            )
        ],
        up_to_date: [
            Comment(
                REVIEWER_LOGIN,
                f"reviewed\n\n{review_marker('sha-4')}",
                "2026-08-01T00:00:00Z",
            )
        ],
    }
    for pr in (never_reviewed, no_recorded_head, new_head, up_to_date):
        fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {
        "pull_requests": [
            PullRequestContext(never_reviewed, []),
            PullRequestContext(
                no_recorded_head, fake_github.comments[no_recorded_head]
            ),
            PullRequestContext(new_head, fake_github.comments[new_head]),
        ],
        "failures": [],
    }
    debug_records = [
        r
        for r in caplog.records
        if r.levelname == "DEBUG" and "reason" in getattr(r, "context", {})
    ]
    reasons = {r.context["number"]: r.context["reason"] for r in debug_records}
    assert reasons[1] == "never reviewed"
    assert reasons[2] == "no recorded head"
    assert reasons[3] == "new head"
    assert reasons[4] == "already up to date"


def test_fetch_pull_requests_selects_pr_by_head_sha_even_with_stale_commit_date(
    fake_github,
):
    pr = PullRequest("org/a", 1, "pr a", "body", "old-force-pushed-sha")
    review_comment = Comment(
        REVIEWER_LOGIN,
        f"reviewed\n\n{review_marker('newer-sha-that-was-reverted')}",
        "2026-08-05T00:00:00Z",
    )
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {
        "pull_requests": [PullRequestContext(pr, [review_comment])],
        "failures": [],
    }


def test_fetch_pull_requests_covers_every_repository_of_the_installation(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {
        "pull_requests": [
            PullRequestContext(pr_a, []),
            PullRequestContext(pr_b, []),
        ],
        "failures": [],
    }


def test_fetch_pull_requests_excludes_unlabeled_pr_never_reviewed(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {"pull_requests": [], "failures": []}


def test_fetch_pull_requests_excludes_labeled_pr_not_due_for_review(fake_github):
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    review_comment = Comment(
        REVIEWER_LOGIN, f"reviewed\n\n{review_marker('sha-a')}", "2026-08-02T00:00:00Z"
    )
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.comments = {pr: [review_comment]}
    fake_github.label(pr, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result == {"pull_requests": [], "failures": []}


def test_fetch_pull_requests_calls_ensure_label_once_per_repository(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"pull_requests": [], "reviews": [], "failures": []})

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

    node(
        {
            "pull_requests": [PullRequestContext(pr_a, [])],
            "reviews": [],
            "failures": [],
        }
    )

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
            "failures": [],
        }
    )

    assert result == {
        "reviews": [
            Review(pr_a, f"{fake_client.reply}\n\n{review_marker('sha-a')}"),
            Review(pr_b, f"{fake_client.reply}\n\n{review_marker('sha-b')}"),
        ],
        "failures": [],
    }


def test_review_pull_requests_appends_head_sha_marker_to_the_body(
    fake_client, fake_github
):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    fake_github.diffs = {pr_a: "diff a"}
    node = review_pull_requests(fake_github, fake_client)

    result = node(
        {
            "pull_requests": [PullRequestContext(pr_a, [])],
            "reviews": [],
            "failures": [],
        }
    )

    assert result == {
        "reviews": [
            Review(pr_a, f"{fake_client.reply}\n\n{review_marker('sha-a')}")
        ],
        "failures": [],
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

    node(
        {
            "pull_requests": [PullRequestContext(pr_a, comments)],
            "reviews": [],
            "failures": [],
        }
    )

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

    node(
        {
            "pull_requests": [PullRequestContext(pr_a, [])],
            "reviews": [],
            "failures": [],
        }
    )

    sent = fake_client.calls[-1]
    assert "(none)" in sent[1].content


def test_fetch_pull_requests_isolates_item_failure_within_a_repository(fake_github):
    pr_1 = PullRequest("org/a", 1, "pr 1", "body", "sha-1")
    pr_2 = PullRequest("org/a", 2, "pr 2", "body", "sha-2")
    pr_3 = PullRequest("org/a", 3, "pr 3", "body", "sha-3")
    fake_github.pull_requests = {"org/a": [pr_1, pr_2, pr_3]}
    for pr in (pr_1, pr_2, pr_3):
        fake_github.label(pr, LABEL)
    original_list_comments = fake_github.list_comments

    def list_comments(target):
        if target == pr_2:
            raise RuntimeError("boom")
        return original_list_comments(target)

    fake_github.list_comments = list_comments
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result["pull_requests"] == [
        PullRequestContext(pr_1, []),
        PullRequestContext(pr_3, []),
    ]
    assert result["failures"] == [
        ItemFailure(
            repository="org/a",
            number=2,
            stage="fetch_pull_requests",
            error_type="RuntimeError",
            error="boom",
        )
    ]


def test_fetch_pull_requests_isolates_repository_failure(fake_github):
    pr_a = PullRequest("org/a", 1, "pr a", "body a", "sha-a")
    pr_b = PullRequest("org/b", 2, "pr b", "body b", "sha-b")
    fake_github.pull_requests = {"org/a": [pr_a], "org/b": [pr_b]}
    fake_github.label(pr_a, LABEL)
    fake_github.label(pr_b, LABEL)
    original_list_open_pull_requests = fake_github.list_open_pull_requests

    def list_open_pull_requests(repository, label):
        if repository == "org/a":
            raise RuntimeError("repo boom")
        return original_list_open_pull_requests(repository, label)

    fake_github.list_open_pull_requests = list_open_pull_requests
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    result = node({"pull_requests": [], "reviews": [], "failures": []})

    assert result["pull_requests"] == [PullRequestContext(pr_b, [])]
    assert result["failures"] == [
        ItemFailure(
            repository="org/a",
            number=0,
            stage="fetch_pull_requests",
            error_type="RuntimeError",
            error="repo boom",
        )
    ]


def test_fetch_pull_requests_logs_failure_at_warning(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    pr = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.pull_requests = {"org/a": [pr]}
    fake_github.label(pr, LABEL)

    def list_comments(target):
        raise RuntimeError("boom")

    fake_github.list_comments = list_comments
    node = fetch_pull_requests(fake_github, REVIEWER_LOGIN, LABEL, LABEL_COLOR)

    node({"pull_requests": [], "reviews": [], "failures": []})

    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_records) == 1
    assert warning_records[0].context["repository"] == "org/a"
    assert warning_records[0].context["number"] == 1
    assert warning_records[0].context["error"] == "boom"


def test_review_pull_requests_isolates_item_failure(fake_github):
    pr_1 = PullRequest("org/a", 1, "pr 1", "body", "sha-1")
    pr_2 = PullRequest("org/a", 2, "pr 2", "body", "sha-2")
    pr_3 = PullRequest("org/a", 3, "pr 3", "body", "sha-3")
    pr_4 = PullRequest("org/a", 4, "pr 4", "body", "sha-4")
    pr_5 = PullRequest("org/a", 5, "pr 5", "body", "sha-5")
    fake_github.diffs = dict.fromkeys((pr_1, pr_2, pr_3, pr_4, pr_5), "diff")

    class RaisingOnThirdClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            if self.calls == 3:
                raise RuntimeError("model boom")
            return AIMessage(content="ok")

    client = RaisingOnThirdClient()
    node = review_pull_requests(fake_github, client)

    result = node(
        {
            "pull_requests": [
                PullRequestContext(pr, []) for pr in (pr_1, pr_2, pr_3, pr_4, pr_5)
            ],
            "reviews": [],
            "failures": [],
        }
    )

    assert len(result["reviews"]) == 4
    assert result["failures"] == [
        ItemFailure(
            repository="org/a",
            number=3,
            stage="review_pull_requests",
            error_type="RuntimeError",
            error="model boom",
        )
    ]


def test_review_pull_requests_logs_failure_at_warning(fake_github, caplog):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    pr_a = PullRequest("org/a", 1, "pr a", "body", "sha-a")
    fake_github.diffs = {pr_a: "diff a"}

    class RaisingClient:
        def complete(self, messages):
            raise RuntimeError("model boom")

    node = review_pull_requests(fake_github, RaisingClient())

    node(
        {
            "pull_requests": [PullRequestContext(pr_a, [])],
            "reviews": [],
            "failures": [],
        }
    )

    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_records) == 1
    assert warning_records[0].context["repository"] == "org/a"
    assert warning_records[0].context["number"] == 1
    assert warning_records[0].context["error"] == "model boom"
