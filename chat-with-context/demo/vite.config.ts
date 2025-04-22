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
  build: {
    outDir: "../../src/expasy-agent/src/expasy_agent/webapp",
  },
});
