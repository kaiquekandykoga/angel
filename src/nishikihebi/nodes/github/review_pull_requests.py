from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient
from nishikihebi.nodes.github import render_comments
from nishikihebi.states.github import PrReviewState, Review

REVIEW_SYSTEM_PROMPT = (
    "You are a meticulous code reviewer. Review the given pull request title, "
    "description, existing comments, and diff, and produce a single self-contained "
    "review comment in markdown covering all your findings, including correctness, "
    "clarity, and test coverage. Avoid repeating points already made in the "
    "existing comments."
)


def review_pull_requests(github: GitHubClient, client: LlmClient):
    def node(state: PrReviewState) -> dict[str, list[Review]]:
        reviews = []
        for context in state["pull_requests"]:
            pull_request = context.pull_request
            diff = github.fetch_diff(pull_request)
            messages = [
                SystemMessage(content=REVIEW_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Repository: {pull_request.repository}\n"
                        f"Pull request #{pull_request.number}: {pull_request.title}\n\n"
                        f"Description:\n{pull_request.body}\n\n"
                        f"Existing comments:\n{render_comments(context.comments)}\n\n"
                        f"Diff:\n{diff}"
                    )
                ),
            ]
            ai_message = client.complete(messages)
            reviews.append(Review(pull_request, cast("str", ai_message.content)))
        return {"reviews": reviews}

    return node
