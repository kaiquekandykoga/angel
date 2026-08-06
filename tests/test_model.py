from collections.abc import Sequence
from typing import cast

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from nishikihebi.model import MissingApiKeyError, NvidiaModel, build_model


class FakeChatModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.invoked_messages: Sequence[BaseMessage] | None = None

    def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.invoked_messages = messages
        return AIMessage(content=self.reply)


def test_complete_forwards_messages_and_returns_ai_message():
    client = FakeChatModel(reply="hi there")
    model = NvidiaModel(cast("BaseChatModel", client))

    messages = [HumanMessage(content="hello"), AIMessage(content="hey")]
    result = model.complete(messages)

    assert isinstance(result, AIMessage)
    assert result.content == "hi there"
    assert client.invoked_messages == messages


def test_complete_forwards_system_messages():
    client = FakeChatModel(reply="hi there")
    model = NvidiaModel(cast("BaseChatModel", client))

    messages = [
        SystemMessage(content="be nice"),
        HumanMessage(content="hello"),
        AIMessage(content="hey"),
    ]
    model.complete(messages)

    assert client.invoked_messages == messages


def test_build_model_constructs_chat_nvidia_with_expected_kwargs(monkeypatch):
    captured_kwargs = {}

    class FakeChatNVIDIA:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr("nishikihebi.model.ChatNVIDIA", FakeChatNVIDIA)
    monkeypatch.setattr("nishikihebi.model.load_api_key", lambda: "test-key")

    model = build_model()

    assert isinstance(model, NvidiaModel)
    assert isinstance(model.client, FakeChatNVIDIA)
    assert captured_kwargs == {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "test-key",
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "max_completion_tokens": 1024,
    }


def test_build_model_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr("nishikihebi.model.load_api_key", lambda: None)

    with pytest.raises(MissingApiKeyError, match="NVIDIA_API_KEY"):
        build_model()
