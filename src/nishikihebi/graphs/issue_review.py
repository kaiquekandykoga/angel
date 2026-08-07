from collections.abc import Sequence

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient
from nishikihebi.graphs import REPOSITORIES, REVIEW_LABEL
from nishikihebi.nodes.fetch_issues import fetch_issues
from nishikihebi.nodes.post_review_comments import post_review_comments
from nishikihebi.nodes.review_issues import review_issues
from nishikihebi.state import IssueReviewState


def build_issue_review_graph(
    client: LlmClient,
    github: GitHubClient,
    repositories: Sequence[str] = REPOSITORIES,
    label: str = REVIEW_LABEL,
) -> CompiledStateGraph:
    graph = StateGraph(IssueReviewState)
    graph.add_node("fetch_issues", fetch_issues(github, repositories, label))
    graph.add_node("review_issues", review_issues(client))
    graph.add_node("post_review_comments", post_review_comments(github))
    graph.add_edge(START, "fetch_issues")
    graph.add_edge("fetch_issues", "review_issues")
    graph.add_edge("review_issues", "post_review_comments")
    graph.add_edge("post_review_comments", END)
    return graph.compile()
