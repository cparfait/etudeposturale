"""Statistiques robustes sur les valeurs par cycle."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Summary:
    mean: float
    sd: float
    n: int
    n_rejected: int

    def as_dict(self) -> dict:
        return {"moyenne": round(self.mean, 2), "ecart_type": round(self.sd, 2), "n": self.n, "n_rejetes": self.n_rejected}


def summarize(values, mad_threshold: float = 3.0) -> Summary:
    """Moyenne ± écart-type après rejet des valeurs à plus de `mad_threshold` écarts médians absolus."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return Summary(float("nan"), float("nan"), 0, 0)
    med = np.median(v)
    mad = 1.4826 * np.median(np.abs(v - med))  # ≈ écart-type pour une loi normale
    keep = np.abs(v - med) <= mad_threshold * mad if mad > 0 else np.ones_like(v, bool)
    kept = v[keep]
    sd = float(np.std(kept, ddof=1)) if len(kept) > 1 else float("nan")
    return Summary(float(np.mean(kept)), sd, int(len(kept)), int((~keep).sum()))
