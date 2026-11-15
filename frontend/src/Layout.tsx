import { useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bike, Bluetooth, Crosshair, FileText, HeartPulse, Home, Lightbulb, Monitor, Moon, Pipette, ShieldCheck, Sliders, Sparkles, Sun, User, Video, Wand2, Package, GraduationCap } from "lucide-react";
import { useTheme, type ThemeChoice } from "./theme";
import { loadEquipment, useEquipment } from "./equipment";

export function LogoMark({ size = 36 }: { size?: number }) {
  // Hanche – genou – cheville avec l'arc de flexion : l'idée de l'outil en un coup d'œil.
  return (
    <span className="logo-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none">
        <path d="M6 3.5 L13.5 12 L9 20.5" stroke="#eef6e4" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M10.2 8.2 A5 5 0 0 0 11.1 15.4" stroke="#b8f34a" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="6" cy="3.5" r="2" fill="#b8f34a" />
        <circle cx="13.5" cy="12" r="2" fill="#b8f34a" />
        <circle cx="9" cy="20.5" r="2" fill="#fb923c" />
      </svg>
    </span>
  );
}

function Logo() {
  return (
    <NavLink to="/" className="logo" aria-label="Accueil — Étude posturale">
      <LogoMark />
      <span className="logo-text">Étude posturale<small>Bike fit à la maison</small></span>
    </NavLink>
  );
}

const MAIN = [
  { to: "/", label: "Accueil", short: "Accueil", icon: Home, end: true, tab: true },
  { to: "/profil", label: "Mon profil", short: "Profil", icon: User },
  { to: "/velo", label: "Mon vélo", short: "Vélo", icon: Bike },
  { to: "/seance", label: "Séances de capture", short: "Séances", icon: Video, tab: true },
  { to: "/seance-guidee", label: "Séance guidée", short: "Guidée", icon: Wand2 },
  { to: "/sante", label: "Santé et ressentis", short: "Santé", icon: HeartPulse, tab: true },
  { to: "/conseils", label: "Recommandations", short: "Conseils", icon: Lightbulb, tab: true },
  { to: "/coach", label: "Coach IA", short: "Coach", icon: Sparkles, tab: true },
];
const TOOLS = [
  { to: "/bienvenue", label: "Guide de démarrage", icon: GraduationCap },
  { to: "/equipement", label: "Mon équipement", icon: Package },
  { to: "/cadrage", label: "Cadrage en direct", icon: Crosshair },
  { to: "/pastilles", label: "Contrôle des pastilles", icon: Pipette },
  { to: "/capteurs", label: "Capteurs et ERG", icon: Bluetooth },
  { to: "/rapport", label: "Rapport", icon: FileText },
  { to: "/reglages-ia", label: "Réglages IA et voix", icon: Sliders },
];

function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const opts: { v: ThemeChoice; icon: typeof Sun; label: string }[] = [
    { v: "light", icon: Sun, label: "Thème clair" },
    { v: "system", icon: Monitor, label: "Thème du système" },
    { v: "dark", icon: Moon, label: "Thème sombre" },
  ];
  return (
    <div className="theme-toggle" role="group" aria-label="Thème">
      {opts.map(({ v, icon: Icon, label }) => (
        <button key={v} type="button" aria-pressed={theme === v} title={label} aria-label={label} onClick={() => setTheme(v)}>
          <Icon size={15} />
        </button>
      ))}
    </div>
  );
}

export default function Layout() {
  const eq = useEquipment();
  const nav = useNavigate();
  const loc = useLocation();
  // Premier lancement : le guide de démarrage s'ouvre tout seul depuis l'accueil
  useEffect(() => {
    if (loc.pathname !== "/") return;
    loadEquipment().then((e) => { if (!e.onboarding_fait) nav("/bienvenue", { replace: true }); }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // Sans aucun capteur Bluetooth, la page Capteurs ne sert à rien
  const noSensors = !!eq && ["trainer_connecte", "capteur_puissance", "cardio"].every((k) => eq.items[k] === false);
  const tools = TOOLS.filter((t) => !(noSensors && t.to === "/capteurs"));
  return (
    <div className="shell">
      <aside className="sidebar">
        <Logo />
        {MAIN.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className="nav-item">
            <Icon size={18} /> {label}
          </NavLink>
        ))}
        <div className="nav-label">Outils</div>
        {tools.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className="nav-item">
            <Icon size={18} /> {label}
          </NavLink>
        ))}
        <div className="sidebar-foot">
          <div className="privacy">
            <ShieldCheck size={16} />
            <span>Tes vidéos restent sur ce PC. Un coach ou une voix en ligne, si tu en choisis un, ne reçoit que du texte.</span>
          </div>
          <ThemeToggle />
        </div>
      </aside>

      <div className="content">
        <header className="mobile-top">
          <Logo />
          <ThemeToggle />
        </header>
        <Outlet />
      </div>

      <nav className="tabbar" aria-label="Navigation principale">
        {MAIN.filter((m) => m.tab).map(({ to, short, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}>
            <Icon size={20} /> {short}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
