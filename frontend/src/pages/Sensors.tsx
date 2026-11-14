import { useRef, useState } from "react";
import { Bluetooth, Gauge, HeartPulse, Minus, Plus, Zap } from "lucide-react";
import { bluetoothAvailable, connectHeartRate, connectPower, connectTrainer, type Trainer } from "../ble";
import { useToast } from "../toast";

export default function Sensors() {
  const toast = useToast();
  const [hr, setHr] = useState<number | null>(null);
  const [power, setPower] = useState<{ power: number; balanceLeft: number | null; cadence: number | null } | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [target, setTarget] = useState(150);
  const trainer = useRef<Trainer | null>(null);
  const [trainerOn, setTrainerOn] = useState<string | null>(null);

  async function run(kind: string, fn: () => Promise<{ name?: string } | undefined>) {
    try {
      const dev = await fn();
      setNames((n) => ({ ...n, [kind]: dev?.name ?? "connecté" }));
    } catch (e) {
      const msg = (e as Error).message;
      if (!/cancel/i.test(msg)) toast(`Connexion impossible : ${msg}`, "error");
    }
  }

  async function connectErg() {
    try {
      const t = await connectTrainer();
      trainer.current = t;
      setTrainerOn(`${t.device.name ?? "Home trainer"} (${t.protocol})`);
      await t.setPower(target);
      toast(`Mode ERG : ${target} W`);
    } catch (e) {
      const msg = (e as Error).message;
      if (!/cancel/i.test(msg)) toast(`Home trainer : ${msg}`, "error");
    }
  }

  async function changeTarget(w: number) {
    const v = Math.max(50, Math.min(600, w));
    setTarget(v);
    if (trainer.current) {
      try { await trainer.current.setPower(v); } catch (e) { toast((e as Error).message, "error"); }
    }
  }

  if (!bluetoothAvailable()) {
    return (
      <div className="page">
        <header className="page-head"><div><div className="eyebrow">Capteurs</div><h1>Capteurs Bluetooth</h1></div></header>
        <div className="alert warn"><Bluetooth size={18} /> Ce navigateur ne gère pas le Web Bluetooth. Utilise Chrome ou Edge sur PC ou Android (en HTTPS ou localhost).</div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Pendant la capture</div>
          <h1>Capteurs et home trainer</h1>
          <p>Impose une puissance constante (mode ERG) et vérifie cadence, équilibre G/D et cardio pendant que tu filmes. Les données fines (phases, efficacité) passent par le .FIT de l'Edge 1050.</p>
        </div>
      </header>

      <div className="grid-3">
        <div className="tile">
          <div className="tile-label"><span className={`status-dot${names.power ? " on" : ""}`} /> <Zap size={15} /> Puissance (Assioma)</div>
          <div className="tile-value">{power?.power ?? "—"}<small>W</small></div>
          <div className="subtle">Cadence {power?.cadence ?? "—"} tr/min · équilibre G {power?.balanceLeft != null ? `${power.balanceLeft.toFixed(1)} %` : "—"}</div>
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={() => run("power", () => connectPower(setPower))}>
            <Bluetooth size={14} /> {names.power ?? "Connecter les pédales"}
          </button>
        </div>
        <div className="tile">
          <div className="tile-label"><span className={`status-dot${names.hr ? " on" : ""}`} /> <HeartPulse size={15} /> Fréquence cardiaque</div>
          <div className="tile-value">{hr ?? "—"}<small>bpm</small></div>
          <div className="subtle">Wahoo TRACKR ou autre ceinture</div>
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={() => run("hr", () => connectHeartRate(setHr))}>
            <Bluetooth size={14} /> {names.hr ?? "Connecter la ceinture"}
          </button>
        </div>
        <div className="tile">
          <div className="tile-label"><span className={`status-dot${trainerOn ? " on" : ""}`} /> <Gauge size={15} /> Mode ERG (Tacx Neo 2T)</div>
          <div className="row" style={{ marginTop: 6 }}>
            <button className="icon-btn" aria-label="−10 W" onClick={() => changeTarget(target - 10)}><Minus size={16} /></button>
            <div className="tile-value" style={{ margin: 0 }}>{target}<small>W</small></div>
            <button className="icon-btn" aria-label="+10 W" onClick={() => changeTarget(target + 10)}><Plus size={16} /></button>
          </div>
          <div className="subtle">{trainerOn ?? "Non connecté"}</div>
          <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={connectErg}><Bluetooth size={14} /> {trainerOn ? "Reconnecter" : "Connecter et imposer"}</button>
        </div>
      </div>

      <div className="alert info" style={{ marginTop: 18 }}>
        <Bluetooth size={17} />
        <span>Un capteur Bluetooth n'accepte souvent qu'une connexion à la fois : laisse l'Edge 1050 en ANT+ et connecte l'application en Bluetooth.
          Le pilotage du Neo (FE-C sur Bluetooth, repli FTMS) suit les spécifications publiées mais n'a pas encore été essayé sur ton matériel.</span>
      </div>
    </div>
  );
}
