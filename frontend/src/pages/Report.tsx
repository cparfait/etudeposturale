import { useEffect, useState } from "react";
import { Printer } from "lucide-react";
import { http, type Any } from "../api";
import { CycleChart, LineChart } from "../components/charts";
import { LogoMark } from "../Layout";
import { fmtDate } from "./Sessions";

const show = (v: Any, unit = "") => (v == null || v === "" ? "—" : `${v}${unit ? ` ${unit}` : ""}`);

export default function Report() {
  const [r, setR] = useState<Any | null>(null);
  useEffect(() => { http.get("/report").then(setR); }, []);
  if (!r) return <div className="page"><p className="subtle">Chargement…</p></div>;

  const prof = r.analyses.profil as Record<string, Any>;
  const sides = Object.keys(prof).sort();
  const p1 = r.metrics.P1.plage.dynamique;
  const cfg = r.configurations.at(-1);
  const zone = (z: string) => z.replace(/_/g, " ");

  return (
    <div className="page report">
      <div className="report-cover">
        <div className="row" style={{ alignItems: "center" }}>
          <LogoMark size={46} />
          <div>
            <div className="eyebrow" style={{ marginBottom: 2 }}>Rapport d'étude posturale</div>
            <h1>{[r.velo?.marque, r.velo?.modele].filter(Boolean).join(" ") || "Mon vélo"}{r.velo?.taille ? ` · taille ${r.velo.taille}` : ""}</h1>
            <p className="subtle">Édité le {new Date().toLocaleDateString("fr-FR", { dateStyle: "long" })} · objectif {show(r.profil?.objectif?.replace("_", " et "))}</p>
          </div>
        </div>
        <button className="btn btn-primary no-print" onClick={() => window.print()}><Printer size={16} /> Imprimer / PDF</button>
      </div>

      <h2>Synthèse</h2>
      {r.hypotheses.length === 0 ? <p className="muted">Aucune hypothèse pour l'instant (données insuffisantes).</p> : (
        <ol>
          {r.hypotheses.map((h: Any) => (
            <li key={h.id} style={{ marginBottom: 10 }}>
              <strong>{h.titre}</strong> — {h.action}
              <div className="subtle" style={{ fontSize: "0.84rem" }}>{h.constats.join(" ; ")}</div>
            </li>
          ))}
        </ol>
      )}

      <h2>Profil et douleurs</h2>
      <div className="grid-2">
        <div className="stat-row">
          <div className="stat"><div className="stat-label">Taille</div><div className="stat-value">{show(r.profil?.taille_cm)}<small>cm</small></div></div>
          <div className="stat"><div className="stat-label">Entrejambe</div><div className="stat-value">{show(r.profil?.entrejambe_mm)}<small>mm</small></div></div>
          <div className="stat"><div className="stat-label">Poids</div><div className="stat-value">{show(r.profil?.poids_kg)}<small>kg</small></div></div>
        </div>
        <div>
          {r.douleurs.length === 0 ? <p className="muted">Aucune douleur active.</p> : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {r.douleurs.map((d: Any) => <li key={d.id}>{zone(d.zone)} {d.cote} : {d.intensite}/10{d.moment ? ` (${d.moment})` : ""}</li>)}
            </ul>
          )}
        </div>
      </div>
      {r.tests.length > 0 && (
        <div className="table-scroll" style={{ marginTop: 12 }}>
          <table className="mtable"><thead><tr><th>Auto-test</th><th>Côté</th><th className="num">Résultat</th></tr></thead>
            <tbody>{r.tests.map((t: Any) => <tr key={t.id}><td>{t.test_id}</td><td>{show(t.cote)}</td><td className="num">{t.resultat ?? show(t.valeur)}</td></tr>)}</tbody></table>
        </div>
      )}

      <h2>Configuration du vélo</h2>
      {cfg ? (
        <div className="table-scroll">
          <table className="mtable">
            <thead><tr><th>Date</th><th>Nom</th><th className="num">Selle</th><th className="num">Recul</th><th className="num">Drop</th><th className="num">Manivelle</th><th>Cales</th></tr></thead>
            <tbody>
              {r.configurations.map((c: Any) => (
                <tr key={c.id}><td>{fmtDate(c.created_at)}</td><td>{c.libelle ?? `n° ${c.id}`}</td><td className="num">{show(c.hauteur_selle_mm, "mm")}</td>
                  <td className="num">{show(c.recul_selle_mm, "mm")}</td><td className="num">{show(c.drop_selle_cintre_mm, "mm")}</td>
                  <td className="num">{show(c.manivelle_mm, "mm")}</td><td>{[c.cales_modele, c.cales_liberte].filter(Boolean).join(" · ") || "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="muted">Aucune configuration enregistrée.</p>}

      <h2>Analyse dynamique — profil</h2>
      {sides.length === 0 ? <p className="muted">Aucune analyse de profil.</p> : (
        <>
          <div className="table-scroll">
            <table className="mtable">
              <thead><tr><th>Mesure</th>{sides.map((s) => <th key={s} className="num">{s === "G" ? "Gauche" : "Droite"}</th>)}<th className="num">Plage indicative</th></tr></thead>
              <tbody>
                {["P1", "P2", "P4", "P5", "P6", "P10"].map((k) => (
                  <tr key={k}>
                    <td>{k} — {r.metrics[k]?.nom}</td>
                    {sides.map((s) => { const m = prof[s].metriques[k]; return <td key={s} className="num">{m ? `${m.moyenne.toFixed(1)} ± ${m.ecart_type.toFixed(1)}` : "—"}</td>; })}
                    <td className="num">{(() => { const p = r.metrics[k]?.plage?.dynamique ?? r.metrics[k]?.plage?.descriptif; return p?.min != null ? `${p.min}–${p.max}` : p?.moyenne != null ? `≈ ${p.moyenne}` : "à définir"; })()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card" style={{ marginTop: 14 }}>
            <h3>Flexion du genou sur un tour de manivelle</h3>
            <CycleChart label="Flexion du genou gauche et droite selon l'angle de manivelle"
              series={sides.filter((s) => prof[s].courbes?.genou_flexion).map((s) => ({
                id: s, label: s === "G" ? "Genou gauche" : "Genou droit", color: s === "G" ? "var(--series-g)" : "var(--series-d)",
                mean: prof[s].courbes.genou_flexion.moyenne, sd: prof[s].courbes.genou_flexion.ecart_type,
              }))}
              range={{ min: p1.min, max: p1.max, label: `Plage indicative en bas (${p1.min}–${p1.max}°)` }} />
          </div>
        </>
      )}

      {(r.analyses.face || r.analyses.dos) && (
        <>
          <h2>Vues de face et de dos</h2>
          <ul>
            {r.analyses.face && (["G", "D"] as const).map((s) => (
              <li key={s}>Genou {s} : va-et-vient latéral {r.analyses.face.metriques.cotes[s].F1.moyenne?.toFixed(1)} {r.analyses.face.metriques.unite}</li>
            ))}
            {r.analyses.dos && <li>Bascule du bassin : {r.analyses.dos.metriques.D1.moyenne?.toFixed(1)}° par tour, inclinaison moyenne {r.analyses.dos.metriques.D3}°</li>}
          </ul>
        </>
      )}

      {r.evolution.length > 1 && (
        <>
          <h2>Évolution (avant / après)</h2>
          <div className="table-scroll">
            <table className="mtable">
              <thead><tr><th>Séance</th><th>Côté</th><th>État</th><th className="num">Extension max (P1)</th><th>Verdict</th></tr></thead>
              <tbody>{r.evolution.map((e: Any, i: number) => (
                <tr key={i}><td>{fmtDate(e.date)}</td><td>{e.cote}</td><td>{e.etat === "fin_effort" ? "fin d'effort" : "reposé"}</td><td className="num">{show(e.P1?.toFixed(1), "°")}</td><td>{e.verdict?.replace(/_/g, " ")}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}

      {r.fit && (
        <>
          <h2>Capteurs (.FIT)</h2>
          <p className="muted">{r.fit.duree_min} min · {show(r.fit.global.puissance_w, "W")} · {show(r.fit.global.cadence_rpm, "tr/min")} · équilibre gauche {show(r.fit.global.equilibre_gauche_pct, "%")}</p>
          {r.fit.par_heure.length > 1 && (
            <div className="card" style={{ marginTop: 10 }}>
              <h3>Équilibre gauche (%) heure par heure</h3>
              <LineChart label="Équilibre de puissance gauche par heure" unit="%" values={r.fit.par_heure.map((h: Any) => h.equilibre_gauche_pct)} />
            </div>
          )}
        </>
      )}

      <h2>Avertissement</h2>
      <p className="muted">{r.avertissement}</p>
    </div>
  );
}
