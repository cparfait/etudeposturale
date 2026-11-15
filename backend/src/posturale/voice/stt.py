"""Reconnaissance vocale : Whisper sur la carte graphique (faster-whisper) ou OpenAI."""
from __future__ import annotations

import threading
from pathlib import Path

import httpx

from posturale.config import repo_root


class STTError(RuntimeError):
    pass


# Vocabulaire du domaine : aide Whisper à bien écrire les termes du vélo.
PROMPT = ("Coach vélo, étude posturale : selle, tige de selle, recul, cintre, potence, manivelle, cales, pédales, "
          "genou, hanche, cheville, ischios, pastilles, home trainer, Tacx Neo, watts, cadence. Suivant, répète, stop, c'est fait.")

MODELS = ["large-v3-turbo", "medium", "small", "base"]
_lock = threading.Lock()
_model = None
_model_info: dict = {}


def _models_dir() -> Path:
    d = repo_root() / "models" / "whisper"  # hors de data/ : ce ne sont pas tes données
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_downloaded(name: str) -> bool:
    return any(_models_dir().glob(f"models--*faster-whisper-{name}*/snapshots/*/model.bin"))


def _device() -> tuple[str, str]:
    try:
        import onnxruntime as ort

        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()  # met à disposition les DLL CUDA/cuDNN installées par pip
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:  # noqa: BLE001 — pas de GPU utilisable : CPU
        pass
    return "cpu", "int8"


def load(name: str):
    global _model, _model_info
    with _lock:
        if _model is not None and _model_info.get("nom") == name:
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise STTError("faster-whisper n'est pas installé (relancer scripts\\installer.bat).") from exc
        device, compute = _device()
        if device == "cpu" and name == "large-v3-turbo":
            name = "small"  # trop lent sur processeur
        _model = WhisperModel(name, device=device, compute_type=compute, download_root=str(_models_dir()))
        _model_info = {"nom": name, "appareil": "GPU (CUDA)" if device == "cuda" else "processeur"}
        return _model


def status(name: str) -> dict:
    return {"modele": name, "telecharge": is_downloaded(name), "charge": _model_info if _model is not None else None}


def whisper(path: str, name: str) -> str:
    model = load(name)
    segments, _info = model.transcribe(path, language="fr", vad_filter=True, beam_size=5, initial_prompt=PROMPT,
                                       condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segments).strip()


def openai(path: str, key: str, model: str = "gpt-4o-mini-transcribe") -> str:
    if not key:
        raise STTError("Clé OpenAI à saisir dans les réglages de l'IA (fournisseur OpenAI).")
    try:
        with open(path, "rb") as f:
            r = httpx.post("https://api.openai.com/v1/audio/transcriptions", headers={"authorization": f"Bearer {key}"},
                           data={"model": model, "language": "fr", "prompt": PROMPT}, files={"file": (Path(path).name, f)},
                           timeout=60)
    except httpx.HTTPError as exc:
        raise STTError("OpenAI injoignable.") from exc
    if r.status_code >= 400:
        raise STTError(f"OpenAI (reconnaissance) — erreur {r.status_code} : {r.text[:200]}")
    return (r.json().get("text") or "").strip()
