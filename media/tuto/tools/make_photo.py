"""Photo d'étalonnage pour la capture : une image du plan LTX « profil » avec des carrés bleus sur les articulations
(repérées par MediaPipe) et des carrés roses sur le pédalier et l'axe de pédale. Écrit work/etalonnage.jpg et
work/etalonnage.json (positions, pour cliquer à la pipette)."""
import json
from pathlib import Path

import cv2
import mediapipe as mp

TUTO = Path(__file__).resolve().parent.parent
SRC = TUTO / "assets" / "ltx" / "profil.mp4"
BLUE = (230, 135, 95)    # BGR de #5f87e6
PINK = (194, 95, 230)    # BGR de #e65fc2

cap = cv2.VideoCapture(str(SRC))
best = None
with mp.solutions.pose.Pose(static_image_mode=True, model_complexity=2) as pose:
    for idx in range(0, 120, 6):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, img = cap.read()
        if not ok:
            break
        res = pose.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        if not res.pose_landmarks:
            continue
        lm = res.pose_landmarks.landmark
        # côté tourné vers la caméra : le plus visible
        side = "R" if sum(lm[i].visibility for i in (12, 24, 26, 28)) >= sum(lm[i].visibility for i in (11, 23, 25, 27)) else "L"
        ids = dict(epaule=12, coude=14, poignet=16, hanche=24, genou=26, cheville=28, talon=30, pied=32) if side == "R" else \
            dict(epaule=11, coude=13, poignet=15, hanche=23, genou=25, cheville=27, talon=29, pied=31)
        vis = sum(lm[i].visibility for i in ids.values())
        if best is None or vis > best[0]:
            best = (vis, idx, img.copy(), {k: (lm[i].x, lm[i].y) for k, i in ids.items()})
assert best, "aucun cycliste détecté"
_, idx, img, pts = best
h, w = img.shape[:2]
px = {k: (int(x * w), int(y * h)) for k, (x, y) in pts.items()}
# Repères du vélo : MediaPipe ne les voit pas ; placés à la main pour l'image retenue (axe du pédalier, axe de pédale)
pedalier = (int(0.5 * w), int(0.8395 * h))     # centre du plateau
pedale = (int(0.522 * w), int(0.771 * h))      # axe de la pédale côté caméra, sous la chaussure
side = max(12, int(w * 0.012))


def square(c, color):
    x, y = c
    cv2.rectangle(img, (x - side // 2, y - side // 2), (x + side // 2, y + side // 2), color, -1, cv2.LINE_AA)


body = {k: px[k] for k in ("epaule", "coude", "poignet", "hanche", "genou", "cheville")}
body["cheville"] = (body["cheville"][0] + int(0.004 * w), body["cheville"][1] - int(0.04 * h))  # malléole, au-dessus de la chaussure
# Pied : placés à la main sur la chaussure de l'image retenue (MediaPipe vise le talon et les orteils, pas les repères)
body["talon"] = (int(0.4906 * w), int(0.7188 * h))       # arrière de la chaussure
body["metatarse"] = (int(0.5297 * w), int(0.7358 * h))   # 5e métatarse, bord extérieur de l'avant-pied
for c in body.values():
    square(c, BLUE)
for c in (pedale, pedalier):
    square(c, PINK)
out = TUTO / "work" / "etalonnage.jpg"
out.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
(TUTO / "work" / "etalonnage.json").write_text(json.dumps({"largeur": w, "hauteur": h, "image": idx, "corps": body,
                                                            "velo": {"pedale": pedale, "pedalier": pedalier}}, indent=1))
print("frame", idx, "points", body, "pedale", pedale, "pedalier", pedalier)
