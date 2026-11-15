import { Activity, AlertTriangle, Bike, Camera, Check, Circle, Gauge, Grid3x3, HeartPulse, Info, Mic, Ruler, Smartphone, Sparkles, Sun, Wand2, X, Zap } from "lucide-react";
import { saveEquipment, type Equipment, type Level } from "../equipment";
import MicTest from "./MicTest";

const ICONS: Record<string, typeof Bike> = {
  bike: Bike, smartphone: Smartphone, tripod: Camera, circle: Circle, ruler: Ruler, sun: Sun, gauge: Gauge, zap: Zap,
  mic: Mic, activity: Activity, grid: Grid3x3, heart: HeartPulse, sparkles: Sparkles,
};
export const LEVEL_LABEL: Record<Level, string> = { obligatoire: "Obligatoire", recommande: "Recommandé", optionnel: "Optionnel" };

/** Liste « J'ai / Je n'ai pas » avec, pour chaque réponse « non », ce que ça change. */
export default function EquipmentList({ eq, levels, compact = false }: { eq: Equipment; levels: Level[]; compact?: boolean }) {
  const set = (id: string, v: boolean | null) => saveEquipment({ items: { [id]: v } });
  return (
    <ul className={`eq-list${compact ? " compact" : ""}`}>
      {eq.catalogue.filter((c) => levels.includes(c.niveau)).map((c) => {
        const Icon = ICONS[c.icone] ?? Circle;
        const v = eq.items[c.id];
        const replaced = c.id === "pastilles_orange" && v === false && eq.items.mire;
        return (
          <li key={c.id} title={c.pourquoi} className={`eq-item lvl-${c.niveau} ${v === true ? "yes" : v === false ? "no" : ""}`}>
            <span className="eq-icon"><Icon size={20} /></span>
            <div className="eq-body">
              <div className="eq-head">
                <strong>{c.nom}</strong>
                <span className={`eq-tag ${c.niveau}`}>{LEVEL_LABEL[c.niveau]}</span>
              </div>
              <p className="eq-why">{c.pourquoi}</p>
              {c.id === "micro" && <MicTest onResult={(ok) => { if (ok) set("micro", true); }} />}
              {v === false && (
                <p className={`eq-without ${c.niveau === "obligatoire" && !replaced ? "danger" : c.niveau === "recommande" ? "warn" : ""}`}>
                  {c.niveau === "obligatoire" && !replaced ? <AlertTriangle size={15} /> : c.niveau === "optionnel" ? <Wand2 size={15} /> : <Info size={15} />}
                  <span>{replaced ? "Remplacées par la mire ChArUco : c'est elle qui donnera l'échelle." : c.sans}</span>
                </p>
              )}
            </div>
            <div className="eq-choice" role="group" aria-label={c.nom}>
              <button type="button" aria-pressed={v === true} onClick={() => set(c.id, v === true ? null : true)}><Check size={15} /> J'ai</button>
              <button type="button" aria-pressed={v === false} onClick={() => set(c.id, v === false ? null : false)}><X size={15} /> Je n'ai pas</button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
