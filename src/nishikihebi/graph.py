from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.edges.graph import add_call_llm_edges
from nishikihebi.model import Model
from nishikihebi.nodes.call_llm import call_llm
from nishikihebi.state import State


def build_graph(
    model: Model, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    graph = StateGraph(State)
    graph.add_node("call_llm", call_llm(model))
    add_call_llm_edges(graph)
    return graph.compile(checkpointer=checkpointer or MemorySaver())
