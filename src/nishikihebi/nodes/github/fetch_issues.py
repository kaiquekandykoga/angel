import logging

from nishikihebi.clients.github import GitHubClient
from nishikihebi.nodes.github import last_review_at
from nishikihebi.states.github import IssueContext, IssueReviewState

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
