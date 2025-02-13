import {Accessor, createSignal, Setter} from "solid-js";
import {Client} from "@langchain/langgraph-sdk";
// import { RemoteGraph } from "@langchain/langgraph/remote";
// import { isAIMessageChunk } from "@langchain/core/messages";

import {getEditorUrl, queryLinkLabels} from "./utils";

// // Types of objects used when interacting with LLM agents
// type RefenceDocument = {
//   page_content: string;
//   metadata: {
//     doc_type: string;
//     endpoint_url: string;
//     question: string;
//     answer: string;
//     score: number;
//   };
// };

type Links = {
  url: string;
  label: string;
  title: string;
};

type Step = {
  node_id: string;
  label: string;
  details: string; // Details about the step as markdown string
  substeps?: {label: string, details: string}[];
  // retrieved_docs?: RefenceDocument[];
};

export type Message = {
  role: "assistant" | "user";
  content: Accessor<string>;
  setContent: Setter<string>;
  steps: Accessor<Step[]>;
  setSteps: Setter<Step[]>;
  links: Accessor<Links[]>;
  setLinks: Setter<Links[]>;
};

export class ChatState {
  apiUrl: string;
  apiKey: string;
  model: string;
  messages: Accessor<Message[]>;
  setMessages: Setter<Message[]>;
  abortController: AbortController;

  constructor({apiUrl = "", apiKey = "", model = ""}: {apiUrl?: string; apiKey?: string; model?: string}) {
    // this.apiUrl = apiUrl.endsWith("/") ? apiUrl : apiUrl + "/";
    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
    this.model = model;

    const [messages, setMessages] = createSignal<Message[]>([]);
    this.messages = messages;
    this.setMessages = setMessages;
    this.abortController = new AbortController();
  }

  abortRequest = () => {
    this.abortController.abort();
    this.abortController = new AbortController();
  };

  lastMsg = () => this.messages()[this.messages().length - 1];

  scrollToInput = () => {};

  appendMessage = (msgContent: string, role: "assistant" | "user" = "assistant") => {
    const [content, setContent] = createSignal(msgContent);
    const [steps, setSteps] = createSignal<Step[]>([]);
    const [links, setLinks] = createSignal<Links[]>([]);
    const newMsg: Message = {content, setContent, steps, setSteps, role, links, setLinks};
    // const query = extractSparqlQuery(msgContent);
    // if (query) newMsg.setLinks([{url: query, ...queryLinkLabels}]);
    this.setMessages(messages => [...messages, newMsg]);
  };

  appendContentToLastMsg = (newContent: string, newline: boolean = false) => {
    this.lastMsg().setContent(content => content + (newline ? "\n\n" : "") + newContent);
  };

  appendStepToLastMsg = (
    node_id: string,
    label: string,
    details: string = "",
    substeps: {label: string, details: string}[] = [],
  ) => {
    this.lastMsg().setSteps(steps => [...steps, {node_id, label, details, substeps}]);
    this.scrollToInput();
    // this.inputTextEl.scrollIntoView({behavior: "smooth"});
  };
}

// Stream a response from various LLM agent providers (OpenAI-like, LangGraph, LangServe)
export async function streamResponse(state: ChatState, question: string) {
  state.appendMessage(question, "user");
  if (state.apiUrl.endsWith(":2024/") || state.apiUrl.endsWith(":8123/")) {
    // Query LangGraph API
    await streamLangGraphApi(state);
  } else if (state.apiUrl.endsWith("/completions/")) {
    // Query the OpenAI-compatible chat API
    await streamOpenAILikeApi(state);
  } else {
    // Query LangGraph through our custom API
    await streamCustomLangGraph(state);
  }
}

async function processLangGraphChunk(state: ChatState, chunk: any) {
  if (chunk.event === "error") {
    throw new Error(`An error occurred. Please try again. ${chunk.data.error}: ${chunk.data.message}`);
  }
  // console.log(chunk);
  // Handle updates to the state (nodes that are retrieving stuff without querying the LLM usually)
  if (chunk.event === "updates") {
    console.log("UPDATES", chunk);
    for (const nodeId of Object.keys(chunk.data)) {
      const nodeData = chunk.data[nodeId];
      if (!nodeData) continue;
      if (nodeData.steps) {
        // Handle most generic steps output sent by the agent
        for (const step of nodeData.steps) {
          state.appendStepToLastMsg(nodeId, step.label, step.details, step.substeps);
          // console.log("STEP", step);
          // Handle step specific to post-generation validation
          if (step.type === "recall") {
            // When `recall` is called, the model will re-generate the response, so we need to update the message
            state.lastMsg().setContent("");
          } else if (step.fixed_message) {
            // If the update contains a message with a fix
            state.lastMsg().setContent(step.fixed_message);
          }
        }
      }
      if (nodeData.structured_output) {
        // Special case to handle things extracted from output
        // Here we add links to open the SPARQL query in an editor
        if (nodeData.structured_output.sparql_query) {
          state.lastMsg().setLinks([
            {
              url: getEditorUrl(
                nodeData.structured_output.sparql_query,
                nodeData.structured_output.sparql_endpoint_url,
              ),
              ...queryLinkLabels,
            },
          ]);
        }
      }
    }
  }
  // Handle messages from the model
  if (chunk.event === "messages") {
    const [msg, metadata] = chunk.data;
    if (metadata.structured_output_format) return;
    // const {message, metadata} = chunk.data;
    // console.log("MESSAGES", msg, metadata);
    if (msg.tool_calls?.length > 0) {
      // Tools calls requested by the model
      const toolNames = msg.tool_calls.map((tool_call: any) => tool_call.name).join(", ");
      if (toolNames) state.appendStepToLastMsg(metadata.langgraph_node, `🔧 Calling tools: ${toolNames}`);
    }
    if (msg.content && msg.type === "tool") {
      // If tool called by model
      state.appendStepToLastMsg(metadata.langgraph_node, `⚗️ Tool ${msg.name} result: ${msg.content}`);
    } else if (msg.content === "</think>" && msg.type === "AIMessageChunk") {
      // Putting thinking process in a separate step
      state.appendContentToLastMsg(msg.content);
      state.appendStepToLastMsg(metadata.langgraph_node, "💭 Thought process", state.lastMsg().content());
      state.lastMsg().setContent("");
    } else if (msg.content && msg.type === "AIMessageChunk") {
      // console.log("AIMessageChunk", msg, metadata);
      // Response from the model
      state.appendContentToLastMsg(msg.content);
    }
  }
}

async function streamCustomLangGraph(state: ChatState) {
  const response = await fetch(`${state.apiUrl}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${state.apiKey}`,
    },
    signal: state.abortController.signal,
    body: JSON.stringify({
      messages: state.messages().map(({content, role}) => ({content: content(), role})),
      stream: true,
      ...(state.model ? {model: state.model} : {}),
    }),
  });

  state.appendMessage("", "assistant");
  const reader = response.body?.getReader()!;
  const decoder = new TextDecoder("utf-8");
  let buffer = ""; // Buffer for incomplete chunks
  // Iterate stream response
  while (true) {
    if (reader) {
      const {value, done} = await reader.read();
      if (done) break;
      const chunkStr = decoder.decode(value, {stream: true});
      buffer += chunkStr;
      let lines = buffer.split("\n");
      // Keep the last line if it's incomplete
      buffer = lines.pop() || "";
      for (const line of lines.filter(line => line.trim() !== "")) {
        if (line === "data: [DONE]") return;
        if (line.startsWith("data: ")) {
          try {
            const json = JSON.parse(line.substring(6));
            processLangGraphChunk(state, json);
          } catch (e) {
            console.log("Error parsing line", e, line);
          }
        }
      }
    }
  }
}

async function streamLangGraphApi(state: ChatState) {
  // Experimental, would need to be updated to properly uses steps output
  const client = new Client({apiUrl: state.apiUrl});
  const graphName = "agent";

  // https://langchain-ai.github.io/langgraphjs/how-tos/stream-tokens
  // https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_messages
  // https://langchain-ai.github.io/langgraph/concepts/streaming/
  const thread = await client.threads.create();
  const streamResponse = client.runs.stream(thread["thread_id"], graphName, {
    // input: {messages: [{role: "human", content: "what is 3 times 6?"}]},
    // input: {messages: [{role: "human", content: question}]},
    input: {messages: state.messages().map(({content, role}) => ({content: content(), role}))},
    config: {configurable: {}},
    streamMode: ["messages-tuple", "updates"],
    signal: state.abortController.signal,
  });
  state.appendMessage("", "assistant");
  for await (const chunk of streamResponse) {
    processLangGraphChunk(state, chunk);
  }
}

async function streamOpenAILikeApi(state: ChatState) {
  // Experimental, would need to be updated to properly uses steps output
  const response = await fetch(`${state.apiUrl}chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${state.apiKey}`,
    },
    signal: state.abortController.signal,
    body: JSON.stringify({
      messages: state.messages().map(({content, role}) => ({content: content(), role})),
      model: state.model,
      // model: "azure_ai/mistral-large",
      max_tokens: 500,
      stream: true,
      // api_key: state.apiKey,
    }),
  });

  state.appendMessage("", "assistant");
  const reader = response.body?.getReader()!;
  const decoder = new TextDecoder("utf-8");
  let partialLine = ""; // Buffer for incomplete lines

  // Iterate stream response
  while (true) {
    if (reader) {
      const {value, done} = await reader.read();
      if (done) break;
      const chunkStr = decoder.decode(value, {stream: true});
      // Combine with any leftover data from the previous iteration
      const combined = partialLine + chunkStr;
      if (partialLine) partialLine = "";
      for (const line of combined.split("\n").filter(line => line.trim() !== "")) {
        if (line === "data: [DONE]") return;
        if (line.startsWith("data: ")) {
          // console.log(line)
          try {
            const json = JSON.parse(line.substring(6));
            if (json.retrieved_docs) {
              state.appendStepToLastMsg(
                `📚️ Using ${json.retrieved_docs.length} documents`,
                "retrieve",
                json.retrieved_docs,
              );
            } else {
              const newContent = json.choices[0].delta?.content;
              if (newContent) {
                // console.log(newContent);
                state.appendContentToLastMsg(newContent);
              }
            }
          } catch {
            partialLine = line;
          }
        }
      }
    }
  }

  // Extract query once message complete
  // const query = extractSparqlQuery(state.lastMsg().content());
  // if (query) state.lastMsg().setLinks([{url: query, ...queryLinkLabels}]);
}
