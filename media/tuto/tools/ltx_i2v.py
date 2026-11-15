"""Anime les images de départ validées (work/stills) avec LTX-2 (image -> vidéo) ; écrit assets/ltx/<plan>.mp4.

Usage : python ltx_i2v.py [plan ...]
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltx_gen import API, DEST, FPS, H, OUT_DIR, W, call, graph  # noqa: E402

STILLS = Path(__file__).resolve().parent.parent / "work" / "stills"
MOTION = {
    # plan: (image validée, images, graine, mouvement)
    "profil": ("profil_1.png", 121, 801, "The cyclist pedals smoothly at a steady cadence of about ninety revolutions per minute: "
               "both legs turn the cranks in full circles, feet stay clipped to the pedals, the upper body and head stay still, "
               "hands stay on the hoods. The bicycle does not move. Static camera."),
    "profil_b": ("profil_1.png", 121, 911, "Indoor cycling training: the cyclist pedals vigorously. His right foot travels a full "
                 "circle with the crank, from the top of the stroke down to the bottom and back up, about one and a half turns per "
                 "second, the knee rising and falling with each stroke. The crank arm and chainring rotate continuously. Upper body "
                 "steady, bicycle fixed on the trainer, static camera."),
    "profil_c": ("profil_1.png", 121, 922, "The cyclist is pedaling fast on the indoor trainer: the cranks spin round and round, "
                 "his knees pump up and down rhythmically, feet clipped in the pedals following the circular motion. Static camera, "
                 "everything else still."),
    "pastille": ("pastille_3.png", 97, 802, "The fingertip presses the small blue square sticker flat onto the knee, then slowly "
                 "lifts away, leaving the square sticker on the skin. Subtle natural movement. Static camera."),
    "materiel": ("materiel_3.png", 97, 803, "Very slow, smooth camera push-in towards the objects on the table. Nothing moves."),
    "selle": ("selle_3.png", 97, 804, "The hands slowly turn the Allen key a quarter turn on the seat post clamp. Gentle, "
              "realistic movement. Static camera."),
}


def upload(path: Path) -> str:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + path.read_bytes() + \
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(API + "/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["name"]


def i2v_graph(image_name: str, prompt: str, frames: int, seed: int, prefix: str) -> dict:
    g = graph(prompt, frames, seed, prefix)
    g["20"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["21"] = {"class_type": "ImageScale", "inputs": {"image": ["20", 0], "upscale_method": "lanczos", "width": W, "height": H, "crop": "center"}}
    g["22"] = {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": ["1", 2], "image": ["21", 0], "latent": ["7", 0],
                                                                  "strength": 1.0, "bypass": False}}
    g["9"]["inputs"]["video_latent"] = ["22", 0]
    return g


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for k in sys.argv[1:] or list(MOTION):
        still, frames, seed, motion = MOTION[k]
        name = upload(STILLS / still)
        r = call("/prompt", {"prompt": i2v_graph(name, motion, frames, seed, f"tuto_i2v/{k}")})
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
                print("ERROR", k, json.dumps(st)[:900], flush=True)
            for out in h[pid].get("outputs", {}).values():
                for v in out.get("images", []) + out.get("videos", []):
                    src = OUT_DIR / v.get("subfolder", "") / v["filename"]
                    if src.suffix == ".mp4":
                        shutil.copy(src, DEST / f"{k}.mp4")
                        print("done", k, flush=True)
            del jobs[pid]


if __name__ == "__main__":
    main()
