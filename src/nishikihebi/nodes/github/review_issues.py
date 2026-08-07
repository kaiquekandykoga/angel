from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from nishikihebi.clients.llm import LlmClient
from nishikihebi.nodes.github import render_comments
from nishikihebi.states.github import IssueReviewState, Review

REVIEW_SYSTEM_PROMPT = (
    "You are a meticulous reviewer. Review the given GitHub issue title, "
    "description, and existing comments, and produce a single self-contained "
    "review comment in markdown that restates the problem, flags gaps or "
    "ambiguities, proposes acceptance criteria, and suggests an approach. Avoid "
    "repeating points already made in the existing comments."
)


def review_issues(client: LlmClient):
    def node(state: IssueReviewState) -> dict[str, list[Review]]:
        reviews = []
        for context in state["issues"]:
            issue = context.issue
            messages = [
                SystemMessage(content=REVIEW_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Repository: {issue.repository}\n"
                        f"Issue #{issue.number}: {issue.title}\n\n"
                        f"Body:\n{issue.body}\n\n"
                        f"Existing comments:\n{render_comments(context.comments)}"
                    )
                ),
            ]
            ai_message = client.complete(messages)
            reviews.append(Review(issue, cast("str", ai_message.content)))
        return {"reviews": reviews}

    return node
