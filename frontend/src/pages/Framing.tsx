import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, CircleDashed, Maximize2, Minimize2, ShieldAlert } from "lucide-react";
import type { NormalizedLandmark, PoseLandmarker } from "@mediapipe/tasks-vision";

// Modèle : d'abord une copie locale (public/mediapipe/), sinon le fichier officiel de Google (téléchargé une fois par le navigateur).
const MODEL_LOCAL = "/mediapipe/pose_landmarker_full.task";
const MODEL_REMOTE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task";

interface Check { id: string; label: string; ok: boolean | null; hint: string }

const BONES = [[11, 12], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28], [27, 31], [28, 32], [11, 13], [13, 15], [12, 14], [14, 16]];

function evaluate(lm: NormalizedLandmark[] | undefined, luminance: number, fps: number | undefined, landscape: boolean): Check[] {
  const key = [11, 12, 23, 24, 25, 26, 27, 28];
  const vis = lm ? key.every((i) => (lm[i].visibility ?? 0) > 0.5 && lm[i].x > 0.02 && lm[i].x < 0.98 && lm[i].y > 0.02 && lm[i].y < 0.98) : null;
  let height: number | null = null, hip: number | null = null;
  if (lm) {
    const ys = lm.slice(0, 33).filter((p) => (p.visibility ?? 0) > 0.4).map((p) => p.y);
    height = ys.length ? Math.max(...ys) - Math.min(...ys) : null;
    hip = (lm[23].y + lm[24].y) / 2;
  }
  return [
    { id: "paysage", label: "Téléphone en paysage", ok: landscape, hint: "Tourne le téléphone à l'horizontale." },
    { id: "corps", label: "Corps entier visible", ok: vis, hint: "Épaules, hanches, genoux et chevilles doivent être dans l'image, avec une marge." },
    { id: "taille", label: "Cycliste ni trop petit ni coupé", ok: height == null ? null : height > 0.5 && height < 0.92, hint: height != null && height <= 0.5 ? "Rapproche le trépied (≈ 2,5 m)." : "Recule le trépied (≈ 3 m)." },
    { id: "hauteur", label: "Caméra à hauteur de selle", ok: hip == null ? null : hip > 0.3 && hip < 0.6, hint: hip != null && hip <= 0.3 ? "Baisse le téléphone." : "Monte le téléphone." },
    { id: "lumiere", label: "Éclairage suffisant", ok: luminance > 0.33, hint: "Ajoute de la lumière continue (projecteurs LED), évite le contre-jour." },
    { id: "fps", label: "60 images/s ou plus", ok: fps == null ? null : fps >= 50, hint: "Le navigateur ne donne pas 60 images/s : c'est normal pour le cadrage, mais filme la mesure avec l'appli Appareil photo en 60 ou 120 images/s." },
  ];
}

export default function Framing() {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState("Caméra arrêtée");
  const [checks, setChecks] = useState<Check[]>(() => evaluate(undefined, 0, undefined, true));
  const [running, setRunning] = useState(false);
  const stopRef = useRef<() => void>(() => {});
  const liveRef = useRef<HTMLDivElement>(null);
  const [fs, setFs] = useState(false);          // plein écran (API du navigateur ou repli CSS sur iPhone)
  const wake = useRef<{ release: () => Promise<void> } | null>(null);

  useEffect(() => () => stopRef.current(), []);
  useEffect(() => {
    const onChange = () => { if (!document.fullscreenElement) setFs(false); };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  async function toggleFullscreen() {
    if (fs) {
      if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
      setFs(false);
      return;
    }
    const el = liveRef.current;
    try { if (el?.requestFullscreen) await el.requestFullscreen(); } catch { /* repli CSS ci-dessous */ }
    setFs(true);
    // Sur téléphone : rester en paysage et garder l'écran allumé pendant l'étalonnage (si le navigateur le permet)
    try { await (screen.orientation as unknown as { lock?: (o: string) => Promise<void> }).lock?.("landscape"); } catch { /* non pris en charge */ }
    try { wake.current = await (navigator as unknown as { wakeLock?: { request: (t: string) => Promise<{ release: () => Promise<void> }> } }).wakeLock?.request("screen") ?? null; } catch { /* non pris en charge */ }
  }
  useEffect(() => { if (!fs) { wake.current?.release().catch(() => {}); wake.current = null; } }, [fs]);

  async function start() {
    try {
      setStatus("Chargement du modèle de pose…");
      const { FilesetResolver, PoseLandmarker } = await import("@mediapipe/tasks-vision");
      const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
      const local = await fetch(MODEL_LOCAL, { method: "HEAD" }).then((r) => r.ok && r.headers.get("content-type") !== "text/html").catch(() => false);
      const landmarker: PoseLandmarker = await PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: local ? MODEL_LOCAL : MODEL_REMOTE, delegate: "GPU" },
        runningMode: "VIDEO", numPoses: 1,
      });
      setStatus("Ouverture de la caméra…");
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 60 } }, audio: false,
      });
      const v = video.current!;
      v.srcObject = stream;
      await v.play();
      const fps = stream.getVideoTracks()[0].getSettings().frameRate;
      setRunning(true);
      setStatus("Cadrage en cours");
      const small = document.createElement("canvas");
      small.width = 64; small.height = 36;
      const sctx = small.getContext("2d", { willReadFrequently: true })!;
      let raf = 0, last = 0;
      const loop = (now: number) => {
        raf = requestAnimationFrame(loop);
        if (now - last < 66 || v.readyState < 2) return; // ~15 analyses/s suffisent
        last = now;
        const res = landmarker.detectForVideo(v, now);
        const lm = res.landmarks[0];
        sctx.drawImage(v, 0, 0, 64, 36);
        const px = sctx.getImageData(0, 0, 64, 36).data;
        let sum = 0;
        for (let i = 0; i < px.length; i += 4) sum += 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
        const lum = sum / (px.length / 4) / 255;
        setChecks(evaluate(lm, lum, fps, v.videoWidth >= v.videoHeight));
        const c = canvas.current!;
        c.width = v.videoWidth; c.height = v.videoHeight;
        const ctx = c.getContext("2d")!;
        ctx.clearRect(0, 0, c.width, c.height);
        // Guides : tiers + zone conseillée pour la hanche
        ctx.strokeStyle = "rgba(255,255,255,0.25)"; ctx.lineWidth = 2; ctx.setLineDash([10, 10]);
        [0.3, 0.6].forEach((y) => { ctx.beginPath(); ctx.moveTo(0, y * c.height); ctx.lineTo(c.width, y * c.height); ctx.stroke(); });
        ctx.setLineDash([]);
        if (lm) {
          ctx.strokeStyle = "#b8f34a"; ctx.lineWidth = Math.max(3, c.width / 300); ctx.lineCap = "round";
          for (const [a, b] of BONES) {
            ctx.beginPath(); ctx.moveTo(lm[a].x * c.width, lm[a].y * c.height); ctx.lineTo(lm[b].x * c.width, lm[b].y * c.height); ctx.stroke();
          }
          ctx.fillStyle = "#b8f34a";
          for (const i of [11, 12, 23, 24, 25, 26, 27, 28]) { ctx.beginPath(); ctx.arc(lm[i].x * c.width, lm[i].y * c.height, ctx.lineWidth * 1.8, 0, Math.PI * 2); ctx.fill(); }
        }
      };
      raf = requestAnimationFrame(loop);
      stopRef.current = () => {
        cancelAnimationFrame(raf);
        stream.getTracks().forEach((t) => t.stop());
        landmarker.close();
        setRunning(false);
        setStatus("Caméra arrêtée");
      };
    } catch (e) {
      setStatus(`Impossible de démarrer : ${(e as Error).message}`);
    }
  }

  const essential = checks.filter((c) => c.id !== "fps");
  const allOk = running && essential.every((c) => c.ok);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Avant d'enregistrer</div>
          <h1>Cadrage en direct</h1>
          <p>Ouvre cette page sur le téléphone posé sur son trépied : quand tout est vert, passe dans l'appli Appareil photo pour filmer la mesure.</p>
        </div>
        {running ? (
          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-primary" onClick={toggleFullscreen}><Maximize2 size={16} /> Plein écran</button>
            <button className="btn btn-ghost" onClick={() => stopRef.current()}>Arrêter</button>
          </div>
        )
          : <button className="btn btn-primary" onClick={start}><Camera size={17} /> Démarrer la caméra</button>}
      </header>

      {!window.isSecureContext && (
        <div className="alert warn" style={{ marginBottom: 16 }}>
          <ShieldAlert size={18} />
          <span>Le navigateur n'autorise la caméra qu'en HTTPS (ou sur ce PC via localhost). Pour le téléphone : génère un certificat local avec mkcert (voir README), puis ouvre l'adresse https:// du PC.</span>
        </div>
      )}

      <div className="bike-layout">
        <div>
          <div className={`live${fs ? " is-fs" : ""}`} ref={liveRef}>
            <video ref={video} playsInline muted />
            <canvas ref={canvas} aria-hidden="true" />
            {running && <span className={`big-light ${allOk ? "go" : "wait"}`}>{allOk ? "Feu vert : tu peux filmer" : "Ajuste le cadrage"}</span>}
            {running && (
              <button type="button" className="live-fs-btn" onClick={toggleFullscreen} aria-label={fs ? "Quitter le plein écran" : "Plein écran"}>
                {fs ? <Minimize2 size={18} /> : <Maximize2 size={18} />}{fs && " Quitter"}
              </button>
            )}
            {running && fs && essential.some((c) => !c.ok) && (
              <ul className="live-todo" aria-live="polite">
                {essential.filter((c) => !c.ok).map((c) => (
                  <li key={c.id} className={c.ok ? "ok" : c.ok === false ? "ko" : ""}>
                    {c.ok ? <CheckCircle2 size={18} /> : c.ok === false ? <AlertTriangle size={18} /> : <CircleDashed size={18} />}
                    <span><strong>{c.label}</strong>{c.ok === false && <em>{c.hint}</em>}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="subtle" style={{ marginTop: 8, fontSize: "0.84rem" }}>{status}. Les pointillés : la hanche doit se trouver entre les deux lignes.</p>
        </div>
        <section className="card">
          <h2>Contrôles</h2>
          <ul className="checks" style={{ marginTop: 12 }}>
            {checks.map((c) => (
              <li key={c.id} className={`check ${c.ok ? "ok" : c.ok === false ? "ko" : ""}`}>
                {c.ok ? <CheckCircle2 size={18} /> : c.ok === false ? <AlertTriangle size={18} /> : <CircleDashed size={18} />}
                <div><strong>{c.label}</strong>{c.ok === false && <div className="subtle" style={{ fontSize: "0.82rem" }}>{c.hint}</div>}</div>
              </li>
            ))}
          </ul>
          <p className="subtle" style={{ fontSize: "0.8rem", marginTop: 12 }}>
            Le calcul se fait dans le navigateur (MediaPipe) : l'image ne quitte pas l'appareil. Le modèle (≈ 9 Mo) est téléchargé une fois depuis Google si aucune copie locale n'existe dans <code>public/mediapipe/</code>.
          </p>
        </section>
      </div>
    </div>
  );
}
