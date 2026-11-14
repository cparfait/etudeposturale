"""Douleurs, auto-tests, ressentis, recommandations et données du rapport."""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session as DB, select

from posturale.config import load_metrics
from posturale.health.catalog import PAIN_ZONES, SELF_TESTS
from posturale.health.rules import Context, evaluate
from posturale.storage import get_session
from posturale.storage.models import (
    Analysis, Bike, BikeConfig, Capture, Feedback, FitFile, PainEntry, Profile, SelfTest, Session as Seance,
)

router = APIRouter(prefix="/api")


@router.get("/catalog")
def catalog() -> dict:
    return {"zones": PAIN_ZONES, "tests": SELF_TESTS}


# ----------------------------------------------------------------- douleurs
class PainIn(BaseModel):
    zone: str
    cote: str = "D"
    intensite: int = Field(3, ge=0, le=10)
    moment: Optional[str] = None
    depuis: Optional[str] = None
    active: bool = True
    notes: Optional[str] = None


def _crud(model, item_in):
    def create(data: item_in, db: DB = Depends(get_session)) -> dict:  # type: ignore[valid-type]
        obj = model(**data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj.model_dump()

    def update(oid: int, data: item_in, db: DB = Depends(get_session)) -> dict:  # type: ignore[valid-type]
        obj = db.get(model, oid)
        if not obj:
            raise HTTPException(404, "Introuvable")
        for k, v in data.model_dump().items():
            setattr(obj, k, v)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj.model_dump()

    def listing(db: DB = Depends(get_session)) -> list[dict]:
        return [o.model_dump() for o in db.exec(select(model).order_by(model.id.desc()))]

    def delete(oid: int, db: DB = Depends(get_session)) -> None:
        obj = db.get(model, oid)
        if not obj:
            raise HTTPException(404, "Introuvable")
        db.delete(obj)
        db.commit()

    return create, update, listing, delete


class SelfTestIn(BaseModel):
    test_id: str
    cote: Optional[str] = None
    valeur: Optional[float] = None
    resultat: Optional[str] = None
    notes: Optional[str] = None


class FeedbackIn(BaseModel):
    bike_config_id: Optional[int] = None
    duree_min: Optional[float] = Field(None, ge=0, le=1440)
    distance_km: Optional[float] = Field(None, ge=0, le=1000)
    rpe: Optional[int] = Field(None, ge=1, le=10)
    confort_selle: Optional[int] = Field(None, ge=0, le=10)
    puissance_ressentie: Optional[int] = Field(None, ge=0, le=10)
    engourdissements: Optional[str] = None
    douleurs: dict[str, int] = {}
    notes: Optional[str] = None


for path, model, item_in in (("pains", PainEntry, PainIn), ("selftests", SelfTest, SelfTestIn), ("feedback", Feedback, FeedbackIn)):
    c, u, l, d = _crud(model, item_in)
    router.add_api_route(f"/{path}", c, methods=["POST"], status_code=201)
    router.add_api_route(f"/{path}/{{oid}}", u, methods=["PUT"])
    router.add_api_route(f"/{path}", l, methods=["GET"])
    router.add_api_route(f"/{path}/{{oid}}", d, methods=["DELETE"], status_code=204)


# ----------------------------------------------------------------- synthèse
def _latest_results(db: DB) -> dict:
    """Dernière analyse terminée par vue (et par côté pour le profil)."""
    out: dict = {"profil": {}, "face": None, "dos": None}
    rows = db.exec(select(Analysis, Capture).where(Analysis.capture_id == Capture.id, Analysis.status == "terminee")
                   .order_by(Analysis.id.desc()))
    for a, c in rows:
        if not a.result_path or not Path(a.result_path).exists():
            continue
        if c.vue == "profil":
            side = (a.summary or {}).get("cote")
            if side and side not in out["profil"]:
                res = json.loads(Path(a.result_path).read_text(encoding="utf-8"))
                res.pop("overlay", None)
                out["profil"][side] = {**res, "analysis_id": a.id, "capture_id": c.id, "session_id": c.session_id}
        elif out[c.vue] is None:
            res = json.loads(Path(a.result_path).read_text(encoding="utf-8"))
            out[c.vue] = {**res, "analysis_id": a.id, "capture_id": c.id}
    return out


def _context(db: DB) -> tuple[Context, dict]:
    latest = _latest_results(db)
    config = db.exec(select(BikeConfig).order_by(BikeConfig.created_at.desc(), BikeConfig.id.desc())).first()
    fit = db.exec(select(FitFile).order_by(FitFile.id.desc())).first()
    ctx = Context(
        profil=latest["profil"], face=latest["face"], dos=latest["dos"],
        douleurs=[p.model_dump() for p in db.exec(select(PainEntry).where(PainEntry.active == True))],  # noqa: E712
        tests=[t.model_dump() for t in db.exec(select(SelfTest).order_by(SelfTest.id))],
        fit=fit.summary if fit else None,
        ressentis=[f.model_dump() for f in db.exec(select(Feedback).order_by(Feedback.id))],
        config=config.model_dump() if config else None,
    )
    return ctx, latest


@router.get("/recommendations")
def recommendations(db: DB = Depends(get_session)) -> dict:
    ctx, _ = _context(db)
    return {"hypotheses": evaluate(ctx), "avertissement": load_metrics()["avertissement"]}


@router.get("/report")
def report(db: DB = Depends(get_session)) -> dict:
    ctx, latest = _context(db)
    profile = db.get(Profile, 1)
    bike = db.get(Bike, 1)
    configs = [c.model_dump() for c in db.exec(select(BikeConfig).order_by(BikeConfig.created_at, BikeConfig.id))]
    # Évolution de l'extension du genou au fil des séances (avant / après)
    evolution = []
    rows = db.exec(select(Analysis, Capture, Seance).where(Analysis.capture_id == Capture.id, Capture.session_id == Seance.id,
                                                            Analysis.status == "terminee", Capture.vue == "profil").order_by(Analysis.id))
    for a, c, s in rows:
        m = (a.summary or {}).get("metriques", {})
        evolution.append({"date": s.created_at.isoformat(), "session_id": s.id, "bike_config_id": s.bike_config_id,
                          "etat": s.etat, "cote": (a.summary or {}).get("cote"),
                          "P1": m.get("P1", {}).get("moyenne"), "P2": m.get("P2", {}).get("moyenne"),
                          "verdict": ((a.summary or {}).get("verdict_selle") or {}).get("statut")})
    return {
        "profil": profile.model_dump() if profile else None,
        "velo": bike.model_dump() if bike else None,
        "configurations": configs,
        "analyses": latest,
        "evolution": evolution,
        "douleurs": ctx.douleurs,
        "tests": ctx.tests,
        "ressentis": ctx.ressentis,
        "fit": ctx.fit,
        "hypotheses": evaluate(ctx),
        "metrics": load_metrics()["metrics"],
        "avertissement": load_metrics()["avertissement"],
    }
