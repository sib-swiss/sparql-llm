import {defineConfig} from "vite";
import solidPlugin from "vite-plugin-solid";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [solidPlugin()],
  server: {
    port: 3000,
  },
  build: {
    outDir: "../../src/sparql_llm/webapp",
  },
});
