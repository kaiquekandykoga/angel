from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.model import Model
from nishikihebi.state import State

SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."


def build_chat_agent(model: Model) -> CompiledStateGraph:
    def respond(state: State) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [model.complete(messages)]}

    graph = StateGraph(State)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile()
