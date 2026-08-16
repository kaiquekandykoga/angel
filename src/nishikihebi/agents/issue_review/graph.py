from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from nishikihebi.agents._shared import post_review_comments
from nishikihebi.agents.issue_review.nodes import fetch_issues, review_issues
from nishikihebi.agents.issue_review.state import IssueReviewState
from nishikihebi.clients.github import GitHubClient
from nishikihebi.clients.llm import LlmClient
from nishikihebi.logs import get_logger
from nishikihebi.settings import LABEL, LABEL_COLOR, REVIEWER_LOGIN

log = get_logger(__name__)

_RETRY_POLICY = RetryPolicy(max_attempts=3)


def build_issue_review_graph(
    client: LlmClient,
    github: GitHubClient,
    reviewer_login: str = REVIEWER_LOGIN,
    label: str = LABEL,
    label_color: str = LABEL_COLOR,
) -> CompiledStateGraph:
    log.debug(
        "wiring issue_review graph nodes",
        reviewer_login=reviewer_login,
        label=label,
    )
    graph = StateGraph(IssueReviewState)
    graph.add_node(
        "fetch_issues",
        fetch_issues(github, reviewer_login, label, label_color),
        retry_policy=_RETRY_POLICY,
    )
    graph.add_node(
        "review_issues", review_issues(client), retry_policy=_RETRY_POLICY
    )
    graph.add_node(
        "post_review_comments",
        post_review_comments(github),
        retry_policy=_RETRY_POLICY,
    )
    graph.add_edge(START, "fetch_issues")
    graph.add_edge("fetch_issues", "review_issues")
    graph.add_edge("review_issues", "post_review_comments")
    graph.add_edge("post_review_comments", END)
    compiled = graph.compile()
    log.info("issue_review graph ready")
    return compiled
