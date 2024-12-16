import {createSignal, For, createEffect, Accessor, Setter} from "solid-js";
import {customElement, noShadowDOM} from "solid-element";
import {marked} from "marked";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
import "highlight.js/styles/default.min.css";
import feather from "feather-icons";

import {extractSparqlQuery, getLangForDocType, style} from "./utils";
import {hljsDefineSparql, hljsDefineTurtle} from "./highlight";
import "./style.css";

// https://github.com/solidjs/solid/blob/main/packages/solid-element/README.md
// https://github.com/solidjs/templates/tree/main/ts-tailwindcss

type GenContext = {
  score: number;
  payload: {
    doc_type: string;
    endpoint_url: string;
    question: string;
    answer: string;
  };
};

type Links = {
  url: string;
  label: string;
  title: string;
};

type Message = {
  role: "assistant" | "user";
  content: Accessor<string>;
  setContent: Setter<string>;
  sources: GenContext[];
  links: Accessor<Links[]>;
  setLinks: Setter<Links[]>;
};

const queryLinkLabels = {label: "Run and edit the query", title: "Open the SPARQL query in an editor in a new tab"};

/**
 * Custom element to create a chat interface with a context-aware assistant.
 * @example <chat-with-context api="http://localhost:8000/"></chat-with-context>
 */
customElement("chat-with-context", {api: "", examples: "", apiKey: ""}, props => {
  noShadowDOM();
  hljs.registerLanguage("ttl", hljsDefineTurtle);
  hljs.registerLanguage("sparql", hljsDefineSparql);

  const [messages, setMessages] = createSignal<Message[]>([]);
  const [warningMsg, setWarningMsg] = createSignal("");
  const [loading, setLoading] = createSignal(false);
  const [feedbackSent, setFeedbackSent] = createSignal(false);

  const apiUrl = props.api.endsWith("/") ? props.api : props.api + "/";
  if (props.api === "") setWarningMsg("Please provide an API URL for the chat component to work.");
  const examples = props.examples.split(",").map(value => value.trim());

  createEffect(() => {
    feather.replace();
    fixInputHeight();
  });
  let chatContainerEl!: HTMLDivElement;
  let inputTextEl!: HTMLTextAreaElement;

  // NOTE: the 2 works but for now we want to always run validation
  const streamResponse = false;

  const appendMessage = (msgContent: string, role: "assistant" | "user" = "assistant", sources: GenContext[] = []) => {
    const [content, setContent] = createSignal(msgContent);
    const [links, setLinks] = createSignal<Links[]>([]);
    const newMsg: Message = {content, setContent, role, sources, links, setLinks};
    const query = extractSparqlQuery(msgContent);
    if (query) newMsg.setLinks([{url: query, ...queryLinkLabels}]);
    setMessages(messages => [...messages, newMsg]);
    feather.replace();
  };

  const highlightAll = () => {
    document.querySelectorAll("pre code:not(.hljs)").forEach(block => {
      hljs.highlightElement(block as HTMLElement);
    });
  };

  // Send the user input to the chat API
  async function submitInput(question: string) {
    if (!question.trim()) return;
    if (loading()) {
      setWarningMsg("⏳ Thinking...");
      return;
    }
    inputTextEl.value = "";
    setLoading(true);
    appendMessage(question, "user");
    setTimeout(() => fixInputHeight(), 0);
    try {
      const response = await fetch(`${apiUrl}chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // 'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          messages: messages().map(({content, role}) => ({content: content(), role})),
          model: "gpt-4o",
          max_tokens: 50,
          stream: streamResponse,
          api_key: props.apiKey,
        }),
      });

      // Handle response differently if streaming or not
      if (streamResponse) {
        const reader = response.body?.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        console.log(reader);
        // Iterate stream response
        while (true) {
          if (reader) {
            const {value, done} = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, {stream: true});
            let boundary = buffer.lastIndexOf("\n");
            if (boundary !== -1) {
              const chunk = buffer.slice(0, boundary);
              buffer = buffer.slice(boundary + 1);

              const lines = chunk.split("\n").filter(line => line.trim() !== "");
              for (const line of lines) {
                if (line === "data: [DONE]") {
                  return;
                }
                if (line.startsWith("data: ")) {
                  // console.log(line)
                  try {
                    const json = JSON.parse(line.substring(6));
                    if (json.docs) {
                      // Docs always come before the message
                      appendMessage("", "assistant", json.docs);
                    } else {
                      const newContent = json.choices[0].delta?.content;
                      if (newContent) {
                        messages()[messages().length - 1].setContent(content => content + newContent);
                      }
                    }
                  } catch (error) {
                    console.warn("Failed to parse JSON", error);
                    setWarningMsg("An error occurred. Please try again.");
                  }
                }
              }
            }
          }
        }
        const lastMsg = messages()[messages().length - 1];
        // Process any remaining data in the buffer
        if (buffer.length > 0) {
          try {
            const json = JSON.parse(buffer.substring(6));
            const newContent = json.choices[0].delta?.content;
            if (newContent) {
              lastMsg.setContent(content => content + newContent);
            }
            setWarningMsg("");
          } catch (error) {
            console.warn("Failed to parse remaining JSON", error);
            setWarningMsg("An error occurred. Please try again.");
          }
        }
        // Extract query once message complete
        const query = extractSparqlQuery(lastMsg.content());
        console.log(query);
        if (query) lastMsg.setLinks([{url: query, ...queryLinkLabels}]);
      } else {
        // Don't stream, await full response with additional checks done on the server
        try {
          const data = await response.json();
          console.log("Complete response", data);
          const respMsg = data.choices[0].message.content;
          appendMessage(respMsg, "assistant", data.docs);
          setWarningMsg("");
        } catch (error) {
          console.error("Error getting API response", error, response);
          setWarningMsg("An error occurred. Please try again.");
        }
      }
    } catch (error) {
      console.error("Failed to send message", error);
      setWarningMsg("An error occurred when querying the API. Please try again or contact an admin.");
    }
    setLoading(false);
    setFeedbackSent(false);
    highlightAll();
    feather.replace();
    inputTextEl.scrollIntoView({behavior: "smooth"});
  }

  function sendFeedback(positive: boolean) {
    fetch(`${apiUrl}feedback`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        like: positive,
        messages: messages(),
      }),
    });
    setFeedbackSent(true);
  }

  // Fix input height to fit content
  function fixInputHeight() {
    inputTextEl.style.height = "auto";
    inputTextEl.style.height = inputTextEl.scrollHeight + "px";
  }

  return (
    <div class={`chat-with-context w-full h-full flex flex-col ${messages().length === 0 ? "justify-center" : ""}`}>
      <style>{style}</style>
      {/* Main chat container */}
      <div ref={chatContainerEl} class={`overflow-y-auto ${messages().length !== 0 ? "flex-grow" : ""}`}>
        <For each={messages()}>
          {(msg, iMsg) => (
            <div class={`w-full flex flex-col flex-grow ${msg.role === "user" ? "items-end" : ""}`}>
              <div class={`py-2.5 mb-2 ${msg.role === "user" ? "bg-gray-300 rounded-3xl px-5" : ""}`}>
                <article
                  class="prose max-w-full"
                  // eslint-disable-next-line solid/no-innerhtml
                  innerHTML={DOMPurify.sanitize(marked.parse(msg.content()) as string)}
                />

                {/* Add sources references dialog */}
                {msg.sources.length > 0 && (
                  <>
                    <button
                      class="my-3 mr-1 px-3 py-1 text-sm bg-gray-300 dark:bg-gray-700 rounded-3xl align-middle"
                      title="See the documents used to generate the response"
                      onClick={() => {
                        (document.getElementById(`source-dialog-${iMsg()}`) as HTMLDialogElement).showModal();
                        highlightAll();
                      }}
                    >
                      See relevant references
                    </button>
                    <dialog
                      id={`source-dialog-${iMsg()}`}
                      class="bg-white dark:bg-gray-800 m-3 rounded-3xl shadow-md w-full"
                    >
                      <button
                        id={`close-dialog-${iMsg()}`}
                        class="fixed top-2 right-8 m-3 px-2 text-xl text-slate-500 bg-gray-200 dark:bg-gray-700 rounded-3xl"
                        title="Close references"
                        onClick={() =>
                          (document.getElementById(`source-dialog-${iMsg()}`) as HTMLDialogElement).close()
                        }
                      >
                        <i data-feather="x" />
                      </button>
                      <article class="prose max-w-full p-3">
                        <For each={msg.sources}>
                          {(source, iSource) => (
                            <>
                              <p>
                                <code class="mr-1">
                                  {iSource() + 1} - {Math.round(source.score * 1000) / 1000}
                                </code>
                                {source.payload.question} (
                                <a href={source.payload.endpoint_url} target="_blank">
                                  {source.payload.endpoint_url}
                                </a>
                                )
                              </p>
                              {getLangForDocType(source.payload.doc_type).startsWith("language-") ? (
                                <pre>
                                  <code class={`${getLangForDocType(source.payload.doc_type)}`}>
                                    {source.payload.answer}
                                  </code>
                                </pre>
                              ) : (
                                <p>{source.payload.answer}</p>
                              )}
                            </>
                          )}
                        </For>
                      </article>
                    </dialog>
                  </>
                )}
                {/* Add links, e.g. to Run and edit the query */}
                <For each={msg.links()}>
                  {link => (
                    <a href={link.url} title={link.title} target="_blank" class="hover:text-inherit">
                      <button class="my-3 mr-1 px-3 py-1 text-sm bg-gray-300 dark:bg-gray-700 rounded-3xl align-middle">
                        {link.label}
                      </button>
                    </a>
                  )}
                </For>
                {/* Show feedback buttons only for last message */}
                {msg.role === "assistant" && iMsg() === messages().length - 1 && !feedbackSent() && (
                  <>
                    <button
                      class="mr-1 my-3 px-3 py-1 text-sm hover:bg-gray-300 dark:hover:bg-gray-800 rounded-3xl align-middle"
                      title="Report a good response"
                      onClick={() => sendFeedback(true)}
                    >
                      {/* @ts-ignore */}
                      <i height="20px" width="20px" class="text-sm align-middle" data-feather="thumbs-up" />
                    </button>
                    <button
                      class="my-3 px-3 py-1 text-sm hover:bg-gray-300 dark:hover:bg-gray-800 rounded-3xl align-middle"
                      title="Report a bad response"
                      onClick={() => sendFeedback(false)}
                    >
                      {/* @ts-ignore */}
                      <i height="20px" width="20px" data-feather="thumbs-down" />
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </For>
      </div>

      {/* Warning message */}
      {warningMsg() && (
        <div class="text-center">
          <div class="bg-orange-300 p-2 text-orange-900 text-sm rounded-3xl font-semibold mb-2 inline-block">
            {warningMsg()}
          </div>
        </div>
      )}

      {/* List of examples */}
      {messages().length < 1 && (
        <div class="py-2 px-4 justify-center items-center text-sm flex flex-col space-y-2">
          <For each={examples}>
            {example => (
              <button onClick={() => submitInput(example)} class="px-5 py-2.5 bg-slate-200 text-slate-600 rounded-3xl">
                {example}
              </button>
            )}
          </For>
        </div>
      )}

      {/* Input text box */}
      <form
        class="p-2 flex"
        onSubmit={event => {
          event.preventDefault();
          submitInput(inputTextEl.value);
        }}
      >
        <div class="container flex mx-auto max-w-5xl">
          <textarea
            ref={inputTextEl}
            autofocus
            class="flex-grow px-4 py-2 h-auto border border-slate-400 bg-slate-200 dark:bg-slate-700 dark:border-slate-500 rounded-3xl focus:outline-none focus:ring focus:ring-blue-200 dark:focus:ring-blue-400 overflow-y-hidden resize-none"
            placeholder="Ask Expasy..."
            rows="1"
            onKeyDown={event => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submitInput(inputTextEl.value);
              }
            }}
            onInput={() => fixInputHeight()}
          />
          <button
            type="submit"
            title={loading() ? "Loading..." : "Send question"}
            class="ml-2 px-4 py-2 rounded-3xl text-slate-500 bg-slate-200 dark:text-slate-400 dark:bg-slate-700 "
            disabled={loading()}
          >
            {loading() ? <i data-feather="loader" class="animate-spin" /> : <i data-feather="send" />}
          </button>
          <button
            title="Start a new conversation"
            class="ml-2 px-4 py-2 rounded-3xl text-slate-500 bg-slate-200 dark:text-slate-400 dark:bg-slate-700"
            onClick={() => setMessages([])}
          >
            <i data-feather="trash" />
          </button>
          {/* <div
            class="ml-4 tooltip-top"
            title="⚠️ Will check if the queries sent are valid SPARQL, no streaming response, slower"
          >
            <input type="checkbox" id="checks-checkbox" class="mr-2" />
            <label for="checks-checkbox">Run additional checks</label>
          </div> */}
        </div>
      </form>
    </div>
  );
});
