from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from langchain_core.messages import BaseMessage


class Model(Protocol):
    def complete(self, messages: Sequence[BaseMessage]) -> str: ...


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaModel:
    def __init__(self, client, model: str = "nvidia/nemotron-3-super-120b-a12b") -> None:
        self.client = client
        self.model = model

    def complete(self, messages: Sequence[BaseMessage]) -> str:
        nvidia_messages = [
            {"role": "assistant" if message.type == "ai" else "user", "content": message.content}
            for message in messages
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=nvidia_messages,
        )
        return response.choices[0].message.content
