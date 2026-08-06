from typing import NamedTuple

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.github_client import GitHubClient
from nishikihebi.graphs.chat import build_chat_graph
from nishikihebi.graphs.pr_review import build_pr_review_graph
from nishikihebi.llm_client import LlmClient


class Graphs(NamedTuple):
    chat: CompiledStateGraph
    pr_review: CompiledStateGraph


def build_graphs(
    client: LlmClient,
    github: GitHubClient,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Graphs:
    return Graphs(
        chat=build_chat_graph(client, checkpointer),
        pr_review=build_pr_review_graph(client, github),
    )
