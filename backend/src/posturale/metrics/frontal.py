"""Vues de face (trajectoire des genoux, F1–F3) et de dos (bassin, D1–D3).

Sans mire, les distances sont exprimées en % de la largeur de bassin mesurée (hanche G ↔ hanche D),
ce qui reste comparable d'une séance à l'autre ; avec mire, en mm.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from posturale.config import load_metrics
from posturale.kinematics.signal import fill_gaps, lowpass
from posturale.kinematics.stats import summarize


def _prep(x: np.ndarray, fps: float) -> np.ndarray:
    t = load_metrics()["traitement"]
    return lowpass(fill_gaps(x, fps, t["trou_max_interpole_ms"]), fps, t["butterworth"]["coupure_hz"], t["butterworth"]["ordre"])


def cycles_from_vertical(y: np.ndarray, fps: float, cadence_max_rpm: float = 130) -> list[tuple[int, int]]:
    """Cycles délimités par le point le plus bas du genou (y image maximal)."""
    ok = ~np.isnan(y)
    if ok.sum() < fps:
        return []
    yy = np.where(ok, y, np.nanmedian(y))
    prom = 0.3 * (np.nanpercentile(y, 95) - np.nanpercentile(y, 5))
    peaks, _ = find_peaks(yy, distance=int(fps * 60 / cadence_max_rpm), prominence=max(prom, 1e-6))
    return [(int(a), int(b)) for a, b in zip(peaks[:-1], peaks[1:])]


def front_metrics(tr: dict[str, np.ndarray], fps: float, mm_per_px: float | None = None) -> dict:
    """tr : hanche_G/D, genou_G/D, cheville_G/D en pixels (n, 2). Image vue de face."""
    p = {k: _prep(v, fps) for k, v in tr.items()}
    pelvis_w = float(np.nanmedian(np.abs(p["hanche_G"][:, 0] - p["hanche_D"][:, 0])))
    unit, scale = ("mm", mm_per_px) if mm_per_px else ("% bassin", 100.0 / pelvis_w if pelvis_w > 0 else np.nan)
    out: dict = {"unite": unit, "largeur_bassin_px": round(pelvis_w, 1), "cotes": {}}
    for s in ("G", "D"):
        knee, hip, ankle = p[f"genou_{s}"], p[f"hanche_{s}"], p[f"cheville_{s}"]
        cyc = cycles_from_vertical(knee[:, 1], fps)
        # F1 : amplitude médio-latérale du genou sur chaque cycle
        f1 = [np.nanmax(knee[a:b, 0]) - np.nanmin(knee[a:b, 0]) for a, b in cyc]
        # F2 : écart latéral moyen du genou à la droite hanche–cheville (signé : + = vers l'extérieur de l'image)
        t = np.clip(((knee - hip) * (ankle - hip)).sum(1) / (((ankle - hip) ** 2).sum(1) + 1e-9), 0, 1)
        proj = hip + t[:, None] * (ankle - hip)
        lateral = knee[:, 0] - proj[:, 0]
        if s == "G":
            lateral = -lateral  # même convention des deux côtés : + = genou vers l'extérieur
        f2 = [np.nanmean(lateral[a:b]) for a, b in cyc]
        out["cotes"][s] = {
            "F1": summarize(np.array(f1) * scale).as_dict(),
            "F2": summarize(np.array(f2) * scale).as_dict(),
            "n_cycles": len(cyc),
            "trajectoire_genou": _decimate(knee, 400),
        }
    g, d = out["cotes"]["G"]["F1"]["moyenne"], out["cotes"]["D"]["F1"]["moyenne"]
    out["F3"] = round(abs(g - d), 2) if np.isfinite(g) and np.isfinite(d) else None
    return out


def rear_metrics(tr: dict[str, np.ndarray], fps: float, mm_per_px: float | None = None) -> dict:
    """tr : hanche_G/D (ou pastilles EIPS), genou_G/D. Image vue de dos."""
    p = {k: _prep(v, fps) for k, v in tr.items()}
    hg, hd = p["hanche_G"], p["hanche_D"]
    roll = np.degrees(np.arctan2(hd[:, 1] - hg[:, 1], hd[:, 0] - hg[:, 0]))
    roll = (roll + 90) % 180 - 90  # inclinaison du bassin, ° (0 = horizontal)
    mid = (hg + hd) / 2
    pelvis_w = float(np.nanmedian(np.linalg.norm(hd - hg, axis=1)))
    unit, scale = ("mm", mm_per_px) if mm_per_px else ("% bassin", 100.0 / pelvis_w if pelvis_w > 0 else np.nan)
    knee_y = p["genou_G"][:, 1] if "genou_G" in p else hg[:, 1]
    cyc = cycles_from_vertical(knee_y, fps)
    d1 = [np.nanmax(roll[a:b]) - np.nanmin(roll[a:b]) for a, b in cyc]
    sway = [np.nanmax(mid[a:b, 0]) - np.nanmin(mid[a:b, 0]) for a, b in cyc]
    return {
        "unite": unit,
        "D1": summarize(d1).as_dict(),                    # amplitude de roulis par cycle (°)
        "D2_balancement": summarize(np.array(sway) * scale).as_dict(),
        "D3": round(float(np.nanmean(roll)), 2),          # inclinaison moyenne (°), + = côté droit plus bas sur l'image
        "n_cycles": len(cyc),
        "roulis_deg": _decimate(roll[:, None], 400),
    }


def _decimate(arr: np.ndarray, n: int) -> list:
    step = max(1, len(arr) // n)
    a = np.asarray(arr)[::step]
    return np.where(np.isnan(a), None, np.round(a, 2)).tolist()
