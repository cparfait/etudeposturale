import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Bike, Check, Gauge, Info, Lock, User, Video } from "lucide-react";
import { api, type BikeConfig, type Values } from "../api";
import PedalingRider from "../components/PedalingRider";
import { KNEE_RANGE } from "../components/bikeGeometry";

function Stat({ label, value, unit }: { label: string; value: unknown; unit: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value == null || value === "" ? "—" : String(value)}{value != null && value !== "" && <small>{unit}</small>}</div>
    </div>
  );
}

export default function Home() {
  const [profile, setProfile] = useState<Values | null>(null);
  const [config, setConfig] = useState<BikeConfig | null>(null);
  const [bike, setBike] = useState<Values | null>(null);
  const [offline, setOffline] = useState(false);
  const hud = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    Promise.all([api.getProfile(), api.listConfigs(), api.getBike()])
      .then(([p, c, b]) => { setProfile(p); setConfig(c[0] ?? null); setBike(b); })
      .catch(() => setOffline(true));
  }, []);

  // Mise à jour directe du HUD (60 fois par seconde) sans re-rendre la page
  const onFlexion = useCallback((f: number) => {
    if (hud.current) hud.current.textContent = `${Math.round(f)}°`;
  }, []);

  const profileDone = !!(profile?.taille_cm && profile?.entrejambe_mm);
  const bikeDone = !!config?.hauteur_selle_mm;

  const steps = [
    { n: 1, to: "/profil", icon: User, title: "Mon profil", text: "Taille, entrejambe, poids et objectif.", done: profileDone },
    { n: 2, to: "/velo", icon: Bike, title: "Mon vélo", text: "Géométrie, cotes actuelles et cales.", done: bikeDone, bike: true },
    { n: 3, icon: Video, title: "Séance de capture", text: "Pastilles, mire, cadrage guidé, vidéo de profil." },
    { n: 4, icon: Gauge, title: "Analyse", text: "Angle du genou, verdict et correction en mm." },
  ];
  const next = steps.find((s) => s.to && !s.done);

  return (
    <div className="page">
      <section className="hero">
        <div>
          <div className="eyebrow">Phase 2 · Hauteur de selle</div>
          <h1>Ta position,<br /><em>mesurée</em> au degré près.</h1>
          <p className="hero-lead">
            Un téléphone, quelques pastilles et ton home trainer : l'outil mesure l'angle de ton genou à chaque coup de pédale et te dit,
            en millimètres, s'il faut toucher à ta selle.
          </p>
          <div className="hero-actions">
            {next ? (
              <Link to={next.to!} className="btn btn-primary">{next.n === 1 ? "Commencer" : "Continuer"} : {next.title} <ArrowRight size={17} /></Link>
            ) : (
              <span className="btn btn-primary" aria-disabled="true">Profil et vélo prêts <Check size={17} /></span>
            )}
            <Link to="/velo" className="btn btn-ghost">Voir mes cotes</Link>
          </div>
          <div className="legend" aria-hidden="true">
            <span><i className="dot body" /> Pastilles sur le corps</span>
            <span><i className="dot bike" /> Repères du vélo</span>
          </div>
        </div>
        <div className="hero-figure">
          <PedalingRider onFlexion={onFlexion} />
          <div className="hud" aria-hidden="true">
            <span className="hud-label">Flexion du genou</span>
            <span className="hud-value" ref={hud}>—</span>
            <span className="hud-sub num">min {Math.round(KNEE_RANGE.min)}° · max {Math.round(KNEE_RANGE.max)}°</span>
          </div>
        </div>
      </section>

      {offline && (
        <div className="alert danger" style={{ marginTop: 20 }} role="alert">
          <Info size={18} />
          <span>Le moteur d'analyse ne répond pas. Lancez-le avec <code>uvicorn posturale.api.main:app</code> dans le dossier <code>backend</code>.</span>
        </div>
      )}

      <div className="section-title">
        <h2>Le parcours</h2>
        <span className="subtle">{steps.filter((s) => s.done).length} / {steps.length} étapes</span>
      </div>
      <div className="steps">
        {steps.map((s) => {
          const Icon = s.icon;
          const body = (
            <>
              <div className="step-top">
                <span className={`icon-tile${s.bike ? " bike" : ""}`}><Icon size={19} /></span>
                {s.done ? <span className="chip ok"><Check size={13} /> Fait</span>
                  : s.to ? <span className="chip warn">À compléter</span>
                    : <span className="chip"><Lock size={12} /> Bientôt</span>}
              </div>
              <div>
                <div className="step-num">Étape {s.n}</div>
                <h3>{s.title}</h3>
              </div>
              <p>{s.text}</p>
            </>
          );
          return s.to
            ? <Link key={s.n} to={s.to} className="step">{body}</Link>
            : <div key={s.n} className="step locked" aria-disabled="true">{body}</div>;
        })}
      </div>

      <div className="section-title"><h2>En un coup d'œil</h2></div>
      <div className="overview">
        <div className="card">
          <div className="card-head">
            <span className="icon-tile bike"><Bike size={19} /></span>
            <div>
              <h2>{[bike?.marque, bike?.modele].filter(Boolean).join(" ") || "Mon vélo"}{bike?.taille ? ` · ${bike.taille}` : ""}</h2>
              <p>{config ? `Configuration en cours : ${config.libelle ?? `n° ${config.id}`}` : "Aucune configuration enregistrée"}</p>
            </div>
          </div>
          <div className="stat-row">
            <Stat label="Hauteur de selle" value={config?.hauteur_selle_mm} unit="mm" />
            <Stat label="Recul de selle" value={config?.recul_selle_mm} unit="mm" />
            <Stat label="Manivelle" value={config?.manivelle_mm} unit="mm" />
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <span className="icon-tile"><User size={19} /></span>
            <div><h2>Mon profil</h2><p>Point de départ et contrôle de vraisemblance</p></div>
          </div>
          <div className="stat-row">
            <Stat label="Taille" value={profile?.taille_cm} unit="cm" />
            <Stat label="Entrejambe" value={profile?.entrejambe_mm} unit="mm" />
            <Stat label="Poids" value={profile?.poids_kg} unit="kg" />
          </div>
        </div>
      </div>

      <p className="disclaimer">
        <Info size={15} />
        Outil d'aide à la décision : les plages affichées sont indicatives et sourcées, les recommandations sont des hypothèses à tester,
        un réglage à la fois. Il ne remplace pas un avis médical : en cas de douleur aiguë, de gonflement ou de douleur qui persiste, consultez un professionnel de santé.
      </p>
    </div>
  );
}
