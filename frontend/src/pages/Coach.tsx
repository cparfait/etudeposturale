import { Fragment, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Cloud, Ear, Eye, Image as ImageIcon, Loader2, Lock, Mic, Send, Settings2, Sparkles, Square, Trash2, Volume2, VolumeX, X } from "lucide-react";
import { http, type Any } from "../api";
import { useToast } from "../toast";
import { command, handsFree, isSpeaking, micAvailable, onSpeaking, pushToTalk, speak, stopSpeaking, transcribe, type TtsEngine } from "../voice";

interface Msg { role: "user" | "assistant"; content: string; vocal?: boolean; images?: number; erreur?: boolean }

const STORE = "posturale.coach.v1";
const SUGGESTIONS = [
  "Explique-moi le verdict sur ma hauteur de selle",
  "Quelle est la première chose à changer ?",
  "J'ai mal derrière le genou sur les longues sorties : pourquoi ?",
  "Mes deux jambes travaillent-elles pareil ?",
  "Prépare ma prochaine séance de capture",
];

function load(): Msg[] {
  try { return JSON.parse(localStorage.getItem(STORE) ?? "[]"); } catch { return []; }
}

/** Markdown minimal : paragraphes, listes, gras. */
function Rich({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  const inline = (s: string) => s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>);
  return (
    <>
      {blocks.map((b, i) => {
        const lines = b.split("\n").filter(Boolean);
        if (lines.length && lines.every((l) => /^\s*([-*•]|\d+[.)])\s+/.test(l))) {
          const ordered = /^\s*\d/.test(lines[0]);
          const items = lines.map((l, k) => <li key={k}>{inline(l.replace(/^\s*([-*•]|\d+[.)])\s+/, ""))}</li>);
          return ordered ? <ol key={i}>{items}</ol> : <ul key={i}>{items}</ul>;
        }
        return <p key={i}>{lines.map((l, k) => <Fragment key={k}>{k > 0 && <br />}{inline(l.replace(/^#+\s*/, ""))}</Fragment>)}</p>;
      })}
    </>
  );
}

export default function Coach() {
  const toast = useToast();
  const [cfg, setCfg] = useState<Any | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>(load);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState<"off" | "ptt" | "libre">("off");
  const [vadState, setVadState] = useState<"ecoute" | "parole">("ecoute");
  const [level, setLevel] = useState(0);
  const [transcribing, setTranscribing] = useState(false);
  const [readAloud, setReadAloud] = useState(true);
  const [withImages, setWithImages] = useState(false);
  const [speakingNow, setSpeakingNow] = useState(false);
  const [preview, setPreview] = useState<Any | null>(null);
  const ptt = useRef<Awaited<ReturnType<typeof pushToTalk>> | null>(null);
  const stopFree = useRef<null | (() => void)>(null);
  const thread = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);
  const msgsRef = useRef(msgs);
  msgsRef.current = msgs;

  useEffect(() => {
    http.get("/ai/settings").then((s) => { setCfg(s); setReadAloud(s.voix.lecture_auto && s.voix.tts !== "aucune"); });
    const off = onSpeaking(setSpeakingNow);
    return () => { off(); stopSpeaking(); stopFree.current?.(); abort.current?.abort(); };
  }, []);
  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify(msgs.slice(-40))); } catch { /* stockage indisponible */ }
    thread.current?.scrollTo({ top: thread.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  const provider = cfg?.fournisseurs.find((p: Any) => p.id === cfg.fournisseur);
  const tts: TtsEngine = cfg?.voix.tts ?? "navigateur";
  const rate = cfg?.voix.vitesse ?? 1;
  const lastAnswer = () => [...msgsRef.current].reverse().find((m) => m.role === "assistant" && !m.erreur);

  async function ask(text: string, vocal = false) {
    const q = text.trim();
    if (!q || busy) return;
    const history = [...msgsRef.current.filter((m) => !m.erreur), { role: "user" as const, content: q, vocal, images: withImages ? 1 : 0 }];
    setMsgs([...history, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    stopSpeaking();
    const ctrl = new AbortController();
    abort.current = ctrl;
    let answer = "", failed = "";
    try {
      const res = await fetch("/api/ai/chat", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: ctrl.signal,
        body: JSON.stringify({ messages: history.map(({ role, content }) => ({ role, content })), vocal: vocal || listening === "libre", images: withImages }),
      });
      if (!res.ok || !res.body) throw new Error((await res.json().catch(() => ({}))).detail ?? `${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          const ev = JSON.parse(part.slice(6));
          if (ev.t) {
            answer += ev.t;
            setMsgs((m) => [...m.slice(0, -1), { role: "assistant", content: answer }]);
          } else if (ev.debut) {
            setMsgs((m) => [...m.slice(0, -1), { role: "assistant", content: "", images: ev.images }]);
          } else if (ev.erreur) failed = ev.erreur;
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") failed = (e as Error).message;
    } finally {
      setBusy(false);
      abort.current = null;
    }
    if (failed) {
      setMsgs((m) => [...m.slice(0, -1), { role: "assistant", content: failed, erreur: true }]);
      return;
    }
    if (answer && (readAloud || vocal)) speak(answer, tts, rate).catch((e) => toast(`Voix : ${e.message}`, "error"));
  }

  async function handleSpoken(blob: Blob) {
    setTranscribing(true);
    try {
      const text = await transcribe(blob);
      if (!text) return;
      const cmd = command(text);
      if (cmd === "stop") return stopSpeaking();
      if (cmd === "repeter") { const a = lastAnswer(); if (a) speak(a.content, tts, rate); return; }
      if (cmd === "effacer") { stopSpeaking(); setMsgs([]); return; }
      await ask(text, true);
    } catch (e) {
      toast(`Micro : ${(e as Error).message}`, "error");
    } finally { setTranscribing(false); }
  }

  async function togglePtt() {
    if (listening === "ptt" && ptt.current) {
      const blob = await ptt.current.stop();
      ptt.current = null;
      setListening("off");
      handleSpoken(blob);
      return;
    }
    if (listening === "libre") { stopFree.current?.(); stopFree.current = null; }
    try { stopSpeaking(); ptt.current = await pushToTalk(); setListening("ptt"); }
    catch (e) { toast((e as Error).message, "error"); setListening("off"); }
  }

  async function toggleFree() {
    if (listening === "libre") { stopFree.current?.(); stopFree.current = null; setListening("off"); setLevel(0); return; }
    if (listening === "ptt") { ptt.current?.cancel(); ptt.current = null; }
    try {
      stopFree.current = await handsFree({ onPhrase: (b) => { if (!isSpeaking()) handleSpoken(b); }, onLevel: setLevel, onState: setVadState });
      setListening("libre");
      toast("Mains libres : parle quand tu veux. Dis « stop » pour couper le coach, « répète » pour réécouter.");
    } catch (e) { toast((e as Error).message, "error"); }
  }

  async function openPreview() {
    try { setPreview(await http.get(`/ai/context?images=${withImages}`)); } catch (e) { toast((e as Error).message, "error"); }
  }

  const empty = msgs.length === 0;

  return (
    <div className="page coach-page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Ton coach</div>
          <h1>Coach IA</h1>
          <p>Pose tes questions à l'écrit ou à la voix, même en pédalant. Le coach s'appuie sur tes mesures, ton vélo, tes douleurs et le moteur de recommandations — il n'invente pas de chiffres.</p>
        </div>
        <div className="row" style={{ gap: 8, alignSelf: "flex-start" }}>
          {provider && (
            <span className={`chip ${provider.local ? "ok" : "bike"}`} title={provider.local ? "Le modèle tourne sur ce PC : rien ne sort." : "Les données texte (et les images si tu les joins) partent chez ce fournisseur."}>
              {provider.local ? <Lock size={12} /> : <Cloud size={12} />} {provider.local ? "Sur ce PC" : "En ligne"} · {provider.nom.replace(/ \(.*\)$/, "")}{provider.modele ? ` · ${provider.modele}` : ""}
            </span>
          )}
          <Link to="/reglages-ia" className="btn btn-ghost btn-sm"><Settings2 size={14} /> Réglages</Link>
        </div>
      </header>

      {provider && !provider.modele && (
        <div className="alert warn" style={{ marginBottom: 14 }}><Settings2 size={16} /><span>Aucun modèle choisi pour {provider.nom}. <Link className="link" to="/reglages-ia">Ouvrir les réglages</Link> pour en choisir un et tester la connexion.</span></div>
      )}

      <div className="coach">
        <div className="coach-thread" ref={thread} aria-live="polite">
          {empty ? (
            <div className="coach-empty">
              <span className="coach-avatar lg"><Sparkles size={22} /></span>
              <h2>Que veux-tu savoir ?</h2>
              <p className="subtle">Exemples :</p>
              <div className="coach-suggest">
                {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>)}
              </div>
            </div>
          ) : msgs.map((m, i) => (
            <div key={i} className={`bubble-row ${m.role}`}>
              {m.role === "assistant" && <span className="coach-avatar"><Sparkles size={14} /></span>}
              <div className={`bubble ${m.role}${m.erreur ? " error" : ""}`}>
                {m.role === "assistant" && !m.content && busy && i === msgs.length - 1 ? (
                  <span className="typing"><i /><i /><i /></span>
                ) : m.role === "assistant" && !m.erreur ? <Rich text={m.content} /> : <p>{m.content}</p>}
                <div className="bubble-meta">
                  {m.vocal && <span><Mic size={11} /> à la voix</span>}
                  {!!m.images && m.role === "assistant" && <span><ImageIcon size={11} /> {m.images} image{m.images > 1 ? "s" : ""} analysée{m.images > 1 ? "s" : ""}</span>}
                  {m.role === "assistant" && m.content && !m.erreur && !(busy && i === msgs.length - 1) && (
                    <button className="bubble-btn" onClick={() => speak(m.content, tts, rate).catch((e) => toast(e.message, "error"))} aria-label="Lire à voix haute"><Volume2 size={13} /> Écouter</button>
                  )}
                  {m.erreur && <Link className="bubble-btn" to="/reglages-ia"><Settings2 size={13} /> Réglages</Link>}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="coach-composer">
          {listening === "libre" && (
            <div className={`vad ${vadState}`}>
              <Ear size={15} /> {transcribing ? "Je transcris…" : speakingNow ? "Le coach parle — dis « stop » pour le couper" : vadState === "parole" ? "Je t'écoute…" : "Mains libres : parle quand tu veux"}
              <span className="vad-meter"><span style={{ width: `${Math.round(level * 100)}%` }} /></span>
            </div>
          )}
          <form className="composer-row" onSubmit={(e) => { e.preventDefault(); ask(input); }}>
            <textarea className="textarea" rows={1} value={input} placeholder={transcribing ? "Transcription…" : "Écris ta question…"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input); } }} />
            {busy ? (
              <button type="button" className="btn btn-ghost" onClick={() => abort.current?.abort()} aria-label="Arrêter la réponse"><Square size={16} /></button>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={!input.trim()} aria-label="Envoyer"><Send size={16} /></button>
            )}
          </form>
          <div className="composer-tools">
            {micAvailable() && (
              <>
                <button type="button" className={`tool ${listening === "ptt" ? "rec" : ""}`} onClick={togglePtt} disabled={transcribing && listening !== "ptt"}>
                  {transcribing && listening === "off" ? <Loader2 size={15} className="spin" /> : listening === "ptt" ? <Square size={15} /> : <Mic size={15} />}
                  {listening === "ptt" ? "Envoyer ma question" : "Parler"}
                </button>
                <button type="button" className={`tool ${listening === "libre" ? "on" : ""}`} onClick={toggleFree} aria-pressed={listening === "libre"}>
                  <Ear size={15} /> Mains libres
                </button>
              </>
            )}
            <button type="button" className={`tool ${readAloud ? "on" : ""}`} aria-pressed={readAloud} onClick={() => { if (readAloud) stopSpeaking(); setReadAloud(!readAloud); }}>
              {readAloud ? <Volume2 size={15} /> : <VolumeX size={15} />} Lire les réponses
            </button>
            <button type="button" className={`tool ${withImages ? "on" : ""}`} aria-pressed={withImages} disabled={!cfg?.images}
              title={cfg?.images ? "Joindre les images clés de la dernière analyse" : "À autoriser dans les réglages de l'IA"} onClick={() => setWithImages(!withImages)}>
              <ImageIcon size={15} /> Joindre les images
            </button>
            <span style={{ flex: 1 }} />
            {speakingNow && <button type="button" className="tool" onClick={stopSpeaking}><VolumeX size={15} /> Couper</button>}
            <button type="button" className="tool" onClick={openPreview}><Eye size={15} /> Ce que voit le coach</button>
            {!empty && <button type="button" className="tool" onClick={() => { stopSpeaking(); setMsgs([]); }} aria-label="Effacer la conversation"><Trash2 size={15} /></button>}
          </div>
        </div>
      </div>

      {preview && (
        <div className="drawer-back" onClick={() => setPreview(null)}>
          <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Données envoyées au coach">
            <div className="row between">
              <h3 style={{ margin: 0 }}>Ce que voit le coach</h3>
              <button className="icon-btn" onClick={() => setPreview(null)} aria-label="Fermer"><X size={16} /></button>
            </div>
            <div className={`alert ${preview.local ? "ok" : "warn"}`}>
              {preview.local ? <Lock size={16} /> : <Cloud size={16} />}
              <span>{preview.local ? `Modèle sur ce PC (${preview.fournisseur}) : rien ne sort.` : `Envoyé à ${preview.fournisseur} à chaque question : ce texte${preview.images.length ? " et les images ci-dessous" : ""}. Jamais la vidéo.`}</span>
            </div>
            {preview.images.length > 0 && (
              <div className="drawer-imgs">
                {preview.images.map((im: Any, i: number) => <figure key={i}><img src={im.url} alt={im.legende} /><figcaption>{im.legende}</figcaption></figure>)}
              </div>
            )}
            <pre className="drawer-pre">{preview.texte}</pre>
          </aside>
        </div>
      )}
    </div>
  );
}
