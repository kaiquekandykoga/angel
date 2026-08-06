from __future__ import annotations

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
