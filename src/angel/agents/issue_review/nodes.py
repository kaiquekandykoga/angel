from langchain_core.messages import HumanMessage, SystemMessage

from angel.agents._shared import (
    IssueReviewOutput,
    ItemFailure,
    Review,
    collect_failures,
    last_review_at,
    log_review_produced,
    render_comments,
    render_issue_review,
)
from angel.agents.issue_review.prompts import REVIEW_SYSTEM_PROMPT
from angel.agents.issue_review.state import IssueContext, IssueReviewState
from angel.clients.github import GitHubClient
from angel.clients.llm import LlmClient
from angel.logs import get_logger

log = get_logger(__name__)


def fetch_issues(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(
        state: IssueReviewState,
    ) -> dict[str, list[IssueContext] | list[ItemFailure]]:
        log.info("fetching issues")
        issues: list[IssueContext] = []
        failures: list[ItemFailure] = []
        repositories = github.list_repositories()
        items_scanned = 0
        for repository in repositories:
            with collect_failures(
                failures,
                "failed to fetch issues for repository",
                stage="fetch_issues",
                repository=repository,
                number=0,
            ):
                github.ensure_label(repository, label, label_color)
                labeled_issues = github.list_open_issues(repository, label)
                log.debug(
                    "scanning repository",
                    repository=repository,
                    labeled_items_found=len(labeled_issues),
                )
                for issue in labeled_issues:
                    items_scanned += 1
                    with collect_failures(
                        failures,
                        "failed to fetch issue",
                        stage="fetch_issues",
                        repository=issue.repository,
                        number=issue.number,
                    ):
                        comments = github.list_comments(issue)
                        last_review = last_review_at(comments, reviewer_login)
                        if last_review is None:
                            selected, reason = True, "never reviewed"
                        elif issue.updated_at > last_review:
                            selected, reason = True, "updated since last review"
                        else:
                            selected, reason = False, "already up to date"
                        log.debug(
                            "evaluated issue",
                            repository=issue.repository,
                            number=issue.number,
                            selected=selected,
                            reason=reason,
                        )
                        if selected:
                            issues.append(IssueContext(issue, comments))
        log.info(
            "issues fetched",
            repositories_scanned=len(repositories),
            items_scanned=items_scanned,
            items_due_for_review=len(issues),
        )
        return {"issues": issues, "failures": failures}

    return node


def review_issues(client: LlmClient):
    def node(state: IssueReviewState) -> dict[str, list[Review] | list[ItemFailure]]:
        issues = state["issues"]
        log.info(f"reviewing {len(issues)} issues")
        reviews: list[Review] = []
        failures: list[ItemFailure] = []
        for context in issues:
            issue = context.issue
            with collect_failures(
                failures,
                "failed to review issue",
                stage="review_issues",
                repository=issue.repository,
                number=issue.number,
            ):
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
                log.debug(
                    "reviewing issue",
                    repository=issue.repository,
                    number=issue.number,
                    prompt_message_count=len(messages),
                )
                output = client.complete_structured(messages, IssueReviewOutput)
                review_body = render_issue_review(output)
                log_review_produced(
                    log,
                    repository=issue.repository,
                    number=issue.number,
                    review=review_body,
                    findings=output.findings,
                )
                log.info(
                    f"reviewed {issue.repository}#{issue.number}",
                    repository=issue.repository,
                    number=issue.number,
                )
                reviews.append(Review(issue, review_body))
        log.info("issues reviewed", count=len(reviews))
        return {"reviews": reviews, "failures": failures}

    return node
