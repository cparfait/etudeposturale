# Phase 0 — Référentiel des métriques

> Base du futur fichier de configuration (`config/metrics.yaml`). Rédigé le 13/11/2026.
> Toutes les plages sont **indicatives** : elles servent à repérer une position atypique, pas à imposer une valeur.
> Fiabilité : **[étude]**, **[revue]**, **[pratique]** (consensus de fitters), **[descriptif]** (moyenne observée, pas une cible), **[à définir]**.

---

## 0. Conventions (valables pour tout l'outil)

- **Angles articulaires en flexion** : 0° = segment aligné (jambe tendue, bras tendu). Un « angle intérieur » de 145° = 35° de flexion. L'interface affiche toujours la convention.
- **Position de la manivelle** : 0° = haut (point mort haut, PMH), 90° = avant (« 3 h »), 180° = bas (point mort bas, PMB). Mesurée pour **chaque jambe** avec sa propre manivelle.
- **Instants de mesure** : la valeur à un instant (ex. PMB) est la **moyenne sur ≥ 20 cycles** ± écart‑type ; les extrêmes (ex. extension max) sont pris sur la courbe de chaque cycle, puis moyennés.
- **Repères anatomiques** (pastilles) : grand trochanter (hanche), épicondyle fémoral latéral (genou), malléole latérale (cheville), talon, 5e tête métatarsienne (pied), acromion (épaule), épicondyle huméral latéral (coude), styloïde ulnaire (poignet). Axe de pédale et axe de pédalier repérés sur le vélo.
- **Côté** : chaque métrique de jambe existe en **G** et **D** ; l'asymétrie = |G − D|.

---

## 1. Analyse dynamique — vue de profil (priorité MVP)

| ID | Métrique | Définition / repères | Plage indicative | Source | Réglage lié | Lien avec tes douleurs |
|---|---|---|---|---|---|---|
| P1 | **Flexion du genou à l'extension max** (≈ PMB) | Angle trochanter–épicondyle–malléole, minimum de flexion du cycle | **30–40°** en dynamique (33–43° faible intensité) ; 25–35° en statique | Holmes 1994 ; Ferrer‑Roca 2012 **[étude]** | **Hauteur de selle** (≈ 1° ↔ 2–3 mm, à calibrer) | < 30° → sur‑extension → **arrière du genou** |
| P2 | **Flexion du genou max** (≈ PMH) | Maximum de flexion du cycle | ~105–115° **[pratique, à vérifier]** | Retül (chiffres non confirmés) | Hauteur de selle, longueur de manivelle | Flexion forte → **avant du genou** |
| P3 | **Amplitude du genou** | P2 − P1 | ~70–80° **[à définir]** | — | Contrôle de cohérence | — |
| P4 | **Angle de hanche fermé** (≈ PMH) | Angle tronc (acromion–trochanter) / cuisse (trochanter–épicondyle), minimum | Indicatif route ~45–60° de fermeture **[pratique, conventions variables]** ; moyenne observée 77 ± 5° (autre convention) **[descriptif]** | Swart & Holliday ; guides commerciaux | Hauteur et recul de selle, hauteur de cintre, manivelle | Hanche très fermée → **douleur avant de hanche**, compensation du genou |
| P5 | **Plage de cheville** (ankling) | Angle jambe (épicondyle–malléole) / pied (talon–5e métatarse), min, max, amplitude | Amplitude ~15–25° **[pratique, à définir]** ; pied qui pointe fortement en bas = signal | Pratique de fitters | Hauteur de selle, cales | Pied qui « va chercher » la pédale → selle haute → **arrière du genou** |
| P6 | **Genou vs axe de pédale à 3 h** (KOPS) | Écart horizontal (mm) entre l'épicondyle et l'axe de pédale, manivelle à 90° | Autour de 0 mm (± 20 mm) — **point de départ, pas une règle** | Burke, Burt **[pratique]** | Recul de selle | Genou très en avant → charge accrue au genou (hypothèse) |
| P7 | **Angle du tronc** | Ligne acromion–trochanter vs horizontale | Route endurance ~40–50°, performance ~30–40° **[pratique]** | Guides de fitters | Hauteur/distance cintre | Lombaires, hanche |
| P8 | **Angle d'épaule** | Bras (acromion–coude) vs tronc | 80–100° ou ~112° selon convention **[pratique / descriptif]** | Swart & Holliday ; guides | Distance du cintre (reach) | Nuque, épaules |
| P9 | **Flexion du coude** | Bras / avant‑bras | ~15–25° (coude légèrement fléchi) ; moyenne 19 ± 8° **[descriptif]** | Swart & Holliday | Reach, hauteur cintre | Mains, épaules |
| P10 | **Mouvement vertical de la hanche** | Amplitude verticale du trochanter sur un cycle (mm) | Faible ; à comparer G/D **[à définir]** | — | Hauteur de selle | Selle haute → bassin qui monte/descend |
| P11 | **Stabilité de la tête** | Amplitude de déplacement de la tête | Faible **[à définir]** | — | Cockpit | Nuque |

---

## 2. Analyse dynamique — vue de face et de dos

| ID | Métrique | Vue | Définition | Plage indicative | Source | Lien avec tes douleurs |
|---|---|---|---|---|---|---|
| F1 | **Trajectoire médio‑latérale du genou** | Face | Déplacement latéral de l'épicondyle (ou centre de rotule) sur un cycle, en mm | Trajectoire verticale, déplacement faible (< ~20 mm) **[pratique, à définir]** | Fitters (Hogg) | Genou qui rentre/sort → cales, Q‑factor ; douleur intérieure/extérieure |
| F2 | **Alignement hanche–genou–pied** | Face | Écart latéral genou vs ligne hanche–2e orteil au PMH et à 3 h | **[à définir]** | — | Douleur avant du genou gauche |
| F3 | Asymétrie de trajectoire G/D | Face | Différence F1 gauche/droite | Faible | — | **Douleur gauche uniquement** |
| D1 | **Bascule du bassin** (roulis) | Dos | Inclinaison de la ligne entre les deux épines iliaques postérieures (ou crêtes iliaques) sur un cycle, en ° | Amplitude faible (quelques degrés) ; **bascule nette = selle trop haute** **[pratique]** | Guides de fitters | **Arrière du genou** |
| D2 | **Décalage latéral du bassin sur la selle** | Dos | Position moyenne du milieu du bassin vs axe de la selle | ~0 mm | — | Assise de travers → une jambe plus tendue → asymétrie |
| D3 | Inclinaison moyenne du bassin | Dos | Bassin plus bas d'un côté en moyenne | ~0° | — | Inégalité de longueur de jambes (fonctionnelle ou vraie) |

---

## 3. Capteurs (synchronisés avec la vidéo)

| ID | Métrique | Source | Usage |
|---|---|---|---|
| C1 | Puissance (W), cadence (tr/min) | Assioma (Bluetooth) / Neo | Conditions de la capture ; consigne ERG |
| C2 | **Équilibre de puissance G/D** (%) | Assioma (Bluetooth) | Asymétrie, à croiser avec F3/D2/D3 ; normal ~48–52 % **[pratique]** |
| C3 | Efficacité du couple, fluidité de pédalage (G/D) | Assioma → Edge 1050 (.FIT) | Qualité du pédalage, comparaison avant/après |
| C4 | Phases de puissance (début/fin, pic) G/D | Assioma → .FIT | Comparaison G/D, effet des réglages |
| C5 | Position du pied sur la pédale (PCO) | Assioma → .FIT | **Peut‑être indisponible sur la Duo [à vérifier]** ; sinon mesure par la vidéo de face |
| C6 | Fréquence cardiaque | Wahoo TRACKR | Intensité, fatigue |

---

## 4. Cotes du vélo (relevées à chaque configuration)

| ID | Cote | Comment la mesurer | Remarque |
|---|---|---|---|
| B1 | **Hauteur de selle** | Axe de pédalier → dessus de la selle, le long du tube de selle (mm) | Mesure de référence de tes changements |
| B2 | Recul de selle | Horizontale entre l'axe de pédalier et le bec de selle (mm) | Avec un niveau / fil à plomb |
| B3 | Inclinaison de selle | Niveau sur la selle (°) | |
| B4 | Drop selle–cintre | Différence de hauteur dessus de selle / dessus du cintre (mm) | |
| B5 | Distance selle–cintre / selle–cocottes | Bec de selle → centre du cintre / cocottes (mm) | |
| B6 | Potence (longueur, angle), entretoises | Lecture | |
| B7 | Largeur de cintre | Lecture | |
| B8 | **Longueur de manivelle** | Lecture : **175 mm** | |
| B9 | **Cales** : modèle, couleur (degré de liberté), position avant/arrière, rotation, latéral | Photo du dessous de la chaussure + mesure | |
| B10 | Stack / reach du cadre | Fiche géométrie Specialized 2020 taille 61 (modèle à préciser) | |

Option : photo de profil calibrée (mire dans le champ) pour mesurer B1–B5 automatiquement.

---

## 5. Évaluation hors vélo (auto‑tests guidés)

| ID | Test | Mesure | Intérêt pour la position |
|---|---|---|---|
| T1 | Entrejambe | mm (livre entre les jambes contre un mur) | Point de départ de la hauteur de selle |
| T2 | Taille, poids, longueur de bras/torse, largeur d'épaules | mm, kg | Cockpit |
| T3 | Largeur des ischions | Carton ondulé / mousse | Choix de selle |
| T4 | **Élévation jambe tendue** (ischios) | Angle (°), G et D, mesuré par caméra | Souplesse des ischios → tolérance à une selle haute / dos penché ; lien avec **arrière du genou** |
| T5 | **Test de Thomas** (fléchisseurs de hanche) | Positif/négatif + angle, G et D | **Douleur de hanche**, angle de hanche fermé toléré |
| T6 | Flexion dorsale de cheville (genou au mur) | cm / °, G et D | Ankling, hauteur de selle |
| T7 | Rotation de hanche | ° G et D | Alignement du genou, cales |
| T8 | **Squat sur une jambe** | Trajectoire du genou par caméra, G et D | Contrôle du genou → **douleur avant gauche** |
| T9 | Inégalité de longueur de jambes (estimation) | mm (allongé, malléoles) ; à confirmer par un pro si > 5 mm | Asymétrie, cales d'épaisseur |
| T10 | Avant‑pied varus/valgus, arche | Photo + observation | Coins de cales, semelles |
| T11 | Gainage | Durée | Stabilité du bassin |

---

## 6. Ressentis et douleurs (questionnaire)

- **Carte des douleurs** : zone précise (genou : avant / arrière‑intérieur / arrière‑extérieur / intérieur / extérieur ; hanche : avant / latérale / fessier ; lombaires ; nuque ; mains ; pieds ; périnée), côté, intensité 0–10, moment (après combien de km/heures, en montée, en danseuse), depuis quand.
- **Après chaque essai de réglage** : confort de selle, pression mains/périnée, engourdissements, douleur par zone (0–10), sensation de puissance, effort perçu (RPE 1–10), durée de la sortie test.
- **Point de départ actuel** : arrière du genou (tendons) sur les grosses sorties ; avant du genou gauche depuis peu ; hanche.

---

## 7. Règles d'aide à la décision (hypothèses à tester, jamais un diagnostic)

| Observation | Hypothèse | Action proposée |
|---|---|---|
| P1 < 30° **et/ou** D1 élevée **et/ou** pied qui pointe (P5) | Selle trop haute | Baisser de 3–5 mm, nouvelle capture |
| P1 > 40° | Selle trop basse | Monter de 3–5 mm |
| P1 ou D1 très différents entre G et D | Asymétrie (bassin, longueur de jambes, cales) | Vue de dos, test T9, vérifier cales ; si persistant → avis pro |
| P2 élevé + P4 très fermé | Haut du coup de pédale trop compressé | Vérifier hauteur de selle, puis manivelle plus courte (−5 à −10 mm) |
| F1 important d'un côté | Alignement genou/pied | Rotation/position latérale des cales, Q‑factor |
| Douleur qui augmente avec la durée | Fatigue → position qui se dégrade | Capture en fin d'effort, comparer P1/D1 début/fin |

Garde‑fous : un seul changement à la fois, ≤ 5 mm (≤ 2–3° pour une rotation de cale), au moins 2–3 sorties avant de juger ; douleur aiguë, gonflement, blocage, douleur au repos ou qui persiste → professionnel de santé.

---

## 8. Qualité de mesure (calculée et affichée à chaque capture)

| ID | Indicateur | Seuil |
|---|---|---|
| Q1 | Fréquence d'image effective | ≥ 60 fps |
| Q2 | Corps entier visible (taux de frames avec tous les repères) | ≥ 95 % |
| Q3 | Perpendicularité caméra (estimée via la mire) | ≤ 5° d'écart **[à définir]** |
| Q4 | Nombre de cycles valides | ≥ 20 |
| Q5 | Écart‑type de P1 entre cycles | ≤ 2–3° |
| Q6 | Écart entre pastilles et modèle de pose | Signalé si > 5 mm / 3° |
| Q7 | Validation ponctuelle vs Kinovea / goniomètre | Erreur cible ≤ 2–3° sur P1 |

---

## Sources principales
- [Revue « Bike fitting » (PMC9219349)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9219349)
- [Bini, Hume & Croft 2011 — hauteur de selle et genou](https://www.researchgate.net/publication/51167758_Effects_of_Bicycle_Saddle_Height_on_Knee_Injury_Risk_and_Cycling_Performance)
- [Bini — forces au genou avec/sans douleur](https://www.researchgate.net/publication/263587378_Effects_of_saddle_height_on_knee_forces_of_recreational_cyclists_with_and_without_knee_pain)
- [Revue systématique douleur du genou (Dovepress)](https://www.dovepress.com/potential-factors-associated-with-knee-pain-in-cyclists-a-systematic-r-peer-reviewed-fulltext-article-OAJSM)
- [Swart & Holliday — anthropométrie et configuration](https://pubmed.ncbi.nlm.nih.gov/35782160/)
- [Manivelles et cinématique — Université de Derby](https://repository.derby.ac.uk/download/87247aeaefdb6fa04d4efe9986f1dd5e31f2caf3281287cfc4f150561df96ec3/3661396/The%20impact%20of%20minor%20crank%20length%20adjustments%20on%20lower%20body%20cycling%20kinematics.pdf)
- [Recul de selle — Cycling Weekly](https://www.cyclingweekly.com/fitness/bike-fit/just-how-important-is-saddle-setback-plus-how-to-tell-if-yours-is-too-far-forwards-or-backwards)
- [FAQ Favero (Cycling Dynamics en ANT+)](https://cycling.favero.com/en/faq)
