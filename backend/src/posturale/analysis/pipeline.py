"""Chaîne complète : vidéo → repères → plan du vélo → métriques → verdict (docs/03_specification.md § 5)."""
from __future__ import annotations

import math
import time
from typing import Callable

import numpy as np

from posturale.calibration.charuco import Intrinsics, PlaneCalib, apply_h, undistort
from posturale.capture.video import detect_clap, iter_frames, probe
from posturale.config import load_metrics
from posturale.kinematics.cycles import normalize_cycle
from posturale.metrics.frontal import front_metrics, rear_metrics
from posturale.metrics.profile_view import analyze_profile
from posturale.pose.engines import FRONTAL, PROFILE_LANDMARKS, PoseEngine
from posturale.pose.fusion import Fuser, assign_markers
from posturale.pose.markers import current_ranges, detect_blobs, fit_circle, locate_bb, pedal_track
from posturale.rules.saddle import saddle_verdict

Progress = Callable[[float, str], None]


def _noop(_p: float, _m: str) -> None:
    pass


def _window(meta, start_s: float | None, duration_s: float | None, path) -> tuple[float, float, float | None]:
    clap = detect_clap(path)
    start = start_s if start_s is not None else (clap + 1.5 if clap is not None else min(3.0, meta.duration_s * 0.1))
    stop = meta.duration_s if duration_s is None else min(meta.duration_s, start + duration_s)
    return start, stop, clap


def rotation_sign(pedal: np.ndarray, bb: np.ndarray) -> float:
    """+1 si la manivelle tourne dans le sens horaire à l'image (avant du vélo à droite), −1 sinon."""
    ang = np.unwrap(np.arctan2(pedal[:, 1] - bb[1], pedal[:, 0] - bb[0])[~np.isnan(pedal).any(1)])
    if len(ang) < 2:
        return 1.0
    return 1.0 if ang[-1] - ang[0] > 0 else -1.0


def to_bike_plane(px: np.ndarray, bb_px: np.ndarray, forward: float, mm_per_px: float,
                  plane: PlaneCalib | None, intr: Intrinsics | None) -> np.ndarray:
    """Pixels → plan du vélo (mm ; x vers l'avant, y vers le haut, origine = axe de pédalier).

    Avec la mire : homographie (corrige la perspective) ; la verticale est celle de l'image (caméra de niveau).
    Sans mire : échelle unique tirée de la longueur de manivelle.
    """
    shape = px.shape
    flat = px.reshape(-1, 2)
    ok = ~np.isnan(flat).any(1)
    out = np.full_like(flat, np.nan)
    if plane is not None:
        pts = undistort(flat[ok], intr)
        bbu = undistort(bb_px[None], intr)[0]
        # Repère orthonormé au pédalier : « haut » = verticale de l'image, « avant » = horizontale image × sens
        ref = apply_h(plane.H, np.vstack([bbu, bbu - [0, 100.0], bbu + [100.0, 0]]))
        up = (ref[1] - ref[0]) / np.linalg.norm(ref[1] - ref[0])
        right = ref[2] - ref[0]
        right = right - (right @ up) * up
        fwd = forward * right / np.linalg.norm(right)
        rel = apply_h(plane.H, pts) - ref[0]
        out[ok] = np.c_[rel @ fwd, rel @ up]
    else:
        rel = flat[ok] - bb_px
        out[ok] = np.c_[forward * rel[:, 0], -rel[:, 1]] * mm_per_px
    return out.reshape(shape)


def analyze_profile_video(
    path: str,
    engine: PoseEngine,
    crank_mm: float = 175.0,
    seat_tube_deg: float | None = None,
    intr: Intrinsics | None = None,
    plane: PlaneCalib | None = None,
    start_s: float | None = None,
    duration_s: float | None = 45.0,
    stride: int = 1,
    progress: Progress = _noop,
) -> dict:
    t0 = time.time()
    meta = probe(path)
    start, stop, clap = _window(meta, start_s, duration_s, path)
    n_est = int((stop - start) * meta.fps / stride) + 2
    progress(0.02, "Lecture de la vidéo")

    side_guess = "D"
    fuser = Fuser(PROFILE_LANDMARKS, n_est)
    orange, times = [], []
    radius = max(12.0, meta.width * 0.025)
    colors = current_ranges()
    vert, orange_rng = colors["vert"], colors["orange"]
    i = 0
    for idx, t, frame in iter_frames(path, start, stop, stride):
        if i >= n_est:
            break
        pose = engine(frame, side_guess)
        green = detect_blobs(frame, vert)
        orange.append(detect_blobs(frame, orange_rng))
        fuser.add(i, pose, assign_markers(pose, green, radius))
        times.append(t)
        i += 1
        if i % 30 == 0:
            progress(0.05 + 0.8 * min(1.0, i / n_est), f"Repères : image {i} / {n_est}")
    n = i
    if n < 30:
        raise ValueError("Trop peu d'images exploitables dans la vidéo.")
    times = np.array(times)
    fps_eff = 1.0 / float(np.median(np.diff(times))) if n > 1 else meta.fps / stride
    tracks_px, fusion_stats = fuser.tracks()
    tracks_px = {k: v[:n] for k, v in tracks_px.items()}
    progress(0.87, "Pédalier, échelle et cycles")

    # Pédalier et pédale : pastilles orange, sinon cercle de la cheville
    bb = locate_bb(orange)
    pedal = pedal_track(orange, bb) if bb is not None else np.full((n, 2), np.nan)
    crank_source = "pastilles"
    if bb is None or np.mean(~np.isnan(pedal).any(1)) < 0.5:
        circ = fit_circle(tracks_px["malleole"])
        if circ is None:
            raise ValueError("Impossible de trouver le pédalier : pastilles orange absentes et cheville mal suivie.")
        bb, _r = circ
        rel = tracks_px["malleole"] - bb
        pedal = bb + rel  # la cheville tourne autour du même axe : sert d'angle de manivelle approché
        crank_source = "trajectoire de la cheville (approché)"
    forward = rotation_sign(pedal, bb)
    side = "D" if forward > 0 else "G"
    r_px = float(np.nanmedian(np.linalg.norm(pedal - bb, axis=1)))
    mm_per_px = crank_mm / r_px if crank_source == "pastilles" else (plane.mm_per_px if plane else float("nan"))
    if not math.isfinite(mm_per_px):
        raise ValueError("Échelle inconnue : ajoutez les pastilles orange (pédalier et pédale) ou une mire ChArUco.")

    tracks_mm = {k: to_bike_plane(v, bb, forward, mm_per_px, plane, intr) for k, v in tracks_px.items()}
    tracks_mm["axe_pedale"] = to_bike_plane(pedal, bb, forward, mm_per_px, plane, intr)
    tracks_mm["axe_pedalier"] = to_bike_plane(np.tile(bb, (n, 1)), bb, forward, mm_per_px, plane, intr)

    res = analyze_profile(tracks_mm, fps_eff)
    progress(0.95, "Verdict")

    verdict = None
    if "P1" in res.summary and res.bdc_mm:
        p1 = res.summary["P1"]
        verdict = saddle_verdict(side, p1.mean, p1.sd, res.bdc_mm["hanche"], res.bdc_mm["cheville"],
                                 res.segments_mm["cuisse_mm"], res.segments_mm["jambe_mm"], seat_tube_deg).as_dict()

    # Courbes moyennes par degré de manivelle (pour les graphiques et l'avant/après)
    curves = {}
    for key in ("genou_flexion", "hanche_angle", "cheville_angle"):
        if key in res.series and res.cycles:
            mat = np.array([normalize_cycle(res.series[key], res.series["manivelle"], c, 4.0) for c in res.cycles])
            curves[key] = {
                "moyenne": _clean(np.nanmean(mat, axis=0)),
                "ecart_type": _clean(np.nanstd(mat, axis=0)),
            }

    q = dict(res.quality)
    cfg_q = load_metrics()["qualite"]
    q["Q1_fps"] = round(fps_eff, 1)
    q["Q1_ok"] = fps_eff >= cfg_q["Q1_fps_min"]
    if plane and plane.tilt_deg is not None:
        q["Q3_perpendicularite_deg"] = round(plane.tilt_deg, 1)
        q["Q3_ok"] = plane.tilt_deg <= cfg_q["Q3_perpendicularite_max_deg"]

    step = max(1, n // 900)
    overlay = {
        "temps": _clean(times[::step]),
        "pedalier": _clean(bb),
        "pedale": _clean(pedal[::step]),
        "reperes": {k: _clean(v[::step]) for k, v in tracks_px.items()},
        "genou_flexion": _clean(res.series["genou_flexion"][::step]),
    }
    return {
        "vue": "profil",
        "cote": side,
        "video": meta.as_dict(),
        "fenetre": {"debut_s": round(start, 2), "fin_s": round(stop, 2), "clap_s": clap, "pas": stride},
        "moteur": engine.name,
        "echelle": {"source": "mire ChArUco" if plane else "longueur de manivelle", "mm_par_px": round(mm_per_px, 4),
                    "manivelle_mm": crank_mm, "pedalier": crank_source},
        "metriques": {k: v.as_dict() for k, v in res.summary.items()},
        "par_cycle": {k: _clean(v) for k, v in res.per_cycle.items()},
        "segments_mm": {k: round(v, 1) for k, v in res.segments_mm.items()},
        "verdict_selle": verdict,
        "qualite": q,
        "fusion": fusion_stats,
        "courbes": curves,
        "overlay": overlay,
        "duree_calcul_s": round(time.time() - t0, 1),
    }


def analyze_frontal_video(path: str, engine, view: str, mm_per_px: float | None = None,
                          start_s: float | None = None, duration_s: float | None = 45.0, stride: int = 1,
                          progress: Progress = _noop) -> dict:
    """Vue de face (« face ») ou de dos (« dos ») : modèle de pose + pastilles vertes (rotules / EIPS)."""
    t0 = time.time()
    meta = probe(path)
    start, stop, clap = _window(meta, start_s, duration_s, path)
    n_est = int((stop - start) * meta.fps / stride) + 2
    names = list(FRONTAL)
    marked = ["genou_G", "genou_D"] if view == "face" else ["hanche_G", "hanche_D"]
    fuser = Fuser(names, n_est)
    radius = max(12.0, meta.width * 0.03)
    vert = current_ranges()["vert"]
    times, i = [], 0
    for _idx, t, frame in iter_frames(path, start, stop, stride):
        if i >= n_est:
            break
        pose = engine.frontal(frame)
        green = detect_blobs(frame, vert)
        fuser.add(i, pose, assign_markers({k: v for k, v in pose.items() if k in marked}, green, radius))
        times.append(t)
        i += 1
        if i % 30 == 0:
            progress(0.05 + 0.85 * min(1.0, i / n_est), f"Repères : image {i} / {n_est}")
    if i < 30:
        raise ValueError("Trop peu d'images exploitables dans la vidéo.")
    times = np.array(times)
    fps_eff = 1.0 / float(np.median(np.diff(times)))
    tracks, stats = fuser.tracks()
    tracks = {k: v[:i] for k, v in tracks.items()}
    # À l'image, le côté gauche du cycliste est à droite en vue de face et à gauche en vue de dos : on garde
    # les étiquettes anatomiques du modèle (déjà latéralisées) et on remet l'axe x dans le sens « vers la droite du cycliste ».
    if view == "face":
        tracks = {k: np.c_[-v[:, 0], v[:, 1]] for k, v in tracks.items()}
    metrics = front_metrics(tracks, fps_eff, mm_per_px) if view == "face" else rear_metrics(tracks, fps_eff, mm_per_px)
    return {
        "vue": view, "video": meta.as_dict(), "moteur": engine.name,
        "fenetre": {"debut_s": round(start, 2), "fin_s": round(stop, 2), "clap_s": clap, "pas": stride},
        "metriques": metrics, "fusion": stats, "qualite": {"Q1_fps": round(fps_eff, 1)},
        "duree_calcul_s": round(time.time() - t0, 1),
    }


def _clean(a):
    a = np.asarray(a, dtype=float)
    return np.where(np.isnan(a), None, np.round(a, 2)).tolist()
