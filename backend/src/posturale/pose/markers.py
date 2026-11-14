"""Détection des pastilles colorées (vert fluo = corps, orange = vélo) et repérage pédalier / pédale."""
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


def _colors_file():
    from posturale.config import data_dir

    return data_dir() / "marker_colors.json"


def current_ranges() -> dict[str, ColorRange]:
    """Plages réglées dans l'app (data/marker_colors.json), sinon les valeurs par défaut."""
    out = dict(DEFAULTS)
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


def save_ranges(ranges: dict[str, ColorRange]) -> None:
    _colors_file().write_text(json.dumps({k: v.as_dict() for k, v in ranges.items()}, indent=2), encoding="utf-8")


def reset_ranges() -> None:
    _colors_file().unlink(missing_ok=True)


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
