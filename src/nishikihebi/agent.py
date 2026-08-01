from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from nishikihebi.model import Model


class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_agent(model: Model):
    def respond(state: State) -> dict:
        return {"messages": [AIMessage(content=model.complete(state["messages"]))]}

    graph = StateGraph(State)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=MemorySaver())
