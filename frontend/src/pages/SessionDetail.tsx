import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Activity, Camera, Check, ClipboardCheck, FileUp, Gauge, Play, Upload, Video } from "lucide-react";
import { http, type Any } from "../api";
import { useToast } from "../toast";
import { fmtDate } from "./Sessions";
import { has, useEquipment } from "../equipment";

const CHECKS = [
  { t: "Pastilles vertes de 20 mm sur le corps (côté caméra)", d: "Grand trochanter, épicondyle du genou, malléole, talon et 5e métatarse (sur la chaussure), acromion, coude, poignet. Repérer cycliste assis, manivelle en bas." },
  { t: "Pastilles orange de 20 mm sur le vélo", d: "Une sur l'axe de pédalier (centre du plateau), une sur le bout de l'axe de pédale côté caméra. Elles donnent l'angle de manivelle ET l'échelle en mm." },
  { t: "Vélo de niveau, marques au sol", d: "Niveau à bulle sur la base ; ruban adhésif sous la roue arrière et les pieds du trépied pour refaire exactement la même prise." },
  { t: "Téléphone : objectif 1x, 1080p, 60 ou 120 fps", d: "Stabilisation et HDR coupés, mise au point et exposition verrouillées (appui long). Jamais l'ultra grand-angle 0,5x." },
  { t: "Trépied à 2,5–3 m, à hauteur de selle, bien de face", d: "Utilise la page « Cadrage en direct » pour le feu vert. Mire ChArUco (optionnelle) posée contre le cadre, dans le plan du vélo." },
  { t: "Échauffement 10 min, puis puissance stable", d: "Mode ERG (Edge 1050 ou page Capteurs), cadence 85–95 tr/min, mains sur les cocottes." },
  { t: "Enregistrer : clap face caméra, puis 60 s de pédalage", d: "Le clap sert à caler le début de l'analyse. Recommencer de l'autre côté (déplacer le trépied, pas le vélo)." },
];

const SLOTS = [
  { vue: "profil", title: "Profil (droit ou gauche)", text: "Le côté est détecté automatiquement. Dépose les deux côtés pour l'asymétrie.", icon: Video },
  { vue: "face", title: "Vue de face", text: "Pastilles vertes au centre des rotules. Trajectoire des genoux.", icon: Camera },
  { vue: "dos", title: "Vue de dos", text: "Pastilles vertes sur les deux fossettes du bas du dos (EIPS). Bascule du bassin.", icon: Camera },
];

function Drop({ label, text, accept, onFile, busy, icon: Icon }: { label: string; text: string; accept: string; onFile: (f: File) => void; busy?: boolean; icon: typeof Video }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={`drop${over ? " over" : ""}`} role="button" tabIndex={0}
      onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) onFile(f); }}>
      <Icon size={22} />
      <strong>{busy ? "Envoi en cours…" : label}</strong>
      <small>{text}</small>
      <input ref={input} type="file" accept={accept} onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </div>
  );
}

const STATUS: Record<string, string> = { en_attente: "En file d'attente", en_cours: "Analyse en cours", terminee: "Terminée", erreur: "Erreur" };

export default function SessionDetail() {
  const { id } = useParams();
  const [s, setS] = useState<Any | null>(null);
  const [calibs, setCalibs] = useState<Any[]>([]);
  const [calibId, setCalibId] = useState<string>("");
  const [done, setDone] = useState<boolean[]>(() => CHECKS.map(() => false));
  const [busy, setBusy] = useState<string | null>(null);
  const [engines, setEngines] = useState<Record<string, string>>({});
  const toast = useToast();
  const eq = useEquipment();

  const load = useCallback(() => http.get(`/sessions/${id}`).then(setS).catch((e) => toast(e.message, "error")), [id, toast]);
  useEffect(() => {
    load();
    http.get("/calibrations").then(setCalibs).catch(() => {});
    http.get("/engines").then(setEngines).catch(() => {});
  }, [load]);

  // Rafraîchit tant qu'une analyse tourne
  const running = s?.captures.some((c: Any) => c.analyses.some((a: Any) => a.status === "en_attente" || a.status === "en_cours"));
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [running, load]);

  async function uploadVideo(vue: string, f: File) {
    setBusy(vue);
    const form = new FormData();
    form.append("file", f);
    form.append("vue", vue);
    if (calibId) form.append("calib_id", calibId);
    try {
      const cap = await http.upload(`/sessions/${id}/captures`, form);
      toast(`Vidéo importée (${cap.meta.fps.toFixed(0)} images/s)`);
      if (cap.meta.fps < 59) toast("Moins de 60 images/s : précision réduite.", "error");
      await http.post(`/captures/${cap.id}/analyze`, { duree_s: 45 });
      load();
    } catch (err) { toast((err as Error).message, "error"); } finally { setBusy(null); }
  }

  async function uploadFit(f: File) {
    setBusy("fit");
    const form = new FormData();
    form.append("file", f);
    form.append("session_id", String(id));
    try {
      const r = await http.upload("/fit", form);
      toast(`Fichier .FIT importé : ${r.summary.duree_min} min`);
      load();
    } catch (err) { toast((err as Error).message, "error"); } finally { setBusy(null); }
  }

  async function uploadCalib(f: File) {
    const camera = prompt("Nom de l'appareil et du mode vidéo (ex. « Pixel 10 Pro 1080p120 ») :");
    if (!camera) return;
    setBusy("calib");
    const form = new FormData();
    form.append("file", f);
    form.append("camera", camera);
    try {
      const c = await http.upload("/calibrations", form);
      toast(`Calibration enregistrée (erreur ${c.rms_px.toFixed(2)} px, ${c.n_views} vues)`);
      setCalibs((l) => [c, ...l]);
      setCalibId(String(c.id));
    } catch (err) { toast((err as Error).message, "error"); } finally { setBusy(null); }
  }

  async function reanalyze(cid: number) {
    await http.post(`/captures/${cid}/analyze`, { duree_s: 45 });
    load();
  }

  if (!s) return <div className="page"><p className="subtle">Chargement…</p></div>;
  // Adapté à l'équipement : sans pastilles vertes, sans home trainer connecté
  const col = eq?.pastilles ?? { corps: "vertes", velo: "orange" };
  const checks = CHECKS.map((c, i) => ({ ...c, i, t: c.t.replace("vertes", col.corps).replace("orange", col.velo), d: c.t.startsWith("Échauffement") && !has(eq, "trainer_connecte")
    ? "Résistance fixe sur le home trainer (la même à chaque séance), cadence 85–95 tr/min, mains sur les cocottes." : c.d }))
    .filter((c) => !(c.i === 0 && !has(eq, "pastilles_vertes")));
  const nextCheck = checks.find((c) => !done[c.i])?.i;  // seule la prochaine étape montre son explication
  const fit = s.fits[0];

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow"><Link to="/seance" className="link">Séances</Link> · {s.etat === "fin_effort" ? "fin d'effort" : "reposé"}</div>
          <h1>Séance du {fmtDate(s.created_at)}</h1>
          <p>{s.config ? `Configuration : ${s.config.libelle ?? `n° ${s.config.id}`} — selle ${s.config.hauteur_selle_mm ?? "?"} mm, manivelle ${s.config.manivelle_mm} mm.` : "Aucune configuration de vélo enregistrée : renseigne « Mon vélo » pour la correction en mm."}</p>
        </div>
        <span className="chip">{engines.rtmw ? `Moteur RTMW : ${engines.rtmw}` : "Moteur de pose…"}</span>
      </header>

      <div className="sd-layout">
        <section className="card">
          <div className="card-head">
            <span className="icon-tile"><ClipboardCheck size={19} /></span>
            <div><h2>Préparation</h2><p>{checks.filter((c) => done[c.i]).length} / {checks.length} — coche au fur et à mesure.</p></div>
          </div>
          <ul className="checklist">
            {checks.map((c) => { const i = c.i; return (
              <li key={i} className={done[i] ? "done" : ""}>
                <button type="button" aria-pressed={done[i]} title={c.d} onClick={() => setDone((d) => d.map((v, j) => (j === i ? !v : v)))}>
                  <span className="ck-box">{done[i] && <Check size={14} />}</span>
                  <span><span className="ck-title">{c.t}</span>{c.i === nextCheck && <span className="ck-text">{c.d}</span>}</span>
                </button>
              </li>
            ); })}
          </ul>
        </section>

        <div className={`sd-main${s.captures.length ? " has-caps" : ""}`}>
        <div className="section-title"><h2>Vidéos</h2><span className="subtle">L'analyse démarre dès l'import (1 à 3 min sur la RTX 4090).</span></div>
        <div className="grid-3">
          {SLOTS.map((sl) => (
            <Drop key={sl.vue} label={sl.title} text={sl.text} accept="video/*" onFile={(f) => uploadVideo(sl.vue, f)} busy={busy === sl.vue} icon={sl.icon} />
          ))}
        </div>

        {s.captures.length > 0 && (
          <section className="card">
            <div className="card-head">
              <span className="icon-tile"><Gauge size={19} /></span>
              <div><h2>Analyses</h2><p>Clique sur une analyse terminée pour voir le résultat.</p></div>
            </div>
            <ul className="list">
              {s.captures.map((c: Any) => {
                const a = c.analyses[0];
                const side = a?.summary?.cote ? (a.summary.cote === "G" ? " gauche" : " droit") : "";
                return (
                  <li key={c.id} className="list-item">
                    <div className="grow">
                      <div className="row">
                        <strong>{c.vue === "profil" ? `Profil${side}` : c.vue === "face" ? "Face" : "Dos"}</strong>
                        <span className="subtle" style={{ fontSize: "0.82rem" }}>{c.filename} · {c.meta.fps?.toFixed(0)} img/s · {c.meta.duration_s?.toFixed(0)} s</span>
                        {a && <span className={`chip ${a.status === "terminee" ? "ok" : a.status === "erreur" ? "warn" : ""}`}>{STATUS[a.status]}</span>}
                      </div>
                      {a && (a.status === "en_cours" || a.status === "en_attente") && (
                        <div style={{ marginTop: 8 }}>
                          <div className="progress"><span style={{ width: `${Math.round(a.progress * 100)}%` }} /></div>
                          <div className="subtle" style={{ fontSize: "0.8rem", marginTop: 4 }}>{a.message}</div>
                        </div>
                      )}
                      {a?.status === "erreur" && <div className="alert danger" style={{ marginTop: 8 }}>{a.error}</div>}
                      {a?.status === "terminee" && a.summary?.verdict_selle && (
                        <div className="subtle" style={{ fontSize: "0.84rem", marginTop: 4 }}>
                          Extension du genou {a.summary.verdict_selle.flexion_moyenne}° ± {a.summary.verdict_selle.flexion_ecart_type}° — {a.summary.verdict_selle.message}
                        </div>
                      )}
                    </div>
                    {a?.status === "terminee" ? (
                      <Link to={`/analyse/${a.id}`} className="btn btn-primary btn-sm">Résultat</Link>
                    ) : a?.status === "erreur" || !a ? (
                      <button className="btn btn-ghost btn-sm" onClick={() => reanalyze(c.id)}><Play size={14} /> Analyser</button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        )}
        </div>
        <div className="stack sd-side">
          {has(eq, "mire") && <section className="card">
            <div className="card-head">
              <span className="icon-tile bike"><Camera size={19} /></span>
              <div><h2>Calibration de l'objectif <span className="chip">optionnelle</span></h2><p>Une fois par téléphone et par mode vidéo : filme la mire 20–30 s en la bougeant.</p></div>
            </div>
            <div className="row">
              <select className="select" style={{ flex: 1, minWidth: 200 }} value={calibId} onChange={(e) => setCalibId(e.target.value)} aria-label="Calibration à utiliser">
                <option value="">Sans correction de distorsion</option>
                {calibs.map((c) => <option key={c.id} value={c.id}>{c.camera} — {c.width}×{c.height}, erreur {c.rms_px.toFixed(2)} px</option>)}
              </select>
              <label className="btn btn-ghost btn-sm" style={{ cursor: "pointer" }}>
                {busy === "calib" ? "Calcul…" : "Nouvelle calibration"}
                <input type="file" accept="video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCalib(f); e.target.value = ""; }} />
              </label>
            </div>
          </section>}

          {has(eq, "compteur_fit") && <section className="card">
            <div className="card-head">
              <span className="icon-tile"><Activity size={19} /></span>
              <div><h2>Fichier .FIT du compteur <span className="chip">optionnel</span></h2><p>Puissance, cadence, équilibre G/D et phases pendant chaque prise.</p></div>
            </div>
            {fit ? (
              <div className="row">
                <span className="chip ok"><Check size={13} /> {fit.filename}</span>
                <span className="subtle">{fit.summary.global.puissance_w ?? "?"} W · {fit.summary.global.cadence_rpm ?? "?"} tr/min · équilibre G {fit.summary.global.equilibre_gauche_pct ?? "?"} %</span>
              </div>
            ) : (
              <Drop label="Déposer le .FIT" text="Garmin Edge : dossier Garmin/Activity" accept=".fit" onFile={uploadFit} busy={busy === "fit"} icon={FileUp} />
            )}
          </section>}
        </div>
      </div>

      <p className="disclaimer"><Upload size={15} /> Les vidéos restent dans le dossier <code>data/</code> de ce PC ; rien n'est envoyé en ligne.</p>
    </div>
  );
}
