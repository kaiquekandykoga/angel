import type { BaseCheckpointSaver } from "@langchain/langgraph";
import { END, MemorySaver, START, StateGraph } from "@langchain/langgraph";
import { getLogger } from "../../../../packages/shared/logs.js";
import type { LlmClient } from "../../external/nvidia/client.js";
import { callLlm } from "./nodes.js";
import { ChatAnnotation } from "./state.js";

const log = getLogger("angel.agents.chat.graph");

export function buildChatGraph(client: LlmClient, checkpointer?: BaseCheckpointSaver) {
  log.debug("wiring call_llm node");
  const graph = new StateGraph(ChatAnnotation)
    .addNode("call_llm", callLlm(client))
    .addEdge(START, "call_llm")
    .addEdge("call_llm", END);
  const compiled = graph.compile({ checkpointer: checkpointer ?? new MemorySaver() });
  log.info("chat graph ready");
  return compiled;
}

export type ChatGraph = ReturnType<typeof buildChatGraph>;
