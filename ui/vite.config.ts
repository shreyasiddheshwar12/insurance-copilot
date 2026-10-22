import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, forward API calls to the FastAPI server on :8000.
const api = "http://127.0.0.1:8000";
const routes = ["/health", "/customers", "/products", "/drafts", "/ask", "/audit"];

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(routes.map((r) => [r, { target: api, changeOrigin: true }])),
  },
});
