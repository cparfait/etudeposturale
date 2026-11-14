"""Métriques de la vue de profil (P1–P10) à partir des trajectoires dans le plan du vélo.

Entrée : dictionnaire repère → tableau (n, 2) en mm (x avant, y haut), NaN si absent.
Repères attendus (noms de config/metrics.yaml) :
    trochanter, epicondyle_femoral, malleole, talon, metatarse5,
    acromion, epicondyle_humeral, styloide_ulnaire, axe_pedale, axe_pedalier
Seuls trochanter, epicondyle_femoral, malleole, axe_pedale et axe_pedalier sont obligatoires.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from posturale.config import load_metrics
from posturale.kinematics.cycles import Cycle, detect_cycles, reject_cycles, value_at_crank
from posturale.kinematics.geometry import angle_vs_horizontal, crank_angle, flexion, segment_angle
from posturale.kinematics.signal import fill_gaps, lowpass
from posturale.kinematics.stats import Summary, summarize

REQUIRED = ("trochanter", "epicondyle_femoral", "malleole", "axe_pedale", "axe_pedalier")


@dataclass
class ProfileAnalysis:
    fps: float
    cycles: list[Cycle]
    rejected: list[tuple[Cycle, str]]
    series: dict[str, np.ndarray]                 # séries filtrées : angles (°) et manivelle
    per_cycle: dict[str, np.ndarray]              # métrique → valeur par cycle gardé
    summary: dict[str, Summary]                   # métrique → moyenne ± écart-type
    segments_mm: dict[str, float]                 # longueurs moyennes (cuisse, jambe)
    bdc_mm: dict[str, np.ndarray] = field(default_factory=dict)  # positions moyennes au PMB (hanche, cheville)
    quality: dict[str, Any] = field(default_factory=dict)


def _prepare(tracks: dict[str, np.ndarray], fps: float, cfg: dict) -> dict[str, np.ndarray]:
    gap = cfg["traitement"]["trou_max_interpole_ms"]
    bw = cfg["traitement"]["butterworth"]
    out = {}
    for name, xy in tracks.items():
        xy = fill_gaps(np.asarray(xy, float), fps, gap)
        out[name] = lowpass(xy, fps, bw["coupure_hz"], bw["ordre"])
    return out


def analyze_profile(tracks: dict[str, np.ndarray], fps: float) -> ProfileAnalysis:
    cfg = load_metrics()
    missing_keys = [k for k in REQUIRED if k not in tracks]
    if missing_keys:
        raise ValueError(f"Repères manquants : {', '.join(missing_keys)}")

    raw_missing = np.zeros(len(tracks["trochanter"]), bool)
    for k in REQUIRED:
        raw_missing |= np.isnan(np.asarray(tracks[k], float)).any(axis=1)

    t = _prepare(tracks, fps, cfg)
    hip, knee, ankle = t["trochanter"], t["epicondyle_femoral"], t["malleole"]
    theta = crank_angle(t["axe_pedalier"], t["axe_pedale"])

    series: dict[str, np.ndarray] = {
        "manivelle": theta,
        "genou_flexion": flexion(hip, knee, ankle),
    }
    if "acromion" in t:
        series["hanche_angle"] = segment_angle(t["acromion"], hip, knee)
        series["tronc_inclinaison"] = angle_vs_horizontal(hip, t["acromion"])
    if "talon" in t and "metatarse5" in t:
        # Angle jambe / pied (intérieur, en degrés) : seule son amplitude est interprétée
        foot_vec_end = ankle + (t["metatarse5"] - t["talon"])
        series["cheville_angle"] = segment_angle(knee, ankle, foot_vec_end)
    if "epicondyle_humeral" in t and "acromion" in t:
        series["epaule_angle"] = segment_angle(hip, t["acromion"], t["epicondyle_humeral"])
        if "styloide_ulnaire" in t:
            series["coude_flexion"] = flexion(t["acromion"], t["epicondyle_humeral"], t["styloide_ulnaire"])

    trt = cfg["traitement"]
    cycles, rejected = reject_cycles(
        detect_cycles(theta), raw_missing, trt["rejet_cycle_cadence_pct"], trt["rejet_cycle_points_manquants_pct"]
    )

    per: dict[str, list[float]] = {k: [] for k in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10")}
    bdc_hip, bdc_ankle = [], []
    for c in cycles:
        sl = slice(c.start, c.stop)
        knee_f = series["genou_flexion"][sl]
        i_min = c.start + int(np.nanargmin(knee_f))
        per["P1"].append(float(np.nanmin(knee_f)))
        per["P2"].append(float(np.nanmax(knee_f)))
        per["P3"].append(per["P2"][-1] - per["P1"][-1])
        bdc_hip.append(hip[i_min])
        bdc_ankle.append(ankle[i_min])
        if "hanche_angle" in series:
            per["P4"].append(float(np.nanmin(series["hanche_angle"][sl])))
            per["P7"].append(float(np.nanmean(series["tronc_inclinaison"][sl])))
        if "cheville_angle" in series:
            a = series["cheville_angle"][sl]
            per["P5"].append(float(np.nanmax(a) - np.nanmin(a)))
        dx = knee[:, 0] - t["axe_pedale"][:, 0]
        per["P6"].append(value_at_crank(dx, theta, c, 90.0))
        if "epaule_angle" in series:
            per["P8"].append(float(np.nanmean(series["epaule_angle"][sl])))
        if "coude_flexion" in series:
            per["P9"].append(float(np.nanmean(series["coude_flexion"][sl])))
        per["P10"].append(float(np.nanmax(hip[sl, 1]) - np.nanmin(hip[sl, 1])))

    per_cycle = {k: np.array(v) for k, v in per.items() if v}
    mad = trt["rejet_aberrant_mad"]
    summary = {k: summarize(v, mad) for k, v in per_cycle.items()}

    thigh = np.linalg.norm(knee - hip, axis=1)
    shank = np.linalg.norm(ankle - knee, axis=1)
    segments = {"cuisse_mm": float(np.nanmedian(thigh)), "jambe_mm": float(np.nanmedian(shank))}
    bdc = {}
    if bdc_hip:
        bdc = {"hanche": np.nanmean(bdc_hip, axis=0), "cheville": np.nanmean(bdc_ankle, axis=0)}

    q = cfg["qualite"]
    quality = {
        "Q1_fps": fps,
        "Q1_ok": fps >= q["Q1_fps_min"],
        "Q2_visibilite_pct": round(100.0 * (1 - raw_missing.mean()), 1),
        "Q2_ok": 100.0 * (1 - raw_missing.mean()) >= q["Q2_visibilite_min_pct"],
        "Q4_cycles": len(cycles),
        "Q4_ok": len(cycles) >= q["Q4_cycles_min"],
        "Q5_ecart_type_P1": round(summary["P1"].sd, 2) if "P1" in summary else None,
        "Q5_ok": bool("P1" in summary and summary["P1"].sd <= q["Q5_ecart_type_P1_max_deg"]),
        "cycles_rejetes": len(rejected),
    }
    return ProfileAnalysis(fps, cycles, rejected, series, per_cycle, summary, segments, bdc, quality)
