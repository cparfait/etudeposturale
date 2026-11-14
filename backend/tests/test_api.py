import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from posturale.api.main import app
from posturale.storage import set_engine


@pytest.fixture()
def client():
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


def test_metrics_served(client):
    data = client.get("/api/metrics").json()
    assert data["metrics"]["P1"]["plage"]["dynamique"] == {
        "min": 30, "max": 40, "source": ["ferrer_roca2012", "bike_fitting_review"], "fiabilite": "etude"}


def test_profile_roundtrip(client):
    assert client.get("/api/profile").json()["taille_cm"] is None
    r = client.put("/api/profile", json={"taille_cm": 185, "entrejambe_mm": 880, "poids_kg": 78})
    assert r.status_code == 200
    assert client.get("/api/profile").json()["entrejambe_mm"] == 880


def test_profile_validation(client):
    assert client.put("/api/profile", json={"taille_cm": 20}).status_code == 422


def test_bike_and_config_history(client):
    client.put("/api/bike", json={"modele": "Allez Sport", "taille": "61", "angle_tube_selle_deg": 73})
    assert client.get("/api/bike").json()["angle_tube_selle_deg"] == 73
    assert client.get("/api/bike/configs/current").json() is None
    first = client.post("/api/bike/configs", json={"hauteur_selle_mm": 760, "libelle": "Départ"}).json()
    second = client.post("/api/bike/configs", json={"hauteur_selle_mm": 755}).json()
    assert first["manivelle_mm"] == 175
    history = client.get("/api/bike/configs").json()
    assert [c["id"] for c in history] == [second["id"], first["id"]]
    assert client.get("/api/bike/configs/current").json()["hauteur_selle_mm"] == 755
    assert client.get(f"/api/bike/configs/{first['id']}").json()["libelle"] == "Départ"
    assert client.get("/api/bike/configs/999").status_code == 404
