from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nishikihebi.nodes.chat.call_llm import SYSTEM_PROMPT, call_llm


def test_call_llm_appends_ai_message(fake_client):
    node = call_llm(fake_client)

    result = node({"messages": [HumanMessage(content="hi")]})

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == fake_client.reply


def test_call_llm_prepends_system_prompt_without_persisting_it(fake_client):
    node = call_llm(fake_client)

    result = node({"messages": [HumanMessage(content="hi")]})

    sent = fake_client.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == SYSTEM_PROMPT
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])
