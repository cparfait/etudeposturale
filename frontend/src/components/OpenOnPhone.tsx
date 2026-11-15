import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Loader2, Smartphone } from "lucide-react";
import { lanUrl } from "../remote";

/** QR code qui ouvre la page courante sur le téléphone (même Wi-Fi que le PC). */
export default function OpenOnPhone({ path, title = "Ouvrir sur le téléphone", children }: { path: string; title?: string; children?: React.ReactNode }) {
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
        <h2><Smartphone size={18} /> {title}</h2>
        <p className="subtle">Scanne ce QR code avec le téléphone (même Wi-Fi que le PC).</p>
        {url && <p className="oop-url">{url}</p>}
        {url.startsWith("https") && (
          <details className="pp-ca">
            <summary>« Connexion non sécurisée » sur le téléphone ?</summary>
            <p>Normal : le certificat vient de ton PC, pas d'internet. Touche « Paramètres avancés » puis « Continuer vers {url.split("/")[2]?.split(":")[0]} ».
              Pour ne plus le voir : sur le téléphone, ouvre <code>{url.split("/").slice(0, 3).join("/")}/api/remote/autorite.crt</code> et installe ce certificat
              (Android : Paramètres › Sécurité › Installer un certificat › Certificat CA ; iPhone : Réglages › Profil téléchargé, puis Informations › Réglages des certificats).</p>
          </details>
        )}
        {children}
      </div>
    </section>
  );
}
