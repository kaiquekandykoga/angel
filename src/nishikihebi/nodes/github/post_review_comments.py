import logging

from nishikihebi.clients.github import GitHubClient
from nishikihebi.states.github import IssueReviewState, PrReviewState

logger = logging.getLogger(__name__)


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
