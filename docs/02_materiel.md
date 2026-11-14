# Matériel nécessaire

> Prix indicatifs (novembre 2026). Déjà disponible : Pixel 10 Pro, Pixel 7a, webcam Logitech, Tacx Neo 2T, Assioma Duo, Garmin Edge 1050, Wahoo TRACKR, PC RTX 4090.

## 1. Pour le MVP « vérifier la hauteur de selle »

| Matériel | Rôle | Prix |
|---|---|---|
| Trépied (montant à ~1 m au moins, rotule) + pince smartphone | Pixel 10 Pro fixe, perpendiculaire, à hauteur de selle | 20–40 € |
| Pastilles rondes adhésives fluo 15–20 mm (vert + orange) ou kinésio colorée découpée | Marquer trochanter, genou, malléole, talon, 5e métatarse, épaule, coude, poignet | 5–10 € |
| **Mire ChArUco** imprimée (fichiers dans [`calibration/`](../calibration/)) + contrecollage sur Forex/Dibond/carton plume | Échelle en mm, distorsion de l'objectif, perpendicularité | 15–30 € |
| 2 projecteurs LED continus **sans scintillement**, IRC > 90 | Image nette à 60–120 fps | 30–60 € |
| Goniomètre à grands bras (30 cm) | Vérifier les angles mesurés | 10–15 € |
| Niveau à bulle, fil à plomb, mètre ruban, ruban adhésif de sol | Vélo à niveau, cotes, positions répétables | ~10 € |
| Cale de roue avant (si absente) | Vélo horizontal sur le Neo | 15–25 € |

**Sous‑total : ~80–150 €**

## 2. Pour la 3D à 3 caméras

| Matériel | Rôle | Prix |
|---|---|---|
| 2 trépieds + pinces supplémentaires | Pixel 7a de face, webcam derrière | 40–60 € |
| Rallonge USB active 5 m | Webcam éloignée du PC | 10–20 € |
| Batteries externes / câbles longs | Autonomie en enregistrement haute cadence | selon existant |

## 3. Optionnel

- Niveau laser à lignes croisées (25–50 €) : alignement caméras, niveau du vélo, verticale de l'axe de pédale.
- Pied à coulisse (~10 €) : position des cales.
- Tenue ajustée, unie, contrastée (cuissard noir) pour faire ressortir les pastilles.

**Total complet : ~150–250 €.** Inutile : autre caméra, centrales inertielles, système pro.

## 4. Webcam Logitech : 30 fps (confirmé le 14/11/2026)

- Trop lente pour mesurer des angles en pédalant (20 images par tour à 90 tr/min) → **réservée au guidage, à la vue de dos en complément et aux photos d'auto‑tests**.
- Pour la 3D à 3 caméras (phase 3/5) : prévoir un **3e appareil filmant en 1080p à 60 fps minimum**, par exemple un smartphone Android d'occasion récent (~100–150 €) ou une webcam 60 fps (~80–120 €). À acheter seulement si la 3D est confirmée après validation du 2D.

## 5. Mire ChArUco : mode d'emploi

| Fichier | Format | Cases | Marqueurs | Usage |
|---|---|---|---|---|
| `calibration/charuco_A3.pdf` | A3 paysage | 7 × 5 de 50 mm | 37,5 mm | Vue de profil, 2,5–3 m |
| `calibration/charuco_A2.pdf` | A2 paysage | 9 × 6 de 60 mm | 45 mm | Plus lisible de loin, conseillée pour la 3D |

1. Imprimer **à 100 %** (aucun « ajuster à la page »), en mat de préférence (pas de reflets).
2. Vérifier la règle de 100 mm au bas de la feuille ; si l'écart dépasse 1 mm, réimprimer.
3. Contrecoller sur un support rigide **parfaitement plan**.
4. Les paramètres exacts sont dans les fichiers `.json` voisins (utilisés par la calibration) ; régénération : `python tools/generate_charuco.py`.
