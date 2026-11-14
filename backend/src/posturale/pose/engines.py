"""Moteurs d'estimation de pose interchangeables.

Un moteur reçoit une image BGR et renvoie {repère: (x, y, confiance)} en pixels, pour le côté demandé.
Les noms de repères sont ceux de config/metrics.yaml.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np

LEG = ["trochanter", "epicondyle_femoral", "malleole", "talon", "metatarse5"]
UPPER = ["acromion", "epicondyle_humeral", "styloide_ulnaire"]
PROFILE_LANDMARKS = LEG + UPPER

# COCO-WholeBody (133 points) : 0-16 corps COCO, 17-22 pieds (gros orteil, petit orteil, talon ; G puis D)
_WB = {
    "G": {"trochanter": 11, "epicondyle_femoral": 13, "malleole": 15, "talon": 19, "metatarse5": 18,
          "acromion": 5, "epicondyle_humeral": 7, "styloide_ulnaire": 9},
    "D": {"trochanter": 12, "epicondyle_femoral": 14, "malleole": 16, "talon": 22, "metatarse5": 21,
          "acromion": 6, "epicondyle_humeral": 8, "styloide_ulnaire": 10},
}
# Points utiles aux vues de face et de dos (deux côtés)
FRONTAL = {"hanche_G": 11, "hanche_D": 12, "genou_G": 13, "genou_D": 14, "cheville_G": 15, "cheville_D": 16,
           "epaule_G": 5, "epaule_D": 6, "orteil_G": 17, "orteil_D": 20}

Points = dict[str, tuple[float, float, float]]


class PoseEngine(Protocol):
    name: str

    def __call__(self, frame_bgr: np.ndarray, side: str) -> Points: ...


class RtmwEngine:
    """RTMW (133 points dont les pieds) via rtmlib / ONNX Runtime. Modèles téléchargés au premier lancement."""

    name = "rtmw"

    def __init__(self, mode: str = "performance", device: str | None = None):
        import onnxruntime as ort
        from rtmlib import Wholebody

        if hasattr(ort, "preload_dlls"):  # charge les DLL CUDA/cuDNN installées par pip (onnxruntime-gpu[cuda,cudnn])
            try:
                ort.preload_dlls()
            except Exception:
                pass
        if device is None:
            device = "cuda" if "CUDAExecutionProvider" in ort.get_available_providers() else "cpu"
        self.device = device
        self.model = Wholebody(mode=mode, backend="onnxruntime", device=device)

    def raw(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        kpts, scores = self.model(frame_bgr)
        if kpts is None or len(kpts) == 0:
            return None
        best = int(np.argmax(np.mean(scores, axis=1)))  # personne la plus nette (le cycliste)
        return kpts[best], scores[best]

    def __call__(self, frame_bgr: np.ndarray, side: str) -> Points:
        r = self.raw(frame_bgr)
        if r is None:
            return {}
        k, s = r
        return {name: (float(k[i, 0]), float(k[i, 1]), float(s[i])) for name, i in _WB[side].items()}

    def frontal(self, frame_bgr: np.ndarray) -> Points:
        r = self.raw(frame_bgr)
        if r is None:
            return {}
        k, s = r
        return {name: (float(k[i, 0]), float(k[i, 1]), float(s[i])) for name, i in FRONTAL.items()}


def available_engines() -> dict[str, str]:
    """Moteurs installés → message d'état."""
    out = {}
    try:
        import onnxruntime as ort
        import rtmlib  # noqa: F401

        if hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls()
            except Exception:
                pass
        gpu = "CUDAExecutionProvider" in ort.get_available_providers()
        out["rtmw"] = "GPU (CUDA)" if gpu else "CPU (installer onnxruntime-gpu + CUDA pour la RTX 4090)"
    except ImportError:
        out["rtmw"] = "non installé (pip install rtmlib onnxruntime-gpu)"
    return out
