from typing import NamedTuple, TypedDict

from nishikihebi.clients.github import Issue, PullRequest


class Review(NamedTuple):
    target: PullRequest | Issue
    body: str


class PrReviewState(TypedDict):
    pull_requests: list[PullRequest]
    reviews: list[Review]


class IssueReviewState(TypedDict):
    issues: list[Issue]
    reviews: list[Review]
