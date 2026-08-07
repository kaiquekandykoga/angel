from nishikihebi.clients.github import GitHubClient
from nishikihebi.nodes.github import last_review_at
from nishikihebi.states.github import IssueContext, IssueReviewState


def fetch_issues(
    github: GitHubClient, reviewer_login: str, label: str, label_color: str
):
    def node(state: IssueReviewState) -> dict[str, list[IssueContext]]:
        issues = []
        for repository in github.list_repositories():
            github.ensure_label(repository, label, label_color)
            for issue in github.list_open_issues(repository, label):
                comments = github.list_comments(issue)
                last_review = last_review_at(comments, reviewer_login)
                if last_review is None or issue.updated_at > last_review:
                    issues.append(IssueContext(issue, comments))
        return {"issues": issues}

    return node
