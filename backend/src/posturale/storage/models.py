"""Modèle de données (SQLite). Un seul utilisateur : profil et vélo sont des singletons (id = 1).

Chaque modification des cotes crée une nouvelle `BikeConfig` datée : on ne les écrase jamais,
ce qui donne l'historique des configurations et les comparaisons avant/après.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class ProfileBase(SQLModel):
    taille_cm: Optional[float] = Field(default=None, ge=100, le=230)
    entrejambe_mm: Optional[float] = Field(default=None, ge=500, le=1100)
    poids_kg: Optional[float] = Field(default=None, ge=30, le=200)
    pointure: Optional[float] = Field(default=None, ge=30, le=52)
    annee_naissance: Optional[int] = Field(default=None, ge=1920, le=2020)
    niveau: Optional[str] = None
    volume_hebdo_h: Optional[float] = Field(default=None, ge=0, le=40)
    objectif: str = "performance_confort"
    notes: Optional[str] = None


class Profile(ProfileBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    updated_at: datetime = Field(default_factory=now)


class BikeBase(SQLModel):
    marque: Optional[str] = "Specialized"
    modele: Optional[str] = None
    annee: Optional[int] = Field(default=None, ge=1980, le=2100)
    taille: Optional[str] = None
    discipline: str = "route"
    # Géométrie (fiche constructeur) — l'angle du tube de selle sert à la correction en mm
    angle_tube_selle_deg: Optional[float] = Field(default=None, ge=65, le=80)
    stack_mm: Optional[float] = Field(default=None, ge=400, le=750)
    reach_mm: Optional[float] = Field(default=None, ge=300, le=500)


class Bike(BikeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    updated_at: datetime = Field(default_factory=now)


class BikeConfigBase(SQLModel):
    libelle: Optional[str] = None
    # B1–B8 (docs/01_metriques.md § 4)
    hauteur_selle_mm: Optional[float] = Field(default=None, ge=500, le=1000)
    recul_selle_mm: Optional[float] = Field(default=None, ge=0, le=150)
    inclinaison_selle_deg: Optional[float] = Field(default=None, ge=-15, le=15)
    drop_selle_cintre_mm: Optional[float] = Field(default=None, ge=-100, le=200)
    distance_selle_cintre_mm: Optional[float] = Field(default=None, ge=300, le=800)
    potence_mm: Optional[float] = Field(default=None, ge=40, le=160)
    potence_angle_deg: Optional[float] = Field(default=None, ge=-30, le=30)
    entretoises_mm: Optional[float] = Field(default=None, ge=0, le=80)
    largeur_cintre_mm: Optional[float] = Field(default=None, ge=300, le=500)
    manivelle_mm: float = Field(default=175, ge=150, le=185)
    selle: Optional[str] = None
    # B9 — pédales, cales, chaussures
    pedales: Optional[str] = None
    cales_modele: Optional[str] = None
    cales_liberte: Optional[str] = None
    cales_avance_mm: Optional[float] = Field(default=None, ge=-30, le=30)
    cales_rotation_g_deg: Optional[float] = Field(default=None, ge=-15, le=15)
    cales_rotation_d_deg: Optional[float] = Field(default=None, ge=-15, le=15)
    cales_lateral_g_mm: Optional[float] = Field(default=None, ge=-15, le=15)
    cales_lateral_d_mm: Optional[float] = Field(default=None, ge=-15, le=15)
    rondelles: Optional[str] = None
    chaussures: Optional[str] = None
    semelles: Optional[str] = None
    notes: Optional[str] = None


class BikeConfig(BikeConfigBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bike_id: int = Field(default=1, foreign_key="bike.id")
    created_at: datetime = Field(default_factory=now)


class BikeConfigRead(BikeConfigBase):
    id: int
    bike_id: int
    created_at: datetime


# ============================================================ séances, vidéos, analyses
from typing import Any  # noqa: E402

from sqlalchemy import JSON, Column  # noqa: E402


class Session(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    bike_config_id: Optional[int] = Field(default=None, foreign_key="bikeconfig.id")
    etat: str = "repose"                 # repose | fin_effort
    puissance_cible_w: Optional[float] = None
    notes: Optional[str] = None


class CameraCalib(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    camera: str
    width: int
    height: int
    rms_px: float
    n_views: int
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Capture(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    session_id: int = Field(foreign_key="session.id")
    vue: str = "profil"                  # profil | face | dos
    appareil: Optional[str] = None
    calib_id: Optional[int] = Field(default=None, foreign_key="cameracalib.id")
    filename: str
    path: str
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Analysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    finished_at: Optional[datetime] = None
    capture_id: int = Field(foreign_key="capture.id")
    status: str = "en_attente"           # en_attente | en_cours | terminee | erreur
    progress: float = 0.0
    message: Optional[str] = None
    error: Optional[str] = None
    result_path: Optional[str] = None
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class FitFile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id")
    filename: str
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


# ============================================================ santé : douleurs, auto-tests, ressentis
class PainEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    zone: str
    cote: str = "D"                      # G | D | centre
    intensite: int = Field(default=3, ge=0, le=10)
    moment: Optional[str] = None         # ex. « après 3 h », « en montée », « au repos »
    depuis: Optional[str] = None
    active: bool = True
    notes: Optional[str] = None


class SelfTest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    test_id: str
    cote: Optional[str] = None
    valeur: Optional[float] = None
    resultat: Optional[str] = None
    notes: Optional[str] = None


class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)
    bike_config_id: Optional[int] = Field(default=None, foreign_key="bikeconfig.id")
    duree_min: Optional[float] = Field(default=None, ge=0, le=1440)
    distance_km: Optional[float] = Field(default=None, ge=0, le=1000)
    rpe: Optional[int] = Field(default=None, ge=1, le=10)
    confort_selle: Optional[int] = Field(default=None, ge=0, le=10)
    puissance_ressentie: Optional[int] = Field(default=None, ge=0, le=10)
    engourdissements: Optional[str] = None
    douleurs: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # {"genou_avant_G": 4, ...}
    notes: Optional[str] = None
