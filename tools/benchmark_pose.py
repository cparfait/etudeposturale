"""Benchmark des moteurs de pose sur une vidéo de profil (phase 1 → début de phase 2).

Pour chaque moteur disponible, calcule image par image la flexion du genou
(0° = jambe tendue) du côté filmé, puis estime P1 (extension max ≈ PMB) et
P2 (flexion max ≈ PMH) sur l'ensemble des cycles. Optionnellement, compare
à une vérité terrain (pointage Kinovea ou autre) fournie en CSV.

Protocole : docs/04_benchmark_pose.md

Installation (dans un environnement dédié) :
    pip install opencv-python numpy scipy rtmlib onnxruntime-gpu mediapipe

Exemples :
    python tools/benchmark_pose.py data/profil_D.mp4 --side D
    python tools/benchmark_pose.py data/profil_G.mp4 --side G --engines rtmw,mediapipe \
        --mediapipe-model models/pose_landmarker_heavy.task --truth data/kinovea_G.csv

Sorties (dans --out, par défaut data/benchmark/<nom_vidéo>/) :
    angles.csv   frame, temps_s, puis pour chaque moteur : flexion_deg, confiance
    resume.csv   moteur, P1 moyenne/écart-type, P2 moyenne/écart-type, n cycles,
                 % images exploitables, temps de calcul, et erreurs vs vérité terrain
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

# Indices (hanche, genou, cheville) par moteur et par côté
KEYPOINTS = {
    # COCO-17 et COCO-WholeBody partagent les 17 premiers points
    "rtmw": {"G": (11, 13, 15), "D": (12, 14, 16)},
    "rtmpose": {"G": (11, 13, 15), "D": (12, 14, 16)},
    "rtmpose_feet": {"G": (11, 13, 15), "D": (12, 14, 16)},
    # MediaPipe Pose (33 points)
    "mediapipe": {"G": (23, 25, 27), "D": (24, 26, 28)},
}
MIN_SCORE = 0.3


def knee_flexion(hip: np.ndarray, knee: np.ndarray, ankle: np.ndarray) -> float:
    """Flexion du genou en degrés : 180° − angle intérieur hanche‑genou‑cheville."""
    a, b = hip - knee, ankle - knee
    cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
    return 180.0 - float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


# --------------------------------------------------------------------------- moteurs
class RtmlibEngine:
    def __init__(self, kind: str, device: str):
        import rtmlib  # import tardif : moteur optionnel

        cls = {"rtmw": rtmlib.Wholebody, "rtmpose": rtmlib.Body, "rtmpose_feet": rtmlib.BodyWithFeet}[kind]
        self.model = cls(mode="performance", backend="onnxruntime", device=device)

    def __call__(self, frame_bgr):
        kpts, scores = self.model(frame_bgr)
        if kpts is None or len(kpts) == 0:
            return None, None
        best = int(np.argmax(np.mean(scores, axis=1)))  # personne la plus nette
        return kpts[best], scores[best]


class MediapipeEngine:
    def __init__(self, model_path: str | None, fps: float):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python import vision

        if not model_path:
            raise RuntimeError("--mediapipe-model requis (pose_landmarker_heavy.task)")
        opts = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        self.mp = mp
        self.model = vision.PoseLandmarker.create_from_options(opts)
        self.fps = fps
        self.i = 0

    def __call__(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        res = self.model.detect_for_video(img, int(self.i * 1000 / self.fps))
        self.i += 1
        if not res.pose_landmarks:
            return None, None
        lm = res.pose_landmarks[0]
        kpts = np.array([[p.x * w, p.y * h] for p in lm])
        scores = np.array([p.visibility for p in lm])
        return kpts, scores


def build_engines(names, args, fps):
    engines = {}
    for name in names:
        try:
            if name == "mediapipe":
                engines[name] = MediapipeEngine(args.mediapipe_model, fps)
            else:
                engines[name] = RtmlibEngine(name, args.device)
            print(f"[ok] moteur {name}")
        except Exception as exc:  # moteur absent ou mal installé : on continue sans lui
            print(f"[ignoré] {name} : {exc}")
    return engines


# --------------------------------------------------------------------------- analyse
def lowpass(x: np.ndarray, fps: float, cutoff: float = 6.0) -> np.ndarray:
    """Interpolation des trous puis Butterworth ordre 4 à phase nulle."""
    idx = np.arange(len(x))
    ok = ~np.isnan(x)
    if ok.sum() < 10:
        return x
    y = np.interp(idx, idx[ok], x[ok])
    b, a = butter(4, cutoff / (fps / 2), btype="low")
    return filtfilt(b, a, y)


def cycle_extrema(flex: np.ndarray, fps: float, cadence_max_rpm: float = 130):
    """P1 = minima de flexion (extension max), P2 = maxima, un de chaque par cycle."""
    min_dist = int(fps * 60 / cadence_max_rpm)
    y = lowpass(flex, fps)
    prom = max(10.0, 0.3 * (np.nanpercentile(y, 95) - np.nanpercentile(y, 5)))
    maxima, _ = find_peaks(y, distance=min_dist, prominence=prom)
    minima, _ = find_peaks(-y, distance=min_dist, prominence=prom)
    return y, minima, maxima


def stats(values: np.ndarray):
    return (float(np.mean(values)), float(np.std(values, ddof=1))) if len(values) > 1 else (float("nan"),) * 2


def load_truth(path: Path):
    """CSV « frame,flexion_deg » (en‑tête obligatoire)."""
    with path.open(encoding="utf-8") as f:
        return {int(r["frame"]): float(r["flexion_deg"]) for r in csv.DictReader(f)}


def main():
    for stream in (sys.stdout, sys.stderr):  # console Windows (cp1252) : forcer l'UTF-8
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video", type=Path)
    p.add_argument("--side", choices=["G", "D"], required=True, help="jambe côté caméra")
    p.add_argument("--engines", default="rtmw,rtmpose,mediapipe")
    p.add_argument("--device", default="cuda")
    p.add_argument("--mediapipe-model", default=None)
    p.add_argument("--truth", type=Path, default=None, help="CSV frame,flexion_deg (pointage manuel)")
    p.add_argument("--start", type=float, default=5.0, help="secondes ignorées au début")
    p.add_argument("--duration", type=float, default=None, help="durée analysée (s)")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"Impossible d'ouvrir {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    first = int(args.start * fps)
    last = n_total if args.duration is None else min(n_total, first + int(args.duration * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    print(f"{args.video.name} : {fps:.2f} fps (nominal), images {first}–{last}")
    if fps < 59:
        print("ATTENTION : moins de 60 fps, précision dégradée (voir protocole)")

    engines = build_engines([e.strip() for e in args.engines.split(",") if e.strip()], args, fps)
    if not engines:
        raise SystemExit("Aucun moteur disponible.")

    n = last - first
    flex = {k: np.full(n, np.nan) for k in engines}
    conf = {k: np.full(n, np.nan) for k in engines}
    elapsed = {k: 0.0 for k in engines}

    for i in range(n):
        ok, frame = cap.read()
        if not ok:
            n = i
            break
        for name, engine in engines.items():
            t0 = time.perf_counter()
            kpts, scores = engine(frame)
            elapsed[name] += time.perf_counter() - t0
            if kpts is None:
                continue
            ih, ik, ia = KEYPOINTS[name][args.side]
            c = float(min(scores[ih], scores[ik], scores[ia]))
            conf[name][i] = c
            if c >= MIN_SCORE:
                flex[name][i] = knee_flexion(kpts[ih], kpts[ik], kpts[ia])
        if i % 300 == 0:
            print(f"  image {i}/{n}")
    cap.release()

    out = args.out or Path("data/benchmark") / args.video.stem
    out.mkdir(parents=True, exist_ok=True)
    names = list(engines)

    with (out / "angles.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame", "temps_s"] + [f"{k}_{c}" for k in names for c in ("flexion_deg", "confiance")])
        for i in range(n):
            row = [first + i, round((first + i) / fps, 4)]
            for k in names:
                row += [round(flex[k][i], 2), round(conf[k][i], 3)]
            w.writerow(row)

    truth = load_truth(args.truth) if args.truth else {}
    rows = []
    for k in names:
        y, mins, maxs = cycle_extrema(flex[k][:n], fps)
        p1m, p1s = stats(y[mins])
        p2m, p2s = stats(y[maxs])
        row = {
            "moteur": k,
            "P1_moy": round(p1m, 1), "P1_et": round(p1s, 1),
            "P2_moy": round(p2m, 1), "P2_et": round(p2s, 1),
            "n_cycles": min(len(mins), len(maxs)),
            "images_ok_pct": round(100 * np.mean(~np.isnan(flex[k][:n])), 1),
            "ms_par_image": round(1000 * elapsed[k] / max(n, 1), 1),
        }
        if truth:
            err = [y[f - first] - v for f, v in truth.items() if 0 <= f - first < n]
            if err:
                err = np.array(err)
                row.update(erreur_abs_moy=round(float(np.mean(np.abs(err))), 2),
                           biais=round(float(np.mean(err)), 2),
                           erreur_max=round(float(np.max(np.abs(err))), 2),
                           n_verite=len(err))
        rows.append(row)

    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
    with (out / "resume.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    print("\nRésumé (flexion du genou, degrés) :")
    for r in rows:
        print("  " + ", ".join(f"{k}={v}" for k, v in r.items()))
    print(f"\nFichiers : {out / 'angles.csv'} ; {out / 'resume.csv'}")


if __name__ == "__main__":
    main()
