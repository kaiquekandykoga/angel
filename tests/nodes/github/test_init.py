from nishikihebi.clients.github import Comment
from nishikihebi.nodes.github import last_review_at, render_comments


def test_last_review_at_returns_none_when_reviewer_never_commented():
    comments = [Comment("someone-else", "hi", "2026-08-01T00:00:00Z")]

    assert last_review_at(comments, "kandy-nishikihebi[bot]") is None


def test_last_review_at_returns_most_recent_reviewer_comment():
    comments = [
        Comment("kandy-nishikihebi[bot]", "first", "2026-08-01T00:00:00Z"),
        Comment("someone-else", "hi", "2026-08-02T00:00:00Z"),
        Comment("kandy-nishikihebi[bot]", "second", "2026-08-03T00:00:00Z"),
    ]

    assert last_review_at(comments, "kandy-nishikihebi[bot]") == "2026-08-03T00:00:00Z"


def test_render_comments_formats_author_and_body():
    comments = [
        Comment("alice", "looks good", "2026-08-01T00:00:00Z"),
        Comment("bob", "needs work", "2026-08-02T00:00:00Z"),
    ]

    assert render_comments(comments) == "@alice: looks good\n\n@bob: needs work"


def test_render_comments_falls_back_when_empty():
    assert render_comments([]) == "(none)"
