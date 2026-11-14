import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from posturale.api.main import app
from posturale.pose.markers import ColorRange, current_ranges, detect_blobs
from posturale.storage import set_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


def _photo() -> np.ndarray:
    img = np.full((480, 640, 3), 60, np.uint8)
    cv2.circle(img, (100, 100), 9, (40, 230, 120), -1)   # vert (BGR)
    cv2.circle(img, (300, 200), 9, (40, 230, 120), -1)
    cv2.circle(img, (500, 400), 9, (0, 120, 255), -1)    # orange
    cv2.circle(img, (200, 400), 9, (60, 20, 230), -1)    # rouge : teinte qui « passe par 0 »
    return img


def test_hue_wraparound():
    img = _photo()
    red = ColorRange((170, 120, 120), (6, 255, 255))
    pts = detect_blobs(img, red)
    assert len(pts) == 1 and pts[0] == pytest.approx([200, 400], abs=1)


def test_tuning_flow(client):
    ok, buf = cv2.imencode(".png", _photo())
    r = client.post("/api/markers/frame", files={"file": ("test.png", buf.tobytes(), "image/png")})
    assert r.status_code == 201, r.text
    fr = r.json()
    assert (fr["largeur"], fr["hauteur"]) == (640, 480)

    cols = client.get("/api/markers/colors").json()
    t = client.post("/api/markers/test", json={"token": fr["token"], **cols["actuel"]}).json()
    assert len(t["vert"]["pastilles"]) == 2 and len(t["orange"]["pastilles"]) == 1
    assert t["vert"]["masque"].startswith("data:image/png;base64,")

    narrow = {**cols["actuel"], "vert": {"lo": [80, 90, 90], "hi": [85, 255, 255]}}
    assert client.post("/api/markers/test", json={"token": fr["token"], **narrow}).json()["vert"]["pastilles"] == []

    saved = client.put("/api/markers/colors", json=narrow).json()
    assert saved["actuel"]["vert"]["lo"] == [80, 90, 90]
    assert current_ranges()["vert"].lo == (80, 90, 90)  # utilisé par la prochaine analyse
    assert client.delete("/api/markers/colors").json()["actuel"] == cols["defaut"]

    bad = {**cols["actuel"], "vert": {"lo": [30, 200, 90], "hi": [80, 100, 255]}}
    assert client.put("/api/markers/colors", json=bad).status_code == 400
    assert client.post("/api/markers/test", json={"token": "abc", **cols["actuel"]}).status_code == 404
