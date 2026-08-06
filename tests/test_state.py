from nishikihebi.github_client import PullRequest
from nishikihebi.state import Review


def test_review_pairs_pull_request_with_body():
    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr")

    review = Review(pull_request, "looks good")

    assert review.pull_request == pull_request
    assert review.body == "looks good"
