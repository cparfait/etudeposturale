from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from posturale.analysis import jobs
from posturale.api.main import app
from posturale.fit.parser import by_hour, decode_balance, summarize
from posturale.storage import set_engine

from synthetic_video import FakeEngine, render


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


def test_full_flow(client, tmp_path):
    video = tmp_path / "profil.mp4"
    px = render(video, saddle_mm=750.0, forward="right", seconds=10)
    jobs.engine_factory = lambda: FakeEngine(px)
    try:
        client.put("/api/bike", json={"angle_tube_selle_deg": 73.5})
        client.post("/api/bike/configs", json={"hauteur_selle_mm": 760, "manivelle_mm": 175})
        s = client.post("/api/sessions", json={"etat": "repose"}).json()
        assert s["config"]["hauteur_selle_mm"] == 760

        with video.open("rb") as f:
            r = client.post(f"/api/sessions/{s['id']}/captures", files={"file": ("profil.mp4", f, "video/mp4")}, data={"vue": "profil"})
        assert r.status_code == 201, r.text
        cap = r.json()
        assert cap["meta"]["fps"] == pytest.approx(60, abs=0.5)

        a = client.post(f"/api/captures/{cap['id']}/analyze", json={"debut_s": 0, "duree_s": None}).json()
        jobs.wait_idle(300)
        a = client.get(f"/api/analyses/{a['id']}").json()
        assert a["status"] == "terminee", a
        assert a["summary"]["verdict_selle"]["statut"] == "trop_tendu"
        full = client.get(f"/api/analyses/{a['id']}/result").json()
        assert len(full["overlay"]["temps"]) > 100

        assert client.get(f"/api/captures/{cap['id']}/video").status_code == 200
        sess = client.get(f"/api/sessions/{s['id']}").json()
        assert sess["captures"][0]["analyses"][0]["status"] == "terminee"

        # Douleur arrière du genou droit + auto-test → hypothèse « selle haute » prioritaire
        client.post("/api/pains", json={"zone": "genou_arriere_ext", "cote": "D", "intensite": 4, "moment": "après 3 h de sortie"})
        client.post("/api/selftests", json={"test_id": "T4", "cote": "D", "valeur": 65})
        rec = client.get("/api/recommendations").json()["hypotheses"]
        ids = [h["id"] for h in rec]
        assert "selle_haute_D" in ids and "charge" in ids
        assert ids.index("charge") < ids.index("selle_haute_D")
        haute = next(h for h in rec if h["id"] == "selle_haute_D")
        assert haute["priorite"] == "haute" and any("Ischio" in c for c in haute["constats"])

        rep = client.get("/api/report").json()
        assert rep["evolution"][0]["verdict"] == "trop_tendu"
        assert "D" in rep["analyses"]["profil"]

        assert client.delete(f"/api/sessions/{s['id']}").status_code == 204
    finally:
        jobs.engine_factory = None


def test_pain_validation_and_red_flag(client):
    assert client.post("/api/pains", json={"zone": "genou_avant", "intensite": 12}).status_code == 422
    client.post("/api/pains", json={"zone": "genou_avant", "cote": "G", "intensite": 8})
    rec = client.get("/api/recommendations").json()["hypotheses"]
    assert rec[0]["id"] == "alerte_medicale"


def test_catalog(client):
    cat = client.get("/api/catalog").json()
    assert any(z["id"] == "genou_avant" for z in cat["zones"])
    assert any(t["id"] == "T4" for t in cat["tests"])


def test_fit_balance_and_summary():
    assert decode_balance(0x80 | 52) == 48.0      # 52 % à droite → 48 % à gauche
    assert decode_balance(52) is None             # côté non indiqué
    t0 = datetime(2026, 10, 18, 8, tzinfo=timezone.utc)
    recs = []
    for i in range(7200):  # 2 h ; la jambe gauche faiblit la 2e heure
        left = 50 if i < 3600 else 47
        recs.append({"timestamp": t0 + timedelta(seconds=i), "power": 170, "cadence": 85, "heart_rate": 130,
                     "left_right_balance": 0x80 | (100 - left), "left_power_phase": (350.0, 200.0)})
    s = summarize(recs)
    assert s["puissance_w"] == 170 and s["equilibre_gauche_pct"] == pytest.approx(48.5)
    assert s["phase_puissance_g"] == [350.0, 200.0]
    h = by_hour(recs)
    assert [x["equilibre_gauche_pct"] for x in h[:2]] == [50.0, 47.0]
