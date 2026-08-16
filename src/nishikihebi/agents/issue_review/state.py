import operator
from typing import Annotated, NamedTuple, TypedDict

from nishikihebi.agents._shared import ItemFailure, Review
from nishikihebi.clients.github import Comment, Issue


class IssueContext(NamedTuple):
    issue: Issue
    comments: list[Comment]


class IssueReviewState(TypedDict):
    issues: list[IssueContext]
    reviews: list[Review]
    failures: Annotated[list[ItemFailure], operator.add]
