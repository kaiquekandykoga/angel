import logging
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.clients.llm import LlmClient
from nishikihebi.nodes.github import render_comments
from nishikihebi.states.github import IssueReviewState, Review

REVIEW_SYSTEM_PROMPT = (
    "You are a meticulous reviewer. Review the given GitHub issue title, "
    "description, and existing comments, and produce a single self-contained "
    "review comment in markdown that restates the problem, flags gaps or "
    "ambiguities, proposes acceptance criteria, and suggests an approach. Avoid "
    "repeating points already made in the existing comments."
)

logger = logging.getLogger(__name__)


def review_issues(client: LlmClient):
    def node(state: IssueReviewState) -> dict[str, list[Review]]:
        issues = state["issues"]
        logger.info(f"reviewing {len(issues)} issues")
        reviews = []
        for context in issues:
            issue = context.issue
            messages = [
                SystemMessage(content=REVIEW_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Repository: {issue.repository}\n"
                        f"Issue #{issue.number}: {issue.title}\n\n"
                        f"Body:\n{issue.body}\n\n"
                        f"Existing comments:\n{render_comments(context.comments)}"
                    )
                ),
            ]
            logger.debug(
                "reviewing issue",
                extra={
                    "context": {
                        "repository": issue.repository,
                        "number": issue.number,
                        "prompt_message_count": len(messages),
                    }
                },
            )
            ai_message = client.complete(messages)
            review_body = cast("str", ai_message.content)
            logger.debug(
                "review produced",
                extra={
                    "context": {
                        "repository": issue.repository,
                        "number": issue.number,
                        "review": review_body,
                    }
                },
            )
            logger.info(
                f"reviewed {issue.repository}#{issue.number}",
                extra={
                    "context": {"repository": issue.repository, "number": issue.number}
                },
            )
            reviews.append(Review(issue, review_body))
        logger.info("issues reviewed", extra={"context": {"count": len(reviews)}})
        return {"reviews": reviews}

    return node
