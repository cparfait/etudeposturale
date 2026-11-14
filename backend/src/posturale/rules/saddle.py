"""Verdict sur la hauteur de selle et correction en millimètres (docs/03_specification.md § 6).

Principe : en bas du coup de pédale, la distance hanche → cheville fixe la flexion du genou
(triangle cuisse / jambe). Monter la selle de Δh déplace la hanche le long du tube de selle.
On cherche Δh qui amène la flexion à la cible, à position de cheville inchangée.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from posturale.config import load_metrics


@dataclass
class SaddleVerdict:
    jambe: str
    flexion_moyenne: float
    flexion_ecart_type: float
    plage_min: float
    plage_max: float
    statut: str                 # dans_la_plage | trop_tendu | trop_plie | indetermine
    cible: float | None
    correction_mm: float        # > 0 : monter la selle ; < 0 : la baisser ; plafonnée
    correction_brute_mm: float  # avant plafonnement
    incertitude_mm: float       # effet d'un écart-type de flexion
    plafonnee: bool
    message: str
    hypotheses: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def hip_ankle_distance(thigh: float, shank: float, flexion_deg: float) -> float:
    """Distance hanche → cheville pour une flexion du genou donnée (loi des cosinus)."""
    return math.sqrt(thigh**2 + shank**2 + 2 * thigh * shank * math.cos(math.radians(flexion_deg)))


def flexion_from_distance(thigh: float, shank: float, distance: float) -> float:
    cos = (distance**2 - thigh**2 - shank**2) / (2 * thigh * shank)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def saddle_delta_mm(
    hip: np.ndarray, ankle: np.ndarray, thigh: float, shank: float, target_flexion: float, seat_tube_deg: float
) -> float:
    """Déplacement de selle (mm, le long du tube) qui donne la flexion cible au PMB.

    hip, ankle : positions (x avant, y haut) en mm au PMB. Le tube de selle monte vers l'arrière.
    """
    u = np.array([-math.cos(math.radians(seat_tube_deg)), math.sin(math.radians(seat_tube_deg))])
    v = np.asarray(hip, float) - np.asarray(ankle, float)
    d_target = hip_ankle_distance(thigh, shank, target_flexion)
    b = float(u @ v)
    disc = b * b - float(v @ v) + d_target**2
    if disc < 0:
        return float("nan")
    roots = (-b + math.sqrt(disc), -b - math.sqrt(disc))
    return min(roots, key=abs)


def saddle_verdict(
    jambe: str,
    mean_flexion: float,
    sd_flexion: float,
    hip_bdc: np.ndarray,
    ankle_bdc: np.ndarray,
    thigh: float,
    shank: float,
    seat_tube_deg: float | None = None,
    context: str = "dynamique",
) -> SaddleVerdict:
    cfg = load_metrics()
    plage = cfg["metrics"]["P1"]["plage"][context]
    lo, hi = float(plage["min"]), float(plage["max"])
    corr_cfg = cfg["correction_selle"]
    sta = seat_tube_deg or corr_cfg["angle_tube_selle_defaut_deg"]
    step = float(corr_cfg["pas_max_mm"])
    hypotheses = []
    if seat_tube_deg is None:
        hypotheses.append(f"Angle du tube de selle par défaut ({sta}°) : à renseigner dans « Mon vélo ».")
    hypotheses.append("Cheville supposée inchangée après réglage (le pied peut compenser).")

    if math.isnan(mean_flexion):
        return SaddleVerdict(jambe, mean_flexion, sd_flexion, lo, hi, "indetermine", None, 0.0, 0.0, 0.0, False,
                             "Mesure impossible : pas assez de cycles valides.", hypotheses)

    if lo <= mean_flexion <= hi:
        statut, cible = "dans_la_plage", None
    else:
        statut = "trop_tendu" if mean_flexion < lo else "trop_plie"
        cible = (lo + hi) / 2 if corr_cfg["cible"] == "milieu_plage" else (lo if mean_flexion < lo else hi)

    raw = 0.0 if cible is None else saddle_delta_mm(hip_bdc, ankle_bdc, thigh, shank, cible, sta)
    capped = max(-step, min(step, raw)) if not math.isnan(raw) else 0.0
    # Incertitude : effet d'un écart-type de flexion sur la hauteur
    if not math.isnan(sd_flexion) and sd_flexion > 0:
        d_lo = saddle_delta_mm(hip_bdc, ankle_bdc, thigh, shank, mean_flexion - sd_flexion, sta)
        d_hi = saddle_delta_mm(hip_bdc, ankle_bdc, thigh, shank, mean_flexion + sd_flexion, sta)
        unc = abs(d_lo - d_hi) / 2
    else:
        unc = float("nan")

    interp = cfg["metrics"]["P1"]["interpretation"]
    if statut == "dans_la_plage":
        msg = f"Flexion du genou en bas du coup de pédale dans la plage indicative ({lo:g}–{hi:g}°)."
    else:
        sens = "monter" if capped > 0 else "baisser"
        msg = (interp["sous_min"] if statut == "trop_tendu" else interp["sur_max"]) + (
            f" Essai proposé : {sens} la selle de {abs(capped):.0f} mm, puis nouvelle capture."
        )
    return SaddleVerdict(jambe, round(mean_flexion, 1), round(sd_flexion, 1), lo, hi, statut, cible,
                         round(capped, 1), round(raw, 1), round(unc, 1),
                         abs(raw) > step, msg, hypotheses)
