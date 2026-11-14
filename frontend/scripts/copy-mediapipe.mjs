// Copie les fichiers WebAssembly de MediaPipe dans public/ pour qu'ils soient servis en local
// (aucun chargement depuis un CDN). Lancé automatiquement avant `dev` et `build`.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "@mediapipe", "tasks-vision", "wasm");
const dest = join(root, "public", "mediapipe", "wasm");
if (!existsSync(src)) {
  console.warn("MediaPipe absent : lancez npm install.");
  process.exit(0);
}
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log("MediaPipe wasm copié dans public/mediapipe/wasm");
