import logging

from nishikihebi.clients.github import GitHubClient
from nishikihebi.nodes.github import last_review_at
from nishikihebi.states.github import PrReviewState, PullRequestContext

logger = logging.getLogger(__name__)


def fetch_pull_requests(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(state: PrReviewState) -> dict[str, list[PullRequestContext]]:
        logger.info("fetching pull requests")
        pull_requests = []
        repositories = github.list_repositories()
        items_scanned = 0
        for repository in repositories:
            github.ensure_label(repository, label, label_color)
            labeled_pull_requests = github.list_open_pull_requests(repository, label)
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
                comments = github.list_comments(pull_request)
                last_review = last_review_at(comments, reviewer_login)
                if last_review is None:
                    selected, reason = True, "never reviewed"
                elif (
                    github.fetch_commit_date(
                        pull_request.repository, pull_request.head_sha
                    )
                    > last_review
                ):
                    selected, reason = True, "new commits"
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
                    pull_requests.append(PullRequestContext(pull_request, comments))
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
        return {"pull_requests": pull_requests}

    return node
