import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.agents._shared import post_review_comments
from nishikihebi.agents.pr_review.nodes import fetch_pull_requests, review_pull_requests
from nishikihebi.agents.pr_review.state import PrReviewState
from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient
from nishikihebi.settings import LABEL, LABEL_COLOR, REVIEWER_LOGIN

logger = logging.getLogger(__name__)


def build_pr_review_graph(
    client: LlmClient,
    github: GitHubClient,
    reviewer_login: str = REVIEWER_LOGIN,
    label: str = LABEL,
    label_color: str = LABEL_COLOR,
) -> CompiledStateGraph:
    logger.debug(
        "wiring pr_review graph nodes",
        extra={"context": {"reviewer_login": reviewer_login, "label": label}},
    )
    graph = StateGraph(PrReviewState)
    graph.add_node(
        "fetch_pull_requests",
        fetch_pull_requests(github, reviewer_login, label, label_color),
    )
    graph.add_node("review_pull_requests", review_pull_requests(github, client))
    graph.add_node("post_review_comments", post_review_comments(github))
    graph.add_edge(START, "fetch_pull_requests")
    graph.add_edge("fetch_pull_requests", "review_pull_requests")
    graph.add_edge("review_pull_requests", "post_review_comments")
    graph.add_edge("post_review_comments", END)
    compiled = graph.compile()
    logger.info("pr_review graph ready")
    return compiled
