"""Plan d'une séance guidée, construit à partir des données (déterministe), puis adaptable par l'IA.

Trois cas :
- « premiere » : aucune analyse terminée → les deux profils (et face / dos si une douleur le justifie) ;
- « verification » : la configuration du vélo a changé depuis la dernière séance analysée → mêmes prises,
  même puissance, pour comparer avant / après ;
- « suivi » : rien n'a changé → on refait les prises utiles (vues manquantes, côtés).
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlmodel import Session as DB, select

from posturale import equipment

from posturale.storage.models import Analysis, BikeConfig, Capture, FitFile, PainEntry, Profile, Session as Seance

VIEWS: dict[str, dict[str, str]] = {
    "profil_D": {"vue": "profil", "cote": "D", "titre": "Profil droit"},
    "profil_G": {"vue": "profil", "cote": "G", "titre": "Profil gauche"},
    "face": {"vue": "face", "cote": "", "titre": "Vue de face"},
    "dos": {"vue": "dos", "cote": "", "titre": "Vue de dos"},
}

FIELDS = {  # champs de configuration comparés pour détecter un changement (libellé, unité)
    "hauteur_selle_mm": ("hauteur de selle", "mm"), "recul_selle_mm": ("recul de selle", "mm"),
    "inclinaison_selle_deg": ("inclinaison de selle", "°"), "drop_selle_cintre_mm": ("drop selle-cintre", "mm"),
    "distance_selle_cintre_mm": ("distance selle-cintre", "mm"), "potence_mm": ("potence", "mm"),
    "potence_angle_deg": ("angle de potence", "°"), "entretoises_mm": ("entretoises", "mm"),
    "largeur_cintre_mm": ("largeur de cintre", "mm"), "manivelle_mm": ("manivelles", "mm"),
    "cales_avance_mm": ("avance des cales", "mm"), "cales_rotation_g_deg": ("rotation cale gauche", "°"),
    "cales_rotation_d_deg": ("rotation cale droite", "°"), "cales_lateral_g_mm": ("latéral cale gauche", "mm"),
    "cales_lateral_d_mm": ("latéral cale droite", "mm"),
}

BODY = [
    ("Épaule", "Acromion : la pointe osseuse au sommet de l'épaule."),
    ("Coude", "Épicondyle : la bosse osseuse à l'extérieur du coude."),
    ("Poignet", "Styloïde : la petite bosse côté auriculaire."),
    ("Hanche", "Grand trochanter : la bosse sur le côté de la hanche, à repérer assis, manivelle en bas."),
    ("Genou", "Épicondyle fémoral : sur le côté du genou, au niveau du pli."),
    ("Cheville", "Malléole externe : la bosse de la cheville."),
    ("Talon", "Sur la chaussure, à l'arrière du talon."),
    ("Pied", "Sur la chaussure, en face de la tête du 5e métatarse (bord extérieur, au plus large)."),
]


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def _last_analyzed_session(db: DB) -> tuple[Seance | None, dict[str, dict]]:
    """Dernière séance avec au moins une analyse terminée, et ses prises (clé de vue → résumé)."""
    rows = db.exec(select(Analysis, Capture, Seance).where(Analysis.capture_id == Capture.id, Capture.session_id == Seance.id,
                                                            Analysis.status == "terminee").order_by(Seance.id.desc(), Analysis.id.desc()))
    sess, views = None, {}
    for a, c, s in rows:
        if sess is None:
            sess = s
        if s.id != sess.id:
            break
        key = view_key(c.vue, (a.summary or {}).get("cote"))
        views.setdefault(key, a.summary or {})
    return sess, views


def view_key(vue: str, cote: str | None) -> str:
    return f"profil_{cote}" if vue == "profil" and cote in ("D", "G") else vue


def config_changes(before: dict | None, after: dict | None) -> list[dict]:
    if not before or not after:
        return []
    out = []
    for k, (label, unit) in FIELDS.items():
        a, b = _num(before.get(k)), _num(after.get(k))
        if a is not None and b is not None and abs(a - b) >= 0.5:
            out.append({"champ": k, "libelle": label, "unite": unit, "avant": a, "apres": b, "delta": round(b - a, 1)})
    return out


def _fmt_change(c: dict) -> str:
    sign = "+" if c["delta"] > 0 else "−"
    return f"{c['libelle']} {sign}{abs(c['delta']):g} {c['unite']}"


def _default_power(db: DB, last: Seance | None) -> int:
    if last and last.puissance_cible_w:
        return int(last.puissance_cible_w)
    fit = db.exec(select(FitFile).order_by(FitFile.id.desc())).first()
    p = _num(((fit.summary or {}).get("global") or {}).get("puissance_w")) if fit else None
    if p:
        return int(min(250, max(100, round(p * 0.95 / 10) * 10)))
    prof = db.get(Profile, 1)
    if prof and prof.poids_kg:
        return int(min(220, max(110, round(prof.poids_kg * 2 / 10) * 10)))  # ≈ endurance pour un cycliste entraîné
    return 150


def facts(db: DB) -> dict[str, Any]:
    """Ce qui détermine le plan (servira aussi à l'IA)."""
    last, last_views = _last_analyzed_session(db)
    current = db.exec(select(BikeConfig).order_by(BikeConfig.created_at.desc(), BikeConfig.id.desc())).first()
    last_cfg = db.get(BikeConfig, last.bike_config_id) if last and last.bike_config_id else None
    changes = config_changes(last_cfg.model_dump() if last_cfg else None, current.model_dump() if current else None)
    pains = [p.model_dump() for p in db.exec(select(PainEntry).where(PainEntry.active == True))]  # noqa: E712
    if last is None:
        kind = "premiere"
    elif changes:
        kind = "verification"
    else:
        kind = "suivi"
    return {"type": kind, "derniere_seance": last, "prises_precedentes": last_views, "changements": changes,
            "douleurs": pains, "config": current, "puissance_defaut": _default_power(db, last)}


def default_views(f: dict) -> tuple[list[str], list[str]]:
    zones = {p["zone"] for p in f["douleurs"]}
    knee = any(z.startswith("genou") for z in zones)
    back = bool(zones & {"lombaires", "fessier", "perinee", "hanche_laterale"})
    reasons: list[str] = []
    if f["type"] == "verification":
        prev = [k for k in VIEWS if k in f["prises_precedentes"]]
        views = prev or ["profil_D", "profil_G"]
        reasons.append("Mêmes prises qu'à la dernière séance pour comparer avant / après.")
    else:
        views = ["profil_D", "profil_G"]
        reasons.append("Les deux profils : hauteur de selle, recul, angles, et l'asymétrie gauche / droite.")
        if f["type"] == "suivi" and set(views) <= set(f["prises_precedentes"]):
            reasons.append("Rien n'a changé depuis la dernière séance : on vérifie que la mesure est répétable.")
    if knee and "face" not in views:
        views.append("face")
        reasons.append("Douleur au genou déclarée : la vue de face montre la trajectoire des genoux.")
    if back and "dos" not in views:
        views.append("dos")
        reasons.append("Douleur au bassin ou au dos déclarée : la vue de dos montre la bascule du bassin.")
    return views, reasons


def _step(id_: str, type_: str, titre: str, dire: str, **kw: Any) -> dict:
    return {"id": id_, "type": type_, "titre": titre, "dire": dire, **kw}


def build(db: DB, override: dict | None = None) -> dict[str, Any]:
    f = facts(db)
    views, reasons = default_views(f)
    override = override or {}
    if override.get("vues"):
        views = override["vues"]
    power = int(override.get("puissance_w") or f["puissance_defaut"])
    warmup = int(override.get("echauffement_min") or 10)
    kind = f["type"]
    profiles = [v for v in views if v.startswith("profil")]
    both = len(profiles) == 2
    change_txt = ", ".join(_fmt_change(c) for c in f["changements"])
    eq = equipment.load()
    green, trainer = equipment.has(eq, "pastilles_vertes"), equipment.has(eq, "trainer_connecte")
    meter, micro = equipment.has(eq, "capteur_puissance"), equipment.has(eq, "micro")
    chart_only = eq["items"].get("pastilles_orange") is False and bool(eq["items"].get("mire"))
    effort = f"à {power} watts" if trainer else "à résistance constante"
    if not green:
        reasons.append("Sans pastilles vertes : l'IA de pose repère les articulations seule (précision un peu réduite).")
    if not trainer:
        reasons.append("Home trainer non connecté : tu règles toi-même une résistance fixe, la même à chaque séance.")

    if kind == "verification":
        titre = "Séance de vérification"
        intro = (f"Séance de vérification après ton réglage : {change_txt}. On refait les mêmes prises, à la même puissance, "
                 f"{effort.removeprefix('à ')}, pour comparer avec la dernière séance. Je te guide étape par étape : dis « c'est fait » ou "
                 "« suivant » pour avancer, « répète » pour réécouter, et pose-moi une question quand tu veux.")
    elif kind == "premiere":
        titre = "Première séance guidée"
        intro = ("Bienvenue pour ta première séance guidée. On va poser les pastilles, installer le téléphone, t'échauffer, "
                 f"puis filmer {len(views)} prise{'s' if len(views) > 1 else ''} d'une minute {effort}. Compte une "
                 "quarantaine de minutes. Dis « c'est fait » ou « suivant » pour avancer, « répète » pour réécouter, et "
                 "pose-moi une question quand tu veux.")
    else:
        titre = "Séance de suivi"
        intro = (f"Séance de suivi : ta configuration n'a pas changé depuis la dernière fois. On refait {len(views)} prise"
                 f"{'s' if len(views) > 1 else ''} {effort} pour confirmer les mesures. Dis « c'est fait » ou « suivant » "
                 "pour avancer, et pose-moi une question quand tu veux.")

    steps = [_step("accueil", "info", titre, intro)]

    # ---- pastilles
    if profiles:
        side_txt = "des deux côtés" if both else ("côté droit" if profiles[0] == "profil_D" else "côté gauche")
        body_items = [{"t": t, "d": d} for t, d in BODY]
        dire = (f"Pastilles vertes sur le corps, {side_txt}. Je te les annonce une par une : dis « c'est fait » après chacune. "
                "Assieds-toi sur le vélo, manivelle en bas, pour repérer la hanche et le genou.")
        if kind == "verification":
            dire = f"Vérifie que les pastilles vertes sont toujours au même endroit, {side_txt}. Remets celles qui ont bougé."
        if green:
            steps.append(_step("pastilles_corps", "checklist", "Pastilles sur le corps", dire, items=body_items))
        bike_items = [{"t": "Axe de pédalier", "d": "Pastille orange au centre du plateau (ou du boîtier côté gauche)."},
                      {"t": "Axe de pédale", "d": "Pastille orange au bout de l'axe de pédale, côté caméra" + (" (les deux pédales)." if both else ".")}]
        if chart_only:
            steps.append(_step("mire", "checklist", "Mire contre le cadre",
                               "Sans pastilles orange, c'est la mire qui donne l'échelle : pose-la à plat contre le cadre, dans le plan du vélo.",
                               items=[{"t": "Mire contre le cadre", "d": "Bien à plat, côté caméra, entièrement visible sur l'image."}]))
        else:
            steps.append(_step("pastilles_velo", "checklist", "Pastilles sur le vélo",
                               "Deux pastilles orange sur le vélo : elles donnent l'angle de manivelle et l'échelle en millimètres.",
                               items=bike_items))
    extra = []
    if "face" in views:
        extra.append({"t": "Rotules", "d": "Une pastille verte au centre de chaque rotule (vue de face)."})
    if "dos" in views:
        extra.append({"t": "Bas du dos", "d": "Une pastille verte sur chacune des deux fossettes au-dessus des fesses (vue de dos)."})
    if extra and green:
        steps.append(_step("pastilles_face_dos", "checklist", "Pastilles face et dos",
                           "Pastilles supplémentaires pour " + (" et ".join(VIEWS[v]["titre"].lower() for v in views if v in ("face", "dos"))) + ".",
                           items=extra))
    steps.append(_step("controle_pastilles", "info", "Contrôle des pastilles",
                       "Si tu veux, vérifie que l'application voit bien toutes les pastilles avec une photo test : page « Contrôle des pastilles ». "
                       "Sinon, dis « suivant ».", lien="/pastilles"))

    # ---- caméra
    cam_items = [
        {"t": "Vélo de niveau", "d": "Niveau à bulle ; ruban adhésif au sol sous la roue arrière et les pieds du trépied."},
        {"t": "Trépied à 2,5–3 m, à hauteur de selle", "d": "Bien perpendiculaire au vélo pour le profil."},
        {"t": "Objectif 1x, 1080p, 60 ou 120 images/s", "d": "Jamais l'ultra grand-angle 0,5x. Stabilisation et HDR coupés."},
        {"t": "Mise au point et exposition verrouillées", "d": "Appui long sur le cycliste dans l'appli Appareil photo."},
        {"t": "Cadrage vérifié", "d": "Page « Cadrage en direct » ouverte sur le téléphone : attends le feu vert."},
    ]
    steps.append(_step("camera", "checklist", "Installer le téléphone",
                       "On installe le téléphone. Même chose : dis « c'est fait » après chaque point.", items=cam_items, lien="/cadrage"))

    # ---- home trainer + échauffement
    devices = (["trainer"] if trainer else []) + (["puissance"] if meter else [])
    if trainer:
        steps.append(_step("home_trainer", "ble", "Home trainer en mode ERG",
                           f"Connecte le home trainer pour imposer {power} watts"
                           + (", et les pédales si tu veux que je surveille ta cadence" if meter else "")
                           + ". Le Bluetooth demande un clic sur l'écran. Si tu utilises ton compteur à la place, règle-le en ERG puis dis « suivant ».",
                           puissance_w=power, appareils=devices))
    else:
        steps.append(_step("home_trainer", "ble" if meter else "info", "Résistance du home trainer",
                           "Règle une résistance fixe (ou un braquet) assez facile pour tenir 85 à 95 tours par minute sans forcer, "
                           "et garde exactement la même pendant toute la séance, et aux séances suivantes."
                           + (" Connecte tes pédales si tu veux que je surveille ta cadence." if meter else ""),
                           appareils=devices))
    steps.append(_step("echauffement", "timer", "Échauffement",
                       f"Échauffement de {warmup} minutes, en souplesse au début, puis "
                       + (f"à {power} watts sur la fin." if trainer else "à ta résistance de mesure sur la fin.")
                       + " Cadence entre 85 et 95. Dis « c'est parti » quand tu pédales ; « pause » si tu dois t'arrêter.",
                       duree_s=warmup * 60, puissance_w=power if trainer else None))

    # ---- prises
    for i, v in enumerate(views):
        info = VIEWS[v]
        before = ""
        if i > 0:
            prev = views[i - 1]
            if prev.startswith("profil") and v.startswith("profil"):
                before = "Descends du vélo et déplace le trépied de l'autre côté, sans bouger le vélo ; vérifie les pastilles de ce côté. "
            elif v == "face":
                before = "Place le trépied devant le vélo, dans l'axe, à hauteur de guidon. "
            elif v == "dos":
                before = "Place le trépied derrière le vélo, dans l'axe, à hauteur de selle. "
        dire = (f"{before}Prise : {info['titre'].lower()}. Lance l'enregistrement sur le téléphone, fais un clap face à la caméra, "
                f"puis pédale régulièrement, mains sur les cocottes. Dis « c'est parti » quand tu es en place : je compte une minute.")
        steps.append(_step(f"prise_{v}", "prise", info["titre"], dire, vue=info["vue"], cote=info["cote"], cle=v,
                           duree_s=60, puissance_w=power if trainer else None))

    steps.append(_step("import", "import", "Importer les vidéos",
                       "C'est filmé. Tu peux arrêter de pédaler. Transfère les vidéos du téléphone vers le PC, puis dépose-les ici : "
                       "l'analyse démarre toute seule. Je te préviens quand c'est fini."))
    steps.append(_step("debrief", "debrief", "Débrief et une seule modification",
                       "Les analyses sont terminées. Voici le débrief."))
    steps.append(_step("fin", "fin", "Fin de séance",
                       "Séance terminée. Roule deux ou trois sorties avec ce réglage, note tes ressentis dans « Santé et ressentis », "
                       "puis lance une séance de vérification."))

    if not micro:  # sans micro : on avance aux boutons ou à la barre d'espace
        for st in steps:
            for a, b in NO_MIC:
                st["dire"] = st["dire"].replace(a, b)
    return {
        "type": kind, "titre": titre, "raisons": reasons, "vues": views, "puissance_w": power, "cadence": "85–95 tr/min",
        "echauffement_min": warmup, "changements": f["changements"],
        "derniere_seance_id": f["derniere_seance"].id if f["derniere_seance"] else None,
        "etapes": steps, "ia": None,
        "equipement": {"pastilles_vertes": green, "trainer": trainer, "capteur_puissance": meter, "micro": micro, "mire_seule": chart_only},
    }


NO_MIC = [("Dis « c'est fait » ou « suivant » pour avancer, « répète » pour réécouter, et pose-moi une question quand tu veux.", "Appuie sur « Suivant » ou sur la barre d'espace pour avancer."), ("Dis « c'est fait » ou « suivant » pour avancer, et pose-moi une question quand tu veux.", "Appuie sur « Suivant » ou sur la barre d'espace pour avancer."), ('Je te guide étape par étape : ', 'Je te guide étape par étape. '), ("dis « c'est fait »", "appuie sur la barre d'espace"), ("Dis « c'est fait »", "Appuie sur la barre d'espace"), ("Dis « c'est parti »", "Appuie sur « C'est parti »"), (" ; « pause » si tu dois t'arrêter", ''), (', puis dis « suivant »', ', puis passe à la suite'), ('Sinon, dis « suivant ».', 'Sinon, passe à la suite.')]


# ----------------------------------------------------------------- adaptation par l'IA
ADAPT = """Tu prépares une séance de capture guidée par la voix (bike fit à la maison). Tu reçois les DONNÉES de la personne et
le PLAN proposé par l'application. Tu peux l'adapter, dans ces limites strictes :
- "vues" : sous-ensemble ordonné de ["profil_D", "profil_G", "face", "dos"], avec au moins un profil. Pour une
  vérification après un réglage, garde les mêmes vues qu'avant ;
- "puissance_w" : entier entre 80 et 400 (garde la même qu'à la séance précédente pour une vérification) ;
- "echauffement_min" : entier entre 5 et 20 ;
- "intro" : 3 à 5 phrases à dire à voix haute pour ouvrir la séance (tutoiement, sans markdown) : pourquoi cette séance,
  ce qu'on va surveiller, en t'appuyant sur les données (douleurs, verdicts, changement en cours) ;
- "conseils" : au plus 4 entrées {"id d'étape": "une phrase à ajouter à cette étape"} (ids d'étape du PLAN), sur la qualité
  de la prise (pastilles, cadrage, régularité, puissance stable) ; ne demande jamais de modifier sa façon de pédaler ;
- "pourquoi" : une phrase qui résume tes adaptations (ou « aucune adaptation »).
Réponds UNIQUEMENT par un objet JSON avec ces clés, sans texte autour."""


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("pas d'objet JSON dans la réponse")
    obj = json.loads(text[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("réponse inattendue")
    return obj


def validate_adaptation(obj: dict, plan: dict) -> tuple[dict, dict]:
    """Garde uniquement ce qui respecte les limites. Renvoie (override du plan, textes)."""
    override: dict[str, Any] = {}
    vues = obj.get("vues")
    if isinstance(vues, list):
        vues = [v for v in dict.fromkeys(vues) if v in VIEWS]
        if any(v.startswith("profil") for v in vues):
            override["vues"] = vues
    if plan["type"] == "verification":
        override.pop("vues", None)  # comparabilité avant / après
    for key, lo, hi in (("puissance_w", 80, 400), ("echauffement_min", 5, 20)):
        v = obj.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            override[key] = int(min(hi, max(lo, round(v))))
    if plan["type"] == "verification":
        override.pop("puissance_w", None)
    texts: dict[str, Any] = {}
    if isinstance(obj.get("intro"), str) and obj["intro"].strip():
        texts["intro"] = obj["intro"].strip()[:900]
    if isinstance(obj.get("pourquoi"), str):
        texts["pourquoi"] = obj["pourquoi"].strip()[:300]
    cons = obj.get("conseils")
    if isinstance(cons, dict):
        texts["conseils"] = {str(k): str(v).strip()[:300] for k, v in list(cons.items())[:4] if isinstance(v, str) and v.strip()}
    return override, texts


def adapt(db: DB) -> dict:
    """Plan adapté par le modèle choisi dans les réglages ; repli sur le plan de l'application en cas d'échec."""
    from posturale.ai import context, providers, settings

    plan = build(db)
    s = settings.load()
    pid = s["fournisseur"]
    p = providers.BY_ID.get(pid)
    meta = {"fournisseur": p.nom if p else pid, "modele": s["modeles"].get(pid, ""), "local": bool(p and providers.is_local(p, s))}
    public_plan = {k: plan[k] for k in ("type", "vues", "puissance_w", "echauffement_min", "changements", "raisons")}
    public_plan["etapes"] = [{"id": st["id"], "titre": st["titre"]} for st in plan["etapes"]]
    user = (context.as_text(context.build(db)) + "\n\nPLAN (JSON) :\n" + json.dumps(public_plan, ensure_ascii=False, default=str)
            + "\n\nAdapte ce plan.")
    try:
        if not p:
            raise providers.AIError("Fournisseur inconnu")
        text = "".join(providers.stream_chat(p, s, settings.get_key(pid, s), meta["modele"], context.SYSTEM + "\n\n" + ADAPT,
                                             [{"role": "user", "content": user}], max_tokens=1500, timeout=120))
        override, texts = validate_adaptation(_extract_json(text), plan)
    except (providers.AIError, ValueError) as exc:
        plan["ia"] = {**meta, "ok": False, "message": str(exc)}
        return plan
    adapted = build(db, override)
    ids = {st["id"] for st in adapted["etapes"]}
    for st in adapted["etapes"]:
        if st["id"] == "accueil" and texts.get("intro"):
            st["dire"] = texts["intro"] + " Dis « c'est fait » ou « suivant » pour avancer, et « répète » pour réécouter."
        if st["id"] in texts.get("conseils", {}):
            st["conseil_ia"] = texts["conseils"][st["id"]]
    adapted["ia"] = {**meta, "ok": True, "pourquoi": texts.get("pourquoi", ""),
                     "conseils_ignores": [k for k in texts.get("conseils", {}) if k not in ids]}
    return adapted
