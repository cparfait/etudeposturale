"""Détection des pastilles colorées (une couleur pour le corps, une pour le vélo) et repérage pédalier / pédale.

Les clés internes restent « vert » (corps) et « orange » (vélo) ; les vraies couleurs dépendent du jeu choisi
(vert + orange, ou bleu + rose en bande de kiné). Ronds ou petits carrés : les deux passent le test de compacité.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ColorRange:
    lo: tuple[int, int, int]  # HSV OpenCV (H 0–179) ; lo[0] > hi[0] = teinte qui passe par le rouge (179 → 0)
    hi: tuple[int, int, int]

    def as_dict(self) -> dict:
        return {"lo": list(self.lo), "hi": list(self.hi)}

    @classmethod
    def from_dict(cls, d: dict) -> "ColorRange":
        lo, hi = [int(v) for v in d["lo"]], [int(v) for v in d["hi"]]
        if len(lo) != 3 or len(hi) != 3:
            raise ValueError("Plage HSV : trois valeurs attendues (teinte, saturation, valeur)")
        lims = (179, 255, 255)
        for k in range(3):
            lo[k], hi[k] = min(max(lo[k], 0), lims[k]), min(max(hi[k], 0), lims[k])
        for k in (1, 2):
            if lo[k] > hi[k]:
                raise ValueError("Plage HSV : minimum supérieur au maximum")
        return cls(tuple(lo), tuple(hi))


GREEN = ColorRange((33, 90, 90), (85, 255, 255))
ORANGE = ColorRange((4, 120, 120), (22, 255, 255))
DEFAULTS = {"vert": GREEN, "orange": ORANGE}
BLUE = ColorRange((92, 80, 50), (130, 255, 255))     # bande de kiné bleue (du cyan au bleu roi)
PINK = ColorRange((143, 60, 90), (172, 255, 255))    # rose / magenta, sans déborder sur le rouge (173–179)

# Jeux de couleurs : plages HSV + noms (accordés) + teinte d'affichage
PRESETS: dict[str, dict] = {
    "vert_orange": {"nom": "Vert + orange", "plages": {"vert": GREEN, "orange": ORANGE},
                    "noms": {"corps": "vertes", "corps1": "verte", "velo": "orange", "velo1": "orange",
                             "teinte_corps": "#a3e635", "teinte_velo": "#f97316"}},
    "bleu_rose": {"nom": "Bleu + rose (bande de kiné)", "plages": {"vert": BLUE, "orange": PINK},
                  "noms": {"corps": "bleues", "corps1": "bleue", "velo": "roses", "velo1": "rose",
                           "teinte_corps": "#3b82f6", "teinte_velo": "#ec4899"}},
}


def _colors_file():
    from posturale.config import data_dir

    return data_dir() / "marker_colors.json"


def _saved() -> dict:
    f = _colors_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (ValueError, OSError):
        return {}


def current_preset() -> str:
    p = _saved().get("preset")
    return p if p in PRESETS or p == "perso" else "vert_orange"


# Noms de couleur selon la teinte OpenCV (0–179) : (fin de plage, féminin pluriel, féminin singulier)
_HUES = [(4, "rouges", "rouge"), (20, "orange", "orange"), (33, "jaunes", "jaune"), (85, "vertes", "verte"),
         (100, "turquoise", "turquoise"), (130, "bleues", "bleue"), (145, "violettes", "violette"),
         (171, "roses", "rose"), (179, "rouges", "rouge")]


def hue_center(r: ColorRange) -> float:
    lo, hi = r.lo[0], r.hi[0]
    return ((lo + hi) / 2) if lo <= hi else (((lo + hi + 180) / 2) % 180)


def color_name(r: ColorRange) -> tuple[str, str]:
    h = hue_center(r)
    for end, pl, sg in _HUES:
        if h <= end:
            return pl, sg
    return "rouges", "rouge"


def _hex(r: ColorRange) -> str:
    h = hue_center(r)
    s_, v_ = max(r.lo[1], 150), 230
    bgr = cv2.cvtColor(np.uint8([[[round(h), s_, v_]]]), cv2.COLOR_HSV2BGR)[0][0]
    return "#{:02x}{:02x}{:02x}".format(int(bgr[2]), int(bgr[1]), int(bgr[0]))


def hue_gap(a: ColorRange, b: ColorRange) -> float:
    d = abs(hue_center(a) - hue_center(b)) % 180
    return min(d, 180 - d)


def sticker_names(ranges: dict[str, "ColorRange"] | None = None) -> dict[str, str]:
    """Noms tirés des couleurs étalonnées (« pastilles bleues », « pastille rose »…), pour tous les textes."""
    if ranges is None and not is_calibrated():  # couleurs pas encore choisies : noms neutres
        r = current_ranges()
        return {"corps": "« corps »", "corps1": "« corps »", "velo": "« vélo »", "velo1": "« vélo »",
                "teinte_corps": _hex(r["vert"]), "teinte_velo": _hex(r["orange"])}
    r = ranges or current_ranges()
    c_pl, c_sg = color_name(r["vert"])
    v_pl, v_sg = color_name(r["orange"])
    return {"corps": c_pl, "corps1": c_sg, "velo": v_pl, "velo1": v_sg, "teinte_corps": _hex(r["vert"]), "teinte_velo": _hex(r["orange"])}


def is_calibrated() -> bool:
    """Couleurs étalonnées sur une photo, ou jeu de couleurs choisi explicitement."""
    return "preset" in _saved()


def apply_preset(pid: str) -> None:
    if pid not in PRESETS:
        raise ValueError("Jeu de couleurs inconnu")
    save_ranges(dict(PRESETS[pid]["plages"]), preset=pid)


def current_ranges() -> dict[str, ColorRange]:
    """Plages réglées dans l'app (data/marker_colors.json), sinon les valeurs par défaut."""
    out = dict(PRESETS.get(current_preset(), PRESETS["vert_orange"])["plages"])
    f = _colors_file()
    if f.exists():
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
            for k in DEFAULTS:
                if k in saved:
                    out[k] = ColorRange.from_dict(saved[k])
        except (ValueError, KeyError, TypeError):
            pass  # fichier abîmé : on retombe sur les valeurs par défaut
    return out


def save_ranges(ranges: dict[str, ColorRange], preset: str | None = None) -> None:
    data = {k: v.as_dict() for k, v in ranges.items()}
    data["preset"] = preset or "perso"   # étalonnage sur une photo : couleurs propres à la personne
    _colors_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def reset_ranges() -> None:
    """Revient aux plages par défaut du jeu de couleurs choisi."""
    pid = _saved().get("preset")
    _colors_file().unlink(missing_ok=True)
    if pid in PRESETS and pid != "vert_orange":
        apply_preset(pid)


def color_mask(frame_bgr: np.ndarray, color: ColorRange) -> np.ndarray:
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    (h0, s0, v0), (h1, s1, v1) = color.lo, color.hi
    if h0 <= h1:
        mask = cv2.inRange(hsv, np.array([h0, s0, v0]), np.array([h1, s1, v1]))
    else:
        mask = cv2.inRange(hsv, np.array([h0, s0, v0]), np.array([179, s1, v1])) | cv2.inRange(
            hsv, np.array([0, s0, v0]), np.array([h1, s1, v1]))
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def detect_blobs(frame_bgr: np.ndarray, color: ColorRange, min_area: float = 12, max_area: float | None = None,
                 min_circularity: float = 0.55) -> np.ndarray:
    """Centres (n, 2) des taches de la couleur demandée, à peu près rondes."""
    mask = color_mask(frame_bgr, color)
    if max_area is None:
        max_area = frame_bgr.shape[0] * frame_bgr.shape[1] * 0.002
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        area = cv2.contourArea(c)
        if not (min_area <= area <= max_area):
            continue
        perim = cv2.arcLength(c, True) or 1.0
        if 4 * np.pi * area / perim**2 < min_circularity:
            continue
        m = cv2.moments(c)
        out.append((m["m10"] / m["m00"], m["m01"] / m["m00"]))
    return np.array(out, dtype=float).reshape(-1, 2)


def locate_bb(orange_per_frame: list[np.ndarray], bin_px: float = 8.0) -> np.ndarray | None:
    """Axe de pédalier = pastille orange immobile : densité maximale des détections sur toute la prise."""
    pts = [p for p in orange_per_frame if len(p)]
    if not pts:
        return None
    allp = np.vstack(pts)
    keys = np.floor(allp / bin_px).astype(int)
    uniq, counts = np.unique(keys, axis=0, return_counts=True)
    best = uniq[np.argmax(counts)]
    near = np.all(np.abs(np.floor(allp / bin_px) - best) <= 1, axis=1)
    if near.sum() < 0.3 * len(pts):  # pas vu sur assez d'images
        return None
    return np.median(allp[near], axis=0)


def pedal_track(orange_per_frame: list[np.ndarray], bb: np.ndarray, min_r_px: float = 10.0) -> np.ndarray:
    """Pastille d'axe de pédale par image : la tache orange qui n'est pas le pédalier, à distance de manivelle."""
    radii = [np.linalg.norm(p - bb, axis=1) for p in orange_per_frame if len(p)]
    cand = np.concatenate(radii) if radii else np.array([])
    cand = cand[cand > min_r_px]
    out = np.full((len(orange_per_frame), 2), np.nan)
    if len(cand) == 0:
        return out
    r_med = np.median(cand)
    for i, p in enumerate(orange_per_frame):
        if not len(p):
            continue
        r = np.linalg.norm(p - bb, axis=1)
        ok = (r > 0.6 * r_med) & (r < 1.4 * r_med)
        if ok.any():
            out[i] = p[ok][np.argmin(np.abs(r[ok] - r_med))]
    return out


def fit_circle(points: np.ndarray) -> tuple[np.ndarray, float] | None:
    """Cercle des moindres carrés (secours : axe de pédalier à partir de la trajectoire de la cheville)."""
    p = points[~np.isnan(points).any(axis=1)]
    if len(p) < 10:
        return None
    A = np.c_[2 * p, np.ones(len(p))]
    b = (p**2).sum(axis=1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:2]
    return c, float(np.sqrt(sol[2] + c @ c))
