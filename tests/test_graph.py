from langgraph.graph.state import CompiledStateGraph

from nishikihebi.graph import Graphs, build_graphs


def test_build_graphs_exposes_the_chat_and_pr_review_graphs(fake_client, fake_github):
    graphs = build_graphs(fake_client, fake_github)

    assert isinstance(graphs, Graphs)
    assert isinstance(graphs.chat, CompiledStateGraph)
    assert isinstance(graphs.pr_review, CompiledStateGraph)
