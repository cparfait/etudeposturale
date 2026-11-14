# Phases 2 à 5 — État d'avancement et validation

> Mis à jour le 14/11/2026. Ce qui est fait, comment c'est vérifié, et ce qui reste à valider avec tes vraies vidéos et ton matériel.

## 1. Fait et vérifié

| Bloc | Contenu | Vérification |
|---|---|---|
| Noyau cinématique | Angles en flexion, angle de manivelle, cycles, comblement des trous, Butterworth 10 Hz à phase nulle, statistiques robustes, métriques P1–P10 | Cycliste simulé : P1/P2 à ± 0,7°, sensibilité 5 mm détectée |
| Correction de selle | Géométrique (cuisse, jambe, angle du tube de selle), plafonnée à 5 mm, incertitude | La correction calculée ramène la flexion à 35° ± 1° sur le modèle |
| Chaîne vidéo | ffprobe (fps réel), clap (audio), pastilles vertes/orange, pédalier = pastille immobile, côté filmé détecté par le sens de rotation, échelle par la manivelle ou la mire, RTMW pour nommer les pastilles | Vidéo synthétique avec pastilles + modèle de pose bruité (± 12 px) : P1 à ~0,6° de la vérité, côté G/D correct |
| Calibration ChArUco | Intrinsèques (distorsion), homographie du plan du vélo, perpendicularité | Vraie mire A3 mise en perspective : case de 50 mm retrouvée à ± 1 mm, échelle à 2 % |
| Vues de face / dos | F1–F3 (va-et-vient des genoux), D1–D3 (bascule du bassin) | Signaux synthétiques : amplitudes retrouvées |
| Moteur de pose | RTMW (rtmlib) sur la RTX 4090 | ≈ 41 ms/image en CUDA (vs 278 ms en CPU) ; cuDNN épinglé en 9.10 |
| .FIT | Puissance, cadence, FC, équilibre G/D décodé, phases, dérive heure par heure, fenêtres des prises | Décodage de l'équilibre testé ; champs conformes au fichier réel du 18/10 |
| Santé | Carte des douleurs (17 zones × côté), 9 auto-tests, ressentis | API + interface testées |
| Recommandations | Règles §7 de 01_metriques + charge, asymétrie, signaux d'alerte | Scénario « selle haute + douleur arrière + ischios raides » → bonne hypothèse en priorité ; alerte médicale en tête si douleur ≥ 7 |
| Interface | 11 écrans, thèmes clair/sombre, mobile 375 px sans débordement | Vérifiée dans le navigateur sur données de démonstration |

## 2. Écrit mais non validé sur le réel

| Élément | Pourquoi | Comment le valider |
|---|---|---|
| **Précision sur tes vraies vidéos** | Aucune vidéo réelle encore | Protocole [04_benchmark_pose.md](04_benchmark_pose.md) : pointage Kinovea de 40 images + goniomètre ; cible ≤ 2–3° sur P1 |
| Détection des pastilles en conditions réelles | Couleurs, reflets, flou dépendent de l'éclairage | Ajuster les plages HSV (`pose/markers.py`) sur la première vidéo |
| Pilotage du Tacx Neo 2T (FE-C sur BLE, repli FTMS) | Pas de matériel ici | Page Capteurs : connecter, imposer 150 W, vérifier sur le compteur |
| Équilibre G/D en Bluetooth (Assioma) | Champ optionnel du Cycling Power Service | Comparer à l'Edge 1050 |
| Cadrage en direct sur le Pixel | Nécessite HTTPS (mkcert) et la caméra du téléphone | README, section « Utiliser le téléphone » |
| Recalage .FIT ↔ vidéo | Repose sur l'horloge du téléphone (date de création du fichier) | Vérifier que les prises tombent dans la bonne fenêtre de puissance |

## 3. Non fait (choix assumés)

- **3D multi-caméra (Pose2Sim)** : nécessite un 3e appareil à 60 fps (la webcam est à 30 fps) et une validation préalable du 2D. Les vues de face et de dos sont analysées en 2D, chacune dans son plan.
- **Synchronisation automatique de plusieurs caméras** : inutile tant que chaque vue est analysée séparément.
- **Transcodage des vidéos pour la lecture dans le navigateur** : les vidéos H.264/HEVC des téléphones sont lues par Chrome ; un autre codec s'analyse mais ne s'affiche pas dans le lecteur.

## 4. Première séance réelle conseillée

1. Remplir « Mon profil », « Mon vélo » (angle du tube de selle sur la fiche Specialized), « Santé ».
2. Calibrer le Pixel 10 Pro (vidéo de la mire bougée 30 s), une seule fois.
3. Séance « reposé » : profil droit puis gauche, 60 s chacun, 85–95 tr/min, ERG en endurance.
4. Contrôler le squelette dans la page d'analyse ; faire le pointage Kinovea (§ 1 de 04_benchmark_pose.md).
5. Appliquer au plus une recommandation, rouler 2–3 sorties, remplir « Ressentis », refaire une séance → comparaison dans le rapport.
