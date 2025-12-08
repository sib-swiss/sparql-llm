import {createSignal, For, createEffect} from "solid-js";
import {customElement, noShadowDOM} from "solid-element";
import {marked} from "marked";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
import "highlight.js/styles/default.min.css";

import {style} from "./utils";
import {hljsDefineSparql, hljsDefineTurtle} from "./highlight";
import arrowUpIcon from "./assets/arrow-up.svg";
import xIcon from "./assets/x.svg";
import editIcon from "./assets/edit.svg";
import squareIcon from "./assets/square.svg";
import thumbsDownIcon from "./assets/thumbs-down.svg";
import thumbsUpIcon from "./assets/thumbs-up.svg";
import "./style.css";
import {streamResponse, ChatState} from "./providers";
// import json from "highlight.js/lib/languages/json";

// Get icons svg from https://feathericons.com/
// SolidJS custom element: https://github.com/solidjs/solid/blob/main/src/solid-element/README.md
// https://github.com/solidjs/templates/tree/main/ts-tailwindcss

/**
 * Custom element to create a chat interface with a context-aware assistant.
 * @example <chat-with-context api="http://localhost:8000/"></chat-with-context>
 */
customElement(
  "chat-with-context",
  {chatEndpoint: "", examples: "", apiKey: "", feedbackEndpoint: "", model: ""},
  props => {
    noShadowDOM();
    hljs.registerLanguage("ttl", hljsDefineTurtle);
    hljs.registerLanguage("sparql", hljsDefineSparql);
    // hljs.registerLanguage("json", json);

    const [examples, setExamples] = createSignal<string[]>([]);
    const [warningMsg, setWarningMsg] = createSignal("");
    const [loading, setLoading] = createSignal(false);
    const [dialogOpen, setDialogOpen] = createSignal("");
    const [selectedDocsTab, setSelectedDocsTab] = createSignal("");

    const [feedbackEndpoint, setFeedbackEndpoint] = createSignal("");
    const [feedbackSent, setFeedbackSent] = createSignal(false);

    const state = new ChatState({});
    let chatContainerEl!: HTMLDivElement;
    let inputTextEl!: HTMLTextAreaElement;

    marked.use({
      gfm: true, // Includes autolinker
    });

    createEffect(() => {
      if (props.chatEndpoint === "") setWarningMsg("Please provide an API URL for the chat component to work.");
      state.apiUrl = props.chatEndpoint;
      state.apiKey = props.apiKey;
      state.model = props.model;
      // Prevent automatic scrolling when typing — keep the window where it is.
      state.scrollToInput = () => {};
      state.onMessageUpdate = () => highlightAll();
      setExamples(props.examples.split(",").map(value => value.trim()));
      setFeedbackEndpoint(props.feedbackEndpoint);
      fixInputHeight();
    });

    const openDialog = (dialogId: string) => {
      setDialogOpen(dialogId);
      (document.getElementById(dialogId) as HTMLDialogElement).showModal();
      history.pushState({dialogOpen: true}, "");
      document.body.style.overflow = "hidden";
      highlightAll();
    };

    const closeDialog = () => {
      document.body.style.overflow = "";
      const dialogEl = document.getElementById(dialogOpen()) as HTMLDialogElement;
      if (dialogEl) dialogEl.close();
      setDialogOpen("");
      // history.back();
    };

    // Close open dialogs with the browser navigation "go back one page" button
    createEffect(() => {
      window.addEventListener("popstate", event => {
        if (dialogOpen()) {
          event.preventDefault();
          closeDialog();
        }
      });
    });

    const highlightAll = () => {
      document.querySelectorAll("pre code:not(.hljs)").forEach(block => {
        hljs.highlightElement(block as HTMLElement);
      });
    };

    // Send the user input to the chat API
    async function submitInput(question: string) {
      if (!question.trim()) return;
      if (loading()) return;
      inputTextEl.value = "";
      setLoading(true);
      setWarningMsg("");
      setTimeout(() => fixInputHeight(), 0);
      const startTime = Date.now();
      try {
        await streamResponse(state, question);
      } catch (error) {
        if (error instanceof Error && error.name !== "AbortError") {
          console.error("An error occurred when querying the API:", error);
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
          messages: state.messages().map(msg => ({
            role: msg.role,
            content: msg.content(),
            steps: msg.steps().map(step => ({
              label: step.label,
              details: step.details,
              node_id: step.node_id,
              substeps: step.substeps,
            })),
          })),
        }),
      });
      setFeedbackSent(true);
    }

    // Fix input height to fit content
    function fixInputHeight() {
      // Preserve window scroll position to avoid jumping when the textarea grows.
      const scrollX = window.scrollX || window.pageXOffset;
      const scrollY = window.scrollY || window.pageYOffset;
      inputTextEl.style.height = "auto";
      inputTextEl.style.height = inputTextEl.scrollHeight + "px";
      // Restore scroll position (do it twice to be robust against layout changes)
      window.scrollTo(scrollX, scrollY);
      setTimeout(() => window.scrollTo(scrollX, scrollY), 0);
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
                        step.substeps && step.substeps.length > 0 ? (
                          <>
                            {/* Dialog to show more details about a step with substeps (e.g. retrieved documents) */}
                            <button
                              class="text-gray-600 ml-8 mb-4 px-3 py-1 border border-gray-300 rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
                              title={`Click to see the documents used to generate the response\n\nNode: ${step.node_id}`}
                              onClick={() => {
                                setSelectedDocsTab(step.substeps?.[0]?.label || "");
                                openDialog(`step-dialog-${iMsg()}-${iStep()}`);
                              }}
                            >
                              {step.label}
                            </button>
                            <dialog
                              id={`step-dialog-${iMsg()}-${iStep()}`}
                              class="bg-white dark:bg-gray-800 m-3 rounded-3xl shadow-md w-full"
                              onClose={() => closeDialog()}
                            >
                              <button
                                id={`close-dialog-${iMsg()}-${iStep()}`}
                                class="fixed top-2 right-8 m-3 px-2 text-xl text-slate-500 bg-gray-200 dark:bg-gray-700 rounded-3xl"
                                title="Close documents details"
                                onClick={() => closeDialog()}
                              >
                                <img src={xIcon} alt="Close the dialog" class="iconBtn" />
                              </button>
                              <article class="prose max-w-full p-3">
                                <div class="flex space-x-2 mb-4">
                                  <For each={step.substeps.map(substep => substep.label)}>
                                    {label => (
                                      <button
                                        class={`px-4 py-2 rounded-lg transition-all ${
                                          selectedDocsTab() === label
                                            ? "bg-gray-600 text-white shadow-md"
                                            : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                                        }`}
                                        onClick={() => {
                                          setSelectedDocsTab(label);
                                          highlightAll();
                                        }}
                                        title={`Show ${label}`}
                                      >
                                        {label}
                                      </button>
                                    )}
                                  </For>
                                </div>
                                <For each={step.substeps.filter(substep => substep.label === selectedDocsTab())}>
                                  {substep => (
                                    <article
                                      class="prose max-w-full"
                                      // eslint-disable-next-line solid/no-innerhtml
                                      innerHTML={DOMPurify.sanitize(marked.parse(substep.details) as string, {
                                        ADD_TAGS: ["think"],
                                      })}
                                    />
                                  )}
                                </For>
                              </article>
                            </dialog>
                          </>
                        ) : step.details ? (
                          <>
                            {/* Dialog to show more details about a step in markdown */}
                            <button
                              class="text-gray-600 ml-8 mb-4 px-3 py-1 border border-gray-300 rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
                              title={`Click to see the documents used to generate the response\n\nNode: ${step.node_id}`}
                              onClick={() => {
                                openDialog(`step-dialog-${iMsg()}-${iStep()}`);
                              }}
                            >
                              {step.label}
                            </button>
                            <dialog
                              id={`step-dialog-${iMsg()}-${iStep()}`}
                              class="bg-white dark:bg-gray-800 m-3 rounded-3xl shadow-md w-full"
                              onClose={() => closeDialog()}
                            >
                              <button
                                id={`close-dialog-${iMsg()}-${iStep()}`}
                                class="fixed top-2 right-8 m-3 px-2 text-xl text-slate-500 bg-gray-200 dark:bg-gray-700 rounded-3xl"
                                title="Close step details"
                                onClick={() => closeDialog()}
                              >
                                <img src={xIcon} alt="Close the dialog" class="iconBtn" />
                              </button>
                              <article
                                class="prose max-w-full p-6"
                                // eslint-disable-next-line solid/no-innerhtml
                                innerHTML={DOMPurify.sanitize(marked.parse(step.details) as string, {
                                  ADD_TAGS: ["think"],
                                })}
                              />
                            </dialog>
                          </>
                        ) : (
                          // Display basic step without details
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
                    innerHTML={DOMPurify.sanitize(marked.parse(msg.content()) as string, {ADD_TAGS: ["think"]})}
                    // innerHTML={marked.parse(msg.content()) as string}
                  />

                  {/* Add links, e.g. to Run or edit the query */}
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
                          <img src={thumbsUpIcon} alt="Thumbs up" height="20px" width="20px" class="iconBtn" />
                        </button>
                        <button
                          class="my-3 px-3 py-1 text-sm hover:bg-gray-300 dark:hover:bg-gray-800 rounded-3xl align-middle"
                          title="Report a bad response"
                          onClick={() => sendFeedback(false)}
                        >
                          <img src={thumbsDownIcon} alt="Thumbs down" height="20px" width="20px" class="iconBtn" />
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
          <div class="container flex mx-auto max-w-5xl items-start space-x-2">
            {/* input wrapper: relative so we can absolutely position the send button inside */}
            <div class="relative flex-grow">
              <textarea
                ref={inputTextEl}
                autofocus
                class="w-full px-4 pr-14 py-2 h-auto border border-slate-400 bg-slate-200 dark:bg-slate-700 dark:border-slate-500 rounded-3xl focus:outline-none focus:ring focus:ring-blue-200 dark:focus:ring-blue-400 overflow-y-hidden resize-none"
                style={{"overflow-anchor": "none"}}
                placeholder="Ask your question"
                rows="1"
                onKeyDown={event => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submitInput(inputTextEl.value);
                  }
                }}
                onInput={() => fixInputHeight()}
              />

              {/* send button positioned inside the input, vertically centered with first line */}
              <button
                type="submit"
                title={loading() ? "Stop generation" : "Send question"}
                class={`absolute right-2 top-1 w-8 h-8 flex items-center justify-center rounded-full text-slate-500 bg-slate-100 dark:text-slate-400 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 shadow-sm ${
                  loading() ? "loading-spark" : ""
                }`}
                aria-label={loading() ? "Stop generation" : "Send question"}
              >
                {loading() ? (
                  <img src={squareIcon} alt="Stop generation" class="iconBtn w-4 h-4" />
                ) : (
                  <img src={arrowUpIcon} alt="Send question" class="iconBtn w-4 h-4" />
                )}
              </button>
            </div>

            {/* Start new conversation button aligned to match submit button position */}
            <div class="flex-shrink-0 self-start mt-1">
              <button
                title="Start a new conversation"
                class="w-8 h-8 flex items-center justify-center rounded-full text-slate-500 bg-slate-100 dark:text-slate-400 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 shadow-sm"
                onClick={() => state.setMessages([])}
                type="button"
                aria-label="Start a new conversation"
              >
                <img src={editIcon} alt="Start a new conversation" class="iconBtn w-4 h-4" />
              </button>
            </div>
          </div>
        </form>

        {/* List of examples */}
        {state.messages().length < 1 && (
          <div class="py-2 px-4 justify-center items-center text-sm flex flex-col space-y-2">
            <For each={examples()}>
              {example => (
                <button
                  onClick={() => submitInput(example)}
                  class="px-5 py-2.5 bg-slate-200 text-slate-600 rounded-3xl"
                >
                  {example}
                </button>
              )}
            </For>
          </div>
        )}
      </div>
    );
  },
);
