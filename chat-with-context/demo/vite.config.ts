import {defineConfig} from "vite";
import solidPlugin from "vite-plugin-solid";
// import tailwindcss from '@tailwindcss/vite';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    solidPlugin(),
    // tailwindcss(),
  ],
  server: {
    port: 3000,
  },
  // Relative asset URLs so the UI also works behind a reverse proxy sub-path
  base: "./",
  build: {
    outDir: "../../src/sparql_llm/agent/webapp",
  },
});
