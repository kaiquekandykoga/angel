import operator
from typing import Annotated, NamedTuple, TypedDict

from angel.agents._shared import ItemFailure, Review
from angel.clients.github import Comment, Issue


class IssueContext(NamedTuple):
    issue: Issue
    comments: list[Comment]


class IssueReviewState(TypedDict):
    issues: list[IssueContext]
    reviews: list[Review]
    failures: Annotated[list[ItemFailure], operator.add]
