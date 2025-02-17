import {defineConfig} from "vite";
import {resolve} from "path";

// https://vitejs.dev/config/
export default defineConfig({
  base: "/sparql-llm/",
  server: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        tutorial: resolve(__dirname, "index.html"),
      },
    },
  },
});