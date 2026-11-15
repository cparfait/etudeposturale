import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, CircleDot, Loader2, Maximize2, Minimize2, MonitorUp, Smartphone, Upload } from "lucide-react";
import { LogoMark } from "../Layout";

// Page du téléphone relié à une séance : aperçu caméra, enregistrement lancé depuis le PC, envoi automatique.

type State = "connexion" | "pret" | "enregistre" | "envoi" | "envoye" | "erreur";
interface Cmd { id: string; action: "start" | "stop"; duree_s: number }
const ROLES = [["profil_D", "Profil droit"], ["profil_G", "Profil gauche"], ["face", "Vue de face"], ["dos", "Vue de dos"]] as const;
const KEY = "posturale.tel";
let joining: Promise<{ appareil: string; role: string; session_id: number }> | null = null;  // une seule connexion par page

const api = async (path: string, init?: RequestInit) => {
  const r = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? `${r.status}`);
  return data;
};

function deviceName() {
  const ua = navigator.userAgent;
  const m = ua.match(/\(([^;)]+);[^)]*?;\s*([^;)]+?)\s*(Build|\))/);
  if (/iPhone/.test(ua)) return "iPhone";
  const model = m?.[2] ?? "";
  if (!model || model === "wv" || model === "K") return /Android/.test(ua) ? "Android" : "Téléphone";  // Chrome masque le modèle (« K »)
  return model.slice(0, 30);
}

function pickMime(): { mime: string; ext: string } {
  const opts: [string, string][] = [["video/mp4;codecs=avc1.640028", "mp4"], ["video/mp4", "mp4"], ["video/webm;codecs=vp9", "webm"], ["video/webm", "webm"]];
  for (const [m, e] of opts) if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m)) return { mime: m, ext: e };
  return { mime: "", ext: "webm" };
}

/** Envoi avec progression (XMLHttpRequest), puis lancement de l'analyse. */
function uploadVideo(sid: number, vue: string, blob: Blob, name: string, onProgress: (p: number) => void): Promise<number> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", blob, name);
    form.append("vue", vue);
    form.append("appareil", deviceName());
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/sessions/${sid}/captures`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = async () => {
      try {
        const cap = JSON.parse(xhr.responseText);
        if (xhr.status >= 400) throw new Error(cap.detail ?? `${xhr.status}`);
        await api(`/captures/${cap.id}/analyze`, { method: "POST", body: JSON.stringify({ duree_s: 45 }) });
        resolve(cap.id);
      } catch (e) { reject(e); }
    };
    xhr.onerror = () => reject(new Error("Envoi impossible : le PC est-il toujours allumé et sur le même Wi-Fi ?"));
    xhr.send(form);
  });
}

export default function Phone() {
  const [params] = useSearchParams();
  const code = (params.get("c") ?? "").toUpperCase();
  const [device, setDevice] = useState<string | null>(null);
  const [sid, setSid] = useState<number | null>(null);
  const [role, setRole] = useState("profil_D");
  const [state, setState] = useState<State>("connexion");
  const [msg, setMsg] = useState("");
  const [left, setLeft] = useState(0);
  const [progress, setProgress] = useState(0);
  const [fps, setFps] = useState<number | null>(null);
  const [camErr, setCamErr] = useState("");
  const [fs, setFs] = useState(false);          // plein écran : API du navigateur, sinon (iPhone) l'image occupe tout l'écran en CSS
  const viewRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onChange = () => { if (!document.fullscreenElement && !(document as unknown as { webkitFullscreenElement?: Element }).webkitFullscreenElement) setFs(false); };
    document.addEventListener("fullscreenchange", onChange);
    document.addEventListener("webkitfullscreenchange", onChange);
    return () => { document.removeEventListener("fullscreenchange", onChange); document.removeEventListener("webkitfullscreenchange", onChange); };
  }, []);
  async function toggleFs() {
    type FsEl = HTMLElement & { webkitRequestFullscreen?: () => Promise<void> | void };
    type FsDoc = Document & { webkitFullscreenElement?: Element; webkitExitFullscreen?: () => void };
    const d = document as FsDoc;
    if (fs) {
      try { if (d.fullscreenElement) await d.exitFullscreen(); else if (d.webkitFullscreenElement) d.webkitExitFullscreen?.(); } catch { /* déjà sorti */ }
      setFs(false);
      return;
    }
    setFs(true);
    const el = viewRef.current as FsEl | null;
    try {
      if (el?.requestFullscreen) await el.requestFullscreen({ navigationUI: "hide" });
      else await el?.webkitRequestFullscreen?.();
    } catch { /* repli CSS */ }
    try { await (screen.orientation as unknown as { lock?: (o: string) => Promise<void> }).lock?.("landscape"); } catch { /* non pris en charge */ }
  }
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const lastCmd = useRef<string | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const captureId = useRef<number | null>(null);
  const fpsRef = useRef<number | null>(null);
  const msgRef = useRef("");
  msgRef.current = msg;
  const secure = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia;
  const [watched, setWatched] = useState(false);   // un écran du PC affiche l'aperçu
  const watchedRef = useRef(false);

  // Rejoindre la séance (ou reprendre après un rechargement de la page)
  useEffect(() => {
    if (!code) { setState("erreur"); setMsg("Lien incomplet : scanne le QR code affiché sur le PC."); return; }
    const saved = (() => { try { return JSON.parse(sessionStorage.getItem(KEY) ?? "null"); } catch { return null; } })();
    if (saved?.code === code) { setDevice(saved.device); setState("pret"); return; }
    joining ??= api(`/remote/${code}/join`, { method: "POST", body: JSON.stringify({ nom: deviceName(), secure }) });
    joining
      .then((r) => {
        setDevice(r.appareil); setRole(r.role); setSid(r.session_id); setState("pret");
        try { sessionStorage.setItem(KEY, JSON.stringify({ code, device: r.appareil })); } catch { /* ignore */ }
      })
      .catch((e) => { setState("erreur"); setMsg(e.message); });
  }, [code, secure]);

  // Caméra : aperçu en continu, cadence réelle mesurée ; écran maintenu allumé
  useEffect(() => {
    if (!secure || !device) return;
    let alive = true;
    navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 60 } }, audio: false,
    }).then((s) => {
      if (!alive) { s.getTracks().forEach((t) => t.stop()); return; }
      stream.current = s;
      const v = video.current!;
      v.srcObject = s;
      v.play().catch(() => {});
      const stamps: number[] = [];
      const rvfc = (v as unknown as { requestVideoFrameCallback?: (cb: (n: number) => void) => number }).requestVideoFrameCallback?.bind(v);
      if (rvfc) {
        const on = (now: number) => {
          if (!alive) return;
          stamps.push(now);
          while (stamps.length && now - stamps[0] > 2000) stamps.shift();
          if (stamps.length > 10) fpsRef.current = ((stamps.length - 1) * 1000) / (now - stamps[0]);
          rvfc(on);
        };
        rvfc(on);
      }
    }).catch((e) => setCamErr(/denied|NotAllowed/i.test(e.message) ? "Accès à la caméra refusé : autorise-le, puis recharge la page." : e.message));
    let lock: { release: () => Promise<void> } | null = null;
    (navigator as unknown as { wakeLock?: { request: (t: string) => Promise<typeof lock> } }).wakeLock?.request("screen").then((l) => { lock = l; }).catch(() => {});
    return () => { alive = false; stream.current?.getTracks().forEach((t) => t.stop()); lock?.release().catch(() => {}); };
  }, [secure, device]);

  const send = useCallback(async (blob: Blob, ext: string) => {
    if (!sid) { setState("erreur"); setMsg("Séance inconnue : rescanne le QR code."); return; }
    setState("envoi"); setProgress(0);
    try {
      const vue = role.startsWith("profil") ? "profil" : role;
      captureId.current = await uploadVideo(sid, vue, blob, `tel-${role}-${new Date().toISOString().slice(11, 19).replace(/:/g, "")}.${ext}`, setProgress);
      setState("envoye"); setMsg("");
    } catch (e) { setState("erreur"); setMsg((e as Error).message); }
  }, [sid, role]);

  const startRec = useCallback((cmd: Cmd) => {
    if (!stream.current || rec.current) return;
    const { mime, ext } = pickMime();
    const chunks: Blob[] = [];
    const r = new MediaRecorder(stream.current, { ...(mime ? { mimeType: mime } : {}), videoBitsPerSecond: 12_000_000 });
    r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    r.onstop = () => { rec.current = null; send(new Blob(chunks, { type: mime || "video/webm" }), ext); };
    r.start(1000);
    rec.current = r;
    setState("enregistre");
    const end = performance.now() + cmd.duree_s * 1000;
    const tick = () => {
      if (!rec.current) return;
      const l = Math.max(0, (end - performance.now()) / 1000);
      setLeft(l);
      if (l <= 0) rec.current.stop(); else requestAnimationFrame(tick);
    };
    tick();
  }, [send]);

  // Interrogation du PC toutes les secondes : état du téléphone, commande à exécuter
  useEffect(() => {
    if (!device) return;
    const id = setInterval(async () => {
      try {
        const r = await api(`/remote/${code}/poll`, { method: "POST", body: JSON.stringify({
          appareil: device, etat: stateRef.current === "connexion" ? "connecte" : stateRef.current,
          capture_id: captureId.current, message: msgRef.current, fps: fpsRef.current,
          largeur: video.current?.videoWidth || null, hauteur: video.current?.videoHeight || null,
        }) });
        watchedRef.current = !!r.apercu; setWatched(!!r.apercu);
        setFps(fpsRef.current);
        setRole(r.role); setSid(r.session_id);
        const cmd: Cmd | null = r.commande;
        if (cmd && cmd.id !== lastCmd.current) {
          lastCmd.current = cmd.id;
          if (cmd.action === "start") {
            if (secure && stream.current) { captureId.current = null; startRec(cmd); }
            else { setState("erreur"); setMsg("Caméra indisponible ici : filme avec l'appli Appareil photo, puis « Envoyer une vidéo déjà filmée »."); }
          }
          if (cmd.action === "stop" && rec.current) rec.current.stop();
        }
      } catch (e) {
        if (/inconnu/i.test((e as Error).message)) { try { sessionStorage.removeItem(KEY); } catch { /* ignore */ } location.reload(); }
      }
    }, 1000);
    return () => clearInterval(id);
  }, [device, code, secure, startRec]);

  // Aperçu en direct vers le PC : petites images JPEG, seulement quand un écran regarde (10 i/s, 3 pendant l'enregistrement)
  useEffect(() => {
    if (!secure || !device) return;
    let ws: WebSocket | null = null;
    let busy = false;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d")!;
    let last = 0;
    const id = setInterval(() => {
      const v = video.current;
      if (!watchedRef.current) { if (ws) { ws.close(); ws = null; } return; }
      if (!ws || ws.readyState > 1) {
        ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/remote/${code}/flux/${device}`);
        return;
      }
      const gap = stateRef.current === "enregistre" ? 330 : 100;
      if (ws.readyState !== 1 || busy || ws.bufferedAmount > 0 || !v || v.readyState < 2 || performance.now() - last < gap) return;
      last = performance.now();
      const w = Math.min(960, v.videoWidth);
      canvas.width = w; canvas.height = Math.round((w * v.videoHeight) / v.videoWidth);
      ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
      busy = true;
      canvas.toBlob((b) => { busy = false; if (b && ws?.readyState === 1) ws.send(b); }, "image/jpeg", 0.65);
    }, 50);
    return () => { clearInterval(id); ws?.close(); };
  }, [secure, device, code]);

  async function changeRole(r: string) {
    setRole(r);
    await api(`/remote/${code}/appareils/${device}`, { method: "PUT", body: JSON.stringify({ role: r }) }).catch(() => {});
  }

  const roleLabel = ROLES.find(([id]) => id === role)?.[1] ?? role;
  return (
    <div className="tel">
      <header className="tel-top">
        <LogoMark size={30} />
        <div className="grow"><strong>Téléphone relié</strong><small>{sid == null && state !== "connexion" ? "Cadrage" : "Séance"} {code}</small></div>
        <select className="select tel-role" value={role} onChange={(e) => changeRole(e.target.value)} aria-label="Vue filmée par ce téléphone" disabled={state === "enregistre"}>
          {ROLES.map(([id, l]) => <option key={id} value={id}>{l}</option>)}
        </select>
      </header>

      {secure ? (
        <div className={`tel-view${fs ? " is-fs" : ""}`} ref={viewRef}>
          <video ref={video} playsInline muted />
          <span className="tel-line" style={{ top: "30%" }} /><span className="tel-line" style={{ top: "60%" }} />
          <span className="tel-badge">{roleLabel}{fps ? ` · ${Math.round(fps)} i/s` : ""}</span>
          {watched && <span className="tel-watched"><MonitorUp size={15} /> Image visible sur le PC</span>}
          {state === "enregistre" && <span className="tel-rec"><CircleDot size={18} /> REC {Math.ceil(left)} s</span>}
          <button type="button" className="tel-fs" aria-label={fs ? "Quitter le plein écran" : "Plein écran"} onClick={toggleFs}>{fs ? <Minimize2 size={20} /> : <Maximize2 size={18} />}</button>
        </div>
      ) : (
        <div className="tel-nocam"><AlertTriangle size={18} /><span>Ce navigateur n'autorise pas la caméra sans HTTPS : filme avec l'appli Appareil photo (1080p, 60 i/s), puis envoie la vidéo ci-dessous.</span></div>
      )}
      {camErr && <p className="tel-msg bad">{camErr}</p>}

      <section className={`tel-status ${state}`} aria-live="polite">
        {state === "connexion" && <><Loader2 className="spin" size={18} /> Connexion à la séance…</>}
        {state === "pret" && <><Smartphone size={18} /> {!secure ? "Relié au PC. Envoie ta vidéo quand elle est filmée."
          : sid == null ? "Relié au cadrage : pose le téléphone sur son trépied et regarde l'écran du PC, les contrôles s'y affichent."
          : "Prêt. Pose le téléphone sur son trépied : l'enregistrement démarrera depuis le PC."}</>}
        {state === "enregistre" && <><CircleDot size={18} /> Enregistrement en cours — ne touche pas au téléphone.</>}
        {state === "envoi" && <><Loader2 className="spin" size={18} /> Envoi de la vidéo au PC… {Math.round(progress * 100)} %</>}
        {state === "envoye" && <><CheckCircle2 size={18} /> Vidéo envoyée : l'analyse démarre sur le PC. Le téléphone reste prêt pour la prise suivante.</>}
        {state === "erreur" && <><AlertTriangle size={18} /> {msg || "Erreur"}</>}
      </section>
      {state === "envoi" && <div className="tel-bar"><span style={{ width: `${progress * 100}%` }} /></div>}

      {sid != null && <label className="btn btn-ghost tel-upload">
        <Upload size={16} /> Envoyer une vidéo déjà filmée ({roleLabel.toLowerCase()})
        <input type="file" accept="video/*" hidden disabled={state === "enregistre" || state === "envoi"}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) send(f, (f.name.split(".").pop() ?? "mp4").toLowerCase()); e.target.value = ""; }} />
      </label>}
    </div>
  );
}
