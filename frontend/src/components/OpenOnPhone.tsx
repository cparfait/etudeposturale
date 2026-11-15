import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Loader2, Smartphone } from "lucide-react";
import { lanUrl } from "../remote";

/** QR code qui ouvre la page courante sur le téléphone (même Wi-Fi que le PC). */
export default function OpenOnPhone({ path, children }: { path: string; children?: React.ReactNode }) {
  const [qr, setQr] = useState("");
  const [url, setUrl] = useState("");
  useEffect(() => {
    lanUrl(path).then(({ url: u }) => {
      setUrl(u);
      QRCode.toDataURL(u, { margin: 1, width: 280, color: { dark: "#0f150e", light: "#ffffff" } }).then(setQr).catch(() => {});
    });
  }, [path]);
  return (
    <section className="card oop">
      <div className="oop-qr">{qr ? <img src={qr} alt={`QR code : ${url}`} /> : <Loader2 className="spin" />}</div>
      <div>
        <h2><Smartphone size={18} /> Ouvrir sur le téléphone</h2>
        <p className="subtle">Scanne ce QR code avec le téléphone (même Wi-Fi que le PC).</p>
        {url && <p className="oop-url">{url}</p>}
        {children}
      </div>
    </section>
  );
}
