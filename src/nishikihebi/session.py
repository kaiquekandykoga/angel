from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import HumanMessage

from nishikihebi.agent import build_agent
from nishikihebi.model import Model


class ChatSession:
    def __init__(self, agent, thread_id: str) -> None:
        self.agent = agent
        self.thread_id = thread_id

    def ask(self, question: str) -> str:
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": self.thread_id}},
        )
        return result["messages"][-1].content


def start_session(model: Model) -> ChatSession:
    return ChatSession(build_agent(model), thread_id=str(uuid4()))
