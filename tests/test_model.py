from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from nishikihebi.model import NvidiaModel


class FakeChatModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.invoked_messages: Sequence[BaseMessage] | None = None

    def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.invoked_messages = messages
        return AIMessage(content=self.reply)


def test_complete_forwards_messages_and_returns_ai_message():
    client = FakeChatModel(reply="hi there")
    model = NvidiaModel(cast(BaseChatModel, client))

    messages = [HumanMessage(content="hello"), AIMessage(content="hey")]
    result = model.complete(messages)

    assert isinstance(result, AIMessage)
    assert result.content == "hi there"
    assert client.invoked_messages == messages


def test_complete_forwards_system_messages():
    client = FakeChatModel(reply="hi there")
    model = NvidiaModel(cast(BaseChatModel, client))

    messages = [
        SystemMessage(content="be nice"),
        HumanMessage(content="hello"),
        AIMessage(content="hey"),
    ]
    model.complete(messages)

    assert client.invoked_messages == messages
