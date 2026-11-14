"""Fusion pastilles + modèle de pose.

Le modèle de pose sert à **nommer** les pastilles : chaque repère prend la pastille verte la plus proche
de sa position estimée (dans un rayon donné, une pastille par repère). Sans pastille, on garde le point
du modèle, corrigé du décalage moyen pastille ↔ modèle observé sur le reste de la prise.
"""
from __future__ import annotations

import numpy as np

from posturale.pose.engines import Points


def assign_markers(pose: Points, blobs: np.ndarray, radius_px: float, min_conf: float = 0.2) -> dict[str, np.ndarray]:
    """Appariement glouton repère ↔ pastille par distance croissante."""
    names = [n for n, (_, _, c) in pose.items() if c >= min_conf]
    if not names or not len(blobs):
        return {}
    P = np.array([pose[n][:2] for n in names])
    D = np.linalg.norm(P[:, None, :] - blobs[None, :, :], axis=2)
    out: dict[str, np.ndarray] = {}
    used_r, used_c = set(), set()
    for flat in np.argsort(D, axis=None):
        r, c = divmod(int(flat), D.shape[1])
        if D[r, c] > radius_px:
            break
        if r in used_r or c in used_c:
            continue
        out[names[r]] = blobs[c]
        used_r.add(r)
        used_c.add(c)
    return out


class Fuser:
    """Accumule les trajectoires image par image puis produit les pistes fusionnées."""

    def __init__(self, landmarks: list[str], n_frames: int, min_conf: float = 0.3):
        self.landmarks = landmarks
        self.min_conf = min_conf
        self.pose = {k: np.full((n_frames, 2), np.nan) for k in landmarks}
        self.conf = {k: np.zeros(n_frames) for k in landmarks}
        self.marker = {k: np.full((n_frames, 2), np.nan) for k in landmarks}

    def add(self, i: int, pose: Points, markers: dict[str, np.ndarray]) -> None:
        for k in self.landmarks:
            if k in pose:
                x, y, c = pose[k]
                self.conf[k][i] = c
                if c >= self.min_conf:
                    self.pose[k][i] = (x, y)
            if k in markers:
                self.marker[k][i] = markers[k]

    def tracks(self) -> tuple[dict[str, np.ndarray], dict[str, dict]]:
        out, stats = {}, {}
        for k in self.landmarks:
            m, p = self.marker[k], self.pose[k]
            both = ~np.isnan(m).any(1) & ~np.isnan(p).any(1)
            offset = np.nanmedian(m[both] - p[both], axis=0) if both.sum() >= 10 else np.zeros(2)
            fused = m.copy()
            fill = np.isnan(fused).any(1) & ~np.isnan(p).any(1)
            fused[fill] = p[fill] + offset
            out[k] = fused
            dev = np.linalg.norm(m[both] - p[both] - offset, axis=1) if both.any() else np.array([])
            n = len(m)
            stats[k] = {
                "pastille_pct": round(100 * float(np.mean(~np.isnan(m).any(1))), 1),
                "modele_pct": round(100 * float(np.mean(~np.isnan(p).any(1))), 1),
                "ecart_px": round(float(np.median(dev)), 1) if len(dev) else None,
                "decalage_px": [round(float(v), 1) for v in offset],
                "n": n,
            }
        return out, stats
