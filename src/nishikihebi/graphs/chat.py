from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.llm_client import LlmClient
from nishikihebi.nodes.call_llm import call_llm
from nishikihebi.state import ChatState


def build_chat_graph(
    client: LlmClient, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    graph = StateGraph(ChatState)
    graph.add_node("call_llm", call_llm(client))
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", END)
    return graph.compile(checkpointer=checkpointer or MemorySaver())
