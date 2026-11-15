import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { CheckCircle2, Loader2, ShieldAlert, Smartphone, WifiOff } from "lucide-react";
import { ETAT_LABEL, phoneUrl, type Pairing } from "../remote";

/** QR code à scanner avec le téléphone, puis la liste des téléphones reliés (vue filmée, état). */
export default function PhonePairing({ pairing, onRole, compact = false }: {
  pairing: Pairing | null; onRole: (did: string, role: string) => void; compact?: boolean;
}) {
  const [qr, setQr] = useState("");
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!pairing?.code) return;
    phoneUrl(pairing.code).then(({ url: u }) => {
      setUrl(u);
      QRCode.toDataURL(u, { margin: 1, width: 360, color: { dark: "#0f150e", light: "#ffffff" } }).then(setQr).catch(() => {});
    });
  }, [pairing?.code]);

  const devices = pairing?.appareils ?? [];
  const secure = location.protocol === "https:";
  return (
    <div className={`pp${compact ? " compact" : ""}`}>
      <div className="pp-qr">
        {qr ? <img src={qr} alt={`QR code : ${url}`} /> : <Loader2 className="spin" />}
        <div className="pp-code">Code <b>{pairing?.code ?? "……"}</b></div>
      </div>
      <div className="pp-side">
        <p className="pp-lead"><Smartphone size={16} /> Scanne ce QR code avec chaque téléphone (même Wi-Fi que le PC).</p>
        {url && <p className="pp-url">{url}</p>}
        {!secure && (
          <p className="pp-warn"><ShieldAlert size={15} /> Sans HTTPS, le téléphone peut envoyer une vidéo filmée avec son appli Appareil photo,
            mais pas filmer depuis la page. Pour l'enregistrement lancé depuis le PC, active le HTTPS (README, « Utiliser le téléphone »).</p>
        )}
        {devices.length === 0 ? <p className="subtle pp-none">Aucun téléphone relié pour l'instant.</p> : (
          <ul className="pp-list">
            {devices.map((d) => (
              <li key={d.id} className={d.connecte ? "" : "off"}>
                {d.connecte ? (d.etat === "envoye" ? <CheckCircle2 size={16} className="ok" /> : <span className={`pp-dot ${d.etat}`} />) : <WifiOff size={16} />}
                <span className="pp-name">{d.nom}</span>
                <select className="select pp-role" value={d.role} onChange={(e) => onRole(d.id, e.target.value)} aria-label={`Vue filmée par ${d.nom}`}>
                  {pairing!.roles.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                </select>
                <span className="pp-state">{d.connecte ? ETAT_LABEL[d.etat] ?? d.etat : "Hors ligne"}
                  {d.connecte && !d.secure && " · envoi seul"}{d.fps ? ` · ${Math.round(d.fps)} i/s` : ""}</span>
                {d.connecte && d.etat === "erreur" && d.message && <span className="pp-err">{d.message}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
