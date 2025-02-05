import {Accessor, createSignal, Setter} from "solid-js";
import {Client} from "@langchain/langgraph-sdk";
// import { RemoteGraph } from "@langchain/langgraph/remote";
// import { isAIMessageChunk } from "@langchain/core/messages";

import {extractSparqlQuery, getEditorUrl, queryLinkLabels} from "./utils";

// Types of objects used when interacting with LLM agents
type RefenceDocument = {
  page_content: string;
  metadata: {
    doc_type: string;
    endpoint_url: string;
    question: string;
    answer: string;
    score: number;
  };
};

type Links = {
  url: string;
  label: string;
  title: string;
};

type Step = {
  // id: string;
  node_id: string;
  label: string;
  retrieved_docs: RefenceDocument[];
  details: string; // Markdown details about the step
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
    const query = extractSparqlQuery(msgContent);
    if (query) newMsg.setLinks([{url: query, ...queryLinkLabels}]);
    this.setMessages(messages => [...messages, newMsg]);
  };

  appendContentToLastMsg = (newContent: string, newline: boolean = false) => {
    this.lastMsg().setContent(content => content + (newline ? "\n\n" : "") + newContent);
  };

  appendStepToLastMsg = (
    label: string,
    node_id: string,
    retrieved_docs: RefenceDocument[] = [],
    details: string = "",
  ) => {
    this.lastMsg().setSteps(steps => [...steps, {node_id, label, retrieved_docs, details}]);
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
    // console.log("UPDATES", chunk);
    for (const nodeId of Object.keys(chunk.data)) {
      const nodeData = chunk.data[nodeId];
      if (nodeData.retrieved_docs) {
        // Retrieved docs sent
        state.appendStepToLastMsg(
          `📚️ Using ${nodeData.retrieved_docs.length} documents`,
          nodeId,
          nodeData.retrieved_docs,
        );
      } else if (nodeData.extracted_entities) {
        // Handle entities extracted from the user input
        state.appendStepToLastMsg(
          `⚗️ Extracted ${nodeData.extracted_entities.length} potential entities`,
          nodeId,
          [],
          nodeData.extracted_entities.map((entity: any) =>
            `\n\nEntities found in the user question for "${entity.text}":\n\n` +
            entity.matchs.map((match: any) =>
              `- ${match.payload.label} with IRI <${match.payload.uri}> in endpoint ${match.payload.endpoint_url}\n\n`
            ).join('')
          ).join(''),
        );
      } else if (nodeData.structured_output) {
        // Handle things extracted from output (SPARQL queries here)
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
      } else if (nodeData.validation) {
        // Handle post-generation validation
        for (const validationStep of nodeData.validation) {
          // Handle messages related to tools (includes post generation validation)
          state.appendStepToLastMsg(validationStep.label, nodeId, [], validationStep.details);
          if (validationStep.type === "recall") {
            // When recall-model is called, the model will re-generate the response, so we need to update the message
            // If the update contains a message with a fix (e.g. done during post generation validation)
            state.lastMsg().setContent("");
          } else if (validationStep.fixed_message) {
            state.lastMsg().setContent(validationStep.fixed_message);
          }
        }
      } else {
        // Handle other updates
        state.appendStepToLastMsg(`💭 ${nodeId.replace("_", " ")}`, nodeId);
      }
    }
  }
  // Handle messages from the model
  if (chunk.event === "messages") {
    const [msg, metadata] = chunk.data;
    // const {message, metadata} = chunk.data;
    // console.log("MESSAGES", msg, metadata);
    if (msg.tool_calls?.length > 0) {
      // Tools calls requested by the model
      const toolNames = msg.tool_calls.map((tool_call: any) => tool_call.name).join(", ");
      if (toolNames) state.appendStepToLastMsg(`🔧 Calling tools: ${toolNames}`, metadata.langgraph_node);
    }
    if (msg.content && msg.type === "tool") {
      // If tool called by model
      state.appendStepToLastMsg(`⚗️ Tool ${msg.name} result: ${msg.content}`, metadata.langgraph_node);
    } else if (msg.content === "</think>" && msg.type === "AIMessageChunk") {
      // Putting thinking process in a separate step
      state.appendContentToLastMsg(msg.content);
      state.appendStepToLastMsg("💭 Thought process", metadata.langgraph_node, [], state.lastMsg().content());
      state.lastMsg().setContent("");
    } else if (msg.content && msg.type === "AIMessageChunk") {
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
  const query = extractSparqlQuery(state.lastMsg().content());
  if (query) state.lastMsg().setLinks([{url: query, ...queryLinkLabels}]);
  // } else {
  //   // When not streaming, await full response with additional checks done on the server
  //   try {
  //     const data = await response.json();
  //     console.log("Complete response", data);
  //     const respMsg = data.choices[0].message.content;
  //     appendMessage(respMsg, "assistant");
  //     setWarningMsg("");
  //   } catch (error) {
  //     console.error("Error getting API response", error, response);
  //     setWarningMsg("An error occurred. Please try again.");
  //   }
  // }
}

// async function streamLangServe(state: ChatState) {
//   // TODO: Query LangGraph through LangServe API
//   const remoteChain = new RemoteRunnable({
//     url: state.apiUrl,
//   });
//   const stream = await remoteChain.stream({
//     // messages: [{role: "human", content: state.lastMsg().content()}],
//     messages: state.messages().map(({content, role}) => ({content: content(), role})),
//   });
//   for await (const chunk of stream) {
//     console.log(chunk);
//   }
// }
