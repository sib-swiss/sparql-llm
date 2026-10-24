// Bundle each widget page with its npm dependencies, scripts, stylesheets and logos in a single self-contained HTML
// file, in the python package where the MCP server reads them
import { readdirSync, readFileSync } from "node:fs";
import { build } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const outDir = "../src/sparql_llm/widgets";
const pages = readdirSync(".").filter((f) => f.endsWith(".html"));

/** Inline the shared classic scripts (colors.js, viewers.js) defining globals used by the pages, vite only bundles modules */
const inlineClassicScripts = {
  name: "inline-classic-scripts",
  transformIndexHtml: {
    order: "pre",
    handler: (html) =>
      html.replace(/<script src="(\w+\.js)"><\/script>/g, (_, file) => `<script>\n${readFileSync(file, "utf8")}</script>`),
  },
};

/** Nightingale packages declare `"sideEffects": false`, but importing them registers their custom elements */
const keepNightingaleElements = {
  name: "keep-nightingale-elements",
  enforce: "pre",
  async resolveId(source, importer, options) {
    if (!source.startsWith("@nightingale-elements/")) return null;
    const resolved = await this.resolve(source, importer, { ...options, skipSelf: true });
    return resolved && { ...resolved, moduleSideEffects: true };
  },
};

// singlefile inlines all chunks, which requires one build per page
for (const [i, page] of pages.entries()) {
  await build({
    logLevel: "warn",
    plugins: [inlineClassicScripts, keepNightingaleElements, viteSingleFile()],
    build: { outDir, emptyOutDir: i === 0, rollupOptions: { input: page } },
  });
  console.log(`✓ ${page}`);
}
