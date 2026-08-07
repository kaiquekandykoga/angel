from nishikihebi.clients.github import PullRequest
from nishikihebi.states.github import Review


def test_review_pairs_target_with_body():
    pull_request = PullRequest("kaiquekandykoga/nishikihebi", 1, "a pr")

    review = Review(pull_request, "looks good")

    assert review.target == pull_request
    assert review.body == "looks good"
