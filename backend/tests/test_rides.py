import io
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from fitgen import activity
from posturale.api.main import app
from posturale.fit import rides as R
from posturale.fit.parser import summarize_file
from posturale.storage import set_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


T0 = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)


def test_generated_fit_is_read(tmp_path):
    p = tmp_path / "a.fit"
    p.write_bytes(activity(T0, 30, left_pct=47, power=210, hr=150))
    s = summarize_file(p)
    assert s["sport"] == "cycling" and s["distance_km"] == 15.0 and s["mouvement_min"] == 30.0
    g = s["global"]
    assert g["puissance_w"] == 210 and g["equilibre_gauche_pct"] == 47 and g["efficacite_couple"] == [75.0, 77.0]


def test_expand_zip_and_sport_filter():
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("123_ACTIVITY.fit", activity(T0, 10))
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:          # export complet : zip dans zip
        z.writestr("DI_CONNECT/UploadedFiles_0.zip", inner.getvalue())
        z.writestr("notes.txt", "x")
    assert [n for n, _ in R.expand("export.zip", outer.getvalue())] == ["123_ACTIVITY.fit"]
    assert R.is_cycling({"sport": "running", "global": {"cadence_rpm": 170}}) is False
    assert R.is_cycling({"sport": None, "global": {"puissance_w": 180}}) is True


def test_import_dedup_and_compare(client):
    # configuration 1 (selle 765) puis 2 (selle 760) : les sorties se rangent selon leur date
    c1 = client.post("/api/bike/configs", json={"libelle": "Départ", "hauteur_selle_mm": 765}).json()
    imp = lambda name, data: client.post("/api/rides/import", files={"file": (name, data, "application/octet-stream")}).json()
    before = [activity(T0 - timedelta(days=d), 120, left_pct=46, left_pct_end=44, power=190, hr=150) for d in (10, 5)]
    # on force la date de la config 1 dans le passé pour que les sorties « avant » lui appartiennent
    from posturale.storage import get_session
    from posturale.storage.models import BikeConfig
    db = next(get_session())
    cfg = db.get(BikeConfig, c1["id"])
    cfg.created_at = (T0 - timedelta(days=30))
    db.add(cfg); db.commit()
    for i, b in enumerate(before):
        assert imp(f"b{i}.fit", b)["importees"] == 1
    assert imp("b0-copie.fit", before[0])["doublons"] == 1                 # même sortie : ignorée
    assert imp("course.fit", activity(T0, 40, sport="running"))["autres_sports"] == 1
    c2 = client.post("/api/bike/configs", json={"libelle": "Selle -5 mm", "hauteur_selle_mm": 760}).json()
    cfg2 = db.get(BikeConfig, c2["id"])
    cfg2.created_at = (T0 - timedelta(days=1))
    db.add(cfg2); db.commit()
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as z:
        z.writestr("after1.fit", activity(T0 + timedelta(days=2), 120, left_pct=49, left_pct_end=48.5, power=195, hr=146))
        z.writestr("after2.fit", activity(T0 + timedelta(days=4), 90, left_pct=49, power=200, hr=147))
    assert imp("garmin.zip", zbuf.getvalue())["importees"] == 2

    rides = client.get("/api/rides").json()
    assert len(rides) == 4 and rides[0]["config"] == "Selle -5 mm" and rides[-1]["config"] == "Départ"
    cmp = client.get("/api/rides/compare").json()
    assert cmp["avant"]["libelle"] == "Départ" and cmp["apres"]["libelle"] == "Selle -5 mm"
    e = cmp["ecarts"]
    assert e["equilibre_gauche_pct"] > 2 and e["asymetrie"] < 0           # plus proche de 50/50
    assert e["w_par_bpm"] > 0                                              # plus de watts pour le même cardio
    assert -2.0 < cmp["avant"]["derive_equilibre"] < -0.5                # la jambe gauche faiblit au fil de la sortie
    client.delete(f"/api/rides/{rides[0]['id']}")
    assert len(client.get("/api/rides").json()) == 3
