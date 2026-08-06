from langchain_core.messages import AnyMessage, SystemMessage

from nishikihebi.llm_client import LlmClient
from nishikihebi.state import State

SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."


def call_llm(client: LlmClient):
    def node(state: State) -> dict[str, list[AnyMessage]]:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [client.complete(messages)]}

    return node
