import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from posturale.ai import providers, secrets, settings
from posturale.api.main import app
from posturale.storage import set_engine
from posturale.voice import tts


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


def test_key_encrypted_and_never_returned(client, tmp_path):
    secret = "sk-test-1234567890"
    r = client.put("/api/ai/keys/openai", json={"cle": secret}).json()
    assert r["cles"] == {"openai": True}
    assert next(p for p in r["fournisseurs"] if p["id"] == "openai")["cle_enregistree"]
    raw = (tmp_path / "data" / "ai_settings.json").read_text(encoding="utf-8")
    assert secret not in raw and secret not in json.dumps(r)
    assert settings.get_key("openai") == secret
    client.put("/api/ai/keys/openai", json={"cle": None})
    assert settings.get_key("openai") == ""


def test_secrets_roundtrip():
    assert secrets.decrypt(secrets.encrypt("clé spéciale é€")) == "clé spéciale é€"


def test_settings_and_locality(client):
    r = client.put("/api/ai/settings", json={"fournisseur": "custom", "urls": {"custom": "http://127.0.0.1:8080/v1"},
                                             "modeles": {"custom": "mon-modele"}, "voix": {"vitesse": 1.2}}).json()
    custom = next(p for p in r["fournisseurs"] if p["id"] == "custom")
    assert custom["local"] and custom["modele"] == "mon-modele" and r["voix"]["vitesse"] == 1.2
    assert r["voix"]["stt"] == "whisper"  # les autres réglages de voix restent
    assert not next(p for p in r["fournisseurs"] if p["id"] == "anthropic")["local"]
    assert client.put("/api/ai/settings", json={"fournisseur": "inconnu"}).status_code == 400


def test_stream_formats():
    assert providers.parse_stream_line("openai", 'data: {"choices":[{"delta":{"content":"Bon"}}]}') == ("texte", "Bon")
    assert providers.parse_stream_line("openai", "data: [DONE]") is None
    assert providers.parse_stream_line("anthropic", 'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"jour"}}') == ("texte", "jour")
    assert providers.parse_stream_line("anthropic", 'data: {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}') == ("erreur", "Overloaded")
    assert providers.parse_stream_line("google", 'data: {"candidates":[{"content":{"parts":[{"text":"!"}]}}]}') == ("texte", "!")


def test_image_payloads():
    msgs = [{"role": "user", "content": "Regarde", "images": [("image/jpeg", "QUJD")]}]
    s = {"urls": {}}
    _, _, body = providers.build_request(providers.get("openai"), s, "k", "m", "sys", msgs)
    assert body["messages"][1]["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"
    _, h, body = providers.build_request(providers.get("anthropic"), s, "k", "m", "sys", msgs)
    assert body["system"] == "sys" and body["messages"][0]["content"][0]["source"]["data"] == "QUJD" and h["x-api-key"] == "k"
    url, _, body = providers.build_request(providers.get("google"), s, "k", "gem", "sys", msgs)
    assert ":streamGenerateContent" in url and body["contents"][0]["parts"][1]["inline_data"]["data"] == "QUJD"


def test_chat_stream_with_context(client, monkeypatch):
    seen = {}

    def fake(p, s, key, model, system, msgs, max_tokens=1200, timeout=120.0):
        seen.update(system=system, msgs=msgs, max_tokens=max_tokens)
        yield "Monte la selle "
        yield "de 4 mm."

    monkeypatch.setattr(providers, "stream_chat", fake)
    client.put("/api/profile", json={"taille_cm": 186, "entrejambe_mm": 880})
    r = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "Que changer ?"}], "vocal": True})
    events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
    assert events[0]["debut"] and events[0]["local"]  # Ollama par défaut
    assert "".join(e.get("t", "") for e in events) == "Monte la selle de 4 mm."
    assert events[-1] == {"fin": True}
    assert "DONNÉES" in seen["msgs"][0]["content"] and '"entrejambe_mm": 880' in seen["msgs"][0]["content"]
    assert "Mode vocal" in seen["system"] and seen["max_tokens"] == 1200

    preview = client.get("/api/ai/context?images=true").json()
    assert preview["images"] == []  # images non autorisées par défaut
    assert "entrejambe_mm" in preview["texte"]


def test_chat_error_is_streamed(client, monkeypatch):
    def boom(*a, **k):
        raise providers.AIError("Ollama (sur ce PC) injoignable")
        yield  # pragma: no cover

    monkeypatch.setattr(providers, "stream_chat", boom)
    r = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "Salut"}]})
    assert '"erreur": "Ollama (sur ce PC) injoignable"' in r.text


def test_missing_key_message():
    with pytest.raises(providers.AIError, match="Clé"):
        list(providers.stream_chat(providers.get("anthropic"), {"urls": {}}, "", "claude", "s", [{"role": "user", "content": "x"}]))


@pytest.mark.skipif(not tts.detect_piper()["executables"] or not tts.detect_piper()["voix"], reason="Piper absent")
def test_piper_tts(client):
    r = client.post("/api/voice/tts", json={"texte": "Monte la selle de quatre millimètres."})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF" and len(r.content) > 20000
