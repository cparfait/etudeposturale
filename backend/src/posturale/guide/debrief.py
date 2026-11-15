"""Débrief d'une séance : résultats, comparaison avec la séance précédente et UNE seule modification proposée.

La modification vient du moteur (règles sourcées) ; l'IA ne fait que l'expliquer.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session as DB, select

from posturale.config import load_metrics
from posturale.guide.plan import config_changes, view_key
from posturale.storage.models import Analysis, BikeConfig, Capture, Session as Seance

COMPARED = ["P1", "P2", "P3", "P4", "P6"]
APPLICABLE = {"hauteur_selle_mm": "Hauteur de selle", "recul_selle_mm": "Recul de selle"}


def session_results(db: DB, sid: int) -> dict[str, dict]:
    """Dernière analyse de chaque prise de la séance (clé de vue → statut + résumé)."""
    out: dict[str, dict] = {}
    for c in db.exec(select(Capture).where(Capture.session_id == sid).order_by(Capture.id)):
        a = db.exec(select(Analysis).where(Analysis.capture_id == c.id).order_by(Analysis.id.desc())).first()
        if not a:
            continue
        summ = a.summary or {}
        key = view_key(c.vue, summ.get("cote")) if a.status == "terminee" else f"{c.vue}#{c.id}"
        out[key] = {"statut": a.status, "analysis_id": a.id, "capture_id": c.id, "erreur": a.error, "resume": summ}
    return out


def _previous(db: DB, sid: int) -> Seance | None:
    rows = db.exec(select(Seance).where(Seance.id < sid).order_by(Seance.id.desc()))
    for s in rows:
        if any(r["statut"] == "terminee" for r in session_results(db, s.id).values()):
            return s
    return None


def _metric(res: dict, k: str) -> float | None:
    v = ((res.get("resume") or {}).get("metriques") or {}).get(k, {})
    v = v.get("moyenne") if isinstance(v, dict) else None
    return round(float(v), 1) if isinstance(v, (int, float)) else None


def compare(now: dict[str, dict], before: dict[str, dict]) -> list[dict]:
    metrics = load_metrics()["metrics"]
    out = []
    for key in ("profil_D", "profil_G"):
        if key not in now or key not in before:
            continue
        for m in COMPARED:
            a, b = _metric(before[key], m), _metric(now[key], m)
            if a is None or b is None:
                continue
            out.append({"prise": key, "metrique": m, "nom": metrics.get(m, {}).get("nom", m), "unite": metrics.get(m, {}).get("unite"),
                        "avant": a, "apres": b, "delta": round(b - a, 1)})
    return out


def propose_change(now: dict[str, dict], hypotheses: list[dict], config: dict | None) -> dict:
    """Une seule modification : santé d'abord, puis hauteur de selle si les deux côtés concordent, sinon le conseil du moteur."""
    for h in hypotheses:
        if h.get("categorie") == "sante" and h.get("priorite") == "haute":
            return {"type": "consulter", "titre": h["titre"], "texte": h["action"],
                    "raison": "Une alerte santé passe avant tout réglage."}
    for h in hypotheses:  # séquence des fitters : un réglage de cales prioritaire passe avant la hauteur de selle
        if h.get("categorie") == "cales" and h.get("priorite") == "haute":
            return {"type": "conseil", "titre": h["titre"], "texte": h["action"], "raison": h.get("hypothese", "")}
    verdicts = {k: (r.get("resume") or {}).get("verdict_selle") or {} for k, r in now.items()
                if k.startswith("profil_") and r["statut"] == "terminee"}
    off = {k: v for k, v in verdicts.items() if v.get("statut") in ("trop_tendu", "trop_plie")}
    if off:
        dirs = {v["statut"] for v in off.values()}
        others = [k for k, v in verdicts.items() if k not in off and v.get("statut") == "dans_la_plage"]
        if len(dirs) > 1:
            return {"type": "aucun", "titre": "Pas de changement de selle pour l'instant",
                    "raison": "Les deux côtés ne vont pas dans le même sens : asymétrie à explorer (cales, bassin, longueur de jambes) avant de toucher la selle."}
        corrs = [float(v.get("correction_mm") or 0) for v in off.values()]
        corr = min(corrs, key=abs)  # le plus prudent
        if others:  # un côté dans la plage : on ne corrige que la moitié, pour ne pas le sortir de la plage
            corr = corr / 2
        corr = round(corr)
        if abs(corr) >= 2:
            before = (config or {}).get("hauteur_selle_mm")
            sens = "Monter" if corr > 0 else "Baisser"
            cotes = " et ".join("droit" if k == "profil_D" else "gauche" for k in off)
            return {
                "type": "reglage", "champ": "hauteur_selle_mm", "libelle": "Hauteur de selle", "delta": corr,
                "avant": before, "apres": round(before + corr, 1) if isinstance(before, (int, float)) else None,
                "titre": f"{sens} la selle de {abs(corr)} mm",
                "raison": f"Extension du genou hors plage côté {cotes}" + (" (l'autre côté est dans la plage : correction réduite de moitié)" if others else "") + ".",
                "comment": "Marque la tige de selle au ruban ou au feutre, desserre le collier, déplace d'autant (réglet contre le repère), "
                           "vérifie l'alignement de la selle et resserre au couple indiqué.",
                "verification": "Roule 2 à 3 sorties sans rien changer d'autre, note tes ressentis, puis lance une séance de vérification.",
            }
    for h in hypotheses:
        if h.get("priorite") in ("haute", "moyenne") and h.get("categorie") != "selle_hauteur":
            return {"type": "conseil", "titre": h["titre"], "texte": h["action"], "raison": h.get("hypothese", "")}
    return {"type": "aucun", "titre": "On ne touche à rien",
            "raison": "Les mesures sont dans les plages et le moteur ne propose pas de changement : garde ce réglage et écoute tes sensations."}


def build(db: DB, sid: int) -> dict[str, Any]:
    from posturale.api.routes_health import _context
    from posturale.health.rules import evaluate

    s = db.get(Seance, sid)
    if not s:
        raise KeyError(sid)
    now = session_results(db, sid)
    prev = _previous(db, sid)
    before = session_results(db, prev.id) if prev else {}
    ctx, _ = _context(db)
    hyps = evaluate(ctx)
    cfg = db.get(BikeConfig, s.bike_config_id) if s.bike_config_id else None
    prev_cfg = db.get(BikeConfig, prev.bike_config_id) if prev and prev.bike_config_id else None
    pending = [k for k, r in now.items() if r["statut"] in ("en_attente", "en_cours")]
    failed = [{"prise": k, "erreur": r["erreur"]} for k, r in now.items() if r["statut"] == "erreur"]
    resultats = {}
    for k, r in now.items():
        if r["statut"] != "terminee":
            continue
        summ = r["resume"]
        resultats[k] = {"verdict_selle": summ.get("verdict_selle"), "qualite": summ.get("qualite"),
                        "mesures": {m: _metric(r, m) for m in COMPARED if _metric(r, m) is not None},
                        "analysis_id": r["analysis_id"]}
        if not k.startswith("profil"):
            resultats[k]["metriques"] = summ.get("metriques")
    return {
        "seance_id": sid, "seance_precedente_id": prev.id if prev else None,
        "en_cours": pending, "erreurs": failed, "resultats": resultats,
        "changement_depuis_precedente": config_changes(prev_cfg.model_dump() if prev_cfg else None, cfg.model_dump() if cfg else None),
        "comparaison": compare(now, before) if prev else [],
        "hypotheses": [{k: h.get(k) for k in ("titre", "categorie", "priorite", "action")} for h in hyps[:4]],
        "modification": propose_change(now, hyps, cfg.model_dump() if cfg else None) if resultats else None,
        # charge d'entraînement, asymétrie : pas une modification du vélo, mais à garder en tête pendant l'essai
        "a_garder_en_tete": [{"titre": h["titre"], "texte": h["action"]} for h in hyps
                             if h.get("categorie") in ("charge", "asymetrie") and h.get("priorite") == "haute"][:2],
        "configuration": {k: v for k, v in (cfg.model_dump() if cfg else {}).items() if k in APPLICABLE or k in ("id", "libelle")},
    }
