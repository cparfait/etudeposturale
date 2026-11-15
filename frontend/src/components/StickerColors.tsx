import { useEffect, useState } from "react";
import { http, type Any } from "../api";
import { loadEquipment } from "../equipment";

/** Choix du jeu de couleurs des pastilles : la détection et les textes de l'app suivent. */
export default function StickerColors({ onChange, compact = false }: { onChange?: (colors: Any) => void; compact?: boolean }) {
  const [data, setData] = useState<Any | null>(null);
  useEffect(() => { http.get("/markers/colors").then(setData).catch(() => {}); }, []);
  if (!data) return null;

  async function choose(id: string) {
    const r = await http.put("/markers/preset", { id });
    setData(r);
    await loadEquipment(true).catch(() => {});
    onChange?.(r);
  }

  return (
    <div className={`sc${compact ? " compact" : ""}`} role="group" aria-label="Couleurs des pastilles">
      <span className="sc-label">Point de départ (facultatif)</span>
      <div className="sc-options">
        {data.presets.map((p: Any) => (
          <button key={p.id} type="button" aria-pressed={data.preset === p.id} onClick={() => choose(p.id)}>
            <span className="sc-sw" style={{ background: p.noms.teinte_corps }} />
            <span className="sc-sw" style={{ background: p.noms.teinte_velo }} />
            {p.nom}
          </button>
        ))}
      </div>
      {!compact && <span className="sc-help">Corps : {data.noms.corps} · vélo : {data.noms.velo}. Le mieux : bande de kiné découpée en carrés de 2 cm (pas en longues bandes : l'app repère des points).</span>}
    </div>
  );
}
