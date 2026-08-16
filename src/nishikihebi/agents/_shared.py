from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, NamedTuple

from nishikihebi.clients.github import Comment, GitHubClient, Issue, PullRequest

if TYPE_CHECKING:
    from nishikihebi.agents.issue_review.state import IssueReviewState
    from nishikihebi.agents.pr_review.state import PrReviewState

logger = logging.getLogger(__name__)


class Review(NamedTuple):
    target: PullRequest | Issue
    body: str


class ItemFailure(NamedTuple):
    repository: str
    number: int
    stage: str
    error_type: str
    error: str


def last_review_at(comments: list[Comment], reviewer_login: str) -> str | None:
    return max(
        (
            comment.created_at
            for comment in comments
            if comment.author == reviewer_login
        ),
        default=None,
    )


_MARKER_PATTERN = re.compile(r"<!-- nishikihebi: sha=(\S+) -->")


def review_marker(sha: str) -> str:
    return f"<!-- nishikihebi: sha={sha} -->"


def reviewed_sha(comments: list[Comment], reviewer_login: str) -> str | None:
    matches = [
        (comment.created_at, comment_matches[-1])
        for comment in comments
        if comment.author == reviewer_login
        if (comment_matches := _MARKER_PATTERN.findall(comment.body))
    ]
    return max(matches)[1] if matches else None


def render_comments(comments: list[Comment]) -> str:
    if not comments:
        return "(none)"
    return "\n\n".join(f"@{comment.author}: {comment.body}" for comment in comments)


def post_review_comments(github: GitHubClient):
    def node(state: PrReviewState | IssueReviewState) -> dict:
        reviews = state["reviews"]
        logger.info(f"posting {len(reviews)} review comments")
        failures: list[ItemFailure] = []
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
            try:
                github.post_comment(target, review.body)
            except Exception as error:
                logger.warning(
                    "failed to post comment",
                    extra={
                        "context": {
                            "repository": target.repository,
                            "number": target.number,
                            "stage": "post_review_comments",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    },
                )
                failures.append(
                    ItemFailure(
                        repository=target.repository,
                        number=target.number,
                        stage="post_review_comments",
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                )
                continue
            logger.info(f"posted {target.repository}#{target.number}")
        return {"failures": failures}

    return node
