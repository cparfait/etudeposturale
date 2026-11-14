"""Import des fichiers .FIT (Garmin Edge 1050 + Favero Assioma Duo + cardio).

Champs exploités (vérifiés sur un vrai fichier, docs/00_etat_de_l_art.md § 3.4) : puissance, cadence,
fréquence cardiaque, équilibre G/D, phases de puissance. PCO toujours à 0 sur l'Assioma Duo : ignoré.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

FIELDS = ("power", "cadence", "heart_rate", "left_right_balance", "left_torque_effectiveness",
          "right_torque_effectiveness", "left_pedal_smoothness", "right_pedal_smoothness",
          "left_power_phase", "right_power_phase", "left_power_phase_peak", "right_power_phase_peak")


def decode_balance(raw: Any) -> float | None:
    """Équilibre FIT : bit 7 = la valeur concerne le côté droit, 7 bits bas = pourcentage. Renvoie le % GAUCHE."""
    if raw is None:
        return None
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    if not v & 0x80:  # côté inconnu : valeur inexploitable
        return None
    right = v & 0x7F
    if not 0 < right < 100:
        return None
    return 100.0 - right


def read_records(path: str | Path) -> list[dict]:
    import fitdecode

    out = []
    with fitdecode.FitReader(str(path)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.records.FitDataMessage) or frame.name != "record":
                continue
            rec: dict[str, Any] = {}
            for f in frame.fields:
                if f.name == "timestamp" or f.name in FIELDS:
                    rec[f.name] = f.value
            if "timestamp" in rec:
                ts = rec["timestamp"]
                if isinstance(ts, datetime) and ts.tzinfo is None:
                    rec["timestamp"] = ts.replace(tzinfo=timezone.utc)
                out.append(rec)
    return out


def _avg(values: Iterable) -> float | None:
    v = [float(x) for x in values if isinstance(x, (int, float))]
    return round(mean(v), 1) if v else None


def _phase_angles(recs: list[dict], key: str) -> list[float] | None:
    vals = [r[key] for r in recs if isinstance(r.get(key), (tuple, list)) and len(r[key]) >= 2]
    vals = [v for v in vals if all(isinstance(x, (int, float)) for x in v[:2])]
    if not vals:
        return None
    return [round(mean(v[0] for v in vals), 1), round(mean(v[1] for v in vals), 1)]


def summarize(recs: list[dict]) -> dict:
    """Moyennes sur un ensemble d'enregistrements (une prise, une heure, toute la sortie)."""
    pedaling = [r for r in recs if (r.get("cadence") or 0) > 20]
    bal = [b for b in (decode_balance(r.get("left_right_balance")) for r in pedaling) if b is not None]
    return {
        "n": len(recs),
        "puissance_w": _avg(r.get("power") for r in pedaling),
        "cadence_rpm": _avg(r.get("cadence") for r in pedaling),
        "fc_bpm": _avg(r.get("heart_rate") for r in recs),
        "equilibre_gauche_pct": round(mean(bal), 1) if bal else None,
        "efficacite_couple": [_avg(r.get("left_torque_effectiveness") for r in pedaling),
                              _avg(r.get("right_torque_effectiveness") for r in pedaling)],
        "fluidite": [_avg(r.get("left_pedal_smoothness") for r in pedaling),
                     _avg(r.get("right_pedal_smoothness") for r in pedaling)],
        "phase_puissance_g": _phase_angles(pedaling, "left_power_phase"),
        "phase_puissance_d": _phase_angles(pedaling, "right_power_phase"),
        "pic_phase_g": _phase_angles(pedaling, "left_power_phase_peak"),
        "pic_phase_d": _phase_angles(pedaling, "right_power_phase_peak"),
    }


def window(recs: list[dict], start: datetime, end: datetime) -> list[dict]:
    return [r for r in recs if start <= r["timestamp"] <= end]


def by_hour(recs: list[dict]) -> list[dict]:
    """Évolution heure par heure (dérive de l'équilibre G/D avec la fatigue)."""
    if not recs:
        return []
    t0 = recs[0]["timestamp"]
    out, h = [], 0
    while True:
        a, b = t0 + timedelta(hours=h), t0 + timedelta(hours=h + 1)
        chunk = window(recs, a, b)
        if not chunk:
            break
        s = summarize(chunk)
        out.append({"heure": h + 1, "puissance_w": s["puissance_w"], "cadence_rpm": s["cadence_rpm"],
                    "fc_bpm": s["fc_bpm"], "equilibre_gauche_pct": s["equilibre_gauche_pct"]})
        h += 1
    return out


def summarize_file(path: str | Path, capture_windows: dict[int, tuple[datetime, datetime]] | None = None) -> dict:
    recs = read_records(path)
    if not recs:
        raise ValueError("Aucun enregistrement « record » dans ce fichier .FIT.")
    out = {
        "debut": recs[0]["timestamp"].isoformat(),
        "fin": recs[-1]["timestamp"].isoformat(),
        "duree_min": round((recs[-1]["timestamp"] - recs[0]["timestamp"]).total_seconds() / 60, 1),
        "global": summarize(recs),
        "par_heure": by_hour(recs),
        "prises": {},
    }
    for cid, (a, b) in (capture_windows or {}).items():
        chunk = window(recs, a, b)
        if chunk:
            out["prises"][str(cid)] = summarize(chunk)
    return out
