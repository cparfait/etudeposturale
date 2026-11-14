"""Cycliste simulé dans le plan du vélo (x avant, y haut, mm) : angles connus pour valider le noyau."""
from __future__ import annotations

import math

import numpy as np

SEAT_TUBE_DEG = 73.5
U_SEAT = np.array([-math.cos(math.radians(SEAT_TUBE_DEG)), math.sin(math.radians(SEAT_TUBE_DEG))])


def knee_position(hip: np.ndarray, ankle: np.ndarray, thigh: float, shank: float) -> np.ndarray:
    """Genou = intersection des cercles (hanche, cuisse) et (cheville, jambe), côté avant."""
    d_vec = ankle - hip
    d = np.linalg.norm(d_vec, axis=-1, keepdims=True)
    a = (thigh**2 - shank**2 + d**2) / (2 * d)
    h = np.sqrt(np.clip(thigh**2 - a**2, 0, None))
    base = hip + a * d_vec / d
    perp = np.stack([-d_vec[..., 1], d_vec[..., 0]], axis=-1) / d
    k1, k2 = base + h * perp, base - h * perp
    return np.where((k1[..., 0] > k2[..., 0])[..., None], k1, k2)


def rider(
    fps: float = 120.0,
    seconds: float = 30.0,
    cadence_rpm: float = 90.0,
    saddle_mm: float = 720.0,
    thigh: float = 460.0,
    shank: float = 470.0,
    crank: float = 175.0,
    ankle_offset=(-25.0, 85.0),
    noise_mm: float = 0.0,
    seed: int = 0,
) -> tuple[dict[str, np.ndarray], float]:
    """Trajectoires des repères. La hanche est à `saddle_mm` le long du tube de selle (+ 90 mm vertical)."""
    rng = np.random.default_rng(seed)
    n = int(fps * seconds)
    t = np.arange(n) / fps
    theta = np.radians(360.0 * cadence_rpm / 60.0 * t)
    bb = np.zeros((n, 2))
    pedal = crank * np.stack([np.sin(theta), np.cos(theta)], axis=1)
    ankle = pedal + np.asarray(ankle_offset)
    hip = np.tile(saddle_mm * U_SEAT + np.array([0.0, 90.0]), (n, 1))
    knee = knee_position(hip, ankle, thigh, shank)
    heel = ankle + np.array([-60.0, -40.0])
    meta5 = ankle + np.array([120.0, -70.0])
    acromion = np.tile(hip[0] + np.array([420.0, 380.0]), (n, 1))
    elbow = acromion + np.array([150.0, -220.0])
    wrist = elbow + np.array([230.0, -40.0])
    tracks = {
        "trochanter": hip, "epicondyle_femoral": knee, "malleole": ankle, "talon": heel, "metatarse5": meta5,
        "acromion": acromion, "epicondyle_humeral": elbow, "styloide_ulnaire": wrist,
        "axe_pedale": pedal, "axe_pedalier": bb,
    }
    if noise_mm:
        tracks = {k: v + rng.normal(0, noise_mm, v.shape) for k, v in tracks.items()}
    return tracks, fps


def true_knee_extremes(**kw) -> tuple[float, float]:
    """Flexion min et max exactes (grille très fine, sans bruit)."""
    kw = {**kw, "fps": 3600.0, "seconds": 60.0 / kw.get("cadence_rpm", 90.0), "noise_mm": 0.0}
    tr, _ = rider(**kw)
    from posturale.kinematics.geometry import flexion

    f = flexion(tr["trochanter"], tr["epicondyle_femoral"], tr["malleole"])
    return float(f.min()), float(f.max())
