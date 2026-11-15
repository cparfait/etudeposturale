import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, CircleDashed, Maximize2, Minimize2, ShieldAlert, SwitchCamera } from "lucide-react";
import type { NormalizedLandmark, PoseLandmarker } from "@mediapipe/tasks-vision";
import FramingGoal from "../components/FramingGoal";
import OpenOnPhone from "../components/OpenOnPhone";

// Modèle : d'abord une copie locale (public/mediapipe/), sinon le fichier officiel de Google (téléchargé une fois par le navigateur).
const MODEL_LOCAL = "/mediapipe/pose_landmarker_full.task";
const MODEL_REMOTE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task";

interface Check { id: string; label: string; ok: boolean | null; hint: string }

const BONES = [[11, 12], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28], [27, 31], [28, 32], [11, 13], [13, 15], [12, 14], [14, 16]];

/** Images par tour de pédale à 90 tr/min : ce qui compte pour mesurer l'extension du genou. */
const perTurn = (fps: number) => Math.round((fps * 60) / 90);

function fpsCheck(fps: number | undefined, width: number, height: number): Check {
  const res = width && height ? ` en ${width}×${height}` : "";
  if (fps == null) return { id: "fps", label: "Images par seconde : mesure en cours…", ok: null, hint: "" };
  const f = Math.round(fps);
  if (f >= 50) return { id: "fps", label: `${f} images/s${res} : parfait pour la mesure`, ok: true, hint: "" };
  if (f >= 24) return {
    id: "fps", label: `${f} images/s${res} mesurées`, ok: false,
    hint: `Assez pour cadrer. Pour la mesure : ${perTurn(f)} images par tour de pédale (40 à 60 images/s), donc un genou moins précis `
      + "et plus de flou. Filme la mesure en 60 images/s si tu peux (téléphone) ; avec cette caméra, éclaire bien : beaucoup de webcams ralentissent dans la pénombre.",
  };
  return {
    id: "fps", label: `Seulement ${f} images/s${res}`, ok: false,
    hint: "Trop peu pour mesurer : ajoute de la lumière (les webcams baissent la cadence quand il fait sombre), ferme les autres applis qui utilisent la caméra, ou passe sur un téléphone.",
  };
}

function evaluate(lm: NormalizedLandmark[] | undefined, luminance: number, fps: number | undefined, landscape: boolean, vw = 0, vh = 0): Check[] {
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
    fpsCheck(fps, vw, vh),
    { id: "resolution", label: "Image d'au moins 1280 × 720", ok: vw ? vw >= 1280 || vh >= 1280 : null,
      hint: "Résolution trop basse : les pastilles deviennent trop petites. Choisis une caméra ou un mode en 720p ou 1080p." },
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
  const CAM_KEY = "posturale.camera";
  const [cams, setCams] = useState<MediaDeviceInfo[]>([]);
  const [camId, setCamId] = useState<string>(() => { try { return localStorage.getItem(CAM_KEY) ?? ""; } catch { return ""; } });
  const gen = useRef(0);                         // chaque démarrage a son numéro : un démarrage dépassé s'arrête tout seul

  // La caméra démarre dès l'ouverture de la page
  useEffect(() => {
    if ("mediaDevices" in navigator) start(camId || undefined);
    return () => { gen.current++; stopRef.current(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
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

  async function start(deviceId?: string) {
    const my = ++gen.current;
    try {
      setStatus("Chargement du modèle de pose…");
      const { FilesetResolver, PoseLandmarker } = await import("@mediapipe/tasks-vision");
      const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
      const local = await fetch(MODEL_LOCAL, { method: "HEAD" }).then((r) => r.ok && r.headers.get("content-type") !== "text/html").catch(() => false);
      const landmarker: PoseLandmarker = await PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: local ? MODEL_LOCAL : MODEL_REMOTE, delegate: "GPU" },
        runningMode: "VIDEO", numPoses: 1,
      });
      if (my !== gen.current) { landmarker.close(); return; }
      setStatus("Ouverture de la caméra…");
      const size = { width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 60 } };
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: deviceId ? { deviceId: { exact: deviceId }, ...size } : { facingMode: "environment", ...size }, audio: false });
      } catch (err) {
        if (!deviceId) throw err;                  // la caméra mémorisée n'existe plus : celle par défaut
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", ...size }, audio: false });
      }
      if (my !== gen.current) { stream.getTracks().forEach((t) => t.stop()); landmarker.close(); return; }
      const used = stream.getVideoTracks()[0]?.getSettings().deviceId ?? "";
      setCamId(used);
      navigator.mediaDevices.enumerateDevices().then((d) => setCams(d.filter((x) => x.kind === "videoinput"))).catch(() => {});
      const v = video.current!;
      v.srcObject = stream;
      await v.play();
      // Cadence réelle : images effectivement reçues (et non la valeur annoncée par la caméra), sur une fenêtre glissante de 2 s
      let fps: number | undefined;
      const stamps: number[] = [];
      type RVFC = (cb: (now: number) => void) => number;
      const rvfc = (v as unknown as { requestVideoFrameCallback?: RVFC }).requestVideoFrameCallback?.bind(v);
      let alive = true;
      if (rvfc) {
        const onFrame = (now: number) => {
          if (!alive) return;
          stamps.push(now);
          while (stamps.length && now - stamps[0] > 2000) stamps.shift();
          if (stamps.length > 10 && now - stamps[0] > 1000) fps = ((stamps.length - 1) * 1000) / (now - stamps[0]);
          rvfc(onFrame);
        };
        rvfc(onFrame);
      } else {
        fps = stream.getVideoTracks()[0].getSettings().frameRate;  // repli : valeur annoncée
      }
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
        setChecks(evaluate(lm, lum, fps, v.videoWidth >= v.videoHeight, v.videoWidth, v.videoHeight));
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
        alive = false;
        stream.getTracks().forEach((t) => t.stop());
        landmarker.close();
        setRunning(false);
        setStatus("Caméra arrêtée");
      };
    } catch (e) {
      const m = (e as Error).message;
      setStatus(/denied|NotAllowed|permission/i.test(m)
        ? "Accès à la caméra refusé : autorise-le dans la barre d'adresse du navigateur, puis « Démarrer la caméra »"
        : /NotFound|Requested device/i.test(m) ? "Aucune caméra trouvée sur cet appareil" : `Impossible de démarrer : ${m}`);
    }
  }

  function switchCam(id: string) {
    try { localStorage.setItem(CAM_KEY, id); } catch { /* stockage indisponible */ }
    setCamId(id);
    stopRef.current();
    start(id);
  }
  const nextCam = () => {
    if (cams.length < 2) return;
    const i = cams.findIndex((c) => c.deviceId === camId);
    switchCam(cams[(i + 1) % cams.length].deviceId);
  };
  const camLabel = (c: MediaDeviceInfo, i: number) => c.label || `Caméra ${i + 1}`;

  const essential = checks.filter((c) => c.id !== "fps");  // la cadence n'empêche pas de cadrer : elle prévient sur la qualité
  const allOk = running && essential.every((c) => c.ok);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Avant d'enregistrer</div>
          <h1>Cadrage en direct</h1>
          <p>Ouvre cette page sur le téléphone posé sur son trépied : quand tout est vert, passe dans l'appli Appareil photo pour filmer la mesure.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {cams.length > 1 && (
            <label className="cam-pick">
              <SwitchCamera size={16} />
              <select className="select" value={camId} onChange={(e) => switchCam(e.target.value)} aria-label="Caméra utilisée">
                {cams.map((c, i) => <option key={c.deviceId} value={c.deviceId}>{camLabel(c, i)}</option>)}
              </select>
            </label>
          )}
          {running ? (
            <>
              <button className="btn btn-primary" onClick={toggleFullscreen}><Maximize2 size={16} /> Plein écran</button>
              <button className="btn btn-ghost" onClick={() => stopRef.current()}>Arrêter</button>
            </>
          ) : <button className="btn btn-primary" onClick={() => start(camId || undefined)}><Camera size={17} /> Démarrer la caméra</button>}
        </div>
      </header>

      {!window.isSecureContext && (
        <div className="alert warn" style={{ marginBottom: 16 }}>
          <ShieldAlert size={18} />
          <span>Le navigateur n'autorise la caméra qu'en HTTPS (ou sur ce PC via localhost). Pour le téléphone : lance scripts\lancer.bat après l'installation (HTTPS automatique), puis scanne le QR code ci-dessous.</span>
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
            {running && fs && cams.length > 1 && (
              <button type="button" className="live-fs-btn cam" onClick={nextCam} aria-label="Caméra suivante"><SwitchCamera size={18} /> Changer de caméra</button>
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
          <FramingGoal />
        </div>
        <div>
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
          <OpenOnPhone path="/cadrage">
            <p className="subtle" style={{ fontSize: "0.8rem" }}>Pour filmer depuis le téléphone avec départ lancé par le PC, utilise plutôt le QR code d'une séance (Séances de capture ou Séance guidée).</p>
          </OpenOnPhone>
        </div>
      </div>
    </div>
  );
}
