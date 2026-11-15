import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from posturale.ai import context, providers
from posturale.api.main import app
from posturale.guide import debrief, plan
from posturale.storage import get_engine, set_engine
from posturale.storage.models import Analysis, Capture


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path / "data"))
    set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    return TestClient(app)


def verdict(statut: str, corr: float, flex: float = 25.0) -> dict:
    return {"statut": statut, "correction_mm": corr, "flexion_moyenne": flex, "plage_min": 30, "plage_max": 40}


def analysed_session(c: TestClient, sides: dict[str, dict], power: float = 160) -> int:
    """Séance avec une analyse de profil terminée par côté (résumé seulement)."""
    sid = c.post("/api/guide/start", json={"type": "premiere", "puissance_w": power}).json()["id"]
    with Session(get_engine()) as db:
        for side, v in sides.items():
            cap = Capture(session_id=sid, vue="profil", filename=f"{side}.mp4", path=f"/absent/{side}.mp4", meta={})
            db.add(cap)
            db.commit()
            db.refresh(cap)
            db.add(Analysis(capture_id=cap.id, status="terminee", progress=1,
                            summary={"vue": "profil", "cote": side, "verdict_selle": v, "metriques": {"P1": {"moyenne": v["flexion_moyenne"]}}}))
        db.commit()
    return sid


def test_first_plan(client):
    p = client.get("/api/guide/plan").json()
    assert p["type"] == "premiere" and p["vues"] == ["profil_D", "profil_G"]
    ids = [s["id"] for s in p["etapes"]]
    assert ids[0] == "accueil" and ids[-3:] == ["import", "debrief", "fin"]
    assert {"prise_profil_D", "prise_profil_G", "echauffement", "home_trainer"} <= set(ids)
    body = next(s for s in p["etapes"] if s["id"] == "pastilles_corps")
    assert len(body["items"]) == 8 and "deux côtés" in body["dire"]


def test_knee_pain_adds_front_view(client):
    client.post("/api/pains", json={"zone": "genou_avant", "cote": "G", "intensite": 3})
    p = client.get("/api/guide/plan").json()
    assert "face" in p["vues"] and any(s["id"] == "pastilles_face_dos" for s in p["etapes"])


def test_verification_after_change(client):
    client.post("/api/bike/configs", json={"hauteur_selle_mm": 760, "manivelle_mm": 172.5})
    analysed_session(client, {"D": verdict("trop_tendu", -5)}, power=170)
    client.post("/api/bike/configs", json={"hauteur_selle_mm": 755, "manivelle_mm": 172.5})
    p = client.get("/api/guide/plan").json()
    assert p["type"] == "verification" and p["vues"] == ["profil_D"] and p["puissance_w"] == 170
    assert p["changements"] == [{"champ": "hauteur_selle_mm", "libelle": "hauteur de selle", "unite": "mm", "avant": 760.0, "apres": 755.0, "delta": -5.0}]
    assert "hauteur de selle −5 mm" in p["etapes"][0]["dire"]


def test_adaptation_limits():
    base = {"type": "premiere"}
    over, texts = plan.validate_adaptation(
        {"vues": ["face", "inconnue", "face"], "puissance_w": 900, "echauffement_min": 2, "intro": "Salut", "conseils": {"camera": "Vise bien"}}, base)
    assert "vues" not in over  # sans profil : refusé
    assert over == {"puissance_w": 400, "echauffement_min": 5} and texts["intro"] == "Salut" and texts["conseils"] == {"camera": "Vise bien"}
    over, _ = plan.validate_adaptation({"vues": ["profil_G", "dos"], "puissance_w": 150}, {"type": "verification"})
    assert over == {}  # vérification : mêmes prises, même puissance


def test_ai_adapts_plan(client, monkeypatch):
    seen = {}

    def fake(p, s, key, model, system, msgs, **kw):
        seen["system"], seen["user"] = system, msgs[0]["content"]
        yield '```json\n{"vues": ["profil_G", "profil_D", "dos"], "puissance_w": 175, "echauffement_min": 12,'
        yield ' "intro": "On commence par la gauche.", "conseils": {"camera": "Trépied bien droit.", "nimporte": "x"}, "pourquoi": "Gauche d\'abord."}\n```'

    monkeypatch.setattr(providers, "stream_chat", fake)
    client.put("/api/ai/settings", json={"modeles": {"ollama": "gemma4:12b"}})
    p = client.post("/api/guide/plan/ia").json()
    assert p["ia"]["ok"] and p["ia"]["pourquoi"] == "Gauche d'abord." and p["ia"]["conseils_ignores"] == ["nimporte"]
    assert p["vues"] == ["profil_G", "profil_D", "dos"] and p["puissance_w"] == 175 and p["echauffement_min"] == 12
    assert p["etapes"][0]["dire"].startswith("On commence par la gauche.")
    assert next(s for s in p["etapes"] if s["id"] == "camera")["conseil_ia"] == "Trépied bien droit."
    assert "PLAN (JSON)" in seen["user"] and "UNIQUEMENT par un objet JSON" in seen["system"]


def test_ai_failure_keeps_plan(client, monkeypatch):
    def broken(*a, **k):
        raise providers.AIError("Ollama injoignable")
        yield  # pragma: no cover

    monkeypatch.setattr(providers, "stream_chat", broken)
    p = client.post("/api/guide/plan/ia").json()
    assert p["ia"]["ok"] is False and "injoignable" in p["ia"]["message"] and p["vues"] == ["profil_D", "profil_G"]


def test_single_change_rules():
    res = lambda v: {"statut": "terminee", "resume": {"verdict_selle": v}}  # noqa: E731
    cfg = {"hauteur_selle_mm": 760}
    m = debrief.propose_change({"profil_D": res(verdict("trop_tendu", -5)), "profil_G": res(verdict("trop_tendu", -8))}, [], cfg)
    assert m["type"] == "reglage" and m["delta"] == -5 and m["apres"] == 755
    m = debrief.propose_change({"profil_D": res(verdict("trop_tendu", -6)), "profil_G": res(verdict("dans_la_plage", 0))}, [], cfg)
    assert m["delta"] == -3  # l'autre côté est dans la plage : moitié
    m = debrief.propose_change({"profil_D": res(verdict("trop_tendu", -5)), "profil_G": res(verdict("trop_plie", 5))}, [], cfg)
    assert m["type"] == "aucun" and "asymétrie" in m["raison"]
    health = [{"categorie": "sante", "priorite": "haute", "titre": "Douleur forte", "action": "Consulter"}]
    assert debrief.propose_change({"profil_D": res(verdict("trop_tendu", -5))}, health, cfg)["type"] == "consulter"


def test_debrief_compare_and_apply(client):
    client.post("/api/bike/configs", json={"hauteur_selle_mm": 760})
    analysed_session(client, {"D": verdict("trop_tendu", -5, 22)})
    sid = analysed_session(client, {"D": verdict("trop_tendu", -4, 26), "G": verdict("trop_tendu", -6, 24)})
    d = client.get(f"/api/guide/debrief/{sid}").json()
    assert d["seance_precedente_id"] == sid - 1
    assert d["comparaison"] == [{"prise": "profil_D", "metrique": "P1", "nom": d["comparaison"][0]["nom"], "unite": d["comparaison"][0]["unite"],
                                 "avant": 22.0, "apres": 26.0, "delta": 4.0}]
    m = d["modification"]
    assert m["type"] == "reglage" and m["delta"] == -4 and m["avant"] == 760
    cfg = client.post(f"/api/guide/apply/{sid}", json={"champ": m["champ"], "delta": m["delta"]}).json()
    assert cfg["hauteur_selle_mm"] == 756 and "−4 mm" in cfg["libelle"]
    assert client.get("/api/guide/plan").json()["type"] == "verification"
    assert client.post(f"/api/guide/apply/{sid}", json={"champ": "manivelle_mm", "delta": -2.5}).status_code == 400
    assert client.post(f"/api/guide/apply/{sid}", json={"champ": "hauteur_selle_mm", "delta": 40}).status_code == 400


def test_session_context_in_prompt():
    s = context.system_prompt(True, False, json.dumps({"etape": "camera"}))
    assert "Séance guidée en cours" in s and '"etape": "camera"' in s
    assert "Séance guidée" not in context.system_prompt(True, False)
