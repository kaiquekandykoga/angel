import operator
from typing import Annotated, NamedTuple, TypedDict

from nishikihebi.agents._shared import ItemFailure, Review
from nishikihebi.clients.github import Comment, PullRequest


class PullRequestContext(NamedTuple):
    pull_request: PullRequest
    comments: list[Comment]


class PrReviewState(TypedDict):
    pull_requests: list[PullRequestContext]
    reviews: list[Review]
    failures: Annotated[list[ItemFailure], operator.add]
