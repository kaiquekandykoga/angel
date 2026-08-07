from collections.abc import Sequence

from nishikihebi.clients.github import GitHubClient, Issue
from nishikihebi.states.github import IssueReviewState


def fetch_issues(github: GitHubClient, repositories: Sequence[str], label: str):
    def node(state: IssueReviewState) -> dict[str, list[Issue]]:
        issues = [
            issue
            for repository in repositories
            for issue in github.list_labeled_issues(repository, label)
        ]
        return {"issues": issues}

    return node
