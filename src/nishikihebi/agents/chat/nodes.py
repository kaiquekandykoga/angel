from typing import cast

from langchain_core.messages import AnyMessage, SystemMessage

from nishikihebi.agents.chat.prompts import SYSTEM_PROMPT
from nishikihebi.agents.chat.state import ChatState
from nishikihebi.clients.llm import LlmClient
from nishikihebi.logs import get_logger

log = get_logger(__name__)


def call_llm(client: LlmClient):
    def node(state: ChatState) -> dict[str, list[AnyMessage]]:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        reply = client.complete(messages)
        reply_length = len(cast("str", reply.content))
        log.debug(
            "call_llm completed",
            message_count=len(messages),
            reply_length=reply_length,
        )
        return {"messages": [reply]}

    return node
