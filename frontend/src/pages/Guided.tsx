import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowLeft, ArrowRight, Bluetooth, Check, CheckCircle2, ChevronRight, Cloud, Ear, ExternalLink, FileUp, Gauge, Loader2, Lock, Mic,
  Pause, Play, RotateCcw, Settings2, Sparkles, Square, Stethoscope, Timer, Volume2, VolumeX, Wand2, Wrench, Zap,
} from "lucide-react";
import { http, type Any } from "../api";
import { useToast } from "../toast";
import { bluetoothAvailable, connectPower, connectTrainer, type PowerSample, type Trainer } from "../ble";
import { command, handsFree, isSpeaking, micAvailable, onSpeaking, pushToTalk, speak, stopSpeaking, transcribe, type TtsEngine } from "../voice";
import { streamChat, type ChatMsg } from "../ai";
import { useEquipment } from "../equipment";
import { useRemote, ETAT_LABEL, type Device } from "../remote";
import PhonePairing from "../components/PhonePairing";
import { TutoButton } from "../components/TutoVideo";

type StepType = "info" | "checklist" | "ble" | "timer" | "prise" | "import" | "debrief" | "fin";
interface Step {
  id: string; type: StepType; titre: string; dire: string; items?: { t: string; d: string }[]; lien?: string;
  duree_s?: number; puissance_w?: number | null; vue?: string; cote?: string; cle?: string; conseil_ia?: string; appareils?: string[];
}
interface Plan {
  type: "premiere" | "verification" | "suivi"; titre: string; raisons: string[]; vues: string[]; puissance_w: number; cadence: string;
  echauffement_min: number; changements: Any[]; etapes: Step[]; ia: Any;
  equipement?: { pastilles_vertes: boolean; trainer: boolean; capteur_puissance: boolean; micro: boolean; mire_seule: boolean };
}
interface Run {
  plan: Plan; sid: number; idx: number; started: string;
  ticks: Record<string, number>;     // checklist : nombre de points faits
  done: Record<string, boolean>;     // minuteries terminées
  uploads: Record<string, number>;   // prise prévue → vidéo importée
  applied?: number;                  // configuration créée par la modification
}

const STORE = "posturale.guide.v1";
const VIEW_LABEL: Record<string, string> = { profil_D: "Profil droit", profil_G: "Profil gauche", face: "Vue de face", dos: "Vue de dos" };
const TYPE_LABEL: Record<string, string> = { premiere: "Première séance", verification: "Vérification", suivi: "Suivi" };

function loadRun(): Run | null {
  try { return JSON.parse(localStorage.getItem(STORE) ?? "null"); } catch { return null; }
}
function saveRun(r: Run | null) {
  try { if (r) localStorage.setItem(STORE, JSON.stringify(r)); else localStorage.removeItem(STORE); } catch { /* stockage indisponible */ }
}
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const words = (n: number) => (n >= 60 ? `${Math.round(n / 60)} minute${n >= 120 ? "s" : ""}` : `${n} secondes`);

/** Durée estimée de la séance (minutes). */
function estimate(p: Plan) {
  return Math.round(12 + p.echauffement_min + p.vues.length * 3 + 8);
}

export default function Guided() {
  const toast = useToast();
  const nav = useNavigate();
  const eqState = useEquipment();
  const [cfg, setCfg] = useState<Any | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [adapting, setAdapting] = useState(false);
  const [run, setRunState] = useState<Run | null>(null);
  const [saved, setSaved] = useState<Run | null>(loadRun);
  const runRef = useRef<Run | null>(null);
  const setRun = useCallback((f: Run | null | ((r: Run) => Run)) => {
    setRunState((prev) => {
      const next = typeof f === "function" ? (prev ? f(prev) : prev) : f;
      runRef.current = next;
      saveRun(next);
      return next;
    });
  }, []);

  // voix
  const [muted, setMuted] = useState(false);
  const [speakingNow, setSpeakingNow] = useState(false);
  const [listening, setListening] = useState<"off" | "ptt" | "libre">("off");
  const [vadState, setVadState] = useState<"ecoute" | "parole">("ecoute");
  const [level, setLevel] = useState(0);
  const [heard, setHeard] = useState("");
  const [thinking, setThinking] = useState(false);
  const [answer, setAnswer] = useState("");
  const qa = useRef<ChatMsg[]>([]);
  const ptt = useRef<Awaited<ReturnType<typeof pushToTalk>> | null>(null);
  const stopFree = useRef<null | (() => void)>(null);

  // capteurs
  const trainer = useRef<Trainer | null>(null);
  const [trainerName, setTrainerName] = useState<string | null>(null);
  const [powerName, setPowerName] = useState<string | null>(null);
  const [live, setLive] = useState<PowerSample | null>(null);
  const liveRef = useRef<PowerSample | null>(null);
  const [target, setTarget] = useState(150);

  // minuterie
  const [now, setNow] = useState(() => performance.now());
  const timer = useRef({ running: false, startedAt: 0, acc: 0, fired: new Set<string>() });

  // import et débrief
  const [sess, setSess] = useState<Any | null>(null);
  const [busyUpload, setBusyUpload] = useState<string | null>(null);
  const [debrief, setDebrief] = useState<Any | null>(null);
  const [debriefText, setDebriefText] = useState("");
  const [debriefBusy, setDebriefBusy] = useState(false);

  const tts: TtsEngine = muted ? "aucune" : cfg?.voix?.tts ?? "navigateur";
  const rate = cfg?.voix?.vitesse ?? 1;
  const ttsRef = useRef(tts);
  ttsRef.current = tts;
  const say = useCallback((text: string) => speak(text, ttsRef.current, rate).catch((e) => toast(`Voix : ${e.message}`, "error")), [rate, toast]);

  useEffect(() => {
    http.get("/ai/settings").then(setCfg).catch(() => {});
    http.get("/guide/plan").then((p: Plan) => { setPlan(p); setTarget(p.puissance_w); }).catch((e) => toast(e.message, "error"));
    const off = onSpeaking(setSpeakingNow);
    return () => { off(); stopSpeaking(); stopFree.current?.(); ptt.current?.cancel(); };
  }, [toast]);

  const step: Step | null = run ? run.plan.etapes[run.idx] : null;

  // Téléphones reliés par QR code : départ et arrêt de l'enregistrement depuis le PC, vidéos reçues toutes seules
  const remote = useRemote(run?.sid);
  const remoteRef = useRef(remote);
  remoteRef.current = remote;
  const keysOf = (st: Step) => (st.cle ?? "").split("+").filter(Boolean);
  const phonesFor = (st: Step): Device[] => remoteRef.current.online.filter((d) => d.secure && keysOf(st).includes(d.role));
  const provider = cfg?.fournisseurs?.find((p: Any) => p.id === cfg.fournisseur);

  // ------------------------------------------------------------------ navigation
  const resetTimer = () => { timer.current = { running: false, startedAt: 0, acc: 0, fired: new Set() }; };

  const announce = useCallback(async (r: Run) => {
    const st = r.plan.etapes[r.idx];
    let text = st.dire + (st.conseil_ia ? ` ${st.conseil_ia}` : "");
    const phones = st.type === "prise" ? phonesFor(st) : [];
    if (phones.length) {
      const before = st.dire.split("Prise :")[0];
      text = `${before}Prise : ${st.titre.toLowerCase()}. ${phones.length > 1 ? "Les téléphones sont prêts" : "Le téléphone est prêt"} : `
        + "rien à toucher. Mets-toi en place, pédale régulièrement, puis dis « c'est parti » : l'enregistrement démarre tout seul et dure une minute.";
    }
    if (st.type === "checklist" && st.items) {
      const k = r.ticks[st.id] ?? 0;
      if (k < st.items.length) text += ` ${k === 0 ? "Premier point" : "Point suivant"} : ${st.items[k].t}. ${st.items[k].d}`;
    }
    await say(text);
  }, [say]);

  const go = useCallback((idx: number) => {
    const r = runRef.current;
    if (!r) return;
    const i = Math.max(0, Math.min(r.plan.etapes.length - 1, idx));
    resetTimer();
    setAnswer("");
    (document.activeElement as HTMLElement | null)?.blur?.(); // la barre d'espace agit sur l'étape, pas sur le dernier bouton cliqué
    const next = { ...r, idx: i };
    setRun(next);
    announce(next);
  }, [announce, setRun]);
  const next = useCallback(() => { const r = runRef.current; if (r) go(r.idx + 1); }, [go]);
  const prev = useCallback(() => { const r = runRef.current; if (r) go(r.idx - 1); }, [go]);

  // ------------------------------------------------------------------ démarrage
  async function adapt() {
    setAdapting(true);
    try {
      const p: Plan = await http.post("/guide/plan/ia");
      setPlan(p);
      setTarget(p.puissance_w);
      if (p.ia?.ok) toast("Séance adaptée par le coach");
      else toast(`Le coach n'a pas pu adapter la séance : ${p.ia?.message ?? "erreur"}`, "error");
    } catch (e) { toast((e as Error).message, "error"); } finally { setAdapting(false); }
  }

  async function start() {
    if (!plan) return;
    try {
      const s = await http.post("/guide/start", { type: plan.type, puissance_w: target });
      const p = { ...plan, puissance_w: target };
      const r: Run = { plan: p, sid: s.id, idx: 0, started: new Date().toISOString(), ticks: {}, done: {}, uploads: {} };
      setSaved(null);
      setRun(r);
      announce(r);
    } catch (e) { toast((e as Error).message, "error"); }
  }

  function resume() {
    if (!saved) return;
    setTarget(saved.plan.puissance_w);
    setRun(saved);
    setSaved(null);
    announce(saved);
  }

  function abandon() {
    if (!confirm("Abandonner la séance guidée ? La séance de capture et les vidéos déjà importées restent dans « Séances ».")) return;
    stopSpeaking();
    stopFree.current?.();
    setListening("off");
    setRun(null);
    setSaved(null);
  }

  // ------------------------------------------------------------------ checklist
  const tick = useCallback(() => {
    const r = runRef.current;
    const st = r?.plan.etapes[r.idx];
    if (!r || !st?.items) return;
    const k = Math.min(st.items.length, (r.ticks[st.id] ?? 0) + 1);
    setRun({ ...r, ticks: { ...r.ticks, [st.id]: k } });
    if (k < st.items.length) say(`${st.items[k].t}. ${st.items[k].d}`);
    else { say("Parfait, c'est tout bon pour cette étape."); setTimeout(() => { if (runRef.current?.idx === r.idx) next(); }, 1800); }
  }, [next, say, setRun]);

  const untick = (i: number) => {
    const r = runRef.current;
    const st = r?.plan.etapes[r.idx];
    if (!r || !st) return;
    setRun({ ...r, ticks: { ...r.ticks, [st.id]: i } });
  };

  // ------------------------------------------------------------------ minuterie (échauffement, prises)
  const elapsed = () => timer.current.acc + (timer.current.running ? (performance.now() - timer.current.startedAt) / 1000 : 0);

  const startTimer = useCallback(() => {
    const r = runRef.current;
    const st = r?.plan.etapes[r.idx];
    if (!st || (st.type !== "timer" && st.type !== "prise") || timer.current.running) return;
    if (r!.done[st.id]) { resetTimer(); setRun({ ...r!, done: { ...r!.done, [st.id]: false } }); }
    timer.current.running = true;
    timer.current.startedAt = performance.now();
    if (st.type === "timer") {
      const easy = Math.round((st.puissance_w ?? target) * 0.65 / 5) * 5;
      trainer.current?.setPower(easy).catch(() => {});
      say(timer.current.acc > 0 ? "On reprend." : `C'est parti pour ${words(st.duree_s ?? 600)}${trainer.current ? `, à ${easy} watts pour commencer` : ""}.`);
    } else {
      trainer.current?.setPower(st.puissance_w ?? target).catch(() => {});
      const phones = phonesFor(st);
      if (phones.length && timer.current.acc === 0) {
        remoteRef.current.command("start", keysOf(st), st.duree_s ?? 60).catch(() => {});
        say(`C'est parti : enregistrement lancé sur ${phones.length > 1 ? "les téléphones" : "le téléphone"}, une minute. Pédale régulièrement.`);
      } else {
        say(timer.current.acc > 0 ? "On reprend." : "C'est parti, une minute. Pédale régulièrement.");
      }
    }
    setNow(performance.now());
  }, [say, setRun, target]);

  const pauseTimer = useCallback(() => {
    if (!timer.current.running) return;
    timer.current.acc = elapsed();
    timer.current.running = false;
    say("Pause. Dis « reprends » quand tu es prêt.");
    setNow(performance.now());
  }, [say]);

  useEffect(() => {
    if (!step || (step.type !== "timer" && step.type !== "prise")) return;
    const id = setInterval(() => {
      if (!timer.current.running) return;
      setNow(performance.now());
      const total = step.duree_s ?? 60;
      const left = total - elapsed();
      const fire = (key: string, cond: boolean, f: () => void) => {
        if (cond && !timer.current.fired.has(key)) { timer.current.fired.add(key); f(); }
      };
      if (step.type === "timer") {
        const ramp = Math.min(180, total * 0.3);
        fire("ramp", left <= ramp, () => {
          trainer.current?.setPower(step.puissance_w ?? target).catch(() => {});
          say(`On monte à ${step.puissance_w ?? target} watts pour finir l'échauffement.`);
        });
        for (const m of [5, 2, 1]) if (total > m * 60 + 30) fire(`m${m}`, left <= m * 60, () => say(`Plus que ${m} minute${m > 1 ? "s" : ""}.`));
      } else {
        fire("30", total > 40 && left <= 30, () => say("Trente secondes. Garde ce rythme."));
        fire("10", left <= 10, () => say("Dix secondes."));
        // cadence : rappel si hors plage pendant plusieurs secondes
        const cad = liveRef.current?.cadence;
        const k = `cad${Math.floor(elapsed() / 15)}`;
        if (cad != null && cad > 30 && (cad < 82 || cad > 98) && elapsed() > 5 && left > 12) {
          fire(k, true, () => say(`Cadence ${cad} : ${cad < 82 ? "accélère un peu" : "ralentis un peu"}.`));
        }
      }
      if (left <= 0) {
        timer.current.running = false;
        timer.current.acc = total;
        const r = runRef.current!;
        setRun({ ...r, done: { ...r.done, [step.id]: true } });
        const remoteTake = step.type === "prise" && phonesFor(step).length > 0;
        if (remoteTake) remoteRef.current.command("stop", keysOf(step)).catch(() => {});
        const msg = step.type === "timer"
          ? "Échauffement terminé. On passe aux prises."
          : remoteTake ? "C'est bon. Les vidéos partent toutes seules vers le PC." : "C'est bon : arrête l'enregistrement sur le téléphone.";
        speak(msg, ttsRef.current, rate).finally(() => setTimeout(() => { if (runRef.current?.idx === r.idx) next(); }, 1200));
      }
    }, 250);
    return () => clearInterval(id);
  }, [step, next, rate, say, setRun, target]);

  // ------------------------------------------------------------------ capteurs
  async function linkTrainer() {
    try {
      const t = await connectTrainer();
      trainer.current = t;
      setTrainerName(`${t.device.name ?? "Home trainer"} (${t.protocol})`);
      await t.setPower(Math.round(target * 0.65));
      say("Home trainer connecté.");
    } catch (e) {
      const m = (e as Error).message;
      if (!/cancel/i.test(m)) toast(`Home trainer : ${m}`, "error");
    }
  }
  async function linkPower() {
    try {
      const dev = await connectPower((s) => { liveRef.current = s; setLive(s); });
      setPowerName(dev?.name ?? "Pédales");
      say("Pédales connectées : je surveille ta cadence pendant les prises.");
    } catch (e) {
      const m = (e as Error).message;
      if (!/cancel/i.test(m)) toast(`Pédales : ${m}`, "error");
    }
  }
  function changeTarget(w: number) {
    const v = Math.max(80, Math.min(400, w));
    setTarget(v);
    setRun((r) => ({ ...r, plan: { ...r.plan, puissance_w: v, etapes: r.plan.etapes.map((s) => (s.puissance_w ? { ...s, puissance_w: v } : s)) } }));
    if (trainer.current && timer.current.running) trainer.current.setPower(v).catch(() => {});
  }

  // ------------------------------------------------------------------ import et analyses
  const loadSess = useCallback(() => {
    const r = runRef.current;
    if (r) http.get(`/sessions/${r.sid}`).then(setSess).catch(() => {});
  }, []);
  const analysing = sess?.captures?.some((c: Any) => ["en_attente", "en_cours"].includes(c.analyses[0]?.status));
  useEffect(() => {
    if (!step || (step.type !== "import" && step.type !== "debrief")) return;
    loadSess();
    if (step.type !== "import") return;
    const id = setInterval(loadSess, 2000);
    return () => clearInterval(id);
  }, [step, loadSess]);

  // Vidéos envoyées par les téléphones : rattachées à la prise correspondante
  useEffect(() => {
    const r = runRef.current;
    if (!r || !remote.pairing) return;
    const add: Record<string, number> = {};
    for (const d of remote.pairing.appareils) {
      if (d.capture_id && r.plan.vues.includes(d.role) && r.uploads[d.role] !== d.capture_id) add[d.role] = d.capture_id;
    }
    if (Object.keys(add).length) { setRun((x) => ({ ...x, uploads: { ...x.uploads, ...add } })); loadSess(); }
  }, [remote.pairing, setRun, loadSess]);

  const capOf = (key: string) => sess?.captures?.find((c: Any) => c.id === run?.uploads[key]);
  const importDone = !!run && Object.keys(run.uploads).length > 0 && !analysing
    && Object.keys(run.uploads).some((k) => capOf(k)?.analyses[0]?.status === "terminee");
  const announcedImport = useRef(false);
  useEffect(() => {
    if (step?.type !== "import") { announcedImport.current = false; return; }
    if (importDone && !announcedImport.current) {
      announcedImport.current = true;
      say("Analyses terminées. On passe au débrief.").finally(() => setTimeout(() => { if (runRef.current?.plan.etapes[runRef.current.idx].type === "import") next(); }, 800));
    }
  }, [importDone, step, next, say]);

  async function upload(key: string, vue: string, f: File) {
    const r = runRef.current;
    if (!r) return;
    setBusyUpload(key);
    const form = new FormData();
    form.append("file", f);
    form.append("vue", vue);
    try {
      const cap = await http.upload(`/sessions/${r.sid}/captures`, form);
      if (cap.meta.fps < 59) toast(`${VIEW_LABEL[key]} : moins de 60 images/s, précision réduite.`, "error");
      await http.post(`/captures/${cap.id}/analyze`, { duree_s: 45 });
      setRun((x) => ({ ...x, uploads: { ...x.uploads, [key]: cap.id } }));
      say(`${VIEW_LABEL[key]} reçue, analyse en cours.`);
      loadSess();
    } catch (e) { toast((e as Error).message, "error"); } finally { setBusyUpload(null); }
  }

  // ------------------------------------------------------------------ débrief
  const runDebrief = useCallback(async () => {
    const r = runRef.current;
    if (!r) return;
    setDebriefText("");
    setDebriefBusy(true);
    let d: Any;
    try { d = await http.get(`/guide/debrief/${r.sid}`); setDebrief(d); } catch (e) { toast((e as Error).message, "error"); setDebriefBusy(false); return; }
    if (!d.modification) {
      setDebriefBusy(false);
      say("Aucune analyse terminée pour cette séance : importe au moins une vidéo pour le débrief.");
      return;
    }
    const q = "Fais-moi le débrief de cette séance guidée : ce qui a été mesuré, la comparaison avec la séance précédente s'il y en a une, "
      + "puis explique la modification retenue (« modification ») et comment la vérifier. N'en propose pas d'autre.";
    let text = "";
    try {
      text = await streamChat({ messages: [{ role: "user", content: q }], vocal: true, seance: JSON.stringify({ etape: "debrief", debrief: d }), onText: setDebriefText });
    } catch (e) {
      const m = d.modification;
      text = `${m.titre}. ${m.raison ?? ""} ${m.texte ?? ""}`.trim();
      setDebriefText(text);
      toast(`Coach IA indisponible (${(e as Error).message}) : débrief de l'application.`, "error");
    } finally { setDebriefBusy(false); }
    if (runRef.current?.plan.etapes[runRef.current.idx].type === "debrief") say(text);
  }, [say, toast]);

  useEffect(() => {
    if (step?.type === "debrief" && !debrief && !debriefBusy) runDebrief();
  }, [step, debrief, debriefBusy, runDebrief]);

  async function applyChange() {
    const r = runRef.current;
    const m = debrief?.modification;
    if (!r || m?.type !== "reglage") return;
    try {
      const c = await http.post(`/guide/apply/${r.sid}`, { champ: m.champ, delta: m.delta });
      setRun({ ...r, applied: c.id });
      toast(`Nouvelle configuration enregistrée : ${m.libelle.toLowerCase()} ${c[m.champ]} mm`);
      say(`C'est noté : ${m.libelle.toLowerCase()} à ${c[m.champ]} millimètres. La prochaine séance sera une vérification.`);
    } catch (e) { toast((e as Error).message, "error"); }
  }

  // ------------------------------------------------------------------ voix : commandes et questions
  const askCoach = useCallback(async (q: string) => {
    const r = runRef.current;
    if (!r) return;
    const st = r.plan.etapes[r.idx];
    setThinking(true);
    setAnswer("");
    const seance = JSON.stringify({
      type: r.plan.type, puissance_w: r.plan.puissance_w, vues: r.plan.vues, changements: r.plan.changements,
      etape_en_cours: { numero: r.idx + 1, sur: r.plan.etapes.length, id: st.id, titre: st.titre, consigne: st.dire, points: st.items, faits: r.ticks[st.id] ?? 0 },
      etapes: r.plan.etapes.map((s) => s.titre),
      modification: debrief?.modification,
    });
    const history = [...qa.current.slice(-6), { role: "user" as const, content: q }];
    try {
      const a = await streamChat({ messages: history, vocal: true, seance, onText: setAnswer });
      qa.current = [...history, { role: "assistant", content: a }];
      say(a);
    } catch (e) {
      setAnswer("");
      toast(`Coach IA : ${(e as Error).message}`, "error");
      say("Je n'arrive pas à joindre le coach. Tu peux continuer avec « suivant » ou « c'est fait ».");
    } finally { setThinking(false); }
  }, [debrief, say, toast]);

  const primary = useCallback(() => {
    const r = runRef.current;
    const st = r?.plan.etapes[r.idx];
    if (!r || !st) return;
    if (st.type === "checklist" && (r.ticks[st.id] ?? 0) < (st.items?.length ?? 0)) return tick();
    if ((st.type === "timer" || st.type === "prise") && !r.done[st.id]) {
      if (!timer.current.running) return startTimer();
      return say(`Encore ${Math.ceil((st.duree_s ?? 60) - elapsed())} secondes.`);
    }
    if (st.type === "import" && !importDone) return say("J'attends les vidéos et la fin des analyses.");
    next();
  }, [importDone, next, say, startTimer, tick]);

  const handleText = useCallback(async (text: string) => {
    setHeard(text);
    const cmd = command(text);
    const r = runRef.current;
    if (!r) return;
    switch (cmd) {
      case "stop": return stopSpeaking();
      case "repeter": return answer ? say(answer) : announce(r);
      case "suivant": return next();
      case "precedent": return prev();
      case "fait": return primary();
      case "partir": return timer.current.running ? undefined : (step?.type === "timer" || step?.type === "prise") ? startTimer() : primary();
      case "pause": return pauseTimer();
      case "reprendre": return startTimer();
      case "effacer": qa.current = []; setAnswer(""); return;
      default: return askCoach(text);
    }
  }, [announce, answer, askCoach, next, pauseTimer, prev, primary, say, startTimer, step]);

  async function handleBlob(b: Blob) {
    try {
      const t = await transcribe(b);
      if (t) await handleText(t);
    } catch (e) { toast(`Micro : ${(e as Error).message}`, "error"); }
  }
  async function toggleFree() {
    if (listening === "libre") { stopFree.current?.(); stopFree.current = null; setListening("off"); setLevel(0); return; }
    if (listening === "ptt") { ptt.current?.cancel(); ptt.current = null; }
    try {
      stopFree.current = await handsFree({ onPhrase: (b) => { if (!isSpeaking()) handleBlob(b); }, onLevel: setLevel, onState: setVadState });
      setListening("libre");
    } catch (e) { toast((e as Error).message, "error"); }
  }
  async function togglePtt() {
    if (listening === "ptt" && ptt.current) {
      const b = await ptt.current.stop();
      ptt.current = null;
      setListening("off");
      handleBlob(b);
      return;
    }
    if (listening === "libre") { stopFree.current?.(); stopFree.current = null; }
    try { stopSpeaking(); ptt.current = await pushToTalk(); setListening("ptt"); } catch (e) { toast((e as Error).message, "error"); }
  }

  // Espace = action principale, flèches = navigation (quand on n'écrit pas)
  useEffect(() => {
    if (!run) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea, select, button")) return;
      if (e.key === " ") { e.preventDefault(); primary(); } else if (e.key === "ArrowRight") next(); else if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run, primary, next, prev]);

  // ================================================================== rendu : avant la séance
  if (!run) {
    return (
      <div className="page">
        <header className="page-head">
          <div>
            <div className="eyebrow">Pas à pas, à la voix</div>
            <h1>Séance guidée</h1>
            <p>Le coach te guide de la pose des pastilles au débrief : il annonce chaque étape, lance l'échauffement et les prises, surveille ta cadence et te propose une seule modification à la fin. Tu avances à la voix, mains sur le guidon.</p>
          </div>
          <div className="row" style={{ gap: 8, alignSelf: "flex-start" }}>
            <TutoButton label="Tuto vidéo" className="btn btn-ghost btn-sm" />
            <Link to="/reglages-ia" className="btn btn-ghost btn-sm"><Settings2 size={14} /> Voix et IA</Link>
          </div>
        </header>

        {saved && (
          <div className="alert info gd-resume">
            <RotateCcw size={17} />
            <span className="grow">Séance guidée en cours : étape {saved.idx + 1} sur {saved.plan.etapes.length} — « {saved.plan.etapes[saved.idx].titre} ».</span>
            <button className="btn btn-primary btn-sm" onClick={resume}>Reprendre</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { saveRun(null); setSaved(null); }}>Oublier</button>
          </div>
        )}

        {eqState && eqState.manquants.length > 0 && (
          <div className="alert danger" style={{ marginBottom: 18 }}>
            <AlertTriangle size={17} />
            <span className="grow">Matériel obligatoire manquant : {eqState.catalogue.filter((c) => eqState.manquants.includes(c.id)).map((c) => c.nom.toLowerCase()).join(", ")}. La mesure ne sera pas possible sans.</span>
            <Link to="/equipement" className="btn btn-ghost btn-sm">Mon équipement</Link>
          </div>
        )}
        {!plan ? <p className="subtle">Préparation du plan…</p> : (
          <div className="gd-prep">
            <section className="card gd-plan">
              <div className="row between" style={{ alignItems: "flex-start" }}>
                <div>
                  <span className={`chip ${plan.type === "verification" ? "bike" : "ok"}`}>{TYPE_LABEL[plan.type]}</span>
                  <h2 className="gd-plan-title">{plan.titre}</h2>
                </div>
                <div className="gd-duration"><Timer size={16} /> ≈ {estimate(plan)} min</div>
              </div>

              {plan.changements.length > 0 && (
                <div className="gd-change">
                  <Wrench size={16} />
                  <span>Depuis la dernière séance : {plan.changements.map((c: Any) => `${c.libelle} ${c.avant} → ${c.apres} ${c.unite}`).join(", ")}.</span>
                </div>
              )}

              <ul className="gd-reasons">{plan.raisons.map((r) => <li key={r}><Check size={14} /> {r}</li>)}</ul>

              <div className="gd-facts">
                <div><span>Prises</span><strong>{plan.vues.map((v) => VIEW_LABEL[v]).join(" · ")}</strong></div>
                <div><span>Échauffement</span><strong>{plan.echauffement_min} min</strong></div>
                {plan.equipement?.trainer === false ? (
                  <div><span>Effort</span><strong>Résistance fixe</strong></div>
                ) : <div>
                  <span>Puissance (ERG)</span>
                  <strong className="gd-power">
                    <button className="icon-btn sm" aria-label="−10 W" onClick={() => setTarget((t) => Math.max(80, t - 10))}>−</button>
                    {target} W
                    <button className="icon-btn sm" aria-label="+10 W" onClick={() => setTarget((t) => Math.min(400, t + 10))}>+</button>
                  </strong>
                </div>}
                <div><span>Cadence</span><strong>{plan.cadence}</strong></div>
              </div>
              {plan.type === "verification" && target !== plan.puissance_w && (
                <p className="alert warn" style={{ marginTop: 12 }}>Pour comparer avant / après, garde la même puissance qu'à la dernière séance ({plan.puissance_w} W).</p>
              )}

              <ol className="gd-outline">
                {plan.etapes.map((s, i) => (
                  <li key={s.id}><span className="gd-num">{i + 1}</span><span className="grow">{s.titre}</span>{s.conseil_ia && <Sparkles size={13} className="gd-ai-dot" aria-label="Conseil du coach" />}</li>
                ))}
              </ol>

              <div className="form-foot">
                <span className="subtle">Crée une séance de capture rattachée à ta configuration actuelle.</span>
                <button className="btn btn-primary" onClick={start}><Play size={16} /> Commencer la séance</button>
              </div>
            </section>

            <div className="stack">
              <section className="card gd-ai">
                <div className="card-head">
                  <span className="icon-tile"><Wand2 size={19} /></span>
                  <div><h2>Adapter avec le coach IA</h2><p>Le coach relit tes données et ajuste la séance : prises, puissance, échauffement, conseils par étape.</p></div>
                </div>
                {provider && (
                  <span className={`chip ${provider.local ? "ok" : "bike"}`} style={{ alignSelf: "flex-start" }}>
                    {provider.local ? <Lock size={12} /> : <Cloud size={12} />} {provider.local ? "Sur ce PC" : "En ligne"} · {provider.nom.replace(/ \(.*\)$/, "")}{provider.modele ? ` · ${provider.modele}` : ""}
                  </span>
                )}
                {plan.ia && (
                  <div className={`alert ${plan.ia.ok ? "ok" : "warn"}`}>
                    {plan.ia.ok ? <Sparkles size={16} /> : <Settings2 size={16} />}
                    <span>{plan.ia.ok ? (plan.ia.pourquoi || "Séance relue par le coach.") : `Plan de l'application conservé : ${plan.ia.message}`}</span>
                  </div>
                )}
                <button className="btn btn-ghost" onClick={adapt} disabled={adapting}>
                  {adapting ? <><Loader2 size={15} className="spin" /> Le coach prépare ta séance…</> : <><Sparkles size={15} /> {plan.ia?.ok ? "Adapter à nouveau" : "Adapter la séance"}</>}
                </button>
                <p className="subtle gd-small">Limites fixées par l'application : au moins un profil, mêmes prises et même puissance pour une vérification. Le plan reste valable sans IA.</p>
              </section>

              <section className="card">
                <div className="card-head">
                  <span className="icon-tile bike"><Mic size={19} /></span>
                  <div><h2>À la voix</h2><p>Active « Mains libres » une fois lancé : le micro du PC t'écoute pendant que tu pédales.</p></div>
                </div>
                <ul className="gd-cmds">
                  <li><q>c'est fait</q> point suivant, ou démarrer</li>
                  <li><q>suivant</q> / <q>précédent</q> changer d'étape</li>
                  <li><q>c'est parti</q> lancer le chrono</li>
                  <li><q>pause</q> / <q>reprends</q></li>
                  <li><q>répète</q> réécouter · <q>stop</q> couper la voix</li>
                  <li>Toute autre phrase : question au coach</li>
                </ul>
                {!micAvailable() && <p className="alert warn">Micro indisponible dans ce navigateur : utilise les boutons (ou la barre d'espace).</p>}
              </section>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ================================================================== rendu : séance en cours
  const st = step!;
  const total = run.plan.etapes.length;
  const ticks = run.ticks[st.id] ?? 0;
  const tEl = Math.min(st.duree_s ?? 60, elapsed());
  const tLeft = Math.max(0, (st.duree_s ?? 60) - tEl);
  const tPct = st.duree_s ? tEl / st.duree_s : 0;
  void now; // la minuterie force le rendu
  const doneStep = (i: number) => {
    const s = run.plan.etapes[i];
    if (s.type === "checklist") return (run.ticks[s.id] ?? 0) >= (s.items?.length ?? 0);
    if (s.type === "timer" || s.type === "prise") return !!run.done[s.id];
    if (s.type === "import") return Object.keys(run.uploads).length > 0;
    return i < run.idx;
  };

  return (
    <div className="page gd-page">
      <header className="page-head gd-head">
        <div>
          <div className="eyebrow">{TYPE_LABEL[run.plan.type]} · séance n° {run.sid}</div>
          <h1>Séance guidée</h1>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={abandon}><Square size={14} /> Abandonner</button>
        </div>
      </header>

      <div className="gd-progress" aria-hidden="true"><span style={{ width: `${((run.idx + (doneStep(run.idx) ? 1 : 0)) / total) * 100}%` }} /></div>

      <div className="gd">
        <nav className="gd-rail" aria-label="Étapes de la séance">
          <ol>
            {run.plan.etapes.map((s, i) => (
              <li key={s.id}>
                <button className={`${i === run.idx ? "current" : ""} ${doneStep(i) && i !== run.idx ? "done" : ""}`} onClick={() => go(i)} aria-current={i === run.idx ? "step" : undefined}>
                  <span className="gd-num">{doneStep(i) && i !== run.idx ? <Check size={12} /> : i + 1}</span>
                  <span className="grow">{s.titre}</span>
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <div className="gd-main">
          <section className={`card gd-step t-${st.type}`} aria-live="polite">
            <div className="gd-step-head">
              <span className="eyebrow">Étape {run.idx + 1} sur {total}</span>
              <h2>{st.titre}</h2>
            </div>
            <p className="gd-say">{st.dire}</p>
            {st.conseil_ia && <p className="gd-tip"><Sparkles size={14} /> {st.conseil_ia}</p>}

            {st.type === "checklist" && st.items && (
              <ol className="gd-items">
                {st.items.map((it, i) => (
                  <li key={it.t} className={i < ticks ? "done" : i === ticks ? "current" : ""}>
                    <button onClick={() => (i < ticks ? untick(i) : i === ticks ? tick() : undefined)} disabled={i > ticks}>
                      <span className="ck-box">{i < ticks && <Check size={14} />}</span>
                      <span><span className="ck-title">{it.t}</span>{i >= ticks && <span className="ck-text">{it.d}</span>}</span>
                    </button>
                  </li>
                ))}
              </ol>
            )}

            {st.id === "camera" && (
              <div className="gd-phones">
                <h3>Relier les téléphones <span className="chip">facultatif</span></h3>
                <p className="subtle">L'enregistrement démarrera depuis le PC (« c'est parti ») et les vidéos arriveront toutes seules : pas de préparation filmée, pas de clap.</p>
                <PhonePairing pairing={remote.pairing} onRole={remote.setRole} compact />
              </div>
            )}
            {(st.type === "prise" || st.type === "import") && remote.online.length > 0 && (
              <ul className="gd-phone-chips" aria-label="Téléphones reliés">
                {remote.online.map((d) => (
                  <li key={d.id} className={d.etat}><span className="pp-dot" /> {d.role_label} · {ETAT_LABEL[d.etat] ?? d.etat}{!d.secure && " (envoi seul)"}</li>
                ))}
              </ul>
            )}
            {st.lien && <Link to={st.lien} target="_blank" className="btn btn-ghost btn-sm gd-link"><ExternalLink size={14} /> Ouvrir « {st.lien === "/cadrage" ? "Cadrage en direct" : "Étalonnage des pastilles"} »</Link>}

            {st.type === "ble" && (
              <div className="gd-ble">
                {!bluetoothAvailable() ? (
                  <p className="alert warn"><Bluetooth size={16} /> Bluetooth indisponible dans ce navigateur (Chrome ou Edge) : règle l'ERG sur ton compteur.</p>
                ) : (
                  <>
                    {(!st.appareils || st.appareils.includes("trainer")) && <div className="tile">
                      <div className="tile-label"><span className={`status-dot${trainerName ? " on" : ""}`} /> <Gauge size={15} /> Home trainer (ERG)</div>
                      <div className="subtle">{trainerName ?? "Non connecté"}</div>
                      <button className="btn btn-primary btn-sm" onClick={linkTrainer}><Bluetooth size={14} /> {trainerName ? "Reconnecter" : "Connecter"}</button>
                    </div>}
                    {(!st.appareils || st.appareils.includes("puissance")) && <div className="tile">
                      <div className="tile-label"><span className={`status-dot${powerName ? " on" : ""}`} /> <Zap size={15} /> Pédales (cadence)</div>
                      <div className="subtle">{powerName ?? "Optionnel"}</div>
                      <button className="btn btn-ghost btn-sm" onClick={linkPower}><Bluetooth size={14} /> {powerName ? "Reconnecter" : "Connecter"}</button>
                    </div>}
                  </>
                )}
                {run.plan.equipement?.trainer !== false && <div className="tile">
                  <div className="tile-label"><Gauge size={15} /> Puissance des prises</div>
                  <div className="row" style={{ gap: 10 }}>
                    <button className="icon-btn" aria-label="−10 W" onClick={() => changeTarget(target - 10)}>−</button>
                    <div className="tile-value" style={{ margin: 0 }}>{target}<small>W</small></div>
                    <button className="icon-btn" aria-label="+10 W" onClick={() => changeTarget(target + 10)}>+</button>
                  </div>
                </div>}
              </div>
            )}

            {(st.type === "timer" || st.type === "prise") && (
              <div className="gd-timer">
                <div className={`gd-ring ${timer.current.running ? "on" : ""} ${run.done[st.id] ? "end" : ""}`} style={{ ["--p" as string]: tPct }}>
                  <div>
                    <strong>{run.done[st.id] ? <CheckCircle2 size={40} /> : mmss(Math.ceil(tLeft))}</strong>
                    <span>{run.done[st.id] ? "Terminé" : timer.current.running ? (st.type === "prise" ? "Enregistrement" : "Échauffement") : timer.current.acc > 0 ? "En pause" : "Prêt"}</span>
                  </div>
                </div>
                <div className="gd-timer-side">
                  {st.type === "prise" && !timer.current.running && !run.done[st.id] && timer.current.acc === 0 && (
                    <ol className="gd-mini">
                      <li>Lance l'enregistrement sur le téléphone</li>
                      <li>Clap face à la caméra</li>
                      <li>Pédale à {run.plan.cadence}, puis « c'est parti »</li>
                    </ol>
                  )}
                  <div className="gd-live">
                    <div><span>Cible</span><strong>{st.puissance_w ? `${st.puissance_w} W` : "Résist. fixe"}</strong></div>
                    <div><span>Puissance</span><strong>{live?.power ?? "—"}{live ? " W" : ""}</strong></div>
                    <div className={live?.cadence != null && (live.cadence < 82 || live.cadence > 98) ? "warn" : ""}><span>Cadence</span><strong>{live?.cadence ?? "—"}</strong></div>
                  </div>
                  <div className="row" style={{ gap: 8 }}>
                    {timer.current.running ? (
                      <button className="btn btn-ghost" onClick={pauseTimer}><Pause size={16} /> Pause</button>
                    ) : run.done[st.id] ? (
                      <button className="btn btn-ghost" onClick={() => { resetTimer(); setRun({ ...run, done: { ...run.done, [st.id]: false } }); }}><RotateCcw size={15} /> Refaire</button>
                    ) : (
                      <button className="btn btn-primary" onClick={startTimer}><Play size={16} /> {timer.current.acc > 0 ? "Reprendre" : st.type === "prise" ? "C'est parti" : "Démarrer"}</button>
                    )}
                    {st.type === "timer" && !run.done[st.id] && <button className="btn btn-ghost" onClick={next}>Passer</button>}
                  </div>
                </div>
              </div>
            )}

            {st.type === "import" && (
              <div className="gd-import">
                {run.plan.vues.map((key) => {
                  const cap = capOf(key);
                  const a = cap?.analyses[0];
                  const side = a?.summary?.cote;
                  const mismatch = key.startsWith("profil_") && side && `profil_${side}` !== key;
                  const vue = key.startsWith("profil") ? "profil" : key;
                  return (
                    <div key={key} className={`gd-up ${a?.status === "terminee" ? "ok" : ""}`}>
                      <div className="row between">
                        <strong>{VIEW_LABEL[key]}</strong>
                        {a && <span className={`chip ${a.status === "terminee" ? "ok" : a.status === "erreur" ? "warn" : ""}`}>{a.status === "terminee" ? "Analysée" : a.status === "erreur" ? "Erreur" : "Analyse…"}</span>}
                      </div>
                      {a && (a.status === "en_cours" || a.status === "en_attente") && (
                        <div><div className="progress"><span style={{ width: `${Math.round(a.progress * 100)}%` }} /></div><small className="subtle">{a.message}</small></div>
                      )}
                      {a?.status === "terminee" && a.summary?.verdict_selle && <small className="subtle">Extension du genou {a.summary.verdict_selle.flexion_moyenne}°</small>}
                      {a?.status === "erreur" && <small className="alert danger">{a.error}</small>}
                      {mismatch && <small className="alert warn">Côté détecté : {side === "G" ? "gauche" : "droit"}.</small>}
                      <label className={`btn btn-sm ${cap ? "btn-ghost" : "btn-primary"}`}>
                        {busyUpload === key ? <Loader2 size={14} className="spin" /> : <FileUp size={14} />} {cap ? "Remplacer" : "Choisir la vidéo"}
                        <input type="file" accept="video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(key, vue, f); e.target.value = ""; }} />
                      </label>
                    </div>
                  );
                })}
                <p className="subtle gd-small">Tu peux aussi importer plus tard : la séance guidée reprendra ici (bouton « Reprendre »).</p>
              </div>
            )}

            {st.type === "debrief" && (
              <div className="gd-debrief">
                {!debrief ? <p className="subtle"><Loader2 size={14} className="spin" /> Préparation du débrief…</p> : (
                  <>
                    {debrief.en_cours.length > 0 && <p className="alert warn">Analyse encore en cours : {debrief.en_cours.join(", ")}.</p>}
                    <div className="gd-results">
                      {Object.entries(debrief.resultats).map(([k, r]: [string, Any]) => (
                        <div key={k} className="tile">
                          <div className="tile-label">{VIEW_LABEL[k] ?? k}</div>
                          {r.verdict_selle ? (
                            <>
                              <div className="tile-value">{r.verdict_selle.flexion_moyenne}<small>°</small></div>
                              <div className="subtle">Extension du genou · plage {r.verdict_selle.plage_min}–{r.verdict_selle.plage_max}°</div>
                              <span className={`chip ${r.verdict_selle.statut === "dans_la_plage" ? "ok" : "warn"}`}>{r.verdict_selle.statut === "dans_la_plage" ? "Dans la plage" : r.verdict_selle.statut === "trop_tendu" ? "Trop tendu" : r.verdict_selle.statut === "trop_plie" ? "Trop plié" : "Indéterminé"}</span>
                            </>
                          ) : <div className="subtle">Analysée</div>}
                          <Link className="link gd-small" to={`/analyse/${r.analysis_id}`}>Voir l'analyse <ChevronRight size={12} /></Link>
                        </div>
                      ))}
                    </div>

                    {debrief.comparaison.length > 0 && (
                      <div className="table-scroll">
                        <table className="mtable gd-compare">
                          <thead><tr><th>Prise</th><th>Mesure</th><th>Avant</th><th>Après</th><th>Écart</th></tr></thead>
                          <tbody>
                            {debrief.comparaison.map((c: Any, i: number) => (
                              <tr key={i}><td>{VIEW_LABEL[c.prise]}</td><td>{c.nom}</td><td>{c.avant}{c.unite === "deg" || c.unite === "°" ? "°" : ""}</td><td>{c.apres}{c.unite === "deg" || c.unite === "°" ? "°" : ""}</td>
                                <td className={Math.abs(c.delta) >= 2 ? "strong" : "subtle"}>{c.delta > 0 ? "+" : ""}{c.delta}</td></tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    <div className="gd-coach">
                      <span className="coach-avatar"><Sparkles size={14} /></span>
                      <div className="grow">
                        {debriefBusy && !debriefText ? <span className="typing"><i /><i /><i /></span> : <p>{debriefText}</p>}
                        <div className="row" style={{ gap: 6, marginTop: 6 }}>
                          {!debriefBusy && debriefText && <button className="bubble-btn" onClick={() => say(debriefText)}><Volume2 size={13} /> Réécouter</button>}
                          {!debriefBusy && <button className="bubble-btn" onClick={runDebrief}><RotateCcw size={13} /> Refaire le débrief</button>}
                        </div>
                      </div>
                    </div>

                    {debrief.modification && <ChangeCard m={debrief.modification} applied={!!run.applied} onApply={applyChange} />}
                    {debrief.a_garder_en_tete?.length > 0 && (
                      <ul className="gd-keep">
                        {debrief.a_garder_en_tete.map((k: Any) => <li key={k.titre}><strong>À garder en tête : {k.titre}.</strong> {k.texte}</li>)}
                      </ul>
                    )}
                  </>
                )}
              </div>
            )}

            {st.type === "fin" && (
              <div className="gd-end">
                <CheckCircle2 size={34} />
                <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                  <Link to="/sante" className="btn btn-ghost btn-sm">Noter mes ressentis</Link>
                  <Link to="/rapport" className="btn btn-ghost btn-sm">Rapport</Link>
                  <button className="btn btn-primary btn-sm" onClick={() => { const sid = run.sid; stopSpeaking(); stopFree.current?.(); setRun(null); nav(`/seance/${sid}`); }}>Terminer la séance</button>
                </div>
              </div>
            )}

            <div className="gd-nav">
              <button className="btn btn-ghost" onClick={prev} disabled={run.idx === 0}><ArrowLeft size={16} /> Précédent</button>
              <button className="btn btn-ghost" onClick={() => announce(run)}><Volume2 size={15} /> Répéter</button>
              {st.type !== "fin" && <button className="btn btn-primary" onClick={next}>Suivant <ArrowRight size={16} /></button>}
            </div>
          </section>

          <section className={`gd-voice ${listening === "libre" ? vadState : ""}`} aria-label="Voix">
            <div className="gd-voice-row">
              {micAvailable() && run.plan.equipement?.micro !== false && (
                <>
                  <button className={`tool ${listening === "libre" ? "on" : ""}`} aria-pressed={listening === "libre"} onClick={toggleFree}><Ear size={15} /> Mains libres</button>
                  <button className={`tool ${listening === "ptt" ? "rec" : ""}`} onClick={togglePtt}>{listening === "ptt" ? <Square size={15} /> : <Mic size={15} />} {listening === "ptt" ? "Envoyer" : "Parler"}</button>
                </>
              )}
              <button className={`tool ${muted ? "" : "on"}`} aria-pressed={!muted} onClick={() => { if (!muted) stopSpeaking(); setMuted(!muted); }}>{muted ? <VolumeX size={15} /> : <Volume2 size={15} />} Voix du coach</button>
              <span className="grow gd-voice-state">
                {run.plan.equipement?.micro === false ? (speakingNow ? "Le coach parle" : "Sans micro : barre d'espace = action suivante, flèches = étapes") : thinking ? "Le coach réfléchit…" : speakingNow ? "Le coach parle — « stop » pour couper" : listening === "libre" ? (vadState === "parole" ? "Je t'écoute…" : "Parle quand tu veux") : "Micro coupé"}
              </span>
              {listening === "libre" && <span className="vad-meter"><span style={{ width: `${Math.round(level * 100)}%` }} /></span>}
            </div>
            {heard && <p className="gd-heard"><Mic size={12} /> « {heard} »</p>}
            {(answer || thinking) && (
              <div className="gd-answer">
                <span className="coach-avatar"><Sparkles size={14} /></span>
                <p>{answer || <span className="typing"><i /><i /><i /></span>}</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function ChangeCard({ m, applied, onApply }: { m: Any; applied: boolean; onApply: () => void }) {
  if (m.type === "consulter") {
    return (
      <div className="gd-mod danger">
        <Stethoscope size={20} />
        <div><strong>{m.titre}</strong><p>{m.texte}</p><small>{m.raison}</small></div>
      </div>
    );
  }
  if (m.type === "reglage") {
    return (
      <div className="gd-mod">
        <Wrench size={20} />
        <div className="grow">
          <span className="eyebrow">La modification à faire</span>
          <strong className="gd-mod-title">{m.titre}</strong>
          {m.avant != null && <div className="gd-mod-values"><span>{m.avant} mm</span><ArrowRight size={14} /><span className="strong">{m.apres} mm</span></div>}
          <p>{m.raison}</p>
          <p className="subtle"><strong>Comment :</strong> {m.comment}</p>
          <p className="subtle"><strong>Ensuite :</strong> {m.verification}</p>
          {applied ? <span className="chip ok"><Check size={13} /> Nouvelle configuration enregistrée</span> : (
            <button className="btn btn-primary btn-sm" onClick={onApply} disabled={m.avant == null}>
              <Check size={14} /> J'ai fait le réglage : enregistrer la configuration
            </button>
          )}
          {m.avant == null && <small className="subtle"> Hauteur actuelle inconnue : renseigne-la dans « Mon vélo ».</small>}
        </div>
      </div>
    );
  }
  return (
    <div className={`gd-mod ${m.type === "aucun" ? "ok" : ""}`}>
      {m.type === "aucun" ? <CheckCircle2 size={20} /> : <Sparkles size={20} />}
      <div><span className="eyebrow">{m.type === "aucun" ? "Pas de modification" : "Prochaine piste"}</span><strong className="gd-mod-title">{m.titre}</strong>{m.texte && <p>{m.texte}</p>}<small className="subtle">{m.raison}</small></div>
    </div>
  );
}
