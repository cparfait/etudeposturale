import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from posturale.ai import settings
from posturale.api.main import app
from posturale.storage import set_engine
from posturale.voice import tts


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


def test_defaults_and_required(client):
    e = client.get("/api/equipment").json()
    assert e["onboarding_fait"] is False and e["repondu"] == 0 and e["manquants"] == [] and e["pret"]
    levels = {c["niveau"] for c in e["catalogue"]}
    assert levels == {"obligatoire", "recommande", "optionnel"}
    required = [c["id"] for c in e["catalogue"] if c["niveau"] == "obligatoire"]
    assert required == ["velo_fixe", "telephone", "support", "pastilles_orange", "metre"]
    e = client.put("/api/equipment", json={"items": {"pastilles_orange": False, "inconnu": True}}).json()
    assert e["manquants"] == ["pastilles_orange"] and not e["pret"] and "inconnu" not in e["items"]
    e = client.put("/api/equipment", json={"items": {"mire": True}, "onboarding_fait": True}).json()
    assert e["manquants"] == [] and e["onboarding_fait"] and e["adaptations"][0]["id"] == "pastilles_orange"


def test_plan_adapts_to_equipment(client):
    full = client.get("/api/guide/plan").json()
    ids = [s["id"] for s in full["etapes"]]
    assert "pastilles_corps" in ids and full["etapes"][ids.index("home_trainer")]["type"] == "ble"
    client.put("/api/equipment", json={"items": {"pastilles_vertes": False, "trainer_connecte": False, "capteur_puissance": False,
                                                 "micro": False, "pastilles_orange": False, "mire": True}})
    p = client.get("/api/guide/plan").json()
    steps = {s["id"]: s for s in p["etapes"]}
    assert "pastilles_corps" not in steps and "pastilles_velo" not in steps and "mire" in steps
    assert steps["home_trainer"]["type"] == "info" and "résistance fixe" in steps["home_trainer"]["dire"]
    assert steps["prise_profil_D"]["puissance_w"] is None and steps["echauffement"]["puissance_w"] is None
    assert "watts" not in steps["accueil"]["dire"] and "barre d'espace" in steps["accueil"]["dire"]
    assert all("Dis «" not in s["dire"] for s in p["etapes"])
    assert p["equipement"] == {"pastilles_vertes": False, "trainer": False, "capteur_puissance": False, "micro": False, "mire_seule": True}
    assert any("pastilles vertes" in r for r in p["raisons"])


def test_power_meter_without_trainer(client):
    client.put("/api/equipment", json={"items": {"trainer_connecte": False, "capteur_puissance": True}})
    st = next(s for s in client.get("/api/guide/plan").json()["etapes"] if s["id"] == "home_trainer")
    assert st["type"] == "ble" and st["appareils"] == ["puissance"]


def test_equipment_in_ai_context(client):
    from posturale.ai import context
    from posturale.storage import get_engine
    from sqlmodel import Session

    client.put("/api/equipment", json={"items": {"pastilles_orange": False, "micro": True}})
    with Session(get_engine()) as db:
        data = context.build(db)
    assert data["equipement"]["obligatoires_manquants"] == ["Pastilles orange (2 par côté filmé)"]


def test_cartesia_key_and_tts(client, monkeypatch, tmp_path):
    r = client.put("/api/voice/keys/cartesia", json={"cle": "sk_car_test123"}).json()
    assert r == {"cle_enregistree": True}
    assert "sk_car_test123" not in (tmp_path / "data" / "ai_settings.json").read_text(encoding="utf-8")
    assert settings.get_key("cartesia") == "sk_car_test123"
    sent = {}

    class Resp:
        status_code, content, text = 200, b"ID3audio", ""

    def fake_post(url, headers, json, timeout):  # noqa: A002
        sent.update(url=url, headers=headers, body=json)
        return Resp()

    monkeypatch.setattr(tts.httpx, "post", fake_post)
    client.put("/api/ai/settings", json={"voix": {"tts": "cartesia", "vitesse": 1.2}})
    res = client.post("/api/voice/tts", json={"texte": "Bonjour"})
    assert res.status_code == 200 and res.headers["content-type"] == "audio/mpeg" and res.content == b"ID3audio"
    assert sent["headers"]["X-API-Key"] == "sk_car_test123" and sent["body"]["language"] == "fr"
    assert sent["body"]["generation_config"] == {"speed": 1.2} and sent["body"]["voice"]["id"]
    assert "cartesia" not in json.dumps(client.get("/api/ai/settings").json()["cles"]) or client.get("/api/ai/settings").json()["cles"]["cartesia"] is True


def test_new_pain_zones_and_meniscus_rule(client):
    zones = {z["id"] for z in client.get("/api/catalog").json()["zones"]}
    assert {"genou_menisque_int", "genou_menisque_ext", "coude", "haut_dos", "epaule"} <= zones
    client.post("/api/pains", json={"zone": "genou_menisque_int", "cote": "D", "intensite": 3})
    h = next(x for x in client.get("/api/recommendations").json()["hypotheses"] if x["id"] == "menisque")
    assert h["categorie"] == "sante" and h["priorite"] == "moyenne" and "flexion" in h["action"]
    assert "face" in client.get("/api/guide/plan").json()["vues"]  # douleur au genou : vue de face ajoutée
