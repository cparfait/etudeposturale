"""Vidéo synthétique d'un cycliste avec pastilles, et moteur de pose simulé (imprécis, comme un vrai réseau)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from synthetic import rider

W, H = 1280, 720
SCALE = 0.55             # px par mm
ORIGIN = np.array([560.0, 560.0])  # pédalier à l'image
BODY = ["trochanter", "epicondyle_femoral", "malleole", "talon", "metatarse5", "acromion", "epicondyle_humeral", "styloide_ulnaire"]
BONES = [("trochanter", "epicondyle_femoral"), ("epicondyle_femoral", "malleole"), ("talon", "metatarse5"),
         ("trochanter", "acromion"), ("acromion", "epicondyle_humeral"), ("epicondyle_humeral", "styloide_ulnaire")]


def mm_to_px(xy: np.ndarray, forward: str = "right") -> np.ndarray:
    s = 1 if forward == "right" else -1
    return np.c_[ORIGIN[0] + s * xy[:, 0] * SCALE, ORIGIN[1] - xy[:, 1] * SCALE]


def render(path: Path, fps: float = 60, seconds: float = 14, saddle_mm: float = 720.0, forward: str = "right",
           markers: bool = True) -> dict[str, np.ndarray]:
    tracks, _ = rider(fps=fps, seconds=seconds, saddle_mm=saddle_mm)
    px = {k: mm_to_px(v, forward) for k, v in tracks.items()}
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    for i in range(len(px["trochanter"])):
        img = np.full((H, W, 3), 70, np.uint8)
        cv2.circle(img, tuple(int(v) for v in mm_to_px(np.array([[-300.0, 0.0]]), forward)[0]), int(340 * SCALE), (110, 110, 110), 6)
        for a, b in BONES:
            cv2.line(img, tuple(px[a][i].astype(int)), tuple(px[b][i].astype(int)), (35, 35, 35), 18, cv2.LINE_AA)
        cv2.line(img, tuple(px["axe_pedalier"][i].astype(int)), tuple(px["axe_pedale"][i].astype(int)), (150, 150, 150), 8)
        if markers:
            for k in BODY:
                cv2.circle(img, tuple(np.round(px[k][i]).astype(int)), 8, (60, 255, 120), -1, cv2.LINE_AA)
            for k in ("axe_pedale", "axe_pedalier"):
                cv2.circle(img, tuple(np.round(px[k][i]).astype(int)), 8, (30, 140, 255), -1, cv2.LINE_AA)
        vw.write(img)
    vw.release()
    return px


class FakeEngine:
    """Simule un réseau de pose : biais fixe par repère (± 12 px) + bruit (3 px)."""

    name = "simulé"

    def __init__(self, px: dict[str, np.ndarray], seed: int = 0):
        rng = np.random.default_rng(seed)
        self.px, self.i = px, 0
        self.bias = {k: rng.uniform(-12, 12, 2) for k in BODY}
        self.rng = rng

    def __call__(self, frame, side):
        i = min(self.i, len(self.px["trochanter"]) - 1)
        self.i += 1
        return {k: (*(self.px[k][i] + self.bias[k] + self.rng.normal(0, 3, 2)), 0.9) for k in BODY}
