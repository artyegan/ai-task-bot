import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs in Docker on :8000; nginx does the same proxying in production.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  test: { environment: "node" },
});
