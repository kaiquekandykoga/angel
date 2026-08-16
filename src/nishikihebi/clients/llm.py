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


class InvalidMaxCompletionTokensError(RuntimeError):
    pass


class TruncatedCompletionError(RuntimeError):
    pass


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
NVIDIA_MAX_COMPLETION_TOKENS_DEFAULT = 32768
NVIDIA_TIMEOUT_SECONDS = 300


class NvidiaClient:
    def __init__(self, chat_model: BaseChatModel, max_completion_tokens: int) -> None:
        self.chat_model = chat_model
        self.max_completion_tokens = max_completion_tokens

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
            usage = reply.usage_metadata
            usage_str = (
                f"input_tokens={usage['input_tokens']}, "
                f"output_tokens={usage['output_tokens']}, "
                f"total_tokens={usage['total_tokens']}"
                if usage is not None
                else "usage metadata unavailable"
            )
            raise TruncatedCompletionError(
                f"Completion for schema {schema.__name__!r} was truncated: "
                f"the model hit the max_completion_tokens limit of "
                f"{self.max_completion_tokens} ({usage_str})."
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

    max_completion_tokens_raw = load_env_var("NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS")
    if not max_completion_tokens_raw:
        max_completion_tokens = NVIDIA_MAX_COMPLETION_TOKENS_DEFAULT
    else:
        try:
            max_completion_tokens = int(max_completion_tokens_raw)
        except ValueError as error:
            raise InvalidMaxCompletionTokensError(
                "NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS must be a positive "
                f"integer, got {max_completion_tokens_raw!r}."
            ) from error
        if max_completion_tokens <= 0:
            raise InvalidMaxCompletionTokensError(
                "NISHIKIHEBI_NVIDIA_MAX_COMPLETION_TOKENS must be a positive "
                f"integer, got {max_completion_tokens_raw!r}."
            )

    chat_model = ChatNVIDIA(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        model=NVIDIA_MODEL,
        max_completion_tokens=max_completion_tokens,
        timeout=NVIDIA_TIMEOUT_SECONDS,
    )
    return NvidiaClient(chat_model, max_completion_tokens)
