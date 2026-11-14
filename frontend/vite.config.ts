import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Le backend FastAPI tourne sur 127.0.0.1:8000 ; le front le joint via /api.
// HTTPS (mkcert) pour l'accès depuis le téléphone : lot 7.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
