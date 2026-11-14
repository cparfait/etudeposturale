// Géométrie schématique d'un vélo de route en coordonnées SVG (y vers le bas), viewBox 0 0 520 340.
// Partagée par le cycliste animé (accueil) et le schéma des cotes (Mon vélo).

export type P = [number, number];

const rad = (d: number) => (d * Math.PI) / 180;
export const add = (a: P, b: P): P => [a[0] + b[0], a[1] + b[1]];
export const sub = (a: P, b: P): P => [a[0] - b[0], a[1] - b[1]];
export const len = (a: P) => Math.hypot(a[0], a[1]);

export const SEAT_TUBE_DEG = 73.5;
const seatDir: P = [-Math.cos(rad(SEAT_TUBE_DEG)), -Math.sin(rad(SEAT_TUBE_DEG))]; // vers le haut et l'arrière
const along = (d: number): P => add(BB, [seatDir[0] * d, seatDir[1] * d]);

export const WHEEL_R = 92;
export const REAR: P = [118, 258];
export const FRONT: P = [424, 258];
export const BB: P = [258, 276];
export const CRANK = 38;
export const SADDLE_TOP: P = along(204);
export const SEAT_CLUSTER: P = along(158);
export const SADDLE_NOSE: P = add(SADDLE_TOP, [30, 1]);
export const SADDLE_TAIL: P = add(SADDLE_TOP, [-28, -2]);
export const HEAD_TOP: P = [384, 126];
export const HEAD_BOTTOM: P = [393, 168];
export const STEM_END: P = [412, 118];
export const HOODS: P = [436, 126];

export const pt = (p: P) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`;

export const FRAME_PATHS = {
  frame: `M${pt(BB)} L${pt(SEAT_CLUSTER)} L${pt(HEAD_TOP)} L${pt(HEAD_BOTTOM)} Z M${pt(BB)} L${pt(REAR)} L${pt(SEAT_CLUSTER)}`,
  seatpost: `M${pt(SEAT_CLUSTER)} L${pt(add(SADDLE_TOP, [0, 6]))}`,
  fork: `M${pt(HEAD_BOTTOM)} Q${pt([404, 220])} ${pt(FRONT)}`,
  stem: `M${pt(HEAD_TOP)} L${pt([385, 116])} L${pt(STEM_END)}`,
  bar: `M${pt(STEM_END)} C 432 114, 446 120, 444 136 C 442 152, 430 160, 418 158`,
  saddle: `M${pt(SADDLE_TAIL)} Q${pt(add(SADDLE_TOP, [0, -4]))} ${pt(SADDLE_NOSE)} L${pt(add(SADDLE_NOSE, [-4, 4]))} Q${pt(add(SADDLE_TOP, [-2, 5]))} ${pt(add(SADDLE_TAIL, [2, 6]))} Z`,
};

// ---------------------------------------------------------------- cycliste
export const HIP: P = add(SADDLE_TOP, [-6, -12]);
export const THIGH = 124;
export const SHANK = 126;
export const ANKLE_OFFSET: P = [-7, -15]; // cheville par rapport à l'axe de pédale
export const SHOULDER: P = [322, 54];
export const ELBOW: P = [372, 94];
export const HEAD: P = [352, 30];

/** Position du pied pour un angle de manivelle θ (degrés, 0 = haut, 90 = avant). */
export function pedalAt(thetaDeg: number): P {
  return [BB[0] + CRANK * Math.sin(rad(thetaDeg)) * 1, BB[1] - CRANK * Math.cos(rad(thetaDeg))];
}

/** Genou : intersection des cercles (hanche, cuisse) et (cheville, jambe), côté avant. */
export function kneeFor(hip: P, ankle: P, l1 = THIGH, l2 = SHANK): P {
  const d = sub(ankle, hip);
  const dist = Math.min(len(d), l1 + l2 - 0.001);
  const a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist);
  const h = Math.sqrt(Math.max(l1 * l1 - a * a, 0));
  const u: P = [d[0] / len(d), d[1] / len(d)];
  const base = add(hip, [u[0] * a, u[1] * a]);
  const k1: P = [base[0] - u[1] * h, base[1] + u[0] * h];
  const k2: P = [base[0] + u[1] * h, base[1] - u[0] * h];
  return k1[0] > k2[0] ? k1 : k2;
}

/** Flexion (0° = alignés) au point b entre b→a et b→c. */
export function flexionAt(a: P, b: P, c: P): number {
  const v1 = sub(a, b), v2 = sub(c, b);
  const cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (len(v1) * len(v2));
  return 180 - (Math.acos(Math.max(-1, Math.min(1, cos))) * 180) / Math.PI;
}

export function legAt(thetaDeg: number) {
  const pedal = pedalAt(thetaDeg);
  const ankle = add(pedal, ANKLE_OFFSET);
  const knee = kneeFor(HIP, ankle);
  const heel = add(ankle, [-15, 8]);
  const toe = add(pedal, [24, 2]);
  return { pedal, ankle, knee, heel, toe, flexion: flexionAt(HIP, knee, ankle) };
}

/** Extension max et flexion max sur un tour (pour le HUD). */
export const KNEE_RANGE = (() => {
  let min = 180, max = 0;
  for (let t = 0; t < 360; t += 1) {
    const f = legAt(t).flexion;
    min = Math.min(min, f);
    max = Math.max(max, f);
  }
  return { min, max };
})();
