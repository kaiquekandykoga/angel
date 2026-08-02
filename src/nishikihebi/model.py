from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage


class Model(Protocol):
    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage: ...


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaModel:
    def __init__(self, client: BaseChatModel) -> None:
        self.client = client

    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage:
        return cast(AIMessage, self.client.invoke(list(messages)))
