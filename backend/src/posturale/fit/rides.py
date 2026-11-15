"""Sorties importées en lot (fichiers .FIT d'un compteur Garmin, ou archives .zip de Garmin Connect).

Chaque sortie est rattachée à la configuration du vélo en vigueur ce jour-là : on compare ainsi les sorties
avant / après un réglage (équilibre G/D, efficacité du couple, fluidité, cadence, puissance pour un même cardio).
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable

CYCLING_SPORTS = {"cycling", "e_biking"}
CYCLING_SUB = {"indoor_cycling", "virtual_activity", "spin", "road", "mountain", "gravel_cycling", "track_cycling",
               "cyclocross", "e_bike_fitness"}
MAX_FILE = 60 * 1024 * 1024   # une sortie .FIT fait rarement plus de quelques Mo


def expand(name: str, data: bytes, depth: int = 0) -> list[tuple[str, bytes]]:
    """Un fichier déposé -> les .FIT qu'il contient (.zip de Garmin Connect, y compris zip dans zip)."""
    low = name.lower()
    if low.endswith(".fit"):
        return [(name, data)]
    if low.endswith(".zip") and depth < 3:
        out: list[tuple[str, bytes]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    if info.is_dir() or info.file_size > (MAX_FILE if info.filename.lower().endswith(".fit") else 4 * 1024 ** 3):
                        continue
                    if info.filename.lower().endswith((".fit", ".zip")):
                        out += expand(info.filename.rsplit("/", 1)[-1], z.read(info), depth + 1)
        except zipfile.BadZipFile:
            return []
        return out
    return []


def is_cycling(summary: dict) -> bool:
    sport, sub = (summary.get("sport") or "").lower(), (summary.get("sous_sport") or "").lower()
    if sport in CYCLING_SPORTS:
        return True
    if sport and sport not in ("generic", "training", "none"):
        return False                       # course à pied, natation, marche… (« road » existe aussi en course à pied)
    if sub in CYCLING_SUB:
        return True                        # sport générique mais sous-type vélo (home trainer, Zwift…)
    g = summary.get("global") or {}
    return bool(g.get("cadence_rpm") or g.get("puissance_w"))   # sport non renseigné : on regarde le pédalage


def _ts(iso: str) -> datetime:
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def config_for(when: datetime, configs: list[Any]) -> Any | None:
    """Configuration en vigueur à cette date : la dernière enregistrée avant. Une sortie antérieure à toutes
    revient à la première : elle décrit le vélo tel qu'il était avant tout changement (saisie après coup)."""
    ordered = sorted(configs, key=lambda c: c.created_at)
    best = ordered[0] if ordered else None
    for c in ordered:
        ca = c.created_at if c.created_at.tzinfo else c.created_at.replace(tzinfo=timezone.utc)
        if ca <= when:
            best = c
    return best


METRICS = ("puissance_w", "cadence_rpm", "fc_bpm", "equilibre_gauche_pct")


def _wmean(pairs: Iterable[tuple[float | None, float]], digits: int = 1) -> float | None:
    pairs = [(v, w) for v, w in pairs if isinstance(v, (int, float)) and w > 0]
    tot = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / tot, digits) if tot else None


def aggregate(rides: list[dict]) -> dict:
    """Moyennes pondérées par le temps en mouvement (une sortie de 3 h compte plus qu'une de 30 min)."""
    w = [r.get("mouvement_min") or r.get("duree_min") or 0 for r in rides]
    g = [r.get("global") or {} for r in rides]
    out: dict[str, Any] = {
        "sorties": len(rides),
        "heures": round(sum(w) / 60, 1),
        "km": round(sum(r.get("distance_km") or 0 for r in rides), 0),
    }
    for m in METRICS:
        out[m] = _wmean((x.get(m), wi) for x, wi in zip(g, w))
    for key in ("efficacite_couple", "fluidite"):
        out[key] = [_wmean(((x.get(key) or [None, None])[i], wi) for x, wi in zip(g, w)) for i in (0, 1)]
    # rendement : watts par battement (même puissance pour un cardio plus bas = mieux)
    out["w_par_bpm"] = _wmean((((x.get("puissance_w") / x["fc_bpm"]) if x.get("puissance_w") and x.get("fc_bpm") else None, wi)
                               for x, wi in zip(g, w)), digits=2)
    # dérive de l'équilibre avec la fatigue : dernière heure - première heure (sorties de 2 h et plus)
    drifts = []
    for r in rides:
        h = [x.get("equilibre_gauche_pct") for x in r.get("par_heure") or []]
        h = [x for x in h if isinstance(x, (int, float))]
        if len(h) >= 2:
            drifts.append(h[-1] - h[0])
    out["derive_equilibre"] = round(sum(drifts) / len(drifts), 1) if drifts else None
    out["sorties_longues"] = len(drifts)
    return out


def view(f: Any, configs: list[Any]) -> dict:
    """Une sortie (FitFile hors séance) telle que l'affichent l'interface, le coach et le débrief."""
    s = f.summary or {}
    c = config_for(_ts(s["debut"]), configs) if s.get("debut") else None
    return {"id": f.id, "fichier": f.filename, "config_id": c.id if c else None, "config": (c.libelle if c else None),
            **{k: s.get(k) for k in ("debut", "duree_min", "mouvement_min", "distance_km", "sport", "sous_sport", "global", "par_heure")}}


def stored_file(summary: dict) -> Any | None:
    """Fichier .FIT gardé à l'import (data/fit/sorties/<début>_<empreinte>.fit)."""
    from posturale.config import data_dir

    if not summary.get("debut"):
        return None
    hits = sorted((data_dir() / "fit" / "sorties").glob(f"{summary['debut'][:19].replace(':', '-')}_*.fit"))
    return hits[0] if hits else None


def series(path: Any, step_min: float = 5.0) -> list[dict]:
    """Moyennes par tranche de 5 minutes : puissance, cadence, cardio, équilibre G/D (lecture du fichier gardé)."""
    from datetime import timedelta

    from posturale.fit.parser import read_records, summarize, window

    recs = read_records(path)
    if not recs:
        return []
    t0, t_end = recs[0]["timestamp"], recs[-1]["timestamp"]
    out, k = [], 0
    while t0 + timedelta(minutes=k * step_min) <= t_end:
        a = t0 + timedelta(minutes=k * step_min)
        chunk = window(recs, a, a + timedelta(minutes=step_min))
        if chunk:
            s = summarize(chunk)
            out.append({"t_min": round(k * step_min + step_min / 2, 1), **{m: s[m] for m in METRICS}})
        k += 1
    return out


def reading(g: dict, serie: list[dict]) -> list[dict]:
    """Lecture automatique : on compare la jambe gauche à la droite (pas de norme inventée)."""
    out: list[dict] = []
    left = g.get("equilibre_gauche_pct")
    if left is not None:
        dev = abs(left - 50)
        strong = "gauche" if left > 50 else "droite"
        share = round(max(left, 100 - left))
        if dev < 2:
            out.append({"ton": "ok", "titre": "Pédalage équilibré", "texte": f"Les deux jambes fournissent presque autant ({_bal(left)})."})
        elif dev < 4:
            out.append({"ton": "info", "titre": "Léger déséquilibre", "texte": f"La jambe {strong} fournit {share} % de la puissance. Courant ; à suivre sur plusieurs sorties."})
        else:
            out.append({"ton": "warn", "titre": "Déséquilibre marqué", "texte": f"La jambe {strong} fournit {share} % de la puissance. Si ça se répète, relie-le à une douleur, "
                        "à la hauteur de selle ou aux cales (séance de capture : angles des deux genoux)."})
    bal = [b["equilibre_gauche_pct"] for b in serie if b.get("equilibre_gauche_pct") is not None]
    if len(bal) >= 8:
        n = max(2, len(bal) // 5)
        first, last = sum(bal[:n]) / n, sum(bal[-n:]) / n
        d = last - first
        if abs(d) >= 1.5:
            weak = "gauche" if d < 0 else "droite"
            out.append({"ton": "warn" if abs(d) >= 3 else "info", "titre": "L'équilibre change en fin de sortie",
                        "texte": f"En fin de sortie, la jambe {weak} fournit {_fr(round(abs(d), 1))} point{'s' if abs(d) >= 2 else ''} de moins qu'au début : "
                                 "elle fatigue plus vite. Fréquent avec une douleur ou une selle mal réglée d'un côté."})
        else:
            out.append({"ton": "ok", "titre": "Équilibre stable", "texte": "L'équilibre ne bouge pas entre le début et la fin de la sortie."})
    for key, name, gap in (("efficacite_couple", "Efficacité du couple", 5), ("fluidite", "Fluidité", 3)):
        v = g.get(key) or [None, None]
        if v[0] is not None and v[1] is not None and abs(v[0] - v[1]) >= gap:
            better = "gauche" if v[0] > v[1] else "droite"
            out.append({"ton": "info", "titre": f"{name} : écart entre les jambes",
                        "texte": f"{_fr(v[0])} % à gauche contre {_fr(v[1])} % à droite : la jambe {better} transmet sa force de façon plus régulière."})
    pg, pd = g.get("phase_puissance_g"), g.get("phase_puissance_d")
    if pg and pd:
        ds, de = (pd[0] - pg[0] + 180) % 360 - 180, (pd[1] - pg[1] + 180) % 360 - 180
        if abs(ds) >= 10 or abs(de) >= 10:
            parts = []
            if abs(ds) >= 10:
                parts.append(f"la jambe {'droite' if ds > 0 else 'gauche'} commence à pousser {round(abs(ds))}° plus tard")
            if abs(de) >= 10:
                parts.append(f"la jambe {'droite' if de > 0 else 'gauche'} arrête de pousser {round(abs(de))}° plus tard")
            out.append({"ton": "info", "titre": "Phases de poussée différentes", "texte": " ; ".join(parts).capitalize()
                        + ". Peut venir d'une cale, d'une jambe plus courte ou d'une gêne : à rapprocher des angles mesurés en vidéo."})
    return out


def detail(f: Any, configs: list[Any]) -> dict:
    v = view(f, configs)
    path = stored_file(f.summary or {})
    try:
        serie = series(path) if path else []
    except Exception:
        serie = []
    g = v.get("global") or {}
    v["serie"] = serie
    v["fichier_disponible"] = path is not None
    v["w_par_bpm"] = round(g["puissance_w"] / g["fc_bpm"], 2) if g.get("puissance_w") and g.get("fc_bpm") else None
    v["lecture"] = reading(g, serie)
    return v


def load(db: Any) -> tuple[list[dict], list[Any]]:
    """Toutes les sorties importées (les plus récentes d'abord) et les configurations du vélo."""
    from sqlmodel import select

    from posturale.storage.models import BikeConfig, FitFile

    configs = list(db.exec(select(BikeConfig)))
    rides = [view(f, configs) for f in db.exec(select(FitFile).where(FitFile.session_id == None))]  # noqa: E711
    return sorted(rides, key=lambda r: r.get("debut") or "", reverse=True), configs


def _fr(x: float, fmt: str = "g") -> str:
    """Nombre à la française (virgule décimale) pour les phrases lues ou affichées."""
    return format(x, fmt).replace(".", ",")


def _bal(x: float | None) -> str:
    return "—" if x is None else f"{round(x)}/{100 - round(x)}"


def road_check(cmp: dict, config_id: int | None) -> dict | None:
    """Le réglage en cours tient-il sur la route ? Sorties depuis le dernier changement contre celles d'avant."""
    a, b = cmp.get("avant"), cmp.get("apres")
    if not a or not b or (config_id is not None and b.get("config_id") != config_id):
        return None
    e = cmp.get("ecarts", {})
    parts = [f"Sur la route depuis « {b['libelle']} » : {b['sorties']} sortie{'s' if b['sorties'] > 1 else ''}, {_fr(b['heures'])} h"]
    if a.get("equilibre_gauche_pct") is not None and b.get("equilibre_gauche_pct") is not None:
        sym = e.get("asymetrie", 0)
        how = "plus symétrique" if sym <= -0.5 else "moins symétrique" if sym >= 0.5 else "sans changement net"
        parts.append(f"équilibre gauche/droite {_bal(b['equilibre_gauche_pct'])} contre {_bal(a['equilibre_gauche_pct'])} avant, {how}")
    if a.get("derive_equilibre") is not None and b.get("derive_equilibre") is not None:
        better = abs(b["derive_equilibre"]) < abs(a["derive_equilibre"]) - 0.3
        worse = abs(b["derive_equilibre"]) > abs(a["derive_equilibre"]) + 0.3
        parts.append("en fin de sortie longue, l'équilibre " + ("dérive moins" if better else "dérive davantage" if worse else "dérive autant"))
    if e.get("w_par_bpm") is not None and abs(e["w_par_bpm"]) >= 0.02:
        parts.append(f"{'plus' if e['w_par_bpm'] > 0 else 'moins'} de watts pour le même cardio ({_fr(e['w_par_bpm'], '+.2f')} W par battement)")
    texte = " ; ".join(parts) + "."
    if b["sorties"] < 3:
        texte += " Encore peu de sorties : c'est une tendance à confirmer."
    keep = ("libelle", "sorties", "heures", "equilibre_gauche_pct", "derive_equilibre", "efficacite_couple", "fluidite", "cadence_rpm", "w_par_bpm")
    return {"avant": {k: a.get(k) for k in keep}, "apres": {k: b.get(k) for k in keep}, "ecarts": e,
            "suffisant": b["sorties"] >= 3, "texte": texte}


def ai_summary(db: Any) -> dict | None:
    """Ce que le coach reçoit des sorties : volume, sorties longues, et avant / après le dernier réglage."""
    rides, configs = load(db)
    if not rides:
        return None
    cmp = compare(rides, configs)
    now = datetime.now(timezone.utc)
    recent = [r for r in rides if r.get("debut") and (now - _ts(r["debut"])).days <= 90]
    durs = [r.get("mouvement_min") or r.get("duree_min") or 0 for r in recent]
    return {
        "sorties_90_jours": len(recent),
        "heures_90_jours": round(sum(durs) / 60, 1),
        "plus_longue_min": max(durs) if durs else None,
        "sorties_de_plus_de_3h_90_jours": sum(1 for d in durs if d >= 180),
        "dernieres": [{"date": r["debut"][:10], "duree_min": r.get("mouvement_min") or r.get("duree_min"),
                       "puissance_w": (r.get("global") or {}).get("puissance_w"), "fc_bpm": (r.get("global") or {}).get("fc_bpm"),
                       "equilibre_gauche_pct": (r.get("global") or {}).get("equilibre_gauche_pct"), "reglage": r.get("config")}
                      for r in rides[:5]],
        "par_reglage": [{k: p.get(k) for k in ("libelle", "sorties", "heures", "equilibre_gauche_pct", "derive_equilibre",
                                               "efficacite_couple", "fluidite", "cadence_rpm", "w_par_bpm")} for p in cmp["periodes"]],
        "verification_dernier_reglage": road_check(cmp, None),
    }


def compare(rides: list[dict], configs: list[Any]) -> dict:
    """Regroupe les sorties par configuration et compare la dernière à celle d'avant."""
    groups: dict[Any, list[dict]] = {}
    for r in rides:
        groups.setdefault(r.get("config_id"), []).append(r)
    by_id = {c.id: c for c in configs}
    periods = []
    for cid, rs in groups.items():
        c = by_id.get(cid)
        periods.append({"config_id": cid, "libelle": (c.libelle if c else None) or ("Avant tes réglages enregistrés" if c is None else f"Configuration {cid}"),
                        "depuis": c.created_at.isoformat() if c else None,
                        "hauteur_selle_mm": c.hauteur_selle_mm if c else None, **aggregate(rs)})
    periods.sort(key=lambda p: p["depuis"] or "")
    out: dict[str, Any] = {"periodes": periods, "avant": None, "apres": None, "ecarts": {}}
    if len(periods) >= 2:
        a, b = periods[-2], periods[-1]
        out["avant"], out["apres"] = a, b
        for m in METRICS + ("w_par_bpm", "derive_equilibre"):
            if a.get(m) is not None and b.get(m) is not None:
                out["ecarts"][m] = round(b[m] - a[m], 2)
        if a.get("equilibre_gauche_pct") is not None and b.get("equilibre_gauche_pct") is not None:
            # plus près de 50/50 = plus symétrique
            out["ecarts"]["asymetrie"] = round(abs(b["equilibre_gauche_pct"] - 50) - abs(a["equilibre_gauche_pct"] - 50), 1)
    return out
