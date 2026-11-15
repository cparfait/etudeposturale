"""Séances, vidéos, analyses, calibration des caméras, fichiers .FIT."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session as DB, select

from posturale.analysis import jobs
from posturale.config import data_dir
from posturale.pose.engines import available_engines
from posturale.storage import get_session
from posturale.storage.models import Analysis, BikeConfig, CameraCalib, Capture, FitFile, Session as Seance

router = APIRouter(prefix="/api")

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def _save_upload(f: UploadFile, folder: str, allowed: set[str]) -> Path:
    ext = Path(f.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Format non pris en charge ({ext or 'inconnu'}) : {', '.join(sorted(allowed))}")
    d = data_dir() / folder
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{uuid.uuid4().hex}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(f.file, out)
    return dest


def _remux(path: Path) -> Path:
    """Les vidéos WebM enregistrées par le navigateur n'ont souvent ni durée ni index : copie sans réencodage en .mkv."""
    import subprocess

    exe = shutil.which("ffmpeg")
    if not exe:
        return path
    out = path.with_suffix(".mkv")
    r = subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(path), "-c", "copy", str(out)], capture_output=True, timeout=300)
    if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
        path.unlink(missing_ok=True)
        return out
    out.unlink(missing_ok=True)
    return path


@router.get("/engines")
def engines() -> dict:
    return available_engines()


# ----------------------------------------------------------------- séances
class SessionIn(BaseModel):
    etat: str = "repose"
    puissance_cible_w: Optional[float] = None
    notes: Optional[str] = None


def _session_view(db: DB, s: Seance) -> dict:
    caps = list(db.exec(select(Capture).where(Capture.session_id == s.id).order_by(Capture.id)))
    out_caps = []
    for c in caps:
        an = list(db.exec(select(Analysis).where(Analysis.capture_id == c.id).order_by(Analysis.id.desc())))
        out_caps.append({**c.model_dump(exclude={"path"}), "analyses": [a.model_dump(exclude={"result_path"}) for a in an]})
    fits = list(db.exec(select(FitFile).where(FitFile.session_id == s.id)))
    config = db.get(BikeConfig, s.bike_config_id) if s.bike_config_id else None
    return {**s.model_dump(), "config": config.model_dump() if config else None, "captures": out_caps,
            "fits": [f.model_dump() for f in fits]}


@router.post("/sessions", status_code=201)
def create_session(data: SessionIn, db: DB = Depends(get_session)) -> dict:
    current = db.exec(select(BikeConfig).order_by(BikeConfig.created_at.desc(), BikeConfig.id.desc())).first()
    s = Seance(**data.model_dump(), bike_config_id=current.id if current else None)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_view(db, s)


@router.get("/sessions")
def list_sessions(db: DB = Depends(get_session)) -> list[dict]:
    return [_session_view(db, s) for s in db.exec(select(Seance).order_by(Seance.id.desc()))]


@router.get("/sessions/{sid}")
def get_session_(sid: int, db: DB = Depends(get_session)) -> dict:
    s = db.get(Seance, sid)
    if not s:
        raise HTTPException(404, "Séance introuvable")
    return _session_view(db, s)


@router.delete("/sessions/{sid}", status_code=204)
def delete_session(sid: int, db: DB = Depends(get_session)) -> None:
    s = db.get(Seance, sid)
    if not s:
        raise HTTPException(404, "Séance introuvable")
    for c in db.exec(select(Capture).where(Capture.session_id == sid)):
        for a in db.exec(select(Analysis).where(Analysis.capture_id == c.id)):
            if a.result_path:
                Path(a.result_path).unlink(missing_ok=True)
            db.delete(a)
        Path(c.path).unlink(missing_ok=True)
        db.delete(c)
    for f in db.exec(select(FitFile).where(FitFile.session_id == sid)):
        db.delete(f)
    db.delete(s)
    db.commit()


# ----------------------------------------------------------------- vidéos
@router.post("/sessions/{sid}/captures", status_code=201)
def upload_capture(sid: int, file: UploadFile = File(...), vue: str = Form("profil"), appareil: str = Form(""),
                   calib_id: Optional[int] = Form(None), db: DB = Depends(get_session)) -> dict:
    from posturale.capture.video import probe

    if not db.get(Seance, sid):
        raise HTTPException(404, "Séance introuvable")
    if vue not in ("profil", "face", "dos"):
        raise HTTPException(400, "Vue inconnue (profil, face, dos)")
    dest = _save_upload(file, "videos", VIDEO_EXT)
    if dest.suffix == ".webm":
        dest = _remux(dest)  # enregistrement du navigateur : durée et index réécrits pour l'analyse
    try:
        meta = probe(dest).as_dict()
    except ValueError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    c = Capture(session_id=sid, vue=vue, appareil=appareil or None, calib_id=calib_id, filename=file.filename or dest.name,
                path=str(dest), meta=meta)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.model_dump(exclude={"path"})


@router.get("/captures/{cid}/video")
def capture_video(cid: int, db: DB = Depends(get_session)):
    c = db.get(Capture, cid)
    if not c or not Path(c.path).exists():
        raise HTTPException(404, "Vidéo introuvable")
    return FileResponse(c.path, filename=c.filename)


class AnalyzeIn(BaseModel):
    duree_s: Optional[float] = 45.0
    debut_s: Optional[float] = None
    pas: int = 1


@router.post("/captures/{cid}/analyze", status_code=202)
def analyze(cid: int, opts: AnalyzeIn, db: DB = Depends(get_session)) -> dict:
    if not db.get(Capture, cid):
        raise HTTPException(404, "Vidéo introuvable")
    a = Analysis(capture_id=cid, message="En file d'attente")
    db.add(a)
    db.commit()
    db.refresh(a)
    jobs.submit(a.id, opts.model_dump())
    return a.model_dump(exclude={"result_path"})


@router.get("/analyses/{aid}")
def get_analysis(aid: int, db: DB = Depends(get_session)) -> dict:
    a = db.get(Analysis, aid)
    if not a:
        raise HTTPException(404, "Analyse introuvable")
    return a.model_dump(exclude={"result_path"})


@router.get("/analyses/{aid}/result")
def analysis_result(aid: int, db: DB = Depends(get_session)) -> Any:
    a = db.get(Analysis, aid)
    if not a or not a.result_path or not Path(a.result_path).exists():
        raise HTTPException(404, "Résultat indisponible")
    return json.loads(Path(a.result_path).read_text(encoding="utf-8"))


# ----------------------------------------------------------------- calibration
@router.get("/calibrations")
def list_calibrations(db: DB = Depends(get_session)) -> list[dict]:
    return [c.model_dump() for c in db.exec(select(CameraCalib).order_by(CameraCalib.id.desc()))]


@router.post("/calibrations", status_code=201)
def create_calibration(file: UploadFile = File(...), camera: str = Form(...), mire: str = Form("A3"),
                       db: DB = Depends(get_session)) -> dict:
    from posturale.calibration.charuco import calibrate_intrinsics, load_board
    from posturale.capture.video import iter_frames, probe

    dest = _save_upload(file, "calibration", VIDEO_EXT)
    try:
        meta = probe(dest)
        step = max(1, int(meta.n_frames / 120))
        frames = (f for _, _, f in iter_frames(dest, 0, None, step))
        intr = calibrate_intrinsics(frames, load_board(mire), camera)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        dest.unlink(missing_ok=True)
    c = CameraCalib(camera=camera, width=intr.width, height=intr.height, rms_px=intr.rms_px, n_views=intr.n_views, data=intr.as_dict())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.model_dump()


# ----------------------------------------------------------------- .FIT
def _capture_windows(db: DB, sid: int) -> dict[int, tuple[datetime, datetime]]:
    """Fenêtre temporelle de chaque prise d'après la date de création de la vidéo (horloge du téléphone)."""
    out = {}
    for c in db.exec(select(Capture).where(Capture.session_id == sid)):
        ct = (c.meta or {}).get("creation_time")
        if not ct:
            continue
        try:
            start = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except ValueError:
            continue
        out[c.id] = (start, start + timedelta(seconds=float(c.meta.get("duration_s") or 60)))
    return out


@router.post("/fit", status_code=201)
def upload_fit(file: UploadFile = File(...), session_id: Optional[int] = Form(None), db: DB = Depends(get_session)) -> dict:
    from posturale.fit.parser import summarize_file

    dest = _save_upload(file, "fit", {".fit"})
    try:
        summary = summarize_file(dest, _capture_windows(db, session_id) if session_id else None)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, f"Fichier .FIT illisible : {exc}") from exc
    f = FitFile(session_id=session_id, filename=file.filename or dest.name, summary=summary)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f.model_dump()


@router.get("/fit")
def list_fit(db: DB = Depends(get_session)) -> list[dict]:
    return [f.model_dump() for f in db.exec(select(FitFile).order_by(FitFile.id.desc()))]
