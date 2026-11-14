import { useCallback, useEffect, useState } from "react";
import { Activity, ClipboardList, HeartPulse, Plus, Stethoscope, Trash2 } from "lucide-react";
import { http, type Any } from "../api";
import { useToast } from "../toast";
import BodyMap, { type ZoneHit } from "../components/BodyMap";
import { Fields, type FieldSpec } from "../fields";
import { fmtDate } from "./Sessions";

type Tab = "douleurs" | "tests" | "ressentis";

function Pains({ catalog, toast }: { catalog: Any; toast: ReturnType<typeof useToast> }) {
  const [pains, setPains] = useState<Any[]>([]);
  const [pick, setPick] = useState<ZoneHit | null>(null);
  const [form, setForm] = useState<Record<string, Any>>({ intensite: 3 });
  const labels = Object.fromEntries(catalog.zones.map((z: Any) => [z.id, z.label]));
  const load = useCallback(() => http.get("/pains").then(setPains), []);
  useEffect(() => { load(); }, [load]);

  async function add() {
    if (!pick) return;
    try {
      await http.post("/pains", { zone: pick.zone, cote: pick.cote, ...form });
      toast("Douleur ajoutée");
      setPick(null);
      setForm({ intensite: 3 });
      load();
    } catch (e) { toast((e as Error).message, "error"); }
  }

  async function toggle(p: Any) {
    await http.put(`/pains/${p.id}`, { ...p, active: !p.active });
    load();
  }

  const active = pains.filter((p) => p.active);
  return (
    <div className="grid-2">
      <section className="card">
        <div className="card-head">
          <span className="icon-tile" style={{ background: "var(--danger-soft)", color: "var(--danger)" }}><HeartPulse size={19} /></span>
          <div><h2>Où as-tu mal ?</h2><p>Touche une zone : chaque zone renvoie à des causes de réglage différentes.</p></div>
        </div>
        <BodyMap labels={labels} selected={pick} pains={active} onPick={setPick} />
      </section>

      <div className="stack">
        <section className="card">
          {pick ? (
            <>
              <h2>{pick.label}</h2>
              <p className="subtle" style={{ margin: "4px 0 14px" }}>Intensité habituelle de la douleur (0 = aucune, 10 = insupportable)</p>
              <div className="intensity" role="group" aria-label="Intensité">
                {Array.from({ length: 11 }, (_, i) => (
                  <button key={i} type="button" aria-pressed={form.intensite === i} onClick={() => setForm({ ...form, intensite: i })}>{i}</button>
                ))}
              </div>
              <div style={{ marginTop: 14 }}>
                <Fields values={form} onChange={(n, v) => setForm({ ...form, [n]: v })} specs={[
                  { name: "moment", label: "Quand ?", type: "text", help: "Ex. « après 3 h de sortie », « en montée », « en danseuse », « au repos »" },
                  { name: "depuis", label: "Depuis quand ?", type: "text", help: "Ex. « depuis ma sortie de 90 km »" },
                  { name: "notes", label: "Précisions", type: "text" },
                ]} />
              </div>
              <div className="form-foot">
                <button className="btn btn-ghost btn-sm" onClick={() => setPick(null)}>Annuler</button>
                <button className="btn btn-primary" onClick={add}><Plus size={16} /> Ajouter</button>
              </div>
            </>
          ) : <p className="empty"><HeartPulse size={28} /><br />Sélectionne une zone sur la silhouette.</p>}
        </section>

        <section className="card">
          <h2>Mes douleurs</h2>
          {pains.length === 0 ? <p className="subtle" style={{ marginTop: 8 }}>Aucune douleur enregistrée.</p> : (
            <ul className="list" style={{ marginTop: 12 }}>
              {pains.map((p) => (
                <li key={p.id} className="list-item" style={p.active ? undefined : { opacity: 0.55 }}>
                  <span className="chip" style={{ background: "var(--danger-soft)", color: "var(--danger)", borderColor: "transparent" }}>{p.intensite}/10</span>
                  <div className="grow">
                    <strong>{labels[p.zone] ?? p.zone} {p.cote === "G" ? "gauche" : p.cote === "D" ? "droit(e)" : ""}</strong>
                    <div className="subtle" style={{ fontSize: "0.82rem" }}>{[p.moment, p.depuis].filter(Boolean).join(" · ") || fmtDate(p.created_at)}</div>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={() => toggle(p)}>{p.active ? "Guérie" : "Réactiver"}</button>
                  <button className="icon-btn" aria-label="Supprimer" onClick={async () => { await http.del(`/pains/${p.id}`); load(); }}><Trash2 size={15} /></button>
                </li>
              ))}
            </ul>
          )}
          {active.some((p) => p.intensite >= 7 || /repos/i.test(p.moment ?? "")) && (
            <div className="alert danger" style={{ marginTop: 12 }}><Stethoscope size={17} /> Douleur forte ou présente au repos : consulte un professionnel de santé avant de modifier ta position.</div>
          )}
        </section>
      </div>
    </div>
  );
}

function Tests({ catalog, toast }: { catalog: Any; toast: ReturnType<typeof useToast> }) {
  const [results, setResults] = useState<Any[]>([]);
  const [draft, setDraft] = useState<Record<string, Any>>({});
  const load = useCallback(() => http.get("/selftests").then(setResults), []);
  useEffect(() => { load(); }, [load]);

  async function save(t: Any, cote: string | null) {
    const key = `${t.id}_${cote ?? ""}`;
    const v = draft[key];
    if (v == null || v === "") return;
    try {
      await http.post("/selftests", { test_id: t.id, cote, ...(t.choix ? { resultat: v } : { valeur: Number(v) }) });
      toast(`${t.label} enregistré`);
      setDraft({ ...draft, [key]: "" });
      load();
    } catch (e) { toast((e as Error).message, "error"); }
  }

  const last = (id: string, cote: string | null) => results.find((r) => r.test_id === id && (r.cote ?? null) === cote);
  return (
    <div className="grid-2">
      {catalog.tests.map((t: Any) => (
        <section key={t.id} className="card">
          <div className="card-head">
            <span className="icon-tile"><Activity size={19} /></span>
            <div><h2>{t.label}</h2><p>Lien : {t.lien}</p></div>
          </div>
          <p className="muted" style={{ fontSize: "0.88rem" }}>{t.protocole}</p>
          <p className="subtle" style={{ fontSize: "0.82rem", marginTop: 8 }}>Repère : {t.repere}</p>
          <div className="grid" style={{ marginTop: 14 }}>
            {(t.cote ? ["G", "D"] : [null]).map((c) => {
              const key = `${t.id}_${c ?? ""}`;
              const prev = last(t.id, c);
              return (
                <div key={key} className="field">
                  <label className="field-label" htmlFor={key}>{c === "G" ? "Gauche" : c === "D" ? "Droite" : "Résultat"}</label>
                  <div className="row" style={{ flexWrap: "nowrap" }}>
                    {t.choix ? (
                      <select id={key} className="select" value={draft[key] ?? ""} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}>
                        <option value="">Choisir…</option>
                        {t.choix.map((o: string) => <option key={o}>{o}</option>)}
                      </select>
                    ) : (
                      <div className="input-wrap" style={{ flex: 1 }}>
                        <input id={key} className={`input${t.unite ? " has-unit" : ""}`} type="number" step="any" value={draft[key] ?? ""}
                          onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
                        {t.unite && <span className="unit">{t.unite}</span>}
                      </div>
                    )}
                    <button className="btn btn-ghost btn-sm" onClick={() => save(t, c)}>OK</button>
                  </div>
                  {prev && <span className="field-help">Dernier : {prev.resultat ?? `${prev.valeur} ${t.unite}`} ({fmtDate(prev.created_at)})</span>}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

const FEEDBACK: FieldSpec[] = [
  { name: "duree_min", label: "Durée", unit: "min" },
  { name: "distance_km", label: "Distance", unit: "km" },
  { name: "rpe", label: "Effort perçu (1–10)", step: 1 },
  { name: "confort_selle", label: "Confort de selle (0–10)", step: 1 },
  { name: "puissance_ressentie", label: "Sensation de puissance (0–10)", step: 1 },
  { name: "engourdissements", label: "Engourdissements", type: "text", help: "Mains, pieds, périnée…" },
  { name: "notes", label: "Notes", type: "textarea" },
];

function Feedback({ toast, catalog }: { toast: ReturnType<typeof useToast>; catalog: Any }) {
  const [list, setList] = useState<Any[]>([]);
  const [pains, setPains] = useState<Any[]>([]);
  const [form, setForm] = useState<Record<string, Any>>({});
  const [levels, setLevels] = useState<Record<string, number>>({});
  const labels = Object.fromEntries(catalog.zones.map((z: Any) => [z.id, z.label]));
  const load = useCallback(() => {
    http.get("/feedback").then(setList);
    http.get("/pains").then((p) => setPains(p.filter((x: Any) => x.active)));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await http.post("/feedback", { ...form, douleurs: levels });
      toast("Ressenti enregistré");
      setForm({});
      setLevels({});
      load();
    } catch (err) { toast((err as Error).message, "error"); }
  }

  return (
    <div className="grid-2">
      <form className="card" onSubmit={save}>
        <div className="card-head">
          <span className="icon-tile"><ClipboardList size={19} /></span>
          <div><h2>Après une sortie</h2><p>2 minutes, après chaque sortie test d'un nouveau réglage.</p></div>
        </div>
        <Fields specs={FEEDBACK} values={form} onChange={(n, v) => setForm({ ...form, [n]: v })} />
        {pains.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3>Tes douleurs pendant cette sortie (0–10)</h3>
            {pains.map((p) => {
              const key = `${p.zone}_${p.cote}`;
              return (
                <div key={p.id} style={{ marginTop: 10 }}>
                  <div className="field-label">{labels[p.zone]} {p.cote}</div>
                  <div className="intensity" role="group" aria-label={`Intensité ${labels[p.zone]}`}>
                    {Array.from({ length: 11 }, (_, i) => (
                      <button key={i} type="button" aria-pressed={levels[key] === i} onClick={() => setLevels({ ...levels, [key]: i })}>{i}</button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div className="form-foot"><span /><button className="btn btn-primary" type="submit"><Plus size={16} /> Enregistrer</button></div>
      </form>

      <section className="card">
        <h2>Historique</h2>
        {list.length === 0 ? <p className="subtle" style={{ marginTop: 8 }}>Aucun ressenti enregistré.</p> : (
          <ul className="list" style={{ marginTop: 12 }}>
            {list.map((f) => (
              <li key={f.id} className="list-item">
                <div className="grow">
                  <strong>{fmtDate(f.created_at)}</strong>
                  <div className="subtle" style={{ fontSize: "0.84rem" }}>
                    {[f.distance_km && `${f.distance_km} km`, f.duree_min && `${f.duree_min} min`, f.rpe && `RPE ${f.rpe}`, f.confort_selle != null && `selle ${f.confort_selle}/10`].filter(Boolean).join(" · ")}
                  </div>
                  {Object.keys(f.douleurs ?? {}).length > 0 && (
                    <div className="row" style={{ marginTop: 6 }}>
                      {Object.entries(f.douleurs).map(([k, v]) => <span key={k} className="chip">{k.replace(/_/g, " ")} : {String(v)}/10</span>)}
                    </div>
                  )}
                </div>
                <button className="icon-btn" aria-label="Supprimer" onClick={async () => { await http.del(`/feedback/${f.id}`); load(); }}><Trash2 size={15} /></button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default function Health() {
  const [tab, setTab] = useState<Tab>("douleurs");
  const [catalog, setCatalog] = useState<Any | null>(null);
  const toast = useToast();
  useEffect(() => { http.get("/catalog").then(setCatalog).catch((e) => toast(e.message, "error")); }, [toast]);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Étape 4</div>
          <h1>Santé et ressentis</h1>
          <p>Douleurs, auto-tests hors vélo et ressentis après chaque sortie : ils pèsent autant que les angles dans les recommandations.</p>
        </div>
      </header>
      <div className="tabs" role="tablist" style={{ maxWidth: 560 }}>
        {([["douleurs", "Douleurs", HeartPulse], ["tests", "Auto-tests", Activity], ["ressentis", "Ressentis", ClipboardList]] as const).map(([id, label, Icon]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}><Icon size={16} /> {label}</button>
        ))}
      </div>
      {!catalog ? <p className="subtle">Chargement…</p> : tab === "douleurs" ? <Pains catalog={catalog} toast={toast} />
        : tab === "tests" ? <Tests catalog={catalog} toast={toast} /> : <Feedback toast={toast} catalog={catalog} />}
    </div>
  );
}
