from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.agents._shared import (
    ItemFailure,
    PullRequestReviewOutput,
    Review,
    collect_failures,
    last_review_at,
    log_review_produced,
    render_comments,
    render_pull_request_review,
    review_marker,
    reviewed_sha,
)
from nishikihebi.agents.pr_review.prompts import REVIEW_SYSTEM_PROMPT
from nishikihebi.agents.pr_review.state import PrReviewState, PullRequestContext
from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient
from nishikihebi.logs import get_logger

log = get_logger(__name__)


def fetch_pull_requests(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(
        state: PrReviewState,
    ) -> dict[str, list[PullRequestContext] | list[ItemFailure]]:
        log.info("fetching pull requests")
        pull_requests: list[PullRequestContext] = []
        failures: list[ItemFailure] = []
        repositories = github.list_repositories()
        items_scanned = 0
        for repository in repositories:
            with collect_failures(
                failures,
                "failed to fetch pull requests for repository",
                stage="fetch_pull_requests",
                repository=repository,
                number=0,
            ):
                github.ensure_label(repository, label, label_color)
                labeled_pull_requests = github.list_open_pull_requests(
                    repository, label
                )
                log.debug(
                    "scanning repository",
                    repository=repository,
                    labeled_items_found=len(labeled_pull_requests),
                )
                for pull_request in labeled_pull_requests:
                    items_scanned += 1
                    with collect_failures(
                        failures,
                        "failed to fetch pull request",
                        stage="fetch_pull_requests",
                        repository=pull_request.repository,
                        number=pull_request.number,
                    ):
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
                        log.debug(
                            "evaluated pull request",
                            repository=pull_request.repository,
                            number=pull_request.number,
                            selected=selected,
                            reason=reason,
                        )
                        if selected:
                            pull_requests.append(
                                PullRequestContext(pull_request, comments)
                            )
        log.info(
            "pull requests fetched",
            repositories_scanned=len(repositories),
            items_scanned=items_scanned,
            items_due_for_review=len(pull_requests),
        )
        return {"pull_requests": pull_requests, "failures": failures}

    return node


def review_pull_requests(github: GitHubClient, client: LlmClient):
    def node(state: PrReviewState) -> dict[str, list[Review] | list[ItemFailure]]:
        pull_requests = state["pull_requests"]
        log.info(f"reviewing {len(pull_requests)} pull requests")
        reviews: list[Review] = []
        failures: list[ItemFailure] = []
        for context in pull_requests:
            pull_request = context.pull_request
            with collect_failures(
                failures,
                "failed to review pull request",
                stage="review_pull_requests",
                repository=pull_request.repository,
                number=pull_request.number,
            ):
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
                log.debug(
                    "reviewing pull request",
                    repository=pull_request.repository,
                    number=pull_request.number,
                    diff_size=len(diff),
                    prompt_message_count=len(messages),
                )
                output = client.complete_structured(messages, PullRequestReviewOutput)
                review_body = render_pull_request_review(output)
                log_review_produced(
                    log,
                    repository=pull_request.repository,
                    number=pull_request.number,
                    review=review_body,
                    findings=output.findings,
                )
                log.info(
                    f"reviewed {pull_request.repository}#{pull_request.number}",
                    repository=pull_request.repository,
                    number=pull_request.number,
                )
                reviews.append(
                    Review(
                        pull_request,
                        f"{review_body}\n\n{review_marker(pull_request.head_sha)}",
                    )
                )
        log.info("pull requests reviewed", count=len(reviews))
        return {"reviews": reviews, "failures": failures}

    return node
