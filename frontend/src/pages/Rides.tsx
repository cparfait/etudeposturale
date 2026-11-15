import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, ExternalLink, FileUp, FolderOpen, Info, Loader2, Trash2, Usb } from "lucide-react";
import { http, type Any } from "../api";

// Mes sorties : fichiers .FIT (compteur Garmin) ou .zip exportés de Garmin Connect, rangés selon le réglage du vélo du jour.

const GC_ACTIVITIES = "https://connect.garmin.com/modern/activities?activityType=cycling";
const GC_EXPORT_ALL = "https://www.garmin.com/fr-FR/account/datamanagement/exportdata/";

const n = (v: number | null | undefined, d = 0) => (v == null ? "—" : v.toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }));
const bal = (left: number | null | undefined) => (left == null ? "—" : `${Math.round(left)} / ${100 - Math.round(left)}`);  // total toujours 100
const hm = (min: number | null | undefined) => (min == null ? "—" : `${Math.floor(min / 60)} h ${String(Math.round(min % 60)).padStart(2, "0")}`);
const day = (iso: string) => new Date(iso).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short", year: "numeric" });

interface Progress { done: number; total: number; importees: number; doublons: number; autres: number; illisibles: number; erreurs: string[] }

/** Ligne du tableau avant / après : sens « mieux » propre à chaque mesure. */
function Row({ label, a, b, delta, better, fmt, hint }: {
  label: string; a: string; b: string; delta?: number | null; better?: "down" | "up" | "zero"; fmt?: (d: number) => string; hint?: string;
}) {
  let tone = "";
  if (delta != null && better && Math.abs(delta) >= 0.05) {
    const good = better === "up" ? delta > 0 : delta < 0;
    tone = good ? "good" : "bad";
  }
  return (
    <tr>
      <th scope="row">{label}{hint && <small>{hint}</small>}</th>
      <td>{a}</td>
      <td>{b}</td>
      <td className={`rd-delta ${tone}`}>{delta == null ? "" : (fmt ? fmt(delta) : `${delta > 0 ? "+" : ""}${n(delta, 1)}`)}</td>
    </tr>
  );
}

export default function Rides() {
  const [rides, setRides] = useState<Any[] | null>(null);
  const [cmp, setCmp] = useState<Any | null>(null);
  const [prog, setProg] = useState<Progress | null>(null);
  const [over, setOver] = useState(false);
  const [all, setAll] = useState(false);
  const files = useRef<HTMLInputElement>(null);
  const nav = useNavigate();
  const folder = useRef<HTMLInputElement>(null);

  const load = () => {
    http.get("/rides").then(setRides).catch(() => setRides([]));
    http.get("/rides/compare").then(setCmp).catch(() => setCmp(null));
  };
  useEffect(load, []);

  async function importFiles(list: FileList | File[]) {
    const fl = Array.from(list).filter((f) => /\.(fit|zip)$/i.test(f.name));
    if (!fl.length) return;
    const p: Progress = { done: 0, total: fl.length, importees: 0, doublons: 0, autres: 0, illisibles: 0, erreurs: [] };
    setProg({ ...p });
    for (const f of fl) {            // un fichier à la fois : progression visible, pas de requête géante
      const form = new FormData();
      form.append("file", f);
      try {
        const r = await http.upload("/rides/import", form);
        p.importees += r.importees; p.doublons += r.doublons; p.autres += r.autres_sports; p.illisibles += r.illisibles;
      } catch (e) {
        p.erreurs.push(`${f.name} : ${(e as Error).message}`);
      }
      p.done += 1;
      setProg({ ...p });
    }
    load();
  }

  async function remove(id: number) {
    await http.del(`/rides/${id}`).catch(() => {});
    load();
  }

  const a = cmp?.avant, b = cmp?.apres, e = cmp?.ecarts ?? {};
  const shown = all ? rides ?? [] : (rides ?? []).slice(0, 40);
  const busy = prog != null && prog.done < prog.total;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Sur la route</div>
          <h1>Mes sorties</h1>
          <p>Importe tes sorties Garmin : chacune est rangée selon le réglage du vélo en vigueur ce jour-là, pour vérifier qu'un réglage tient sur la durée.</p>
        </div>
      </header>

      <div className="rides-layout">
        <div className="stack" style={{ gap: 16 }}>
          {a && b && (
          <section className="card">
              <h2>Avant / après le dernier réglage</h2>
              {a && b ? (
                <>
                  <p className="subtle rd-periods">
                    <b>{a.libelle}</b> : {a.sorties} sortie{a.sorties > 1 ? "s" : ""}, {n(a.heures, 1)} h
                    <br /><b>{b.libelle}</b> : {b.sorties} sortie{b.sorties > 1 ? "s" : ""}, {n(b.heures, 1)} h
                    {b.hauteur_selle_mm && a.hauteur_selle_mm && b.hauteur_selle_mm !== a.hauteur_selle_mm && ` · selle ${n(a.hauteur_selle_mm)} → ${n(b.hauteur_selle_mm)} mm`}
                  </p>
                  <table className="rd-cmp">
                    <thead><tr><th /><th>Avant</th><th>Après</th><th>Écart</th></tr></thead>
                    <tbody>
                      <Row label="Équilibre gauche / droite" a={bal(a.equilibre_gauche_pct)} b={bal(b.equilibre_gauche_pct)}
                        delta={e.asymetrie} better="down" fmt={(d) => (d < 0 ? `${n(-d, 1)} pt plus symétrique` : `${n(d, 1)} pt moins symétrique`)} />
                      <Row label="Dérive sur les sorties longues" hint="dernière heure − première heure" a={a.derive_equilibre == null ? "—" : `${n(a.derive_equilibre, 1)} pt`}
                        b={b.derive_equilibre == null ? "—" : `${n(b.derive_equilibre, 1)} pt`}
                        delta={a.derive_equilibre != null && b.derive_equilibre != null ? Math.abs(b.derive_equilibre) - Math.abs(a.derive_equilibre) : null} better="down"
                        fmt={(d) => (d < 0 ? "plus stable" : "moins stable")} />
                      <Row label="Efficacité du couple G / D" a={`${n(a.efficacite_couple?.[0])} / ${n(a.efficacite_couple?.[1])} %`} b={`${n(b.efficacite_couple?.[0])} / ${n(b.efficacite_couple?.[1])} %`} />
                      <Row label="Fluidité G / D" a={`${n(a.fluidite?.[0])} / ${n(a.fluidite?.[1])} %`} b={`${n(b.fluidite?.[0])} / ${n(b.fluidite?.[1])} %`} />
                      <Row label="Cadence" a={`${n(a.cadence_rpm)} tr/min`} b={`${n(b.cadence_rpm)} tr/min`} delta={e.cadence_rpm} />
                      <Row label="Watts par battement" hint="même effort, cardio plus bas = mieux" a={n(a.w_par_bpm, 2)} b={n(b.w_par_bpm, 2)} delta={e.w_par_bpm} better="up"
                        fmt={(d) => `${d > 0 ? "+" : ""}${n(d, 2)}`} />
                    </tbody>
                  </table>
                  <p className="rd-note"><Info size={14} /> Compare des sorties semblables (durée, terrain, forme). Avec moins de 3 sorties de chaque côté, c'est une tendance, pas une conclusion.</p>
                </>
              ) : (
                <p className="subtle">Il faut des sorties avant <i>et</i> après un changement de réglage. Les réglages viennent de <Link className="link" to="/velo">Mon vélo</Link> et
                  du débrief de la <Link className="link" to="/seance-guidee">séance guidée</Link> ; chaque sortie est rangée selon sa date.</p>
              )}
            </section>
          )}
          <section className="card">
            <h2>Importer</h2>
            <div className={`drop rd-drop${over ? " over" : ""}`} role="button" tabIndex={0}
              onClick={() => !busy && files.current?.click()} onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && files.current?.click()}
              onDragOver={(ev) => { ev.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={(ev) => { ev.preventDefault(); setOver(false); if (!busy) importFiles(ev.dataTransfer.files); }}>
              {busy ? <Loader2 size={22} className="spin" /> : <FileUp size={22} />}
              <strong>{busy ? `Import ${prog!.done} / ${prog!.total}…` : "Dépose tes fichiers .FIT ou .zip ici"}</strong>
              <small>Plusieurs à la fois · les doublons et les autres sports (course, marche…) sont ignorés</small>
              <input ref={files} type="file" accept=".fit,.zip" multiple hidden onChange={(ev) => { if (ev.target.files) importFiles(ev.target.files); ev.target.value = ""; }} />
              <input ref={folder} type="file" multiple hidden {...({ webkitdirectory: "" } as Any)}
                onChange={(ev) => { if (ev.target.files) importFiles(ev.target.files); ev.target.value = ""; }} />
            </div>
            <button type="button" className="btn btn-ghost btn-sm rd-folder" disabled={busy} onClick={() => folder.current?.click()}>
              <FolderOpen size={14} /> Importer un dossier entier
            </button>
            {prog && !busy && (
              <p className="rd-result"><CheckCircle2 size={16} />
                {prog.importees} sortie{prog.importees > 1 ? "s" : ""} importée{prog.importees > 1 ? "s" : ""}
                {prog.doublons > 0 && ` · ${prog.doublons} déjà présente${prog.doublons > 1 ? "s" : ""}`}
                {prog.autres > 0 && ` · ${prog.autres} autre${prog.autres > 1 ? "s" : ""} sport${prog.autres > 1 ? "s" : ""} ignoré${prog.autres > 1 ? "s" : ""}`}
                {prog.illisibles > 0 && ` · ${prog.illisibles} illisible${prog.illisibles > 1 ? "s" : ""}`}
              </p>
            )}
            {prog?.erreurs.map((m) => <p key={m} className="rd-err">{m}</p>)}

            <div className="rd-howto">
              <h3>Depuis Garmin Connect</h3>
              <a className="btn btn-primary btn-sm" href={GC_ACTIVITIES} target="_blank" rel="noreferrer">
                <ExternalLink size={14} /> Ouvrir mes sorties vélo sur Garmin Connect
              </a>
              <ol>
                <li>Ouvre une sortie.</li>
                <li>Roue dentée <b>⚙</b> en haut à droite › <b>Exporter l'original</b> : un .zip se télécharge.</li>
                <li>Dépose ce .zip ici, tel quel (inutile de le décompresser).</li>
              </ol>
              <p className="subtle"><b>Tout l'historique d'un coup :</b> <a className="link" href={GC_EXPORT_ALL} target="_blank" rel="noreferrer">demande l'export de tes données Garmin</a>.
                Garmin envoie un lien par e-mail (souvent sous 48 h) ; dépose le gros .zip ici, l'app trie les sorties vélo.</p>
              <p className="subtle"><Usb size={14} /> Ou branche ton compteur en USB et importe le dossier <code>GARMIN/Activity</code>.</p>
            </div>
          </section>

          {!(a && b) && (
          <section className="card">
              <h2>Avant / après le dernier réglage</h2>
              {a && b ? (
                <>
                  <p className="subtle rd-periods">
                    <b>{a.libelle}</b> : {a.sorties} sortie{a.sorties > 1 ? "s" : ""}, {n(a.heures, 1)} h
                    <br /><b>{b.libelle}</b> : {b.sorties} sortie{b.sorties > 1 ? "s" : ""}, {n(b.heures, 1)} h
                    {b.hauteur_selle_mm && a.hauteur_selle_mm && b.hauteur_selle_mm !== a.hauteur_selle_mm && ` · selle ${n(a.hauteur_selle_mm)} → ${n(b.hauteur_selle_mm)} mm`}
                  </p>
                  <table className="rd-cmp">
                    <thead><tr><th /><th>Avant</th><th>Après</th><th>Écart</th></tr></thead>
                    <tbody>
                      <Row label="Équilibre gauche / droite" a={bal(a.equilibre_gauche_pct)} b={bal(b.equilibre_gauche_pct)}
                        delta={e.asymetrie} better="down" fmt={(d) => (d < 0 ? `${n(-d, 1)} pt plus symétrique` : `${n(d, 1)} pt moins symétrique`)} />
                      <Row label="Dérive sur les sorties longues" hint="dernière heure − première heure" a={a.derive_equilibre == null ? "—" : `${n(a.derive_equilibre, 1)} pt`}
                        b={b.derive_equilibre == null ? "—" : `${n(b.derive_equilibre, 1)} pt`}
                        delta={a.derive_equilibre != null && b.derive_equilibre != null ? Math.abs(b.derive_equilibre) - Math.abs(a.derive_equilibre) : null} better="down"
                        fmt={(d) => (d < 0 ? "plus stable" : "moins stable")} />
                      <Row label="Efficacité du couple G / D" a={`${n(a.efficacite_couple?.[0])} / ${n(a.efficacite_couple?.[1])} %`} b={`${n(b.efficacite_couple?.[0])} / ${n(b.efficacite_couple?.[1])} %`} />
                      <Row label="Fluidité G / D" a={`${n(a.fluidite?.[0])} / ${n(a.fluidite?.[1])} %`} b={`${n(b.fluidite?.[0])} / ${n(b.fluidite?.[1])} %`} />
                      <Row label="Cadence" a={`${n(a.cadence_rpm)} tr/min`} b={`${n(b.cadence_rpm)} tr/min`} delta={e.cadence_rpm} />
                      <Row label="Watts par battement" hint="même effort, cardio plus bas = mieux" a={n(a.w_par_bpm, 2)} b={n(b.w_par_bpm, 2)} delta={e.w_par_bpm} better="up"
                        fmt={(d) => `${d > 0 ? "+" : ""}${n(d, 2)}`} />
                    </tbody>
                  </table>
                  <p className="rd-note"><Info size={14} /> Compare des sorties semblables (durée, terrain, forme). Avec moins de 3 sorties de chaque côté, c'est une tendance, pas une conclusion.</p>
                </>
              ) : (
                <p className="subtle">Il faut des sorties avant <i>et</i> après un changement de réglage. Les réglages viennent de <Link className="link" to="/velo">Mon vélo</Link> et
                  du débrief de la <Link className="link" to="/seance-guidee">séance guidée</Link> ; chaque sortie est rangée selon sa date.</p>
              )}
            </section>
          )}
        </div>

        <section className="card rd-list">
          <div className="rd-list-head">
            <h2>Sorties importées</h2>
            <span className="subtle">{rides ? `${rides.length} sortie${rides.length > 1 ? "s" : ""}` : ""}</span>
          </div>
          {rides == null ? <Loader2 className="spin" /> : rides.length === 0 ? (
            <p className="subtle">Aucune sortie pour l'instant : importe tes fichiers à gauche.</p>
          ) : (
            <div className="rd-table-wrap">
              <table className="rd-table">
                <thead>
                  <tr><th>Date</th><th>Durée</th><th>Distance</th><th>Puissance</th><th>Cadence</th><th>FC</th><th>G / D</th><th>Réglage</th><th /></tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <tr key={r.id} className="rd-row" onClick={() => nav(`/sorties/${r.id}`)}>
                      <td><Link className="link" to={`/sorties/${r.id}`} onClick={(ev) => ev.stopPropagation()}>{day(r.debut)}</Link></td>
                      <td>{hm(r.mouvement_min ?? r.duree_min)}</td>
                      <td>{r.distance_km != null ? `${n(r.distance_km, 1)} km` : "—"}</td>
                      <td>{r.global?.puissance_w != null ? `${n(r.global.puissance_w)} W` : "—"}</td>
                      <td>{n(r.global?.cadence_rpm)}</td>
                      <td>{n(r.global?.fc_bpm)}</td>
                      <td>{bal(r.global?.equilibre_gauche_pct)}</td>
                      <td><span className="rd-cfg" title={r.config ?? undefined}>{r.config ?? "avant tes réglages"}</span></td>
                      <td><button type="button" className="icon-btn" aria-label={`Supprimer la sortie du ${day(r.debut)}`} onClick={(ev) => { ev.stopPropagation(); remove(r.id); }}><Trash2 size={15} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!all && rides.length > 40 && <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAll(true)}>Voir les {rides.length - 40} autres</button>}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
