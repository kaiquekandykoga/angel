from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.agents.chat.nodes import call_llm
from nishikihebi.agents.chat.state import ChatState
from nishikihebi.clients.llm import LlmClient
from nishikihebi.logs import get_logger

log = get_logger(__name__)


def build_chat_graph(
    client: LlmClient, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    log.debug("wiring call_llm node")
    graph = StateGraph(ChatState)
    graph.add_node("call_llm", call_llm(client))
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", END)
    compiled = graph.compile(checkpointer=checkpointer or MemorySaver())
    log.info("chat graph ready")
    return compiled
