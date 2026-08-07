import logging
from typing import cast

from langchain_core.messages import AnyMessage, SystemMessage

from nishikihebi.clients.llm import LlmClient
from nishikihebi.states.chat import ChatState

SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."

logger = logging.getLogger(__name__)


def call_llm(client: LlmClient):
    def node(state: ChatState) -> dict[str, list[AnyMessage]]:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        reply = client.complete(messages)
        reply_length = len(cast("str", reply.content))
        logger.debug(
            "call_llm completed",
            extra={
                "context": {
                    "message_count": len(messages),
                    "reply_length": reply_length,
                }
            },
        )
        return {"messages": [reply]}

    return node
