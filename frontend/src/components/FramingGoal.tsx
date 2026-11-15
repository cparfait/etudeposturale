import { Target } from "lucide-react";
import PedalingRider from "./PedalingRider";

/** Ce qu'on cherche à obtenir : l'image attendue et la position du trépied vue de dessus. */
export default function FramingGoal() {
  return (
    <section className="card fg">
      <div className="card-head">
        <span className="icon-tile"><Target size={19} /></span>
        <div><h2>Le but à atteindre</h2><p>Quand l'image ressemble à celle-ci, les contrôles passent au vert.</p></div>
      </div>
      <div className="fg-grid">
        <figure>
          <div className="fg-frame" aria-label="Image attendue : cycliste entier, de profil, centré, avec de la marge">
            <div className="fg-rider"><PedalingRider /></div>
            <span className="fg-line" style={{ top: "30%" }} />
            <span className="fg-line" style={{ top: "60%" }} />
            <span className="fg-tag">hanche entre les pointillés</span>
          </div>
          <figcaption>Ce que le téléphone doit voir : le cycliste en entier, de profil, avec de la marge tout autour.</figcaption>
        </figure>
        <figure>
          <svg viewBox="0 0 260 160" className="fg-top" role="img" aria-label="Vue de dessus : trépied à 2,5 à 3 mètres, perpendiculaire au vélo">
            <g stroke="currentColor" strokeLinecap="round" fill="none">
              {/* vélo vu de dessus */}
              <line x1="60" y1="34" x2="200" y2="34" strokeWidth="6" />
              <line x1="182" y1="22" x2="182" y2="46" strokeWidth="4" />
              <rect x="88" y="29" width="22" height="10" rx="4" strokeWidth="3" />
              {/* axe perpendiculaire */}
              <line x1="130" y1="44" x2="130" y2="116" strokeWidth="1.5" strokeDasharray="4 4" opacity="0.6" />
              <path d="M124 52 L130 44 L136 52" strokeWidth="1.5" opacity="0.6" />
            </g>
            <text x="138" y="84" className="fg-txt">2,5 à 3 m</text>
            <g className="fg-phone">
              <circle cx="130" cy="126" r="11" />
              <rect x="120" y="117" width="20" height="9" rx="2" />
            </g>
            <text x="130" y="153" className="fg-txt" textAnchor="middle">trépied à hauteur de selle</text>
            <text x="60" y="20" className="fg-txt muted">vélo</text>
          </svg>
          <figcaption>Vu de dessus : le téléphone bien en face du pédalier, à angle droit, objectif 1x.</figcaption>
        </figure>
      </div>
    </section>
  );
}
