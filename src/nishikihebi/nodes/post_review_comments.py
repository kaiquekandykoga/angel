from nishikihebi.clients.github import GitHubClient
from nishikihebi.state import PrReviewState


def post_review_comments(github: GitHubClient):
    def node(state: PrReviewState) -> dict:
        for review in state["reviews"]:
            github.post_comment(review.pull_request, review.body)
        return {}

    return node
