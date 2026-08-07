from typing import NamedTuple, TypedDict

from nishikihebi.clients.github import Comment, Issue, PullRequest


class Review(NamedTuple):
    target: PullRequest | Issue
    body: str


class PullRequestContext(NamedTuple):
    pull_request: PullRequest
    comments: list[Comment]


class IssueContext(NamedTuple):
    issue: Issue
    comments: list[Comment]


class PrReviewState(TypedDict):
    pull_requests: list[PullRequestContext]
    reviews: list[Review]


class IssueReviewState(TypedDict):
    issues: list[IssueContext]
    reviews: list[Review]
