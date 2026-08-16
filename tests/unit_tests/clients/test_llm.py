from collections.abc import Sequence
from typing import cast

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from nishikihebi.clients.llm import (
    MissingApiKeyError,
    NvidiaClient,
    TruncatedCompletionError,
    build_llm_client,
)


class Answer(BaseModel):
    text: str


class FakeBoundRunnable:
    def __init__(
        self, reply: AIMessage | None = None, error: Exception | None = None
    ) -> None:
        self.reply = reply
        self.error = error
        self.invoked_messages: Sequence[BaseMessage] | None = None

    def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.invoked_messages = messages
        if self.error is not None:
            raise self.error
        assert self.reply is not None
        return self.reply


class FakeChatModel:
    def __init__(
        self,
        reply: str,
        bound_reply: AIMessage | None = None,
        bound_error: Exception | None = None,
    ) -> None:
        self.reply = reply
        self.invoked_messages: Sequence[BaseMessage] | None = None
        self.bound_reply = bound_reply
        self.bound_error = bound_error
        self.bind_kwargs: dict[str, object] | None = None
        self.bound_runnable: FakeBoundRunnable | None = None

    def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.invoked_messages = messages
        return AIMessage(content=self.reply)

    def bind(self, **kwargs: object) -> FakeBoundRunnable:
        self.bind_kwargs = kwargs
        self.bound_runnable = FakeBoundRunnable(self.bound_reply, self.bound_error)
        return self.bound_runnable


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


def test_complete_structured_binds_json_schema_response_format_and_returns_model():
    reply = AIMessage(
        content='{"text": "hi"}', response_metadata={"finish_reason": "stop"}
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    messages = [HumanMessage(content="hello")]
    result = client.complete_structured(messages, Answer)

    assert result == Answer(text="hi")
    assert chat_model.bind_kwargs == {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "Answer",
                "schema": Answer.model_json_schema(),
                "strict": True,
            },
        }
    }
    assert chat_model.bound_runnable is not None
    assert chat_model.bound_runnable.invoked_messages == messages


def test_complete_structured_raises_truncated_error_when_finish_reason_is_length():
    reply = AIMessage(
        content='{"text": "hi"}', response_metadata={"finish_reason": "length"}
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    with pytest.raises(TruncatedCompletionError, match="Answer"):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_complete_structured_propagates_validation_error_for_json_not_matching_schema():
    reply = AIMessage(
        content='{"wrong": "field"}', response_metadata={"finish_reason": "stop"}
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    with pytest.raises(ValidationError):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_complete_structured_propagates_validation_error_for_non_json_content():
    reply = AIMessage(content="not json", response_metadata={"finish_reason": "stop"})
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    with pytest.raises(ValidationError):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_complete_structured_raises_value_error_when_content_is_not_a_string():
    reply = AIMessage(
        content=["a", "b"], response_metadata={"finish_reason": "stop"}
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model))

    with pytest.raises(ValueError, match="Answer"):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_complete_structured_propagates_errors_from_the_model_call():
    error = ValueError("bad output")
    chat_model = FakeChatModel(reply="unused", bound_error=error)
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
        "max_completion_tokens": 8192,
        "timeout": 300,
    }


def test_build_llm_client_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", lambda name: None)

    with pytest.raises(MissingApiKeyError, match="NISHIKIHEBI_NVIDIA_API_KEY"):
        build_llm_client()
