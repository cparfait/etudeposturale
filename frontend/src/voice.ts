// Voix du coach : lecture (Piper / OpenAI via le backend, ou voix du navigateur) et écoute du micro
// (appui pour parler ou mains libres avec détection de la parole). La reconnaissance se fait sur le PC (Whisper).

export type TtsEngine = "piper" | "openai" | "navigateur" | "aucune";

let current: HTMLAudioElement | null = null;
let token = 0;
const speakingListeners = new Set<(on: boolean) => void>();
let speaking = false;

function setSpeaking(on: boolean) {
  speaking = on;
  speakingListeners.forEach((f) => f(on));
}
export const isSpeaking = () => speaking;
export function onSpeaking(f: (on: boolean) => void) {
  speakingListeners.add(f);
  return () => { speakingListeners.delete(f); };
}

/** Texte lisible à voix haute : sans markdown ni symboles. */
export function plain(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[*_#>`]+/g, "")
    .replace(/^\s*[-•]\s+/gm, "")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

export function stopSpeaking() {
  token++;
  if (current) { current.pause(); current = null; }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  setSpeaking(false);
}

function browserSpeak(text: string, rate = 1): Promise<void> {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) return resolve();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "fr-FR";
    u.rate = rate;
    const fr = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("fr"));
    if (fr) u.voice = fr;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    window.speechSynthesis.speak(u);
  });
}

/** Lit un texte avec le moteur choisi. Repli sur la voix du navigateur si le moteur du PC échoue. */
export async function speak(text: string, engine: TtsEngine, rate = 1): Promise<void> {
  const t = plain(text);
  if (!t || engine === "aucune") return;
  stopSpeaking();
  const my = ++token;
  setSpeaking(true);
  try {
    if (engine === "navigateur") {
      await browserSpeak(t, rate);
      return;
    }
    const res = await fetch("/api/voice/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texte: t }) });
    if (!res.ok) {
      let msg = `${res.status}`;
      try { msg = (await res.json()).detail ?? msg; } catch { /* non JSON */ }
      throw new Error(msg);
    }
    const url = URL.createObjectURL(await res.blob());
    const audio = new Audio(url);
    if (my !== token) return; // une autre lecture a commencé entre-temps
    current = audio;
    await new Promise<void>((resolve) => {
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.onpause = () => resolve();
      audio.play().catch(() => resolve());
    });
    URL.revokeObjectURL(url);
  } finally {
    if (my === token) { current = null; setSpeaking(false); }
  }
}

export async function transcribe(blob: Blob): Promise<string> {
  const form = new FormData();
  form.append("file", blob, blob.type.includes("ogg") ? "parole.ogg" : "parole.webm");
  const res = await fetch("/api/voice/stt", { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? `${res.status}`);
  return (data.texte ?? "").trim();
}

export const micAvailable = () => !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

async function openMic(): Promise<MediaStream> {
  if (!micAvailable()) throw new Error("Micro indisponible (il faut Chrome ou Edge, en localhost ou en HTTPS).");
  return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
}

/** Appui pour parler : start() puis stop() renvoie l'enregistrement. */
export async function pushToTalk() {
  const stream = await openMic();
  const rec = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.start();
  return {
    stop: () => new Promise<Blob>((resolve) => {
      rec.onstop = () => { stream.getTracks().forEach((t) => t.stop()); resolve(new Blob(chunks, { type: rec.mimeType })); };
      rec.stop();
    }),
    cancel: () => { rec.onstop = null; rec.stop(); stream.getTracks().forEach((t) => t.stop()); },
  };
}

/**
 * Mains libres : écoute en continu, enregistre dès que tu parles, s'arrête après un silence
 * et envoie la phrase. Se met en pause pendant que le coach parle (pour ne pas s'écouter lui-même).
 */
export async function handsFree(opts: { onPhrase: (b: Blob) => void; onLevel?: (v: number) => void; onState?: (s: "ecoute" | "parole") => void }) {
  const stream = await openMic();
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  const an = ctx.createAnalyser();
  an.fftSize = 1024;
  src.connect(an);
  const buf = new Float32Array(an.fftSize);
  let noise = 0.01, rec: MediaRecorder | null = null, chunks: Blob[] = [], voiced = 0, silent = 0, started = 0, raf = 0, alive = true;

  const tick = () => {
    if (!alive) return;
    an.getFloatTimeDomainData(buf);
    let sum = 0;
    for (const v of buf) sum += v * v;
    const rms = Math.sqrt(sum / buf.length);
    opts.onLevel?.(Math.min(1, rms * 12));
    const thr = Math.max(0.02, noise * 3.2);
    if (speaking) {
      voiced = 0;
    } else if (!rec) {
      noise = noise * 0.97 + rms * 0.03; // bruit de fond (home trainer, ventilateur)
      voiced = rms > thr ? voiced + 1 : 0;
      if (voiced > 4) {
        rec = new MediaRecorder(stream);
        chunks = [];
        rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
        rec.onstop = () => {
          const r = rec!;
          rec = null;
          if (performance.now() - started > 600) opts.onPhrase(new Blob(chunks, { type: r.mimeType }));
          opts.onState?.("ecoute");
        };
        rec.start();
        started = performance.now();
        silent = 0;
        opts.onState?.("parole");
      }
    } else {
      silent = rms < thr * 0.8 ? silent + 1 : 0;
      const long = performance.now() - started > 20000;
      if (silent > 55 || long) rec.stop(); // ≈ 0,9 s de silence à 60 images/s
    }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  opts.onState?.("ecoute");
  return () => {
    alive = false;
    cancelAnimationFrame(raf);
    if (rec && rec.state !== "inactive") { rec.onstop = null; rec.stop(); }
    stream.getTracks().forEach((t) => t.stop());
    ctx.close();
  };
}

/** Commandes vocales comprises sans IA. */
export type Command = "repeter" | "stop" | "effacer" | "suivant" | "fait" | null;
export function command(text: string): Command {
  const t = text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z' ]/g, " ").replace(/\s+/g, " ").trim();
  if (/^(repete|repetes|tu peux repeter|redis|encore une fois)\b/.test(t)) return "repeter";
  if (/^(stop|tais toi|silence|chut|arrete)\b/.test(t)) return "stop";
  if (/^(efface|nouvelle conversation|on recommence)\b/.test(t)) return "effacer";
  if (/^(suivant|etape suivante|on continue|continue)$/.test(t)) return "suivant";
  if (/^(c'est fait|c est fait|fait|termine|ok c'est bon)$/.test(t)) return "fait";
  return null;
}
