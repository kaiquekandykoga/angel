from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nishikihebi.nodes.call_llm import SYSTEM_PROMPT, call_llm


def test_call_llm_appends_ai_message(fake_model):
    node = call_llm(fake_model)

    result = node({"messages": [HumanMessage(content="hi")]})

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == fake_model.reply


def test_call_llm_prepends_system_prompt_without_persisting_it(fake_model):
    node = call_llm(fake_model)

    result = node({"messages": [HumanMessage(content="hi")]})

    sent = fake_model.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == SYSTEM_PROMPT
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])
