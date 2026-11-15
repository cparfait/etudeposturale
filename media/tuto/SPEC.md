# Tutoriel « Une séance d'étude posturale » — spec

GOAL:    à la fin, la personne sait faire une séance seule : matériel, pastilles, téléphones, cadrage, prise, résultat.
OUTPUT:  HyperFrames, 1920 x 1080, 30 i/s ; 7 sous-compositions (c0 à c6), chacune réutilisable seule.
TIME:    ≈ 101 s x 30 = 3030 images. Pas de musique (aucune source disponible) : la voix est l'horloge.
LOOK:    médium = l'interface réelle de l'app + plans filmés (LTX).
         sol #f3f5f2 (celui de l'app), encre #121a12, accent unique #b8f34a (citron vert de l'app) : la barre de chapitre,
         l'anneau qui désigne un élément, le chiffre clé. Bleu #5f87e6 et rose #e65fc2 seulement pour les pastilles.
         Titres : Space Grotesk 650, 96 px (titre de chapitre), -2 % d'approche ; étiquettes Inter 600, 34 px.
         Panneaux : blanc #ffffff, rayon 28 px, ombre 0 18px 50px rgba(18,26,18,.18). Pas de grain, pas de vignette.
OBJECTS: le vélo sur home trainer, le téléphone sur trépied, les carrés de bande de kiné (2 cm), l'écran de l'app.
MOTION:  entrée power3.out 0,5 s ; déplacement caméra (zoom sur capture) power2.inOut 1,2–1,6 s ; sortie power2.in 0,35 s.
         Une action principale par plan ; les secondaires 120–200 ms après, 50–70 % de l'amplitude.
SHOTS:
  c0 0–7 s      plan LTX salon (ralenti x1,5) ; titre « Régler son vélo chez soi » en bas à gauche à 0,8 s ; voix c0.
  c1 7–24 s     LTX matériel + carte « 1 · Le matériel » (voix c1a) ; capture Mon équipement, anneau sur l'éclairage
                quand la conséquence s'affiche (voix c1b).
  c2 24–44 s    LTX pastille + carte « 2 · Les pastilles » (c2a) ; schéma corps/vélo, points bleus puis roses (c2b) ;
                capture Étalonnage, pipette sur une pastille (c2c).
  c3 44–59 s    LTX téléphone + carte « 3 · Les téléphones » (c3a) ; capture QR, les deux vignettes arrivent (c3b).
  c4 59–70 s    capture Cadrage : squelette, contrôles au vert, carte « 4 · Le cadrage » (c4a, c4b).
  c5 70–82 s    capture séance guidée « C'est parti », minuteur (c5a) ; LTX profil qui pédale (c5b).
  c6 82–101 s   capture Analyse, zoom sur « −5 mm » (c6a, c6b) ; LTX clé Allen + phrase finale (c6c).
BANNED:  fond noir vide ; lueurs, néons, particules ; dégradés violets/bleus ; tout centré ; tout qui monte en fondu ;
         titre sur capture assombrie ; trois cartes en ligne ; logo dans un coin ; texte qui bouge pendant la lecture.
QA:      3.0 (titre lisible sur le salon), 12 (carte 1), 19 (anneau éclairage), 36 (schéma pastilles), 54 (2 vignettes),
         66 (feu vert), 74 (minuteur), 90 (−5 mm agrandi), 99 (phrase finale).
