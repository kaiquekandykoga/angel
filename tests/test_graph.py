from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from nishikihebi.graph import build_graph


def test_graph_routes_through_chat_node(fake_model):
    graph = build_graph(fake_model)
    config: RunnableConfig = {"configurable": {"thread_id": "t1"}}

    result = graph.invoke({"messages": [HumanMessage(content="hi")]}, config=config)

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == fake_model.reply
