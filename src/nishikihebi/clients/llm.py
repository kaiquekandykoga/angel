from collections.abc import Sequence
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from nishikihebi.env import load_env_var


class LlmClient(Protocol):
    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage: ...


class MissingApiKeyError(RuntimeError):
    pass


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"
NVIDIA_MAX_COMPLETION_TOKENS = 1024


class NvidiaClient:
    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage:
        return cast("AIMessage", self.chat_model.invoke(list(messages)))


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
    )
    return NvidiaClient(chat_model)
