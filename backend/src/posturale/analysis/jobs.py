"""File d'analyses en arrière-plan : une seule analyse à la fois (GPU partagé)."""
from __future__ import annotations

import json
import queue
import threading
import traceback
from typing import Any, Callable

from sqlmodel import Session as DB

from posturale.config import data_dir
from posturale.storage import get_engine
from posturale.storage.models import Analysis, Bike, BikeConfig, CameraCalib, Capture, now
from posturale.storage.models import Session as Seance

_queue: "queue.Queue[tuple[int, dict]]" = queue.Queue()
_worker: threading.Thread | None = None
_engine_cache: dict[str, Any] = {}
_lock = threading.Lock()

# Point d'injection pour les tests (moteur de pose simulé)
engine_factory: Callable[[], Any] | None = None


def get_pose_engine():
    if engine_factory is not None:
        return engine_factory()
    with _lock:
        if "rtmw" not in _engine_cache:
            from posturale.pose.engines import RtmwEngine

            _engine_cache["rtmw"] = RtmwEngine()
        return _engine_cache["rtmw"]


def submit(analysis_id: int, options: dict) -> None:
    global _worker
    _queue.put((analysis_id, options))
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_loop, name="analyses", daemon=True)
        _worker.start()


def wait_idle(timeout: float = 600) -> None:
    """Pour les tests : attend que la file soit vide."""
    import time

    t0 = time.time()
    while (not _queue.empty() or _busy.is_set()) and time.time() - t0 < timeout:
        time.sleep(0.1)


_busy = threading.Event()


def _update(aid: int, **fields) -> None:
    with DB(get_engine()) as db:
        a = db.get(Analysis, aid)
        if a is None:
            return
        for k, v in fields.items():
            setattr(a, k, v)
        db.add(a)
        db.commit()


def _loop() -> None:
    while True:
        aid, opts = _queue.get()
        _busy.set()
        try:
            _run(aid, opts)
        except Exception as exc:  # l'erreur est remontée à l'interface
            _update(aid, status="erreur", error=str(exc), message="Échec de l'analyse", finished_at=now())
            traceback.print_exc()
        finally:
            _busy.clear()
            _queue.task_done()


def _to_json(o):
    import numpy as np

    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Type non sérialisable : {type(o).__name__}")


def summary_of(result: dict) -> dict:
    """Résumé stocké en base (le résultat complet est dans un fichier JSON)."""
    s = {"vue": result["vue"], "cote": result.get("cote"), "qualite": result.get("qualite")}
    if result["vue"] == "profil":
        s["metriques"] = result["metriques"]
        s["verdict_selle"] = result.get("verdict_selle")
        s["echelle"] = result.get("echelle")
    else:
        m = dict(result["metriques"])
        for side in m.get("cotes", {}).values():
            side.pop("trajectoire_genou", None)
        m.pop("roulis_deg", None)
        s["metriques"] = m
    return s


def _run(aid: int, opts: dict) -> None:
    from posturale.analysis.pipeline import analyze_frontal_video, analyze_profile_video
    from posturale.calibration.charuco import Intrinsics, load_board, plane_from_frames
    from posturale.capture.video import iter_frames

    with DB(get_engine()) as db:
        a = db.get(Analysis, aid)
        cap = db.get(Capture, a.capture_id)
        seance = db.get(Seance, cap.session_id)
        config = db.get(BikeConfig, seance.bike_config_id) if seance and seance.bike_config_id else None
        bike = db.get(Bike, 1)
        calib = db.get(CameraCalib, cap.calib_id) if cap.calib_id else None
        path, vue = cap.path, cap.vue
        crank = (config.manivelle_mm if config else None) or 175.0
        sta = bike.angle_tube_selle_deg if bike else None
        intr = Intrinsics(**calib.data) if calib else None

    _update(aid, status="en_cours", progress=0.01, message="Chargement du modèle de pose")
    engine = get_pose_engine()

    def progress(p: float, msg: str) -> None:
        _update(aid, progress=round(p, 3), message=msg)

    common = dict(start_s=opts.get("debut_s"), duration_s=opts.get("duree_s", 45.0), stride=int(opts.get("pas", 1)), progress=progress)
    if vue == "profil":
        plane = None
        progress(0.02, "Recherche de la mire ChArUco")
        for board_name in ("A3", "A2"):
            frames = [f for i, (_, _, f) in enumerate(iter_frames(path, 0, 8)) if i % 20 == 0]
            plane = plane_from_frames(frames, load_board(board_name), intr)
            if plane:
                break
        result = analyze_profile_video(path, engine, crank_mm=crank, seat_tube_deg=sta, intr=intr, plane=plane, **common)
    else:
        result = analyze_frontal_video(path, engine, vue, **common)

    result = json.loads(json.dumps(result, ensure_ascii=False, default=_to_json))  # types NumPy → JSON
    out = data_dir() / "analyses"
    out.mkdir(exist_ok=True)
    fp = out / f"analyse_{aid}.json"
    fp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    _update(aid, status="terminee", progress=1.0, message="Analyse terminée", result_path=str(fp),
            summary=summary_of(result), finished_at=now())
