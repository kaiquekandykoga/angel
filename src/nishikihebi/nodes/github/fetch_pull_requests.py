from nishikihebi.clients.github import GitHubClient
from nishikihebi.nodes.github import last_review_at
from nishikihebi.states.github import PrReviewState, PullRequestContext


def fetch_pull_requests(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(state: PrReviewState) -> dict[str, list[PullRequestContext]]:
        pull_requests = []
        for repository in github.list_repositories():
            github.ensure_label(repository, label, label_color)
            for pull_request in github.list_open_pull_requests(repository, label):
                comments = github.list_comments(pull_request)
                last_review = last_review_at(comments, reviewer_login)
                if last_review is None or (
                    github.fetch_commit_date(
                        pull_request.repository, pull_request.head_sha
                    )
                    > last_review
                ):
                    pull_requests.append(PullRequestContext(pull_request, comments))
        return {"pull_requests": pull_requests}

    return node
