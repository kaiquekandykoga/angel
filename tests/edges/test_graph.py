from langgraph.graph import END, START, StateGraph

from nishikihebi.edges.graph import add_call_llm_edges
from nishikihebi.state import State


def test_add_call_llm_edges_wires_start_call_llm_end():
    graph = StateGraph(State)
    graph.add_node("call_llm", lambda state: state)

    add_call_llm_edges(graph)

    assert graph.edges == {(START, "call_llm"), ("call_llm", END)}
