import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertTriangle, ArrowLeft, Palette, ArrowRight, Bike, Camera, Check, CheckCircle2, Gauge, HeartPulse, Lock, Package, Pause, RefreshCw,
  User, Video, Volume2, VolumeX, Wand2, Wrench,
} from "lucide-react";
import { LogoMark } from "../Layout";
import PedalingRider from "../components/PedalingRider";
import EquipmentList from "../components/EquipmentList";
import { saveEquipment, useEquipment, type Equipment } from "../equipment";
import { api, http } from "../api";

const STEPS = [
  { id: "bienvenue", titre: "Bienvenue" },
  { id: "fonctionnement", titre: "Comment ça marche" },
  { id: "indispensable", titre: "Le matériel indispensable" },
  { id: "options", titre: "Les options" },
  { id: "parcours", titre: "Ton parcours" },
  { id: "pret", titre: "C'est parti" },
] as const;
const AUTO = "posturale.onboarding.voix";

function readAuto() { try { return localStorage.getItem(AUTO) !== "0"; } catch { return true; } }

/** Première étape du parcours pas encore faite (profil → vélo → séance guidée). */
async function nextStep(): Promise<string> {
  try {
    const [p, c] = await Promise.all([api.getProfile(), api.listConfigs()]);
    if (!(p?.taille_cm && p?.entrejambe_mm)) return "/profil";
    if (!c[0]?.hauteur_selle_mm) return "/velo";
    return "/seance-guidee";
  } catch { return "/profil"; }
}

export default function Onboarding() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const eq = useEquipment();
  const [i, setI] = useState(() => Math.max(0, STEPS.findIndex((s) => s.id === params.get("etape"))));
  const [auto, setAuto] = useState(readAuto);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [started, setStarted] = useState(false); // le navigateur n'autorise le son qu'après un clic : écran d'accueil
  const audio = useRef<HTMLAudioElement | null>(null);
  const step = STEPS[i];

  // Voix off : une piste par écran ; lecture automatique si la personne l'a laissée active
  useEffect(() => {
    const a = new Audio(`/onboarding/${step.id}.mp3`);
    audio.current = a;
    a.onplay = () => setPlaying(true);
    a.onpause = a.onended = () => setPlaying(false);
    a.ontimeupdate = () => setProgress(a.duration ? a.currentTime / a.duration : 0);
    setProgress(0);
    if (auto && started) a.play().catch(() => setPlaying(false));
    return () => { a.pause(); a.src = ""; };
  }, [step.id, started]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = () => {
    const a = audio.current;
    if (!a) return;
    if (a.paused) { if (a.ended) a.currentTime = 0; a.play().catch(() => {}); } else a.pause();
  };
  const setAutoPref = (v: boolean) => {
    setAuto(v);
    try { localStorage.setItem(AUTO, v ? "1" : "0"); } catch { /* stockage indisponible */ }
    if (!v) audio.current?.pause();
  };
  const go = (n: number) => { setI(Math.max(0, Math.min(STEPS.length - 1, n))); window.scrollTo({ top: 0 }); };
  async function finish(to: string) {
    await saveEquipment({ onboarding_fait: true }).catch(() => {});
    nav(to === "suite" ? await nextStep() : to);
  }

  if (!started) {
    const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    return (
      <div className="ob ob-splash">
        <div className="ob-splash-card">
          <h1 className="sr-only">Étude posturale</h1>
          <video className="ob-intro" src="/intro/intro.mp4" poster="/intro/intro-poster.jpg" autoPlay={!reduced} muted playsInline
            aria-label="Présentation : un cycliste pédale, l'application pose les pastilles et mesure l'angle du genou." />
          <p className="ob-lead">
            Filme-toi en pédalant sur ton home trainer : l'application mesure les angles de tes articulations à chaque tour
            et te dit, au millimètre près, quoi régler sur ton vélo. Une modification à la fois, et tes vidéos restent sur ton ordinateur.
          </p>
          {/* Ce clic autorise aussi le navigateur à jouer la voix qui accompagne les écrans suivants */}
          <button className="btn btn-primary ob-splash-go" onClick={() => setStarted(true)}>Commencer <ArrowRight size={20} /></button>
        </div>
      </div>
    );
  }

  return (
    <div className="ob">
      <header className="ob-top">
        <span className="ob-brand"><LogoMark size={32} /> Étude posturale</span>
        <span className="ob-count">Étape {i + 1} sur {STEPS.length}</span>
        <button className="ob-skip" onClick={() => finish("/")}>Passer le guide</button>
      </header>
      <div className="ob-dots" aria-hidden="true">
        {STEPS.map((s, k) => <button key={s.id} className={k === i ? "on" : k < i ? "done" : ""} onClick={() => go(k)} tabIndex={-1} />)}
      </div>

      <main className="ob-main">
        <div className="ob-head">
        <h1>{step.titre}</h1>

        <div className="ob-voice">
          <button className={`ob-play ${playing ? "on" : ""}`} onClick={toggle} aria-label={playing ? "Mettre en pause" : "Écouter l'explication"}>
            {playing ? <Pause size={18} /> : <Volume2 size={18} />}
          </button>
          <div className="ob-voice-text">
            <strong>{playing ? "Je t'explique…" : "Écouter l'explication"}</strong>
            <span className="ob-bar"><span style={{ width: `${progress * 100}%` }} /></span>
          </div>
          <button className="ob-auto" aria-pressed={auto} onClick={() => setAutoPref(!auto)}>
            {auto ? <Volume2 size={14} /> : <VolumeX size={14} />} Lecture auto
          </button>
        </div>
        </div>

        {step.id === "bienvenue" && <Welcome />}
        {step.id === "fonctionnement" && <HowItWorks />}
        {step.id === "indispensable" && (eq ? <Needed eq={eq} /> : <p className="subtle">Chargement…</p>)}
        {step.id === "options" && (eq ? <Options eq={eq} /> : <p className="subtle">Chargement…</p>)}
        {step.id === "parcours" && (eq ? <Path eq={eq} /> : <p className="subtle">Chargement…</p>)}
        {step.id === "pret" && <Ready eq={eq} onGo={finish} />}
      </main>

      <footer className="ob-foot">
        <button className="btn btn-ghost" onClick={() => go(i - 1)} disabled={i === 0}><ArrowLeft size={16} /> Précédent</button>
        {i < STEPS.length - 1
          ? <button className="btn btn-primary" onClick={() => go(i + 1)}>{i === 0 ? "C'est parti" : "Suivant"} <ArrowRight size={16} /></button>
          : <button className="btn btn-primary" onClick={() => finish("suite")}>Continuer <ArrowRight size={16} /></button>}
      </footer>
    </div>
  );
}

function Welcome() {
  return (
    <div className="ob-welcome">
      <div className="ob-figure"><PedalingRider /></div>
      <div className="ob-welcome-text">
      <p className="ob-lead">Cet outil t'aide à <strong>régler ta position sur le vélo</strong>, seul, chez toi.</p>
      <ol className="ob-three">
        <li><Video size={22} /><strong>Tu te filmes</strong><span>une minute de pédalage, de profil</span></li>
        <li><Gauge size={22} /><strong>L'outil mesure</strong><span>les angles de tes articulations, à chaque tour</span></li>
        <li><Wrench size={22} /><strong>Tu règles</strong><span>une seule chose à la fois, en millimètres</span></li>
      </ol>
      <p className="ob-note"><Lock size={15} /> Tes vidéos restent sur ton ordinateur. Si tu choisis un coach IA ou une voix en ligne, ils ne reçoivent que du texte, jamais tes vidéos.</p>
      </div>
    </div>
  );
}

function HowItWorks() {
  const rows = [
    { icon: User, t: "Ton profil et ton vélo", d: "Taille, entrejambe, et les cotes actuelles du vélo (hauteur de selle…).", time: "10 min · une seule fois" },
    { icon: Video, t: "La séance guidée", d: "Pastilles, téléphone, échauffement, puis une minute filmée de chaque côté. Je t'annonce chaque étape.", time: "≈ 40 min" },
    { icon: Gauge, t: "L'analyse", d: "L'ordinateur repère tes articulations image par image et calcule les angles.", time: "2 à 3 min, tout seul" },
    { icon: Wrench, t: "Une modification, puis on vérifie", d: "Tu fais un seul réglage, tu roules 2 ou 3 sorties, puis tu refais une séance pour comparer.", time: "1 à 2 semaines" },
  ];
  return (
    <div className="ob-how">
      <ol className="ob-timeline">
        {rows.map((r, k) => (
          <li key={r.t}>
            <span className="ob-num">{k + 1}</span>
            <div><strong><r.icon size={16} /> {r.t}</strong><p>{r.d}</p><span className="ob-time">{r.time}</span></div>
          </li>
        ))}
      </ol>
      <p className="ob-note"><RefreshCw size={15} /> On recommence jusqu'à ce que les mesures soient dans les plages et que tu n'aies plus de gêne.</p>
    </div>
  );
}

function Needed({ eq }: { eq: Equipment }) {
  const answered = eq.catalogue.filter((c) => c.niveau !== "optionnel" && eq.items[c.id] != null).length;
  const total = eq.catalogue.filter((c) => c.niveau !== "optionnel").length;
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="ob-lead-row">
        <p className="ob-lead">As-tu chaque élément ? Réponds <strong>Oui</strong> ou <strong>Non</strong> : l'outil te dit ce que ça change. <span className="subtle">({answered} / {total})</span></p>
      </div>
      <p className="ob-colors-note"><Palette size={15} /> Couleurs libres : deux couleurs vives bien différentes (corps / vélo). L'app les apprend sur une photo (étalonnage, 1 min).</p>
      <EquipmentList eq={eq} levels={["obligatoire", "recommande"]} />
    </div>
  );
}

function Options({ eq }: { eq: Equipment }) {
  return (
    <div className="stack" style={{ gap: 14 }}>
      <p className="ob-lead">Rien de tout ça n'est nécessaire. Si tu l'as, l'outil s'en sert ; sinon il <strong>s'adapte</strong>.</p>
      <EquipmentList eq={eq} levels={["optionnel"]} />
    </div>
  );
}

function Path({ eq }: { eq: Equipment }) {
  const missing = eq.catalogue.filter((c) => eq.manquants.includes(c.id));
  const [done, setDone] = useState<Record<string, boolean>>({});
  useEffect(() => {
    Promise.all([api.getProfile(), api.listConfigs(), http.get("/pains"), http.get("/sessions")]).then(([p, c, pains, sessions]) => setDone({
      profil: !!(p?.taille_cm && p?.entrejambe_mm), velo: !!c[0]?.hauteur_selle_mm, sante: pains.length > 0,
      seance: sessions.some((x: { captures: { analyses: { status: string }[] }[] }) => x.captures.some((cap) => cap.analyses.some((a) => a.status === "terminee"))),
    })).catch(() => {});
  }, []);
  const steps = [
    { icon: User, t: "Remplir ton profil", d: "Taille, entrejambe, poids, objectif.", tag: "obligatoire", time: "2 min", to: "/profil", done: done.profil },
    { icon: Bike, t: "Décrire ton vélo", d: "Hauteur de selle au mètre ruban (axe du pédalier → dessus de la selle), longueur de manivelle, recul.", tag: "obligatoire", time: "10 min", to: "/velo", done: done.velo },
    { icon: HeartPulse, t: "Noter tes douleurs", d: "Si tu as une gêne (genou, dos…), le moteur en tient compte.", tag: "recommande", time: "3 min", to: "/sante", done: done.sante },
    { icon: Package, t: "Préparer le matériel", d: missing.length ? `À te procurer : ${missing.map((m) => m.nom.toLowerCase()).join(", ")}.` : "Tout l'indispensable est là.", tag: "obligatoire", time: missing.length ? "avant la séance" : "prêt", done: !missing.length },
    { icon: Camera, t: "Faire ta première séance guidée", d: "Je te guide de la pose des pastilles jusqu'au débrief.", tag: "obligatoire", time: "≈ 40 min", to: "/seance-guidee", done: done.seance },
    { icon: Wrench, t: "Appliquer une modification, puis vérifier", d: "Le débrief propose un seul réglage. Après 2–3 sorties, nouvelle séance pour comparer.", tag: "obligatoire", time: "ensuite" },
  ];
  return (
    <div className="ob-path-grid">
      <ol className="ob-path">
        {steps.map((s, k) => (
          <li key={s.t} className={s.done ? "done" : ""}>
            <span className="ob-num">{s.done ? <Check size={14} /> : k + 1}</span>
            <div className="grow">
              <div className="ob-path-head"><strong>{s.t}</strong><span className={`eq-tag ${s.tag}`}>{s.tag === "obligatoire" ? "Obligatoire" : "Recommandé"}</span><span className="ob-time">{s.done ? "fait" : s.time}</span></div>
              <p>{s.d}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="ob-path-side">
      {missing.length === 0 && eq.adaptations.length === 0 && (
        <div className="ob-adapt"><strong><Check size={16} /> Tout l'indispensable est là</strong><ul><li>Tu peux enchaîner sur ton profil, ton vélo, puis la séance guidée.</li></ul></div>
      )}
      {missing.length > 0 && (
        <div className="ob-missing">
          <AlertTriangle size={20} />
          <div>
            <strong>Avant ta première séance, il te manque {missing.length > 1 ? `${missing.length} éléments obligatoires` : "un élément obligatoire"} :</strong>
            <ul>{missing.map((m) => <li key={m.id}><b>{m.nom}</b> — {m.sans}</li>)}</ul>
          </div>
        </div>
      )}
      {eq.adaptations.length > 0 && (
        <div className="ob-adapt">
          <strong><Wand2 size={16} /> L'outil s'adapte à ton matériel</strong>
          <ul>{eq.adaptations.map((a) => <li key={a.id}><b>{a.nom}</b> : {a.texte.replace(/^L'outil s'adapte : /, "")}</li>)}</ul>
        </div>
      )}
      </div>
    </div>
  );
}

function Ready({ eq, onGo }: { eq: Equipment | null; onGo: (to: string) => void }) {
  return (
    <div className="ob-ready">
      {eq && !eq.pret ? <AlertTriangle size={52} className="ob-warn-icon" /> : <CheckCircle2 size={56} />}
      <p className="ob-lead">{eq && !eq.pret ? "Procure-toi le matériel obligatoire manquant, puis :" : "Tu as tout ce qu'il faut."} commence par ton <strong>profil</strong>, puis ton <strong>vélo</strong>, et lance la <strong>séance guidée</strong>.</p>
      <div className="ob-ready-actions">
        <button className="btn btn-primary" onClick={() => onGo("suite")}><ArrowRight size={16} /> Continuer mon parcours</button>
        <button className="btn btn-ghost" onClick={() => onGo("/")}>Aller à l'accueil</button>
      </div>
      <p className="ob-note">Ce guide reste accessible dans le menu : <Link className="link" to="/bienvenue">Guide de démarrage</Link> · <Link className="link" to="/equipement">Mon équipement</Link></p>
    </div>
  );
}
