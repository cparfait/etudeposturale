import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowDown, ArrowUp, CheckCircle2, Info, Ruler, ShieldCheck } from "lucide-react";
import { http, type Any } from "../api";
import { CycleChart, Gauge, LineChart } from "../components/charts";
import VideoOverlay from "../components/VideoOverlay";

const NAMES: Record<string, string> = {
  P1: "Flexion du genou — extension max (bas)", P2: "Flexion du genou max (haut)", P3: "Amplitude du genou",
  P4: "Angle de hanche fermé", P5: "Plage de cheville", P6: "Genou vs axe de pédale à 3 h (KOPS)",
  P7: "Inclinaison du tronc", P8: "Angle d'épaule", P9: "Flexion du coude", P10: "Mouvement vertical de la hanche",
};
const FIAB: Record<string, string> = { etude: "étude", revue: "revue", pratique: "pratique de fitters", descriptif: "moyenne observée", a_definir: "à définir" };

function rangeText(p: Any): string {
  if (!p) return "—";
  if (p.min != null && p.max != null) return `${p.min} – ${p.max}`;
  if (p.max != null) return `< ${p.max}`;
  if (p.moyenne != null) return `≈ ${p.moyenne} ± ${p.ecart_type}`;
  return "à définir";
}

function status(v: number, p: Any): "ok" | "warn" | null {
  if (!p || p.min == null || p.max == null) return null;
  return v >= p.min && v <= p.max ? "ok" : "warn";
}

function QualityChips({ q }: { q: Any }) {
  const items = [
    ["Images/s", q.Q1_fps, q.Q1_ok],
    ["Repères visibles", q.Q2_visibilite_pct != null ? `${q.Q2_visibilite_pct} %` : null, q.Q2_ok],
    ["Tours valides", q.Q4_cycles, q.Q4_ok],
    ["Régularité (σ P1)", q.Q5_ecart_type_P1 != null ? `${q.Q5_ecart_type_P1}°` : null, q.Q5_ok],
    ["Perpendicularité", q.Q3_perpendicularite_deg != null ? `${q.Q3_perpendicularite_deg}°` : null, q.Q3_ok],
  ].filter((x) => x[1] != null);
  return (
    <div className="row">
      {items.map(([label, val, ok]) => (
        <span key={label as string} className={`chip ${ok ? "ok" : ok === false ? "warn" : ""}`}>
          {ok ? <CheckCircle2 size={13} /> : ok === false ? <AlertTriangle size={13} /> : null} {label} : {String(val)}
        </span>
      ))}
    </div>
  );
}

function ProfileResult({ r, metrics, a }: { r: Any; metrics: Any; a: Any }) {
  const v = r.verdict_selle;
  const p1 = metrics.P1.plage.dynamique;
  const sideName = r.cote === "G" ? "gauche" : "droite";
  const color = r.cote === "G" ? "var(--series-g)" : "var(--series-d)";
  const knee = r.courbes?.genou_flexion;
  const [detail, setDetail] = useState<"courbe" | "mesures">(knee ? "courbe" : "mesures");
  return (
    <>
      <div className="an-layout">
        <div className="an-left">
        <section className="card">
          <div className="card-head">
            <span className="icon-tile"><Ruler size={19} /></span>
            <div><h2>Hauteur de selle — jambe {sideName}</h2><p>Flexion du genou en bas du coup de pédale, sur {r.metriques.P1?.n ?? "?"} tours.</p></div>
          </div>
          {v ? (
            <>
              <div className="row between">
                <div className="verdict-big">{v.flexion_moyenne}°<small>± {v.flexion_ecart_type}°</small></div>
                <span className={`chip ${v.statut === "dans_la_plage" ? "ok" : "warn"}`}>
                  {v.statut === "dans_la_plage" ? "Dans la plage indicative" : v.statut === "trop_tendu" ? "Genou très tendu" : v.statut === "trop_plie" ? "Genou très plié" : "Indéterminé"}
                </span>
              </div>
              <Gauge value={v.flexion_moyenne} sd={v.flexion_ecart_type} min={15} max={55} lo={v.plage_min} hi={v.plage_max} />
              <p className="muted" style={{ marginTop: 10 }}>{v.message}</p>
              {v.correction_mm !== 0 && (
                <div className="correction">
                  {v.correction_mm > 0 ? <ArrowUp size={28} color="#c4f56a" /> : <ArrowDown size={28} color="#c4f56a" />}
                  <span className="big">{v.correction_mm > 0 ? "+" : "−"}{Math.abs(v.correction_mm)} mm</span>
                  <p>{v.plafonnee ? `Calcul : ${v.correction_brute_mm > 0 ? "+" : ""}${v.correction_brute_mm} mm, plafonné à 5 mm par étape. ` : ""}
                    Incertitude ± {v.incertitude_mm} mm. Puis 2 ou 3 sorties et une nouvelle capture.</p>
                </div>
              )}
            </>
          ) : <p className="subtle">Verdict indisponible (pas assez de tours valides).</p>}
        </section>


      <div className="tabs an-tabs" role="tablist" aria-label="Détails">
        {knee && <button type="button" role="tab" aria-selected={detail === "courbe"} onClick={() => setDetail("courbe")}>Le genou sur un tour</button>}
        <button type="button" role="tab" aria-selected={detail === "mesures"} onClick={() => setDetail("mesures")}>Toutes les mesures ({Object.keys(r.metriques).length})</button>
      </div>

      {knee && detail === "courbe" && (
        <section className="card">
          <div className="card-head">
            <span className="icon-tile"><Info size={19} /></span>
            <div><h2>Le genou sur un tour de manivelle</h2><p>Moyenne des tours ; la zone verte est la plage indicative de l'extension max (bas du coup de pédale).</p></div>
          </div>
          <CycleChart label={`Flexion du genou ${sideName} selon l'angle de manivelle`}
            series={[{ id: r.cote, label: `Genou ${sideName}`, color, mean: knee.moyenne, sd: knee.ecart_type }]}
            range={{ min: p1.min, max: p1.max, label: `Plage indicative en bas (${p1.min}–${p1.max}°)` }} />
        </section>
      )}

      {detail === "mesures" && <section className="card">
        <div className="card-head">
          <span className="icon-tile"><Ruler size={19} /></span>
          <div><h2>Toutes les mesures de profil</h2><p>Plages indicatives et sources : config/metrics.yaml.</p></div>
        </div>
        <div className="table-scroll">
          <table className="mtable">
            <thead><tr><th>Mesure</th><th className="num">Valeur</th><th className="num">Plage</th><th>Fiabilité</th></tr></thead>
            <tbody>
              {Object.entries(r.metriques).map(([k, m]: [string, Any]) => {
                const def = metrics[k];
                const plage = def?.plage?.dynamique ?? def?.plage?.descriptif ?? def?.plage?.performance;
                const st = status(m.moyenne, plage);
                return (
                  <tr key={k} title={plage?.fiabilite ? `Fiabilité : ${FIAB[plage.fiabilite]}` : undefined}>
                    <td><strong>{k}</strong> {NAMES[k] ?? def?.nom}</td>
                    <td className="num">{m.moyenne?.toFixed(1)} ± {m.ecart_type?.toFixed(1)} {def?.unite === "mm" ? "mm" : "°"}
                      {st && <> <span className={`chip ${st}`} style={{ marginLeft: 6 }}>{st === "ok" ? "ok" : "hors plage"}</span></>}</td>
                    <td className="num">{rangeText(plage)}</td>
                    <td className="subtle">{plage?.fiabilite ? FIAB[plage.fiabilite] : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="subtle" style={{ fontSize: "0.8rem", marginTop: 10 }}>
          Échelle : {r.echelle.source} ({r.echelle.mm_par_px} mm/px) · pédalier : {r.echelle.pedalier} · moteur : {r.moteur} · calcul {r.duree_calcul_s} s.
        </p>
        {v && (
          <ul className="subtle" style={{ fontSize: "0.8rem", marginTop: 8, paddingLeft: 18 }}>
            {v.hypotheses.map((h: string) => <li key={h}>{h}</li>)}
            <li>Plage {p1.min}–{p1.max}° en dynamique : {p1.source.join(", ")} ({FIAB[p1.fiabilite]}).</li>
          </ul>
        )}
      </section>}
        </div>
        <section className="card">
          <div className="card-head">
            <span className="icon-tile bike"><ShieldCheck size={19} /></span>
            <div><h2>Contrôle du suivi</h2><p>Vérifie que le squelette colle aux pastilles.</p></div>
          </div>
          <VideoOverlay src={`/api/captures/${a.capture_id}/video`} overlay={r.overlay} width={r.video.width} height={r.video.height} />
          <div style={{ marginTop: 12 }}><QualityChips q={r.qualite} /></div>
        </section>
      </div>
    </>
  );
}

function FrontalResult({ r }: { r: Any }) {
  const m = r.metriques;
  if (r.vue === "face") {
    return (
      <div className="grid-2">
        {(["G", "D"] as const).map((s) => (
          <section className="card" key={s}>
            <div className="card-head"><div><h2>Genou {s === "G" ? "gauche" : "droit"}</h2><p>{m.cotes[s].n_cycles} tours analysés</p></div></div>
            <div className="verdict-big">{m.cotes[s].F1.moyenne?.toFixed(1)}<small>{m.unite}</small></div>
            <p className="muted">Va-et-vient latéral du genou par tour (repère : faible, &lt; 20 mm environ).</p>
            <p className="subtle" style={{ marginTop: 8 }}>Décalage moyen vers {m.cotes[s].F2.moyenne > 0 ? "l'extérieur" : "l'intérieur"} : {Math.abs(m.cotes[s].F2.moyenne ?? 0).toFixed(1)} {m.unite}</p>
          </section>
        ))}
        <section className="card"><h2>Asymétrie (F3)</h2><p className="verdict-big" style={{ marginTop: 10 }}>{m.F3 ?? "—"}<small>{m.unite}</small></p></section>
      </div>
    );
  }
  return (
    <div className="grid-2">
      <section className="card">
        <h2>Bascule du bassin (D1)</h2>
        <div className="verdict-big" style={{ marginTop: 10 }}>{m.D1.moyenne?.toFixed(1)}°<small>± {m.D1.ecart_type?.toFixed(1)}</small></div>
        <p className="muted">Amplitude du roulis par tour. Une bascule nette est un signe classique de selle trop haute.</p>
        <p className="subtle" style={{ marginTop: 8 }}>Inclinaison moyenne (D3) : {m.D3}° · balancement latéral : {m.D2_balancement.moyenne?.toFixed(1)} {m.unite}</p>
      </section>
      <section className="card">
        <h2>Roulis au fil du temps</h2>
        <LineChart label="Inclinaison du bassin au fil de la prise" unit="°" values={m.roulis_deg.map((x: Any) => x?.[0] ?? null)} />
      </section>
    </div>
  );
}

export default function AnalysisPage() {
  const { id } = useParams();
  const [a, setA] = useState<Any | null>(null);
  const [r, setR] = useState<Any | null>(null);
  const [metrics, setMetrics] = useState<Any | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([http.get(`/analyses/${id}`), http.get(`/analyses/${id}/result`), http.get("/metrics")])
      .then(([aa, rr, mm]) => { setA(aa); setR(rr); setMetrics(mm.metrics); })
      .catch((e) => setErr(e.message));
  }, [id]);

  if (err) return <div className="page"><div className="alert danger">{err}</div></div>;
  if (!a || !r || !metrics) return <div className="page"><p className="subtle">Chargement…</p></div>;
  const title = r.vue === "profil" ? `Profil ${r.cote === "G" ? "gauche" : "droit"}` : r.vue === "face" ? "Vue de face" : "Vue de dos";

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow"><Link className="link" to="/seance">Séances</Link> · Analyse n° {a.id}</div>
          <h1>{title}</h1>
          <p>Prise de {r.fenetre.debut_s}s à {r.fenetre.fin_s}s{r.fenetre.clap_s != null ? ` (clap détecté à ${r.fenetre.clap_s.toFixed(1)} s)` : ""} · {r.video.width}×{r.video.height} · {r.video.fps.toFixed(0)} images/s.</p>
        </div>
        <Link to="/conseils" className="btn btn-primary">Voir les recommandations</Link>
      </header>
      {r.vue === "profil" ? <ProfileResult r={r} metrics={metrics} a={a} /> : <FrontalResult r={r} />}
      <p className="disclaimer"><Info size={15} /> Plages indicatives et sourcées ; recommandations = hypothèses à tester un réglage à la fois. Ne remplace pas un avis médical.</p>
    </div>
  );
}
