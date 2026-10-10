/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the console talks to the backend on :8000 (python -m c2.server).
const backend = "http://127.0.0.1:8000";
const proxied = ["/state", "/fleet", "/decisions", "/audit"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      ...Object.fromEntries(proxied.map((p) => [p, backend])),
      "/ws": { target: backend, ws: true },
    },
  },
  build: { chunkSizeWarningLimit: 1200 },
  test: { environment: "jsdom", include: ["src/**/*.test.ts", "src/**/*.test.tsx"] },
});
