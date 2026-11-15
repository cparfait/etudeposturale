import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, CheckCircle2, Info, Loader2, Sparkles } from "lucide-react";
import { http, type Any } from "../api";
import { TimeChart } from "../components/charts";

// Une sortie en détail : équilibre G/D au fil de la sortie, puissance, cardio, et les deux jambes comparées.

const LEFT = "#121a12", RIGHT = "#7fb82e";
const n = (v: number | null | undefined, d = 0) => (v == null ? "—" : v.toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }));
const hm = (min: number | null | undefined) => (min == null ? "—" : `${Math.floor(min / 60)} h ${String(Math.round(min % 60)).padStart(2, "0")}`);

/** Cadran de manivelle : arc de poussée de chaque jambe (début → fin), pic marqué. 0° = manivelle en haut. */
function CrankDial({ g, d, pg, pd }: { g?: number[] | null; d?: number[] | null; pg?: number[] | null; pd?: number[] | null }) {
  const c = 110, R = { g: 84, d: 66 };
  const pt = (deg: number, r: number) => [c + r * Math.sin((deg * Math.PI) / 180), c - r * Math.cos((deg * Math.PI) / 180)];
  const arc = (ph: number[], r: number) => {
    const [s, e] = ph, span = ((e - s) % 360 + 360) % 360;
    const [x1, y1] = pt(s, r), [x2, y2] = pt(e, r);
    return `M${x1.toFixed(1)},${y1.toFixed(1)} A${r},${r} 0 ${span > 180 ? 1 : 0} 1 ${x2.toFixed(1)},${y2.toFixed(1)}`;
  };
  const peak = (p: number[] | null | undefined, r: number, col: string) => {
    if (!p) return null;
    const mid = p.length >= 2 ? (p[0] + ((((p[1] - p[0]) % 360) + 360) % 360) / 2) : p[0];
    const [x, y] = pt(mid, r);
    return <circle cx={x} cy={y} r={6} fill="#fff" stroke={col} strokeWidth={3} />;
  };
  return (
    <svg viewBox="-18 -4 256 228" className="rd-dial" role="img" aria-label="Phases de poussée des deux jambes sur un tour de manivelle">
      <circle cx={c} cy={c} r={R.g} className="rd-dial-track" />
      <circle cx={c} cy={c} r={R.d} className="rd-dial-track" />
      {[0, 90, 180, 270].map((a) => { const [x, y] = pt(a, 110); return <text key={a} x={x} y={y + 4} className="axis-text" textAnchor="middle">{a}°</text>; })}
      {g && <path d={arc(g, R.g)} stroke={LEFT} strokeWidth={12} fill="none" strokeLinecap="round" />}
      {d && <path d={arc(d, R.d)} stroke={RIGHT} strokeWidth={12} fill="none" strokeLinecap="round" />}
      {peak(pg, R.g, LEFT)}{peak(pd, R.d, RIGHT)}
      <text x={c} y={c - 4} textAnchor="middle" className="rd-dial-c">haut</text>
      <text x={c} y={c + 14} textAnchor="middle" className="axis-text">= 0°</text>
    </svg>
  );
}

export default function Ride() {
  const { id } = useParams();
  const [r, setR] = useState<Any | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { http.get(`/rides/${id}`).then(setR).catch((e) => setErr((e as Error).message)); }, [id]);

  if (err) return <div className="page"><p className="alert danger">{err}</p><Link className="link" to="/sorties">Retour à mes sorties</Link></div>;
  if (!r) return <div className="page"><Loader2 className="spin" /></div>;
  const g = r.global ?? {};
  const t = (r.serie ?? []).map((b: Any) => b.t_min);
  const col = (k: string) => (r.serie ?? []).map((b: Any) => b[k] ?? null);
  const left = g.equilibre_gauche_pct;
  const hasLegs = left != null || g.efficacite_couple?.[0] != null || g.phase_puissance_g;
  const date = new Date(r.debut).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const hour = new Date(r.debut).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="page">
      <Link className="link rd-back" to="/sorties"><ArrowLeft size={15} /> Mes sorties</Link>
      <header className="page-head">
        <div>
          <div className="eyebrow">Sortie du {hour}</div>
          <h1 className="rd-title">{date}</h1>
          <p>{hm(r.mouvement_min ?? r.duree_min)}{r.distance_km != null && ` · ${n(r.distance_km, 1)} km`} · réglage : <span className="rd-cfg">{r.config ?? "avant tes réglages"}</span></p>
        </div>
      </header>

      <div className="rd-stats">
        <div><span>Puissance</span><strong>{n(g.puissance_w)}<small> W</small></strong></div>
        <div><span>Cadence</span><strong>{n(g.cadence_rpm)}<small> tr/min</small></strong></div>
        <div><span>Cardio</span><strong>{n(g.fc_bpm)}<small> bpm</small></strong></div>
        <div><span>Watts par battement</span><strong>{n(r.w_par_bpm, 2)}</strong></div>
        <div><span>Gauche / droite</span><strong>{left == null ? "—" : `${Math.round(left)} / ${100 - Math.round(left)}`}<small> %</small></strong></div>
      </div>

      <div className="rd-detail">
        <div className="stack" style={{ gap: 16 }}>
          {r.lecture?.length > 0 && (
            <section className="card">
              <h2>Ce que montre la sortie</h2>
              <ul className="rd-reading">
                {r.lecture.map((x: Any) => (
                  <li key={x.titre} className={x.ton}>
                    {x.ton === "ok" ? <CheckCircle2 size={18} /> : x.ton === "warn" ? <AlertTriangle size={18} /> : <Info size={18} />}
                    <div><strong>{x.titre}</strong><p>{x.texte}</p></div>
                  </li>
                ))}
              </ul>
              <p className="rd-note"><Sparkles size={14} /> Pour aller plus loin, pose la question au <Link className="link" to="/coach">coach IA</Link> : il reçoit tes sorties.</p>
            </section>
          )}

          {hasLegs && (
            <section className="card">
              <h2>Jambe gauche, jambe droite</h2>
              <div className="rd-legs">
                <table className="rd-cmp">
                  <thead><tr><th /><th><i className="rd-key" style={{ background: LEFT }} />Gauche</th><th><i className="rd-key" style={{ background: RIGHT }} />Droite</th></tr></thead>
                  <tbody>
                    <tr><th scope="row">Part de la puissance</th><td>{left == null ? "—" : `${Math.round(left)} %`}</td><td>{left == null ? "—" : `${100 - Math.round(left)} %`}</td></tr>
                    <tr><th scope="row">Efficacité du couple<small>force utile / force totale</small></th><td>{n(g.efficacite_couple?.[0])} %</td><td>{n(g.efficacite_couple?.[1])} %</td></tr>
                    <tr><th scope="row">Fluidité<small>régularité sur le tour</small></th><td>{n(g.fluidite?.[0])} %</td><td>{n(g.fluidite?.[1])} %</td></tr>
                    <tr><th scope="row">Phase de poussée<small>début → fin de la poussée</small></th>
                      <td>{g.phase_puissance_g ? `${n(g.phase_puissance_g[0])}° → ${n(g.phase_puissance_g[1])}°` : "—"}</td>
                      <td>{g.phase_puissance_d ? `${n(g.phase_puissance_d[0])}° → ${n(g.phase_puissance_d[1])}°` : "—"}</td></tr>
                  </tbody>
                </table>
                {(g.phase_puissance_g || g.phase_puissance_d) ? (
                  <CrankDial g={g.phase_puissance_g} d={g.phase_puissance_d} pg={g.pic_phase_g} pd={g.pic_phase_d} />
                ) : <p className="subtle rd-nophase">Pas de phases de poussée dans ce fichier (pédales sans « dynamique de cyclisme », ou option désactivée dans l'appli du capteur).</p>}
              </div>
            </section>
          )}
        </div>

        <section className="card rd-charts">
          <h2>Au fil de la sortie</h2>
          {!r.fichier_disponible ? (
            <p className="subtle">Le fichier d'origine n'est plus disponible : réimporte la sortie pour voir les courbes.</p>
          ) : (
            <>
              {left != null && (
                <div className="rd-chart">
                  <h3>Part de la jambe gauche</h3>
                  <TimeChart t={t} values={col("equilibre_gauche_pct")} unit="%" label="Part de la puissance fournie par la jambe gauche, toutes les 5 minutes"
                    reference={{ value: 50, label: "50 / 50" }} band={[48, 52]} color={LEFT} digits={1} />
                  <p className="rd-cap">Bande claire : 48 à 52 %, pédalage équilibré. Une courbe qui descend en fin de sortie = la jambe gauche fatigue.</p>
                </div>
              )}
              <div className="rd-chart">
                <h3>Puissance</h3>
                <TimeChart t={t} values={col("puissance_w")} unit="W" label="Puissance moyenne toutes les 5 minutes" color="var(--brand-text)" />
              </div>
              <div className="rd-chart">
                <h3>Cardio</h3>
                <TimeChart t={t} values={col("fc_bpm")} unit="bpm" label="Fréquence cardiaque moyenne toutes les 5 minutes" color="#c2410c" />
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
