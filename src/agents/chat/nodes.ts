import { type BaseMessage, SystemMessage } from "@langchain/core/messages";
import type { LlmClient } from "../../clients/llm.js";
import { getLogger } from "../../logs.js";
import { SYSTEM_PROMPT } from "./prompts.js";
import type { ChatState } from "./state.js";

const log = getLogger("angel.agents.chat.nodes");

/** Prepends the system prompt, calls the model, and appends its reply. */
export function callLlm(client: LlmClient) {
  return async (state: ChatState): Promise<{ messages: BaseMessage[] }> => {
    const messages = [new SystemMessage(SYSTEM_PROMPT), ...state.messages];
    const reply = await client.complete(messages);
    log.debug("call_llm completed", {
      message_count: messages.length,
      reply_length: typeof reply.content === "string" ? reply.content.length : 0,
    });
    return { messages: [reply] };
  };
}
