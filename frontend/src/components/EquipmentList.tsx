import { Activity, AlertTriangle, Bike, Camera, Check, Circle, Gauge, Grid3x3, HeartPulse, Info, Mic, Ruler, Smartphone, Sparkles, Sun, Wand2, Zap } from "lucide-react";
import { saveEquipment, type Equipment, type Level } from "../equipment";
import MicTest from "./MicTest";

const ICONS: Record<string, typeof Bike> = {
  bike: Bike, smartphone: Smartphone, tripod: Camera, circle: Circle, ruler: Ruler, sun: Sun, gauge: Gauge, zap: Zap,
  mic: Mic, activity: Activity, grid: Grid3x3, heart: HeartPulse, sparkles: Sparkles,
};
export const LEVEL_LABEL: Record<Level, string> = { obligatoire: "Obligatoire", recommande: "Recommandé", optionnel: "Optionnel" };
const LEVEL_HINT: Record<Level, string> = {
  obligatoire: "indispensable pour mesurer",
  recommande: "pour plus de précision",
  optionnel: "si tu l'as, l'outil s'en sert ; sinon il s'adapte",
};

/** Matériel groupé par niveau : une carte par niveau, une ligne par élément, interrupteur Oui / Non. */
export default function EquipmentList({ eq, levels }: { eq: Equipment; levels: Level[]; compact?: boolean }) {
  const set = (id: string, v: boolean | null) => saveEquipment({ items: { [id]: v } });
  return (
    <div className="eqg-wrap">
      {levels.map((lvl) => {
        const items = eq.catalogue.filter((c) => c.niveau === lvl);
        const yes = items.filter((c) => eq.items[c.id] === true).length;
        const answered = items.filter((c) => eq.items[c.id] != null).length;
        return (
          <section key={lvl} className={`eqg lvl-${lvl}`}>
            <header className="eqg-head">
              <span className="eqg-dot" />
              <strong>{LEVEL_LABEL[lvl]}</strong>
              <span className="eqg-hint">{LEVEL_HINT[lvl]}</span>
              <span className="eqg-count">{answered < items.length ? `${answered} / ${items.length} répondu${answered > 1 ? "s" : ""}` : `${yes} / ${items.length} disponible${yes > 1 ? "s" : ""}`}</span>
            </header>
            <ul className="eqg-list">
              {items.map((c) => {
                const Icon = ICONS[c.icone] ?? Circle;
                const v = eq.items[c.id];
                const replaced = c.id === "pastilles_orange" && v === false && eq.items.mire;
                const tone = v !== false ? "" : c.niveau === "obligatoire" && !replaced ? "bad" : c.niveau === "recommande" ? "warn" : "info";
                return (
                  <li key={c.id} className={`eqr ${v === true ? "yes" : v === false ? `no ${tone}` : ""}`}>
                    <span className="eqr-icon"><Icon size={18} /></span>
                    <div className="eqr-text">
                      <strong>{c.nom}</strong>
                      <span>{c.pourquoi}</span>
                      {c.id === "micro" && <MicTest onResult={(ok) => { if (ok) set("micro", true); }} />}
                      {v === false && (
                        <p className={`eqr-note ${tone}`}>
                          {tone === "bad" ? <AlertTriangle size={14} /> : tone === "warn" ? <Info size={14} /> : <Wand2 size={14} />}
                          <span>{replaced ? "Remplacées par la mire ChArUco : c'est elle qui donnera l'échelle." : c.sans}</span>
                        </p>
                      )}
                    </div>
                    <div className="eqr-toggle" role="radiogroup" aria-label={c.nom}>
                      <button type="button" role="radio" aria-checked={v === true} className="yes" onClick={() => set(c.id, v === true ? null : true)}>
                        {v === true && <Check size={14} />} Oui
                      </button>
                      <button type="button" role="radio" aria-checked={v === false} className="no" onClick={() => set(c.id, v === false ? null : false)}>
                        Non
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
