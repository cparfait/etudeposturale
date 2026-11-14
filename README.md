# Étude posturale vélo

Outil local d'étude posturale (bike fit) à partir d'une webcam ou d'un téléphone, de pastilles et des capteurs du home trainer.
Premier objectif : **vérifier la hauteur de selle**. Tout est traité sur le PC, aucune vidéo n'est envoyée en ligne.

- Cadrage et décisions : [PROMPT_PROJET_ETUDE_POSTURALE.md](PROMPT_PROJET_ETUDE_POSTURALE.md)
- Phase 0 : [état de l'art](docs/00_etat_de_l_art.md), [métriques](docs/01_metriques.md), [matériel](docs/02_materiel.md)
- Phase 1 : [spécification](docs/03_specification.md), [benchmark de pose](docs/04_benchmark_pose.md), [référentiel sourcé](config/metrics.yaml)

## État (phase 2, lots 1–2)

| Partie | Contenu | État |
|---|---|---|
| `backend/` | API FastAPI (profil, vélo, historique des configurations), SQLite | ✅ testé |
| `backend/src/posturale/kinematics`, `metrics`, `rules` | Angles, cycles de pédalage, filtrage, statistiques, métriques P1–P10, verdict et correction de selle en mm | ✅ testé sur cycliste simulé |
| `frontend/` | Interface React : accueil, « Mon profil », « Mon vélo » (schéma des cotes, cales, historique) | ✅ vérifié dans le navigateur |
| Vidéo, calibration ChArUco, pastilles, RTMW | Lots 3–5 | à faire |

## Lancer l'application

Prérequis : Python 3.10+ et Node.js 20+.

Backend (une fois) :

```bash
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
```

Backend (à chaque fois), depuis la racine du dépôt :

```bash
backend/.venv/Scripts/python -m uvicorn posturale.api.main:app --port 8000 --app-dir backend/src
```

Interface (une fois, puis à chaque fois) :

```bash
npm --prefix frontend install
```

```bash
npm --prefix frontend run dev
```

Ouvrir http://localhost:5173. Les données sont dans `data/posturale.sqlite` (ignoré par git).

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest
```

Les tests valident le noyau d'analyse sur un **cycliste simulé** dont les angles sont connus : extension et flexion max du genou à ±0,7°, correction de selle qui ramène la flexion à la cible, détection d'un déplacement de selle de 5 mm.
