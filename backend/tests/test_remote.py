import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from posturale.api import routes_remote
from posturale.api.main import app
from posturale.storage import set_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    routes_remote._pairs.clear()
    return TestClient(app)


def test_pairing_roles_and_commands(client):
    sid = client.post("/api/sessions", json={}).json()["id"]
    p = client.post("/api/remote", json={"session_id": sid}).json()
    code = p["code"]
    assert len(code) == 6 and client.post("/api/remote", json={"session_id": sid}).json()["code"] == code  # même code
    a = client.post(f"/api/remote/{code.lower()}/join", json={"nom": "Pixel", "secure": True}).json()
    b = client.post(f"/api/remote/{code}/join", json={"nom": "Galaxy", "secure": True}).json()
    assert (a["role"], b["role"]) == ("profil_D", "profil_G")                # 1er à droite, 2e à gauche
    assert client.post(f"/api/remote/{code}/poll", json={"appareil": a["appareil"]}).json()["commande"] is None
    client.post(f"/api/remote/{code}/command", json={"action": "start", "cles": ["profil_G"], "duree_s": 60})
    assert client.post(f"/api/remote/{code}/poll", json={"appareil": a["appareil"]}).json()["commande"] is None  # pas concerné
    cmd = client.post(f"/api/remote/{code}/poll", json={"appareil": b["appareil"], "etat": "enregistre"}).json()["commande"]
    assert cmd["action"] == "start" and cmd["duree_s"] == 60
    client.post(f"/api/remote/{code}/poll", json={"appareil": b["appareil"], "etat": "envoye", "capture_id": 42})
    st = client.get(f"/api/remote/{code}").json()
    dev = {d["nom"]: d for d in st["appareils"]}
    assert dev["Galaxy"]["capture_id"] == 42 and dev["Galaxy"]["etat"] == "envoye" and dev["Galaxy"]["connecte"]
    client.put(f"/api/remote/{code}/appareils/{a['appareil']}", json={"role": "face"})
    assert client.post(f"/api/remote/{code}/poll", json={"appareil": a["appareil"]}).json()["role"] == "face"
    assert client.put(f"/api/remote/{code}/appareils/{a['appareil']}", json={"role": "plafond"}).status_code == 400
    assert client.post("/api/remote/ZZZZZZ/join", json={}).status_code == 404
    assert client.post(f"/api/remote/{code}/poll", json={"appareil": "inconnu"}).status_code == 404


def test_lan_address_endpoint(client):
    ips = client.get("/api/remote/address").json()["adresses"]
    assert isinstance(ips, list) and all(not ip.startswith("127.") for ip in ips)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg absent")
def test_browser_webm_is_remuxed(client, tmp_path):
    """Un WebM enregistré par le navigateur (souvent sans durée) est réécrit en .mkv lisible par l'analyse."""
    src = tmp_path / "rec.webm"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=2",
                    "-c:v", "libvpx-vp9", "-b:v", "500k", str(src)], check=True, timeout=120)
    sid = client.post("/api/sessions", json={}).json()["id"]
    with src.open("rb") as f:
        cap = client.post(f"/api/sessions/{sid}/captures", files={"file": ("rec.webm", f, "video/webm")}, data={"vue": "profil"}).json()
    assert cap["meta"]["duration_s"] > 1.5 and round(cap["meta"]["fps"]) == 30
    assert list((tmp_path / "data" / "videos").glob("*.mkv"))
