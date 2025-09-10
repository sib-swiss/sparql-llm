import {Accessor, createSignal, Setter} from "solid-js";

import {getEditorUrl, queryLinkLabels} from "./utils";

type Links = {
  url: string;
  label: string;
  title: string;
};

type Step = {
  node_id: string;
  label: string;
  details: string; // Details about the step as markdown string
  substeps?: {label: string; details: string}[];
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
  onMessageUpdate: () => void;
  currentTool: any;

  constructor({apiUrl = "", apiKey = "", model = ""}: {apiUrl?: string; apiKey?: string; model?: string}) {
    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
    this.model = model;

    const [messages, setMessages] = createSignal<Message[]>([]);
    this.messages = messages;
    this.setMessages = setMessages;
    this.abortController = new AbortController();
    this.onMessageUpdate = () => {};
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
    this.onMessageUpdate();
  };

  appendStepToLastMsg = (
    node_id: string,
    label: string,
    details: string = "",
    substeps: {label: string; details: string}[] = [],
  ) => {
    this.lastMsg().setSteps(steps => [...steps, {node_id, label, details, substeps}]);
    this.scrollToInput();
    this.onMessageUpdate();
    // this.inputTextEl.scrollIntoView({behavior: "smooth"});
  };
}

// Stream a response from various LLM agent providers (OpenAI-like, LangGraph, LangServe)
export async function streamResponse(state: ChatState, question: string) {
  state.appendMessage(question, "user");
  // Query LangGraph through our custom API
  // await streamCustomLangGraph(state);
  await streamCustomMcp(state);
  // if (state.apiUrl.endsWith(":2024/") || state.apiUrl.endsWith(":8123/")) {
  //   // Query LangGraph API
  //   await streamLangGraphApi(state);
  // } else if (state.apiUrl.endsWith("/completions/")) {
  //   // Query the OpenAI-compatible chat API
  //   await streamOpenAILikeApi(state);
  // } else {
  //   // Query LangGraph through our custom API
  //   await streamCustomLangGraph(state);
  // }
}

async function streamCustomMcp(state: ChatState) {
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
  let buffer = "";
  let currentEvent: string | null = null;
  // Iterate stream response
  while (true) {
    if (reader) {
      const {value, done} = await reader.read();
      if (done) break;
      const chunkStr = decoder.decode(value, {stream: true});
      buffer += chunkStr;
      let lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines.filter(line => line.trim() !== "")) {
        if (line === "data: [DONE]") return;
        if (line.startsWith("event: ")) {
          currentEvent = line.substring(7).trim();
        } else if (line.startsWith("data: ")) {
          try {
            const dataStr = line.substring(6);
            let data;
            // Try to parse JSON, fallback to string if not JSON
            try {
              data = JSON.parse(dataStr);
            } catch {
              data = dataStr;
            }
            if (currentEvent) {
              processMcpChunk(state, {event: currentEvent, data});
              currentEvent = null;
            } else {
              // fallback for legacy format
              processMcpChunk(state, data);
            }
          } catch (e) {
            console.log("Error parsing line", e, line);
          }
        }
      }
    }
  }
}

async function processMcpChunk(state: ChatState, chunk: any) {
  console.log("processLangGraphChunk", chunk);
  if (chunk.event === "error") {
    throw new Error(`An error occurred. Please try again. ${chunk.data.error}: ${chunk.data.message}`);
  }
  // console.log(chunk);
  // Handle updates to the state (nodes that are retrieving stuff without querying the LLM usually)
  if (chunk.event === "updates") {
    for (const nodeId of Object.keys(chunk.data)) {
      const nodeData = chunk.data[nodeId];
      if (!nodeData) continue;
      if (nodeData.steps) {
        for (const step of nodeData.steps) {
          if (step.type === "recall") {
            state.appendMessage("", "assistant");
          } else if (step.fixed_message) {
            state.lastMsg().setContent(step.fixed_message);
          }
          state.appendStepToLastMsg(nodeId, step.label, step.details, step.substeps);
        }
      }
      if (nodeData.structured_output) {
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
  // Handle tool_call_requested event
  if (chunk.event === "tool_call_requested") {
    // console.log("TOOL CALL REQUESTED", chunk.data);
    // chunk.data is an array of tool calls
    for (const toolCall of chunk.data) {
      // const label = `🔧 Tool call requested: ${toolCall.function?.name || toolCall.type}`;
      // const details = toolCall.function?.arguments || JSON.stringify(toolCall);
      // state.appendMessage("", "assistant");
      // state.appendStepToLastMsg(toolCall.id || "tool_call", label, `\`\`\`json\n${details}\n\`\`\``);
      state.currentTool = toolCall;
      // TODO: does not work with results if multiple tool calls are requested
    }
  }
  // Handle tool_call_results event
  if (chunk.event === "tool_call_results") {
    // chunk.data contains results, query, etc.
    console.log("TOOL CALL RESULTS", chunk.data);
    let label = state.currentTool.function?.name.replaceAll("_", " ").replace(/^\w/, (c: string) => c.toUpperCase()) || "Tool call";
    if (chunk.data.total_found) {
      label += ` (${chunk.data.total_found})`;
    }
    let details = `## Tool call\n\n\`\`\`json\n${state.currentTool.function?.arguments || JSON.stringify(state.currentTool)}\n\`\`\`\n\n`;
    details += chunk.data.results ? `## Results\n\n\`\`\`json\n${JSON.stringify(chunk.data.results, null, 2)}\n\`\`\`` : JSON.stringify(chunk.data);
    state.appendMessage("", "assistant");
    state.appendStepToLastMsg("tool_call_results", label, details);
  }
  console.log("CHUNK", chunk.event, chunk);
  // Handle messages from the model
  if (chunk.event === "message") {
    const msg = chunk.data;
    // if (metadata.structured_output_format) return;
    // console.log("MESSAGES", msg, metadata);
    // if (msg.tool_calls?.length > 0) {
    //   // Tools calls requested by the model
    //   const toolNames = msg.tool_calls.map((tool_call: any) => tool_call.name).join(", ");
    //   if (toolNames) state.appendStepToLastMsg(metadata.langgraph_node, `🔧 Calling tool ${toolNames}`);
    //   console.log("TOOL call", msg, metadata);
    // }
    if (msg.content && msg.type === "tool") {
      // If tool called by model
      // console.log("TOOL res", msg, metadata);
      const name = msg.name ? msg.name.replace(/_/g, " ").replace(/^\w/, (c: string) => c.toUpperCase()) : "Tool";
      const icon = msg.name.includes("resources") ? "📚" : msg.name.includes("execute") ? "📡" : "🔧";
      state.appendMessage("", "assistant");
      state.appendStepToLastMsg("", `${icon} ${name}`, msg.content);
    } else if (msg.content === "</think>" && msg.type === "AIMessageChunk") {
      // Putting thinking process in a separate step
      state.appendContentToLastMsg(msg.content);
      state.appendStepToLastMsg("", "💭 Thought process", state.lastMsg().content());
      state.lastMsg().setContent("");
    } else {
      // This will only stream response from the langgraph node "call_model"
      // console.log("AIMessageChunk", msg, metadata);
      state.appendContentToLastMsg(msg.choices[0]?.delta?.content);
    }
  }
}


// async function processLangGraphChunk(state: ChatState, chunk: any) {
//   console.log("processLangGraphChunk", chunk);
//   if (chunk.event === "error") {
//     throw new Error(`An error occurred. Please try again. ${chunk.data.error}: ${chunk.data.message}`);
//   }
//   // console.log(chunk);
//   // Handle updates to the state (nodes that are retrieving stuff without querying the LLM usually)
//   if (chunk.event === "updates") {
//     // console.log("UPDATES", chunk);
//     for (const nodeId of Object.keys(chunk.data)) {
//       const nodeData = chunk.data[nodeId];
//       if (!nodeData) continue;
//       if (nodeData.steps) {
//         // Handle most generic steps output sent by the agent
//         for (const step of nodeData.steps) {
//           // console.log("STEP", step);
//           // Handle step specific to post-generation validation
//           if (step.type === "recall") {
//             // When `recall` is called, the model will re-generate the response, so we create a new message
//             // state.lastMsg().setContent("");
//             state.appendMessage("", "assistant");
//           } else if (step.fixed_message) {
//             // If the update contains a message with a fix
//             state.lastMsg().setContent(step.fixed_message);
//           }
//           state.appendStepToLastMsg(nodeId, step.label, step.details, step.substeps);
//         }
//       }
//       if (nodeData.structured_output) {
//         // Special case to handle things extracted from output
//         // Here we add links to open the SPARQL query in an editor
//         if (nodeData.structured_output.sparql_query) {
//           state.lastMsg().setLinks([
//             {
//               url: getEditorUrl(
//                 nodeData.structured_output.sparql_query,
//                 nodeData.structured_output.sparql_endpoint_url,
//               ),
//               ...queryLinkLabels,
//             },
//           ]);
//         }
//       }
//     }
//   }
//   console.log("CHUNK", chunk.event, chunk);
//   // Handle messages from the model
//   if (chunk.event === "message") {
//     const [msg, metadata] = chunk.data;
//     if (metadata.structured_output_format) return;
//     // console.log("MESSAGES", msg, metadata);
//     // if (msg.tool_calls?.length > 0) {
//     //   // Tools calls requested by the model
//     //   const toolNames = msg.tool_calls.map((tool_call: any) => tool_call.name).join(", ");
//     //   if (toolNames) state.appendStepToLastMsg(metadata.langgraph_node, `🔧 Calling tool ${toolNames}`);
//     //   console.log("TOOL call", msg, metadata);
//     // }
//     if (msg.content && msg.type === "tool") {
//       // If tool called by model
//       // console.log("TOOL res", msg, metadata);
//       const name = msg.name ? msg.name.replace(/_/g, " ").replace(/^\w/, (c: string) => c.toUpperCase()) : "Tool";
//       const icon = msg.name.includes("resources") ? "📚" : msg.name.includes("execute") ? "📡" : "🔧";
//       state.appendMessage("", "assistant");
//       state.appendStepToLastMsg(metadata.langgraph_node, `${icon} ${name}`, msg.content);
//     } else if (msg.content === "</think>" && msg.type === "AIMessageChunk") {
//       // Putting thinking process in a separate step
//       state.appendContentToLastMsg(msg.content);
//       state.appendStepToLastMsg(metadata.langgraph_node, "💭 Thought process", state.lastMsg().content());
//       state.lastMsg().setContent("");
//     } else if (msg.content && msg.type === "AIMessageChunk" && metadata.langgraph_node === "call_model") {
//       // This will only stream response from the langgraph node "call_model"
//       // console.log("AIMessageChunk", msg, metadata);
//       state.appendContentToLastMsg(msg.content);
//     }
//   }
// }

// async function streamCustomLangGraph(state: ChatState) {
//   const response = await fetch(`${state.apiUrl}`, {
//     method: "POST",
//     headers: {
//       "Content-Type": "application/json",
//       Authorization: `Bearer ${state.apiKey}`,
//     },
//     signal: state.abortController.signal,
//     body: JSON.stringify({
//       messages: state.messages().map(({content, role}) => ({content: content(), role})),
//       stream: true,
//       ...(state.model ? {model: state.model} : {}),
//     }),
//   });

//   state.appendMessage("", "assistant");
//   const reader = response.body?.getReader()!;
//   const decoder = new TextDecoder("utf-8");
//   let buffer = ""; // Buffer for incomplete chunks
//   // Iterate stream response
//   while (true) {
//     if (reader) {
//       const {value, done} = await reader.read();
//       if (done) break;
//       const chunkStr = decoder.decode(value, {stream: true});
//       buffer += chunkStr;
//       let lines = buffer.split("\n");
//       // Keep the last line if it's incomplete
//       buffer = lines.pop() || "";
//       for (const line of lines.filter(line => line.trim() !== "")) {
//         if (line === "data: [DONE]") return;
//         if (line.startsWith("data: ")) {
//           try {
//             const json = JSON.parse(line.substring(6));
//             processLangGraphChunk(state, json);
//           } catch (e) {
//             console.log("Error parsing line", e, line);
//           }
//         }
//       }
//     }
//   }
// }


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

// // NOTE: experimental, kept for reference, would need to be updated to properly uses steps output
// import {Client} from "@langchain/langgraph-sdk";
// import { RemoteGraph } from "@langchain/langgraph/remote";
// import { isAIMessageChunk } from "@langchain/core/messages";
// async function streamLangGraphApi(state: ChatState) {
//   const client = new Client({apiUrl: state.apiUrl});
//   const graphName = "agent";

//   // https://langchain-ai.github.io/langgraphjs/how-tos/stream-tokens
//   // https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_messages
//   // https://langchain-ai.github.io/langgraph/concepts/streaming/
//   const thread = await client.threads.create();
//   const streamResponse = client.runs.stream(thread["thread_id"], graphName, {
//     // input: {messages: [{role: "human", content: "what is 3 times 6?"}]},
//     // input: {messages: [{role: "human", content: question}]},
//     input: {messages: state.messages().map(({content, role}) => ({content: content(), role}))},
//     config: {configurable: {}},
//     streamMode: ["messages-tuple", "updates"],
//     signal: state.abortController.signal,
//   });
//   state.appendMessage("", "assistant");
//   for await (const chunk of streamResponse) {
//     processLangGraphChunk(state, chunk);
//   }
// }

// async function streamOpenAILikeApi(state: ChatState) {
//   // Experimental, would need to be updated to properly uses steps output
//   const response = await fetch(`${state.apiUrl}chat/completions`, {
//     method: "POST",
//     headers: {
//       "Content-Type": "application/json",
//       Authorization: `Bearer ${state.apiKey}`,
//     },
//     signal: state.abortController.signal,
//     body: JSON.stringify({
//       messages: state.messages().map(({content, role}) => ({content: content(), role})),
//       model: state.model,
//       // model: "azure_ai/mistral-large",
//       max_tokens: 500,
//       stream: true,
//       // api_key: state.apiKey,
//     }),
//   });

//   state.appendMessage("", "assistant");
//   const reader = response.body?.getReader()!;
//   const decoder = new TextDecoder("utf-8");
//   let partialLine = ""; // Buffer for incomplete lines

//   // Iterate stream response
//   while (true) {
//     if (reader) {
//       const {value, done} = await reader.read();
//       if (done) break;
//       const chunkStr = decoder.decode(value, {stream: true});
//       // Combine with any leftover data from the previous iteration
//       const combined = partialLine + chunkStr;
//       if (partialLine) partialLine = "";
//       for (const line of combined.split("\n").filter(line => line.trim() !== "")) {
//         if (line === "data: [DONE]") return;
//         if (line.startsWith("data: ")) {
//           // console.log(line)
//           try {
//             const json = JSON.parse(line.substring(6));
//             if (json.retrieved_docs) {
//               state.appendStepToLastMsg(
//                 `📚️ Using ${json.retrieved_docs.length} documents`,
//                 "retrieve",
//                 json.retrieved_docs,
//               );
//             } else {
//               const newContent = json.choices[0].delta?.content;
//               if (newContent) {
//                 // console.log(newContent);
//                 state.appendContentToLastMsg(newContent);
//               }
//             }
//           } catch {
//             partialLine = line;
//           }
//         }
//       }
//     }
//   }

//   // Extract query once message complete
//   // const query = extractSparqlQuery(state.lastMsg().content());
//   // if (query) state.lastMsg().setLinks([{url: query, ...queryLinkLabels}]);
// }
