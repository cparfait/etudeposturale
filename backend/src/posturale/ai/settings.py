"""Réglages du coach et de la voix (data/ai_settings.json). Les clés y sont chiffrées, jamais renvoyées à l'interface."""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from typing import Any

from posturale.ai import secrets
from posturale.config import data_dir

DEFAULTS: dict[str, Any] = {
    "fournisseur": "ollama",
    "modeles": {},          # fournisseur → modèle choisi
    "urls": {},             # fournisseur → adresse (Ollama, LM Studio, personnalisé)
    "cles": {},             # fournisseur → clé chiffrée
    "images": False,        # autoriser l'envoi d'images de l'analyse au modèle
    "voix": {
        "tts": "piper",               # piper | openai | navigateur | aucune
        "piper_exe": "",
        "piper_voix": "",
        "vitesse": 1.0,
        "openai_voix": "coral",
        "openai_tts_modele": "gpt-4o-mini-tts",
        "stt": "whisper",             # whisper | openai
        "whisper_modele": "large-v3-turbo",
        "openai_stt_modele": "gpt-4o-mini-transcribe",
        "lecture_auto": True,
    },
}

_lock = threading.Lock()


def _file():
    return data_dir() / "ai_settings.json"


def load() -> dict[str, Any]:
    s = deepcopy(DEFAULTS)
    f = _file()
    if f.exists():
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
            voix = {**s["voix"], **saved.get("voix", {})}
            s.update(saved)
            s["voix"] = voix
        except (ValueError, TypeError):
            pass
    return s


def save(s: dict[str, Any]) -> None:
    with _lock:
        _file().write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


def update(patch: dict[str, Any]) -> dict[str, Any]:
    s = load()
    for k in ("fournisseur", "images"):
        if k in patch:
            s[k] = patch[k]
    for k in ("modeles", "urls"):
        if k in patch:
            s[k] = {**s[k], **{p: v for p, v in patch[k].items() if v is not None}}
    if "voix" in patch:
        s["voix"] = {**s["voix"], **patch["voix"]}
    save(s)
    return s


def set_key(provider: str, key: str | None) -> None:
    s = load()
    if key:
        s["cles"][provider] = secrets.encrypt(key.strip())
    else:
        s["cles"].pop(provider, None)
    save(s)


def get_key(provider: str, s: dict | None = None) -> str:
    tok = (s or load())["cles"].get(provider)
    if not tok:
        return ""
    try:
        return secrets.decrypt(tok)
    except (ValueError, OSError):
        return ""


def public(s: dict[str, Any]) -> dict[str, Any]:
    """Réglages sans les clés (seulement l'information « clé enregistrée »)."""
    out = deepcopy(s)
    out["cles"] = {p: True for p in s["cles"]}
    return out
