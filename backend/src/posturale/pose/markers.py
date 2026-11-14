"""Détection des pastilles colorées (vert fluo = corps, orange = vélo) et repérage pédalier / pédale."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ColorRange:
    lo: tuple[int, int, int]  # HSV OpenCV (H 0–179)
    hi: tuple[int, int, int]


GREEN = ColorRange((33, 90, 90), (85, 255, 255))
ORANGE = ColorRange((4, 120, 120), (22, 255, 255))


def detect_blobs(frame_bgr: np.ndarray, color: ColorRange, min_area: float = 12, max_area: float | None = None,
                 min_circularity: float = 0.55) -> np.ndarray:
    """Centres (n, 2) des taches de la couleur demandée, à peu près rondes."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(color.lo), np.array(color.hi))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
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
