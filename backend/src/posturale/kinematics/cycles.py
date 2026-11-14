"""Découpage en cycles de pédalage à partir de l'angle de manivelle."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Cycle:
    start: int  # index de la première image (passage au PMH)
    stop: int   # index exclusif (passage suivant au PMH)

    @property
    def length(self) -> int:
        return self.stop - self.start


def unwrap_crank(theta_deg: np.ndarray) -> np.ndarray:
    """Angle de manivelle cumulé (degrés, croissant), NaN conservés."""
    theta = np.asarray(theta_deg, dtype=float)
    out = np.full_like(theta, np.nan)
    valid = ~np.isnan(theta)
    if valid.sum() < 2:
        return out
    out[valid] = np.degrees(np.unwrap(np.radians(theta[valid])))
    if np.nanmedian(np.diff(out[valid])) < 0:  # sens de rotation inversé (repère mal orienté)
        out = -out
    return out


def detect_cycles(theta_deg: np.ndarray) -> list[Cycle]:
    """Un cycle commence à chaque passage de la manivelle par 0° (PMH)."""
    cum = unwrap_crank(theta_deg)
    valid = np.flatnonzero(~np.isnan(cum))
    if len(valid) < 2:
        return []
    turns = np.floor(cum[valid] / 360.0)
    crossings = valid[1:][np.diff(turns) > 0]
    return [Cycle(int(a), int(b)) for a, b in zip(crossings[:-1], crossings[1:])]


def reject_cycles(
    cycles: list[Cycle],
    missing: np.ndarray,
    cadence_tolerance_pct: float,
    max_missing_pct: float,
) -> tuple[list[Cycle], list[tuple[Cycle, str]]]:
    """Rejette les cycles de durée anormale (vs médiane) ou avec trop de points manquants.

    missing : booléen (n,) — True si un repère nécessaire manque sur l'image.
    Retourne (cycles gardés, [(cycle rejeté, raison)]).
    """
    if not cycles:
        return [], []
    median = float(np.median([c.length for c in cycles]))
    kept, rejected = [], []
    for c in cycles:
        if abs(c.length - median) > median * cadence_tolerance_pct / 100.0:
            rejected.append((c, "cadence"))
        elif 100.0 * np.mean(missing[c.start : c.stop]) > max_missing_pct:
            rejected.append((c, "points_manquants"))
        else:
            kept.append(c)
    return kept, rejected


def value_at_crank(series: np.ndarray, theta_deg: np.ndarray, cycle: Cycle, target_deg: float) -> float:
    """Valeur interpolée d'une série au moment où la manivelle passe par target_deg dans ce cycle."""
    sl = slice(cycle.start, cycle.stop)
    cum = unwrap_crank(theta_deg)[sl]
    cum = cum - np.floor(cum[0] / 360.0) * 360.0  # 0–360 environ dans ce cycle
    y = np.asarray(series, float)[sl]
    ok = ~np.isnan(cum) & ~np.isnan(y)
    if ok.sum() < 2 or not (cum[ok][0] <= target_deg <= cum[ok][-1]):
        return float("nan")
    return float(np.interp(target_deg, cum[ok], y[ok]))


def normalize_cycle(series: np.ndarray, theta_deg: np.ndarray, cycle: Cycle, step_deg: float = 1.0) -> np.ndarray:
    """Ré-échantillonne un cycle sur 0–360° de manivelle (pour superposer les cycles et comparer avant/après)."""
    grid = np.arange(0.0, 360.0, step_deg)
    return np.array([value_at_crank(series, theta_deg, cycle, g) for g in grid])
