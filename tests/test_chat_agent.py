from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nishikihebi.agents.chat import SYSTEM_PROMPT, build_chat_agent


def test_respond_node_appends_ai_message(fake_model):
    agent = build_chat_agent(fake_model)

    result = agent.invoke({"messages": [HumanMessage(content="hi")]})

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == fake_model.reply


def test_respond_prepends_system_prompt_without_persisting_it(fake_model):
    agent = build_chat_agent(fake_model)

    result = agent.invoke({"messages": [HumanMessage(content="hi")]})

    sent = fake_model.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == SYSTEM_PROMPT
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])
