"""Voix off du tutoriel (Cartesia, voix Henri). La clé est lue chiffrée dans les réglages de l'app, jamais affichée.

Usage : backend/.venv/Scripts/python media/tuto/tools/voix.py [id ...]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from posturale.ai import settings  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "voix"
VOICE = "d9f4af15-c402-4f50-bbda-d8823d028d6a"  # Henri (français), comme le guide de démarrage

LINES = {
    "c0": "Régler son vélo chez soi, avec son téléphone. Voici une séance complète, en six étapes.",
    "c1a": "Première étape : le matériel. Indique ce que tu as.",
    "c1b": "Cinq choses sont obligatoires. Le reste est facultatif : l'appli adapte la séance à ton équipement.",
    "c2a": "Deuxième étape : les pastilles. Découpe des carrés de deux centimètres dans de la bande de kiné.",
    "c2b": "Une couleur pour le corps : épaule, hanche, genou, cheville. Une autre, bien différente, pour le vélo.",
    "c2c": "Montre-les à la caméra et clique dessus : l'appli apprend leurs couleurs.",
    "c3a": "Troisième étape : les téléphones. Scanne le QR code de la séance.",
    "c3b": "Deux téléphones ? Un à droite, un à gauche. Leur image arrive en direct sur le PC.",
    "c4a": "Quatrième étape : le cadrage. Ajuste jusqu'au feu vert.",
    "c4b": "Corps entier dans l'image, caméra à hauteur de selle, assez de lumière.",
    "c5a": "Cinquième étape : l'enregistrement. Dis simplement : c'est parti.",
    "c5b": "Les téléphones filment une minute pendant que tu pédales normalement, puis envoient la vidéo.",
    "c6a": "Dernière étape : les résultats. L'appli mesure tes angles, à droite et à gauche.",
    "c6b": "Puis elle propose un seul réglage, ici baisser la selle de cinq millimètres.",
    "c6c": "Un réglage à la fois, puis une nouvelle séance pour vérifier.",
}


def duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return round(float(r.stdout.strip()), 2)


def main() -> int:
    key = settings.get_key("cartesia", settings.load())
    if not key:
        print("Pas de clé Cartesia dans les réglages de l'app.", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    for lid, text in LINES.items():
        if only and lid not in only:
            continue
        r = httpx.post("https://api.cartesia.ai/tts/bytes", timeout=120, headers={
            "X-API-Key": key, "Cartesia-Version": "2025-04-16", "Content-Type": "application/json"}, json={
            "model_id": "sonic-3", "transcript": text, "language": "fr", "voice": {"mode": "id", "id": VOICE},
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100}})
        if r.status_code >= 400:
            print(f"{lid} : erreur {r.status_code} {r.text[:200]}", file=sys.stderr)
            return 2
        (OUT / f"{lid}.wav").write_bytes(r.content)
    durs = {lid: duration(OUT / f"{lid}.wav") for lid in LINES if (OUT / f"{lid}.wav").exists()}
    (OUT / "durees.json").write_text(json.dumps({"textes": LINES, "durees": durs}, ensure_ascii=False, indent=1), encoding="utf-8")
    for lid, d in durs.items():
        print(f"{lid}: {d} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

