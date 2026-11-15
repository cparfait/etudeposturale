import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { openPreview } from "../remote";

/** Image en direct d'un téléphone relié (aperçu réduit, ≈ 10 images/s). */
export default function PhoneFeed({ code, did, label }: { code: string; did: string; label: string }) {
  const img = useRef<HTMLImageElement>(null);
  const [live, setLive] = useState(false);
  useEffect(() => {
    let url = "";
    const stop = openPreview(code, did, (blob) => {
      const next = URL.createObjectURL(blob);
      if (img.current) img.current.src = next;
      if (url) URL.revokeObjectURL(url);
      url = next;
      setLive(true);
    });
    return () => { stop(); if (url) URL.revokeObjectURL(url); };
  }, [code, did]);
  return (
    <figure className="pf">
      <img ref={img} alt={`Image en direct : ${label}`} hidden={!live} />
      {!live && <span className="pf-wait"><Loader2 className="spin" size={18} /> Image en attente…</span>}
      <figcaption>{label}</figcaption>
    </figure>
  );
}
