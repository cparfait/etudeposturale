// Lecteur vidéo avec le squelette mesuré superposé (contrôle visuel de la qualité du suivi).
import { useEffect, useRef, useState } from "react";

type Pt = [number | null, number | null] | null;
export interface Overlay {
  temps: (number | null)[];
  pedalier: (number | null)[];
  pedale: Pt[];
  reperes: Record<string, Pt[]>;
  genou_flexion: (number | null)[];
}

const BONES: [string, string][] = [
  ["trochanter", "epicondyle_femoral"], ["epicondyle_femoral", "malleole"], ["talon", "metatarse5"], ["malleole", "talon"],
  ["trochanter", "acromion"], ["acromion", "epicondyle_humeral"], ["epicondyle_humeral", "styloide_ulnaire"],
];

function nearest(times: (number | null)[], t: number) {
  let lo = 0, hi = times.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if ((times[mid] ?? 0) < t) lo = mid + 1; else hi = mid;
  }
  return lo;
}

export default function VideoOverlay({ src, overlay, width, height }: { src: string; overlay: Overlay; width: number; height: number }) {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [flex, setFlex] = useState<number | null>(null);
  const [show, setShow] = useState(true);

  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const v = video.current, c = canvas.current;
      if (v && c) {
        const ctx = c.getContext("2d")!;
        c.width = width;
        c.height = height;
        ctx.clearRect(0, 0, width, height);
        const t = v.currentTime;
        const first = overlay.temps[0] ?? 0, last = overlay.temps[overlay.temps.length - 1] ?? 0;
        if (show && t >= first - 0.05 && t <= last + 0.05) {
          const i = nearest(overlay.temps, t);
          const lw = Math.max(2, width / 400);
          const p = (k: string) => overlay.reperes[k]?.[i];
          ctx.lineCap = "round";
          ctx.strokeStyle = "rgba(184, 243, 74, 0.95)";
          ctx.lineWidth = lw * 1.6;
          for (const [a, b] of BONES) {
            const pa = p(a), pb = p(b);
            if (pa?.[0] != null && pb?.[0] != null) {
              ctx.beginPath(); ctx.moveTo(pa[0], pa[1] as number); ctx.lineTo(pb[0], pb[1] as number); ctx.stroke();
            }
          }
          const bb = overlay.pedalier, ped = overlay.pedale[i];
          ctx.strokeStyle = "rgba(251, 146, 60, 0.95)";
          if (bb[0] != null && ped?.[0] != null) {
            ctx.beginPath(); ctx.moveTo(bb[0], bb[1] as number); ctx.lineTo(ped[0], ped[1] as number); ctx.stroke();
          }
          const dot = (q: Pt, color: string) => {
            if (q?.[0] == null) return;
            ctx.beginPath(); ctx.arc(q[0], q[1] as number, lw * 3, 0, Math.PI * 2);
            ctx.fillStyle = color; ctx.fill(); ctx.lineWidth = lw; ctx.strokeStyle = "#0b0f0b"; ctx.stroke();
          };
          Object.values(overlay.reperes).forEach((arr) => dot(arr[i], "#b8f34a"));
          dot([bb[0], bb[1]], "#fb923c");
          dot(ped, "#fb923c");
          setFlex(overlay.genou_flexion[i]);
        } else {
          setFlex(null);
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [overlay, width, height, show]);

  return (
    <div>
      <div className="player">
        <video ref={video} src={src} controls playsInline muted preload="metadata" />
        <canvas ref={canvas} aria-hidden="true" />
        {flex != null && <div className="player-hud">Flexion du genou <b>{flex.toFixed(0)}°</b></div>}
      </div>
      <label className="row subtle" style={{ marginTop: 8, fontSize: "0.85rem" }}>
        <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> Afficher le squelette mesuré
        <span>· Astuce : ralentissez la lecture (clic droit sur la vidéo → vitesse) pour contrôler le suivi.</span>
      </label>
    </div>
  );
}
