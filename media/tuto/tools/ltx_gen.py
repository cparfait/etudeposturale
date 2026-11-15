"""Génère les plans LTX-2 du tutoriel via l'API ComfyUI (D:/ComfyUI, port 8188), puis les copie dans assets/ltx/.

Usage : python ltx_gen.py [id ...]   (sans argument : tous les plans manquants)
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
DEST = Path(__file__).resolve().parent.parent / "assets" / "ltx"
W, H, FPS = 1280, 704, 24

STYLE = " Unbranded equipment without any lettering. Photorealistic, natural colors, soft even daylight, sharp focus, no text, no logo."
SHOTS = {
    "intro": (97, 101, "Wide shot of a bright modern living room. A cyclist in a black jersey and black shorts rides a road bike "
              "mounted on a smart indoor trainer, pedaling steadily, seen from the side. In the foreground a smartphone on a small "
              "tripod stands at saddle height, filming him. Static camera."),
    "materiel": (97, 212, "Top-down view of a light oak table with exactly four objects laid out flat and well apart: a black "
                 "smartphone, a small black folding tripod, a yellow tape measure, and a sheet of small bright blue and bright pink "
                 "square stickers. Very slow camera push-in, clean product photography."),
    "pastille": (97, 313, "Extreme close-up of the outer side of a cyclist's bare knee. A fingertip presses one single tiny bright "
                 "blue square sticker, the size of a fingernail, onto the skin over the knee joint, then lifts away, leaving the small "
                 "square dot on the knee. The sticker is a small square, not a band. Shallow depth of field."),
    "telephone": (97, 404, "Medium close-up: a hand places a smartphone in landscape orientation into a phone clamp on top of a "
                  "black tripod, next to a road bike on an indoor trainer in a living room. The phone screen faces the bike. Static camera."),
    "profil": (121, 515, "Wide shot from far away, exact side profile: a cyclist wearing a white helmet pedals a plain unbranded matte black "
               "road bike whose rear wheel is mounted on a black indoor smart trainer, in front of a plain light grey wall. The whole "
               "cyclist from helmet to shoes and the whole bike fill only the middle of the frame, with empty wall above the helmet and "
               "floor visible below the wheels. Black jersey, black shorts, bare legs. Camera static at saddle height. Even studio lighting."),
    "profil_a": (121, 616, "Side view of a man riding a black road bike fixed on an indoor turbo trainer, pedaling at a steady "
                 "cadence. Full body and the entire bicycle in frame, from the white helmet down to the black cycling shoes clipped "
                 "into the pedals. One handlebar at the front, saddle at the back. Plain light grey wall, static camera at saddle height."),
    "profil_b": (121, 727, "Static side-on shot of a cyclist training indoors: he sits on the saddle of a black road bike mounted on "
                 "an indoor trainer and pedals smoothly, hands on the handlebar at the front. White helmet, black kit, black cycling "
                 "shoes. The whole rider and bike are visible with space around them, plain light grey wall."),
    "selle": (97, 606, "Close-up of two hands using an Allen key to loosen the seat post clamp of a road bike and raise the saddle "
              "a few millimetres, home workshop, shallow depth of field."),
}


def graph(prompt: str, frames: int, seed: int, prefix: str) -> dict:
    ck = "ltx-2-19b-distilled-fp8.safetensors"
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ck}},
        "2": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": ck}},
        "3": {"class_type": "LTXAVTextEncoderLoader", "inputs": {"text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors", "ckpt_name": ck, "device": "default"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt + STYLE}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": ""}},
        "6": {"class_type": "LTXVConditioning", "inputs": {"positive": ["4", 0], "negative": ["5", 0], "frame_rate": FPS}},
        "7": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": W, "height": H, "length": frames, "batch_size": 1}},
        "8": {"class_type": "LTXVEmptyLatentAudio", "inputs": {"frames_number": frames, "frame_rate": FPS, "batch_size": 1, "audio_vae": ["2", 0]}},
        "9": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["7", 0], "audio_latent": ["8", 0]}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["6", 0], "negative": ["6", 1], "cfg": 1.0}},
        "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        "13": {"class_type": "ManualSigmas", "inputs": {"sigmas": "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["11", 0], "sampler": ["12", 0], "sigmas": ["13", 0], "latent_image": ["9", 0]}},
        "15": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["14", 0]}},
        "16": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["15", 0], "vae": ["1", 2], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "18": {"class_type": "CreateVideo", "inputs": {"images": ["16", 0], "fps": FPS}},
        "19": {"class_type": "SaveVideo", "inputs": {"video": ["18", 0], "filename_prefix": prefix, "format": "mp4", "codec": "h264"}},
    }


def call(path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, json.dumps(body).encode() if body else None, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    ids = sys.argv[1:] or [k for k in SHOTS if not (DEST / f"{k}.mp4").exists()]
    jobs = {}
    for k in ids:
        frames, seed, prompt = SHOTS[k]
        r = call("/prompt", {"prompt": graph(prompt, frames, seed, f"tuto/{k}")})
        jobs[r["prompt_id"]] = k
        print("queued", k, flush=True)
    while jobs:
        time.sleep(5)
        for pid, k in list(jobs.items()):
            h = call(f"/history/{pid}")
            if pid not in h:
                continue
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                print("ERROR", k, json.dumps(st)[:800], flush=True)
                del jobs[pid]
                continue
            for out in h[pid].get("outputs", {}).values():
                for v in out.get("images", []) + out.get("videos", []) + out.get("gifs", []):
                    src = OUT_DIR / v.get("subfolder", "") / v["filename"]
                    if src.suffix == ".mp4":
                        shutil.copy(src, DEST / f"{k}.mp4")
                        print("done", k, "->", DEST / f"{k}.mp4", flush=True)
            del jobs[pid]


if __name__ == "__main__":
    main()
