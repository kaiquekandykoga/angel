from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from nishikihebi.agents.chat import build_chat_agent
from nishikihebi.model import Model
from nishikihebi.state import State


def build_graph(model: Model, checkpointer=None):
    graph = StateGraph(State)
    graph.add_node("chat", build_chat_agent(model))
    graph.add_edge(START, "chat")
    graph.add_edge("chat", END)
    return graph.compile(checkpointer=checkpointer or MemorySaver())
