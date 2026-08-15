from typing import NamedTuple, TypedDict

from nishikihebi.agents._shared import Review
from nishikihebi.clients.github import Comment, PullRequest


class PullRequestContext(NamedTuple):
    pull_request: PullRequest
    comments: list[Comment]


class PrReviewState(TypedDict):
    pull_requests: list[PullRequestContext]
    reviews: list[Review]
