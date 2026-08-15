from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple

from nishikihebi.clients.github import Comment, GitHubClient, Issue, PullRequest

if TYPE_CHECKING:
    from nishikihebi.agents.issue_review.state import IssueReviewState
    from nishikihebi.agents.pr_review.state import PrReviewState

logger = logging.getLogger(__name__)


class Review(NamedTuple):
    target: PullRequest | Issue
    body: str


def last_review_at(comments: list[Comment], reviewer_login: str) -> str | None:
    return max(
        (
            comment.created_at
            for comment in comments
            if comment.author == reviewer_login
        ),
        default=None,
    )


def render_comments(comments: list[Comment]) -> str:
    if not comments:
        return "(none)"
    return "\n\n".join(f"@{comment.author}: {comment.body}" for comment in comments)


def post_review_comments(github: GitHubClient):
    def node(state: PrReviewState | IssueReviewState) -> dict:
        reviews = state["reviews"]
        logger.info(f"posting {len(reviews)} review comments")
        for review in reviews:
            target = review.target
            logger.debug(
                "posting comment",
                extra={
                    "context": {
                        "repository": target.repository,
                        "number": target.number,
                        "body_length": len(review.body),
                    }
                },
            )
            github.post_comment(target, review.body)
            logger.info(f"posted {target.repository}#{target.number}")
        return {}

    return node
