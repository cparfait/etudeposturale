"""Séance guidée : plan (adapté par l'IA en option), débrief, application de la modification retenue."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session as DB, select

from posturale.guide import debrief, plan
from posturale.storage import get_session
from posturale.storage.models import BikeConfig, BikeConfigBase, Session as Seance

router = APIRouter(prefix="/api/guide")


@router.get("/plan")
def get_plan(db: DB = Depends(get_session)) -> dict:
    return plan.build(db)


@router.post("/plan/ia")
def ai_plan(db: DB = Depends(get_session)) -> dict:
    return plan.adapt(db)


class StartIn(BaseModel):
    type: str = "premiere"
    puissance_w: float | None = None


@router.post("/start", status_code=201)
def start(data: StartIn, db: DB = Depends(get_session)) -> dict:
    """Crée la séance de capture rattachée à la configuration en cours."""
    current = db.exec(select(BikeConfig).order_by(BikeConfig.created_at.desc(), BikeConfig.id.desc())).first()
    labels = {"premiere": "première séance", "verification": "vérification", "suivi": "suivi"}
    s = Seance(etat="repose", puissance_cible_w=data.puissance_w, bike_config_id=current.id if current else None,
               notes=f"Séance guidée ({labels.get(data.type, data.type)})")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s.model_dump()


@router.get("/debrief/{sid}")
def get_debrief(sid: int, db: DB = Depends(get_session)) -> dict:
    try:
        return debrief.build(db, sid)
    except KeyError:
        raise HTTPException(404, "Séance introuvable") from None


class ApplyIn(BaseModel):
    champ: str
    delta: float


@router.post("/apply/{sid}", status_code=201)
def apply(sid: int, data: ApplyIn, db: DB = Depends(get_session)) -> dict:
    """Nouvelle configuration = configuration de la séance + la modification (l'ancienne reste dans l'historique)."""
    s = db.get(Seance, sid)
    if not s:
        raise HTTPException(404, "Séance introuvable")
    if data.champ not in debrief.APPLICABLE or not 0 < abs(data.delta) <= 15:
        raise HTTPException(400, "Modification non applicable automatiquement")
    base = db.get(BikeConfig, s.bike_config_id) if s.bike_config_id else None
    if not base or getattr(base, data.champ) is None:
        raise HTTPException(400, f"{debrief.APPLICABLE[data.champ]} actuelle inconnue : renseigne-la dans « Mon vélo ».")
    values = BikeConfigBase(**base.model_dump(exclude={"id", "bike_id", "created_at"})).model_dump()
    values[data.champ] = round(values[data.champ] + data.delta, 1)
    sign = "+" if data.delta > 0 else "−"
    values["libelle"] = f"Séance guidée du {datetime.now():%d/%m} : {debrief.APPLICABLE[data.champ].lower()} {sign}{abs(data.delta):g} mm"
    cfg = BikeConfig(**BikeConfigBase(**values).model_dump(), bike_id=base.bike_id)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg.model_dump()
