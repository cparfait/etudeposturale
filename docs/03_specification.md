# Phase 1 — Spécification

> Rédigé le 14/11/2026. S'appuie sur [00_etat_de_l_art.md](00_etat_de_l_art.md), [01_metriques.md](01_metriques.md) et [02_materiel.md](02_materiel.md).
> Ce document fixe **quoi** construire et **comment**, avec l'objectif immédiat de la phase 2 : le MVP « vérifier ma hauteur de selle ».
> Les décisions marquées **[à valider]** dépendent du benchmark (§ 8) ou d'une réponse du porteur de projet (§ 11).

---

## 1. Principes directeurs

1. **Mesurer juste avant de mesurer beaucoup.** Le MVP ne fait qu'une chose (le genou, la hanche, la cheville et le bassin vus de profil), mais avec une précision vérifiée (≤ 2–3° sur la flexion du genou en bas du coup de pédale).
2. **Enregistrer en natif, analyser après.** Les vidéos de mesure sont filmées avec l'application Appareil photo du téléphone (meilleure qualité, fréquence d'image élevée, pas de compression navigateur), puis importées. Le navigateur sert au **guidage en direct** et à l'interface, pas à l'enregistrement de mesure.
3. **Tout en local.** Aucune vidéo ne sort du PC. Pas de compte, pas de cloud, un seul utilisateur.
4. **Chaque valeur cible est sourcée et configurable** (`config/metrics.yaml`), jamais écrite en dur dans le code.
5. **Hypothèses, pas diagnostics.** Toute recommandation affiche sa source, sa fiabilité et l'avertissement médical.
6. **Un changement à la fois, petit, puis on remesure.** L'outil est conçu autour de la boucle « mesurer → régler → rouler → ressentir → remesurer ».

---

## 2. Parcours utilisateur

### 2.1 Parcours complet (cible, phases 2 à 5)

```
Accueil ─► Mon profil & douleurs ─► Mon vélo (cotes) ─► Auto-tests ─► Séance de capture ─► Analyse ─► Recommandation ─► Sorties test + ressentis ─► Nouvelle séance (A/B)
             (phase 4)               (phase 2 min.)     (phase 4)        (phase 2)          (phase 2)     (phase 2)          (phase 4)
```

### 2.2 Parcours du MVP (phase 2) — « Vérifier ma hauteur de selle »

| Étape | Écran | Ce que fait l'utilisateur | Ce que fait l'outil |
|---|---|---|---|
| 0 | **Mon profil / Mon vélo** (une fois, modifiable à tout moment) | Saisit taille, entrejambe, poids, modèle du vélo, angle du tube de selle, cotes B1…B10, cales | Crée le profil et la première *configuration de vélo* |
| 1 | **Nouvelle séance** | Confirme (ou modifie) la configuration en cours, coche les douleurs du moment (arrière, avant G…) et précise s'il s'agit d'une capture « reposé » ou « en fin d'effort » | Crée une *séance* rattachée à la configuration |
| 2 | **Préparation** | Suit la check‑list illustrée : pastilles, mire, éclairage, vélo de niveau, marques au sol | Affiche où coller chaque pastille (schéma) |
| 3 | **Calibration du téléphone** (une seule fois par téléphone et par mode vidéo) | Filme la mire ChArUco 20–30 s en la bougeant devant l'objectif | Calcule la distorsion de l'objectif, la mémorise |
| 4 | **Cadrage en direct** | Ouvre `https://<pc>:5180/cadrage` sur le Pixel 10 Pro, pose le téléphone sur le trépied | MediaPipe en direct : corps entier visible ? caméra à la bonne hauteur ? perpendiculaire (mire) ? lumière suffisante ? → feu vert |
| 5 | **Enregistrement** | Échauffement 10 min, puis passe dans l'appli Appareil photo, lance l'enregistrement, **clap**, pédale 60 s à la puissance demandée, change de côté (vélo retourné ou caméra déplacée), recommence | Affiche le minuteur du protocole et la puissance cible |
| 6 | **Import** | Branche le téléphone en USB (ou dépose les fichiers) | Copie les vidéos dans `data/`, lit les métadonnées (fps réel, résolution, date) |
| 7 | **Analyse** | Attend 1 à 3 min | Correction de distorsion → pastilles + modèle de pose → cycles → angles → statistiques → qualité |
| 8 | **Contrôle** | Regarde la vidéo avec squelette et pastilles superposés, corrige au besoin une pastille mal détectée | Signale les frames et cycles rejetés |
| 9 | **Résultat** | Lit le verdict | Pour chaque jambe : flexion du genou en bas (P1) dans la plage / trop tendue / trop pliée, **correction proposée en mm**, indicateurs liés (pied qui pointe, bassin), comparaison G/D, indice de qualité |
| 10 | **Après réglage** | Modifie la selle, refait une séance | Comparaison avant/après côte à côte |

---

## 3. Protocole de capture (MVP, vue de profil)

### 3.1 Installation

| Élément | Consigne | Vérifié automatiquement ? |
|---|---|---|
| Vélo | Sur le Neo 2T, roue avant calée, **axes de roues à niveau** (niveau à bulle sur la base) | Non (photo de contrôle) |
| Caméra | Pixel 10 Pro sur trépied, **objectif principal 1x** (jamais 0,5x), en paysage, à **2,5–3 m**, objectif **à hauteur de la selle**, axe optique perpendiculaire au plan du vélo | Oui : hauteur et perpendicularité via la mire, corps entier via MediaPipe |
| Mode vidéo | **1080p à 120 fps** si l'éclairage le permet, sinon 1080p à 60 fps ; stabilisation **désactivée** ; HDR désactivé ; mise au point et exposition verrouillées (appui long) | Oui : fps et résolution lus dans le fichier |
| Mire ChArUco | A3 ou A2 collée sur support rigide, **posée verticalement dans le plan médian du vélo** (contre le cadre, côté caméra, sans masquer le pédalier), visible pendant toute la prise | Oui : détection de la mire |
| Éclairage | 2 projecteurs LED continus, de part et d'autre de la caméra, pas de contre‑jour | Oui : luminosité et flou de mouvement estimés |
| Sol | Ruban adhésif : position des pieds du trépied et de la roue arrière | Non |
| Tenue | Cuissard et maillot ajustés, sombres et unis ; pieds dans les chaussures habituelles | Non |

Pourquoi la mire dans le plan du vélo : elle donne l'**échelle en mm dans le plan où bouge la jambe** (indispensable pour la correction en mm et pour le KOPS) et permet de vérifier que la caméra est bien de face par rapport à ce plan (une mire vue de biais apparaît trapézoïdale).

### 3.2 Pastilles (repères anatomiques)

Pastilles rondes de 15–20 mm, couleur fluo unique (vert) sur le corps, une autre couleur (orange) sur le vélo :

| Repère | Couleur | Utilisé pour |
|---|---|---|
| Grand trochanter | vert | Hanche (P1, P4, P10) |
| Épicondyle fémoral latéral | vert | Genou (P1, P2, P6) |
| Malléole latérale | vert | Cheville (P1, P5) |
| Talon (arrière de la chaussure) | vert | Pied (P5) |
| 5e tête métatarsienne (sur la chaussure) | vert | Pied (P5) |
| Acromion | vert | Tronc, épaule (P4, P7, P8) |
| Épicondyle huméral latéral | vert | Coude (P8, P9) |
| Styloïde ulnaire | vert | Coude (P9) |
| **Extrémité de l'axe de pédale** (côté caméra) | orange | Angle de manivelle → détection des cycles |
| Axe de pédalier (ou centre du plateau, une fois, image fixe) | orange | Centre de rotation de la manivelle |

Les repères anatomiques sont repérés **cycliste debout puis assis sur le vélo, manivelle à 6 h**, en palpant (guide illustré dans l'application). Les pastilles se décollent un peu sur la peau en mouvement : c'est une erreur connue (artefact de peau), acceptée et mesurée par le contrôle croisé (§ 9).

### 3.3 Déroulé d'une séance MVP

1. Échauffement 10 min, cadence libre.
2. Mire et cadrage validés (feu vert).
3. **Prise côté droit** : enregistrement, clap des mains face caméra, 60 s à **cadence 85–95 tr/min**, puissance stable en **endurance (Z2)** ; puis 60 s au **seuil** (optionnel).
4. **Prise côté gauche** : déplacer le trépied de l'autre côté (marques au sol) et recommencer. Le vélo ne bouge pas.
5. (Optionnel, lié à la douleur arrière) : même prise **en fin de sortie longue** pour mesurer l'effet de la fatigue.

Puissance imposée : au MVP, **le mode ERG est piloté par l'Edge 1050** (séance structurée avec paliers de puissance), sans développement. Le pilotage depuis l'application (Web Bluetooth) arrive en phase 3. Le .FIT de la séance sert à vérifier puissance et cadence pendant chaque prise.

### 3.4 Prises de vue des phases suivantes (pour mémoire)

| Vue | Appareil | Phase | Remarques |
|---|---|---|---|
| Profil D et G | Pixel 10 Pro | 2 | Mode 1 caméra, deux prises successives |
| Face | Pixel 7a | 3 | Pastilles centre de rotule + 2e orteil ; trajectoire du genou (F1–F3) |
| Dos | Pixel 7a (la webcam Logitech, à 30 fps, seulement en complément) | 3 | Pastilles sur les deux épines iliaques postéro‑supérieures (EIPS) ; bascule du bassin (D1–D3) |
| 3D | les 3 en même temps | 3/5 | Synchronisation clap + flash, calibration ChArUco commune, triangulation Pose2Sim |

---

## 4. Architecture

### 4.1 Vue d'ensemble

```
┌────────────────────────── Navigateur (Chrome PC / Pixel) ──────────────────────────┐
│  Front TypeScript (React + Vite)                                                   │
│  • Parcours, formulaires, carte des douleurs        • Cadrage en direct (MediaPipe)│
│  • Lecteur vidéo + calques (squelette, angles)      • Web Bluetooth (phase 3)      │
│  • Graphiques, rapport HTML → PDF                                                  │
└──────────────────────────────▲─────────────────────────────────────────────────────┘
                               │ HTTP/JSON + WebSocket (progression)  — réseau local
┌──────────────────────────────┴─────────────────── PC (RTX 4090) ───────────────────┐
│  Backend Python 3.11 (FastAPI)                                                     │
│  api/ ─► jobs (file d'attente locale, 1 analyse à la fois sur le GPU)              │
│  capture/      import vidéo, métadonnées (ffprobe), découpe des prises (clap)      │
│  calibration/  intrinsèques ChArUco, échelle et perpendicularité par prise         │
│  pose/         moteurs interchangeables : markers (OpenCV) · rtmw (rtmlib/ONNX)    │
│                · mediapipe ; fusion                                                │
│  kinematics/   angle de manivelle, cycles, filtrage, angles, statistiques          │
│  metrics/      calcul des métriques P1…P11 d'après config/metrics.yaml            │
│  fit/          import .FIT (fitdecode), recalage temporel                          │
│  rules/        règles d'aide à la décision, correction en mm                       │
│  report/       rendu HTML (Jinja2) → PDF (navigateur)                              │
│  storage/      SQLite (SQLModel) + data/ (vidéos, résultats .parquet)              │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Choix techniques justifiés

| Sujet | Choix | Pourquoi | Alternatives écartées |
|---|---|---|---|
| Langage d'analyse | **Python 3.11** | Tout l'écosystème utile y est (OpenCV, ONNX Runtime, NumPy/SciPy, fitdecode, Pose2Sim) | Rust : gain de vitesse inutile, le GPU fait le travail lourd ; à reconsidérer seulement pour un module chaud |
| Moteur de pose de mesure | **RTMW via `rtmlib`** (ONNX Runtime GPU) **[à valider par le benchmark]** | RTMW suit les pieds (talon, orteils) ; `rtmlib` évite l'installation MMCV/MMPose, réputée fragile sous Windows ; c'est la même brique que Pose2Sim | MMPose complet (installation lourde), ViTPose‑H, Sapiens (à évaluer si RTMW déçoit) |
| Repères de référence | **Pastilles détectées par OpenCV** | Points exactement sur les repères osseux ; précision attendue meilleure que tout réseau (§ 3.2 de l'état de l'art) | Sans marqueur seul : 3–9° d'erreur publiée, insuffisant |
| Guidage en direct | **MediaPipe Pose Landmarker** (tasks‑vision, WebAssembly/WebGPU) | Tourne dans le navigateur du téléphone, temps réel | Envoyer le flux au PC : latence, complexité |
| API | **FastAPI** + WebSocket | Typage (Pydantic), documentation auto, asynchrone pour la progression | Flask (moins adapté), Django (trop lourd) |
| Front | **React + Vite + TypeScript** | Écosystème le plus large (lecteur vidéo, graphiques, exemples MediaPipe et Web Bluetooth) | Svelte : très bien aussi, mais moins d'exemples ; choix réversible tôt |
| Graphiques | **uPlot** (courbes d'angle, rapides) + composants SVG maison (schémas) | Léger, rapide sur des milliers de points | Chart.js, Plotly (lourds) |
| Stockage | **SQLite** (SQLModel) + fichiers dans `data/` ; séries temporelles en **Parquet** | Un seul utilisateur, zéro serveur, sauvegarde = copier un dossier | PostgreSQL (inutile) |
| Rapport | **HTML** (Jinja2) imprimé en PDF par le navigateur | Un seul rendu à maintenir, mise en page CSS `@media print` | WeasyPrint (dépendances GTK sous Windows) |
| Paquets | **uv** (Python), **npm** (front) | Environnements reproductibles et rapides | pip + venv à la main |
| Vidéo | **ffmpeg/ffprobe** (métadonnées, fps réel, extraction audio du clap), OpenCV (lecture image par image) | Standard | — |

### 4.3 HTTPS sur le réseau local (point bloquant identifié)

Le navigateur n'autorise la caméra (`getUserMedia`) et le Bluetooth que dans un **contexte sécurisé** : `localhost` ou **HTTPS**. Le PC passe par `localhost`, mais le Pixel accède au PC par son adresse IP locale → il faut **HTTPS**.
Solution : certificat local généré par **mkcert**, autorité installée une fois sur les deux Pixel ; Vite et FastAPI servent en HTTPS sur le réseau local. Alternative de secours : `chrome://flags/#unsafely-treat-insecure-origin-as-secure` sur le téléphone (moins propre).

### 4.4 Arborescence du dépôt

```
etudeposturale/
├─ backend/
│  ├─ pyproject.toml
│  ├─ src/posturale/{api,capture,calibration,pose,kinematics,metrics,fit,rules,report,storage}/
│  └─ tests/                  # tests unitaires + jeux de données synthétiques
├─ frontend/
│  ├─ package.json, vite.config.ts
│  └─ src/{pages,components,live,ble,api}/
├─ config/
│  └─ metrics.yaml            # métriques, conventions, plages sourcées, seuils de qualité
├─ calibration/               # mires ChArUco (existant)
├─ tools/                     # scripts autonomes (générateur de mire, benchmark de pose)
├─ docs/
└─ data/                      # (ignoré par git) vidéos, base SQLite, résultats
```

---

## 5. Chaîne de traitement d'une prise de profil

```
vidéo ─► 1. métadonnées ─► 2. découpe ─► 3. distorsion ─► 4. mire ─► 5. points ─► 6. fusion ─► 7. manivelle ─► 8. cycles ─► 9. angles ─► 10. stats ─► 11. verdict
```

| # | Étape | Détail | Sortie |
|---|---|---|---|
| 1 | Métadonnées | ffprobe : fps **réel** (horodatages des images, les téléphones ont un fps variable), résolution, rotation, date de création | `CaptureMeta` |
| 2 | Découpe | Détection du **clap** dans l'audio (pic d'énergie) ; on garde la portion pédalée ; rejet des 5 premières secondes | intervalle utile |
| 3 | Distorsion | Correction avec les intrinsèques ChArUco du téléphone et du mode vidéo (calibrés une fois) | images corrigées (à la volée) |
| 4 | Mire | Détection ChArUco sur quelques images → **homographie** image → plan du vélo : échelle en mm/px, **angle de vue** (perpendicularité, Q3), hauteur de la caméra | `PlaneCalib` |
| 5 | Points | (a) **Pastilles** : seuillage HSV + composantes connexes + suivi image à image (prédiction de position, appariement) ; (b) **RTMW** : 133 points + score de confiance ; (c) MediaPipe (pour comparaison) | trajectoires 2D par repère et par moteur |
| 6 | Fusion | Pastille prioritaire quand elle est vue ; sinon point RTMW **recalé** (décalage moyen pastille ↔ point RTMW appris sur les images où les deux existent) ; marquage des trous | trajectoires fusionnées + origine de chaque point |
| 7 | Manivelle | Angle de manivelle = direction (axe de pédalier → pastille d'axe de pédale), 0° en haut, sens du pédalage ; repli : cercle ajusté sur la trajectoire de la malléole | angle de manivelle θ(t) |
| 8 | Cycles | Un cycle = passage de θ par 0° ; rejet des cycles de durée anormale (cadence ± 10 %) ou avec > 5 % de points manquants | liste de cycles |
| 9 | Angles | Projection dans le plan du vélo (homographie), interpolation des trous courts (< 50 ms), **filtre Butterworth passe‑bas** d'ordre 4 à phase nulle (fréquence de coupure 10 Hz : à 6 Hz le filtre sous-estime l'extension max du genou de 0,3 à 0,8°, mesuré sur données simulées ; à revoir sur vraies vidéos), calcul des angles en **flexion** | séries d'angles par cycle |
| 10 | Stats | Pour chaque métrique : valeur par cycle (extrême du cycle ou valeur à un angle de manivelle), puis moyenne ± écart‑type sur ≥ 20 cycles ; rejet des cycles aberrants (> 3 écarts médians absolus) | `MetricResult` par jambe |
| 11 | Verdict | Comparaison aux plages de `metrics.yaml` → statut, **correction en mm** (§ 6), qualité de mesure (Q1–Q7) | `Verdict` |

Ré‑échantillonnage : chaque cycle est aussi normalisé sur 0–360° de manivelle (pas de 1°) pour superposer les cycles et comparer avant/après indépendamment de la cadence.

---

## 6. De l'angle du genou à une correction en millimètres

La règle « 1° ≈ 2–3 mm » dépend de la longueur des jambes. On calcule plutôt la correction par **géométrie**, à partir des mesures de la prise elle‑même :

1. Dans le plan du vélo (en mm grâce à la mire), on mesure sur chaque cycle : longueur de cuisse `L1` (trochanter → épicondyle), longueur de jambe `L2` (épicondyle → malléole), et la position de la cheville en bas du coup de pédale.
2. En bas du coup de pédale, la distance hanche → cheville vaut `d = √(L1² + L2² − 2·L1·L2·cos(180° − flexion))`.
3. La flexion cible `f*` (milieu de la plage, ou bord le plus proche) donne une distance cible `d*`.
4. Monter la selle de `Δh` déplace la hanche **le long du tube de selle** (angle du tube de selle, ~73,5° sur un vélo de route, à lire sur la fiche de géométrie). On cherche `Δh` tel que la nouvelle distance hanche → cheville vaille `d*`, **à cheville inchangée** (hypothèse : le pied garde la même posture ; on l'affiche).
5. Résultat arrondi au mm, **plafonné à 5 mm par étape** (garde‑fou de [01_metriques.md § 7](01_metriques.md)), accompagné de la plage d'incertitude issue de l'écart‑type de P1.

Cette méthode est simple, vérifiable sur la prise suivante (on compare la flexion prédite et la flexion mesurée après réglage) et elle s'améliore avec les itérations. **[à valider]** sur les premières séances réelles.

---

## 7. Modèle de données (SQLite)

| Table | Champs principaux | Remarque |
|---|---|---|
| `bike` | modèle, taille, angle du tube de selle, stack, reach | un seul vélo, mais structure prête |
| `bike_config` | date, B1…B10 (hauteur, recul, inclinaison, drop, manivelle, cales…), note libre, photo(s) | une ligne par configuration testée |
| `session` | date, `bike_config_id`, objectif, conditions (puissance cible, durée d'échauffement), notes | une séance de capture |
| `camera_calib` | appareil, mode (résolution, fps), matrice intrinsèque, distorsion, erreur de reprojection, date | réutilisée entre séances |
| `capture` | `session_id`, vue (profil/face/dos), côté (G/D), appareil, chemin vidéo, fps réel, intervalle utile, `.FIT` associé | une prise vidéo |
| `analysis` | `capture_id`, moteur(s), version du code et de `metrics.yaml`, qualité Q1–Q7, chemins Parquet (trajectoires, cycles, angles) | rejouable : on peut réanalyser une vieille vidéo avec un meilleur moteur |
| `metric_result` | `analysis_id`, id métrique (P1…), jambe, moyenne, écart‑type, n cycles, statut | alimente verdicts et comparaisons |
| `recommendation` | `session_id`, réglage, valeur proposée, justification, source, statut (proposée / appliquée / annulée) | |
| `feedback` (phase 4) | `bike_config_id`, sortie test, douleurs par zone (0–10), RPE, confort | |
| `pain_map`, `self_test`, `profile` (phase 4) | | |

---

## 8. Benchmark des moteurs de pose (à faire en début de phase 2)

But : choisir le moteur de mesure **sur tes vidéos**, avec des chiffres.

| Élément | Contenu |
|---|---|
| Vidéos | 2 prises de profil (G et D), 60 s chacune, protocole § 3, **avec pastilles** |
| Moteurs | Pastilles (OpenCV) · RTMW‑x et RTMW‑l (`rtmlib`) · RTMPose‑x body (`rtmlib`) · MediaPipe Pose Heavy |
| Vérité terrain | **Pointage manuel dans Kinovea** de 40 images (20 en bas, 20 en haut du coup de pédale, sur des cycles différents) + **goniomètre** en statique, manivelle à 6 h (3 mesures) |
| Mesures | Pour P1, P2, P4, P5 : erreur absolue moyenne, biais (moyenne signée), écart‑type, erreur max ; taux d'images exploitables ; temps de calcul par minute de vidéo |
| Critère de choix | Erreur absolue moyenne sur P1 ≤ 2–3° ; à précision égale, le plus robuste (le moins de trous) |
| Outil | [`tools/benchmark_pose.py`](../tools/benchmark_pose.py) : extrait les angles de genou image par image pour chaque moteur disponible et les exporte en CSV ; le protocole détaillé est dans [04_benchmark_pose.md](04_benchmark_pose.md) |

Hypothèse de travail : **pastilles = mesure, RTMW = secours et contrôle**, MediaPipe = guidage seulement.

---

## 9. Validation de la précision (fil rouge, formalisé en phase 5)

| Test | Méthode | Cible |
|---|---|---|
| Exactitude | Angles mesurés vs Kinovea (images) et goniomètre (statique) | Erreur absolue moyenne ≤ 2–3° sur P1 |
| Répétabilité intra‑séance | 3 prises successives sans rien toucher | Écart‑type de P1 entre prises ≤ 1,5° |
| Reproductibilité inter‑séances | 2 séances à quelques jours, même réglage, réinstallation complète (pastilles recollées) | Écart de P1 ≤ 2–3° ; ICC ≥ 0,9 sur l'ensemble des métriques |
| Sensibilité | Selle déplacée de +5 mm puis −5 mm | Variation de P1 détectée, dans le sens attendu, cohérente avec la prédiction du § 6 |

La **sensibilité** est le test le plus parlant pour toi : si l'outil voit clairement un changement de 5 mm, il est utile pour régler la selle.

---

## 10. Phase 2 — Périmètre et critères d'acceptation du MVP

### 10.1 Inclus
- Backend : import d'une vidéo, calibration intrinsèque ChArUco, mire dans le plan, pastilles + RTMW, fusion, angle de manivelle, cycles, filtrage, métriques **P1, P2, P3, P4, P5, P6, P10**, verdict hauteur de selle avec correction en mm, indicateurs Q1–Q6.
- Front : écrans « Mon profil » et « Mon vélo » (toutes les cotes et les cales modifiables, historique des configurations), nouvelle séance, check‑list de préparation, **page de cadrage en direct** sur le téléphone, import, lecteur vidéo avec calques, page de résultat G/D, comparaison avant/après simple.
- Import .FIT de la séance (puissance et cadence pendant chaque prise, équilibre G/D en information).
- `config/metrics.yaml` comme source unique des plages.
- Tests unitaires sur données synthétiques (jambe simulée à angles connus) pour les étapes 7 à 11.

### 10.2 Exclu (phases suivantes)
Vues de face et de dos, 3D, pilotage du Neo depuis l'application, anamnèse et auto‑tests, rapport PDF complet, cales, haut du corps détaillé (P7–P9 calculés mais non interprétés).

### 10.3 Critères d'acceptation
1. Sur une prise de 60 s conforme au protocole, l'analyse produit ≥ 20 cycles valides par jambe en moins de 3 min sur la RTX 4090.
2. Erreur absolue moyenne sur P1 ≤ 3° par rapport au pointage Kinovea (objectif 2°).
3. Le test de sensibilité ±5 mm est détecté dans le bon sens sur les deux jambes.
4. Le verdict affiche : valeur ± écart‑type, plage et source, statut, correction en mm plafonnée à 5 mm, indicateurs liés, qualité, avertissement médical.
5. Aucune donnée ne quitte le PC (vérifiable : aucune requête sortante hors chargement des modèles au premier lancement).

### 10.4 Découpage en lots (ordre de réalisation)
1. Squelette du dépôt (backend uv + FastAPI, front Vite + React), `metrics.yaml`, base SQLite, écrans « Mon profil » et « Mon vélo ».
2. Noyau cinématique sur données synthétiques (manivelle, cycles, filtrage, angles, stats, correction en mm) — **testé avant toute vidéo**.
3. Calibration ChArUco (intrinsèques + plan) et import vidéo.
4. Détection et suivi des pastilles ; branchement RTMW ; fusion.
5. Benchmark sur tes premières vidéos → choix définitif du moteur.
6. API + pages front (séance, import, résultat, lecteur avec calques).
7. Cadrage en direct (MediaPipe, HTTPS mkcert).
8. Import .FIT, comparaison avant/après, test de sensibilité.

---

## 11. Réponses reçues (14/11/2026) et questions ouvertes

### 11.1 Réponses et conséquences

| Sujet | Réponse | Conséquence sur la conception |
|---|---|---|
| Modèle du vélo, taille, entrejambe, poids | **À saisir dans l'application** | Écrans **« Mon profil »** et **« Mon vélo »** dès le lot 1 : tous les champs sont modifiables à tout moment. L'angle du tube de selle (utilisé au § 6) a une valeur par défaut de 73,5°, signalée comme « valeur par défaut, à remplacer par la fiche de géométrie ». |
| Cotes actuelles (B1…B10) | **À saisir dans l'application** | Chaque modification crée une nouvelle *configuration* datée (`bike_config`), sans écraser la précédente → historique et comparaisons avant/après automatiques. |
| Pédales, cales, chaussures, semelles | **À saisir dans l'application** | Formulaire « Cales » dans « Mon vélo » (modèle, couleur/liberté, position avant‑arrière, rotation, latéral, rondelles, photo) ; listes de choix pour les modèles courants (Look Kéo, Shimano SPD‑SL, Time…) + saisie libre. |
| Changement récent avant la douleur avant gauche | **Sortie de 90 km, une première** (le .FIT du 18/10/2026 : 5 h 19, NP 166 W) | Un **pic de volume** est une cause très fréquente de douleur au genou, indépendamment des réglages **[pratique]**. L'outil doit donc : (1) toujours rappeler ce facteur dans les hypothèses ; (2) rendre prioritaire la **capture en fin d'effort** (§ 3.3, étape 5) pour voir si la position se dégrade avec la fatigue ; (3) suivre la dérive de l'équilibre G/D, déjà visible sur cette sortie (49,7/50,3 % → 47,4/52,6 %, la jambe gauche fournissant moins en fin de sortie). Si la douleur avant gauche persiste au repos ou plusieurs jours → avis médical. |
| Webcam Logitech | **30 fps** | **Non utilisée pour la mesure** des angles en dynamique (à 90 tr/min, 30 fps = 20 images par tour : trop peu, et flou de mouvement). Usages possibles : guidage, vue de dos en complément (bascule du bassin, mouvement lent), photos d'auto‑tests. Pour la 3D à 3 caméras, il faudra un 3e appareil à 60 fps (téléphone d'occasion) → [02_materiel.md](02_materiel.md) mis à jour. |

### 11.2 Questions encore ouvertes

| # | Question | Ce que ça change |
|---|---|---|
| 1 | Le Pixel 10 Pro propose‑t‑il 1080p à 120 fps sans stabilisation forcée dans l'appli Appareil photo ? | Fréquence d'image retenue au protocole (à vérifier sur le téléphone) |
| 2 | Accepte‑t‑on React (plutôt que Svelte) pour le front ? | Choix réversible seulement avant le lot 6 |
