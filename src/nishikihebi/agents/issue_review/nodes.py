import logging
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.agents._shared import Review, last_review_at, render_comments
from nishikihebi.agents.issue_review.prompts import REVIEW_SYSTEM_PROMPT
from nishikihebi.agents.issue_review.state import IssueContext, IssueReviewState
from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient

logger = logging.getLogger(__name__)


def fetch_issues(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(state: IssueReviewState) -> dict[str, list[IssueContext]]:
        logger.info("fetching issues")
        issues = []
        repositories = github.list_repositories()
        items_scanned = 0
        for repository in repositories:
            github.ensure_label(repository, label, label_color)
            labeled_issues = github.list_open_issues(repository, label)
            logger.debug(
                "scanning repository",
                extra={
                    "context": {
                        "repository": repository,
                        "labeled_items_found": len(labeled_issues),
                    }
                },
            )
            for issue in labeled_issues:
                items_scanned += 1
                comments = github.list_comments(issue)
                last_review = last_review_at(comments, reviewer_login)
                if last_review is None:
                    selected, reason = True, "never reviewed"
                elif issue.updated_at > last_review:
                    selected, reason = True, "updated since last review"
                else:
                    selected, reason = False, "already up to date"
                logger.debug(
                    "evaluated issue",
                    extra={
                        "context": {
                            "repository": issue.repository,
                            "number": issue.number,
                            "selected": selected,
                            "reason": reason,
                        }
                    },
                )
                if selected:
                    issues.append(IssueContext(issue, comments))
        logger.info(
            "issues fetched",
            extra={
                "context": {
                    "repositories_scanned": len(repositories),
                    "items_scanned": items_scanned,
                    "items_due_for_review": len(issues),
                }
            },
        )
        return {"issues": issues}

    return node


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
