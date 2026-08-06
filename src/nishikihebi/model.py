from collections.abc import Sequence
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from nishikihebi.env import load_api_key


class Model(Protocol):
    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage: ...


class MissingApiKeyError(RuntimeError):
    pass


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"
NVIDIA_MAX_COMPLETION_TOKENS = 1024


class NvidiaModel:
    def __init__(self, client: BaseChatModel) -> None:
        self.client = client

    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage:
        return cast("AIMessage", self.client.invoke(list(messages)))


def build_model() -> Model:
    api_key = load_api_key()
    if not api_key:
        raise MissingApiKeyError("NVIDIA_API_KEY environment variable is not set.")

    client = ChatNVIDIA(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        model=NVIDIA_MODEL,
        max_completion_tokens=NVIDIA_MAX_COMPLETION_TOKENS,
    )
    return NvidiaModel(client)
