import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, Mic, RotateCcw } from "lucide-react";
import { command, micAvailable, pushToTalk, transcribe } from "../voice";

type State = "idle" | "rec" | "busy" | "ok" | "empty" | "error";

/**
 * Test du micro : 3 secondes d'enregistrement, reconnaissance sur le PC (Whisper), puis ce qui a été entendu.
 * `onResult(true)` quand une phrase a été comprise.
 */
export default function MicTest({ onResult }: { onResult?: (ok: boolean) => void }) {
  const [state, setState] = useState<State>("idle");
  const [heard, setHeard] = useState("");
  const [err, setErr] = useState("");
  const [left, setLeft] = useState(3);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);

  if (!micAvailable()) {
    return <p className="mic-test-msg warn">Micro indisponible dans ce navigateur (il faut Chrome ou Edge, sur ce PC ou en HTTPS).</p>;
  }

  async function run() {
    setErr(""); setHeard("");
    try {
      const rec = await pushToTalk();
      setState("rec"); setLeft(3);
      let n = 3;
      timer.current = window.setInterval(() => { n -= 1; setLeft(n); }, 1000);
      await new Promise((r) => setTimeout(r, 3000));
      if (timer.current) window.clearInterval(timer.current);
      const blob = await rec.stop();
      setState("busy");
      const text = await transcribe(blob);
      setHeard(text);
      setState(text ? "ok" : "empty");
      onResult?.(!!text);
    } catch (e) {
      const m = (e as Error).message;
      setErr(/denied|permission|NotAllowed/i.test(m) ? "Accès au micro refusé : autorise-le dans la barre d'adresse du navigateur." : m);
      setState("error");
      onResult?.(false);
    }
  }

  return (
    <div className="mic-test" onClick={(e) => e.stopPropagation()}>
      {state === "idle" && <button type="button" className="mic-test-btn" onClick={run}><Mic size={15} /> Tester le micro</button>}
      {state === "rec" && <span className="mic-test-msg rec"><i className="rec-dot" /> Parle maintenant, par exemple « c'est parti »… {left} s</span>}
      {state === "busy" && <span className="mic-test-msg"><Loader2 size={14} className="spin" /> Je transcris sur le PC (la première fois, le modèle se charge : jusqu'à 30 s)…</span>}
      {state === "ok" && (
        <span className="mic-test-msg ok"><CheckCircle2 size={15} /> J'ai entendu : « {heard} »{command(heard) === "partir" ? " — commande reconnue." : ""}</span>
      )}
      {state === "empty" && <span className="mic-test-msg warn">Je n'ai rien entendu. Rapproche-toi du micro ou monte le volume d'entrée.</span>}
      {state === "error" && <span className="mic-test-msg warn">{err}</span>}
      {(state === "ok" || state === "empty" || state === "error") && (
        <button type="button" className="mic-test-btn ghost" onClick={run}><RotateCcw size={14} /> Recommencer</button>
      )}
    </div>
  );
}
