# Étude posturale vélo

Outil local d'étude posturale (bike fit) à partir d'un téléphone, de pastilles colorées et des capteurs du home trainer.
Tout est traité sur le PC (RTX 4090) : aucune vidéo n'est envoyée en ligne.

- Cadrage et décisions : [PROMPT_PROJET_ETUDE_POSTURALE.md](PROMPT_PROJET_ETUDE_POSTURALE.md)
- Phase 0 : [état de l'art](docs/00_etat_de_l_art.md), [métriques](docs/01_metriques.md), [matériel](docs/02_materiel.md)
- Phase 1 : [spécification](docs/03_specification.md), [benchmark de pose](docs/04_benchmark_pose.md), [référentiel sourcé](config/metrics.yaml)
- Phases 2–5 : [état d'avancement et validation](docs/05_etat_et_validation.md)

## Ce que fait l'application

| Écran | Rôle |
|---|---|
| Mon profil, Mon vélo | Mensurations, géométrie, cotes et cales (schémas « où mesurer »), historique des configurations |
| Santé et ressentis | Carte des douleurs cliquable, 9 auto-tests guidés, questionnaire après chaque sortie |
| Séances de capture | Check-list, calibration ChArUco, dépôt des vidéos (profil, face, dos) et du .FIT, analyse automatique |
| Analyse | Verdict hauteur de selle + correction en mm, squelette superposé à la vidéo, courbe du genou, toutes les mesures sourcées |
| Recommandations | Hypothèses ordonnées comme chez un fitter (santé → charge → asymétrie → cales → selle → recul → manivelle) |
| Rapport | Synthèse imprimable / PDF, comparaison G/D et avant/après |
| Contrôle des pastilles | Sur une photo ou une image de la vidéo : pastilles trouvées, pipette, réglage des couleurs utilisé par les analyses |
| Cadrage en direct | MediaPipe dans le navigateur du téléphone : feu vert quand le cadrage est bon |
| Capteurs et ERG | Web Bluetooth : puissance et équilibre (Assioma), cardio, puissance imposée au Tacx Neo 2T |

## Installation

Prérequis : Python 3.10+, Node.js 20+, ffmpeg dans le PATH, pilote NVIDIA récent.

### En un clic (Windows)

Double-cliquer `scripts\installer.bat` (une fois), puis `scripts\lancer.bat` à chaque utilisation :
le backend et l'interface s'ouvrent dans deux fenêtres et le navigateur s'ouvre sur l'application.
Le script d'installation applique lui-même le correctif ONNX Runtime GPU décrit ci-dessous.

### À la main

#### Backend

```bash
cd backend && python -m venv .venv
```

```bash
backend/.venv/Scripts/python -m pip install -e "backend[dev,gpu]"
```

`rtmlib` tire la version CPU d'ONNX Runtime, qui masque la version GPU. Après l'installation :

```bash
backend/.venv/Scripts/python -m pip uninstall -y onnxruntime
```

```bash
backend/.venv/Scripts/python -m pip install --force-reinstall --no-deps onnxruntime-gpu==1.23.2 nvidia-cudnn-cu12==9.10.2.21
```

Vérification (doit afficher `GPU (CUDA)`) :

```bash
backend/.venv/Scripts/python -c "from posturale.pose.engines import available_engines; print(available_engines())"
```

Les modèles RTMW (~250 Mo) sont téléchargés depuis OpenMMLab à la première analyse.

#### Interface

```bash
npm --prefix frontend install
```

## Lancer

Backend, depuis la racine du dépôt :

```bash
backend/.venv/Scripts/python -m uvicorn posturale.api.main:app --port 8000 --app-dir backend/src
```

Interface :

```bash
npm --prefix frontend run dev
```

Ouvrir http://localhost:5173. Données dans `data/` (base SQLite, vidéos, résultats) — ignoré par git.

### Utiliser le téléphone (cadrage en direct, Bluetooth)

Le navigateur n'autorise la caméra et le Bluetooth qu'en HTTPS. Avec [mkcert](https://github.com/FiloSottile/mkcert) :

```bash
mkcert -install
```

```bash
cd frontend && mkdir -p certs && mkcert -cert-file certs/cert.pem -key-file certs/key.pem localhost 192.168.1.10
```

(remplacer `192.168.1.10` par l'adresse IP du PC), installer l'autorité `rootCA.pem` (dossier donné par `mkcert -CAROOT`) sur le téléphone, relancer l'interface, puis ouvrir `https://192.168.1.10:5173/cadrage` sur le téléphone.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest
```

36 tests : noyau cinématique sur cycliste simulé, chaîne vidéo complète sur vidéo synthétique avec pastilles (angles retrouvés à ~1°),
calibration ChArUco sur la vraie mire, vues de face et de dos, import .FIT, moteur de recommandations, API, réglage des couleurs de pastilles.
