"""Synthèse vocale : Piper sur ce PC (par défaut) ou OpenAI. Les phrases déjà dites sont gardées en cache."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

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


CARTESIA = "https://api.cartesia.ai"
CARTESIA_HEADERS = {"Cartesia-Version": "2025-04-16", "Content-Type": "application/json"}


def cartesia(text: str, key: str, voice: str, model: str = "sonic-3", speed: float = 1.0) -> tuple[bytes, str]:
    if not key:
        raise TTSError("Clé Cartesia à saisir dans les réglages de la voix.")
    speed = min(max(speed, 0.6), 1.5)
    ck = hashlib.sha1(f"{model}|{voice}|{speed:.2f}|{text}".encode()).hexdigest() + ".mp3"
    out = _cache("cartesia", ck)
    if out.exists():
        return out.read_bytes(), "audio/mpeg"
    body = {"model_id": model, "transcript": text, "language": "fr", "voice": {"mode": "id", "id": voice},
            "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000}}
    if abs(speed - 1) > 0.01:
        body["generation_config"] = {"speed": round(speed, 2)}
    try:
        r = httpx.post(f"{CARTESIA}/tts/bytes", headers={**CARTESIA_HEADERS, "X-API-Key": key}, json=body, timeout=60)
    except httpx.HTTPError as exc:
        raise TTSError("Cartesia injoignable.") from exc
    if r.status_code >= 400:
        raise TTSError(f"Cartesia — erreur {r.status_code} : {r.text[:200]}")
    out.write_bytes(r.content)
    return r.content, "audio/mpeg"


def cartesia_voices(key: str) -> list[dict]:
    if not key:
        raise TTSError("Clé Cartesia à saisir dans les réglages de la voix.")
    try:
        r = httpx.get(f"{CARTESIA}/voices", params={"language": "fr", "limit": 100},
                      headers={**CARTESIA_HEADERS, "X-API-Key": key}, timeout=20)
    except httpx.HTTPError as exc:
        raise TTSError("Cartesia injoignable.") from exc
    if r.status_code >= 400:
        raise TTSError(f"Cartesia — erreur {r.status_code} : {r.text[:200]}")
    data = r.json()
    items = data.get("data", data) if isinstance(data, dict) else data
    return [{"id": v["id"], "nom": v.get("name", v["id"]), "description": v.get("description") or ""}
            for v in items if v.get("language") == "fr"]


# ----------------------------------------------------------------- Fish Audio
FISH = "https://api.fish.audio"


def _fish_error(r: httpx.Response) -> str:
    hint = {401: "clé refusée", 402: "plus de crédit pour ce modèle (le modèle s2.1-pro-free est gratuit)",
            400: "requête refusée (identifiant de voix ?)", 429: "trop de requêtes"}.get(r.status_code, f"erreur {r.status_code}")
    return f"Fish Audio — {hint}" + (f" : {r.text[:200]}" if r.text.strip() else "")


# Voix génériques choisies à la main : la bibliothèque publique de fish.audio mélange des imitations de personnes
# réelles et du spam, on ne la liste donc pas automatiquement (un identifiant peut toujours être collé à la main).
FISH_VOICES = [
    {"id": "", "nom": "Voix par défaut de Fish Audio", "description": ""},
    {"id": "a288bdc744da4ad194921adad6863175", "nom": "Clémence", "description": "femme, calme et douce"},
    {"id": "9f0935a47689459480b820ed3f6d782d", "nom": "Voix masculine dynamique", "description": "homme, énergique et clair"},
    {"id": "6d3a8a05a287483ab32da9891d7f7fc9", "nom": "Voix masculine posée", "description": "homme, sérieux et clair"},
]


def fish_voices(key: str) -> list[dict]:
    if not key:
        raise TTSError("Clé Fish Audio à saisir dans les réglages de la voix.")
    return FISH_VOICES


def fish(text: str, key: str, voice: str = "", model: str = "s2.1-pro-free", speed: float = 1.0) -> tuple[bytes, str]:
    if not key:
        raise TTSError("Clé Fish Audio à saisir dans les réglages de la voix.")
    speed = min(max(speed, 0.6), 1.6)
    out = _cache("fish", hashlib.sha1(f"{model}|{voice}|{speed:.2f}|{text}".encode()).hexdigest() + ".mp3")
    if out.exists():
        return out.read_bytes(), "audio/mpeg"
    body: dict = {"text": text, "format": "mp3"}
    if voice:
        body["reference_id"] = voice
    if abs(speed - 1) > 0.01:
        body["prosody"] = {"speed": round(speed, 2)}
    try:
        r = httpx.post(f"{FISH}/v1/tts", json=body, timeout=90,
                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "model": model})
    except httpx.HTTPError as exc:
        raise TTSError("Fish Audio injoignable.") from exc
    if r.status_code >= 400:
        raise TTSError(_fish_error(r))
    out.write_bytes(r.content)
    return r.content, "audio/mpeg"


# ----------------------------------------------------------------- Google Cloud Text-to-Speech
GOOGLE = "https://texttospeech.googleapis.com/v1"


def _google_error(r: httpx.Response) -> str:
    try:
        msg = r.json().get("error", {}).get("message", "")
    except ValueError:
        msg = r.text[:200]
    hint = {400: "requête refusée", 401: "clé refusée", 403: "clé refusée ou API « Cloud Text-to-Speech » non activée",
            429: "quota atteint"}.get(r.status_code, f"erreur {r.status_code}")
    return f"Google — {hint} : {msg[:200]}"


def google_voices(key: str) -> list[dict]:
    if not key:
        raise TTSError("Clé Google Cloud à saisir dans les réglages de la voix.")
    try:
        r = httpx.get(f"{GOOGLE}/voices", params={"languageCode": "fr-FR"}, headers={"X-Goog-Api-Key": key}, timeout=20)
    except httpx.HTTPError as exc:
        raise TTSError("Google Cloud injoignable.") from exc
    if r.status_code >= 400:
        raise TTSError(_google_error(r))
    rank = lambda n: (0 if "Chirp3-HD" in n else 1 if "Chirp" in n else 2 if "Neural2" in n else 3 if "Wavenet" in n else 4, n)  # noqa: E731
    voices = [v for v in r.json().get("voices", []) if any(c.startswith("fr-FR") for c in v.get("languageCodes", []))]
    voices.sort(key=lambda v: rank(v["name"]))
    gender = {"FEMALE": "femme", "MALE": "homme"}
    return [{"id": v["name"], "nom": v["name"].removeprefix("fr-FR-"),
             "description": f"Voix {gender.get(v.get('ssmlGender'), '')}".strip()} for v in voices]


def google(text: str, key: str, voice: str = "", speed: float = 1.0) -> tuple[bytes, str]:
    if not key:
        raise TTSError("Clé Google Cloud à saisir dans les réglages de la voix.")
    if not voice:
        voices = google_voices(key)
        if not voices:
            raise TTSError("Google — aucune voix française disponible.")
        voice = voices[0]["id"]
    speed = min(max(speed, 0.6), 1.6)
    out = _cache("google", hashlib.sha1(f"{voice}|{speed:.2f}|{text}".encode()).hexdigest() + ".mp3")
    if out.exists():
        return out.read_bytes(), "audio/mpeg"
    body = {"input": {"text": text}, "voice": {"languageCode": "fr-FR", "name": voice},
            "audioConfig": {"audioEncoding": "MP3", **({"speakingRate": round(speed, 2)} if abs(speed - 1) > 0.01 else {})}}
    try:
        r = httpx.post(f"{GOOGLE}/text:synthesize", headers={"X-Goog-Api-Key": key}, json=body, timeout=60)
        if r.status_code == 400 and "speakingRate" in body["audioConfig"]:  # certaines voix n'acceptent pas la vitesse
            body["audioConfig"].pop("speakingRate")
            r = httpx.post(f"{GOOGLE}/text:synthesize", headers={"X-Goog-Api-Key": key}, json=body, timeout=60)
    except httpx.HTTPError as exc:
        raise TTSError("Google Cloud injoignable.") from exc
    if r.status_code >= 400:
        raise TTSError(_google_error(r))
    audio = base64.b64decode(r.json().get("audioContent", ""))
    out.write_bytes(audio)
    return audio, "audio/mpeg"


# ----------------------------------------------------------------- Azure Speech
def _azure_base(region: str) -> str:
    region = "".join(ch for ch in (region or "").lower() if ch.isalnum())
    if not region:
        raise TTSError("Région Azure à renseigner (ex. francecentral, westeurope).")
    return f"https://{region}.tts.speech.microsoft.com/cognitiveservices"


def _azure_error(r: httpx.Response) -> str:
    hint = {400: "requête refusée (voix inconnue ?)", 401: "clé refusée ou mauvaise région", 403: "accès refusé",
            429: "quota atteint (offre gratuite F0 : 500 000 caractères par mois)"}.get(r.status_code, f"erreur {r.status_code}")
    return f"Azure — {hint}" + (f" : {r.text[:200]}" if r.text.strip() else "")


def azure_voices(key: str, region: str) -> list[dict]:
    if not key:
        raise TTSError("Clé Azure Speech à saisir dans les réglages de la voix.")
    try:
        r = httpx.get(f"{_azure_base(region)}/voices/list", headers={"Ocp-Apim-Subscription-Key": key}, timeout=20)
    except httpx.HTTPError as exc:
        raise TTSError(f"Azure injoignable (région « {region} »).") from exc
    if r.status_code >= 400:
        raise TTSError(_azure_error(r))
    gender = {"Female": "femme", "Male": "homme"}
    voices = [v for v in r.json() if v.get("Locale") == "fr-FR"]
    voices.sort(key=lambda v: ("Multilingual" in v["ShortName"], v["ShortName"]))
    return [{"id": v["ShortName"], "nom": v.get("LocalName") or v["ShortName"],
             "description": f"Voix {gender.get(v.get('Gender'), '')}".strip() + (" · multilingue" if "Multilingual" in v["ShortName"] else "")}
            for v in voices]


def azure(text: str, key: str, region: str, voice: str = "fr-FR-DeniseNeural", speed: float = 1.0) -> tuple[bytes, str]:
    if not key:
        raise TTSError("Clé Azure Speech à saisir dans les réglages de la voix.")
    speed = min(max(speed, 0.6), 1.6)
    out = _cache("azure", hashlib.sha1(f"{voice}|{speed:.2f}|{text}".encode()).hexdigest() + ".mp3")
    if out.exists():
        return out.read_bytes(), "audio/mpeg"
    rate = f"{round((speed - 1) * 100):+d}%"
    ssml = (f"<speak version='1.0' xml:lang='fr-FR'><voice name='{escape(voice)}'>"
            f"<prosody rate='{rate}'>{escape(text)}</prosody></voice></speak>")
    try:
        r = httpx.post(f"{_azure_base(region)}/v1", content=ssml.encode("utf-8"), timeout=60, headers={
            "Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3", "User-Agent": "etude-posturale"})
    except httpx.HTTPError as exc:
        raise TTSError(f"Azure injoignable (région « {region} »).") from exc
    if r.status_code >= 400:
        raise TTSError(_azure_error(r))
    out.write_bytes(r.content)
    return r.content, "audio/mpeg"


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
