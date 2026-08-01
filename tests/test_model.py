from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from nishikihebi.model import NvidiaModel


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.create_kwargs = None

    def create(self, **kwargs):
        self.create_kwargs = kwargs
        return FakeResponse(self.reply)


class FakeChat:
    def __init__(self, reply: str) -> None:
        self.completions = FakeCompletions(reply)


class FakeClient:
    def __init__(self, reply: str) -> None:
        self.chat = FakeChat(reply)


def test_complete_sends_expected_request_and_extracts_text():
    client = FakeClient(reply="hi there")
    model = NvidiaModel(client, model="nvidia/nemotron-3-super-120b-a12b")

    result = model.complete([HumanMessage(content="hello"), AIMessage(content="hey")])

    assert result == "hi there"
    assert client.chat.completions.create_kwargs == {
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hey"},
        ],
    }
