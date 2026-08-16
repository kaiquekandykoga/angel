from collections.abc import Sequence
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from pydantic import BaseModel

from nishikihebi.env import load_env_var


class LlmClient(Protocol):
    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage: ...

    def complete_structured[T: BaseModel](
        self, messages: Sequence[BaseMessage], schema: type[T]
    ) -> T: ...


class MissingApiKeyError(RuntimeError):
    pass


class TruncatedCompletionError(RuntimeError):
    pass


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"
NVIDIA_MAX_COMPLETION_TOKENS = 8192
NVIDIA_TIMEOUT_SECONDS = 300


class NvidiaClient:
    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage:
        return cast("AIMessage", self.chat_model.invoke(list(messages)))

    def complete_structured[T: BaseModel](
        self, messages: Sequence[BaseMessage], schema: type[T]
    ) -> T:
        reply = cast(
            "AIMessage",
            self.chat_model.bind(
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "schema": schema.model_json_schema(),
                        "strict": True,
                    },
                }
            ).invoke(list(messages)),
        )
        if reply.response_metadata.get("finish_reason") == "length":
            raise TruncatedCompletionError(
                f"Completion for schema {schema.__name__!r} was truncated: "
                "the model hit the max_completion_tokens limit."
            )
        if not isinstance(reply.content, str):
            raise ValueError(
                f"Expected string content for schema {schema.__name__!r}, "
                f"got {type(reply.content).__name__} instead."
            )
        return schema.model_validate_json(reply.content)


def build_llm_client() -> LlmClient:
    api_key = load_env_var("NISHIKIHEBI_NVIDIA_API_KEY")
    if not api_key:
        raise MissingApiKeyError(
            "NISHIKIHEBI_NVIDIA_API_KEY environment variable is not set."
        )

    chat_model = ChatNVIDIA(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        model=NVIDIA_MODEL,
        max_completion_tokens=NVIDIA_MAX_COMPLETION_TOKENS,
        timeout=NVIDIA_TIMEOUT_SECONDS,
    )
    return NvidiaClient(chat_model)
