"""Fournisseurs d'IA (catalogue repris de LMU) : construction des requêtes, flux de réponse, liste des modèles.

Trois formats couvrent tout : compatible OpenAI (OpenAI, Mistral, Groq, Ollama, LM Studio…), Anthropic, Google.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterator
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class Provider:
    id: str
    nom: str
    format: str                      # openai | anthropic | google
    url: str                         # racine de l'API (modifiable pour Ollama, LM Studio, personnalisé)
    cle: str = "requise"             # requise | facultative | aucune
    local: bool = False
    url_cle: str = ""
    doc: str = ""
    note: str = ""
    modeles: list[str] = field(default_factory=list)  # repli si la liste n'est pas lisible
    url_modifiable: bool = False


CATALOG: list[Provider] = [
    Provider("ollama", "Ollama (sur ce PC)", "openai", "http://localhost:11434/v1", cle="aucune", local=True, url_modifiable=True,
             doc="https://ollama.com/library", note="Rien ne sort du PC. Lancer Ollama puis « ollama pull <modèle> »."),
    Provider("lmstudio", "LM Studio (sur ce PC)", "openai", "http://localhost:1234/v1", cle="aucune", local=True, url_modifiable=True,
             doc="https://lmstudio.ai/models", note="Rien ne sort du PC. Démarrer le serveur local dans LM Studio."),
    Provider("openai", "OpenAI (GPT)", "openai", "https://api.openai.com/v1", url_cle="https://platform.openai.com/api-keys",
             doc="https://platform.openai.com/docs/models", modeles=["gpt-5-mini", "gpt-5.2", "gpt-5.5"],
             note="Sert aussi pour la voix en ligne (synthèse et reconnaissance)."),
    Provider("anthropic", "Anthropic (Claude)", "anthropic", "https://api.anthropic.com/v1", url_cle="https://console.anthropic.com/settings/keys",
             doc="https://docs.claude.com/en/docs/about-claude/models/overview",
             modeles=["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"]),
    Provider("google", "Google (Gemini)", "google", "https://generativelanguage.googleapis.com/v1beta",
             url_cle="https://aistudio.google.com/app/apikey", doc="https://ai.google.dev/gemini-api/docs/models",
             modeles=["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"], note="Offre gratuite avec quota."),
    Provider("mistral", "Mistral", "openai", "https://api.mistral.ai/v1", url_cle="https://console.mistral.ai/api-keys",
             doc="https://docs.mistral.ai/getting-started/models/models_overview/", modeles=["mistral-large-latest", "mistral-medium-latest"],
             note="Hébergé dans l'Union européenne."),
    Provider("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", url_cle="https://openrouter.ai/keys",
             doc="https://openrouter.ai/models", modeles=["openrouter/free", "google/gemma-4-31b-it:free"], note="Modèles gratuits disponibles."),
    Provider("groq", "Groq", "openai", "https://api.groq.com/openai/v1", url_cle="https://console.groq.com/keys",
             doc="https://console.groq.com/docs/models", modeles=["openai/gpt-oss-120b", "openai/gpt-oss-20b"], note="Offre gratuite avec quota."),
    Provider("deepseek", "DeepSeek", "openai", "https://api.deepseek.com", url_cle="https://platform.deepseek.com/api_keys",
             doc="https://api-docs.deepseek.com/quick_start/pricing", modeles=["deepseek-chat", "deepseek-reasoner"]),
    Provider("ovhcloud", "OVHcloud AI Endpoints", "openai", "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", cle="facultative",
             doc="https://endpoints.ai.cloud.ovh.net/", note="Union européenne ; utilisable sans clé (2 requêtes/min)."),
    Provider("custom", "Personnalisé (compatible OpenAI)", "openai", "", cle="facultative", url_modifiable=True,
             note="vLLM, passerelle d'entreprise, autre service… Saisir l'adresse de base (…/v1)."),
]

BY_ID = {p.id: p for p in CATALOG}
NOT_CHAT = re.compile(r"embed|bge-|^bge|minilm|rerank|(^|/)e5-|whisper|tts|transcribe|moderation|dall-e|image|audio|realtime", re.I)


class AIError(RuntimeError):
    pass


def get(pid: str) -> Provider:
    if pid not in BY_ID:
        raise AIError(f"Fournisseur inconnu : {pid}")
    return BY_ID[pid]


def base_url(p: Provider, settings: dict) -> str:
    url = (settings.get("urls", {}).get(p.id) or p.url).strip().rstrip("/")
    if not url:
        raise AIError("Adresse du service à renseigner dans les réglages.")
    return url


def is_local(p: Provider, settings: dict) -> bool:
    try:
        host = urlparse(base_url(p, settings)).hostname or ""
    except AIError:
        return p.local
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")


def _headers(p: Provider, key: str) -> dict[str, str]:
    if p.format == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if p.format == "google":
        return {"x-goog-api-key": key, "content-type": "application/json"}
    h = {"content-type": "application/json"}
    if key:
        h["authorization"] = f"Bearer {key}"
    return h


# ----------------------------------------------------------------- messages
# Message interne : {"role": "user"|"assistant", "content": str, "images": [(mime, base64)]}

def _openai_messages(system: str, msgs: list[dict]) -> list[dict]:
    out = [{"role": "system", "content": system}]
    for m in msgs:
        if m.get("images"):
            parts = [{"type": "text", "text": m["content"]}]
            parts += [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}} for mime, b64 in m["images"]]
            out.append({"role": m["role"], "content": parts})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def _anthropic_messages(msgs: list[dict]) -> list[dict]:
    out = []
    for m in msgs:
        parts: list[dict] = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}
                             for mime, b64 in m.get("images") or []]
        parts.append({"type": "text", "text": m["content"]})
        out.append({"role": m["role"], "content": parts})
    return out


def _google_contents(msgs: list[dict]) -> list[dict]:
    out = []
    for m in msgs:
        parts: list[dict] = [{"text": m["content"]}]
        parts += [{"inline_data": {"mime_type": mime, "data": b64}} for mime, b64 in m.get("images") or []]
        out.append({"role": "model" if m["role"] == "assistant" else "user", "parts": parts})
    return out


def build_request(p: Provider, settings: dict, key: str, model: str, system: str, msgs: list[dict],
                  max_tokens: int = 1200) -> tuple[str, dict, dict]:
    base = base_url(p, settings)
    if p.format == "anthropic":
        return f"{base}/messages", _headers(p, key), {
            "model": model, "system": system, "messages": _anthropic_messages(msgs), "max_tokens": max_tokens, "stream": True}
    if p.format == "google":
        return f"{base}/models/{model}:streamGenerateContent?alt=sse", _headers(p, key), {
            "systemInstruction": {"parts": [{"text": system}]}, "contents": _google_contents(msgs),
            "generationConfig": {"maxOutputTokens": max_tokens}}
    body = {"model": model, "messages": _openai_messages(system, msgs), "stream": True}
    # Les modèles récents d'OpenAI refusent max_tokens (raisonnement compris dans max_completion_tokens).
    body["max_completion_tokens" if p.id == "openai" else "max_tokens"] = max_tokens
    if p.id == "ollama":
        body["reasoning_effort"] = "none"  # sinon les modèles « qui réfléchissent » épuisent le budget avant de répondre
    return f"{base}/chat/completions", _headers(p, key), body


def parse_stream_line(fmt: str, line: str) -> tuple[str, str] | None:
    """Ligne SSE → ("texte", fragment) | ("erreur", message) | None."""
    line = line.strip()
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        obj = json.loads(data)
    except ValueError:
        return None
    if isinstance(obj, dict) and obj.get("error"):
        err = obj["error"]
        return ("erreur", err.get("message", str(err)) if isinstance(err, dict) else str(err))
    if fmt == "anthropic":
        if obj.get("type") == "content_block_delta":
            return ("texte", obj.get("delta", {}).get("text", ""))
        return None
    if fmt == "google":
        cands = obj.get("candidates") or []
        if not cands:
            return None
        parts = (cands[0].get("content") or {}).get("parts") or []
        return ("texte", "".join(pt.get("text", "") for pt in parts if not pt.get("thought")))
    choices = obj.get("choices") or []
    if not choices:
        return None
    return ("texte", (choices[0].get("delta") or {}).get("content") or "")


def _error_text(status: int, body: str) -> str:
    try:
        obj = json.loads(body)
        err = obj.get("error", obj) if isinstance(obj, dict) else obj
        if isinstance(err, list) and err:
            err = err[0].get("error", err[0])
        msg = err.get("message") if isinstance(err, dict) else str(err)
    except ValueError:
        msg = body[:300]
    hints = {401: "clé refusée", 403: "accès refusé", 404: "modèle ou adresse introuvable", 429: "limite de requêtes atteinte"}
    return f"{hints.get(status, f'erreur {status}')} : {msg}" if msg else hints.get(status, f"erreur {status}")


def stream_chat(p: Provider, settings: dict, key: str, model: str, system: str, msgs: list[dict],
                max_tokens: int = 1200, timeout: float = 120.0) -> Iterator[str]:
    if p.cle == "requise" and not key:
        raise AIError(f"Clé {p.nom} à saisir dans les réglages.")
    if not model:
        raise AIError("Choisir un modèle dans les réglages.")
    url, headers, body = build_request(p, settings, key, model, system, msgs, max_tokens)
    try:
        with httpx.stream("POST", url, headers=headers, json=body, timeout=httpx.Timeout(timeout, connect=8.0)) as r:
            if r.status_code >= 400:
                raise AIError(f"{p.nom} — {_error_text(r.status_code, r.read().decode(errors='replace'))}")
            for line in r.iter_lines():
                ev = parse_stream_line(p.format, line)
                if ev is None:
                    continue
                kind, text = ev
                if kind == "erreur":
                    raise AIError(f"{p.nom} — {text}")
                if text:
                    yield text
    except httpx.ConnectError as exc:
        hint = " Le service est-il lancé ?" if is_local(p, settings) else ""
        raise AIError(f"{p.nom} injoignable ({base_url(p, settings)}).{hint}") from exc
    except httpx.TimeoutException as exc:
        raise AIError(f"{p.nom} : pas de réponse dans le délai.") from exc


def list_models(p: Provider, settings: dict, key: str) -> list[str]:
    base = base_url(p, settings)
    url = f"{base}/models"
    try:
        r = httpx.get(url, headers=_headers(p, key), timeout=8.0)
    except httpx.HTTPError as exc:
        raise AIError(f"{p.nom} injoignable ({base}).") from exc
    if r.status_code >= 400:
        raise AIError(f"{p.nom} — {_error_text(r.status_code, r.text)}")
    obj = r.json()
    if p.format == "google":
        ids = [m.get("name", "").removeprefix("models/") for m in obj.get("models", [])
               if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    else:
        ids = [m.get("id", "") for m in obj.get("data", [])]
    if p.id == "openai":
        ids = [i for i in ids if i.startswith(("gpt-", "o", "chatgpt"))]
    # modèles qui ne savent pas discuter (vecteurs, voix, image)
    ids = [i for i in ids if not NOT_CHAT.search(i)]
    return sorted({i for i in ids if i})
