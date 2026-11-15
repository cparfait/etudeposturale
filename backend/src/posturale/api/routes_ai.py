"""Coach IA : réglages, fournisseurs, aperçu des données envoyées, conversation en flux."""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session as DB

from posturale.ai import context, providers, settings
from posturale.ai.providers import AIError
from posturale.storage import get_session

router = APIRouter(prefix="/api/ai")


def _provider_view(p: providers.Provider, s: dict) -> dict:
    return {"id": p.id, "nom": p.nom, "format": p.format, "url_defaut": p.url, "url": s["urls"].get(p.id) or p.url,
            "cle": p.cle, "cle_enregistree": p.id in s["cles"], "local": providers.is_local(p, s), "url_cle": p.url_cle,
            "doc": p.doc, "note": p.note, "modeles_repli": p.modeles, "url_modifiable": p.url_modifiable,
            "modele": s["modeles"].get(p.id, "")}


@router.get("/settings")
def get_settings() -> dict:
    s = settings.load()
    return {**settings.public(s), "fournisseurs": [_provider_view(p, s) for p in providers.CATALOG]}


class SettingsIn(BaseModel):
    fournisseur: Optional[str] = None
    modeles: Optional[dict[str, str]] = None
    urls: Optional[dict[str, str]] = None
    images: Optional[bool] = None
    voix: Optional[dict[str, Any]] = None


@router.put("/settings")
def put_settings(data: SettingsIn) -> dict:
    patch = data.model_dump(exclude_none=True)
    if "fournisseur" in patch and patch["fournisseur"] not in providers.BY_ID:
        raise HTTPException(400, "Fournisseur inconnu")
    settings.update(patch)
    return get_settings()


class KeyIn(BaseModel):
    cle: Optional[str] = None


@router.put("/keys/{pid}")
def put_key(pid: str, data: KeyIn) -> dict:
    if pid not in providers.BY_ID:
        raise HTTPException(404, "Fournisseur inconnu")
    settings.set_key(pid, data.cle)
    return get_settings()


@router.get("/models/{pid}")
def models(pid: str) -> dict:
    s = settings.load()
    try:
        p = providers.get(pid)
        return {"modeles": providers.list_models(p, s, settings.get_key(pid, s)), "source": "service"}
    except AIError as exc:
        p = providers.BY_ID.get(pid)
        return {"modeles": p.modeles if p else [], "source": "repli", "erreur": str(exc)}


@router.post("/test/{pid}")
def test(pid: str) -> dict:
    """Question minimale au modèle choisi : vérifie l'adresse, la clé et le modèle."""
    s = settings.load()
    try:
        p = providers.get(pid)
        text = "".join(providers.stream_chat(p, s, settings.get_key(pid, s), s["modeles"].get(pid, ""),
                                             "Réponds en français, en une phrase très courte.",
                                             [{"role": "user", "content": "Dis bonjour au cycliste."}], max_tokens=600, timeout=90))
    except AIError as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": text.strip() or "(réponse vide)"}


@router.get("/context")
def preview(images: bool = False, db: DB = Depends(get_session)) -> dict:
    """Exactement ce qui sera envoyé au modèle (transparence)."""
    s = settings.load()
    p = providers.BY_ID.get(s["fournisseur"])
    imgs = context.key_images(db) if images and s["images"] else []
    return {"texte": context.as_text(context.build(db)), "local": bool(p and providers.is_local(p, s)),
            "fournisseur": p.nom if p else None, "modele": s["modeles"].get(s["fournisseur"], ""),
            "images": [{"legende": i["legende"], "url": f"data:{i['mime']};base64,{i['data']}"} for i in imgs]}


class Msg(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    messages: list[Msg]
    vocal: bool = False
    images: bool = False
    seance: Optional[str] = None  # séance guidée en cours : étape, plan ou débrief (texte)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(data: ChatIn, db: DB = Depends(get_session)) -> StreamingResponse:
    s = settings.load()
    pid = s["fournisseur"]
    msgs = [m.model_dump() for m in data.messages if m.role in ("user", "assistant") and m.content.strip()][-20:]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(400, "Le dernier message doit venir de toi")
    send_images = data.images and s["images"]
    imgs = context.key_images(db) if send_images else []
    # Les données sont rattachées au premier message : toujours fraîches, sans alourdir le prompt système.
    msgs[0] = {**msgs[0], "content": context.as_text(context.build(db)) + "\n\nQUESTION :\n" + msgs[0]["content"]}
    if imgs:
        legend = "\n".join(f"Image {k + 1} : {i['legende']}" for k, i in enumerate(imgs))
        msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + "\n\n" + legend, "images": [(i["mime"], i["data"]) for i in imgs]}
    system = context.system_prompt(data.vocal, bool(imgs), (data.seance or "")[:8000])

    def gen():
        try:
            p = providers.get(pid)
            yield _sse({"debut": True, "fournisseur": p.nom, "local": providers.is_local(p, s), "images": len(imgs)})
            for chunk in providers.stream_chat(p, s, settings.get_key(pid, s), s["modeles"].get(pid, ""), system, msgs,
                                               max_tokens=1200 if data.vocal else 4000):
                yield _sse({"t": chunk})
            yield _sse({"fin": True})
        except AIError as exc:
            yield _sse({"erreur": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
