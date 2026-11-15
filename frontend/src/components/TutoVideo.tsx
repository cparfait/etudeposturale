import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PlayCircle, X } from "lucide-react";

/** Chapitres du tutoriel vidéo (media/tuto : durées des compositions c0 à c6). */
export const TUTO_CHAPTERS = [
  { id: "intro", t: 0, label: "Ouverture" },
  { id: "materiel", t: 6.0, label: "1 · Le matériel" },
  { id: "pastilles", t: 16.6, label: "2 · Les pastilles" },
  { id: "telephones", t: 35.0, label: "3 · Les téléphones" },
  { id: "cadrage", t: 46.4, label: "4 · Le cadrage" },
  { id: "enregistrement", t: 55.3, label: "5 · L'enregistrement" },
  { id: "resultats", t: 65.9, label: "6 · Les résultats" },
] as const;
export type TutoChapter = (typeof TUTO_CHAPTERS)[number]["id"];

/** Lecteur du tutoriel avec ses chapitres cliquables (le chapitre en cours est surligné). */
export function TutoPlayer({ start = "intro", autoPlay = true }: { start?: TutoChapter; autoPlay?: boolean }) {
  const video = useRef<HTMLVideoElement>(null);
  const [now, setNow] = useState(0);
  useEffect(() => {
    const v = video.current;
    const c = TUTO_CHAPTERS.find((x) => x.id === start);
    if (v && c && c.t) v.currentTime = c.t;
  }, [start]);
  const current = [...TUTO_CHAPTERS].reverse().find((c) => now >= c.t - 0.05)?.id ?? "intro";
  function go(t: number) {
    const v = video.current;
    if (!v) return;
    v.currentTime = t;
    v.play().catch(() => {});
  }
  return (
    <div className="tuto">
      <video ref={video} src="/tuto/seance.mp4" poster="/tuto/seance-poster.jpg" controls playsInline preload="metadata"
        autoPlay={autoPlay} onTimeUpdate={(e) => setNow(e.currentTarget.currentTime)} />
      <nav className="tuto-chapters" aria-label="Chapitres du tutoriel">
        {TUTO_CHAPTERS.map((c) => (
          <button key={c.id} type="button" className={c.id === current ? "on" : ""} aria-current={c.id === current} onClick={() => go(c.t)}>
            {c.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

/** Bouton « Voir le tuto » qui ouvre le lecteur dans une fenêtre (Échap ou clic à côté pour fermer). */
export function TutoButton({ label = "Voir le tuto vidéo", start, className = "btn btn-ghost" }: { label?: string; start?: TutoChapter; className?: string }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    document.querySelectorAll("audio").forEach((a) => a.pause());   // la narration du guide se tait pendant la vidéo
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [open]);
  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)}><PlayCircle size={16} /> {label}</button>
      {open && createPortal(
        <div className="tuto-modal" role="dialog" aria-modal="true" aria-label="Tutoriel vidéo : une séance complète" onClick={() => setOpen(false)}>
          <div className="tuto-box" onClick={(e) => e.stopPropagation()}>
            <div className="tuto-head">
              <strong>Une séance complète, en 1 min 20</strong>
              <button type="button" className="tuto-close" onClick={() => setOpen(false)} aria-label="Fermer"><X size={20} /></button>
            </div>
            <TutoPlayer start={start} />
          </div>
        </div>,
        document.body,   // hors de la page : aucune carte ne passe par-dessus
      )}
    </>
  );
}
