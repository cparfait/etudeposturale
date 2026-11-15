// Carte du corps cliquable (face et dos). Une zone = (id de zone, côté).
export interface ZoneHit { zone: string; cote: string; label: string }
interface Z { zone: string; cote: string; cx: number; cy: number; rx: number; ry: number }

// Vue de face : le côté droit du cycliste est à GAUCHE de l'image. Vue de dos : le côté droit est à DROITE.
const FRONT: Z[] = [
  { zone: "epaule", cote: "D", cx: 62, cy: 72, rx: 13, ry: 10 }, { zone: "epaule", cote: "G", cx: 138, cy: 72, rx: 13, ry: 10 },
  { zone: "main", cote: "D", cx: 36, cy: 214, rx: 10, ry: 12 }, { zone: "main", cote: "G", cx: 164, cy: 214, rx: 10, ry: 12 },
  { zone: "hanche_avant", cote: "D", cx: 82, cy: 196, rx: 12, ry: 10 }, { zone: "hanche_avant", cote: "G", cx: 118, cy: 196, rx: 12, ry: 10 },
  { zone: "perinee", cote: "centre", cx: 100, cy: 214, rx: 7, ry: 7 },
  { zone: "cuisse_avant", cote: "D", cx: 82, cy: 245, rx: 13, ry: 24 }, { zone: "cuisse_avant", cote: "G", cx: 118, cy: 245, rx: 13, ry: 24 },
  { zone: "genou_avant", cote: "D", cx: 82, cy: 296, rx: 11, ry: 11 }, { zone: "genou_avant", cote: "G", cx: 118, cy: 296, rx: 11, ry: 11 },
  { zone: "genou_interieur", cote: "D", cx: 94, cy: 292, rx: 4, ry: 7 }, { zone: "genou_interieur", cote: "G", cx: 106, cy: 292, rx: 4, ry: 7 },
  { zone: "genou_exterieur", cote: "D", cx: 69, cy: 292, rx: 4, ry: 7 }, { zone: "genou_exterieur", cote: "G", cx: 131, cy: 292, rx: 4, ry: 7 },
  { zone: "genou_menisque_int", cote: "D", cx: 92, cy: 307, rx: 5, ry: 4 }, { zone: "genou_menisque_int", cote: "G", cx: 108, cy: 307, rx: 5, ry: 4 },
  { zone: "genou_menisque_ext", cote: "D", cx: 71, cy: 307, rx: 5, ry: 4 }, { zone: "genou_menisque_ext", cote: "G", cx: 129, cy: 307, rx: 5, ry: 4 },
  { zone: "coude", cote: "D", cx: 46, cy: 142, rx: 7, ry: 9 }, { zone: "coude", cote: "G", cx: 154, cy: 142, rx: 7, ry: 9 },
  { zone: "pied", cote: "D", cx: 80, cy: 404, rx: 12, ry: 8 }, { zone: "pied", cote: "G", cx: 120, cy: 404, rx: 12, ry: 8 },
];
const BACK: Z[] = [
  { zone: "nuque", cote: "centre", cx: 100, cy: 56, rx: 9, ry: 7 },
  { zone: "epaule", cote: "G", cx: 62, cy: 72, rx: 13, ry: 10 }, { zone: "epaule", cote: "D", cx: 138, cy: 72, rx: 13, ry: 10 },
  { zone: "haut_dos", cote: "centre", cx: 100, cy: 100, rx: 18, ry: 16 },
  { zone: "coude", cote: "G", cx: 46, cy: 142, rx: 7, ry: 9 }, { zone: "coude", cote: "D", cx: 154, cy: 142, rx: 7, ry: 9 },
  { zone: "lombaires", cote: "centre", cx: 100, cy: 170, rx: 18, ry: 12 },
  { zone: "hanche_laterale", cote: "G", cx: 64, cy: 194, rx: 7, ry: 12 }, { zone: "hanche_laterale", cote: "D", cx: 136, cy: 194, rx: 7, ry: 12 },
  { zone: "fessier", cote: "G", cx: 84, cy: 208, rx: 14, ry: 12 }, { zone: "fessier", cote: "D", cx: 116, cy: 208, rx: 14, ry: 12 },
  { zone: "cuisse_arriere", cote: "G", cx: 82, cy: 250, rx: 13, ry: 22 }, { zone: "cuisse_arriere", cote: "D", cx: 118, cy: 250, rx: 13, ry: 22 },
  { zone: "genou_arriere_ext", cote: "G", cx: 74, cy: 297, rx: 6, ry: 10 }, { zone: "genou_arriere_int", cote: "G", cx: 89, cy: 297, rx: 6, ry: 10 },
  { zone: "genou_arriere_int", cote: "D", cx: 111, cy: 297, rx: 6, ry: 10 }, { zone: "genou_arriere_ext", cote: "D", cx: 126, cy: 297, rx: 6, ry: 10 },
  { zone: "mollet", cote: "G", cx: 82, cy: 345, rx: 10, ry: 22 }, { zone: "mollet", cote: "D", cx: 118, cy: 345, rx: 10, ry: 22 },
];

const BODY = "M100,8 a22,22 0 1 1 -0.1,0 Z M78,56 Q100,50 122,56 L148,66 Q156,70 156,84 L166,200 Q168,214 160,222 L152,212 L144,120 L138,118 L134,200 Q138,214 132,226 L130,300 L128,390 Q132,410 120,412 L108,410 L106,300 L102,226 L98,226 L94,300 L92,410 L80,412 Q68,410 72,390 L70,300 L68,226 Q62,214 66,200 L62,118 L56,120 L48,212 L40,222 Q32,214 34,200 L44,84 Q44,70 52,66 Z";

export default function BodyMap({ labels, selected, pains, onPick }: {
  labels: Record<string, string>;
  selected: { zone: string; cote: string } | null;
  pains: { zone: string; cote: string; intensite: number }[];
  onPick: (z: ZoneHit) => void;
}) {
  const view = (zones: Z[], title: string) => (
    <figure>
      <svg viewBox="0 0 200 420" role="group" aria-label={`Silhouette ${title}`}>
        <path className="bm-body" d={BODY} />
        {zones.map((z) => {
          const pain = pains.find((p) => p.zone === z.zone && p.cote === z.cote);
          const sel = selected?.zone === z.zone && selected?.cote === z.cote;
          const side = z.cote === "G" ? "gauche" : z.cote === "D" ? "droit(e)" : "";
          const label = `${labels[z.zone] ?? z.zone} ${side}`.trim();
          return (
            <ellipse key={`${z.zone}-${z.cote}`} className={`bm-zone${sel ? " sel" : ""}${pain ? " pain" : ""}`}
              style={pain ? ({ "--i": 0.15 + pain.intensite / 14 } as React.CSSProperties) : undefined}
              cx={z.cx} cy={z.cy} rx={z.rx} ry={z.ry} tabIndex={0} role="button" aria-pressed={sel} aria-label={label}
              onClick={() => onPick({ zone: z.zone, cote: z.cote, label })}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onPick({ zone: z.zone, cote: z.cote, label })}>
              <title>{label}{pain ? ` — ${pain.intensite}/10` : ""}</title>
            </ellipse>
          );
        })}
        <text x="18" y="414" className="axis-text" style={{ fill: "var(--text-3)", fontSize: 11 }}>{title === "de face" ? "D" : "G"}</text>
        <text x="176" y="414" className="axis-text" style={{ fill: "var(--text-3)", fontSize: 11 }}>{title === "de face" ? "G" : "D"}</text>
      </svg>
      <figcaption>Vue {title}</figcaption>
    </figure>
  );
  return <div className="bodymap">{view(FRONT, "de face")}{view(BACK, "de dos")}</div>;
}
