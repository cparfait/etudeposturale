import { useEffect, useState } from "react";
import { Check, Cloud, Download, ExternalLink, Image as ImageIcon, KeyRound, Loader2, Lock, Mic, RefreshCw, Square, Trash2, Volume2, Zap } from "lucide-react";
import { http, type Any } from "../api";
import { useToast } from "../toast";
import { pushToTalk, speak, stopSpeaking, transcribe, type TtsEngine } from "../voice";

const OPENAI_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"];

export function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} className="switch" onClick={() => onChange(!on)}>
      <span />
    </button>
  );
}

function ProviderPanel({ p, onSaved }: { p: Any; onSaved: (s: Any) => void }) {
  const toast = useToast();
  const [url, setUrl] = useState(p.url);
  const [key, setKey] = useState("");
  const [model, setModel] = useState(p.modele || "");
  const [models, setModels] = useState<string[]>(p.modeles_repli);
  const [listInfo, setListInfo] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [test, setTest] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const r = await http.get(`/ai/models/${p.id}`);
      setModels(r.modeles);
      setListInfo(r.source === "service" ? `${r.modeles.length} modèles trouvés` : `Liste du service illisible — ${r.erreur}`);
      if (!model && r.modeles.length) setModel(r.modeles[0]);
    } finally { setLoading(false); }
  }
  useEffect(() => { if (p.local || p.cle_enregistree || p.cle !== "requise") refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [p.id]);

  async function save() {
    const patch: Any = { fournisseur: p.id, modeles: { [p.id]: model } };
    if (p.url_modifiable) patch.urls = { [p.id]: url };
    let s = await http.put("/ai/settings", patch);
    if (key.trim()) { s = await http.put(`/ai/keys/${p.id}`, { cle: key.trim() }); setKey(""); }
    onSaved(s);
    toast(`${p.nom} enregistré${model ? ` · ${model}` : ""}`);
    return s;
  }
  async function runTest() {
    setTesting(true); setTest(null);
    try { await save(); setTest(await http.post(`/ai/test/${p.id}`)); }
    catch (e) { setTest({ ok: false, message: (e as Error).message }); }
    finally { setTesting(false); }
  }
  async function dropKey() {
    onSaved(await http.put(`/ai/keys/${p.id}`, { cle: null }));
    toast("Clé supprimée");
  }

  return (
    <div className="ai-panel">
      {p.note && <p className="subtle" style={{ margin: 0, fontSize: "0.86rem" }}>{p.note}</p>}
      {p.url_modifiable && (
        <label className="field">
          <span className="field-label">Adresse du service</span>
          <input className="input" value={url} placeholder="http://localhost:11434/v1" onChange={(e) => setUrl(e.target.value)} />
        </label>
      )}
      {p.cle !== "aucune" && (
        <label className="field">
          <span className="field-label"><KeyRound size={14} /> Clé d'API {p.cle === "facultative" && <span className="chip">facultative</span>}
            {p.cle_enregistree && <span className="chip ok"><Check size={12} /> enregistrée, chiffrée par Windows</span>}</span>
          <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
            <input className="input" type="password" autoComplete="off" value={key} style={{ flex: 1 }}
              placeholder={p.cle_enregistree ? "•••••••• (laisser vide pour garder la clé)" : "Coller la clé ici"} onChange={(e) => setKey(e.target.value)} />
            {p.cle_enregistree && <button className="icon-btn" title="Supprimer la clé" aria-label="Supprimer la clé" onClick={dropKey}><Trash2 size={16} /></button>}
          </div>
          {p.url_cle && <a className="link" href={p.url_cle} target="_blank" rel="noreferrer" style={{ fontSize: "0.82rem" }}>Obtenir une clé <ExternalLink size={12} /></a>}
        </label>
      )}
      <label className="field">
        <span className="field-label">Modèle</span>
        <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
          <input className="input" list={`models-${p.id}`} value={model} style={{ flex: 1 }} placeholder="Choisir ou saisir l'identifiant du modèle" onChange={(e) => setModel(e.target.value)} />
          <datalist id={`models-${p.id}`}>{models.map((m) => <option key={m} value={m} />)}</datalist>
          <button className="icon-btn" title="Actualiser la liste" aria-label="Actualiser la liste des modèles" onClick={refresh} disabled={loading}>
            {loading ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
          </button>
        </div>
        <span className="field-help">{listInfo || (p.doc ? <>Liste officielle : <a className="link" href={p.doc} target="_blank" rel="noreferrer">{new URL(p.doc).hostname}</a></> : "")}</span>
      </label>
      <div className="row" style={{ gap: 8 }}>
        <button className="btn btn-primary btn-sm" onClick={save}>Utiliser ce fournisseur</button>
        <button className="btn btn-ghost btn-sm" onClick={runTest} disabled={testing}>{testing ? <Loader2 size={14} className="spin" /> : <Zap size={14} />} Tester</button>
      </div>
      {test && <div className={`alert ${test.ok ? "ok" : "danger"}`}>{test.ok ? <Check size={16} /> : <Zap size={16} />}<span>{test.message}</span></div>}
    </div>
  );
}

export default function AISettings() {
  const toast = useToast();
  const [s, setS] = useState<Any | null>(null);
  const [open, setOpen] = useState<string>("");
  const [vs, setVs] = useState<Any | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [rec, setRec] = useState<{ stop: () => Promise<Blob> } | null>(null);
  const [heard, setHeard] = useState<string>("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    http.get("/ai/settings").then((r) => { setS(r); setOpen(r.fournisseur); });
    http.get("/voice/status").then(setVs);
  }, []);
  if (!s) return <div className="page"><p className="subtle">Chargement…</p></div>;

  const v = s.voix;
  const setVoice = async (patch: Any) => setS(await http.put("/ai/settings", { voix: patch }));
  const active = s.fournisseurs.find((p: Any) => p.id === s.fournisseur);
  const groups = [
    { titre: "Sur ce PC — rien ne sort", items: s.fournisseurs.filter((p: Any) => p.local && p.id !== "custom") },
    { titre: "En ligne — avec ta clé", items: s.fournisseurs.filter((p: Any) => !p.local || p.id === "custom") },
  ];

  async function prepare() {
    setPreparing(true);
    try { await http.post("/voice/stt/prepare"); setVs(await http.get("/voice/status")); toast("Reconnaissance vocale prête"); }
    catch (e) { toast((e as Error).message, "error"); }
    finally { setPreparing(false); }
  }
  async function micTest() {
    if (rec) {
      setBusy(true);
      const blob = await rec.stop();
      setRec(null);
      try { setHeard((await transcribe(blob)) || "(rien entendu)"); }
      catch (e) { toast((e as Error).message, "error"); }
      finally { setBusy(false); setVs(await http.get("/voice/status")); }
      return;
    }
    try { setHeard(""); setRec(await pushToTalk()); }
    catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Coach IA</div>
          <h1>Réglages IA et voix</h1>
          <p>Choisis qui fait tourner le coach : un modèle sur ton PC (rien ne sort) ou un service en ligne avec ta clé.
            Les mesures restent calculées par l'application ; l'IA les explique et te guide.</p>
        </div>
        {active && (
          <span className={`chip ${active.local ? "ok" : "bike"}`} style={{ alignSelf: "flex-start" }}>
            {active.local ? <Lock size={12} /> : <Cloud size={12} />} {active.nom}{active.modele ? ` · ${active.modele}` : ""}
          </span>
        )}
      </header>

      <section className="stack">
        <h2 className="section-title">Fournisseur d'IA</h2>
        {groups.map((g) => (
          <div key={g.titre} className="stack" style={{ gap: 10 }}>
            <div className="eyebrow" style={{ margin: 0 }}>{g.titre}</div>
            <div className="ai-grid">
              {g.items.map((p: Any) => (
                <div key={p.id} className={`ai-card${open === p.id ? " open" : ""}${s.fournisseur === p.id ? " active" : ""}`}>
                  <button className="ai-card-head" aria-expanded={open === p.id} onClick={() => setOpen(open === p.id ? "" : p.id)}>
                    <span className={`ai-ico ${p.local ? "local" : "cloud"}`}>{p.local ? <Lock size={16} /> : <Cloud size={16} />}</span>
                    <span className="ai-card-name">
                      <strong>{p.nom}</strong>
                      <small>{s.fournisseur === p.id ? `Utilisé${p.modele ? ` · ${p.modele}` : ""}` : p.cle_enregistree ? "Clé enregistrée" : p.cle === "aucune" ? "Sans clé" : p.cle === "facultative" ? "Clé facultative" : "Clé requise"}</small>
                    </span>
                    {s.fournisseur === p.id && <span className="chip brand"><Check size={12} /> actif</span>}
                  </button>
                  {open === p.id && <ProviderPanel p={p} onSaved={(r) => setS(r)} />}
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="card ai-option">
          <span className="icon-tile"><ImageIcon size={18} /></span>
          <div style={{ flex: 1 }}>
            <strong>Autoriser l'envoi d'images de l'analyse</strong>
            <p className="subtle" style={{ margin: "4px 0 0", fontSize: "0.86rem" }}>
              Quand tu coches « Joindre les images » dans le coach, il reçoit 2 images par côté filmé (extension et flexion maximales),
              avec le squelette dessiné, réduites à 1024 px. Jamais la vidéo. Le modèle doit savoir lire les images
              (Claude, GPT, Gemini, ou un modèle local « vision » comme qwen2.5vl ou gemma3).
              {!active?.local && " Avec un fournisseur en ligne, ces images quittent ton PC."}
            </p>
          </div>
          <Switch label="Autoriser l'envoi d'images" on={s.images} onChange={async (x) => setS(await http.put("/ai/settings", { images: x }))} />
        </div>
      </section>

      <section className="stack" style={{ marginTop: 28 }}>
        <h2 className="section-title">Voix du coach</h2>
        <div className="grid-2">
          <div className="card stack" style={{ gap: 14 }}>
            <div className="card-head" style={{ marginBottom: 0 }}><span className="icon-tile"><Volume2 size={18} /></span><div><h3 style={{ margin: 0 }}>Le coach te parle</h3><p>Synthèse vocale</p></div></div>
            <div className="segmented">
              {([["piper", "Piper (PC)"], ["fish", "Fish Audio"], ["google", "Google"], ["azure", "Azure"], ["cartesia", "Cartesia"], ["openai", "OpenAI"], ["navigateur", "Navigateur"], ["aucune", "Muet"]] as [TtsEngine, string][]).map(([id, label]) => (
                <button key={id} aria-pressed={v.tts === id} onClick={() => setVoice({ tts: id })}>{label}</button>
              ))}
            </div>
            {v.tts === "piper" && vs && (
              vs.piper.executables.length === 0 ? (
                <div className="alert warn">Piper introuvable sur ce PC. Copie piper.exe et une voix française (.onnx + .onnx.json) dans <code>data/voice/</code>.</div>
              ) : (
                vs.piper.voix.length === 0 ? (
                  <div className="alert warn" style={{ flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
                    <span>Piper est installé mais aucune voix n'a été trouvée. Copie une voix française (fichiers <code>.onnx</code> et <code>.onnx.json</code>) dans <code>data/voice/</code>, puis cherche à nouveau.</span>
                    {vs.piper.dossiers?.length > 0 && <small>Dossiers parcourus : {vs.piper.dossiers.join(" · ")}</small>}
                    <button className="btn btn-ghost btn-sm" onClick={async () => setVs(await http.get("/voice/status"))}>Chercher à nouveau</button>
                  </div>
                ) : (
                <>
                  <label className="field"><span className="field-label">Voix</span>
                    <select className="select" value={v.piper_voix || vs.piper.voix[0]?.chemin || ""} onChange={(e) => setVoice({ piper_voix: e.target.value, piper_exe: v.piper_exe || vs.piper.executables[0] })}>
                      {vs.piper.voix.map((x: Any) => <option key={x.chemin} value={x.chemin}>{x.nom}{x.langue ? ` (${x.langue})` : ""}</option>)}
                    </select>
                    <span className="field-help">Trouvée avec ton installation de LMU Stats Viewer · 100 % local</span>
                  </label>
                </>
                )
              )
            )}
            {(["fish", "cartesia", "google", "azure"] as const).includes(v.tts) && (() => {
              const svc = CLOUD[v.tts as CloudId];
              return <CloudVoicePanel key={v.tts} svc={svc} hasKey={!!s.cles?.[svc.cle]} voice={v[svc.champ]} region={v.azure_region}
                onVoice={(id) => setVoice({ [svc.champ]: id })} onRegion={(r) => setVoice({ azure_region: r })}
                onKey={async (cle) => { await http.put(`/voice/keys/${v.tts}`, { cle }); setS(await http.get("/ai/settings")); }} />;
            })()}
            {v.tts === "openai" && (
              <label className="field"><span className="field-label">Voix OpenAI</span>
                <select className="select" value={v.openai_voix} onChange={(e) => setVoice({ openai_voix: e.target.value })}>
                  {OPENAI_VOICES.map((x) => <option key={x} value={x}>{x}</option>)}
                </select>
                <span className="field-help">Utilise la clé du fournisseur OpenAI ci-dessus. Le texte lu part chez OpenAI.</span>
              </label>
            )}
            {v.tts === "navigateur" && <p className="subtle" style={{ margin: 0, fontSize: "0.86rem" }}>Voix intégrée à Windows / Chrome : immédiate, plus robotique.</p>}
            {v.tts !== "aucune" && (
              <>
                <label className="mk-slider">
                  <span className="mk-slider-head"><span>Vitesse</span><b>× {Number(v.vitesse).toFixed(2)}</b></span>
                  <input type="range" min={0.7} max={1.4} step={0.05} value={v.vitesse} onChange={(e) => setS({ ...s, voix: { ...v, vitesse: +e.target.value } })}
                    onPointerUp={(e) => setVoice({ vitesse: +(e.target as HTMLInputElement).value })} onKeyUp={(e) => setVoice({ vitesse: +(e.target as HTMLInputElement).value })} />
                </label>
                <div className="row between">
                  <label className="row" style={{ gap: 10 }}><Switch label="Lire les réponses automatiquement" on={v.lecture_auto} onChange={(x) => setVoice({ lecture_auto: x })} /> <span style={{ fontSize: "0.88rem" }}>Lire les réponses automatiquement</span></label>
                  <button className="btn btn-ghost btn-sm" onClick={() => speak("Bonjour ! Je suis ton coach. On commence par vérifier la hauteur de selle ?", v.tts, v.vitesse).catch((e) => { stopSpeaking(); toast(e.message, "error"); })}>
                    <Volume2 size={14} /> Écouter
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="card stack" style={{ gap: 14 }}>
            <div className="card-head" style={{ marginBottom: 0 }}><span className="icon-tile"><Mic size={18} /></span><div><h3 style={{ margin: 0 }}>Tu parles au coach</h3><p>Reconnaissance vocale</p></div></div>
            <div className="segmented">
              <button aria-pressed={v.stt === "whisper"} onClick={() => setVoice({ stt: "whisper" })}>Whisper (PC)</button>
              <button aria-pressed={v.stt === "openai"} onClick={() => setVoice({ stt: "openai" })}>OpenAI</button>
            </div>
            {v.stt === "whisper" && vs && (
              <>
                <label className="field"><span className="field-label">Modèle</span>
                  <select className="select" value={v.whisper_modele} onChange={async (e) => { await setVoice({ whisper_modele: e.target.value }); setVs(await http.get("/voice/status")); }}>
                    {vs.modeles_whisper.map((m: string) => <option key={m} value={m}>{m}{m === "large-v3-turbo" ? " — recommandé sur la RTX 4090" : ""}</option>)}
                  </select>
                </label>
                <div className="row between">
                  <span className={`chip ${vs.whisper.telecharge ? "ok" : "warn"}`}>
                    {vs.whisper.charge ? `Chargé · ${vs.whisper.charge.appareil}` : vs.whisper.telecharge ? "Téléchargé" : "À télécharger (≈ 1,6 Go pour large-v3-turbo)"}
                  </span>
                  {!vs.whisper.charge && (
                    <button className="btn btn-ghost btn-sm" onClick={prepare} disabled={preparing}>
                      {preparing ? <Loader2 size={14} className="spin" /> : <Download size={14} />} {vs.whisper.telecharge ? "Charger" : "Télécharger"}
                    </button>
                  )}
                </div>
              </>
            )}
            {v.stt === "openai" && <p className="subtle" style={{ margin: 0, fontSize: "0.86rem" }}>Utilise la clé OpenAI. L'enregistrement de ta voix part chez OpenAI.</p>}
            <div className="mic-test">
              <button className={`btn ${rec ? "btn-primary" : "btn-ghost"} btn-sm`} onClick={micTest} disabled={busy}>
                {busy ? <Loader2 size={14} className="spin" /> : rec ? <Square size={14} /> : <Mic size={14} />} {rec ? "Arrêter et transcrire" : "Tester le micro"}
              </button>
              {rec && <span className="rec-dot" aria-label="Enregistrement en cours" />}
              {heard && <q>{heard}</q>}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

type CloudId = "fish" | "cartesia" | "google" | "azure";
interface CloudSvc { id: CloudId; nom: string; cle: string; champ: string; placeholder: string; lien: string; aide: string; defaut: string; libre?: boolean }
const CLOUD: Record<CloudId, CloudSvc> = {
  fish: {
    id: "fish", nom: "Fish Audio", cle: "fish_audio", champ: "fish_voix", placeholder: "Clé API Fish Audio", defaut: "Voix par défaut", libre: true,
    lien: "https://fish.audio/app/api-keys/",
    aide: "Modèle gratuit « s2.1-pro-free », sans carte bancaire (usage personnel). Sur fish.audio : créer un compte, puis API Keys → nouvelle clé. Tu peux aussi coller l'identifiant de n'importe quelle voix du site (dans son adresse fish.audio/m/…).",
  },
  google: {
    id: "google", nom: "Google Cloud", cle: "google_tts", champ: "google_voix", placeholder: "AIza…", defaut: "Meilleure voix Chirp 3 HD",
    lien: "https://console.cloud.google.com/apis/library/texttospeech.googleapis.com",
    aide: "Gratuit jusqu'à ≈ 1 million de caractères par mois en voix naturelles. Dans la console Google Cloud : activer « Cloud Text-to-Speech API », puis Identifiants → Créer une clé API (la restreindre à cette API). Carte bancaire demandée : mets une alerte de budget.",
  },
  azure: {
    id: "azure", nom: "Azure Speech", cle: "azure_speech", champ: "azure_voix", placeholder: "Clé 1 de la ressource Speech", defaut: "fr-FR-DeniseNeural",
    lien: "https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices",
    aide: "Gratuit jusqu'à 500 000 caractères par mois (offre F0). Dans le portail Azure : créer une ressource « Speech », niveau tarifaire Gratuit F0, puis « Clés et point de terminaison » : copier la clé 1 et la région.",
  },
  cartesia: {
    id: "cartesia", nom: "Cartesia", cle: "cartesia", champ: "cartesia_voix", placeholder: "sk_car_…", defaut: "Henri (par défaut)",
    lien: "https://play.cartesia.ai/keys", aide: "Voix très naturelles et rapides ; petite offre gratuite, puis payant.",
  },
};
const AZURE_REGIONS = ["francecentral", "westeurope", "northeurope", "switzerlandnorth", "germanywestcentral", "uksouth", "eastus", "westus2"];

/** Service de voix en ligne : clé (chiffrée, jamais réaffichée), région (Azure) et choix d'une voix française. */
function CloudVoicePanel({ svc, hasKey, voice, region, onVoice, onRegion, onKey }: {
  svc: CloudSvc; hasKey: boolean; voice: string; region: string;
  onVoice: (id: string) => void; onRegion: (r: string) => void; onKey: (cle: string | null) => Promise<void>;
}) {
  const [key, setKey] = useState("");
  const [voices, setVoices] = useState<{ id: string; nom: string; description: string }[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const refresh = () => {
    setLoading(true);
    http.get(`/voice/${svc.id}/voices`).then((r) => { setVoices(r.voix); setErr(""); }).catch((e) => { setVoices([]); setErr(e.message); }).finally(() => setLoading(false));
  };
  useEffect(() => { if (hasKey) refresh(); }, [hasKey, region]); // eslint-disable-line react-hooks/exhaustive-deps
  const current = voices.find((x) => x.id === voice);
  return (
    <div className="stack" style={{ gap: 12 }}>
      <p className="subtle" style={{ margin: 0, fontSize: "0.84rem" }}>{svc.aide}</p>
      <label className="field"><span className="field-label">Clé {svc.nom} {hasKey && <span className="chip ok" style={{ marginLeft: 6 }}>enregistrée</span>}</span>
        <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
          <input className="input" type="password" autoComplete="off" placeholder={hasKey ? "•••••••• (remplacer)" : svc.placeholder} value={key} onChange={(e) => setKey(e.target.value)} style={{ flex: 1, minWidth: 0 }} />
          <button className="btn btn-primary btn-sm" disabled={!key.trim()} onClick={async () => { await onKey(key.trim()); setKey(""); }}>Enregistrer</button>
          {hasKey && <button className="btn btn-ghost btn-sm" onClick={() => onKey(null)}>Supprimer</button>}
        </div>
        <span className="field-help">Chiffrée par Windows sur ce PC, jamais réaffichée. <a className="link" href={svc.lien} target="_blank" rel="noreferrer">Obtenir une clé</a></span>
      </label>
      {svc.id === "azure" && (
        <label className="field"><span className="field-label">Région de la ressource</span>
          <select className="select" value={region} onChange={(e) => onRegion(e.target.value)}>
            {!AZURE_REGIONS.includes(region) && <option value={region}>{region}</option>}
            {AZURE_REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
      )}
      {hasKey && svc.libre && (
        <label className="field"><span className="field-label">Identifiant de voix (facultatif)</span>
          <input className="input" value={voice} placeholder="ex. collé depuis fish.audio/m/…" onChange={(e) => onVoice(e.target.value.trim().replace(/^.*\/m\//, "").replace(/[/?#].*$/, ""))} />
        </label>
      )}
      {hasKey && (
        <label className="field"><span className="field-label">Voix {loading && <Loader2 size={12} className="spin" />}</span>
          <select className="select" value={voice} onChange={(e) => onVoice(e.target.value)}>
            {!current && <option value={voice}>{voice || svc.defaut}</option>}
            {voices.map((x) => <option key={x.id} value={x.id}>{x.nom}{x.description ? ` — ${x.description}` : ""}</option>)}
          </select>
          <span className="field-help">{err ? <span style={{ color: "var(--danger)" }}>{err}</span> : `${voices.length ? `${voices.length} voix françaises.` : "Voix française."} En ligne : le texte lu part chez ${svc.nom}.`}</span>
        </label>
      )}
    </div>
  );
}
