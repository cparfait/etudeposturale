"""Synthèse vocale : Piper sur ce PC (par défaut) ou OpenAI. Les phrases déjà dites sont gardées en cache."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

from posturale.config import data_dir


class TTSError(RuntimeError):
    pass


def _app_roots() -> tuple[list[Path], list[Path]]:
    """Dossiers AppData Local et Roaming : variables d'environnement ET dossier de l'utilisateur.

    Selon la façon dont le serveur est lancé, LOCALAPPDATA / APPDATA peuvent manquer ou pointer ailleurs.
    """
    home = Path.home() / "AppData"
    local = [Path(x) for x in (os.environ.get("LOCALAPPDATA"),) if x] + [home / "Local"]
    roaming = [Path(x) for x in (os.environ.get("APPDATA"),) if x] + [home / "Roaming"]
    return local, roaming


def _candidates_dirs() -> list[Path]:
    """Dossiers où chercher Piper et ses voix : ceux du projet, puis ceux de LMU Stats Viewer s'il est installé."""
    local, roaming = _app_roots()
    dirs = [data_dir() / "voice"] + [r / "LMU Stats Viewer" / "tts" for r in local]
    for r in roaming:
        try:
            dirs += sorted(r.glob("com.cparfait.lmustatsviewer*/tts")) + sorted(r.glob("LMU_Stats_Viewer/tts"))
        except OSError:
            continue
    out, seen = [], set()
    for d in dirs:
        try:
            key = str(d.resolve()).lower()
            if key not in seen and d.is_dir():
                seen.add(key)
                out.append(d)
        except OSError:
            continue
    return out


def detect_piper() -> dict:
    exe_name = "piper.exe" if sys.platform == "win32" else "piper"
    exes, voices = [], []
    dirs = _candidates_dirs()
    for d in dirs:
        try:
            exes += [str(p) for p in d.rglob(exe_name)]
            onnx_files = list(d.rglob("*.onnx"))
        except OSError:
            continue
        for onnx in onnx_files:
            meta = onnx.with_suffix(".onnx.json")
            if not meta.exists():
                continue
            try:
                info = json.loads(meta.read_text(encoding="utf-8"))
                lang = (info.get("language") or {}).get("code") or info.get("espeak", {}).get("voice", "")
            except (ValueError, OSError):
                lang = ""
            voices.append({"chemin": str(onnx), "nom": onnx.stem, "langue": lang})
    voices.sort(key=lambda v: (not str(v["langue"]).startswith("fr"), len(v["nom"]) < 4, v["nom"]))  # voix nommées (siwis…) avant « fr »
    # dédoublonne (même voix copiée à plusieurs endroits)
    seen, uniq = set(), []
    for v in voices:
        if v["nom"] not in seen:
            seen.add(v["nom"])
            uniq.append(v)
    return {"executables": list(dict.fromkeys(exes)), "voix": uniq, "dossiers": [str(d) for d in dirs]}


def _cache(engine: str, key: str) -> Path:
    d = data_dir() / "voice" / "cache" / engine
    d.mkdir(parents=True, exist_ok=True)
    return d / key


def piper(text: str, exe: str, voice: str, speed: float = 1.0) -> tuple[bytes, str]:
    if not exe or not Path(exe).exists():
        raise TTSError("Piper introuvable : choisir piper.exe dans les réglages de la voix.")
    if not voice or not Path(voice).exists():
        raise TTSError("Voix Piper introuvable : choisir une voix (.onnx) dans les réglages.")
    speed = min(max(speed, 0.6), 1.6)
    key = hashlib.sha1(f"{voice}|{speed:.2f}|{text}".encode()).hexdigest() + ".wav"
    out = _cache("piper", key)
    if not out.exists():
        tmp = out.with_suffix(".tmp.wav")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            r = subprocess.run([exe, "-m", voice, "-f", str(tmp), "--length_scale", f"{1 / speed:.3f}", "-q"],
                               input=text.encode("utf-8"), capture_output=True, timeout=90, cwd=str(Path(exe).parent),
                               creationflags=flags)
        except subprocess.TimeoutExpired as exc:
            raise TTSError("Piper n'a pas répondu à temps.") from exc
        if r.returncode != 0 or not tmp.exists():
            raise TTSError(f"Piper en échec : {r.stderr.decode(errors='replace')[-300:]}")
        tmp.replace(out)
    return out.read_bytes(), "audio/wav"


def openai(text: str, key: str, voice: str = "coral", model: str = "gpt-4o-mini-tts", speed: float = 1.0) -> tuple[bytes, str]:
    if not key:
        raise TTSError("Clé OpenAI à saisir dans les réglages de l'IA (fournisseur OpenAI).")
    ck = hashlib.sha1(f"{model}|{voice}|{speed:.2f}|{text}".encode()).hexdigest() + ".mp3"
    out = _cache("openai", ck)
    if out.exists():
        return out.read_bytes(), "audio/mpeg"
    body = {"model": model, "voice": voice, "input": text, "response_format": "mp3", "speed": min(max(speed, 0.6), 1.6)}
    if "tts-1" not in model:
        body["instructions"] = "Voix de coach sportif calme et précise, en français."
    try:
        r = httpx.post("https://api.openai.com/v1/audio/speech", headers={"authorization": f"Bearer {key}"}, json=body, timeout=60)
    except httpx.HTTPError as exc:
        raise TTSError("OpenAI injoignable.") from exc
    if r.status_code >= 400:
        raise TTSError(f"OpenAI (voix) — erreur {r.status_code} : {r.text[:200]}")
    out.write_bytes(r.content)
    return r.content, "audio/mpeg"
