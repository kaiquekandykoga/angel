import logging

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.agents._shared import (
    IssueReviewOutput,
    ItemFailure,
    Review,
    last_review_at,
    render_comments,
    render_issue_review,
)
from nishikihebi.agents.issue_review.prompts import REVIEW_SYSTEM_PROMPT
from nishikihebi.agents.issue_review.state import IssueContext, IssueReviewState
from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient

logger = logging.getLogger(__name__)


def fetch_issues(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(
        state: IssueReviewState,
    ) -> dict[str, list[IssueContext] | list[ItemFailure]]:
        logger.info("fetching issues")
        issues: list[IssueContext] = []
        failures: list[ItemFailure] = []
        repositories = github.list_repositories()
        items_scanned = 0
        for repository in repositories:
            try:
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
                    try:
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
                    except Exception as error:
                        logger.warning(
                            "failed to fetch issue",
                            extra={
                                "context": {
                                    "repository": issue.repository,
                                    "number": issue.number,
                                    "stage": "fetch_issues",
                                    "error_type": type(error).__name__,
                                    "error": str(error),
                                }
                            },
                        )
                        failures.append(
                            ItemFailure(
                                repository=issue.repository,
                                number=issue.number,
                                stage="fetch_issues",
                                error_type=type(error).__name__,
                                error=str(error),
                            )
                        )
            except Exception as error:
                logger.warning(
                    "failed to fetch issues for repository",
                    extra={
                        "context": {
                            "repository": repository,
                            "number": 0,
                            "stage": "fetch_issues",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    },
                )
                failures.append(
                    ItemFailure(
                        repository=repository,
                        number=0,
                        stage="fetch_issues",
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                )
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
        return {"issues": issues, "failures": failures}

    return node


def review_issues(client: LlmClient):
    def node(state: IssueReviewState) -> dict[str, list[Review] | list[ItemFailure]]:
        issues = state["issues"]
        logger.info(f"reviewing {len(issues)} issues")
        reviews: list[Review] = []
        failures: list[ItemFailure] = []
        for context in issues:
            issue = context.issue
            try:
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
                output = client.complete_structured(messages, IssueReviewOutput)
                review_body = render_issue_review(output)
                severity_counts: dict[str, int] = {}
                for finding in output.findings:
                    severity_counts[finding.severity.value] = (
                        severity_counts.get(finding.severity.value, 0) + 1
                    )
                logger.debug(
                    "review produced",
                    extra={
                        "context": {
                            "repository": issue.repository,
                            "number": issue.number,
                            "review": review_body,
                            "finding_count": len(output.findings),
                            "severity_counts": severity_counts,
                        }
                    },
                )
                logger.info(
                    f"reviewed {issue.repository}#{issue.number}",
                    extra={
                        "context": {
                            "repository": issue.repository,
                            "number": issue.number,
                        }
                    },
                )
            except Exception as error:
                logger.warning(
                    "failed to review issue",
                    extra={
                        "context": {
                            "repository": issue.repository,
                            "number": issue.number,
                            "stage": "review_issues",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    },
                )
                failures.append(
                    ItemFailure(
                        repository=issue.repository,
                        number=issue.number,
                        stage="review_issues",
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                )
                continue
            reviews.append(Review(issue, review_body))
        logger.info("issues reviewed", extra={"context": {"count": len(reviews)}})
        return {"reviews": reviews, "failures": failures}

    return node
