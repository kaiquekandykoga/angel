import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nishikihebi.agents.chat.nodes import call_llm
from nishikihebi.agents.chat.prompts import SYSTEM_PROMPT


def test_call_llm_logs_message_count_in_and_reply_length_out_at_debug(
    fake_client, caplog
):
    caplog.set_level(logging.DEBUG, logger="nishikihebi")
    node = call_llm(fake_client)

    node({"messages": [HumanMessage(content="hi")]})

    assert all(r.levelname == "DEBUG" for r in caplog.records)
    context = caplog.records[0].context
    assert context["message_count"] == 2
    assert context["reply_length"] == len(fake_client.reply)


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
