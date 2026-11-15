"""Téléphones reliés à une séance par QR code : rôle (vue filmée), départ / arrêt de l'enregistrement depuis le PC.

Tout passe par de simples requêtes du téléphone toutes les secondes (pas de WebSocket) ; l'état vit en mémoire
du serveur local : une appairage dure le temps de la séance. Les vidéos arrivent par l'envoi habituel
(/api/sessions/{id}/captures) puis l'analyse démarre.
"""
from __future__ import annotations

import asyncio
import secrets
import socket
import threading
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlmodel import Session as DB

from posturale.storage import get_session
from posturale.storage.models import Session as Seance

router = APIRouter(prefix="/api/remote")

ROLES = ("profil_D", "profil_G", "face", "dos")
ROLE_LABEL = {"profil_D": "Profil droit", "profil_G": "Profil gauche", "face": "Vue de face", "dos": "Vue de dos"}
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I
_lock = threading.Lock()
_pairs: dict[str, dict[str, Any]] = {}
STALE_S = 6.0
_live: dict[str, dict[str, Any]] = {}   # aperçu en direct par téléphone : dernière image JPEG, numéro, écrans qui regardent


def _slot(did: str) -> dict:
    return _live.setdefault(did, {"img": None, "seq": 0, "viewers": 0})


def _now() -> float:
    return time.time()


def _get(code: str) -> dict:
    p = _pairs.get(code.upper())
    if not p:
        raise HTTPException(404, "Code inconnu ou expiré : rescanne le QR code affiché sur le PC.")
    return p


def _device_view(d: dict) -> dict:
    age = _now() - d["vu"]
    return {k: d.get(k) for k in ("id", "nom", "role", "etat", "capture_id", "message", "secure", "fps", "largeur", "hauteur")} | {
        "role_label": ROLE_LABEL.get(d["role"], "—"), "connecte": age < STALE_S, "vu_il_y_a_s": round(age, 1)}


def _view(code: str, p: dict) -> dict:
    for did in [k for k, d in p["appareils"].items() if _now() - d["vu"] > 120]:
        del p["appareils"][did]  # téléphone parti depuis plus de 2 min
    return {"code": code, "session_id": p["sid"], "commande": p["commande"],
            "appareils": [_device_view(d) for d in p["appareils"].values()],
            "roles": [{"id": r, "label": ROLE_LABEL[r]} for r in ROLES]}


def lan_addresses() -> list[str]:
    """Adresses du PC sur le réseau local (pour le QR code), la plus probable en premier."""
    out: list[str] = []
    try:  # aucune donnée n'est envoyée : sert seulement à connaître l'interface de sortie
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.0.1", 9))
        out.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in out:
                out.append(ip)
    except OSError:
        pass
    private = [ip for ip in out if ip.startswith(("192.168.", "10.")) or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)]
    return private or [ip for ip in out if not ip.startswith("127.")]


def _ca_file():
    from posturale.config import data_dir

    return data_dir() / "https" / "ca.crt"


@router.get("/address")
def address() -> dict:
    return {"adresses": lan_addresses(), "autorite": _ca_file().exists()}


@router.get("/autorite.crt")
def authority():
    """Autorité HTTPS locale (scripts/https_local.py), à installer une fois sur le téléphone pour éviter l'avertissement."""
    from fastapi.responses import FileResponse

    f = _ca_file()
    if not f.exists():
        raise HTTPException(404, "Pas d'autorité locale : HTTPS non configuré sur ce PC.")
    return FileResponse(f, media_type="application/x-x509-ca-cert", filename="etude-posturale-autorite.crt")


class PairIn(BaseModel):
    session_id: Optional[int] = None   # None : cadrage seul (aperçu en direct, sans enregistrement)


@router.post("", status_code=201)
def pair(data: PairIn, db: DB = Depends(get_session)) -> dict:
    """Code d'appairage de la séance (le même tant que le serveur tourne)."""
    if data.session_id is not None and not db.get(Seance, data.session_id):
        raise HTTPException(404, "Séance introuvable")
    with _lock:
        for code, p in _pairs.items():
            if p["sid"] == data.session_id:
                return _view(code, p)
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        _pairs[code] = {"sid": data.session_id, "appareils": {}, "commande": None, "cree": _now()}
        return _view(code, _pairs[code])


@router.get("/{code}")
def status(code: str) -> dict:
    with _lock:
        return _view(code.upper(), _get(code))


class JoinIn(BaseModel):
    nom: str = "Téléphone"
    secure: bool = False


@router.post("/{code}/join")
def join(code: str, data: JoinIn) -> dict:
    with _lock:
        p = _get(code)
        taken = {d["role"] for d in p["appareils"].values() if _now() - d["vu"] < STALE_S}
        role = next((r for r in ROLES if r not in taken), "profil_D")  # 1er téléphone : profil droit, 2e : gauche…
        did = secrets.token_hex(4)
        p["appareils"][did] = {"id": did, "nom": data.nom[:40] or "Téléphone", "role": role, "etat": "connecte",
                               "capture_id": None, "message": "", "secure": data.secure, "fps": None, "vu": _now()}
        return {"appareil": did, "role": role, "role_label": ROLE_LABEL[role], **_view(code.upper(), p)}


class PollIn(BaseModel):
    appareil: str
    etat: str = "pret"                 # connecte | pret | enregistre | envoi | envoye | erreur
    capture_id: Optional[int] = None
    message: str = ""
    fps: Optional[float] = None
    largeur: Optional[int] = None
    hauteur: Optional[int] = None


@router.post("/{code}/poll")
def poll(code: str, data: PollIn) -> dict:
    """Le téléphone donne son état et reçoit la commande en cours (départ, arrêt)."""
    with _lock:
        p = _get(code)
        d = p["appareils"].get(data.appareil)
        if not d:
            raise HTTPException(404, "Téléphone inconnu : rescanne le QR code.")
        d.update(vu=_now(), etat=data.etat, message=data.message[:200], fps=data.fps, largeur=data.largeur, hauteur=data.hauteur)
        if data.capture_id:
            d["capture_id"] = data.capture_id
        cmd = p["commande"]
        concerned = cmd is not None and (not cmd["cles"] or d["role"] in cmd["cles"])
        return {"role": d["role"], "role_label": ROLE_LABEL[d["role"]], "session_id": p["sid"],
                "commande": cmd if concerned else None, "apercu": _slot(data.appareil)["viewers"] > 0}


class RoleIn(BaseModel):
    role: str


@router.put("/{code}/appareils/{did}")
def set_role(code: str, did: str, data: RoleIn) -> dict:
    if data.role not in ROLES:
        raise HTTPException(400, "Vue inconnue")
    with _lock:
        p = _get(code)
        if did not in p["appareils"]:
            raise HTTPException(404, "Téléphone inconnu")
        p["appareils"][did]["role"] = data.role
        return _view(code.upper(), p)


class CommandIn(BaseModel):
    action: str                         # start | stop
    cles: list[str] = []               # vues concernées (vide : tous les téléphones)
    duree_s: float = 60


@router.post("/{code}/command")
def command(code: str, data: CommandIn) -> dict:
    if data.action not in ("start", "stop"):
        raise HTTPException(400, "Action inconnue")
    with _lock:
        p = _get(code)
        p["commande"] = {"id": secrets.token_hex(4), "action": data.action, "cles": [c for c in data.cles if c in ROLES],
                         "duree_s": max(5.0, min(180.0, data.duree_s)), "a": _now()}
        if data.action == "start":
            for d in p["appareils"].values():
                if not p["commande"]["cles"] or d["role"] in p["commande"]["cles"]:
                    d["capture_id"] = None   # nouvelle prise : l'ancienne vidéo n'est plus celle attendue
        return _view(code.upper(), p)


# --- Aperçu en direct : le téléphone envoie de petites images JPEG, le PC les affiche (cadrage, séance) ---

def _known(code: str, did: str) -> bool:
    with _lock:
        p = _pairs.get(code.upper())
        return bool(p and did in p["appareils"])


@router.websocket("/{code}/flux/{did}")
async def phone_feed(ws: WebSocket, code: str, did: str) -> None:
    """Le téléphone pousse ses images (uniquement quand un écran regarde : voir « apercu » dans /poll)."""
    if not _known(code, did):
        await ws.close(code=4404)
        return
    await ws.accept()
    slot = _slot(did)
    try:
        while True:
            img = await ws.receive_bytes()
            if len(img) <= 2_000_000:
                slot["img"], slot["seq"] = img, slot["seq"] + 1
    except (WebSocketDisconnect, RuntimeError):
        pass


@router.websocket("/{code}/apercu/{did}")
async def preview(ws: WebSocket, code: str, did: str) -> None:
    """Le PC reçoit la dernière image du téléphone dès qu'elle change (les images en retard sont sautées)."""
    if not _known(code, did):
        await ws.close(code=4404)
        return
    await ws.accept()
    slot = _slot(did)
    slot["viewers"] += 1
    gone = asyncio.ensure_future(ws.receive())   # se termine quand l'écran ferme la connexion
    seq = -1
    try:
        while not gone.done():
            if slot["img"] is not None and slot["seq"] != seq:
                seq = slot["seq"]
                await ws.send_bytes(slot["img"])
            else:
                await asyncio.sleep(0.02)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        slot["viewers"] -= 1
        gone.cancel()
