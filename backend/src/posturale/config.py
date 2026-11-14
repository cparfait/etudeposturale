"""Chemins du projet et chargement du référentiel des métriques (config/metrics.yaml)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    """Racine du dépôt : premier parent contenant config/metrics.yaml."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "metrics.yaml").exists():
            return parent
    return Path.cwd()


def metrics_path() -> Path:
    return Path(os.environ.get("POSTURALE_METRICS", repo_root() / "config" / "metrics.yaml"))


def data_dir() -> Path:
    path = Path(os.environ.get("POSTURALE_DATA", repo_root() / "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@lru_cache(maxsize=1)
def load_metrics() -> dict[str, Any]:
    with metrics_path().open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def metric_range(metric_id: str, context: str = "dynamique") -> dict[str, Any] | None:
    """Plage indicative d'une métrique pour un contexte (dynamique, statique…)."""
    metric = load_metrics()["metrics"].get(metric_id)
    if not metric:
        return None
    return metric.get("plage", {}).get(context)
