"""Captures fixes de pages de la démo (repérage) : python explore.py /equipement /seance/1 ..."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://localhost:5181"
OUT = Path(__file__).resolve().parent.parent / "work" / "repérage"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--ignore-certificate-errors"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, ignore_https_errors=True, device_scale_factor=1)
    for path in sys.argv[1:]:
        pg.goto(BASE + path, wait_until="networkidle")
        pg.wait_for_timeout(1500)
        name = path.strip("/").replace("/", "_") or "accueil"
        pg.screenshot(path=str(OUT / f"{name}.png"))
        print(name, pg.evaluate("document.documentElement.scrollHeight"))
    b.close()
