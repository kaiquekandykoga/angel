from langchain_core.messages import AnyMessage, SystemMessage

from nishikihebi.model import Model
from nishikihebi.state import State

SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."


def call_llm(model: Model):
    def node(state: State) -> dict[str, list[AnyMessage]]:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [model.complete(messages)]}

    return node
