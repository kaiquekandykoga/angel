from collections.abc import Sequence

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient
from nishikihebi.graphs.github import REPOSITORIES, REVIEW_LABEL
from nishikihebi.nodes.github.fetch_pull_requests import fetch_pull_requests
from nishikihebi.nodes.github.post_review_comments import post_review_comments
from nishikihebi.nodes.github.review_pull_requests import review_pull_requests
from nishikihebi.states.github import PrReviewState


def build_pr_review_graph(
    client: LlmClient,
    github: GitHubClient,
    repositories: Sequence[str] = REPOSITORIES,
    label: str = REVIEW_LABEL,
) -> CompiledStateGraph:
    graph = StateGraph(PrReviewState)
    graph.add_node(
        "fetch_pull_requests", fetch_pull_requests(github, repositories, label)
    )
    graph.add_node("review_pull_requests", review_pull_requests(github, client))
    graph.add_node("post_review_comments", post_review_comments(github))
    graph.add_edge(START, "fetch_pull_requests")
    graph.add_edge("fetch_pull_requests", "review_pull_requests")
    graph.add_edge("review_pull_requests", "post_review_comments")
    graph.add_edge("post_review_comments", END)
    return graph.compile()
