import { useEffect, useRef, useState } from "react";
import {
  BACK_CTRL, BB, CRANK, ELBOW, FRAME_PATHS, FRONT, HEAD, HEAD_R, HIP, HOODS, KNEE_RANGE, REAR, SCENE_VIEWBOX, SHOULDER, WHEEL_R,
  legAt, pt, sub, type P,
} from "./bikeGeometry";

const CADENCE_RPM = 80;
const BODY = "#b8f34a";
const BIKE = "#fb923c";

function arcPath(center: P, from: P, to: P, r: number) {
  const a1 = Math.atan2(from[1] - center[1], from[0] - center[0]);
  const a2 = Math.atan2(to[1] - center[1], to[0] - center[0]);
  let delta = a2 - a1;
  while (delta > Math.PI) delta -= 2 * Math.PI;
  while (delta < -Math.PI) delta += 2 * Math.PI;
  const s: P = [center[0] + r * Math.cos(a1), center[1] + r * Math.sin(a1)];
  const e: P = [center[0] + r * Math.cos(a1 + delta), center[1] + r * Math.sin(a1 + delta)];
  return `M${pt(s)} A${r},${r} 0 0 ${delta > 0 ? 1 : 0} ${pt(e)}`;
}

/** Cycliste schématique qui pédale, avec pastilles et angle du genou mesuré en direct. */
export default function PedalingRider({ onFlexion }: { onFlexion?: (f: number) => void }) {
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [theta, setTheta] = useState(reduced ? 168 : 0);
  const raf = useRef(0);

  useEffect(() => {
    if (reduced) return;
    const t0 = performance.now();
    const tick = (now: number) => {
      setTheta((((now - t0) / 1000) * 360 * CADENCE_RPM) / 60 % 360);
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [reduced]);

  const near = legAt(theta);
  const far = legAt((theta + 180) % 360);
  useEffect(() => onFlexion?.(near.flexion), [near.flexion, onFlexion]);

  // Arc de flexion : entre le prolongement de la cuisse et la jambe
  const thighDir = sub(near.knee, HIP);
  const ext: P = [near.knee[0] + thighDir[0] * 0.3, near.knee[1] + thighDir[1] * 0.3];
  const atBottom = near.flexion < KNEE_RANGE.min + 4;

  const limb = (a: P, b: P) => `M${pt(a)} L${pt(b)}`;

  return (
    <svg viewBox={SCENE_VIEWBOX} role="img" aria-label="Cycliste schématique en train de pédaler, avec les pastilles sur la hanche, le genou et la cheville, et l'angle du genou mesuré en direct">
      <defs>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={BODY} stopOpacity="0.55" />
          <stop offset="100%" stopColor={BODY} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Sol et home trainer */}
      <line x1="40" y1="352" x2="500" y2="352" stroke="rgb(255 255 255 / 0.12)" />
      <path d={`M${REAR[0] - 34},350 L${REAR[0]},${REAR[1]} L${REAR[0] + 34},350`} stroke="rgb(255 255 255 / 0.22)" strokeWidth="5" fill="none" strokeLinecap="round" />

      {/* Roues */}
      {[REAR, FRONT].map((c, i) => (
        <g key={i}>
          <circle cx={c[0]} cy={c[1]} r={WHEEL_R} fill="none" stroke="rgb(255 255 255 / 0.85)" strokeWidth="5" />
          <circle cx={c[0]} cy={c[1]} r={WHEEL_R - 9} fill="none" stroke="rgb(255 255 255 / 0.12)" strokeWidth="1.5" />
          <circle cx={c[0]} cy={c[1]} r="5" fill="rgb(255 255 255 / 0.7)" />
        </g>
      ))}

      {/* Jambe opposée (en retrait) */}
      <g opacity="0.32" stroke="#dfe9d6" strokeLinecap="round" fill="none">
        <path d={limb(HIP, far.knee)} strokeWidth="15" />
        <path d={limb(far.knee, far.ankle)} strokeWidth="12" />
        <path d={limb(far.heel, far.toe)} strokeWidth="9" />
      </g>
      <line x1={BB[0]} y1={BB[1]} x2={far.pedal[0]} y2={far.pedal[1]} stroke="rgb(255 255 255 / 0.35)" strokeWidth="5" strokeLinecap="round" />

      {/* Cadre */}
      <g fill="none" stroke="#eef3ea" strokeLinecap="round" strokeLinejoin="round">
        <path d={FRAME_PATHS.frame} strokeWidth="7" />
        <path d={FRAME_PATHS.fork} strokeWidth="6" />
        <path d={FRAME_PATHS.seatpost} strokeWidth="5" />
        <path d={FRAME_PATHS.stem} strokeWidth="6" />
        <path d={FRAME_PATHS.bar} strokeWidth="5" />
      </g>
      <path d={FRAME_PATHS.saddle} fill="#eef3ea" />
      <circle cx={BB[0]} cy={BB[1]} r={CRANK + 6} fill="none" stroke="rgb(255 255 255 / 0.25)" strokeWidth="3" />

      {/* Haut du corps */}
      <g stroke="#cfdcc4" strokeLinecap="round" fill="none">
        <path d={`M${pt(HIP)} Q ${pt(BACK_CTRL)} ${pt(SHOULDER)}`} strokeWidth="26" />
        <path d={limb(SHOULDER, ELBOW)} strokeWidth="12" />
        <path d={limb(ELBOW, HOODS)} strokeWidth="10" />
      </g>
      <circle cx={HEAD[0]} cy={HEAD[1]} r={HEAD_R} fill="#cfdcc4" />

      {/* Jambe côté caméra */}
      <g stroke="#f4f8ef" strokeLinecap="round" fill="none">
        <path d={limb(HIP, near.knee)} strokeWidth="17" />
        <path d={limb(near.knee, near.ankle)} strokeWidth="13" />
        <path d={limb(near.heel, near.toe)} strokeWidth="10" />
      </g>
      <line x1={BB[0]} y1={BB[1]} x2={near.pedal[0]} y2={near.pedal[1]} stroke="#eef3ea" strokeWidth="6" strokeLinecap="round" />

      {/* Lignes de mesure + arc de flexion */}
      <g stroke={BODY} strokeWidth="2" fill="none" strokeLinecap="round">
        <path d={limb(HIP, near.knee)} />
        <path d={limb(near.knee, near.ankle)} />
        <path d={limb(near.knee, ext)} strokeDasharray="3 5" opacity="0.8" />
        <path d={arcPath(near.knee, ext, near.ankle, 26)} strokeWidth="3" />
      </g>

      {/* Pastilles */}
      {atBottom && <circle cx={near.knee[0]} cy={near.knee[1]} r="30" fill="url(#glow)" />}
      {[HIP, near.knee, near.ankle, SHOULDER, ELBOW].map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r="6" fill={BODY} stroke="#0c1406" strokeWidth="2" />
      ))}
      {[near.pedal, BB].map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r="5.5" fill={BIKE} stroke="#1a0d03" strokeWidth="2" />
      ))}
    </svg>
  );
}
