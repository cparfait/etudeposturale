import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Le backend FastAPI tourne sur 127.0.0.1:8000 ; le front le joint via /api.
// HTTPS sur le réseau local (obligatoire pour la caméra et le Bluetooth sur le téléphone) :
// certs/cert.pem et certs/key.pem (créés par scripts/https_local.py) → serveur HTTPS ; sans eux, HTTP (envoi de vidéos seulement).
const cert = fileURLToPath(new URL("certs/cert.pem", import.meta.url));
const key = fileURLToPath(new URL("certs/key.pem", import.meta.url));
const https = existsSync(cert) && existsSync(key) ? { cert: readFileSync(cert), key: readFileSync(key) } : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,  // port propre à l'appli (5173 est le port par défaut de Vite, souvent pris par un autre projet)
    strictPort: true,  // pas de bascule silencieuse sur 5174 : l'adresse ouverte et le QR code restent justes
    host: true,  // accessible depuis le téléphone (même Wi-Fi) : QR code de la séance
    https,
    proxy: { "/api": { target: process.env.POSTURALE_API ?? "http://127.0.0.1:8000", ws: true } },  // ws : aperçu en direct des téléphones
  },
});
