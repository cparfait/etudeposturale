"""Voix : synthèse (texte → audio) et reconnaissance (audio → texte)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from posturale.ai import settings
from posturale.voice import stt, tts

router = APIRouter(prefix="/api/voice")


@router.get("/status")
def status() -> dict:
    s = settings.load()["voix"]
    return {"piper": tts.detect_piper(), "whisper": stt.status(s["whisper_modele"]), "modeles_whisper": stt.MODELS}


class SayIn(BaseModel):
    texte: str


@router.post("/tts")
def say(data: SayIn) -> Response:
    s = settings.load()
    v = s["voix"]
    text = data.texte.strip()[:1500]
    if not text:
        raise HTTPException(400, "Texte vide")
    try:
        if v["tts"] == "openai":
            audio, mime = tts.openai(text, settings.get_key("openai", s), v["openai_voix"], v["openai_tts_modele"], v["vitesse"])
        elif v["tts"] == "piper":
            exe, voice = v["piper_exe"], v["piper_voix"]
            if not exe or not voice:  # première utilisation : ce qui a été trouvé sur le PC
                found = tts.detect_piper()
                exe = exe or (found["executables"] or [""])[0]
                voice = voice or (found["voix"] or [{"chemin": ""}])[0]["chemin"]
            audio, mime = tts.piper(text, exe, voice, v["vitesse"])
        else:
            raise HTTPException(400, "La voix de l'application est désactivée (voix du navigateur ou aucune).")
    except tts.TTSError as exc:
        raise HTTPException(502, str(exc)) from exc
    return Response(audio, media_type=mime)


@router.post("/stt/prepare")
def prepare() -> dict:
    """Télécharge (première fois) et charge le modèle Whisper choisi."""
    v = settings.load()["voix"]
    try:
        stt.load(v["whisper_modele"])
    except stt.STTError as exc:
        raise HTTPException(502, str(exc)) from exc
    return stt.status(v["whisper_modele"])


@router.post("/stt")
def transcribe(file: UploadFile = File(...)) -> dict:
    s = settings.load()
    v = s["voix"]
    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        path = tmp.name
    try:
        if v["stt"] == "openai":
            text = stt.openai(path, settings.get_key("openai", s), v["openai_stt_modele"])
        else:
            text = stt.whisper(path, v["whisper_modele"])
    except stt.STTError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — audio illisible, etc.
        raise HTTPException(400, f"Audio non reconnu : {exc}") from exc
    finally:
        Path(path).unlink(missing_ok=True)
    return {"texte": text}
