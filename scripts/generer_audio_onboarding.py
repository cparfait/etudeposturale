"""Génère les voix off du guide de démarrage avec Cartesia (une fois, fichiers MP3 commités).

Usage (la clé n'est jamais écrite dans le dépôt) :
    set CARTESIA_API_KEY=sk_car_...
    backend\\.venv\\Scripts\\python scripts\\generer_audio_onboarding.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
TEXTS = ROOT / "frontend" / "src" / "onboarding" / "narration.json"
OUT = ROOT / "frontend" / "public" / "onboarding"
VOICE = "d9f4af15-c402-4f50-bbda-d8823d028d6a"  # Henri - Express Host (français)
MODELS = ("sonic-3", "sonic-2")


def main() -> int:
    key = os.environ.get("CARTESIA_API_KEY")
    if not key:
        print("Définir CARTESIA_API_KEY.", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))["etapes"]
    only = set(sys.argv[1:])
    for sid, text in texts.items():
        if only and sid not in only:
            continue
        for model in MODELS:
            r = httpx.post("https://api.cartesia.ai/tts/bytes", timeout=120, headers={
                "X-API-Key": key, "Cartesia-Version": "2025-04-16", "Content-Type": "application/json"}, json={
                "model_id": model, "transcript": text, "language": "fr",
                "voice": {"mode": "id", "id": VOICE},
                "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000}})
            if r.status_code < 400:
                (OUT / f"{sid}.mp3").write_bytes(r.content)
                print(f"{sid}.mp3 : {len(r.content) // 1024} Ko ({model})")
                break
            print(f"{sid} ({model}) : erreur {r.status_code} {r.text[:200]}", file=sys.stderr)
        else:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
