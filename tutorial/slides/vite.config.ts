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
  // Required to automatically reload the page when a markdown file changes:
  plugins: [
    {
      name: 'reload',
      configureServer(server) {
        server.watcher.on('change', file => {
          if (file.endsWith('.md')) server.ws.send({type: 'full-reload'})
        })
      }
    }
  ],
});