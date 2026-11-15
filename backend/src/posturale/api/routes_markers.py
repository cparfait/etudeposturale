"""Réglage des couleurs de pastilles : image test, masques, plages HSV enregistrées."""
from __future__ import annotations

import base64
import uuid
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session as DB

from posturale.config import data_dir
from posturale.pose.markers import (
    PRESETS, ColorRange, apply_preset, is_calibrated, color_mask, current_preset, current_ranges, detect_blobs, reset_ranges, save_ranges, sticker_names,
)
from posturale.storage import get_session
from posturale.storage.models import Capture

router = APIRouter(prefix="/api/markers")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_SIDE = 1600  # au-delà, l'image test est réduite (les seuils de surface sont relatifs à la taille)


class Range(BaseModel):
    lo: list[int]
    hi: list[int]


class Colors(BaseModel):
    vert: Range
    orange: Range


def _ranges(c: Colors) -> dict[str, ColorRange]:
    try:
        return {"vert": ColorRange.from_dict(c.vert.model_dump()), "orange": ColorRange.from_dict(c.orange.model_dump())}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _view(r: dict[str, ColorRange]) -> dict:
    return {k: v.as_dict() for k, v in r.items()}


def _frames_dir():
    d = data_dir() / "markers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _data_url(img: np.ndarray, ext: str = ".jpg") -> str:
    ok, buf = cv2.imencode(ext, img, [cv2.IMWRITE_JPEG_QUALITY, 85] if ext == ".jpg" else [])
    if not ok:
        raise HTTPException(500, "Encodage de l'image impossible")
    mime = "image/jpeg" if ext == ".jpg" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(buf.tobytes()).decode()}"


def _store(frame: np.ndarray) -> dict:
    h, w = frame.shape[:2]
    if max(h, w) > MAX_SIDE:
        k = MAX_SIDE / max(h, w)
        frame = cv2.resize(frame, (round(w * k), round(h * k)), interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]
    token = uuid.uuid4().hex
    for old in sorted(_frames_dir().glob("*.png"), key=lambda p: p.stat().st_mtime)[:-5]:
        old.unlink(missing_ok=True)  # on ne garde que les dernières images test
    cv2.imwrite(str(_frames_dir() / f"{token}.png"), frame)
    return {"token": token, "largeur": w, "hauteur": h, "image": _data_url(frame)}


@router.get("/colors")
def get_colors() -> dict:
    from posturale.pose.markers import hue_gap

    pid = current_preset()
    cur = current_ranges()
    base = PRESETS.get(pid, PRESETS["vert_orange"])["plages"]
    gap = hue_gap(cur["vert"], cur["orange"])
    return {"actuel": _view(cur), "defaut": _view(base), "preset": pid, "etalonne": is_calibrated(), "noms": sticker_names(),
            "ecart_teinte": round(gap), "trop_proches": gap < 20,
            "presets": [{"id": k, "nom": v["nom"], "noms": sticker_names(v["plages"])} for k, v in PRESETS.items()]}


class PresetIn(BaseModel):
    id: str


@router.put("/preset")
def put_preset(data: PresetIn) -> dict:
    """Choisit le jeu de couleurs (vert + orange, bleu + rose) : plages de détection et noms dans les textes."""
    try:
        apply_preset(data.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return get_colors()


@router.put("/colors")
def put_colors(c: Colors) -> dict:
    save_ranges(_ranges(c))
    return get_colors()


@router.delete("/colors")
def delete_colors() -> dict:
    reset_ranges()
    return get_colors()


@router.post("/frame", status_code=201)
def frame(file: Optional[UploadFile] = File(None), capture_id: Optional[int] = Form(None), t: float = Form(2.0),
          db: DB = Depends(get_session)) -> dict:
    """Image test : une photo déposée, ou l'image d'une vidéo de séance à l'instant t (s)."""
    if file is not None and file.filename:
        ext = "." + (file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "")
        if ext not in IMAGE_EXT:
            raise HTTPException(400, f"Format d'image non pris en charge ({ext}) : {', '.join(sorted(IMAGE_EXT))}")
        img = cv2.imdecode(np.frombuffer(file.file.read(), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(400, "Image illisible")
        return _store(img)
    if capture_id is None:
        raise HTTPException(400, "Déposer une photo ou choisir une vidéo de séance")
    c = db.get(Capture, capture_id)
    if not c:
        raise HTTPException(404, "Vidéo introuvable")
    cap = cv2.VideoCapture(c.path)
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
        ok, img = cap.read()
    finally:
        cap.release()
    if not ok:
        raise HTTPException(400, "Impossible de lire l'image à cet instant de la vidéo")
    return _store(img)


class TestIn(Colors):
    token: str


@router.post("/test")
def test(data: TestIn) -> dict:
    """Pastilles trouvées et masques pour les plages proposées (sans les enregistrer)."""
    if not data.token.isalnum():
        raise HTTPException(400, "Image test invalide")
    path = _frames_dir() / f"{data.token}.png"
    img = cv2.imread(str(path)) if path.exists() else None
    if img is None:
        raise HTTPException(404, "Image test expirée : la recharger")
    r = _ranges(data)
    out: dict = {}
    for k, rng in r.items():
        mask = color_mask(img, rng)
        rgba = np.zeros((*mask.shape, 4), np.uint8)
        rgba[mask > 0] = (255, 255, 255, 255)
        out[k] = {"pastilles": detect_blobs(img, rng).round(1).tolist(), "masque": _data_url(rgba, ".png"),
                  "couverture_pct": round(float((mask > 0).mean() * 100), 2)}
    return out
