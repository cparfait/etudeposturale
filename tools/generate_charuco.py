"""Génère les mires ChArUco imprimables (PNG 300 dpi + PDF à l'échelle exacte).

Usage : python tools/generate_charuco.py [dossier_sortie]
Les paramètres de chaque mire sont aussi écrits en JSON pour l'étape de calibration.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

DPI = 300
MM_PER_INCH = 25.4
DICTIONARY = "DICT_5X5_100"

# Formats paysage (largeur x hauteur en mm)
BOARDS = {
    "A3": dict(paper=(420, 297), cols=7, rows=5, square_mm=50.0, marker_mm=37.5),
    "A2": dict(paper=(594, 420), cols=9, rows=6, square_mm=60.0, marker_mm=45.0),
}


def mm2px(mm: float) -> int:
    return round(mm / MM_PER_INCH * DPI)


def font(size_px: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def build(name: str, cfg: dict, out: Path) -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, DICTIONARY))
    board = cv2.aruco.CharucoBoard(
        (cfg["cols"], cfg["rows"]), cfg["square_mm"] / 1000, cfg["marker_mm"] / 1000, dictionary
    )
    bw, bh = mm2px(cfg["cols"] * cfg["square_mm"]), mm2px(cfg["rows"] * cfg["square_mm"])
    board_img = board.generateImage((bw, bh), marginSize=0, borderBits=1)

    pw, ph = mm2px(cfg["paper"][0]), mm2px(cfg["paper"][1])
    page = Image.new("L", (pw, ph), 255)
    x0, y0 = (pw - bw) // 2, mm2px(12)
    page.paste(Image.fromarray(board_img), (x0, y0))

    draw = ImageDraw.Draw(page)
    f = font(mm2px(4))
    y_text = y0 + bh + mm2px(6)
    # Règle de contrôle de 100 mm
    rx = x0
    draw.line([(rx, y_text), (rx + mm2px(100), y_text)], fill=0, width=mm2px(0.5))
    for i in range(11):
        tick = mm2px(3 if i % 5 else 5)
        xi = rx + mm2px(10 * i)
        draw.line([(xi, y_text - tick), (xi, y_text)], fill=0, width=mm2px(0.3))
    draw.text((rx + mm2px(105), y_text - mm2px(4)), "100 mm", fill=0, font=f)
    draw.text(
        (rx, y_text + mm2px(3)),
        f"Mire ChArUco {name} — {cfg['cols']}x{cfg['rows']} cases de {cfg['square_mm']:g} mm, "
        f"marqueurs {cfg['marker_mm']:g} mm, {DICTIONARY}. IMPRIMER À 100 % (sans ajustement), "
        "vérifier la règle, coller sur support rigide parfaitement plan.",
        fill=0,
        font=f,
    )

    out.mkdir(parents=True, exist_ok=True)
    stem = out / f"charuco_{name}"
    page.save(f"{stem}.png", dpi=(DPI, DPI))
    page.convert("RGB").save(f"{stem}.pdf", resolution=DPI)
    params = dict(name=name, dictionary=DICTIONARY, dpi=DPI, **cfg)
    Path(f"{stem}.json").write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"{stem}.pdf / .png / .json")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("calibration")
    for n, c in BOARDS.items():
        build(n, c, target)
