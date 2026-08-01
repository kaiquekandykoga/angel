from __future__ import annotations

from collections.abc import Sequence

import pytest
from langchain_core.messages import AIMessage, BaseMessage


class FakeModel:
    def __init__(self, reply: str = "fake reply") -> None:
        self.reply = reply
        self.calls: list[Sequence[BaseMessage]] = []

    def complete(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.calls.append(list(messages))
        return AIMessage(content=self.reply)


@pytest.fixture
def fake_model() -> FakeModel:
    return FakeModel()
