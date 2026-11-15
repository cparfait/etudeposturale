// Téléphones reliés à une séance par QR code : état partagé côté PC (code, téléphones, commandes).
import { useCallback, useEffect, useRef, useState } from "react";
import { http, type Any } from "./api";

export interface Device {
  id: string; nom: string; role: string; role_label: string; etat: string; capture_id: number | null;
  message: string; secure: boolean; fps: number | null; connecte: boolean;
}
export interface Pairing { code: string; session_id: number; appareils: Device[]; roles: { id: string; label: string }[]; commande: Any }

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

/** Appairage de la séance et suivi des téléphones (interrogé toutes les 1,5 s). */
export function useRemote(sid: number | null | undefined) {
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const code = useRef<string | null>(null);
  useEffect(() => {
    if (!sid) return;
    let alive = true;
    http.post("/remote", { session_id: sid }).then((p: Pairing) => { if (alive) { code.current = p.code; setPairing(p); } }).catch(() => {});
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
