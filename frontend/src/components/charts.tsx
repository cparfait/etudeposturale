// Graphiques maison (SVG) : courbe sur un tour de manivelle, jauge de plage, série temporelle simple.
import { useMemo, useRef, useState } from "react";

type Num = number | null;
export interface CycleSeries { id: string; label: string; color: string; mean: Num[]; sd?: Num[] }

const W = 640, H = 260, M = { l: 40, r: 14, t: 14, b: 30 };

function path(xs: number[], ys: Num[]) {
  let d = "", pen = false;
  ys.forEach((y, i) => {
    if (y == null) { pen = false; return; }
    d += `${pen ? "L" : "M"}${xs[i].toFixed(1)},${y.toFixed(1)}`;
    pen = true;
  });
  return d;
}

/** Une ou deux courbes (G/D) sur 0–360° de manivelle, bande ± écart-type, plage cible optionnelle. */
export function CycleChart({ series, range, unit = "°", label }: {
  series: CycleSeries[]; range?: { min: number; max: number; label: string }; unit?: string; label: string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const n = series[0]?.mean.length ?? 0;
  const step = n ? 360 / n : 4;

  const { yMin, yMax } = useMemo(() => {
    const vals: number[] = [];
    series.forEach((s) => s.mean.forEach((v, i) => {
      if (v == null) return;
      const sd = s.sd?.[i] ?? 0;
      vals.push(v - sd, v + sd);
    }));
    if (range) vals.push(range.min, range.max);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.08 || 5;
    return { yMin: Math.floor((lo - pad) / 10) * 10, yMax: Math.ceil((hi + pad) / 10) * 10 };
  }, [series, range]);

  const x = (deg: number) => M.l + (deg / 360) * (W - M.l - M.r);
  const y = (v: number) => M.t + (1 - (v - yMin) / (yMax - yMin)) * (H - M.t - M.b);
  const xs = Array.from({ length: n }, (_, i) => x(i * step));
  const ticksY: number[] = [];
  const yStep = (yMax - yMin) > 80 ? 20 : 10;
  for (let v = yMin; v <= yMax; v += yStep) ticksY.push(v);

  function onMove(e: React.PointerEvent) {
    const r = ref.current!.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const deg = ((px - M.l) / (W - M.l - M.r)) * 360;
    setHover(deg < 0 || deg > 360 || !n ? null : Math.min(n - 1, Math.max(0, Math.round(deg / step))));
  }

  const hx = hover != null ? xs[hover] : 0;
  return (
    <div className="chart-wrap">
      <svg ref={ref} className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}
        onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {ticksY.map((v) => (
          <g key={v}>
            <line className="grid-line" x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} />
            <text className="axis-text" x={M.l - 6} y={y(v) + 4} textAnchor="end">{v}{unit}</text>
          </g>
        ))}
        {[0, 90, 180, 270, 360].map((d) => (
          <text key={d} className="axis-text" x={x(d)} y={H - 8} textAnchor="middle">
            {d === 0 ? "0° haut" : d === 90 ? "90° avant" : d === 180 ? "180° bas" : d === 270 ? "270° arrière" : "360°"}
          </text>
        ))}
        {range && (
          <g>
            <rect className="band" x={M.l} width={W - M.l - M.r} y={y(range.max)} height={Math.max(0, y(range.min) - y(range.max))} />
            <line className="band-edge" x1={M.l} x2={W - M.r} y1={y(range.max)} y2={y(range.max)} />
            <line className="band-edge" x1={M.l} x2={W - M.r} y1={y(range.min)} y2={y(range.min)} />
          </g>
        )}
        {series.map((s) => s.sd && (
          <path key={`sd-${s.id}`} className="sd" fill={s.color}
            d={(() => {
              const up = s.mean.map((m, i) => (m == null || s.sd![i] == null ? null : y(m + (s.sd![i] as number))));
              const lo = s.mean.map((m, i) => (m == null || s.sd![i] == null ? null : y(m - (s.sd![i] as number))));
              const pts = xs.map((xx, i) => (up[i] == null ? null : `${xx.toFixed(1)},${(up[i] as number).toFixed(1)}`)).filter(Boolean);
              const ptsLo = xs.map((xx, i) => (lo[i] == null ? null : `${xx.toFixed(1)},${(lo[i] as number).toFixed(1)}`)).filter(Boolean).reverse();
              return pts.length ? `M${pts.join("L")}L${ptsLo.join("L")}Z` : "";
            })()} />
        ))}
        {series.map((s) => (
          <path key={s.id} className="series" stroke={s.color} d={path(xs, s.mean.map((v) => (v == null ? null : y(v))))} />
        ))}
        {hover != null && (
          <g>
            <line className="cross" x1={hx} x2={hx} y1={M.t} y2={H - M.b} />
            {series.map((s) => s.mean[hover] != null && (
              <circle key={s.id} className="dot" cx={hx} cy={y(s.mean[hover] as number)} r={5} fill={s.color} />
            ))}
          </g>
        )}
        <rect x={M.l} y={M.t} width={W - M.l - M.r} height={H - M.t - M.b} fill="transparent" />
      </svg>
      {hover != null && (
        <div className="tooltip" style={{ left: `${(hx / W) * 100}%`, top: `${(M.t / H) * 100}%` }}>
          Manivelle {Math.round(hover * step)}°
          {series.map((s) => s.mean[hover] != null && (
            <div key={s.id}>{s.label} : {(s.mean[hover] as number).toFixed(1)}{unit}{s.sd?.[hover] != null ? ` ± ${(s.sd[hover] as number).toFixed(1)}` : ""}</div>
          ))}
        </div>
      )}
      <div className="chart-legend">
        {series.length > 1 && series.map((s) => (
          <span key={s.id}><i className="swatch" style={{ background: s.color }} /> {s.label}</span>
        ))}
        {range && <span><i className="swatch band" /> {range.label}</span>}
        <span className="subtle">Bande claire : ± 1 écart-type entre les tours</span>
      </div>
    </div>
  );
}

/** Jauge : valeur ± écart-type positionnée par rapport à une plage cible. */
export function Gauge({ value, sd, min, max, lo, hi, unit = "°" }: {
  value: number; sd?: number; min: number; max: number; lo: number; hi: number; unit?: string;
}) {
  const pct = (v: number) => `${Math.min(100, Math.max(0, ((v - min) / (max - min)) * 100))}%`;
  return (
    <div>
      <div className="gauge" role="img" aria-label={`${value.toFixed(1)}${unit}, plage indicative ${lo} à ${hi}${unit}`}>
        <div className="gauge-track" />
        <div className="gauge-range" style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }} />
        {sd ? <div className="gauge-sd" style={{ left: pct(value - sd), width: `calc(${pct(value + sd)} - ${pct(value - sd)})` }} /> : null}
        <div className="gauge-marker" style={{ left: pct(value) }} />
      </div>
      <div className="gauge-scale"><span>{min}{unit}</span><span>{lo}–{hi}{unit} indicatif</span><span>{max}{unit}</span></div>
    </div>
  );
}

/** Petite série temporelle (un seul trait), avec survol. */
export function LineChart({ values, unit, label, color = "var(--brand-text)" }: { values: Num[]; unit: string; label: string; color?: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const vals = values.filter((v): v is number => v != null);
  if (!vals.length) return <p className="subtle">Pas de données.</p>;
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * 0.1 || 1;
  const h = 140, m = { l: 40, r: 10, t: 10, b: 18 };
  const x = (i: number) => m.l + (i / Math.max(1, values.length - 1)) * (W - m.l - m.r);
  const y = (v: number) => m.t + (1 - (v - (lo - pad)) / (hi - lo + 2 * pad)) * (h - m.t - m.b);
  return (
    <div className="chart-wrap">
      <svg ref={ref} className="chart" viewBox={`0 0 ${W} ${h}`} role="img" aria-label={label}
        onPointerMove={(e) => {
          const r = ref.current!.getBoundingClientRect();
          const i = Math.round((((e.clientX - r.left) / r.width) * W - m.l) / (W - m.l - m.r) * (values.length - 1));
          setHover(i >= 0 && i < values.length ? i : null);
        }} onPointerLeave={() => setHover(null)}>
        {[lo, (lo + hi) / 2, hi].map((v, i) => (
          <g key={i}>
            <line className="grid-line" x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} />
            <text className="axis-text" x={m.l - 6} y={y(v) + 4} textAnchor="end">{v.toFixed(1)}</text>
          </g>
        ))}
        <path className="series" stroke={color} d={path(values.map((_, i) => x(i)), values.map((v) => (v == null ? null : y(v))))} />
        {hover != null && values[hover] != null && (
          <g><line className="cross" x1={x(hover)} x2={x(hover)} y1={m.t} y2={h - m.b} />
            <circle className="dot" cx={x(hover)} cy={y(values[hover] as number)} r={5} fill={color} /></g>
        )}
      </svg>
      {hover != null && values[hover] != null && (
        <div className="tooltip" style={{ left: `${(x(hover) / W) * 100}%`, top: "10%" }}>{(values[hover] as number).toFixed(1)} {unit}</div>
      )}
    </div>
  );
}

/** Mesure au fil d'une sortie (minutes en abscisse) ; ligne de référence et bande optionnelles (ex. 50 % ± 2). */
export function TimeChart({ t, values, unit, label, color = "var(--brand-text)", reference, band, digits = 0 }: {
  t: number[]; values: Num[]; unit: string; label: string; color?: string;
  reference?: { value: number; label: string }; band?: [number, number]; digits?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const vals = values.filter((v): v is number => v != null);
  if (!vals.length || t.length < 2) return <p className="subtle">Pas assez de données pour tracer la courbe.</p>;
  const extra = [...(reference ? [reference.value] : []), ...(band ?? [])];
  const lo0 = Math.min(...vals, ...extra), hi0 = Math.max(...vals, ...extra);
  const pad = (hi0 - lo0) * 0.12 || 1, lo = lo0 - pad, hi = hi0 + pad;
  const h = 170, m = { l: 44, r: 12, t: 12, b: 26 };
  const t0 = 0, t1 = Math.max(t[t.length - 1] + (t[1] - t[0]) / 2, 1);
  const x = (tm: number) => m.l + ((tm - t0) / (t1 - t0)) * (W - m.l - m.r);
  const y = (v: number) => m.t + (1 - (v - lo) / (hi - lo)) * (h - m.t - m.b);
  const fmtT = (tm: number) => (tm >= 60 ? `${Math.floor(tm / 60)} h${String(Math.round(tm % 60)).padStart(2, "0")}` : `${Math.round(tm)} min`);
  const ticks = (() => {                                       // graduations toutes les 15, 30 ou 60 min
    const span = t1 - t0, stepT = span > 180 ? 60 : span > 75 ? 30 : 15;
    const out: number[] = [];
    for (let v = 0; v <= t1; v += stepT) out.push(v);
    return out;
  })();
  const yTicks = [lo0, (lo0 + hi0) / 2, hi0];
  return (
    <div className="chart-wrap">
      <svg ref={ref} className="chart" viewBox={`0 0 ${W} ${h}`} role="img" aria-label={label}
        onPointerMove={(e) => {
          const r = ref.current!.getBoundingClientRect();
          const tm = t0 + ((((e.clientX - r.left) / r.width) * W - m.l) / (W - m.l - m.r)) * (t1 - t0);
          let best = 0;
          t.forEach((v, i) => { if (Math.abs(v - tm) < Math.abs(t[best] - tm)) best = i; });
          setHover(best);
        }} onPointerLeave={() => setHover(null)}>
        {band && <rect className="ref-band" x={m.l} width={W - m.l - m.r} y={y(band[1])} height={Math.max(1, y(band[0]) - y(band[1]))} />}
        {yTicks.map((v, i) => (
          <g key={i}>
            <line className="grid-line" x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} />
            <text className="axis-text" x={m.l - 6} y={y(v) + 4} textAnchor="end">{v.toFixed(digits).replace(".", ",")}</text>
          </g>
        ))}
        {reference && (
          <g>
            <line className="ref-line" x1={m.l} x2={W - m.r} y1={y(reference.value)} y2={y(reference.value)} />
            <text className="axis-text" x={W - m.r} y={y(reference.value) - 5} textAnchor="end">{reference.label}</text>
          </g>
        )}
        {ticks.map((v) => <text key={v} className="axis-text" x={x(v)} y={h - 6} textAnchor="middle">{fmtT(v)}</text>)}
        <path className="series" stroke={color} d={path(t.map(x), values.map((v) => (v == null ? null : y(v))))} />
        {hover != null && values[hover] != null && (
          <g><line className="cross" x1={x(t[hover])} x2={x(t[hover])} y1={m.t} y2={h - m.b} />
            <circle className="dot" cx={x(t[hover])} cy={y(values[hover] as number)} r={5} fill={color} /></g>
        )}
      </svg>
      {hover != null && values[hover] != null && (
        <div className="tooltip" style={{ left: `${(x(t[hover]) / W) * 100}%`, top: "8%" }}>
          {fmtT(t[hover])} · {(values[hover] as number).toFixed(digits).replace(".", ",")} {unit}
        </div>
      )}
    </div>
  );
}
