from collections.abc import Sequence
from typing import cast

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from nishikihebi.clients.llm import MissingApiKeyError, NvidiaClient, build_llm_client


class Answer(BaseModel):
    text: str


class FakeStructuredRunnable:
    def __init__(
        self, result: BaseModel | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.invoked_messages: Sequence[BaseMessage] | None = None

    def invoke(self, messages: Sequence[BaseMessage]) -> BaseModel:
        self.invoked_messages = messages
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class FakeChatModel:
    def __init__(
        self,
        reply: str,
        structured_runnable: FakeStructuredRunnable | None = None,
    ) -> None:
        self.reply = reply
        self.invoked_messages: Sequence[BaseMessage] | None = None
        self.structured_runnable = structured_runnable
        self.structured_output_schema: type[BaseModel] | None = None

    def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.invoked_messages = messages
        return AIMessage(content=self.reply)

    def with_structured_output(
        self, schema: type[BaseModel]
    ) -> FakeStructuredRunnable | None:
        self.structured_output_schema = schema
        return self.structured_runnable


def test_complete_forwards_messages_and_returns_ai_message():
    chat_model = FakeChatModel(reply="hi there")
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    messages = [HumanMessage(content="hello"), AIMessage(content="hey")]
    result = client.complete(messages)

    assert isinstance(result, AIMessage)
    assert result.content == "hi there"
    assert chat_model.invoked_messages == messages


def test_complete_forwards_system_messages():
    chat_model = FakeChatModel(reply="hi there")
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    messages = [
        SystemMessage(content="be nice"),
        HumanMessage(content="hello"),
        AIMessage(content="hey"),
    ]
    client.complete(messages)

    assert chat_model.invoked_messages == messages


def test_complete_structured_forwards_schema_and_messages_and_returns_parsed_model():
    parsed = Answer(text="hi")
    runnable = FakeStructuredRunnable(result=parsed)
    chat_model = FakeChatModel(reply="unused", structured_runnable=runnable)
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    messages = [HumanMessage(content="hello")]
    result = client.complete_structured(messages, Answer)

    assert result is parsed
    assert chat_model.structured_output_schema is Answer
    assert runnable.invoked_messages == messages


def test_complete_structured_propagates_exception():
    error = ValueError("bad output")
    runnable = FakeStructuredRunnable(error=error)
    chat_model = FakeChatModel(reply="unused", structured_runnable=runnable)
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    with pytest.raises(ValueError, match="bad output"):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_build_llm_client_constructs_chat_nvidia_with_expected_kwargs(monkeypatch):
    captured_kwargs = {}

    class FakeChatNVIDIA:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr("nishikihebi.clients.llm.ChatNVIDIA", FakeChatNVIDIA)
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", lambda name: "test-key")

    client = build_llm_client()

    assert isinstance(client, NvidiaClient)
    assert isinstance(client.chat_model, FakeChatNVIDIA)
    assert captured_kwargs == {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "test-key",
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "max_completion_tokens": 1024,
    }


def test_build_llm_client_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", lambda name: None)

    with pytest.raises(MissingApiKeyError, match="NISHIKIHEBI_NVIDIA_API_KEY"):
        build_llm_client()
