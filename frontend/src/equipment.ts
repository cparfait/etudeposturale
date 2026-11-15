// Équipement de la personne (partagé entre les pages) : ce qui est obligatoire, ce qui manque, comment l'outil s'adapte.
import { useEffect, useState } from "react";
import { http } from "./api";

export type Level = "obligatoire" | "recommande" | "optionnel";
export interface Item { id: string; niveau: Level; icone: string; nom: string; pourquoi: string; sans: string }
export interface Equipment {
  onboarding_fait: boolean;
  items: Record<string, boolean | null>;
  catalogue: Item[];
  manquants: string[];
  adaptations: { id: string; nom: string; texte: string }[];
  pastilles: { preset: string; corps: string; corps1: string; velo: string; velo1: string; teinte_corps: string; teinte_velo: string };
  repondu: number;
  total: number;
  pret: boolean;
}

let cache: Equipment | null = null;
let pending: Promise<Equipment> | null = null;
const subs = new Set<(e: Equipment) => void>();
const publish = (e: Equipment) => { cache = e; subs.forEach((f) => f(e)); return e; };

export function loadEquipment(force = false): Promise<Equipment> {
  if (cache && !force) return Promise.resolve(cache);
  pending ??= http.get<Equipment>("/equipment").then(publish).finally(() => { pending = null; });
  return pending;
}

export const saveEquipment = (patch: { items?: Record<string, boolean | null>; onboarding_fait?: boolean }) =>
  http.put<Equipment>("/equipment", patch).then(publish);

export function useEquipment(): Equipment | null {
  const [eq, setEq] = useState<Equipment | null>(cache);
  useEffect(() => {
    subs.add(setEq);
    loadEquipment().catch(() => {});
    return () => { subs.delete(setEq); };
  }, []);
  return eq;
}

/** Présent ou pas encore répondu (l'outil suppose alors qu'il est là). */
export const has = (eq: Equipment | null, id: string) => eq?.items[id] !== false;
