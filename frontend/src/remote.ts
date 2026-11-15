// Téléphones reliés à une séance par QR code : état partagé côté PC (code, téléphones, commandes).
import { useCallback, useEffect, useRef, useState } from "react";
import { http, type Any } from "./api";

export interface Device {
  id: string; nom: string; role: string; role_label: string; etat: string; capture_id: number | null;
  message: string; secure: boolean; fps: number | null; connecte: boolean; largeur: number | null; hauteur: number | null;
}
export interface Pairing { code: string; session_id: number | null; appareils: Device[]; roles: { id: string; label: string }[]; commande: Any }

export const ETAT_LABEL: Record<string, string> = {
  connecte: "Relié", pret: "Prêt", enregistre: "Enregistre…", envoi: "Envoi…", envoye: "Vidéo envoyée", erreur: "Erreur",
};

/** Adresse d'une page vue du téléphone : même protocole et même port que l'interface, mais l'IP du PC sur le réseau. */
export async function lanUrl(path: string): Promise<{ url: string; ips: string[]; autorite: boolean }> {
  const r = await http.get("/remote/address").catch(() => ({ adresses: [], autorite: false }));
  const ips: string[] = r.adresses ?? [];
  const host = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname) ? ips[0] ?? location.hostname : location.hostname;
  const port = location.port ? `:${location.port}` : "";
  return { url: `${location.protocol}//${host}${port}${path}`, ips, autorite: !!r.autorite };
}

/** Adresse à mettre dans le QR code d'une séance. */
export const phoneUrl = (code: string) => lanUrl(`/tel?c=${code}`);

/** Appairage d'une séance (ou du cadrage seul : "cadrage") et suivi des téléphones (interrogé toutes les 1,5 s). */
export function useRemote(sid: number | "cadrage" | null | undefined) {
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const code = useRef<string | null>(null);
  useEffect(() => {
    if (!sid) return;
    let alive = true;
    http.post("/remote", { session_id: sid === "cadrage" ? null : sid }).then((p: Pairing) => { if (alive) { code.current = p.code; setPairing(p); } }).catch(() => {});
    const id = setInterval(() => {
      if (code.current) http.get(`/remote/${code.current}`).then((p) => alive && setPairing(p)).catch(() => {});
    }, 1500);
    return () => { alive = false; clearInterval(id); };
  }, [sid]);

  const command = useCallback(async (action: "start" | "stop", cles: string[], duree_s = 60) => {
    if (!code.current) return;
    setPairing(await http.post(`/remote/${code.current}/command`, { action, cles, duree_s }));
  }, []);
  const setRole = useCallback(async (did: string, role: string) => {
    if (!code.current) return;
    setPairing(await http.put(`/remote/${code.current}/appareils/${did}`, { role }));
  }, []);

  const online = (pairing?.appareils ?? []).filter((d) => d.connecte);
  return { pairing, online, command, setRole };
}

/**
 * Aperçu en direct d'un téléphone : reçoit ses images JPEG (WebSocket), reconnexion automatique.
 * Tant que la connexion est ouverte, le téléphone sait qu'un écran regarde et envoie ses images.
 */
export function openPreview(code: string, did: string, onFrame: (img: Blob) => void): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry = 0;
  const connect = () => {
    if (closed) return;
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/remote/${code}/apercu/${did}`);
    ws.binaryType = "blob";
    ws.onmessage = (e) => onFrame(e.data as Blob);
    ws.onclose = () => { if (!closed) retry = window.setTimeout(connect, 1500); };
  };
  connect();
  return () => { closed = true; clearTimeout(retry); ws?.close(); };
}

/** Flux vidéo fabriqué à partir de l'aperçu du téléphone : se branche sur un <video> comme une caméra. */
export function phoneStream(code: string, did: string): { stream: MediaStream; stop: () => void } {
  const canvas = document.createElement("canvas");
  canvas.width = 960; canvas.height = 540;
  const ctx = canvas.getContext("2d")!;
  let busy = false;
  const stop = openPreview(code, did, async (img) => {
    if (busy) return;                     // une image encore en décodage : on saute celle-ci
    busy = true;
    try {
      const bmp = await createImageBitmap(img);
      if (canvas.width !== bmp.width || canvas.height !== bmp.height) { canvas.width = bmp.width; canvas.height = bmp.height; }
      ctx.drawImage(bmp, 0, 0);
      bmp.close();
    } catch { /* image incomplète */ } finally { busy = false; }
  });
  const stream = canvas.captureStream(30);
  return { stream, stop: () => { stop(); stream.getTracks().forEach((t) => t.stop()); } };
}
