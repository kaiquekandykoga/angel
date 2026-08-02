from __future__ import annotations

from langgraph.graph import END, START, StateGraph


def add_call_llm_edges(graph: StateGraph) -> None:
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", END)
