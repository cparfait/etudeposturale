"""Images de départ des plans (Z-Image Turbo via ComfyUI), à valider avant de les animer avec LTX (image -> vidéo).

Usage : python zimg.py [plan ...]      -> work/stills/<plan>_<n>.png (3 variantes) + planche work/stills/planche.jpg
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8188"
OUT_DIR = Path("D:/ComfyUI/output")
DEST = Path(__file__).resolve().parent.parent / "work" / "stills"
W, H = 1280, 704
SEEDS = (11, 22, 33) if len(__import__('sys').argv) < 3 else (44, 55, 66)

STYLE = (" Photorealistic photograph, natural colors, soft even daylight, sharp focus, correct anatomy, "
         "unbranded equipment without any lettering or logo.")
STILLS = {
    "profil": "Wide shot photographed from four metres away, exact side profile from the right side: an adult male cyclist "
              "sitting on the saddle of a plain matte black road bicycle whose rear wheel is clamped in a black indoor smart trainer. "
              "The bicycle faces right, one drop handlebar at the front, hands on the brake hoods, right foot in a black road cycling "
              "shoe clipped into the pedal. White helmet, black short-sleeve jersey, black bib shorts. The rider and bike are small in "
              "the frame and centred: they fill only the middle sixty percent of the image height, with a large empty light grey wall "
              "above the helmet and a strip of light floor below the wheels. Camera at saddle height.",
    "intro": "Wide photograph of a bright modern living room with large windows. In the middle distance, an adult male cyclist "
             "in a black jersey, black bib shorts and a white helmet rides a plain matte black road bicycle whose rear wheel is clamped "
             "in a black indoor smart trainer, seen exactly from the side, the bicycle facing right with one handlebar at the front. "
             "In the left foreground, a black smartphone in landscape orientation sits in a clamp on top of a small black tripod at "
             "saddle height; we see the back of the phone, its screen faces the cyclist and is not visible. Soft daylight.",
    "telephone": "Medium shot photograph in a living room: a hand clips a black smartphone in landscape orientation into the clamp "
                 "on top of a black tripod. Behind it, at a few metres, a plain matte black road bicycle stands on a black indoor smart "
                 "trainer, seen exactly from the side: two normal round wheels with thin spokes, one drop handlebar at the front, "
                 "saddle at the back, chain and crankset in the middle. We see the back of the phone; its screen faces the bicycle.",
    "pastille": "Close-up photograph of the outer side of a cyclist's bare knee, sitting on a road bike indoors. A single small "
                "bright blue square sticker, about two centimetres wide, is stuck on the skin over the knee joint, and a fingertip "
                "is pressing it flat. Black cycling shorts above the knee. Shallow depth of field.",
    "materiel": "Top-down photograph of a light oak table with four objects laid flat and well apart: a black smartphone, a small "
                "black folding tripod, a yellow tape measure, and a sheet of small bright blue and bright pink square stickers.",
    "selle": "Close-up photograph of two hands using a black hex Allen key on the seat post clamp of a matte black road bike, "
             "adjusting the saddle height, home workshop, shallow depth of field.",
}


def graph(prompt: str, seed: int, prefix: str) -> dict:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt + STYLE}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0],
                                                    "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "res_multistep",
                                                    "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": prefix}},
    }


def call(path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, json.dumps(body).encode() if body else None, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for k in sys.argv[1:] or list(STILLS):
        for n, seed in enumerate(SEEDS, 1):
            r = call("/prompt", {"prompt": graph(STILLS[k], seed, f"tuto_stills/{k}_{n}")})
            jobs[r["prompt_id"]] = f"{k}_{n}"
    while jobs:
        time.sleep(2)
        for pid, name in list(jobs.items()):
            h = call(f"/history/{pid}")
            if pid not in h:
                continue
            if h[pid].get("status", {}).get("status_str") == "error":
                print("ERREUR", name, json.dumps(h[pid]["status"])[:600])
            for out in h[pid].get("outputs", {}).values():
                for im in out.get("images", []):
                    shutil.copy(OUT_DIR / im.get("subfolder", "") / im["filename"], DEST / f"{name}.png")
                    print("ok", name, flush=True)
            del jobs[pid]


if __name__ == "__main__":
    main()
