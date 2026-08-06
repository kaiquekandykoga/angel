from langgraph.graph.state import CompiledStateGraph

from nishikihebi.graph import Graphs, build_graphs


def test_build_graphs_exposes_the_chat_graph(fake_client):
    graphs = build_graphs(fake_client)

    assert isinstance(graphs, Graphs)
    assert isinstance(graphs.chat, CompiledStateGraph)
