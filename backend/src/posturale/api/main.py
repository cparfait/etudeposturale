"""API locale (FastAPI). Lancement : uvicorn posturale.api.main:app --reload"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from posturale import __version__
from posturale.config import load_metrics
from posturale.storage import get_session
from posturale.storage.models import (
    Bike,
    BikeBase,
    BikeConfig,
    BikeConfigBase,
    BikeConfigRead,
    Profile,
    ProfileBase,
    now,
)

app = FastAPI(title="Étude posturale vélo", version=__version__)

from posturale.api.routes_capture import router as capture_router  # noqa: E402
from posturale.api.routes_health import router as health_router  # noqa: E402
from posturale.api.routes_markers import router as markers_router  # noqa: E402

app.include_router(capture_router)
app.include_router(health_router)
app.include_router(markers_router)

SINGLETON = 1


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    """Référentiel des métriques (plages sourcées, seuils, avertissement)."""
    return load_metrics()


# ----------------------------------------------------------------- profil
@app.get("/api/profile", response_model=ProfileBase)
def get_profile(session: Session = Depends(get_session)) -> Profile | ProfileBase:
    return session.get(Profile, SINGLETON) or ProfileBase()


@app.put("/api/profile", response_model=ProfileBase)
def put_profile(data: ProfileBase, session: Session = Depends(get_session)) -> Profile:
    profile = session.get(Profile, SINGLETON) or Profile(id=SINGLETON)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    profile.updated_at = now()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


# ----------------------------------------------------------------- vélo
def _bike(session: Session) -> Bike:
    bike = session.get(Bike, SINGLETON)
    if bike is None:
        bike = Bike(id=SINGLETON)
        session.add(bike)
        session.commit()
        session.refresh(bike)
    return bike


@app.get("/api/bike", response_model=BikeBase)
def get_bike(session: Session = Depends(get_session)) -> Bike:
    return _bike(session)


@app.put("/api/bike", response_model=BikeBase)
def put_bike(data: BikeBase, session: Session = Depends(get_session)) -> Bike:
    bike = _bike(session)
    for key, value in data.model_dump().items():
        setattr(bike, key, value)
    bike.updated_at = now()
    session.add(bike)
    session.commit()
    session.refresh(bike)
    return bike


@app.get("/api/bike/configs", response_model=list[BikeConfigRead])
def list_configs(session: Session = Depends(get_session)) -> list[BikeConfig]:
    """Historique des configurations, la plus récente en premier."""
    stmt = select(BikeConfig).order_by(BikeConfig.created_at.desc(), BikeConfig.id.desc())
    return list(session.exec(stmt))


@app.get("/api/bike/configs/current", response_model=BikeConfigRead | None)
def current_config(session: Session = Depends(get_session)) -> BikeConfig | None:
    configs = list_configs(session)
    return configs[0] if configs else None


@app.post("/api/bike/configs", response_model=BikeConfigRead, status_code=201)
def create_config(data: BikeConfigBase, session: Session = Depends(get_session)) -> BikeConfig:
    """Nouvelle configuration (jamais d'écrasement : l'ancienne reste dans l'historique)."""
    bike = _bike(session)
    config = BikeConfig(**data.model_dump(), bike_id=bike.id)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


@app.get("/api/bike/configs/{config_id}", response_model=BikeConfigRead)
def get_config(config_id: int, session: Session = Depends(get_session)) -> BikeConfig:
    config = session.get(BikeConfig, config_id)
    if config is None:
        raise HTTPException(404, "Configuration introuvable")
    return config
