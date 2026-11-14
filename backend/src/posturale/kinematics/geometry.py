"""Géométrie dans le plan du vélo.

Repère commun à tout le code d'analyse (« plan du vélo ») :
    x vers l'AVANT du vélo, y vers le HAUT, unités en mm.
Les points image (pixels, y vers le bas) y sont ramenés par `image_to_bike`
(échelle simple au lot 2, homographie de la mire au lot 3).

Conventions (config/metrics.yaml) :
    - angles articulaires en FLEXION, 0° = segment aligné ;
    - manivelle : 0° = haut (PMH), 90° = avant, 180° = bas (PMB), croissant dans le sens du pédalage.
"""
from __future__ import annotations

import numpy as np

Array = np.ndarray


def image_to_bike(points_px: Array, mm_per_px: float, forward: str = "right", origin_px=(0.0, 0.0)) -> Array:
    """Pixels (..., 2) → plan du vélo en mm.

    forward : côté de l'image vers lequel pointe l'avant du vélo
              ("right" quand on filme le côté droit du cycliste, "left" pour le côté gauche).
    """
    pts = np.asarray(points_px, dtype=float) - np.asarray(origin_px, dtype=float)
    sign = 1.0 if forward == "right" else -1.0
    out = np.empty_like(pts)
    out[..., 0] = sign * pts[..., 0] * mm_per_px
    out[..., 1] = -pts[..., 1] * mm_per_px
    return out


def segment_angle(a: Array, b: Array, c: Array) -> Array:
    """Angle intérieur en b (degrés) entre les segments b→a et b→c. Fonctionne sur des séries (..., 2)."""
    v1 = np.asarray(a, float) - np.asarray(b, float)
    v2 = np.asarray(c, float) - np.asarray(b, float)
    dot = np.sum(v1 * v2, axis=-1)
    norm = np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos = np.clip(dot / norm, -1.0, 1.0)
    return np.degrees(np.arccos(cos))


def flexion(a: Array, b: Array, c: Array) -> Array:
    """Flexion articulaire en b : 180° − angle intérieur (0° = segments alignés)."""
    return 180.0 - segment_angle(a, b, c)


def crank_angle(bb: Array, pedal: Array) -> Array:
    """Angle de manivelle (degrés, 0–360) à partir de l'axe de pédalier et de l'axe de pédale."""
    r = np.asarray(pedal, float) - np.asarray(bb, float)
    return np.degrees(np.arctan2(r[..., 0], r[..., 1])) % 360.0


def angle_vs_horizontal(a: Array, b: Array) -> Array:
    """Inclinaison du segment a→b par rapport à l'horizontale (degrés, positif si b plus haut que a)."""
    d = np.asarray(b, float) - np.asarray(a, float)
    return np.degrees(np.arctan2(d[..., 1], np.abs(d[..., 0])))
