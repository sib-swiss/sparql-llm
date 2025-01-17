import {createSignal, For, createEffect} from "solid-js";
import {customElement, noShadowDOM} from "solid-element";
import {marked} from "marked";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
import "highlight.js/styles/default.min.css";

import {getLangForDocType, style} from "./utils";
import {hljsDefineSparql, hljsDefineTurtle} from "./highlight";
import sendLogo from "./assets/send.svg";
import xLogo from "./assets/x.svg";
import editLogo from "./assets/edit.svg";
import squareLogo from "./assets/square.svg";
import thumbsDownLogo from "./assets/thumbs-down.svg";
import thumbsUpLogo from "./assets/thumbs-up.svg";
import "./style.css";
import {streamResponse, ChatState} from "./providers";

// Get icons svg from https://feathericons.com/
// SolidJS custom element: https://github.com/solidjs/solid/blob/main/packages/solid-element/README.md
// https://github.com/solidjs/templates/tree/main/ts-tailwindcss

/**
 * Custom element to create a chat interface with a context-aware assistant.
 * @example <chat-with-context api="http://localhost:8000/"></chat-with-context>
 */
customElement("chat-with-context", {chatEndpoint: "", examples: "", apiKey: "", feedbackEndpoint: ""}, props => {
  noShadowDOM();
  hljs.registerLanguage("ttl", hljsDefineTurtle);
  hljs.registerLanguage("sparql", hljsDefineSparql);

  const [warningMsg, setWarningMsg] = createSignal("");
  const [loading, setLoading] = createSignal(false);
  const [feedbackSent, setFeedbackSent] = createSignal(false);
  const [selectedTab, setSelectedTab] = createSignal("");

  const [feedbackEndpoint, setFeedbackEndpoint] = createSignal("");

  const state = new ChatState({
    // eslint-disable-next-line solid/reactivity
    apiUrl: props.chatEndpoint,
    // eslint-disable-next-line solid/reactivity
    apiKey: props.apiKey,
    model: "gpt-4o-mini",
  });
  let chatContainerEl!: HTMLDivElement;
  let inputTextEl!: HTMLTextAreaElement;
  // eslint-disable-next-line solid/reactivity
  const examples = props.examples.split(",").map(value => value.trim());

  createEffect(() => {
    if (props.chatEndpoint === "") setWarningMsg("Please provide an API URL for the chat component to work.");

    state.scrollToInput = () => inputTextEl.scrollIntoView({behavior: "smooth"});
    fixInputHeight();

    setFeedbackEndpoint(props.feedbackEndpoint);
    // setFeedbackEndpoint(props.feedbackEndpoint.endsWith("/") ? props.feedbackEndpoint : props.feedbackEndpoint + "/");
  });

  const highlightAll = () => {
    document.querySelectorAll("pre code:not(.hljs)").forEach(block => {
      hljs.highlightElement(block as HTMLElement);
    });
  };

  // Send the user input to the chat API
  async function submitInput(question: string) {
    if (!question.trim()) return;
    if (loading()) {
      // setWarningMsg("⏳ Thinking...");
      return;
    }
    inputTextEl.value = "";
    setLoading(true);
    setWarningMsg("");
    setTimeout(() => fixInputHeight(), 0);
    const startTime = Date.now();
    try {
      await streamResponse(state, question);
    } catch (error) {
      if (error instanceof Error && error.name !== "AbortError") {
        console.error("An error occurred when querying the API", error);
        setWarningMsg("An error occurred when querying the API. Please try again or contact an admin.");
      }
    }
    setLoading(false);
    setFeedbackSent(false);
    highlightAll();
    state.scrollToInput();
    console.log(`Request completed in ${(Date.now() - startTime) / 1000} seconds`);
  }

  function sendFeedback(positive: boolean) {
    fetch(feedbackEndpoint(), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        like: positive,
        messages: state.messages(),
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
    <div
      class={`chat-with-context w-full h-full flex flex-col ${state.messages().length === 0 ? "justify-center" : ""}`}
    >
      <style>{style}</style>
      {/* Main chat container */}
      <div ref={chatContainerEl} class={`overflow-y-auto ${state.messages().length !== 0 ? "flex-grow" : ""}`}>
        <For each={state.messages()}>
          {(msg, iMsg) => (
            <div class={`w-full flex flex-col flex-grow ${msg.role === "user" ? "items-end" : ""}`}>
              <div class={`py-2.5 mb-2 ${msg.role === "user" ? "bg-gray-300 rounded-3xl px-5" : ""}`}>
                <div class="flex flex-col items-start">
                  <For each={msg.steps()}>
                    {(step, iStep) =>
                      step.retrieved_docs.length > 0 ? (
                        <>
                          {/* Add reference docs dialog */}
                          <button
                            class="text-gray-400 ml-8 mb-4"
                            title={`Click to see the documents used to generate the response\n\nNode: ${step.node_id}`}
                            onClick={() => {
                              (
                                document.getElementById(`source-dialog-${iMsg()}-${iStep()}`) as HTMLDialogElement
                              ).showModal();
                              setSelectedTab(step.retrieved_docs[0].metadata.doc_type);
                              highlightAll();
                            }}
                          >
                            {step.label}
                          </button>
                          <dialog
                            id={`source-dialog-${iMsg()}-${iStep()}`}
                            class="bg-white dark:bg-gray-800 m-3 rounded-3xl shadow-md w-full"
                          >
                            <button
                              id={`close-dialog-${iMsg()}-${iStep()}`}
                              class="fixed top-2 right-8 m-3 px-2 text-xl text-slate-500 bg-gray-200 dark:bg-gray-700 rounded-3xl"
                              title="Close references"
                              onClick={() =>
                                (
                                  document.getElementById(`source-dialog-${iMsg()}-${iStep()}`) as HTMLDialogElement
                                ).close()
                              }
                            >
                              <img src={xLogo} alt="Close the dialog" class="iconBtn" />
                            </button>
                            <article class="prose max-w-full p-3">
                              <div class="flex space-x-2 mb-4">
                                <For each={Array.from(new Set(step.retrieved_docs.map(doc => doc.metadata.doc_type)))}>
                                  {docType => (
                                    <button
                                      class={`px-4 py-2 rounded-lg transition-all ${
                                        selectedTab() === docType
                                          ? "bg-gray-600 text-white shadow-md"
                                          : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                                      }`}
                                      onClick={() => {
                                        setSelectedTab(docType);
                                        highlightAll();
                                      }}
                                      title="Show only this type of document"
                                    >
                                      {docType}
                                    </button>
                                  )}
                                </For>
                              </div>
                              <For each={step.retrieved_docs.filter(doc => doc.metadata.doc_type === selectedTab())}>
                                {(doc, iDoc) => (
                                  <>
                                    <p>
                                      <code class="mr-1">
                                        {iDoc() + 1} - {Math.round(doc.metadata.score * 1000) / 1000}
                                      </code>
                                      {doc.metadata.question} (
                                      <a href={doc.metadata.endpoint_url} target="_blank">
                                        {doc.metadata.endpoint_url}
                                      </a>
                                      )
                                    </p>
                                    {getLangForDocType(doc.metadata.doc_type).startsWith("language-") ? (
                                      <pre>
                                        <code class={`${getLangForDocType(doc.metadata.doc_type)}`}>
                                          {doc.metadata.answer}
                                        </code>
                                      </pre>
                                    ) : (
                                      <p>{doc.metadata.answer}</p>
                                    )}
                                  </>
                                )}
                              </For>
                            </article>
                          </dialog>
                        </>
                      ) : step.details ? (
                        <>
                          {/* Dialog to show more details in markdown */}
                          <button
                            class="text-gray-400 ml-8 mb-4"
                            title={`Click to see the documents used to generate the response\n\nNode: ${step.node_id}`}
                            onClick={() => {
                              (
                                document.getElementById(`step-dialog-${iMsg()}-${iStep()}`) as HTMLDialogElement
                              ).showModal();
                              highlightAll();
                            }}
                          >
                            {step.label}
                          </button>
                          <dialog
                            id={`step-dialog-${iMsg()}-${iStep()}`}
                            class="bg-white dark:bg-gray-800 m-3 rounded-3xl shadow-md w-full"
                          >
                            <button
                              id={`close-dialog-${iMsg()}-${iStep()}`}
                              class="fixed top-2 right-8 m-3 px-2 text-xl text-slate-500 bg-gray-200 dark:bg-gray-700 rounded-3xl"
                              title="Close step details"
                              onClick={() =>
                                (
                                  document.getElementById(`step-dialog-${iMsg()}-${iStep()}`) as HTMLDialogElement
                                ).close()
                              }
                            >
                              <img src={xLogo} alt="Close the dialog" class="iconBtn" />
                            </button>
                            <article
                              class="prose max-w-full p-6"
                              // eslint-disable-next-line solid/no-innerhtml
                              innerHTML={DOMPurify.sanitize(marked.parse(step.details) as string)}
                            />
                          </dialog>
                        </>
                      ) : (
                        // Display regular step
                        <p class="text-gray-400 ml-8 mb-4" title={`Node: ${step.node_id}`}>
                          {step.label}
                        </p>
                      )
                    }
                  </For>
                </div>
                <article
                  class="prose max-w-full"
                  // eslint-disable-next-line solid/no-innerhtml
                  innerHTML={DOMPurify.sanitize(marked.parse(msg.content()) as string)}
                />

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
                {feedbackEndpoint() &&
                  msg.role === "assistant" &&
                  iMsg() === state.messages().length - 1 &&
                  state.lastMsg().content() &&
                  !feedbackSent() && (
                    <>
                      <button
                        class="mr-1 my-3 px-3 py-1 text-sm hover:bg-gray-300 dark:hover:bg-gray-800 rounded-3xl align-middle"
                        title="Report a good response"
                        onClick={() => sendFeedback(true)}
                      >
                        <img src={thumbsUpLogo} alt="Thumbs up" height="20px" width="20px" class="iconBtn" />
                      </button>
                      <button
                        class="my-3 px-3 py-1 text-sm hover:bg-gray-300 dark:hover:bg-gray-800 rounded-3xl align-middle"
                        title="Report a bad response"
                        onClick={() => sendFeedback(false)}
                      >
                        <img src={thumbsDownLogo} alt="Thumbs down" height="20px" width="20px" class="iconBtn" />
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
      {state.messages().length < 1 && (
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
          // Only abort if it's a click event (not from pressing Enter)
          if (event.type === "submit" && event.submitter && loading()) {
            state.abortRequest();
          }
          submitInput(inputTextEl.value);
        }}
      >
        <div class="container flex mx-auto max-w-5xl">
          <textarea
            ref={inputTextEl}
            autofocus
            class="flex-grow px-4 py-2 h-auto border border-slate-400 bg-slate-200 dark:bg-slate-700 dark:border-slate-500 rounded-3xl focus:outline-none focus:ring focus:ring-blue-200 dark:focus:ring-blue-400 overflow-y-hidden resize-none"
            placeholder="Ask a question"
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
            title={loading() ? "Stop generation" : "Send question"}
            class="ml-2 px-4 py-2 rounded-3xl text-slate-500 bg-slate-200 dark:text-slate-400 dark:bg-slate-700"
          >
            {loading() ? (
              <img src={squareLogo} alt="Stop generation" class="iconBtn" />
            ) : (
              <img src={sendLogo} alt="Send question" class="iconBtn" />
            )}
            {/* <img src={loaderLogo} alt="Loading" class="iconBtn animate-spin" /> */}
          </button>
          <button
            title="Start a new conversation"
            class="ml-2 px-4 py-2 rounded-3xl text-slate-500 bg-slate-200 dark:text-slate-400 dark:bg-slate-700"
            onClick={() => state.setMessages([])}
          >
            <img src={editLogo} alt="Start a new conversation" class="iconBtn" />
          </button>
        </div>
      </form>
    </div>
  );
});
