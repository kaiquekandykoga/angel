from typing import Annotated, NamedTuple, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from nishikihebi.clients.github import Issue, PullRequest


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class Review(NamedTuple):
    target: PullRequest | Issue
    body: str


class PrReviewState(TypedDict):
    pull_requests: list[PullRequest]
    reviews: list[Review]


class IssueReviewState(TypedDict):
    issues: list[Issue]
    reviews: list[Review]
