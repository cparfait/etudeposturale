import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, GraduationCap, Wand2 } from "lucide-react";
import EquipmentList from "../components/EquipmentList";
import { useEquipment } from "../equipment";

export default function Equipment() {
  const eq = useEquipment();
  if (!eq) return <div className="page"><p className="subtle">Chargement…</p></div>;
  const missing = eq.catalogue.filter((c) => eq.manquants.includes(c.id));
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Avant de filmer</div>
          <h1>Mon équipement</h1>
          <p>Indique ce que tu as : l'outil adapte la séance guidée et les écrans. Seul le matériel marqué « obligatoire » est indispensable pour mesurer.</p>
        </div>
        <Link to="/bienvenue" className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }}><GraduationCap size={15} /> Guide de démarrage</Link>
      </header>

      {missing.length > 0 ? (
        <div className="alert danger" style={{ marginBottom: 18 }}>
          <AlertTriangle size={18} />
          <span>Il te manque pour mesurer : <strong>{missing.map((m) => m.nom.toLowerCase()).join(", ")}</strong>.</span>
        </div>
      ) : (
        <div className="alert ok" style={{ marginBottom: 18 }}>
          <CheckCircle2 size={18} />
          <span>{eq.repondu < eq.total ? "Rien d'obligatoire ne manque parmi tes réponses." : "Tout l'indispensable est là : tu peux lancer la séance guidée."}</span>
        </div>
      )}

      <div className="eq-page">
        <section>
          <h2 className="eq-section">Indispensable et recommandé</h2>
          <EquipmentList eq={eq} levels={["obligatoire", "recommande"]} />
        </section>
        <section>
          <h2 className="eq-section">Optionnel</h2>
          <EquipmentList eq={eq} levels={["optionnel"]} />
          {eq.adaptations.length > 0 && (
            <div className="ob-adapt" style={{ marginTop: 14 }}>
              <strong><Wand2 size={16} /> Ce que l'outil adapte pour toi</strong>
              <ul>{eq.adaptations.map((a) => <li key={a.id}><b>{a.nom}</b> : {a.texte.replace(/^L'outil s'adapte : /, "")}</li>)}</ul>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
