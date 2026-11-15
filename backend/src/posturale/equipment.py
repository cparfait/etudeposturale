"""Équipement de la personne : ce qui est obligatoire, recommandé ou optionnel, et comment l'outil s'adapte.

Stocké dans data/equipement.json : {"onboarding_fait": bool, "items": {id: true | false | null}}.
null = pas encore répondu (l'outil se comporte alors comme si l'équipement était présent).
"""
from __future__ import annotations

import json
from typing import Any

from posturale.config import data_dir

CATALOG: list[dict[str, str]] = [
    # ---- obligatoire
    {"id": "velo_fixe", "niveau": "obligatoire", "icone": "bike", "nom": "Ton vélo sur un home trainer",
     "pourquoi": "Tu pédales sur place, toujours au même endroit, devant la caméra.",
     "sans": "Indispensable : sans support fixe, impossible de filmer ton pédalage de profil. Des rouleaux conviennent si tu es à l'aise dessus."},
    {"id": "telephone", "niveau": "obligatoire", "icone": "smartphone", "nom": "Un smartphone pour filmer",
     "pourquoi": "Il filme une minute de pédalage, idéalement en 60 images par seconde (réglage de l'appli Appareil photo).",
     "sans": "Indispensable. Presque tous les téléphones récents filment en 60 images/s ; à 30 images/s la mesure reste possible mais moins précise."},
    {"id": "support", "niveau": "obligatoire", "icone": "tripod", "nom": "Un trépied ou un support stable",
     "pourquoi": "Le téléphone doit rester immobile, à hauteur de selle, à 2,5–3 m du vélo.",
     "sans": "Indispensable. Un trépied de téléphone coûte environ 15–20 € ; en dépannage, une chaise et des livres bien calés."},
    {"id": "pastilles_orange", "niveau": "obligatoire", "icone": "circle", "nom": "Pastilles {velo} de 20 mm (2 par côté filmé)",
     "pourquoi": "Sur l'axe du pédalier et au bout de l'axe de pédale : l'échelle en millimètres et la position de la manivelle. "
                 "Deux côtés filmés : 4.",
     "sans": "Indispensable pour les millimètres. Le mieux : de la bande de kiné en carrés de 2 cm ; sinon des gommettes mates de 19–20 mm. "
             "Alternative : une mire ChArUco imprimée."},
    {"id": "metre", "niveau": "obligatoire", "icone": "ruler", "nom": "Un mètre ruban",
     "pourquoi": "Pour relever ta hauteur de selle actuelle : la correction proposée part de cette valeur.",
     "sans": "Indispensable pour appliquer la correction en millimètres. Un mètre de bricolage fait l'affaire."},
    # ---- recommandé
    {"id": "pastilles_vertes", "niveau": "recommande", "icone": "circle", "nom": "Pastilles {corps} de 20 mm sur le corps (8 par côté)",
     "pourquoi": "Épaule, coude, poignet, hanche, genou, cheville, talon, pied. "
                 "Deux côtés : 16, + 2 rotules (face) et 2 bas du dos (dos).",
     "sans": "L'outil s'adapte : l'IA de pose repère les articulations seule. Compte quelques degrés de précision en moins."},
    {"id": "eclairage", "niveau": "recommande", "icone": "sun", "nom": "Un bon éclairage",
     "pourquoi": "Une lumière continue et homogène donne une image nette et des pastilles bien visibles.",
     "sans": "L'outil s'adapte : le contrôle des pastilles te dira si l'image est trop sombre. Évite surtout le contre-jour."},
    # ---- optionnel
    {"id": "trainer_connecte", "niveau": "optionnel", "icone": "gauge", "nom": "Home trainer connecté (Bluetooth, mode ERG)",
     "pourquoi": "L'outil impose la puissance tout seul pendant l'échauffement et le film.",
     "sans": "L'outil s'adapte : tu règles une résistance fixe et tu gardes la même allure ; il te le rappelle."},
    {"id": "capteur_puissance", "niveau": "optionnel", "icone": "zap", "nom": "Capteur de puissance ou de cadence (Bluetooth)",
     "pourquoi": "Le coach surveille ta cadence pendant le film et te dit d'accélérer ou de ralentir.",
     "sans": "L'outil s'adapte : vise 85 à 95 tours par minute, au compteur ou au ressenti."},
    {"id": "micro", "niveau": "optionnel", "icone": "mic", "nom": "Un micro (casque ou celui du PC)",
     "pourquoi": "Tu pilotes la séance guidée à la voix, mains sur le guidon.",
     "sans": "L'outil s'adapte : tu avances avec les boutons ou la barre d'espace."},
    {"id": "compteur_fit", "niveau": "optionnel", "icone": "activity", "nom": "Compteur GPS (fichier .FIT)",
     "pourquoi": "Ajoute puissance, cadence et équilibre gauche / droite pendant les prises.",
     "sans": "L'outil s'adapte : l'import du fichier .FIT est masqué."},
    {"id": "mire", "niveau": "optionnel", "icone": "grid", "nom": "Mire ChArUco imprimée",
     "pourquoi": "Corrige la déformation de l'objectif et peut remplacer les pastilles orange pour l'échelle.",
     "sans": "L'outil s'adapte : pas de correction d'objectif, la longueur de manivelle sert d'échelle."},
    {"id": "cardio", "niveau": "optionnel", "icone": "heart", "nom": "Ceinture cardio",
     "pourquoi": "Ta fréquence cardiaque s'affiche pendant la séance.",
     "sans": "Rien ne change pour la mesure."},
    {"id": "ia", "niveau": "optionnel", "icone": "sparkles", "nom": "Le coach IA (Ollama sur le PC ou un service en ligne)",
     "pourquoi": "Il explique tes résultats, répond à tes questions et adapte la séance.",
     "sans": "L'outil s'adapte : le plan de séance et la modification proposée viennent toujours de l'application ; seules les explications libres disparaissent."},
]
BY_ID = {c["id"]: c for c in CATALOG}


def catalog() -> list[dict[str, str]]:
    """Catalogue avec les noms des couleurs de pastilles choisies (« orange », « roses »…)."""
    from posturale.pose.markers import sticker_names

    n = sticker_names()
    return [{k: (v.format_map(n) if isinstance(v, str) else v) for k, v in c.items()} for c in CATALOG]


def _path():
    return data_dir() / "equipement.json"


def load() -> dict[str, Any]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    items = {k: raw.get("items", {}).get(k) for k in BY_ID}
    return {"onboarding_fait": bool(raw.get("onboarding_fait")), "items": items}


def save(patch: dict[str, Any]) -> dict[str, Any]:
    cur = load()
    if "onboarding_fait" in patch:
        cur["onboarding_fait"] = bool(patch["onboarding_fait"])
    for k, v in (patch.get("items") or {}).items():
        if k in BY_ID and v in (True, False, None):
            cur["items"][k] = v
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


def has(state: dict, key: str) -> bool:
    """Présent ou pas encore répondu."""
    return state["items"].get(key) is not False


def missing_required(state: dict) -> list[str]:
    out = []
    for c in CATALOG:
        if c["niveau"] != "obligatoire" or state["items"].get(c["id"]) is not False:
            continue
        if c["id"] == "pastilles_orange" and state["items"].get("mire"):
            continue  # la mire donne l'échelle
        out.append(c["id"])
    return out


def view(state: dict | None = None) -> dict[str, Any]:
    s = state or load()
    missing = missing_required(s)
    cat = catalog()
    adaptations = [{"id": c["id"], "nom": c["nom"], "texte": c["sans"]} for c in cat
                   if c["niveau"] != "obligatoire" and s["items"].get(c["id"]) is False and c["id"] != "cardio"]
    if s["items"].get("pastilles_orange") is False and s["items"].get("mire"):
        adaptations.insert(0, {"id": "pastilles_orange", "nom": "Pastilles du vélo",
                               "texte": "Pas de pastilles sur le vélo : la mire ChArUco posée contre le cadre donne l'échelle."})
    answered = sum(v is not None for v in s["items"].values())
    from posturale.pose.markers import current_preset, sticker_names

    return {**s, "catalogue": cat, "pastilles": {"preset": current_preset(), **sticker_names()}, "manquants": missing, "adaptations": adaptations,
            "repondu": answered, "total": len(CATALOG), "pret": not missing}


def summary_for_ai(state: dict | None = None) -> dict[str, Any] | None:
    s = state or load()
    if not any(v is not None for v in s["items"].values()):
        return None
    names = {c["id"]: c["nom"] for c in catalog()}
    return {"present": [names[k] for k, v in s["items"].items() if v],
            "absent": [names[k] for k, v in s["items"].items() if v is False],
            "obligatoires_manquants": [names[k] for k in missing_required(s)]}
