// Semelles vues de dessous : position avant/arrière, rotation et décalage latéral de chaque cale.
import type { Values } from "../api";

const SOLE = "M80,10 C120,10 136,60 133,112 C130,162 118,200 112,230 C108,252 52,252 48,230 C42,200 30,162 27,112 C24,60 40,10 80,10Z";

function Shoe({ side, active, values }: { side: "g" | "d"; active: string | null; values: Values }) {
  const rot = Number(values[`cales_rotation_${side}_deg`] ?? 0) || 0;
  const lat = Number(values[`cales_lateral_${side}_mm`] ?? 0) || 0;
  const adv = Number(values.cales_avance_mm ?? 0) || 0;
  // Schéma indicatif : les valeurs saisies déplacent la cale (+ = vers l'extérieur, talon vers l'intérieur)
  const outward = side === "g" ? -1 : 1;
  const on = (k: string) => active === k;
  const hl = { stroke: "var(--brand-text)", strokeWidth: 2.5 };
  const mute = { stroke: "var(--text-3)", strokeWidth: 1.5, opacity: 0.6 };
  return (
    <svg viewBox="0 0 160 260" role="img" aria-label={`Semelle ${side === "g" ? "gauche" : "droite"} vue de dessous avec la cale`}>
      <path d={SOLE} transform={side === "g" ? "translate(160,0) scale(-1,1)" : undefined}
        style={{ fill: "var(--surface-3)", stroke: "var(--line-strong)", strokeWidth: 2 }} />
      {/* axe de la pédale = tête du 1er métatarse (repère) */}
      <line x1="18" y1="86" x2="142" y2="86" style={{ stroke: "var(--bike)", strokeDasharray: "4 4", strokeWidth: 1.5 }} />
      <g transform={`translate(${80 + outward * lat * 2},${86 - adv * 2}) rotate(${-outward * rot})`}>
        <path d="M0,-30 L28,22 L-28,22Z" style={{ fill: "var(--text-2)", opacity: 0.85 }} />
        <circle r="3.5" style={{ fill: "var(--bike)" }} />
      </g>
      {/* avance */}
      <g style={on("cales_avance_mm") ? hl : mute} fill="none" strokeLinecap="round">
        <line x1="150" y1="60" x2="150" y2="112" />
        <path d="M145,66 L150,60 L155,66 M145,106 L150,112 L155,106" />
      </g>
      {/* rotation */}
      <g style={on(`cales_rotation_${side}_deg`) ? hl : mute} fill="none" strokeLinecap="round">
        <path d="M52,132 A40,40 0 0 0 108,132" />
        <path d="M102,126 L108,132 L100,136" />
      </g>
      {/* latéral */}
      <g style={on(`cales_lateral_${side}_mm`) ? hl : mute} fill="none" strokeLinecap="round">
        <line x1="48" y1="160" x2="112" y2="160" />
        <path d="M54,155 L48,160 L54,165 M106,155 L112,160 L106,165" />
      </g>
    </svg>
  );
}

export default function CleatDiagram({ active, values }: { active: string | null; values: Values }) {
  return (
    <div className="cleat-figure">
      <figure><Shoe side="g" active={active} values={values} /><figcaption>Pied gauche</figcaption></figure>
      <figure><Shoe side="d" active={active} values={values} /><figcaption>Pied droit</figcaption></figure>
    </div>
  );
}

export const CLEAT_INFO: Record<string, { title: string; how: string }> = {
  cales_avance_mm: { title: "Position avant / arrière", how: "Distance entre l'axe de la cale et ta référence (souvent la tête du 1er métatarse, pointillé orange). + = cale vers l'avant." },
  cales_rotation_g_deg: { title: "Rotation de la cale gauche", how: "Angle de la cale par rapport à l'axe de la chaussure. + = talon vers l'intérieur (vers le cadre)." },
  cales_rotation_d_deg: { title: "Rotation de la cale droite", how: "Angle de la cale par rapport à l'axe de la chaussure. + = talon vers l'intérieur (vers le cadre)." },
  cales_lateral_g_mm: { title: "Décalage latéral gauche", how: "+ = pied plus éloigné du cadre (cale décalée vers l'intérieur de la semelle)." },
  cales_lateral_d_mm: { title: "Décalage latéral droit", how: "+ = pied plus éloigné du cadre (cale décalée vers l'intérieur de la semelle)." },
};
