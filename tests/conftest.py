from __future__ import annotations

from collections.abc import Sequence

import pytest
from langchain_core.messages import BaseMessage


class FakeModel:
    def __init__(self, reply: str = "fake reply") -> None:
        self.reply = reply
        self.calls: list[Sequence[BaseMessage]] = []

    def complete(self, messages: Sequence[BaseMessage]) -> str:
        self.calls.append(list(messages))
        return self.reply


@pytest.fixture
def fake_model() -> FakeModel:
    return FakeModel()
