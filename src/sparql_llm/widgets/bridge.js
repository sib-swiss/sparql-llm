// Minimal MCP App client: JSON-RPC with the host over postMessage, without the SDK
// oxlint-disable-next-line no-unused-vars -- global used by the widget pages
const mcpApp = (() => {
  let lastId = 0;
  const pending = {};
  const handlers = {};
  const post = (msg) => parent.postMessage({ jsonrpc: "2.0", ...msg }, "*");
  const request = (method, params) =>
    new Promise((resolve, reject) => {
      const id = ++lastId;
      pending[id] = { resolve, reject };
      post({ id, method, params });
    });
  const notify = (method, params) => post({ method, params });

  // Theme and display mode of the host, as attributes on <html> for the CSS
  const setHostContext = (ctx = {}) => {
    if (ctx.theme) document.documentElement.dataset.theme = ctx.theme;
    if (ctx.displayMode && ctx.displayMode !== document.documentElement.dataset.mode) {
      document.documentElement.dataset.mode = ctx.displayMode;
      // Back inline: size sent again once laid out, the host may have kept another one
      height = 0;
      requestAnimationFrame(reportSize);
    }
    handlers.hostContext?.(ctx);
  };

  addEventListener("message", ({ source, data: m }) => {
    if (source !== parent || !m || m.jsonrpc !== "2.0") return;
    // Response to a request of the app
    if (m.id !== undefined && !m.method) {
      const p = pending[m.id];
      delete pending[m.id];
      if (m.error) p?.reject(new Error(m.error.message));
      else p?.resolve(m.result);
      return;
    }
    if (m.method === "ui/notifications/host-context-changed") setHostContext(m.params);
    else if (m.method === "ui/notifications/tool-input") handlers.input?.(m.params.arguments ?? {});
    else if (m.method === "ui/notifications/tool-result") handlers.result?.(m.params);
    // Requests from the host, e.g. teardown, need an answer
    if (m.id !== undefined) post({ id: m.id, result: {} });
  });

  // Content height, so the host sizes the iframe (not when it fills the screen). Measured on the body, the
  // document scroll height is at least the iframe height, which is the screen while full screen
  let height = 0;
  const reportSize = () => {
    const h = Math.ceil(document.body.getBoundingClientRect().height);
    if (h === height || document.documentElement.dataset.mode === "fullscreen") return;
    height = h;
    notify("ui/notifications/size-changed", { width: 0, height: h });
  };
  new ResizeObserver(reportSize).observe(document.body);

  return {
    /** Handlers: `input` (tool arguments), `result` (CallToolResult), `hostContext` */
    on: (name, fn) => (handlers[name] = fn),
    start: (name) =>
      request("ui/initialize", {
        protocolVersion: "2026-01-26",
        appInfo: { name, version: "0.0.1" },
        appCapabilities: { availableDisplayModes: ["inline", "fullscreen"] },
      }).then((r) => {
        setHostContext(r.hostContext);
        notify("ui/notifications/initialized", {});
        return r;
      }),
    /** Sends a user message to the chat */
    message: (text) => request("ui/message", { role: "user", content: [{ type: "text", text }] }),
    /** Tells the model what the user sees or selected, sent with the next message */
    context: (text) => request("ui/update-model-context", { content: [{ type: "text", text }] }),
    openLink: (url) => request("ui/open-link", { url }),
    displayMode: (mode) => request("ui/request-display-mode", { mode }),
  };
})();
