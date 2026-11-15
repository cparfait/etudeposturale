import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, ArrowRight, NotebookPen, Ruler, Save } from "lucide-react";
import { api, type Values } from "../api";
import { Fields, type FieldSpec } from "../fields";
import { useToast } from "../toast";

const BODY: FieldSpec[] = [
  { name: "taille_cm", label: "Taille", unit: "cm" },
  { name: "entrejambe_mm", label: "Hauteur d'entrejambe", unit: "mm", help: "Pieds nus contre un mur, un livre serré entre les jambes : du sol au dessus du livre." },
  { name: "poids_kg", label: "Poids", unit: "kg" },
  { name: "pointure", label: "Pointure", unit: "EU", step: 0.5 },
];

const PRACTICE: FieldSpec[] = [
  {
    name: "objectif", label: "Objectif", type: "segmented",
    options: [
      { value: "confort", label: "Confort" },
      { value: "performance_confort", label: "Performance et confort" },
      { value: "performance", label: "Performance" },
    ],
  },
  {
    name: "niveau", label: "Niveau", type: "segmented",
    options: [
      { value: "loisir", label: "Loisir" },
      { value: "sportif", label: "Sportif" },
      { value: "competition", label: "Compétition" },
    ],
  },
  { name: "volume_hebdo_h", label: "Volume hebdomadaire", unit: "h/sem." },
  { name: "annee_naissance", label: "Année de naissance", step: 1 },
];

const NOTES: FieldSpec[] = [
  { name: "notes", label: "Douleurs, blessures, historique", type: "textarea", help: "Ex. « arrière du genou sur les grosses sorties ; avant du genou gauche depuis ma première sortie de 90 km »." },
];

export default function Profile() {
  const [values, setValues] = useState<Values>({});
  const [saved, setSaved] = useState<Values>({});
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    api.getProfile().then((v) => { setValues(v); setSaved(v); }).catch((e) => toast(e.message, "error"));
  }, [toast]);

  const dirty = useMemo(() => Object.keys({ ...values, ...saved }).some((k) => (values[k] ?? null) !== (saved[k] ?? null)), [values, saved]);
  const set = (n: string, v: string | number | null) => setValues((s) => ({ ...s, [n]: v }));
  const complete = !!(saved.taille_cm && saved.entrejambe_mm);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const v = await api.putProfile(values);
      setValues(v);
      setSaved(v);
      toast("Profil enregistré");
    } catch (err) {
      toast((err as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="page" onSubmit={save}>
      <header className="page-head">
        <div>
          <div className="eyebrow">Étape 1</div>
          <h1>Mon profil</h1>
          <p>Ces mesures servent de point de départ et de contrôle de vraisemblance pour la hauteur de selle. Tout reste modifiable à tout moment.</p>
        </div>
        {complete && !dirty ? (
          <Link to="/velo" className="btn btn-primary">Continuer : mon vélo <ArrowRight size={17} /></Link>
        ) : (
          <button className="btn btn-primary" type="submit" disabled={!dirty || busy}>
            <Save size={17} /> {busy ? "Enregistrement…" : dirty ? "Enregistrer" : "Enregistré"}
          </button>
        )}
      </header>

      <div className="profile-grid">
        <div className="stack">
        <section className="card">
          <div className="card-head">
            <span className="icon-tile"><Ruler size={19} /></span>
            <div><h2>Mensurations</h2><p>Mesurées pieds nus, idéalement à deux.</p></div>
          </div>
          <Fields specs={BODY} values={values} onChange={set} />
        </section>

        <section className="card">
          <div className="card-head">
            <span className="icon-tile"><NotebookPen size={19} /></span>
            <div><h2>Notes</h2><p>Blessures, antécédents. Les douleurs actuelles se notent sur la carte de « Santé et ressentis ».</p></div>
          </div>
          <Fields specs={NOTES} values={values} onChange={set} />
          <div className="form-foot">
            <span className="subtle">{dirty ? "Modifications non enregistrées" : complete ? "Tout est enregistré : passe à ton vélo." : "Taille et entrejambe sont nécessaires."}</span>
            {complete && !dirty
              ? <Link to="/velo" className="btn btn-primary">Continuer : mon vélo <ArrowRight size={17} /></Link>
              : <button className="btn btn-primary" type="submit" disabled={!dirty || busy}><Save size={17} /> Enregistrer</button>}
          </div>
        </section>
        </div>

        <section className="card">
          <div className="card-head">
            <span className="icon-tile"><Activity size={19} /></span>
            <div><h2>Pratique</h2><p>L'objectif change les plages cibles proposées.</p></div>
          </div>
          <Fields specs={PRACTICE} values={values} onChange={set} />
        </section>
      </div>
    </form>
  );
}
