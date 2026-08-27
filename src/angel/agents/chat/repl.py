from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph


class Session(Protocol):
    def ask(self, question: str) -> str: ...


class ChatSession:
    def __init__(self, graph: CompiledStateGraph, thread_id: str) -> None:
        self.graph = graph
        self.thread_id = thread_id

    def ask(self, question: str) -> str:
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": self.thread_id}},
        )
        return result["messages"][-1].content


def start_session(graph: CompiledStateGraph) -> ChatSession:
    return ChatSession(graph, thread_id=str(uuid4()))


def run(
    session: Session,
    input_fn: Callable[[str], str] = input,
    output: Callable[[str], None] = print,
) -> None:
    while True:
        try:
            line = input_fn("> ")
        except EOFError:
            return

        question = line.strip()
        if not question:
            continue
        if question == "/exit":
            return

        output(session.ask(question))
