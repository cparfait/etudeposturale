"""Connexion SQLite locale (data/posturale.sqlite)."""
from __future__ import annotations

import threading
from collections.abc import Iterator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from posturale.config import data_dir

_engine: Engine | None = None
_lock = threading.Lock()


def get_engine() -> Engine:
    """Moteur partagé, créé une seule fois.

    Le verrou évite que plusieurs requêtes simultanées au premier démarrage créent les tables
    en même temps (« table profile already exists »).
    """
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                engine = create_engine(
                    f"sqlite:///{data_dir() / 'posturale.sqlite'}", connect_args={"check_same_thread": False}
                )
                SQLModel.metadata.create_all(engine)
                _engine = engine
    return _engine


def set_engine(engine: Engine) -> None:
    """Pour les tests : base en mémoire."""
    global _engine
    _engine = engine
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
