import { existsSync, readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Le backend FastAPI tourne sur 127.0.0.1:8000 ; le front le joint via /api.
// HTTPS sur le réseau local (obligatoire pour la caméra et le Bluetooth sur le téléphone) :
// placer certs/cert.pem et certs/key.pem (générés par mkcert, voir README) → serveur HTTPS exposé sur le réseau.
const cert = "certs/cert.pem", key = "certs/key.pem";
const https = existsSync(cert) && existsSync(key) ? { cert: readFileSync(cert), key: readFileSync(key) } : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: https ? true : "localhost",
    https,
    proxy: { "/api": process.env.POSTURALE_API ?? "http://127.0.0.1:8000" },
  },
});
