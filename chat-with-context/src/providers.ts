import {Accessor, createSignal, Setter} from "solid-js";
import {Client} from "@langchain/langgraph-sdk";
import {RemoteRunnable} from "@langchain/core/runnables/remote";
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
  messages: Accessor<Message[]>;
  setMessages: Setter<Message[]>;
  abortController: AbortController;

  constructor({apiUrl, apiKey}: {
    apiUrl: string;
    apiKey: string;
  }) {
    this.apiUrl = apiUrl.endsWith("/") ? apiUrl : apiUrl + "/";
    this.apiKey = apiKey;

    const [messages, setMessages] = createSignal<Message[]>([]);
    this.messages = messages;
    this.setMessages = setMessages;
    this.abortController = new AbortController();
  }

  abortRequest = () => {
    this.abortController.abort();
    this.abortController = new AbortController();
  }

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
  if (state.apiUrl.endsWith(":2024/") || state.apiUrl.endsWith(":8123/") || state.apiUrl.endsWith("/langgraph/")) {
    // Query LangGraph API
    await streamLangGraphApi(state);

  } else if (state.apiUrl.endsWith("/langgraph")) {
    // Query LangGraph through LangServe API
    await streamLangServe(state);

  } else {
    // Query the OpenAI-compatible chat API
    await streamOpenAILikeApi(state);
  }
}

async function streamLangServe(state: ChatState) {
  // TODO: Query LangGraph through LangServe API
  const remoteChain = new RemoteRunnable({
    url: state.apiUrl,
  });
  const stream = await remoteChain.stream({
    // messages: [{role: "human", content: state.lastMsg().content()}],
    messages: state.messages().map(({content, role}) => ({content: content(), role})),
  });
  for await (const chunk of stream) {
    console.log(chunk);
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
    // console.log(chunk.event, chunk);
    if (chunk.event === "updates") {
      // Handle updates to the state
      if (chunk.data.retrieve?.retrieved_docs) {
        // Retrieved docs sent
        state.appendStepToLastMsg(
          `📚️ Using ${chunk.data.retrieve.retrieved_docs.length} documents`,
          "retrieve",
          chunk.data.retrieve.retrieved_docs,
        );
      }
      if (chunk.data.validate_output?.extracted_entities) {
        const extractedEntities = chunk.data.validate_output?.extracted_entities;
        // Retrieved extracted_entities sent
        if (extractedEntities.sparql_query) {
          state.lastMsg().setLinks([
            {
              url: getEditorUrl(extractedEntities.sparql_query, extractedEntities.sparql_endpoint_url),
              ...queryLinkLabels,
            },
          ]);
        }
      }
    }
    if (chunk.event === "messages") {
      // Handle messages from the model
      const [msg, metadata] = chunk.data;
      // console.log("MESSAGES", msg, metadata);
      if (msg.tool_calls?.length > 0) {
        // Tools calls requested by the model
        const toolNames = msg.tool_calls.map((tool_call: any) => tool_call.name).join(", ");
        if (toolNames) state.appendStepToLastMsg(`💭 Calling tools: ${toolNames}`, metadata.langgraph_node);
      }
      if (msg.content && msg.type === "tool") {
        // Response from a tool
        state.appendStepToLastMsg(`🔧 Tool ${msg.name} result: ${msg.content}`, metadata.langgraph_node);
      } else if (msg.content && msg.type === "AIMessageChunk") {
        // Response from the model
        state.appendContentToLastMsg(msg.content);
      }

      if (msg.name) {
        // Handle messages related to validation
        const originalContent = state.lastMsg().content();
        if (msg.name.startsWith("fix-")) {
          // If the update contains a message with a fix (e.g. done during post generation validation)
          const msgName = msg.name.slice(4);
          state.appendStepToLastMsg(
            `✅ Fixed the generated SPARQL query automatically (${msgName})`,
            "validate_output",
            [],
            `${msgName[0].toUpperCase() + msgName.slice(1)} corrected from the query generated in the original response.\n\n## Original response\n\n${originalContent}`,
          );
          state.lastMsg().setContent(msg.content);
        }
        if (msg.name === "recall-model") {
          // If the update contains a message with a fix (e.g. done during post generation validation)
          state.appendStepToLastMsg(
            `🐞 Generated query invalid, fixing it`,
            "validate_output",
            [],
            `The query generated in the original response is not valid according to the endpoints schema.\n\n## Original response\n\n${originalContent}\n\n## Validation results\n\n${msg.additional_kwargs?.validation_results}`,
          );
          state.lastMsg().setContent("");
        }
      }
    }
    if (chunk.event === "error") {
      throw new Error(`An error occurred. Please try again. ${chunk.data.error}: ${chunk.data.message}`);
    }
  }
}

async function streamOpenAILikeApi(state: ChatState) {
  const response = await fetch(`${state.apiUrl}chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    signal: state.abortController.signal,
    body: JSON.stringify({
      messages: state.messages().map(({content, role}) => ({content: content(), role})),
      model: "gpt-4o-mini",
      // model: "azure_ai/mistral-large",
      max_tokens: 500,
      stream: true,
      api_key: state.apiKey,
    }),
  });

  // TODO: try this way of streaming: https://github.com/vercel/ai/blob/main/packages/ui-utils/src/process-text-stream.ts#L1

  // Handle response differently if streaming or not
  // if (streamResponse) {
  // for await (const chunk of response.body) {
  //   // if (signal.aborted) break; // just break out of loop
  //   // Do something with the chunk
  //   console.log(chunk)
  // }

  state.appendMessage("", "assistant");
  const reader = response.body?.getReader()!;
  const decoder = new TextDecoder("utf-8");
  let partialLine = ""; // Buffer for incomplete lines

  // Iterate stream response
  while (true) {
    if (reader) {
      const {value, done} = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, {stream: true});
      // Combine with any leftover data from the previous iteration
      const combined = partialLine + chunk;
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
                console.log(newContent);
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

  // https://developer.mozilla.org/en-US/docs/Web/API/Streams_API/Using_readable_streams
  // if (reader) {
  //   const readableStream = new ReadableStream({
  //     start(controller) {
  //         async function pump() {
  //             while (true) {
  //                 const { done, value } = await reader.read();
  //                 if (done) {
  //                     controller.close();
  //                     break;
  //                 }
  //                 // const chunk = decoder.decode(value, { stream: true });
  //                 controller.enqueue(decoder.decode(value, { stream: true }));
  //             }
  //         }
  //         pump();
  //     },
  //   });
  //   for await (const chunk of readableStream) {
  //     const combined = partialLine + chunk;
  //     if (partialLine) partialLine = "";
  //     // Combine with any leftover data from the previous iteration
  //     for (const line of combined.split("\n").filter(line => line.trim() !== "")) {
  //       if (line === "data: [DONE]") return;
  //       if (line.startsWith("data: ")) {
  //         // console.log(line)
  //         try {
  //           const json = JSON.parse(line.substring(6));
  //           if (json.retrieved_docs) {
  //             appendStepToLastMsg(`📚️ Using ${json.retrieved_docs.length} documents`, "retrieve", json.retrieved_docs);
  //           } else {
  //             const newContent = json.choices[0].delta?.content;
  //             if (newContent) {
  //               // console.log(newContent);
  //               appendContentToLastMsg(newContent);
  //             }
  //           }
  //         } catch {
  //           partialLine = line;
  //           console.log("Partial line", partialLine);
  //         }
  //       }
  //     }
  //   }
  // }

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
