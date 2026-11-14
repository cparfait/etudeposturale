"""Lecture des vidéos : métadonnées réelles (ffprobe), détection du clap, itération des images."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass
class VideoMeta:
    path: str
    fps: float              # fréquence moyenne réelle
    fps_nominal: float
    n_frames: int
    width: int
    height: int
    duration_s: float
    rotation: int = 0
    creation_time: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _ffprobe(path: Path) -> dict | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=avg_frame_rate,r_frame_rate,nb_frames,width,height,duration:stream_side_data=rotation"
             ":stream_tags=rotate,creation_time:format_tags=creation_time:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return json.loads(out.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return None


def _ratio(s: str | None) -> float:
    if not s or s in ("0/0", "N/A"):
        return 0.0
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b) if float(b) else 0.0
    return float(s)


def probe(path: str | Path) -> VideoMeta:
    path = Path(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Vidéo illisible : {path.name}")
    fps_cv = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    meta = VideoMeta(str(path), fps_cv, fps_cv, n, w, h, n / fps_cv if fps_cv else 0.0)
    info = _ffprobe(path)
    if info and info.get("streams"):
        st = info["streams"][0]
        avg, nominal = _ratio(st.get("avg_frame_rate")), _ratio(st.get("r_frame_rate"))
        if avg:
            meta.fps = avg
        if nominal:
            meta.fps_nominal = nominal
        dur = float(st.get("duration") or info.get("format", {}).get("duration") or 0)
        if dur:
            meta.duration_s = dur
        tags = {**info.get("format", {}).get("tags", {}), **st.get("tags", {})}
        meta.creation_time = tags.get("creation_time")
        rot = tags.get("rotate")
        for sd in st.get("side_data_list", []) or []:
            rot = sd.get("rotation", rot)
        meta.rotation = int(float(rot)) % 360 if rot else 0
    return meta


def detect_clap(path: str | Path, search_s: float = 20.0, rate: int = 8000) -> float | None:
    """Instant (s) du clap : pic d'énergie sonore le plus net dans les `search_s` premières secondes."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    try:
        raw = subprocess.run(
            [exe, "-v", "error", "-i", str(path), "-t", str(search_s), "-vn", "-ac", "1", "-ar", str(rate),
             "-f", "s16le", "-"], capture_output=True, timeout=60, check=True,
        ).stdout
    except subprocess.SubprocessError:
        return None
    x = np.frombuffer(raw, dtype=np.int16).astype(float)
    if len(x) < rate:
        return None
    win = rate // 100  # 10 ms
    energy = np.convolve(x**2, np.ones(win) / win, mode="same")
    peak = int(np.argmax(energy))
    background = np.median(energy) + 1e-9
    if energy[peak] / background < 30:  # pas de clap franc
        return None
    return peak / rate


def iter_frames(path: str | Path, start_s: float = 0.0, stop_s: float | None = None, step: int = 1) -> Iterator[tuple[int, float, np.ndarray]]:
    """(index, temps_s, image BGR). Le temps vient du conteneur (fps variable des téléphones)."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000)
    idx = int(round(start_s * fps))
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 or idx / fps
            if stop_s is not None and t > stop_s:
                break
            if (idx % step) == 0:
                yield idx, t, frame
            idx += 1
    finally:
        cap.release()
