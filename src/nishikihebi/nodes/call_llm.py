from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import SystemMessage

from nishikihebi.model import Model
from nishikihebi.state import State

SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."


def call_llm(model: Model) -> Callable[[State], dict]:
    def node(state: State) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [model.complete(messages)]}

    return node
