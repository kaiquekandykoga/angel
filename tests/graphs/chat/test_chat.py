from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from nishikihebi.graphs.chat import build_chat_graph


def test_graph_routes_through_chat_node(fake_client):
    graph = build_chat_graph(fake_client)
    config: RunnableConfig = {"configurable": {"thread_id": "t1"}}

    result = graph.invoke({"messages": [HumanMessage(content="hi")]}, config=config)

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == fake_client.reply
