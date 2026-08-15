import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.agents._shared import post_review_comments
from nishikihebi.agents.issue_review.nodes import fetch_issues, review_issues
from nishikihebi.agents.issue_review.state import IssueReviewState
from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient
from nishikihebi.settings import LABEL, LABEL_COLOR, REVIEWER_LOGIN

logger = logging.getLogger(__name__)


def build_issue_review_graph(
    client: LlmClient,
    github: GitHubClient,
    reviewer_login: str = REVIEWER_LOGIN,
    label: str = LABEL,
    label_color: str = LABEL_COLOR,
) -> CompiledStateGraph:
    logger.debug(
        "wiring issue_review graph nodes",
        extra={"context": {"reviewer_login": reviewer_login, "label": label}},
    )
    graph = StateGraph(IssueReviewState)
    graph.add_node(
        "fetch_issues", fetch_issues(github, reviewer_login, label, label_color)
    )
    graph.add_node("review_issues", review_issues(client))
    graph.add_node("post_review_comments", post_review_comments(github))
    graph.add_edge(START, "fetch_issues")
    graph.add_edge("fetch_issues", "review_issues")
    graph.add_edge("review_issues", "post_review_comments")
    graph.add_edge("post_review_comments", END)
    compiled = graph.compile()
    logger.info("issue_review graph ready")
    return compiled
