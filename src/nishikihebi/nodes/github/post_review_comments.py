from nishikihebi.clients.github import GitHubClient
from nishikihebi.states.github import IssueReviewState, PrReviewState


def post_review_comments(github: GitHubClient):
    def node(state: PrReviewState | IssueReviewState) -> dict:
        for review in state["reviews"]:
            github.post_comment(review.target, review.body)
        return {}

    return node
