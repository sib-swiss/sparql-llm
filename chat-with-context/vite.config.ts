import {defineConfig} from "vite";
import solidPlugin from "vite-plugin-solid";
// import typescript from "@rollup/plugin-typescript";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [solidPlugin()],
  server: {
    port: 3000,
  },
  envDir: '../',
  envPrefix: 'EXPASY_',
  build: {
    outDir: "dist",
    target: ["esnext"],
    lib: {
      entry: "src/chat-with-context.tsx",
      name: "@sib-swiss/chat-with-context",
      fileName: "chat-with-context",
    },
    sourcemap: true,
    // rollupOptions: {
    //   plugins: [typescript()],
    // },
  },
  // test: {
  //   globals: true,
  //   environment: "jsdom",
  // },
});
