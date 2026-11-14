import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Compass, FileText, Info, Lightbulb } from "lucide-react";
import { http, type Any } from "../api";

const CAT: Record<string, string> = {
  sante: "Santé", charge: "Charge d'entraînement", asymetrie: "Asymétrie", cales: "Cales", selle_hauteur: "Hauteur de selle",
  selle_recul: "Recul de selle", cockpit: "Cockpit", manivelle: "Manivelle",
};
const PRIO: Record<string, string> = { haute: "Priorité haute", moyenne: "À tester", info: "Pour information" };
const FIAB: Record<string, string> = { etude: "appuyé par des études", pratique: "pratique de fitters", a_definir: "à confirmer" };

export default function Recommendations() {
  const [data, setData] = useState<Any | null>(null);
  useEffect(() => { http.get("/recommendations").then(setData); }, []);
  if (!data) return <div className="page"><p className="subtle">Chargement…</p></div>;
  const hyps: Any[] = data.hypotheses;
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Étape 5</div>
          <h1>Recommandations</h1>
          <p>Dans l'ordre d'un bike fitter : santé, charge, cales, hauteur de selle, recul, cockpit, manivelle. Un seul changement à la fois, puis 2 ou 3 sorties et une nouvelle capture.</p>
        </div>
        <Link to="/rapport" className="btn btn-ghost"><FileText size={16} /> Rapport complet</Link>
      </header>

      {hyps.length === 0 ? (
        <div className="card empty">
          <Compass size={30} />
          <h2>Rien à signaler pour l'instant</h2>
          <p style={{ marginTop: 6 }}>Ajoute une analyse vidéo, tes douleurs et tes auto-tests : les hypothèses apparaîtront ici.</p>
          <div className="row" style={{ justifyContent: "center", marginTop: 14 }}>
            <Link to="/seance" className="btn btn-primary">Nouvelle séance</Link>
            <Link to="/sante" className="btn btn-ghost">Santé</Link>
          </div>
        </div>
      ) : (
        <ol className="stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {hyps.map((h, i) => (
            <li key={h.id} className={`card hypo ${h.priorite}`}>
              <div className="row between">
                <div className="row">
                  <span className="step-num">{i + 1}</span>
                  <span className="chip">{CAT[h.categorie] ?? h.categorie}</span>
                  <span className={`chip ${h.priorite === "haute" ? "warn" : h.priorite === "info" ? "brand" : ""}`}>{PRIO[h.priorite]}</span>
                </div>
                <span className="subtle" style={{ fontSize: "0.78rem" }}>{FIAB[h.fiabilite] ?? h.fiabilite}{h.sources?.length ? ` · ${h.sources.join(", ")}` : ""}</span>
              </div>
              <h2 style={{ marginTop: 10 }}>{h.titre}</h2>
              <ul>{h.constats.map((c: string) => <li key={c}>{c}</li>)}</ul>
              <p className="why muted"><strong>Hypothèse :</strong> {h.hypothese}</p>
              <div className="action row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}><Lightbulb size={17} style={{ flex: "none", color: "var(--brand-text)", marginTop: 2 }} /> <span>{h.action}</span></div>
            </li>
          ))}
        </ol>
      )}
      <p className="disclaimer"><Info size={15} /> {data.avertissement}</p>
    </div>
  );
}
