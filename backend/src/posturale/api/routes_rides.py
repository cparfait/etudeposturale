"""Mes sorties : import en lot de fichiers .FIT (ou .zip de Garmin Connect) et comparaison avant / après réglage."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session as DB, select

from posturale.fit import rides as R
from posturale.storage import get_session
from posturale.storage.models import FitFile

router = APIRouter(prefix="/api/rides")


def _rides(db: DB) -> list[FitFile]:
    return list(db.exec(select(FitFile).where(FitFile.session_id == None)))  # noqa: E711 (sorties hors séance)




@router.post("/import")
async def import_rides(file: UploadFile = File(...), db: DB = Depends(get_session)) -> dict:
    """Un fichier par requête (l'interface envoie les fichiers un par un pour afficher la progression).
    Un .zip peut contenir plusieurs sorties : export « original » d'une activité ou export complet du compte Garmin."""
    from posturale.config import data_dir
    from posturale.fit.parser import summarize_file

    data = await file.read()
    fits = R.expand(file.filename or "fichier.fit", data)
    if not fits:
        raise HTTPException(400, "Aucun fichier .FIT dans ce dépôt (attendu : .fit, ou .zip exporté de Garmin Connect).")
    seen = {(f.summary or {}).get("debut") for f in _rides(db)}
    folder = data_dir() / "fit" / "sorties"
    folder.mkdir(parents=True, exist_ok=True)
    res = {"importees": 0, "doublons": 0, "autres_sports": 0, "illisibles": 0, "sorties": []}
    for name, blob in fits:
        with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
            tmp.write(blob)
        try:
            summary = summarize_file(tmp.name)
        except Exception:
            res["illisibles"] += 1
            continue
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        if not R.is_cycling(summary):
            res["autres_sports"] += 1
            continue
        if summary["debut"] in seen:
            res["doublons"] += 1
            continue
        seen.add(summary["debut"])
        dest = folder / f"{summary['debut'][:19].replace(':', '-')}_{hashlib.sha1(blob).hexdigest()[:8]}.fit"
        dest.write_bytes(blob)
        f = FitFile(session_id=None, filename=name, summary=summary)
        db.add(f)
        res["importees"] += 1
        res["sorties"].append(summary["debut"])
    db.commit()
    return res


@router.get("")
def list_rides(db: DB = Depends(get_session)) -> list[dict]:
    return R.load(db)[0]


@router.get("/compare")
def compare(db: DB = Depends(get_session)) -> dict:
    rides, configs = R.load(db)
    return R.compare(rides, configs)


@router.get("/{rid}")
def ride_detail(rid: int, db: DB = Depends(get_session)) -> dict:
    """Une sortie en détail : série toutes les 5 min (fichier gardé à l'import), jambes gauche / droite, lecture."""
    from posturale.storage.models import BikeConfig

    f = db.get(FitFile, rid)
    if not f or f.session_id is not None:
        raise HTTPException(404, "Sortie introuvable")
    return R.detail(f, list(db.exec(select(BikeConfig))))


@router.delete("/{rid}", status_code=204)
def delete_ride(rid: int, db: DB = Depends(get_session)) -> None:
    f = db.get(FitFile, rid)
    if not f or f.session_id is not None:
        raise HTTPException(404, "Sortie introuvable")
    db.delete(f)
    db.commit()
