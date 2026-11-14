// Schéma du vélo avec les cotes : la cote du champ en cours de saisie s'allume et s'explique.
import type { Values } from "../api";
import {
  BB, CRANK, FRAME_PATHS, FRONT, HEAD_TOP, REAR, SADDLE_NOSE, SADDLE_TOP, SEAT_TUBE_DEG, STEM_END, WHEEL_R,
  add, pedalAt, pt, type P,
} from "./bikeGeometry";

export type DimKey = "saddleHeight" | "setback" | "tilt" | "drop" | "saddleBar" | "stem" | "crank" | "sta" | "stack" | "reach";

export const FIELD_TO_DIM: Record<string, DimKey> = {
  hauteur_selle_mm: "saddleHeight",
  recul_selle_mm: "setback",
  inclinaison_selle_deg: "tilt",
  drop_selle_cintre_mm: "drop",
  distance_selle_cintre_mm: "saddleBar",
  potence_mm: "stem",
  potence_angle_deg: "stem",
  entretoises_mm: "stem",
  manivelle_mm: "crank",
  angle_tube_selle_deg: "sta",
  stack_mm: "stack",
  reach_mm: "reach",
};

export const DIM_INFO: Record<DimKey, { title: string; how: string; field: string; unit: string }> = {
  saddleHeight: { title: "Hauteur de selle", field: "hauteur_selle_mm", unit: "mm", how: "Du centre de l'axe de pédalier au dessus de la selle, en suivant le tube de selle. Le réglage n° 1 pour le genou." },
  setback: { title: "Recul de selle", field: "recul_selle_mm", unit: "mm", how: "Distance horizontale entre la verticale de l'axe de pédalier et le bec de selle (niveau ou fil à plomb)." },
  tilt: { title: "Inclinaison de selle", field: "inclinaison_selle_deg", unit: "°", how: "Niveau posé sur la selle, du bec à l'arrière. Proche de 0° en général." },
  drop: { title: "Drop selle–cintre", field: "drop_selle_cintre_mm", unit: "mm", how: "Différence de hauteur entre le dessus de la selle et le dessus du cintre, vélo de niveau." },
  saddleBar: { title: "Distance selle–cintre", field: "distance_selle_cintre_mm", unit: "mm", how: "Du bec de selle au centre du cintre (au niveau de la potence)." },
  stem: { title: "Potence", field: "potence_mm", unit: "mm", how: "Longueur (axe du pivot → axe du cintre), angle gravé sur la potence, entretoises sous la potence." },
  crank: { title: "Longueur de manivelle", field: "manivelle_mm", unit: "mm", how: "Gravée au dos de la manivelle (ex. 175). Influe sur la flexion du genou et de la hanche en haut du coup de pédale." },
  sta: { title: "Angle du tube de selle", field: "angle_tube_selle_deg", unit: "°", how: "Sur la fiche géométrie du constructeur. Sert à convertir l'angle du genou en millimètres de selle." },
  stack: { title: "Stack", field: "stack_mm", unit: "mm", how: "Hauteur verticale entre l'axe de pédalier et le haut du tube de direction (fiche géométrie)." },
  reach: { title: "Reach", field: "reach_mm", unit: "mm", how: "Distance horizontale entre l'axe de pédalier et le haut du tube de direction (fiche géométrie)." },
};

function Label({ at, text }: { at: P; text: string }) {
  const w = Math.max(34, text.length * 7.9 + 16);
  return (
    <g>
      <rect className="dim-bg" x={at[0] - w / 2} y={at[1] - 12} width={w} height={23} rx={7} />
      <text x={at[0]} y={at[1] + 4} textAnchor="middle">{text}</text>
    </g>
  );
}

/** Cote : ligne a→b avec petites barres aux extrémités et étiquette au milieu. */
function Dim({ id, a, b, label, active, labelOffset = [0, 0] }: { id: DimKey; a: P; b: P; label: string; active: boolean; labelOffset?: P }) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l = Math.hypot(dx, dy) || 1;
  const n: P = [(-dy / l) * 5, (dx / l) * 5];
  const mid: P = add([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], labelOffset);
  return (
    <g className={`dim${active ? " active" : ""}`} data-dim={id}>
      <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} />
      <line x1={a[0] - n[0]} y1={a[1] - n[1]} x2={a[0] + n[0]} y2={a[1] + n[1]} />
      <line x1={b[0] - n[0]} y1={b[1] - n[1]} x2={b[0] + n[0]} y2={b[1] + n[1]} />
      <Label at={mid} text={label} />
    </g>
  );
}

const guide = { stroke: "var(--line-strong)", strokeDasharray: "3 4", strokeWidth: 1 };

export default function BikeDiagram({ active, values }: { active: DimKey | null; values: Values }) {
  const val = (k: DimKey, fallback: string) => {
    const info = DIM_INFO[k];
    const v = values[info.field];
    return v == null || v === "" ? fallback : `${v} ${info.unit}`;
  };
  const is = (k: DimKey) => active === k;

  const rad = (d: number) => (d * Math.PI) / 180;
  const seatN: P = [-Math.sin(rad(SEAT_TUBE_DEG)), Math.cos(rad(SEAT_TUBE_DEG))]; // normale vers l'arrière
  const off = (p: P, k: number): P => [p[0] + seatN[0] * k, p[1] + seatN[1] * k];
  const shA = off(BB, 26), shB = off(SADDLE_TOP, 26);
  const setbackY = SADDLE_TOP[1] - 34;
  const dropX = 486;
  const pedal = pedalAt(110);
  const stackX = HEAD_TOP[0] + 30;
  const reachY = 14;

  return (
    <svg viewBox="0 0 520 360" className={active ? "dims-dim" : undefined} role="img"
      aria-label="Schéma d'un vélo de route avec les cotes à relever : hauteur et recul de selle, drop, distance selle–cintre, potence, manivelle, stack et reach">
      {/* Vélo */}
      <g style={{ stroke: "var(--text-3)", fill: "none", strokeLinecap: "round", strokeLinejoin: "round" }} opacity={0.75}>
        {[REAR, FRONT].map((c, i) => <circle key={i} cx={c[0]} cy={c[1]} r={WHEEL_R} strokeWidth={3} />)}
        <path d={FRAME_PATHS.frame} strokeWidth={5} style={{ stroke: "var(--text-2)" }} />
        <path d={FRAME_PATHS.fork} strokeWidth={4} style={{ stroke: "var(--text-2)" }} />
        <path d={FRAME_PATHS.seatpost} strokeWidth={4} />
        <path d={FRAME_PATHS.bar} strokeWidth={4} />
        <path d={FRAME_PATHS.stem} strokeWidth={is("stem") ? 7 : 4} style={is("stem") ? { stroke: "var(--brand-text)" } : undefined} />
        <circle cx={BB[0]} cy={BB[1]} r={CRANK + 6} strokeWidth={2} />
        <line x1={BB[0]} y1={BB[1]} x2={pedal[0]} y2={pedal[1]} strokeWidth={is("crank") ? 7 : 4} style={is("crank") ? { stroke: "var(--brand-text)" } : undefined} />
      </g>
      <path d={FRAME_PATHS.saddle} style={{ fill: is("tilt") ? "var(--brand-text)" : "var(--text-2)" }} />
      <circle cx={BB[0]} cy={BB[1]} r={5} style={{ fill: "var(--bike)" }} />
      <circle cx={pedal[0]} cy={pedal[1]} r={4.5} style={{ fill: "var(--bike)" }} />

      {/* Repères */}
      <line x1={BB[0]} y1={BB[1]} x2={BB[0]} y2={setbackY - 6} style={guide} />
      <line x1={SADDLE_TOP[0]} y1={SADDLE_TOP[1]} x2={dropX + 6} y2={SADDLE_TOP[1]} style={guide} />
      <line x1={STEM_END[0]} y1={STEM_END[1] - 3} x2={dropX + 6} y2={STEM_END[1] - 3} style={guide} />
      <line x1={BB[0]} y1={BB[1]} x2={shA[0]} y2={shA[1]} style={guide} />
      <line x1={SADDLE_TOP[0]} y1={SADDLE_TOP[1]} x2={shB[0]} y2={shB[1]} style={guide} />

      {/* Cotes */}
      <Dim id="saddleHeight" a={shA} b={shB} label={val("saddleHeight", "Hauteur")} active={is("saddleHeight")} labelOffset={[-22, 0]} />
      <Dim id="setback" a={[SADDLE_NOSE[0], setbackY]} b={[BB[0], setbackY]} label={val("setback", "Recul")} active={is("setback")} labelOffset={[0, -16]} />
      <Dim id="drop" a={[dropX, SADDLE_TOP[1]]} b={[dropX, STEM_END[1] - 3]} label={val("drop", "Drop")} active={is("drop")} labelOffset={[-4, 26]} />
      <Dim id="saddleBar" a={add(SADDLE_NOSE, [0, -16])} b={add(STEM_END, [0, -18])} label={val("saddleBar", "Selle–cintre")} active={is("saddleBar")} labelOffset={[0, -12]} />
      <Dim id="stack" a={[stackX, BB[1]]} b={[stackX, HEAD_TOP[1]]} label={val("stack", "Stack")} active={is("stack")} labelOffset={[0, 30]} />
      <Dim id="reach" a={[BB[0], reachY]} b={[HEAD_TOP[0], reachY]} label={val("reach", "Reach")} active={is("reach")} />

      <g className={`dim${is("sta") ? " active" : ""}`}>
        <path className="dim-line" fill="none" d={`M${pt(add(BB, [-46, 0]))} A46,46 0 0 1 ${pt(add(BB, [-46 * Math.cos(rad(SEAT_TUBE_DEG)), -46 * Math.sin(rad(SEAT_TUBE_DEG))]))}`} />
        <line x1={BB[0]} y1={BB[1]} x2={BB[0] - 60} y2={BB[1]} />
        <Label at={add(BB, [-74, -20])} text={val("sta", "Angle")} />
      </g>
      {(is("crank") || is("stem") || is("tilt")) && (
        <g className="dim active">
          {is("crank") && <Label at={add(pedal, [34, 14])} text={val("crank", "Manivelle")} />}
          {is("stem") && <Label at={add(STEM_END, [-6, -22])} text={val("stem", "Potence")} />}
          {is("tilt") && <Label at={add(SADDLE_TOP, [0, -22])} text={val("tilt", "Inclinaison")} />}
        </g>
      )}
    </svg>
  );
}
