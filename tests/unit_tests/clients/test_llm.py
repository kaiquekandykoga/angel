import logging
from collections.abc import Sequence
from typing import cast

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from nishikihebi.clients.llm import (
    InvalidMaxCompletionTokensError,
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
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    messages = [HumanMessage(content="hello"), AIMessage(content="hey")]
    result = client.complete(messages)

    assert isinstance(result, AIMessage)
    assert result.content == "hi there"
    assert chat_model.invoked_messages == messages


def test_complete_forwards_system_messages():
    chat_model = FakeChatModel(reply="hi there")
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    messages = [
        SystemMessage(content="be nice"),
        HumanMessage(content="hello"),
        AIMessage(content="hey"),
    ]
    client.complete(messages)

    assert chat_model.invoked_messages == messages


def test_complete_logs_model_call_completed(caplog):
    reply = AIMessage(
        content="hi there",
        response_metadata={"finish_reason": "stop"},
        usage_metadata={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
    )
    chat_model = FakeChatModel(reply="unused")
    chat_model.invoke = lambda messages: reply  # type: ignore[method-assign]
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with caplog.at_level(logging.DEBUG, logger="nishikihebi.clients.llm"):
        client.complete([HumanMessage(content="hello")])

    records = [r for r in caplog.records if r.message == "model call completed"]
    assert len(records) == 1
    context = records[0].context
    assert context["call"] == "complete"
    assert "schema" not in context
    assert context["finish_reason"] == "stop"
    assert context["input_tokens"] == 5
    assert context["output_tokens"] == 2
    assert context["total_tokens"] == 7
    assert isinstance(context["duration_ms"], float)
    assert context["duration_ms"] >= 0


def test_complete_logs_none_when_usage_metadata_and_finish_reason_missing(caplog):
    reply = AIMessage(content="hi there")
    chat_model = FakeChatModel(reply="unused")
    chat_model.invoke = lambda messages: reply  # type: ignore[method-assign]
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with caplog.at_level(logging.DEBUG, logger="nishikihebi.clients.llm"):
        client.complete([HumanMessage(content="hello")])

    matched = next(r for r in caplog.records if r.message == "model call completed")
    context = matched.context
    assert context["finish_reason"] is None
    assert context["input_tokens"] is None
    assert context["output_tokens"] is None
    assert context["total_tokens"] is None


def test_complete_structured_binds_json_schema_response_format_and_returns_model():
    reply = AIMessage(
        content='{"text": "hi"}', response_metadata={"finish_reason": "stop"}
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

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


def test_complete_structured_logs_model_call_completed(caplog):
    reply = AIMessage(
        content='{"text": "hi"}',
        response_metadata={"finish_reason": "stop"},
        usage_metadata={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with caplog.at_level(logging.DEBUG, logger="nishikihebi.clients.llm"):
        client.complete_structured([HumanMessage(content="hello")], Answer)

    records = [r for r in caplog.records if r.message == "model call completed"]
    assert len(records) == 1
    context = records[0].context
    assert context["call"] == "complete_structured"
    assert context["schema"] == "Answer"
    assert context["finish_reason"] == "stop"
    assert context["input_tokens"] == 5
    assert context["output_tokens"] == 2
    assert context["total_tokens"] == 7
    assert isinstance(context["duration_ms"], float)
    assert context["duration_ms"] >= 0


def test_complete_structured_logs_before_raising_truncated_error(caplog):
    reply = AIMessage(
        content='{"text": "hi"}',
        response_metadata={"finish_reason": "length"},
        usage_metadata={
            "input_tokens": 3015,
            "output_tokens": 8192,
            "total_tokens": 11207,
        },
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with (
        caplog.at_level(logging.DEBUG, logger="nishikihebi.clients.llm"),
        pytest.raises(TruncatedCompletionError),
    ):
        client.complete_structured([HumanMessage(content="hello")], Answer)

    records = [r for r in caplog.records if r.message == "model call completed"]
    assert len(records) == 1
    assert records[0].context["finish_reason"] == "length"


def test_complete_structured_does_not_log_when_model_call_raises(caplog):
    error = ValueError("bad output")
    chat_model = FakeChatModel(reply="unused", bound_error=error)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with (
        caplog.at_level(logging.DEBUG, logger="nishikihebi.clients.llm"),
        pytest.raises(ValueError, match="bad output"),
    ):
        client.complete_structured([HumanMessage(content="hello")], Answer)

    assert not [r for r in caplog.records if r.message == "model call completed"]


def test_complete_structured_raises_truncated_error_when_finish_reason_is_length():
    reply = AIMessage(
        content='{"text": "hi"}',
        response_metadata={"finish_reason": "length"},
        usage_metadata={
            "input_tokens": 3015,
            "output_tokens": 8192,
            "total_tokens": 11207,
        },
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with pytest.raises(TruncatedCompletionError, match="Answer") as excinfo:
        client.complete_structured([HumanMessage(content="hello")], Answer)

    message = str(excinfo.value)
    assert "8192" in message
    assert "3015" in message
    assert "11207" in message


def test_complete_structured_truncated_error_handles_missing_usage_metadata():
    reply = AIMessage(
        content='{"text": "hi"}', response_metadata={"finish_reason": "length"}
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with pytest.raises(TruncatedCompletionError, match="Answer") as excinfo:
        client.complete_structured([HumanMessage(content="hello")], Answer)

    message = str(excinfo.value)
    assert "None" not in message
    assert "8192" in message


def test_complete_structured_propagates_validation_error_for_json_not_matching_schema():
    reply = AIMessage(
        content='{"wrong": "field"}', response_metadata={"finish_reason": "stop"}
    )
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with pytest.raises(ValidationError):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_complete_structured_propagates_validation_error_for_non_json_content():
    reply = AIMessage(content="not json", response_metadata={"finish_reason": "stop"})
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with pytest.raises(ValidationError):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_complete_structured_raises_value_error_when_content_is_not_a_string():
    reply = AIMessage(content=["a", "b"], response_metadata={"finish_reason": "stop"})
    chat_model = FakeChatModel(reply="unused", bound_reply=reply)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with pytest.raises(ValueError, match="Answer"):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_complete_structured_propagates_errors_from_the_model_call():
    error = ValueError("bad output")
    chat_model = FakeChatModel(reply="unused", bound_error=error)
    client = NvidiaClient(cast("BaseChatModel", chat_model), max_completion_tokens=8192)

    with pytest.raises(ValueError, match="bad output"):
        client.complete_structured([HumanMessage(content="hello")], Answer)


def test_build_llm_client_constructs_chat_nvidia_with_expected_kwargs(monkeypatch):
    captured_kwargs = {}

    class FakeChatNVIDIA:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr("nishikihebi.clients.llm.ChatNVIDIA", FakeChatNVIDIA)
    env = {"NISHIKIHEBI_NVIDIA_API_KEY": "test-key"}
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", env.get)

    client = build_llm_client()

    assert isinstance(client, NvidiaClient)
    assert isinstance(client.chat_model, FakeChatNVIDIA)
    assert captured_kwargs == {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "test-key",
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "max_completion_tokens": 32768,
        "timeout": 300,
        "temperature": 0.0,
    }
    assert client.max_completion_tokens == 32768


def test_build_llm_client_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", lambda name: None)

    with pytest.raises(MissingApiKeyError, match="NISHIKIHEBI_NVIDIA_API_KEY"):
        build_llm_client()


def test_build_llm_client_uses_max_completion_tokens_override(monkeypatch):
    captured_kwargs = {}

    class FakeChatNVIDIA:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr("nishikihebi.clients.llm.ChatNVIDIA", FakeChatNVIDIA)
    env = {
        "NISHIKIHEBI_NVIDIA_API_KEY": "test-key",
        "NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS": "16000",
    }
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", env.get)

    client = build_llm_client()

    assert isinstance(client, NvidiaClient)
    assert captured_kwargs["max_completion_tokens"] == 16000
    assert client.max_completion_tokens == 16000


def test_build_llm_client_raises_when_max_completion_tokens_not_an_integer(monkeypatch):
    env = {
        "NISHIKIHEBI_NVIDIA_API_KEY": "test-key",
        "NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS": "not-a-number",
    }
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", env.get)

    with pytest.raises(
        InvalidMaxCompletionTokensError,
        match="NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS",
    ):
        build_llm_client()


def test_build_llm_client_raises_when_max_completion_tokens_not_positive(monkeypatch):
    env = {
        "NISHIKIHEBI_NVIDIA_API_KEY": "test-key",
        "NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS": "0",
    }
    monkeypatch.setattr("nishikihebi.clients.llm.load_env_var", env.get)

    with pytest.raises(
        InvalidMaxCompletionTokensError,
        match="NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS",
    ):
        build_llm_client()
