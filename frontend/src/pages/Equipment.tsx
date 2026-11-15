import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, GraduationCap } from "lucide-react";
import EquipmentList from "../components/EquipmentList";
import { useEquipment } from "../equipment";

export default function Equipment() {
  const eq = useEquipment();
  if (!eq) return <div className="page"><p className="subtle">Chargement…</p></div>;
  const missing = eq.catalogue.filter((c) => eq.manquants.includes(c.id));
  return (
    <div className="page eq-compact">
      <header className="page-head">
        <div>
          <div className="eyebrow">Avant de filmer</div>
          <h1>Mon équipement</h1>
          <p>Indique ce que tu as : l'outil s'adapte. Seul le matériel « obligatoire » est indispensable. Pastilles : deux couleurs vives au choix, apprises dans <Link className="link" to="/pastilles">l'étalonnage</Link>.</p>
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
        <EquipmentList eq={eq} levels={["obligatoire", "recommande", "optionnel"]} />
      </div>
    </div>
  );
}
