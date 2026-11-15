import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Check, ImagePlus, Pipette, RotateCcw, Save, Video } from "lucide-react";
import { http, type Any } from "../api";
import StickerColors from "../components/StickerColors";
import { loadEquipment } from "../equipment";
import { useToast } from "../toast";

type HSV = [number, number, number];
interface Range { lo: HSV; hi: HSV }
type Key = "vert" | "orange";
type Colors = Record<Key, Range>;
interface Frame { token: string; largeur: number; hauteur: number; image: string }
interface Result { pastilles: [number, number][]; masque: string; couverture_pct: number }

const VIEWS = [
  { id: "profil", label: "Profil", vert: 8, orange: 2, aide: "8 vertes (trochanter, genou, malléole, talon, 5e métatarse, épaule, coude, poignet) et 2 orange (axe de pédale, pédalier)." },
  { id: "face", label: "Face", vert: 4, orange: 0, aide: "4 vertes : centre des deux rotules et des deux 2es orteils." },
  { id: "dos", label: "Dos", vert: 2, orange: 0, aide: "2 vertes : les deux épines iliaques postéro-supérieures." },
] as const;

/** RVB (0–255) → HSV au format OpenCV (H 0–179, S et V 0–255). */
function rgbToHsv(r: number, g: number, b: number): HSV {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  let h = 0;
  if (d) h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  h = Math.round(((h * 60 + 360) % 360) / 2);
  return [h % 180, mx ? Math.round((d / mx) * 255) : 0, mx];
}

/** Plage proposée autour d'une couleur relevée à la pipette. */
function rangeAround([h, s, v]: HSV): Range {
  const lo = (h - 10 + 180) % 180, hi = (h + 10) % 180;
  return { lo: [lo, Math.max(40, Math.round(s * 0.55)), Math.max(40, Math.round(v * 0.5))], hi: [hi, 255, 255] };
}

const same = (a?: Colors, b?: Colors) => JSON.stringify(a) === JSON.stringify(b);
const hueCss = (h: number) => `hsl(${h * 2} 90% 52%)`;

function HueSlider({ range, onChange }: { range: Range; onChange: (r: Range) => void }) {
  const [lo, hi] = [range.lo[0], range.hi[0]];
  const wrap = lo > hi;
  const band = wrap
    ? `linear-gradient(90deg, transparent 0 ${(hi / 179) * 100}%, rgb(0 0 0 / 0.55) ${(hi / 179) * 100}% ${(lo / 179) * 100}%, transparent ${(lo / 179) * 100}%)`
    : `linear-gradient(90deg, rgb(0 0 0 / 0.55) 0 ${(lo / 179) * 100}%, transparent ${(lo / 179) * 100}% ${(hi / 179) * 100}%, rgb(0 0 0 / 0.55) ${(hi / 179) * 100}%)`;
  const set = (i: 0 | 1, v: number) => {
    const r: Range = { lo: [...range.lo] as HSV, hi: [...range.hi] as HSV };
    (i === 0 ? r.lo : r.hi)[0] = v;
    onChange(r);
  };
  return (
    <div className="hue-slider">
      <div className="hue-track" style={{ backgroundImage: `${band}, linear-gradient(90deg, ${Array.from({ length: 13 }, (_, k) => hueCss(k * 15)).join(",")})` }} />
      <input type="range" min={0} max={179} value={lo} aria-label="Teinte minimale" onChange={(e) => set(0, +e.target.value)} />
      <input type="range" min={0} max={179} value={hi} aria-label="Teinte maximale" onChange={(e) => set(1, +e.target.value)} />
    </div>
  );
}

function Slider({ label, value, onChange, hint }: { label: string; value: number; onChange: (v: number) => void; hint: string }) {
  return (
    <label className="mk-slider">
      <span className="mk-slider-head"><span>{label}</span><b>{value}</b></span>
      <input type="range" min={0} max={255} value={value} onChange={(e) => onChange(+e.target.value)} />
      <small>{hint}</small>
    </label>
  );
}

export default function Markers() {
  const toast = useToast();
  const [saved, setSaved] = useState<Colors>();
  const [defaults, setDefaults] = useState<Colors>();
  const [colors, setColors] = useState<Colors>();
  const [frame, setFrame] = useState<Frame | null>(null);
  const [result, setResult] = useState<Record<Key, Result> | null>(null);
  const [view, setView] = useState<(typeof VIEWS)[number]["id"]>("profil");
  const [show, setShow] = useState<Record<Key, boolean>>({ vert: true, orange: true });
  const [pick, setPick] = useState<Key | null>(null);
  const [picked, setPicked] = useState<{ hsv: HSV; rgb: string } | null>(null);
  const [captures, setCaptures] = useState<Any[]>([]);
  const [capId, setCapId] = useState<number | "">("");
  const [t, setT] = useState(2);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [names, setNames] = useState({ corps: "vertes", corps1: "verte", velo: "orange", velo1: "orange", teinte_corps: "#a3e635", teinte_velo: "#f97316" });
  const upper = (x: string) => x.charAt(0).toUpperCase() + x.slice(1);
  const TINT: Record<Key, string> = { vert: names.teinte_corps, orange: names.teinte_velo };
  const LABEL: Record<Key, string> = { vert: `Pastilles du corps (${names.corps})`, orange: `Repères du vélo (${names.velo})` };
  const SHORT: Record<Key, string> = { vert: upper(names.corps1), orange: upper(names.velo1) };
  const aide = (txt: string) => txt.replace(/vertes/g, names.corps).replace(/ orange/g, ` ${names.velo}`);
  const [info, setInfo] = useState<Any | null>(null);
  const applyColors = (c: Any) => { setSaved(c.actuel); setDefaults(c.defaut); setColors(c.actuel); setNames(c.noms); setInfo(c); };

  useEffect(() => {
    http.get("/markers/colors").then(applyColors);
    http.get("/sessions").then((ss: Any[]) => setCaptures(ss.flatMap((s) => s.captures.map((c: Any) => ({ ...c, seance: s })))));
  }, []);

  // Pixels de l'image test pour la pipette.
  useEffect(() => {
    if (!frame) return;
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = img.width; c.height = img.height;
      c.getContext("2d", { willReadFrequently: true })!.drawImage(img, 0, 0);
      canvas.current = c;
    };
    img.src = frame.image;
  }, [frame]);

  // Détection relancée à chaque réglage (légèrement différée pendant le glissement des curseurs).
  useEffect(() => {
    if (!frame || !colors) return;
    const id = setTimeout(() => {
      http.post("/markers/test", { token: frame.token, ...colors }).then(setResult).catch((e) => toast((e as Error).message, "error"));
    }, 180);
    return () => clearTimeout(id);
  }, [frame, colors, toast]);

  async function loadFrame(form: FormData) {
    setBusy(true);
    try { setFrame(await http.upload<Frame>("/markers/frame", form)); setPicked(null); }
    catch (e) { toast((e as Error).message, "error"); }
    finally { setBusy(false); }
  }
  function fromFile(f?: File | null) {
    if (!f) return;
    const form = new FormData(); form.append("file", f); loadFrame(form);
  }
  function fromCapture(id: number, at: number) {
    const form = new FormData(); form.append("capture_id", String(id)); form.append("t", String(at)); loadFrame(form);
  }

  function onImageClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!frame || !canvas.current || !colors) return;
    const box = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - box.left) / box.width) * frame.largeur);
    const y = Math.round(((e.clientY - box.top) / box.height) * frame.hauteur);
    // moyenne 5 × 5 pour ne pas tomber sur un pixel isolé
    const d = canvas.current.getContext("2d")!.getImageData(Math.max(0, x - 2), Math.max(0, y - 2), 5, 5).data;
    let r = 0, g = 0, b = 0, n = 0;
    for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
    [r, g, b] = [r / n, g / n, b / n].map(Math.round);
    const hsv = rgbToHsv(r, g, b);
    setPicked({ hsv, rgb: `rgb(${r} ${g} ${b})` });
    if (pick) {
      setColors({ ...colors, [pick]: rangeAround(hsv) });
      toast(`Plage des pastilles ${pick === "vert" ? names.corps : names.velo} recentrée sur la couleur relevée`);
      setPick(null);
    }
  }

  const update = (k: Key, r: Range) => colors && setColors({ ...colors, [k]: r });
  const setChan = (k: Key, side: "lo" | "hi", ch: 1 | 2, v: number) => {
    if (!colors) return;
    const r: Range = { lo: [...colors[k].lo] as HSV, hi: [...colors[k].hi] as HSV };
    r[side][ch] = v;
    if (side === "lo" && r.hi[ch] < v) r.hi[ch] = v;
    update(k, r);
  };

  async function save() {
    try {
      const c = await http.put("/markers/colors", colors);
      applyColors(c);
      setInfo(c);
      await loadEquipment(true).catch(() => {});
      toast(`Couleurs étalonnées : pastilles ${c.noms.corps} pour le corps, ${c.noms.velo} pour le vélo`);
    } catch (e) { toast((e as Error).message, "error"); }
  }
  async function reset() {
    const c = await http.del("/markers/colors").then(() => http.get("/markers/colors"));
    applyColors(c); setInfo(c);
    toast("Valeurs par défaut rétablies");
  }

  const v = VIEWS.find((x) => x.id === view)!;
  const verdict = useMemo(() => {
    if (!result) return null;
    return (["vert", "orange"] as Key[]).filter((k) => v[k] > 0 || result[k].pastilles.length > 0).map((k) => {
      const n = result[k].pastilles.length, want = v[k];
      const tone = n === want ? "ok" : n < want ? "warn" : "danger";
      const msg = n === want ? "le compte est bon" : n < want ? `${want - n} manquante${want - n > 1 ? "s" : ""} : élargis la plage ou relève la couleur à la pipette` : `${n - want} de trop : resserre la plage (reflet, vêtement, décor ?)`;
      return { k, n, want, tone, msg };
    });
  }, [result, v]);

  const cap = captures.find((c) => c.id === capId);
  const dirty = !same(colors, saved);

  if (!colors) return <div className="page"><p className="subtle">Chargement…</p></div>;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Avant la première séance</div>
          <h1>Étalonnage des pastilles</h1>
          <p>Couleurs libres, si celles du corps et du vélo sont bien différentes : l'application les apprend ici. À refaire si tu changes de pastilles ou d'éclairage.</p>
        </div>
      </header>
      <ol className="mk-steps">
        <li className={frame ? "done" : "current"}><b>1</b> Une photo de toi sur le vélo, pastilles posées (ou une image d'une vidéo)</li>
        <li className={frame ? "current" : ""}><b>2</b> « Pipette » : clique sur une pastille du corps, puis sur une du vélo</li>
        <li className={dirty ? "current" : ""}><b>3</b> Vérifie le compte de pastilles, puis « Enregistrer »</li>
      </ol>
      {info?.trop_proches && (
        <div className="alert warn" style={{ marginBottom: 12 }}><AlertTriangle size={16} /><span>Les deux couleurs sont trop proches (écart de teinte {info.ecart_teinte}) : l'application risque de les confondre. Choisis des pastilles plus différentes.</span></div>
      )}

      <div className="mk-layout">
        <section className="stack">
          {!frame ? (
            <div className="grid-2">
              <label className={`drop${over ? " over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
                onDrop={(e) => { e.preventDefault(); setOver(false); fromFile(e.dataTransfer.files[0]); }}>
                <ImagePlus size={26} />
                <strong>Déposer une photo</strong>
                <small>Prise dans les mêmes conditions que la vidéo (JPG, PNG)</small>
                <input type="file" accept="image/*" onChange={(e) => fromFile(e.target.files?.[0])} />
              </label>
              <div className="card mk-source">
                <div className="row" style={{ gap: 8 }}><Video size={18} /><strong>Image d'une vidéo de séance</strong></div>
                {captures.length === 0 ? <p className="subtle" style={{ margin: 0 }}>Aucune vidéo importée pour l'instant.</p> : (
                  <>
                    <select className="select" value={capId} onChange={(e) => setCapId(e.target.value ? +e.target.value : "")}>
                      <option value="">Choisir une vidéo…</option>
                      {captures.map((c) => <option key={c.id} value={c.id}>Séance {c.seance.id} · {c.vue} · {c.filename}</option>)}
                    </select>
                    <button className="btn btn-primary btn-sm" disabled={!capId || busy} onClick={() => fromCapture(Number(capId), t)}>Extraire l'image</button>
                  </>
                )}
              </div>
            </div>
          ) : (
            <>
              <div className={`mk-stage${pick ? " picking" : ""}`} style={{ aspectRatio: `${frame.largeur} / ${frame.hauteur}` }} onClick={onImageClick}>
                <img src={frame.image} alt="Image test" />
                {result && (["vert", "orange"] as Key[]).map((k) => show[k] && (
                  <div key={k} className="mk-mask" style={{ background: TINT[k], WebkitMaskImage: `url(${result[k].masque})`, maskImage: `url(${result[k].masque})` }} />
                ))}
                {result && (
                  <svg viewBox={`0 0 ${frame.largeur} ${frame.hauteur}`} className="mk-dots" aria-hidden>
                    {(["vert", "orange"] as Key[]).map((k) => show[k] && result[k].pastilles.map(([x, y], i) => (
                      <circle key={`${k}${i}`} cx={x} cy={y} r={Math.max(10, frame.largeur * 0.014)} className={`mk-ring ${k}`} />
                    )))}
                  </svg>
                )}
                {pick && <div className="mk-hint"><Pipette size={14} /> Clique au centre d'une pastille {pick === "vert" ? names.corps1 : names.velo1}</div>}
              </div>

              <div className="row mk-toolbar">
                {(["vert", "orange"] as Key[]).map((k) => (
                  <button key={k} className={`chip ${k === "vert" ? "brand" : "bike"} mk-toggle`} aria-pressed={show[k]} onClick={() => setShow({ ...show, [k]: !show[k] })}>
                    <span className="mk-sw" style={{ background: TINT[k] }} /> {SHORT[k]} · {result?.[k].pastilles.length ?? "…"}
                  </button>
                ))}
                {picked && (
                  <span className="chip"><span className="mk-sw" style={{ background: picked.rgb }} /> T {picked.hsv[0]} · S {picked.hsv[1]} · V {picked.hsv[2]}</span>
                )}
                <span style={{ flex: 1 }} />
                {cap && (
                  <label className="mk-time">
                    <span className="subtle">Instant</span>
                    <input type="range" min={0} max={Math.max(1, Math.floor(cap.meta.duration_s ?? 10))} step={0.5} value={t}
                      onChange={(e) => setT(+e.target.value)} onPointerUp={() => fromCapture(cap.id, t)} onKeyUp={() => fromCapture(cap.id, t)} />
                    <b>{t.toFixed(1)} s</b>
                  </label>
                )}
                <button className="btn btn-ghost btn-sm" onClick={() => { setFrame(null); setResult(null); }}>Changer d'image</button>
              </div>

              {verdict && (
                <div className="stack" style={{ gap: 8 }}>
                  {verdict.map(({ k, n, want, tone, msg }) => (
                    <div key={k} className={`alert ${tone === "ok" ? "ok" : tone === "warn" ? "warn" : "danger"}`}>
                      {tone === "ok" ? <Check size={17} /> : <span className="mk-sw" style={{ background: TINT[k], marginTop: 3 }} />}
                      <span><strong>{SHORT[k]} : {n} / {want}</strong> — {msg}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        <aside className="stack mk-aside">
          <div className="card mk-view">
            <h3 style={{ marginTop: 0 }}>Vue filmée</h3>
            <div className="segmented">
              {VIEWS.map((x) => <button key={x.id} aria-pressed={view === x.id} onClick={() => setView(x.id)}>{x.label}</button>)}
            </div>
            <p className="subtle" style={{ fontSize: "0.84rem", marginBottom: 0 }}>{aide(v.aide)}</p>
            <div style={{ marginTop: 12 }}><StickerColors compact onChange={applyColors} /></div>
          </div>

          {(["vert", "orange"] as Key[]).map((k) => (
            <div key={k} className="card mk-color">
              <div className="card-head" style={{ marginBottom: 10 }}>
                <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}><span className="mk-sw lg" style={{ background: TINT[k] }} />{LABEL[k]}</h3>
                <button className={`btn btn-sm ${pick === k ? "btn-primary" : "btn-ghost"}`} disabled={!frame} onClick={() => setPick(pick === k ? null : k)} title="Relever la couleur sur l'image">
                  <Pipette size={14} /> Pipette
                </button>
              </div>
              <div className="mk-slider">
                <span className="mk-slider-head"><span>Teinte</span><b>{colors[k].lo[0]} → {colors[k].hi[0]}</b></span>
                <HueSlider range={colors[k]} onChange={(r) => update(k, r)} />
                <small>Zone claire = couleurs retenues{colors[k].lo[0] > colors[k].hi[0] ? " (passe par le rouge)" : ""}</small>
              </div>
              <Slider label="Saturation minimale" value={colors[k].lo[1]} onChange={(x) => setChan(k, "lo", 1, x)} hint="Monter écarte les teintes ternes (peau, bois, vêtements délavés)" />
              <Slider label="Luminosité minimale" value={colors[k].lo[2]} onChange={(x) => setChan(k, "lo", 2, x)} hint="Baisser si les pastilles à l'ombre disparaissent" />
              {result && <p className="subtle" style={{ margin: "6px 0 0", fontSize: "0.8rem" }}>{result[k].couverture_pct} % de l'image retenue{result[k].couverture_pct > 3 ? " — beaucoup : risque de fausses détections" : ""}</p>}
            </div>
          ))}

          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-primary" style={{ flex: 1 }} disabled={!dirty} onClick={save}><Save size={16} /> {dirty ? "Enregistrer" : "Enregistré"}</button>
            <button className="btn btn-ghost" disabled={same(saved, defaults) && !dirty} onClick={reset} title="Revenir aux valeurs par défaut"><RotateCcw size={16} /></button>
          </div>
        </aside>
      </div>
    </div>
  );
}
