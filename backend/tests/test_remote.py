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
    routes_remote._live.clear()
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


def test_local_https_authority(client, tmp_path):
    assert client.get("/api/remote/address").json()["autorite"] is False
    assert client.get("/api/remote/autorite.crt").status_code == 404
    pytest.importorskip("cryptography")
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("https_local", Path(__file__).resolve().parents[2] / "scripts" / "https_local.py")
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    h.CA_DIR, h.CERT_DIR = tmp_path / "data" / "https", tmp_path / "certs"
    assert h.issue_server_cert() is True and h.issue_server_cert() is False      # rien à refaire si l'IP n'a pas changé
    pem = (tmp_path / "certs" / "cert.pem").read_text()
    assert pem.count("BEGIN CERTIFICATE") == 2                                    # certificat + autorité (chaîne complète)
    assert "localhost" in h.current_sans(tmp_path / "certs" / "cert.pem")
    assert client.get("/api/remote/address").json()["autorite"] is True
    r = client.get("/api/remote/autorite.crt")
    assert r.status_code == 200 and b"BEGIN CERTIFICATE" in r.content and b"PRIVATE" not in r.content


def test_live_preview_relay(client):
    code = client.post("/api/remote", json={}).json()["code"]                 # cadrage seul : pas de séance
    did = client.post(f"/api/remote/{code}/join", json={"nom": "Pixel", "secure": True}).json()["appareil"]
    assert client.post(f"/api/remote/{code}/poll", json={"appareil": did}).json()["apercu"] is False
    with client.websocket_connect(f"/api/remote/{code}/apercu/{did}") as viewer:
        poll = client.post(f"/api/remote/{code}/poll", json={"appareil": did, "largeur": 1920, "hauteur": 1080}).json()
        assert poll["apercu"] is True and poll["session_id"] is None             # un écran regarde : le téléphone envoie
        with client.websocket_connect(f"/api/remote/{code}/flux/{did}") as phone:
            phone.send_bytes(b"jpeg-1")
            assert viewer.receive_bytes() == b"jpeg-1"
            phone.send_bytes(b"jpeg-2")
            assert viewer.receive_bytes() == b"jpeg-2"
    dev = client.get(f"/api/remote/{code}").json()["appareils"][0]
    assert (dev["largeur"], dev["hauteur"]) == (1920, 1080)
