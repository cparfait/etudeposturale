import base64

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from posturale.api.main import app
from posturale.storage import set_engine
from posturale.voice import tts


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


class Resp:
    def __init__(self, status=200, content=b"", data=None, text=""):
        self.status_code, self.content, self._data, self.text = status, content, data, text

    def json(self):
        return self._data


def capture(monkeypatch, response, get_response=None):
    calls = []

    def post(url, **kw):
        calls.append(("POST", url, kw))
        return response

    def get(url, **kw):
        calls.append(("GET", url, kw))
        return get_response

    monkeypatch.setattr(tts.httpx, "post", post)
    monkeypatch.setattr(tts.httpx, "get", get)
    return calls


def test_google_tts(client, monkeypatch):
    voices = {"voices": [{"name": "fr-FR-Standard-A", "languageCodes": ["fr-FR"], "ssmlGender": "FEMALE"},
                         {"name": "fr-FR-Chirp3-HD-Charon", "languageCodes": ["fr-FR"], "ssmlGender": "MALE"},
                         {"name": "en-US-Neural2-A", "languageCodes": ["en-US"]}]}
    calls = capture(monkeypatch, Resp(data={"audioContent": base64.b64encode(b"MP3").decode()}), Resp(data=voices))
    assert client.put("/api/voice/keys/google", json={"cle": "AIzaTEST"}).json() == {"cle_enregistree": True}
    listed = client.get("/api/voice/google/voices").json()["voix"]
    assert [v["id"] for v in listed] == ["fr-FR-Chirp3-HD-Charon", "fr-FR-Standard-A"]  # Chirp 3 HD d'abord, pas d'anglais
    client.put("/api/ai/settings", json={"voix": {"tts": "google"}})
    res = client.post("/api/voice/tts", json={"texte": "Bonjour"})
    assert res.status_code == 200 and res.content == b"MP3"
    method, url, kw = calls[-1]
    assert url.endswith("/text:synthesize") and kw["headers"]["X-Goog-Api-Key"] == "AIzaTEST"
    assert kw["json"]["voice"]["name"] == "fr-FR-Chirp3-HD-Charon"  # voix vide : la meilleure trouvée


def test_azure_tts(client, monkeypatch):
    calls = capture(monkeypatch, Resp(content=b"ID3azure"))
    client.put("/api/voice/keys/azure", json={"cle": "az-key"})
    client.put("/api/ai/settings", json={"voix": {"tts": "azure", "azure_region": "westeurope", "vitesse": 1.2}})
    res = client.post("/api/voice/tts", json={"texte": "Selle & genou <5 mm>"})
    assert res.status_code == 200 and res.content == b"ID3azure"
    _, url, kw = calls[-1]
    assert url == "https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1"
    assert kw["headers"]["Ocp-Apim-Subscription-Key"] == "az-key"
    ssml = kw["content"].decode()
    assert "fr-FR-DeniseNeural" in ssml and "rate='+20%'" in ssml and "Selle &amp; genou &lt;5 mm&gt;" in ssml


def test_azure_error_message(client, monkeypatch):
    capture(monkeypatch, Resp(status=401))
    client.put("/api/voice/keys/azure", json={"cle": "bad"})
    client.put("/api/ai/settings", json={"voix": {"tts": "azure"}})
    res = client.post("/api/voice/tts", json={"texte": "Test"})
    assert res.status_code == 502 and "mauvaise région" in res.json()["detail"]


def test_fish_tts(client, monkeypatch):
    calls = capture(monkeypatch, Resp(content=b"ID3fish"))
    client.put("/api/voice/keys/fish", json={"cle": "fish-key"})
    listed = client.get("/api/voice/fish/voices").json()["voix"]
    assert listed[0]["id"] == "" and "Clémence" in [v["nom"] for v in listed]  # liste choisie, pas la bibliothèque publique
    client.put("/api/ai/settings", json={"voix": {"tts": "fish", "fish_voix": "abc123"}})
    res = client.post("/api/voice/tts", json={"texte": "Salut"})
    assert res.status_code == 200 and res.content == b"ID3fish"
    _, url, kw = calls[-1]
    assert url == "https://api.fish.audio/v1/tts" and kw["headers"]["model"] == "s2.1-pro-free"
    assert kw["headers"]["Authorization"] == "Bearer fish-key" and kw["json"]["reference_id"] == "abc123"
    assert client.put("/api/voice/keys/inconnu", json={"cle": "x"}).status_code == 404
