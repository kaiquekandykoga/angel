from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from nishikihebi.agent import build_agent


def test_respond_node_appends_ai_message(fake_model):
    agent = build_agent(fake_model)
    config = {"configurable": {"thread_id": "t1"}}

    result = agent.invoke({"messages": [HumanMessage(content="hi")]}, config=config)

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == fake_model.reply
