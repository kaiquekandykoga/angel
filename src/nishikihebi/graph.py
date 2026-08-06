from typing import NamedTuple

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.graphs.chat import build_chat_graph
from nishikihebi.llm_client import LlmClient


class Graphs(NamedTuple):
    chat: CompiledStateGraph


def build_graphs(
    client: LlmClient, checkpointer: BaseCheckpointSaver | None = None
) -> Graphs:
    return Graphs(chat=build_chat_graph(client, checkpointer))
