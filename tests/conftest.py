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


@pytest.fixture
def scripted_input():
    def factory(*lines: str):
        inputs = iter(lines)

        def input_fn(_prompt: str = "") -> str:
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError from None

        return input_fn

    return factory
