from typing import NamedTuple, TypedDict

from nishikihebi.agents._shared import Review
from nishikihebi.clients.github import Comment, Issue


class IssueContext(NamedTuple):
    issue: Issue
    comments: list[Comment]


class IssueReviewState(TypedDict):
    issues: list[IssueContext]
    reviews: list[Review]
