import logging

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.agents._shared import (
    ItemFailure,
    PullRequestReviewOutput,
    Review,
    last_review_at,
    render_comments,
    render_pull_request_review,
    review_marker,
    reviewed_sha,
)
from nishikihebi.agents.pr_review.prompts import REVIEW_SYSTEM_PROMPT
from nishikihebi.agents.pr_review.state import PrReviewState, PullRequestContext
from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient

logger = logging.getLogger(__name__)


def fetch_pull_requests(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(
        state: PrReviewState,
    ) -> dict[str, list[PullRequestContext] | list[ItemFailure]]:
        logger.info("fetching pull requests")
        pull_requests: list[PullRequestContext] = []
        failures: list[ItemFailure] = []
        repositories = github.list_repositories()
        items_scanned = 0
        for repository in repositories:
            try:
                github.ensure_label(repository, label, label_color)
                labeled_pull_requests = github.list_open_pull_requests(
                    repository, label
                )
                logger.debug(
                    "scanning repository",
                    extra={
                        "context": {
                            "repository": repository,
                            "labeled_items_found": len(labeled_pull_requests),
                        }
                    },
                )
                for pull_request in labeled_pull_requests:
                    items_scanned += 1
                    try:
                        comments = github.list_comments(pull_request)
                        if last_review_at(comments, reviewer_login) is None:
                            selected, reason = True, "never reviewed"
                        elif (
                            recorded_sha := reviewed_sha(comments, reviewer_login)
                        ) is None:
                            selected, reason = True, "no recorded head"
                        elif recorded_sha != pull_request.head_sha:
                            selected, reason = True, "new head"
                        else:
                            selected, reason = False, "already up to date"
                        logger.debug(
                            "evaluated pull request",
                            extra={
                                "context": {
                                    "repository": pull_request.repository,
                                    "number": pull_request.number,
                                    "selected": selected,
                                    "reason": reason,
                                }
                            },
                        )
                        if selected:
                            pull_requests.append(
                                PullRequestContext(pull_request, comments)
                            )
                    except Exception as error:
                        logger.warning(
                            "failed to fetch pull request",
                            extra={
                                "context": {
                                    "repository": pull_request.repository,
                                    "number": pull_request.number,
                                    "stage": "fetch_pull_requests",
                                    "error_type": type(error).__name__,
                                    "error": str(error),
                                }
                            },
                        )
                        failures.append(
                            ItemFailure(
                                repository=pull_request.repository,
                                number=pull_request.number,
                                stage="fetch_pull_requests",
                                error_type=type(error).__name__,
                                error=str(error),
                            )
                        )
            except Exception as error:
                logger.warning(
                    "failed to fetch pull requests for repository",
                    extra={
                        "context": {
                            "repository": repository,
                            "number": 0,
                            "stage": "fetch_pull_requests",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    },
                )
                failures.append(
                    ItemFailure(
                        repository=repository,
                        number=0,
                        stage="fetch_pull_requests",
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                )
        logger.info(
            "pull requests fetched",
            extra={
                "context": {
                    "repositories_scanned": len(repositories),
                    "items_scanned": items_scanned,
                    "items_due_for_review": len(pull_requests),
                }
            },
        )
        return {"pull_requests": pull_requests, "failures": failures}

    return node


def review_pull_requests(github: GitHubClient, client: LlmClient):
    def node(state: PrReviewState) -> dict[str, list[Review] | list[ItemFailure]]:
        pull_requests = state["pull_requests"]
        logger.info(f"reviewing {len(pull_requests)} pull requests")
        reviews: list[Review] = []
        failures: list[ItemFailure] = []
        for context in pull_requests:
            pull_request = context.pull_request
            try:
                diff = github.fetch_diff(pull_request)
                messages = [
                    SystemMessage(content=REVIEW_SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            f"Repository: {pull_request.repository}\n"
                            f"Pull request #{pull_request.number}: "
                            f"{pull_request.title}\n\n"
                            f"Description:\n{pull_request.body}\n\n"
                            f"Existing comments:\n"
                            f"{render_comments(context.comments)}\n\n"
                            f"Diff:\n{diff}"
                        )
                    ),
                ]
                logger.debug(
                    "reviewing pull request",
                    extra={
                        "context": {
                            "repository": pull_request.repository,
                            "number": pull_request.number,
                            "diff_size": len(diff),
                            "prompt_message_count": len(messages),
                        }
                    },
                )
                output = client.complete_structured(messages, PullRequestReviewOutput)
                review_body = render_pull_request_review(output)
                severity_counts: dict[str, int] = {}
                for finding in output.findings:
                    severity_counts[finding.severity.value] = (
                        severity_counts.get(finding.severity.value, 0) + 1
                    )
                logger.debug(
                    "review produced",
                    extra={
                        "context": {
                            "repository": pull_request.repository,
                            "number": pull_request.number,
                            "review": review_body,
                            "finding_count": len(output.findings),
                            "severity_counts": severity_counts,
                        }
                    },
                )
                logger.info(
                    f"reviewed {pull_request.repository}#{pull_request.number}",
                    extra={
                        "context": {
                            "repository": pull_request.repository,
                            "number": pull_request.number,
                        }
                    },
                )
            except Exception as error:
                logger.warning(
                    "failed to review pull request",
                    extra={
                        "context": {
                            "repository": pull_request.repository,
                            "number": pull_request.number,
                            "stage": "review_pull_requests",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    },
                )
                failures.append(
                    ItemFailure(
                        repository=pull_request.repository,
                        number=pull_request.number,
                        stage="review_pull_requests",
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                )
                continue
            reviews.append(
                Review(
                    pull_request,
                    f"{review_body}\n\n{review_marker(pull_request.head_sha)}",
                )
            )
        logger.info(
            "pull requests reviewed", extra={"context": {"count": len(reviews)}}
        )
        return {"reviews": reviews, "failures": failures}

    return node
