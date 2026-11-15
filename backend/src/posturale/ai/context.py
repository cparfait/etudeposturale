"""Ce que le coach reçoit : un résumé texte des données (jamais la vidéo) et, si autorisé, des images clés annotées."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlmodel import Session as DB, select

from posturale import equipment
from posturale.config import load_metrics
from posturale.storage.models import Analysis, Bike, Capture, Profile

SYSTEM = """Tu es le coach de l'application « Étude posturale vélo », un outil local de bike fit utilisé seul à la maison
(home trainer, téléphone, pastilles colorées). Tu parles français et tu tutoies.

Règles :
1. Tu t'appuies uniquement sur le bloc DONNÉES. Tu n'inventes aucun chiffre. Si une donnée manque, dis-le et indique
   comment l'obtenir (séance de capture, auto-test, saisie du profil ou du vélo).
2. Les mesures, verdicts et hypothèses viennent du moteur de l'application (règles sourcées). Tu les expliques et tu peux
   les nuancer (qualité de la mesure, cohérence entre côtés), mais tu ne contredis jamais une alerte santé.
3. Une seule modification à la fois : laquelle, de combien (mm), comment la faire concrètement, comment la vérifier
   (rouler 2–3 sorties, refaire une séance), avant d'en envisager une autre.
4. Douleur forte (≥ 7/10), douleur au repos ou la nuit, gonflement, engourdissement, blessure : recommande de consulter
   un professionnel de santé avant tout réglage. Tu n'es ni médecin ni kinésithérapeute.
5. Les plages de référence sont indicatives : le confort et l'absence de douleur priment.
6. Réponses claires et concrètes, sans jargon inutile."""

VOCAL = """Mode vocal : ta réponse est lue à voix haute pendant que la personne pédale. 2 à 4 phrases courtes, sans markdown,
sans liste, sans symbole ; nombres simples (« quatre millimètres »)."""

IMAGES = """Des images de la vidéo sont jointes, avec le squelette détecté (lignes) : vue 2D de profil, angles projetés.
Décris ce que tu observes avec prudence et rapproche-le des mesures ; ne déduis pas d'angle précis à l'œil."""

KEYS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"]
SKELETON = [("acromion", "trochanter"), ("trochanter", "epicondyle_femoral"), ("epicondyle_femoral", "malleole"),
            ("malleole", "talon"), ("talon", "metatarse5"), ("malleole", "metatarse5"),
            ("acromion", "epicondyle_humeral"), ("epicondyle_humeral", "styloide_ulnaire")]


def _r(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 1)
    if isinstance(v, dict):
        return {k: _r(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [_r(x) for x in v]
    return v


def _clean(d: dict | None, drop: tuple[str, ...] = ("id", "updated_at", "created_at", "notes")) -> dict | None:
    if not d:
        return None
    return {k: v for k, v in d.items() if k not in drop and v not in (None, "", [])}


def _profile_summary(res: dict, metrics: dict) -> dict:
    out: dict[str, Any] = {"echelle": res.get("echelle", {}).get("source"), "verdict_selle": res.get("verdict_selle"),
                           "qualite": res.get("qualite"), "segments_mm": res.get("segments_mm")}
    m = {}
    for k in KEYS:
        v = res.get("metriques", {}).get(k)
        if not v:
            continue
        ref = metrics.get(k, {})
        plage = (ref.get("plage") or {}).get("dynamique") or (ref.get("plage") or {}).get("descriptif")
        m[k] = {"nom": ref.get("nom"), "moyenne": v.get("moyenne"), "ecart_type": v.get("ecart_type"),
                "unite": ref.get("unite"), "plage_indicative": plage}
    out["mesures"] = m
    return out


def build(db: DB) -> dict[str, Any]:
    """Données envoyées au coach (dict lisible, sans vidéo)."""
    from posturale.api.routes_health import _context  # évite un import circulaire au chargement
    from posturale.health.rules import evaluate

    ctx, latest = _context(db)
    metrics = load_metrics()["metrics"]
    profile, bike = db.get(Profile, 1), db.get(Bike, 1)
    data = {
        "profil": _clean(profile.model_dump() if profile else None),
        "velo": _clean(bike.model_dump() if bike else None),
        "configuration_actuelle": _clean(ctx.config, ("id", "bike_id", "created_at")),
        "analyses_profil": {("gauche" if s == "G" else "droite"): _profile_summary(r, metrics) for s, r in latest["profil"].items()},
        "vue_de_face": (latest["face"] or {}).get("metriques"),
        "vue_de_dos": (latest["dos"] or {}).get("metriques"),
        "douleurs_actives": [_clean(d, ("id", "created_at", "active")) for d in ctx.douleurs],
        "auto_tests": [_clean(t, ("id", "created_at")) for t in ctx.tests],
        "ressentis_recents": [_clean(f, ("id",)) for f in ctx.ressentis[-3:]],
        "fichier_fit": {k: (ctx.fit or {}).get(k) for k in ("duree_min", "global", "par_heure")} if ctx.fit else None,
        "equipement": equipment.summary_for_ai(),
        "hypotheses_du_moteur": [{k: h.get(k) for k in ("titre", "categorie", "priorite", "hypothese", "action", "constats", "fiabilite")} for h in evaluate(ctx)],
    }
    return _r({k: v for k, v in data.items() if v not in (None, {}, [])})


def as_text(data: dict) -> str:
    return "DONNÉES (JSON, générées par l'application) :\n" + json.dumps(data, ensure_ascii=False, indent=1, default=str)


GUIDE = """Séance guidée en cours : tu pilotes la séance de capture pas à pas, à la voix. La personne est sur le vélo
ou en train de s'installer. Réponds à sa question en lien avec l'étape en cours, puis rappelle ce qu'il faut faire pour
avancer. Ne propose jamais de modification du vélo pendant la séance : la seule modification est celle du débrief,
indiquée dans « modification » ; tu l'expliques sans en proposer d'autre."""


def system_prompt(vocal: bool, with_images: bool, seance: str = "") -> str:
    parts = [SYSTEM] + ([VOCAL] if vocal else []) + ([IMAGES] if with_images else [])
    if seance:
        parts += [GUIDE, "SÉANCE GUIDÉE (JSON) :\n" + seance]
    return "\n\n".join(parts)


# ----------------------------------------------------------------- images clés
def _frame_at(path: str, t: float) -> np.ndarray | None:
    cap = cv2.VideoCapture(path)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
        ok, img = cap.read()
    finally:
        cap.release()
    return img if ok else None


def _draw(img: np.ndarray, reperes: dict[str, list], i: int) -> np.ndarray:
    out = img.copy()
    pts = {}
    for k, track in reperes.items():
        if i < len(track) and track[i] and track[i][0] is not None:
            pts[k] = (int(track[i][0]), int(track[i][1]))
    w = max(2, img.shape[1] // 400)
    for a, b in SKELETON:
        if a in pts and b in pts:
            cv2.line(out, pts[a], pts[b], (60, 230, 160), w, cv2.LINE_AA)
    for p in pts.values():
        cv2.circle(out, p, w * 3, (255, 255, 255), -1, cv2.LINE_AA)
    return out


def _jpeg(img: np.ndarray, max_side: int = 1024) -> str:
    h, w = img.shape[:2]
    k = min(1.0, max_side / max(h, w))
    if k < 1:
        img = cv2.resize(img, (round(w * k), round(h * k)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return base64.b64encode(buf.tobytes()).decode()


def key_images(db: DB, limit_sides: int = 2) -> list[dict]:
    """Par côté filmé : extension maximale (bas du coup de pédale) et flexion maximale (haut), squelette dessiné."""
    out: list[dict] = []
    seen: set[str] = set()
    rows = db.exec(select(Analysis, Capture).where(Analysis.capture_id == Capture.id, Analysis.status == "terminee",
                                                   Capture.vue == "profil").order_by(Analysis.id.desc()))
    for a, c in rows:
        side = (a.summary or {}).get("cote")
        if not side or side in seen or not a.result_path or not Path(a.result_path).exists() or not Path(c.path).exists():
            continue
        seen.add(side)
        ov = json.loads(Path(a.result_path).read_text(encoding="utf-8")).get("overlay") or {}
        knee = np.array([np.nan if v is None else v for v in ov.get("genou_flexion", [])], dtype=float)
        times = ov.get("temps", [])
        if not len(knee) or np.all(np.isnan(knee)):
            continue
        label_side = "gauche" if side == "G" else "droit"
        for label, idx in ((f"Côté {label_side} — extension maximale du genou", int(np.nanargmin(knee))),
                           (f"Côté {label_side} — flexion maximale du genou", int(np.nanargmax(knee)))):
            img = _frame_at(c.path, times[idx])
            if img is None:
                continue
            out.append({"legende": f"{label} ({knee[idx]:.0f}° de flexion mesurée)", "mime": "image/jpeg",
                        "data": _jpeg(_draw(img, ov.get("reperes", {}), idx))})
        if len(seen) >= limit_sides:
            break
    return out
