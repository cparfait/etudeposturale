import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bike as BikeIcon, Footprints, History, Info, Ruler, Save } from "lucide-react";
import { api, type BikeConfig, type Values } from "../api";
import { Fields, type FieldSpec } from "../fields";
import { useToast } from "../toast";
import BikeDiagram, { DIM_INFO, FIELD_TO_DIM } from "../components/BikeDiagram";
import CleatDiagram, { CLEAT_INFO } from "../components/CleatDiagram";

const FRAME: FieldSpec[] = [
  { name: "marque", label: "Marque", type: "text" },
  { name: "modele", label: "Modèle", type: "text", help: "Ex. Allez Sport, Tarmac SL6 Sport, Roubaix Sport" },
  { name: "annee", label: "Année", step: 1 },
  { name: "taille", label: "Taille du cadre", type: "text" },
  { name: "angle_tube_selle_deg", label: "Angle du tube de selle", unit: "°", step: 0.1, help: "73,5° par défaut tant qu'il n'est pas renseigné." },
  { name: "stack_mm", label: "Stack", unit: "mm" },
  { name: "reach_mm", label: "Reach", unit: "mm" },
];

const COTES: FieldSpec[] = [
  { name: "hauteur_selle_mm", label: "Hauteur de selle", unit: "mm" },
  { name: "recul_selle_mm", label: "Recul de selle", unit: "mm" },
  { name: "inclinaison_selle_deg", label: "Inclinaison de selle", unit: "°", step: 0.1 },
  { name: "drop_selle_cintre_mm", label: "Drop selle–cintre", unit: "mm" },
  { name: "distance_selle_cintre_mm", label: "Distance selle–cintre", unit: "mm" },
  { name: "manivelle_mm", label: "Manivelle", unit: "mm", step: 2.5 },
  { name: "potence_mm", label: "Potence", unit: "mm" },
  { name: "potence_angle_deg", label: "Angle de potence", unit: "°" },
  { name: "entretoises_mm", label: "Entretoises", unit: "mm" },
  { name: "largeur_cintre_mm", label: "Largeur de cintre", unit: "mm" },
  { name: "selle", label: "Selle (modèle)", type: "text" },
];

const CALES: FieldSpec[] = [
  { name: "pedales", label: "Pédales", type: "text", help: "Ex. Favero Assioma Duo" },
  {
    name: "cales_modele", label: "Système de cales", type: "segmented",
    options: [
      { value: "look_keo", label: "Look Kéo" },
      { value: "shimano_spd_sl", label: "Shimano SPD-SL" },
      { value: "time", label: "Time" },
      { value: "speedplay", label: "Speedplay" },
      { value: "autre", label: "Autre" },
    ],
  },
  { name: "cales_liberte", label: "Liberté / couleur", type: "text", help: "Ex. grise 4,5°, rouge 9°" },
  { name: "cales_avance_mm", label: "Avant / arrière", unit: "mm", step: 0.5 },
  { name: "cales_rotation_g_deg", label: "Rotation gauche", unit: "°", step: 0.5 },
  { name: "cales_rotation_d_deg", label: "Rotation droite", unit: "°", step: 0.5 },
  { name: "cales_lateral_g_mm", label: "Latéral gauche", unit: "mm", step: 0.5 },
  { name: "cales_lateral_d_mm", label: "Latéral droit", unit: "mm", step: 0.5 },
  { name: "rondelles", label: "Rondelles de pédale", type: "text" },
  { name: "chaussures", label: "Chaussures", type: "text" },
  { name: "semelles", label: "Semelles", type: "text" },
  { name: "notes", label: "Notes sur cette configuration", type: "textarea" },
];

const CONFIG_FIELDS = [...COTES, ...CALES];
const EDITABLE = CONFIG_FIELDS.map((f) => f.name);
const LABELS: Record<string, FieldSpec> = Object.fromEntries(CONFIG_FIELDS.map((f) => [f.name, f]));
const OPTION_LABEL: Record<string, string> = Object.fromEntries(
  CONFIG_FIELDS.flatMap((f) => f.options?.map((o) => [o.value, o.label]) ?? []),
);

type Tab = "cadre" | "cotes" | "cales";

function fmtDate(iso: string) {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
  return d.toLocaleString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function show(v: unknown) {
  if (v == null || v === "") return "—";
  return OPTION_LABEL[String(v)] ?? String(v);
}

function Delta({ field, from, to }: { field: string; from: unknown; to: unknown }) {
  const spec = LABELS[field];
  const numeric = typeof from === "number" && typeof to === "number";
  const diff = numeric ? Math.round(((to as number) - (from as number)) * 10) / 10 : 0;
  return (
    <span className="delta">
      {spec?.label ?? field} : {show(from)} → <b>{show(to)}</b>
      {spec?.unit && to != null ? ` ${spec.unit}` : ""}
      {numeric && diff !== 0 && <span className={diff > 0 ? "up" : "down"}> ({diff > 0 ? "+" : ""}{diff})</span>}
    </span>
  );
}

export default function Bike() {
  const [tab, setTab] = useState<Tab>("cotes");
  const [bike, setBike] = useState<Values>({});
  const [bikeSaved, setBikeSaved] = useState<Values>({});
  const [draft, setDraft] = useState<Values>({ manivelle_mm: 175 });
  const [history, setHistory] = useState<BikeConfig[]>([]);
  const [focus, setFocus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    const [b, configs] = await Promise.all([api.getBike(), api.listConfigs()]);
    setBike(b);
    setBikeSaved(b);
    setHistory(configs);
    if (configs[0]) {
      const current: Values = {};
      for (const k of EDITABLE) current[k] = configs[0][k] ?? null;
      setDraft(current);
    }
  }, []);

  useEffect(() => {
    load().catch((e) => toast(e.message, "error"));
  }, [load, toast]);

  const current = history[0];
  const changed = useMemo(
    () => new Set(current ? EDITABLE.filter((k) => (draft[k] ?? null) !== (current[k] ?? null)) : []),
    [draft, current],
  );
  const bikeDirty = Object.keys({ ...bike, ...bikeSaved }).some((k) => (bike[k] ?? null) !== (bikeSaved[k] ?? null));
  const canSaveConfig = current ? changed.size > 0 : EDITABLE.some((k) => k !== "manivelle_mm" && draft[k] != null);
  const changedIn = (specs: FieldSpec[]) => specs.filter((f) => changed.has(f.name)).length;

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    try {
      await action();
      await load();
      toast(message);
    } catch (err) {
      toast((err as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  const saveConfig = () => {
    const label = changed.size === 1 ? `${LABELS[[...changed][0]].label} ${show(draft[[...changed][0]])}` : null;
    return run(() => api.createConfig({ ...draft, libelle: current ? label : "Configuration de départ" }), "Nouvelle configuration enregistrée");
  };

  // Légende du schéma
  const dim = focus ? FIELD_TO_DIM[focus] : null;
  const cleat = focus ? CLEAT_INFO[focus] : null;
  const caption = dim
    ? { title: DIM_INFO[dim].title, how: DIM_INFO[dim].how }
    : cleat ?? (tab === "cales"
      ? { title: "Cales", how: "Clique dans un champ pour voir où mesurer. Un seul changement à la fois, 2 à 3° de rotation au plus." }
      : { title: "Où mesurer ?", how: "Clique dans un champ : la cote correspondante s'allume sur le schéma avec la façon de la relever." });
  const diagramValues = { ...bike, ...draft };

  const tabs: { id: Tab; label: string; icon: typeof BikeIcon; count: number }[] = [
    { id: "cadre", label: "Cadre", icon: BikeIcon, count: 0 },
    { id: "cotes", label: "Cotes", icon: Ruler, count: changedIn(COTES) },
    { id: "cales", label: "Cales et chaussures", icon: Footprints, count: changedIn(CALES) },
  ];

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Étape 2</div>
          <h1>Mon vélo</h1>
          <p>Chaque enregistrement des cotes crée une <strong>nouvelle configuration datée</strong> : l'historique sert aux comparaisons avant/après.</p>
        </div>
        {current && <span className="chip brand">En cours : {current.libelle ?? `n° ${current.id}`}</span>}
      </header>

      <div className="bike-layout">
        <aside className="card diagram-card">
          {tab === "cales" ? <CleatDiagram active={focus} values={draft} /> : <BikeDiagram active={dim} values={diagramValues} />}
          <div className="diagram-caption" aria-live="polite">
            <span className={`icon-tile${dim || tab !== "cales" ? " bike" : ""}`}><Info size={18} /></span>
            <div><h3>{caption.title}</h3><p>{caption.how}</p></div>
          </div>
        </aside>

        <div>
          <div className="tabs" role="tablist" aria-label="Sections">
            {tabs.map(({ id, label, icon: Icon, count }) => (
              <button key={id} role="tab" type="button" aria-selected={tab === id} onClick={() => { setTab(id); setFocus(null); }}>
                <Icon size={16} /> {label} {count > 0 && <span className="count">{count}</span>}
              </button>
            ))}
          </div>

          {tab === "cadre" ? (
            <form className="card" onSubmit={(e) => { e.preventDefault(); run(() => api.putBike(bike), "Vélo enregistré"); }}>
              <div className="card-head">
                <span className="icon-tile bike"><BikeIcon size={19} /></span>
                <div><h2>Cadre et géométrie</h2><p>Sur la fiche géométrie du constructeur (année et taille exactes).</p></div>
              </div>
              <Fields specs={FRAME} values={bike} onChange={(n, v) => setBike((s) => ({ ...s, [n]: v }))} onFocusField={setFocus} />
              <div className="form-foot">
                <span className="subtle">{bikeDirty ? "Modifications non enregistrées" : "Tout est enregistré"}</span>
                <button className="btn btn-primary" type="submit" disabled={!bikeDirty || busy}><Save size={17} /> Enregistrer le vélo</button>
              </div>
            </form>
          ) : (
            <form className="card" onSubmit={(e) => { e.preventDefault(); saveConfig(); }}>
              <div className="card-head">
                <span className={`icon-tile${tab === "cotes" ? " bike" : ""}`}>{tab === "cotes" ? <Ruler size={19} /> : <Footprints size={19} />}</span>
                <div>
                  <h2>{tab === "cotes" ? "Cotes actuelles" : "Pédales, cales et chaussures"}</h2>
                  <p>{tab === "cotes" ? "Mesurées vélo de niveau, au millimètre." : "Photo du dessous des chaussures conseillée (phase 4)."}</p>
                </div>
              </div>
              <Fields specs={tab === "cotes" ? COTES : CALES} values={draft} changed={changed}
                onChange={(n, v) => setDraft((s) => ({ ...s, [n]: v }))} onFocusField={setFocus} />
              {changed.size > 1 && (
                <div className="alert warn" style={{ marginTop: 18 }}>
                  <AlertTriangle size={17} />
                  <span><strong>{changed.size} réglages modifiés à la fois.</strong> Difficile ensuite de savoir lequel a eu un effet : idéalement, un seul changement, de 5 mm au plus, puis 2 ou 3 sorties.</span>
                </div>
              )}
              <div className="form-foot">
                <span className="subtle">
                  {!current ? "Première configuration" : changed.size === 0 ? "Identique à la configuration en cours" : `${changed.size} modification${changed.size > 1 ? "s" : ""} non enregistrée${changed.size > 1 ? "s" : ""}`}
                </span>
                <button className="btn btn-primary" type="submit" disabled={!canSaveConfig || busy}>
                  <Save size={17} /> {current ? "Enregistrer comme nouvelle configuration" : "Enregistrer ma configuration"}
                </button>
              </div>
            </form>
          )}

          <section className="card" style={{ marginTop: 18 }}>
            <div className="card-head">
              <span className="icon-tile"><History size={19} /></span>
              <div><h2>Historique des configurations</h2><p>La plus récente en haut, avec ce qui a changé.</p></div>
            </div>
            {history.length === 0 ? (
              <p className="subtle">Aucune configuration pour l'instant : renseigne tes cotes actuelles puis enregistre.</p>
            ) : (
              <ol className="timeline">
                {history.map((c, i) => {
                  const prev = history[i + 1];
                  const diffs = prev ? EDITABLE.filter((k) => k !== "notes" && (c[k] ?? null) !== (prev[k] ?? null)) : [];
                  return (
                    <li key={c.id} className={`tl-item${i === 0 ? " current" : ""}`}>
                      <div className="tl-rail"><span className="tl-dot" /></div>
                      <div className="tl-body">
                        <div className="tl-head">
                          <span className="tl-title">{c.libelle ?? `Configuration n° ${c.id}`}</span>
                          {i === 0 && <span className="chip brand">En cours</span>}
                          <span className="tl-date">{fmtDate(c.created_at)}</span>
                        </div>
                        <div className="tl-changes">
                          {prev ? (
                            diffs.length ? diffs.map((k) => <Delta key={k} field={k} from={prev[k]} to={c[k]} />)
                              : <span className="delta">Aucun changement de cote</span>
                          ) : (
                            <>
                              <span className="delta">Selle <b>{show(c.hauteur_selle_mm)}</b> mm</span>
                              <span className="delta">Recul <b>{show(c.recul_selle_mm)}</b> mm</span>
                              <span className="delta">Manivelle <b>{show(c.manivelle_mm)}</b> mm</span>
                            </>
                          )}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
