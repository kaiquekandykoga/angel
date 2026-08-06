from collections.abc import Sequence

from nishikihebi.clients.github import GitHubClient, PullRequest
from nishikihebi.state import PrReviewState


def fetch_pull_requests(github: GitHubClient, repositories: Sequence[str], label: str):
    def node(state: PrReviewState) -> dict[str, list[PullRequest]]:
        pull_requests = [
            pull_request
            for repository in repositories
            for pull_request in github.list_labeled_pull_requests(repository, label)
        ]
        return {"pull_requests": pull_requests}

    return node
