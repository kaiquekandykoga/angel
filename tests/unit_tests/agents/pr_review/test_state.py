import operator
from typing import get_args

from nishikihebi.agents._shared import Review
from nishikihebi.agents.pr_review.state import PrReviewState, PullRequestContext
from nishikihebi.clients.github import Comment, PullRequest


def test_review_pairs_target_with_body():
    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr", "body", "sha")

    review = Review(pull_request, "looks good")

    assert review.target == pull_request
    assert review.body == "looks good"


def test_pull_request_context_pairs_pull_request_with_comments():
    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr", "body", "sha")
    comment = Comment("someone", "hi", "2026-08-01T00:00:00Z")

    context = PullRequestContext(pull_request, [comment])

    assert context.pull_request == pull_request
    assert context.comments == [comment]


def test_failures_annotation_carries_operator_add_reducer():
    _, reducer = get_args(PrReviewState.__annotations__["failures"])

    assert reducer is operator.add
