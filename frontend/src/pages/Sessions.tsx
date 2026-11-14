import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Plus, Trash2, Video } from "lucide-react";
import { http, type Any } from "../api";
import { useToast } from "../toast";
import { Fields, type FieldSpec } from "../fields";

export const fmtDate = (iso: string) =>
  new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z").toLocaleString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

const NEW: FieldSpec[] = [
  { name: "etat", label: "Moment de la capture", type: "segmented", options: [
    { value: "repose", label: "Reposé (après échauffement)" }, { value: "fin_effort", label: "En fin d'effort / sortie longue" }] },
  { name: "puissance_cible_w", label: "Puissance imposée (ERG)", unit: "W", help: "Endurance (Z2) conseillée pour la hauteur de selle." },
  { name: "notes", label: "Notes", type: "text" },
];

export default function Sessions() {
  const [list, setList] = useState<Any[]>([]);
  const [draft, setDraft] = useState<Record<string, Any>>({ etat: "repose" });
  const toast = useToast();
  const nav = useNavigate();

  const load = () => http.get("/sessions").then(setList).catch((e) => toast(e.message, "error"));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      const s = await http.post("/sessions", draft);
      nav(`/seance/${s.id}`);
    } catch (err) { toast((err as Error).message, "error"); }
  }

  async function remove(id: number) {
    if (!confirm("Supprimer cette séance, ses vidéos et ses analyses ? Cette action est définitive.")) return;
    await http.del(`/sessions/${id}`);
    toast("Séance supprimée");
    load();
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Étape 3</div>
          <h1>Séances de capture</h1>
          <p>Une séance = une configuration du vélo, une ou plusieurs vidéos (profil droit et gauche, face, dos) et, si tu veux, le fichier .FIT de ton compteur.</p>
        </div>
        <Link to="/cadrage" className="btn btn-ghost">Cadrage en direct</Link>
      </header>

      <div className="grid-2">
        <form className="card" onSubmit={create}>
          <div className="card-head">
            <span className="icon-tile"><Plus size={19} /></span>
            <div><h2>Nouvelle séance</h2><p>Rattachée à ta configuration de vélo en cours.</p></div>
          </div>
          <Fields specs={NEW} values={draft} onChange={(n, v) => setDraft((d) => ({ ...d, [n]: v }))} />
          <div className="form-foot">
            <span className="subtle">Ensuite : préparation, vidéos, analyse.</span>
            <button className="btn btn-primary" type="submit">Créer la séance <ArrowRight size={16} /></button>
          </div>
        </form>

        <section className="card">
          <div className="card-head">
            <span className="icon-tile bike"><Video size={19} /></span>
            <div><h2>Mes séances</h2><p>{list.length} séance{list.length > 1 ? "s" : ""}</p></div>
          </div>
          {list.length === 0 ? <p className="empty">Aucune séance pour l'instant.</p> : (
            <ul className="list">
              {list.map((s) => {
                const done = s.captures.flatMap((c: Any) => c.analyses).filter((a: Any) => a.status === "terminee").length;
                return (
                  <li key={s.id} className="list-item">
                    <Link to={`/seance/${s.id}`} className="grow">
                      <strong>{fmtDate(s.created_at)}</strong>
                      <div className="subtle" style={{ fontSize: "0.84rem" }}>
                        {s.etat === "fin_effort" ? "Fin d'effort" : "Reposé"} · {s.captures.length} vidéo{s.captures.length > 1 ? "s" : ""} · {done} analyse{done > 1 ? "s" : ""}
                        {s.config?.hauteur_selle_mm ? ` · selle ${s.config.hauteur_selle_mm} mm` : ""}
                      </div>
                    </Link>
                    <button className="icon-btn" onClick={() => remove(s.id)} aria-label="Supprimer la séance"><Trash2 size={16} /></button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
