from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from langchain_core.messages import AIMessage, BaseMessage


class Model(Protocol):
    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage: ...


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

_ROLES = {"human": "user", "ai": "assistant", "system": "system"}


class NvidiaModel:
    def __init__(self, client, model: str = "nvidia/nemotron-3-super-120b-a12b") -> None:
        self.client = client
        self.model = model

    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage:
        nvidia_messages = [
            {"role": _ROLES[message.type], "content": message.content}
            for message in messages
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=nvidia_messages,
        )
        return AIMessage(content=response.choices[0].message.content)
