import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.clients.llm import LlmClient
from nishikihebi.nodes.chat.call_llm import call_llm
from nishikihebi.states.chat import ChatState

logger = logging.getLogger(__name__)


def build_chat_graph(
    client: LlmClient, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    graph = StateGraph(ChatState)
    logger.debug("wiring call_llm node")
    graph.add_node("call_llm", call_llm(client))
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", END)
    compiled = graph.compile(checkpointer=checkpointer or MemorySaver())
    logger.info("chat graph ready")
    return compiled
