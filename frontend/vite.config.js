import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker, the backend is reachable at http://backend:8000 (the service name).
// Locally it's http://localhost:8000. We read this from an env variable so
// docker-compose can override it without touching this file.
const apiTarget = process.env.BACKEND_URL ?? "http://localhost:8000";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // --host makes Vite listen on all network interfaces.
    // Required inside Docker so the container port is reachable from your browser.
    host: true,
    proxy: {
      // Any request from the browser to /api/... is forwarded to the FastAPI server.
      // This avoids CORS issues during development — the browser thinks everything
      // comes from localhost:5173, but /api calls secretly go to the backend.
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "face-api": ["@vladmandic/face-api"],
        },
      },
    },
  },
});
