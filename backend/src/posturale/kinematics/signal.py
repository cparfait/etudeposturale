"""Traitement du signal : comblement des trous courts et filtrage passe-bas à phase nulle."""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt


def fill_gaps(x: np.ndarray, fps: float, max_gap_ms: float) -> np.ndarray:
    """Interpole linéairement les trous (NaN) de durée ≤ max_gap_ms ; laisse les plus longs en NaN.

    x : (n,) ou (n, d). Les trous en début et fin de série ne sont pas extrapolés.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        return np.stack([fill_gaps(x[:, j], fps, max_gap_ms) for j in range(x.shape[1])], axis=1)
    out = x.copy()
    nan = np.isnan(x)
    if not nan.any() or nan.all():
        return out
    max_gap = int(round(max_gap_ms * fps / 1000.0))
    idx = np.arange(len(x))
    i = 0
    while i < len(x):
        if not nan[i]:
            i += 1
            continue
        j = i
        while j < len(x) and nan[j]:
            j += 1
        if i > 0 and j < len(x) and (j - i) <= max_gap:
            out[i:j] = np.interp(idx[i:j], [i - 1, j], [x[i - 1], x[j]])
        i = j
    return out


def lowpass(x: np.ndarray, fps: float, cutoff_hz: float, order: int = 4) -> np.ndarray:
    """Butterworth à phase nulle (filtfilt), appliqué par segments continus sans NaN.

    Les segments trop courts pour le filtre sont laissés tels quels.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        return np.stack([lowpass(x[:, j], fps, cutoff_hz, order) for j in range(x.shape[1])], axis=1)
    b, a = butter(order, cutoff_hz / (fps / 2.0), btype="low")
    pad = 3 * max(len(a), len(b))
    out = x.copy()
    valid = ~np.isnan(x)
    edges = np.flatnonzero(np.diff(np.concatenate([[0], valid.astype(int), [0]])))
    for start, stop in zip(edges[::2], edges[1::2]):
        if stop - start > pad:
            out[start:stop] = filtfilt(b, a, x[start:stop])
    return out
