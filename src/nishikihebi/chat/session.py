from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from nishikihebi.graph import build_graph
from nishikihebi.model import Model


class Session(Protocol):
    def ask(self, question: str) -> str: ...


class ChatSession:
    def __init__(self, agent: CompiledStateGraph, thread_id: str) -> None:
        self.agent = agent
        self.thread_id = thread_id

    def ask(self, question: str) -> str:
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": self.thread_id}},
        )
        return result["messages"][-1].content


def start_session(model: Model) -> ChatSession:
    return ChatSession(build_graph(model), thread_id=str(uuid4()))
