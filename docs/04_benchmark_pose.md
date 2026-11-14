# Protocole de benchmark des moteurs de pose

> Rédigé le 14/11/2026 · à réaliser au début de la phase 2 · référence : [03_specification.md § 8](03_specification.md).
> But : choisir, **sur tes vidéos**, le moteur qui mesure le mieux la flexion du genou vue de profil.

## 1. Ce qu'on compare

| Moteur | Points | Rôle pressenti |
|---|---|---|
| Pastilles (OpenCV) | Exactement sur les repères osseux | Mesure de référence (ajouté au script en phase 2, lot 4) |
| **RTMW** (`rtmlib`, mode performance) | 133 points, dont talon et orteils | Mesure de secours, contrôle |
| RTMPose‑x body (`rtmlib`) | 17 points | Comparaison |
| MediaPipe Pose Heavy | 33 points | Guidage en direct (on vérifie qu'il ne suffit pas pour mesurer) |

## 2. Prises vidéo

Suivre le protocole de capture de la spec (§ 3) : Pixel 10 Pro, 1080p à 120 fps (ou 60), objectif 1x, 2,5–3 m, à hauteur de selle, mire ChArUco dans le plan du vélo, pastilles collées, éclairage LED.

1. **Profil droit**, 60 s en endurance, 85–95 tr/min.
2. **Profil gauche**, idem.
3. **Statique** : manivelle bloquée à 6 h (pédale en bas), 5 s immobile, pour la mesure au goniomètre.

## 3. Vérité terrain

1. **Goniomètre** (statique) : bras sur trochanter → épicondyle et épicondyle → malléole, 3 mesures, moyenne. Noter la valeur en **flexion** (180° − la lecture si le goniomètre donne l'angle intérieur).
2. **Kinovea** (dynamique) : ouvrir la vidéo, choisir **40 images** (20 en bas du coup de pédale, 20 en haut, sur des cycles différents), y placer l'outil « Angle » sur trochanter / épicondyle / malléole, noter l'angle et le **numéro d'image**.
3. Créer `data/kinovea_D.csv` (et `_G`) :

```csv
frame,flexion_deg
1234,36.5
1301,108.0
```

Kinovea affiche l'angle intérieur : convertir en flexion (180° − angle).

## 4. Lancer le script

Environnement Python dédié (une fois) :

```bash
python -m venv .venv-bench
```

```bash
.venv-bench/Scripts/pip install opencv-python numpy scipy rtmlib onnxruntime-gpu mediapipe
```

Modèle MediaPipe : télécharger `pose_landmarker_heavy.task` depuis la page officielle *MediaPipe Pose Landmarker* et le placer dans `models/` (ignoré par git). Les modèles RTMW/RTMPose sont téléchargés automatiquement par `rtmlib` au premier lancement.

```bash
.venv-bench/Scripts/python tools/benchmark_pose.py data/profil_D.mp4 --side D --mediapipe-model models/pose_landmarker_heavy.task --truth data/kinovea_D.csv
```

Sorties dans `data/benchmark/profil_D/` : `angles.csv` (une ligne par image) et `resume.csv` (un moteur par ligne).

## 5. Lire les résultats

| Colonne | Sens | Seuil visé |
|---|---|---|
| `erreur_abs_moy` | Écart moyen avec Kinovea (°) | **≤ 2–3°** |
| `biais` | Écart signé moyen : un moteur qui surestime toujours de 4° est corrigeable, un moteur dispersé ne l'est pas | proche de 0 |
| `erreur_max` | Pire image | < 6° |
| `P1_moy ± P1_et` | Extension max moyenne et dispersion entre cycles | écart‑type ≤ 2–3° |
| `images_ok_pct` | Images où les 3 points sont détectés avec confiance | ≥ 95 % |
| `ms_par_image` | Temps de calcul | informatif |

**Décision** : le moteur retenu pour la mesure est celui qui satisfait le seuil d'erreur avec le moins de trous. Résultats et choix à consigner en bas de ce fichier (§ 6), avec la date et les vidéos utilisées.

## 6. Résultats

*(à compléter après les premières vidéos)*
