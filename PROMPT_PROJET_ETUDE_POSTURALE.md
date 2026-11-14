# Prompt de lancement — Outil d'étude posturale vélo (webcam / smartphone)

> À coller tel quel au début d'une nouvelle session (Claude Code ou autre agent).
> Compléter d'abord la section **« 9. Réponses du porteur de projet »** en bas du fichier.

---

## 1. Rôle

Tu es à la fois :
- **un bike fitter expert** (méthodes statiques type Holmes/goniomètre, méthodes dynamiques type Retül / Guru / Shimano Bike Fitting, approche Steve Hogg pour les cales et les asymétries) ;
- **un ingénieur en vision par ordinateur et biomécanique** (estimation de pose 2D/3D, calibration caméra, traitement du signal) ;
- **un développeur full‑stack** capable de livrer une application utilisable par un non‑spécialiste.

Ton objectif : concevoir et développer un outil qui permet de réaliser **une étude posturale complète, équivalente à celle d'un spécialiste**, à partir d'une webcam ou d'un téléphone, enrichie par des photos, des données capteurs et des ressentis.

Règle d'or : **on se documente avant de coder.** Les besoins et les métriques d'abord, la technologie ensuite.

---

## 2. Contexte matériel

- Home trainer **Tacx Neo 2T** (direct drive, Bluetooth FTMS + ANT+ FE‑C → pilotable en mode ERG pour imposer une puissance constante pendant les captures).
- Pédales capteur de puissance **Favero Assioma Duo** (double face : puissance G/D, équilibre G/D, cadence ; en ANT+ « Cycling Dynamics » : *Platform Center Offset* (position du pied sur la pédale), phases de puissance, efficacité du couple, fluidité de pédalage).
- Caméras : webcam PC et/ou smartphone(s) (à préciser, voir questions).
- Utilisateur final : un cycliste **non spécialiste** → l'outil doit guider chaque étape (placement caméra, marqueurs, protocole, interprétation).

---

## 3. Phase 0 — Recherche documentaire (OBLIGATOIRE avant tout code)

Produis un document `docs/00_etat_de_l_art.md` qui couvre :

1. **Le déroulé complet d'une étude posturale professionnelle** (entretien, évaluation physique, mesures du vélo, analyse dynamique, ajustements itératifs, rapport).
2. **Le référentiel des métriques** : définition exacte, convention de mesure (angle intérieur vs flexion !), plage cible, source scientifique, et *dans quel cas la plage change* (route/CLM/VTT/gravel, statique vs dynamique, intensité).
3. **Les technologies de capture** et leur précision publiée.
4. **Les outils existants** (commerciaux et open source) : ce qu'on peut réutiliser, ce qu'on doit écrire.
5. Les **limites** (2D vs 3D, occlusions, distorsion objectif, jitter) et comment les compenser.

Cite systématiquement les sources (articles, docs officielles). Signale clairement ce qui est vérifié vs supposé.

### Pistes déjà identifiées (à approfondir et vérifier)

**Référentiel biomécanique**
- Angle de flexion du genou au point mort bas : 25–35° en statique (Holmes 1994), ~30–40° en dynamique (Ferrer‑Roca 2012) — attention aux conventions (flexion vs angle intérieur 145–155°). Revue : *Bike fitting: a review* [PMC9219349](https://pmc.ncbi.nlm.nih.gov/articles/PMC9219349).
- *Cycling Biomechanics Optimization – the (R)Evolution of Bicycle Fitting* [PubMed 31834181](https://pubmed.ncbi.nlm.nih.gov/31834181/).
- Plages Retül (genou en flexion max/extension, hanche, épaule, coude…) à retrouver depuis une source primaire.

**Précision de la capture sans marqueur**
- Pose2Sim (multi‑caméras, open source) : erreur moyenne ~4° en cyclisme vs système à marqueurs, cheville partiellement occultée [PMC9002957](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9002957/).
- OpenCap en cyclisme (2 iPhones, OpenSim) : précision comparable pour hanche/genou en flexion‑extension, cheville moins bonne [arXiv 2409.03766](https://arxiv.org/pdf/2409.03766v3.pdf).
- Comparaison réseaux open source (OpenPose / MSRA) pour les angles en pédalage : [Springer s11332‑023‑01075‑7](https://link.springer.com/content/pdf/10.1007/s11332-023-01075-7.pdf).

**Moteurs d'estimation de pose à évaluer**
- MediaPipe Pose Landmarker (33 points, tourne dans le navigateur / mobile, temps réel).
- RTMPose / RTMW / ViTPose via MMPose (plus précis, Python, exportable ONNX → `onnxruntime-web`).
- Pose2Sim (calibration + triangulation multi‑caméra), OpenCap (pipeline cloud + OpenSim).
- **Hybride marqueurs** : pastilles colorées / ArUco sur les repères anatomiques (grand trochanter, épicondyle fémoral latéral, malléole latérale, 5e métatarse, acromion, épicondyle huméral, styloïde ulnaire) → amélioration nette de la précision, à comparer au sans‑marqueur.

**Outils existants (à analyser, pas à copier)**
- Commerciaux : MyVeloFit (IA webcam), Bike Fast Fit, Retül, Shimano Bike Fitting, Guru, MyBikeFitting (gratuit).
- Open source / réutilisables : **Kinovea** (analyse vidéo manuelle, utile comme vérité terrain), **QuickPose BikeVision** (exemple iOS Apache 2.0, SDK propriétaire), [AndreaBe99/computer-vision-project](https://github.com/AndreaBe99/computer-vision-project) (à vérifier), repo AUT d'angle du genou MediaPipe [openrepository.aut.ac.nz](https://openrepository.aut.ac.nz/items/c4b011fc-2b3c-4f09-bd47-4c231e7dcdaf), Pose2Sim, OpenCap.
- Capteurs : Web Bluetooth (Chrome) → *Cycling Power Service* (Assioma) et *FTMS* (Neo 2T, contrôle ERG). Cycling Dynamics (PCO, phases) passent surtout en ANT+ → prévoir **l'import d'un fichier .FIT** enregistré par un compteur Garmin/autre.

### Benchmark MyVeloFit (observé sur le portail et leur documentation, nov. 2026)

**Ce qu'il fait (base minimale à égaler) :**
- Paramètres de session : **objectif** (Performance / Performance et confort / Confort) × **type de vélo** (route, gravel/CX, VTT, triathlon, CLM, hybride, vélo d'appartement, smart bike) → les plages cibles dépendent de ce couple, avec un schéma de la position visée.
- Une seule vidéo **de profil**, 15–20 s, après 10–15 min d'échauffement, 75–95 tr/min, mains sur les cocottes (prolongateurs en CLM), vêtements ajustés et contrastés, caméra sur trépied à hauteur de selle, à 2–3 m, perpendiculaire, en paysage, sans grand‑angle (0,5x) ni 4K, axes de roues à niveau, **positions caméra/vélo marquées au sol** pour la répétabilité.
- Rapport : 4 réglages (hauteur de selle, recul de selle, hauteur de cintre, reach de cintre), chacun avec **position actuelle dans une plage cible + recommandation**, plus des notes libres ; angles agrégés sur tous les cycles à 3 instants (haut, bas, avant du coup de pédale) ; vue d'ensemble avec centre de masse et trajectoires du genou, de la hanche et de l'épaule ; vidéo avec squelette superposé (pour contrôler la qualité du suivi) ; **comparaison avant/après** (fondu ou curseur) ; historique des séances ; suggestion de longueur de manivelle à partir du haut du coup de pédale.
- Module séparé de **choix de taille de vélo** par scan corporel.

**Ce qu'il ne fait pas (là où notre outil apporte quelque chose) :**
- Pas de vue de face ni de dos (trajectoire du genou, bascule du bassin), une seule jambe analysée → pas d'asymétrie gauche/droite.
- Pas de cales, pas de capteurs (puissance, équilibre G/D, position du pied sur la pédale), pas de séances à plusieurs intensités ni de pilotage du home trainer.
- Pas d'entretien, de carte des douleurs, d'auto‑tests physiques ni de questionnaire de ressentis après les essais.
- Traitement dans le cloud (vidéos envoyées chez eux) ; nombre de sessions limité dans l'offre gratuite.

---

## 4. Périmètre fonctionnel attendu (tout le spectre d'une étude pro)

### 4.1 Entretien / anamnèse (formulaire guidé)
- Profil : âge, taille, poids, niveau, discipline(s), volume hebdo, objectifs (confort, performance, aéro, longue distance).
- Historique : blessures, opérations, douleurs actuelles → **carte du corps cliquable** (zone, côté, intensité 0–10, moment d'apparition : après X km, en montée, en danseuse…).
- Matériel : vélo(s), taille cadre, selle, chaussures, semelles, cales, longueur de manivelle, cotes actuelles.

### 4.2 Évaluation physique hors vélo (auto‑tests guidés, assistés par caméra quand c'est possible)
- Mesures anthropométriques : entrejambe, longueur torse/bras, largeur d'épaules, largeur des ischions, pointure, longueur de pied.
- Souplesse / mobilité : élévation jambe tendue (ischios), test de Thomas (fléchisseurs de hanche), flexion dorsale de cheville (knee‑to‑wall), rotation de hanche, flexion avant.
- Alignements : inégalité de longueur de jambes (estimation), varus/valgus de l'avant‑pied, arche plantaire, squat sur une jambe (contrôle du genou).
- Stabilité du tronc (gainage simple).
→ Chaque test : vidéo/photo explicative + saisie du résultat + mesure automatique d'angle par la caméra si faisable.

### 4.3 Relevé des cotes du vélo
Hauteur de selle (axe pédalier → dessus de selle), recul de selle, inclinaison de selle, stack/reach, drop selle‑cintre, distance selle‑cintre, longueur/angle de potence, largeur de cintre, position des cocottes, longueur de manivelle, position et rotation des cales, Q‑factor / rondelles.
→ Possible aide par photo calibrée (règle/mire ArUco dans le champ).

### 4.4 Analyse dynamique sur home trainer (cœur de l'outil)
Protocole : échauffement, puis captures à **plusieurs intensités imposées en ERG** (ex. endurance ~Z2 et seuil), cadence contrôlée, mains en haut / cocottes / bas du cintre (ou prolongateurs), éventuellement en fin d'effort (fatigue).

| Vue | Métriques (par cycle de pédalage, moyenne ± écart‑type, G/D) |
|---|---|
| **Côté** (G et D) | Angle du genou en extension max (PMB) et flexion max (PMH) ; angle de hanche fermé au PMH ; plage de cheville (ankling) ; angle du dos/tronc ; angle épaule (bras‑tronc) ; angle du coude ; position genou vs axe de pédale à 3 h (KOPS) ; position du pied ; mouvement de la tête |
| **Face** | Trajectoire du genou (déplacement médio‑latéral), alignement hanche‑genou‑cheville‑pied, symétrie |
| **Arrière** | Bascule / roulis du bassin, déplacement latéral, asymétries, position sur la selle |
| **Dessus** (optionnel) | Rotation des épaules, alignement des pieds |

Traitement : détection automatique des cycles (trajectoire du pied/cheville ou cadence capteur), filtrage (Butterworth), rejet des frames peu fiables (score de confiance), indicateur de qualité de capture.

Fusion capteurs : puissance G/D, équilibre, cadence, PCO, phases de puissance, efficacité du couple, fluidité → synchronisées avec la vidéo.

### 4.5 Ressentis et itérations (A/B)
- Après chaque réglage : questionnaire court (confort selle, pression mains/périnée, engourdissements, douleurs localisées, sensation de puissance, RPE).
- Historique des configurations → comparaison avant/après (angles + capteurs + ressentis).
- Aide au diagnostic : règles de type « douleur genou antérieure → selle trop basse/avancée ? », « douleur postérieure → selle trop haute/reculée ? », « latérale/médiale → cales/rotation/Q‑factor ? » — toujours présentées comme **hypothèses**, pas comme un diagnostic médical.

### 4.6 Recommandations et rapport
- Recommandations chiffrées (mm, degrés) avec **ordre logique des réglages** (cales → hauteur de selle → recul → cockpit) et **changements progressifs** (ex. ≤ 5 mm à la fois).
- Rapport PDF/HTML : synthèse, captures annotées (squelette + angles), graphiques, comparatif avant/après, recommandations, plan de suivi.
- Avertissement clair : outil d'aide, ne remplace pas un avis médical / un fitter en cas de douleur persistante.

### 4.7 Photos complémentaires
Import de photos (pied nu, chaussures/cales, vélo de profil, assise), annotées et rattachées à l'étude.

---

## 5. Exigences techniques

- **Guidage de capture** : vérification automatique du cadrage (corps entier visible, caméra perpendiculaire, hauteur ≈ pédalier/hanche, distance, éclairage, fps ≥ 60 si possible), calibration d'échelle et de distorsion (mire ChArUco/ArUco imprimable).
- **Confidentialité** : traitement local par défaut (vidéos d'une personne). Pas d'envoi cloud sans accord explicite.
- **Précision mesurée** : protocole de validation interne — comparaison aux mesures manuelles (goniomètre, Kinovea), test‑retest (répétabilité, ICC), cible d'erreur à définir (ex. ≤ 3° sur le genou en vue de côté).
- **Code** : modulaire (capture / pose / métriques / capteurs / règles d'expertise / rapport), testé, documenté ; métriques et plages cibles dans un fichier de configuration sourcé (pas en dur).

Architecture retenue (détails et justification en section 9, à challenger en phase 0) :
- Front : application web (TypeScript, React ou Svelte + Vite) → guidage de cadrage en direct (MediaPipe), Web Bluetooth (Neo 2T FTMS/ERG, Assioma, Wahoo TRACKR), formulaires, carte des douleurs, rapports.
- Analyse : backend **Python local** (FastAPI) sur **RTX 4090** → RTMPose/RTMW ou ViTPose (CUDA), détection des pastilles (OpenCV), synchronisation multi‑caméra (son/flash), calibration ChArUco, triangulation 3D (Pose2Sim), NumPy/SciPy (cycles, filtrage, stats), import .FIT Edge 1050 (`fitdecode`), stockage SQLite.
- 3 caméras : Pixel 10 Pro (profil), Pixel 7a (face), webcam Logitech (dos ou profil opposé) ; mode 1 caméra toujours disponible.

---

## 6. Plan de travail attendu

1. **Phase 0 – État de l'art** (`docs/00_etat_de_l_art.md`) + **référentiel des métriques** (`docs/01_metriques.md`, tableau sourcé).
2. **Phase 1 – Spécification** : parcours utilisateur, protocole de capture, architecture, choix techno justifiés (benchmark MediaPipe vs RTMPose sur mes vidéos).
3. **Phase 2 – MVP « vérifier ma hauteur de selle »** : vidéo de profil au Pixel 10 Pro + pastilles + mire ChArUco, guidage de cadrage, détection des cycles, angle du genou en bas et en haut du coup de pédale, angle de hanche, cheville, bascule du bassin, verdict « dans la plage / trop haut / trop bas » avec correction en mm, contrôle croisé au goniomètre ou dans Kinovea. Puissance imposée par le Neo 2T en ERG si c'est simple à brancher.
4. **Phase 3** : vues de face et de dos (Pixel 7a, webcam), synchronisation, trajectoire du genou, asymétries G/D, 3D multi‑caméra, fusion Assioma/cardio + import .FIT de l'Edge 1050, cales.
5. **Phase 4** : anamnèse, auto‑tests physiques, ressentis, itérations A/B, moteur de recommandations.
6. **Phase 5** : validation de précision, rapport complet, (option) 3D multi‑caméra.

À chaque phase : livrable démontrable + liste de questions ouvertes.

---

## 7. Ce que tu dois faire en premier

1. Lire la section 9 (mes réponses et les décisions qui en découlent).
2. Me poser **seulement les questions encore manquantes** (groupées, en disant pourquoi chacune change la conception), par exemple : description précise de mes douleurs genou/hanche, cotes actuelles du vélo, type de pédales/cales, longueur de manivelle.
3. Lancer la phase 0 et me présenter l'état de l'art **avant** de proposer du code, en mettant l'accent sur : hauteur de selle, douleurs genou/hanche, précision 2D avec pastilles vs 3D multi‑caméra, synchronisation de 3 appareils différents.
4. Me donner la liste d'achats définitive (avec ordre de prix) avant la phase 2.

---

## 8. Hors périmètre / garde‑fous

- Pas de diagnostic médical. Douleurs aiguës ou persistantes → orienter vers un professionnel de santé.
- Ne pas copier le code, les visuels ou les textes d'outils commerciaux.
- Toute valeur cible affichée doit être sourcée et marquée comme « plage indicative ».

---

## 9. Réponses du porteur de projet (13/11/2026)

| # | Question | Réponse |
|---|---|---|
| 1 | Pour qui ? | Pour moi seul (pas de multi‑utilisateur, pas de mode « fitter/clients »). |
| 2 | Discipline | Route, un seul vélo. |
| 3 | Objectif | Confort / prévention des douleurs **et** performance (objectif « performance et confort »). |
| 4 | Douleurs / historique | **Douleurs au genou et à la hanche.** Jamais fait d'étude posturale. |
| 5 | Caméras | **3 appareils utilisables en même temps** : Google Pixel 10 Pro, Google Pixel 7a, webcam Logitech. |
| 6 | Espace / éclairage | De la place autour du home trainer, éclairage possible. |
| 7 | Marqueurs | Oui, j'accepte de coller des pastilles. |
| 8 | Compteur / cardio | Garmin Edge 1050 (enregistre les Cycling Dynamics des Assioma en .FIT) + ceinture cardio Wahoo TRACKR. |
| 9 | Plateforme / matériel | Application web ; PC avec **RTX 4090**. |
| 10 | Local / cloud | Local de préférence, cloud acceptable si nécessaire. |
| 11 | Stack | Pas de préférence : « le mieux pour l'app » (Rust évoqué). |
| 12 | Budget | Petits achats possibles s'ils améliorent nettement la précision. |
| 13 | Cales | Oui, inclure le relevé et le réglage des cales. |
| 14 | Auto‑tests physiques | Oui. |
| 15 | Rapport | Complet (niveau « fitter »). |
| 16 | Langue | Français. |
| 17 | Premier usage | **Vérifier ma hauteur de selle.** |
| 18 | Échéance | Aucune. |

### Décisions qui en découlent (à valider en phase 0/1)

**Priorités cliniques (genou + hanche)**
- Le MVP vise la **hauteur de selle** (angle du genou en bas du coup de pédale), mais doit aussi relever d'emblée les indicateurs liés aux douleurs genou/hanche : flexion max du genou en haut du coup de pédale, angle de hanche fermé, **bascule du bassin** et balancement sur la selle (signe de selle trop haute), **trajectoire du genou vue de face** (genou qui rentre ou sort), asymétries gauche/droite, recul de selle.
- La carte des douleurs doit distinguer la localisation précise (genou avant / arrière / intérieur / extérieur ; hanche avant / latérale / fessier) car chaque zone renvoie à des causes de réglage différentes (selle, recul, cales, Q‑factor, longueur de manivelle).
- Les cales passent tôt dans la séquence de réglages (rotation, avance/recul, écartement), en s'appuyant aussi sur la position du pied mesurée par les Assioma.

**Capture : 3 caméras → 3D possible**
- Configuration cible : **Pixel 10 Pro de profil** (caméra principale, la plus précise), **Pixel 7a de face**, **webcam Logitech derrière** (ou de profil côté opposé pour l'asymétrie G/D). Mode 1 caméra conservé comme mode de base.
- Évaluer deux approches : (a) chaque vue analysée en 2D dans son plan (simple, robuste) ; (b) **reconstruction 3D** par triangulation multi‑caméra (Pose2Sim : calibration ChArUco + triangulation + éventuel modèle OpenSim).
- Problème clé à résoudre : la **synchronisation** de 3 appareils différents. Pistes : enregistrement local sur chaque téléphone (meilleure qualité, 60 fps ou plus) puis recalage automatique par corrélation du son (clap) et/ou d'un événement visuel (flash LED), plutôt qu'un flux en direct par le navigateur. Le guidage de cadrage en direct peut, lui, passer par le navigateur du téléphone.
- Les pastilles sont la base de la précision : pastilles de couleur vive (ou mini ArUco) sur grand trochanter, épicondyle fémoral latéral, malléole latérale, talon, 5e métatarse, acromion, épicondyle huméral, styloïde ulnaire ; détection OpenCV fusionnée avec l'estimation de pose.

**Capteurs**
- Temps réel dans le navigateur (Web Bluetooth, Chrome) : Neo 2T en **FTMS** (mode ERG pour imposer la puissance), Assioma en **Cycling Power Service** (puissance, équilibre G/D, cadence), Wahoo TRACKR en **Heart Rate Service**.
- Données fines : **import du .FIT de l'Edge 1050** (Platform Center Offset, phases de puissance, efficacité du couple, fluidité), recalé dans le temps sur les vidéos.
- Attention : un capteur Bluetooth n'accepte souvent qu'un nombre limité de connexions ; si l'Edge 1050 est connecté en ANT+ et l'app en Bluetooth, ça doit fonctionner, à vérifier.

**Calcul local sur RTX 4090**
- La 4090 permet d'utiliser en local les modèles les plus précis (RTMPose‑x / RTMW, ViTPose‑H, voire Sapiens, avec suivi temporel), en analyse après capture plutôt qu'en direct. Le cloud n'est pas nécessaire.

**Stack recommandée (réponse à « Rust ? »)**
- **Analyse : Python** (FastAPI). Tout l'écosystème utile y est (MMPose/RTMPose, Pose2Sim, OpenCV, PyTorch/CUDA, NumPy/SciPy, `fitdecode`, OpenSim). Le réécrire en Rust coûterait des mois sans gain de précision.
- **Interface : TypeScript** (application web, par ex. React ou Svelte + Vite), car Web Bluetooth, caméra et MediaPipe en direct sont natifs du navigateur.
- Rust seulement plus tard et si besoin, pour un module précis où la vitesse compte (ce qui n'est pas le cas a priori : la 4090 fait le travail lourd).
- Stockage local SQLite + dossier de vidéos ; rapport HTML exportable en PDF.

**Petits achats à envisager (à confirmer en phase 1)**
- 2 à 3 trépieds + supports de téléphone ; mire **ChArUco** imprimée et collée sur un support rigide (carton plume/dibond) pour l'échelle et la calibration 3D.
- Pastilles adhésives de couleur (ou ArUco imprimés) ; 1 à 2 lampes LED à lumière continue (pas de scintillement à 60+ fps).
- Goniomètre (~10–15 €) et niveau / laser croix pour vérifier les mesures et le niveau du vélo ; mètre ruban ; éventuellement un fil à plomb.
- Optionnel : un câble USB‑C ou un hub pour rapatrier vite les vidéos des téléphones.

### Compléments (13/11/2026)

- **Douleurs :**
  - **arrière du genou, sur les tendons** (ischio‑jambiers : biceps fémoral à l'extérieur, semi‑tendineux/membraneux à l'intérieur), **lors des grosses sorties** ;
  - **depuis peu, devant le genou gauche** (côté unique, apparition récente).
- **Vélo :** Specialized « Sport » 2020, taille **61** (modèle exact à préciser : Allez Sport, Tarmac SL6 Sport, Roubaix Sport… la géométrie stack/reach en dépend).
- **Manivelles :** 175 mm.

**Pistes à vérifier en priorité (hypothèses de fitter, pas un diagnostic) :**
- Douleur **arrière** en fin de longue sortie → signe classique d'une **selle trop haute et/ou trop reculée** (genou en sur‑extension en bas du coup de pédale, pied qui « pointe » pour aller chercher la pédale), parfois de cales trop avancées. À mesurer : extension max du genou, plage de cheville, bascule du bassin, recul de selle — et leur évolution avec la fatigue (capture en début et en fin d'effort).
- Douleur **avant, d'un seul côté (gauche), récente** → plutôt selle trop basse/avancée ou flexion importante en haut du coup de pédale **pour cette jambe-là** ; l'asymétrie fait penser à un bassin qui bascule d'un côté (une jambe trop tendue, l'autre trop pliée), une **différence de longueur de jambes**, un réglage de cale gauche différent, ou un changement récent (matériel, chaussures, volume).
- Les deux ensemble → priorité à la **mesure gauche/droite** : angles des deux genoux, bascule du bassin vue de dos, trajectoire des genoux vue de face, équilibre de puissance G/D des Assioma et position du pied sur chaque pédale (.FIT).
- 175 mm sur un 61 est la monte d'origine habituelle ; à réévaluer selon la flexion du genou et de la hanche en haut du coup de pédale (la douleur avant peut aussi venir de là).

**Questions restantes à poser au démarrage :**
- Modèle exact du vélo, taille du cycliste, hauteur d'entrejambe, poids.
- Cotes actuelles : hauteur de selle, recul, drop selle‑cintre (ou photo de profil avec mètre).
- Type de pédales/cales (Look Kéo ? couleur de la cale = degré de liberté), chaussures, semelles.
- Changement récent (matériel, position, volume d'entraînement) avant l'apparition de la douleur avant gauche ? Durée typique d'une « grosse sortie » avant que l'arrière du genou fasse mal ?

### Compléments (14/11/2026)

- **Profil, vélo, cotes, cales** : à saisir et modifier **dans l'application** (écrans « Mon profil » et « Mon vélo », historique des configurations).
- **Douleur avant du genou gauche** : apparue après une sortie de **90 km, une première** (.FIT du 18/10/2026) → pic de volume à prendre en compte en priorité, capture en fin d'effort.
- **Webcam Logitech** : 30 fps → pas de mesure dynamique ; guidage, vue de dos en complément, auto‑tests.
- **Phase 1 livrée** : [docs/03_specification.md](docs/03_specification.md), [config/metrics.yaml](config/metrics.yaml), [docs/04_benchmark_pose.md](docs/04_benchmark_pose.md) + `tools/benchmark_pose.py`.
