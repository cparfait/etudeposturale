"""Écrit les chapitres du tutoriel (compositions/c0..c6.html) et index.html à partir d'une seule description.

Les fichiers produits restent du HTML HyperFrames ordinaire, modifiables dans le studio ; relancer ce script les réécrit.
Durées : voix (assets/voix/durees.json) et vidéos (ffprobe).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

TUTO = Path(__file__).resolve().parent.parent
DUR = json.loads((TUTO / "assets" / "voix" / "durees.json").read_text(encoding="utf-8"))["durees"]


def vlen(rel: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(TUTO / rel)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


CSS = """
    @font-face { font-family: "Space Grotesk"; src: url("assets/fonts/SpaceGrotesk.woff2") format("woff2"); font-weight: 300 700; }
    #root { position: absolute; inset: 0; overflow: hidden; background: #f3f5f2; font-family: "Inter", sans-serif; color: #121a12; }
    #root .media { position: absolute; inset: 0; width: 1920px; height: 1080px; object-fit: cover; }
    #root .card { position: absolute; left: 120px; bottom: 110px; padding: 34px 48px 38px 44px; border-radius: 28px; background: #ffffff;
      box-shadow: 0 18px 50px rgba(18, 26, 18, 0.18); display: flex; gap: 30px; align-items: stretch; }
    #root .card .bar { width: 12px; border-radius: 6px; background: #b8f34a; }
    #root .card .k { font-size: 32px; font-weight: 600; color: #4c5a48; letter-spacing: 0.01em; }
    #root .card .t { font-family: "Space Grotesk", sans-serif; font-size: 96px; font-weight: 650; letter-spacing: -0.02em; line-height: 1.02; margin-top: 6px; }
    #root .card .s { font-size: 36px; font-weight: 500; color: #3a4637; margin-top: 12px; }
    #root .ring { position: absolute; border: 7px solid #b8f34a; border-radius: 22px; box-shadow: 0 0 0 4px rgba(18, 26, 18, 0.85); }
    #root .pr { position: absolute; width: 52px; height: 52px; border-radius: 50%; border: 6px solid; box-shadow: 0 0 0 3px #ffffff; }
    #root .tag { position: absolute; padding: 14px 24px; border-radius: 16px; background: #121a12; color: #f3f5f2; font-size: 34px; font-weight: 600; }
"""


def card(cid: str, k: str, t: str, s: str, start: float, dur: float, exit: bool = True) -> tuple[str, str]:
    i = f"{cid}-card"
    html = (f'<div id="{i}" class="clip card-host" data-start="{start}" data-duration="{dur}">'
            f'<div class="card" id="{i}-in"><div class="bar" id="{i}-bar"></div><div><div class="k">{k}</div><div class="t">{t}</div>'
            + (f'<div class="s">{s}</div>' if s else "") + "</div></div></div>")
    js = (f'tl.fromTo("#{i}-in", {{x: -70, opacity: 0}}, {{x: 0, opacity: 1, duration: 0.3, ease: "power3.out"}}, {start});\n'
          f'tl.fromTo("#{i}-bar", {{scaleY: 0, transformOrigin: "50% 100%"}}, {{scaleY: 1, duration: 0.3, ease: "power3.out"}}, {start + 0.1});\n'
          + (f'tl.to("#{i}-in", {{x: -40, opacity: 0, duration: 0.2, ease: "power2.in"}}, {start + dur - 0.22});\n' if exit else ""))
    return html, js


def video(cid: str, n: int, src: str, start: float, dur: float, media_start: float = 0.0) -> str:
    return (f'<video id="{cid}-v{n}" class="clip media" src="{src}" data-start="{start}" data-duration="{dur:.2f}"'
            + (f' data-media-start="{media_start}"' if media_start else "") + ' muted playsinline></video>')


def voice(cid: str, lid: str, start: float) -> str:
    return (f'<audio id="{cid}-vo-{lid}" class="clip" src="assets/voix/{lid}.wav" data-start="{start}" '
            f'data-duration="{DUR[lid]:.2f}" data-volume="1"></audio>')


def ring(cid: str, n: int, x, y, w, h, start, dur, tag: str = "", tag_pos=None) -> tuple[str, str]:
    i = f"{cid}-ring{n}"
    html = (f'<div id="{i}" class="clip" data-start="{start}" data-duration="{dur}" data-layout-allow-overlap>'
            f'<div class="ring" id="{i}-r" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"></div>'
            + (f'<div class="tag" id="{i}-t" style="left:{tag_pos[0]}px;top:{tag_pos[1]}px">{tag}</div>' if tag else "") + "</div>")
    js = (f'tl.fromTo("#{i}-r", {{scale: 1.18, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.6)"}}, {start});\n'
          + (f'tl.fromTo("#{i}-t", {{y: 16, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.4, ease: "power3.out"}}, {start + 0.15});\n' if tag else "")
          + f'tl.to("#{i}-r, #{i}-t", {{opacity: 0, duration: 0.3, ease: "power2.in"}}, {start + dur - 0.35});\n')
    return html, js


def zoom(cid: str, n: int, start: float, scale: float, ox: float, oy: float, dur: float = 1.4) -> str:
    return (f'tl.fromTo("#{cid}-v{n}", {{scale: 1, transformOrigin: "{ox}px {oy}px"}}, '
            f'{{scale: {scale}, duration: {dur}, ease: "power2.inOut"}}, {start});\n')


SCHEMA = """
<div id="c2-schema" class="clip" data-start="{s}" data-duration="{d}">
  <svg id="c2-svg" viewBox="0 0 900 700" style="position:absolute;left:110px;top:150px;width:1000px;height:778px">
    <g fill="none" stroke="#9aa597" stroke-width="10" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="230" cy="520" r="150"/><circle cx="690" cy="520" r="150"/>
      <path d="M230 520 L430 540 L370 260 Z M370 260 L620 285 L430 540 M620 285 L690 520 M620 285 L640 240 L690 240"/>
      <path d="M335 255 L405 255"/>
    </g>
    <g fill="none" stroke="#121a12" stroke-width="16" stroke-linecap="round" stroke-linejoin="round">
      <path d="M375 238 L560 140 L612 200 L655 243"/><path d="M375 238 L500 390 L465 560 L505 590"/>
      <path d="M430 540 L480 596" stroke="#5e6a5b" stroke-width="12"/>
    </g>
    <circle cx="600" cy="88" r="38" fill="#121a12"/>
    <g id="c2-dots-b" fill="#5f87e6" stroke="#ffffff" stroke-width="6">
      <circle class="db" cx="560" cy="140" r="20"/><circle class="db" cx="375" cy="238" r="20"/>
      <circle class="db" cx="500" cy="390" r="20"/><circle class="db" cx="465" cy="560" r="20"/>
    </g>
    <g fill="#e65fc2" stroke="#ffffff" stroke-width="6">
      <rect class="dp" x="414" y="524" width="32" height="32" rx="6"/><rect class="dp" x="464" y="580" width="32" height="32" rx="6"/>
    </g>
  </svg>
  <div id="c2-legend" style="position:absolute;left:1180px;top:300px;width:620px;display:flex;flex-direction:column;gap:46px">
    <div id="c2-lb" style="display:flex;gap:26px;align-items:flex-start">
      <span style="flex:none;width:58px;height:58px;border-radius:12px;background:#5f87e6;margin-top:6px"></span>
      <div><div style="font-family:'Space Grotesk',sans-serif;font-size:64px;font-weight:650;letter-spacing:-0.02em">Le corps</div>
      <div style="font-size:38px;font-weight:500;color:#3a4637;margin-top:8px">épaule, hanche, genou, cheville</div></div>
    </div>
    <div id="c2-lp" style="display:flex;gap:26px;align-items:flex-start">
      <span style="flex:none;width:58px;height:58px;border-radius:12px;background:#e65fc2;margin-top:6px"></span>
      <div><div style="font-family:'Space Grotesk',sans-serif;font-size:64px;font-weight:650;letter-spacing:-0.02em">Le vélo</div>
      <div style="font-size:38px;font-weight:500;color:#3a4637;margin-top:8px">une autre couleur, bien différente</div></div>
    </div>
    <div style="font-size:34px;font-weight:600;color:#121a12">Carrés de bande de kiné de 2 cm</div>
  </div>
</div>"""


TOPVIEW = """
<div id="c3-top" class="clip" data-start="4.9" data-duration="3.1" style="background:#f3f5f2">
  <svg viewBox="0 0 1920 1080" style="position:absolute;inset:0;width:1920px;height:1080px">
    <g stroke-linecap="round" stroke-linejoin="round">
      <rect x="610" y="518" width="300" height="44" rx="22" fill="#e3e8e0" stroke="#121a12" stroke-width="6"/>
      <rect x="1010" y="518" width="300" height="44" rx="22" fill="#e3e8e0" stroke="#121a12" stroke-width="6"/>
      <path d="M760 540 H1160" stroke="#121a12" stroke-width="14" fill="none"/>
      <path d="M1175 455 V625" stroke="#121a12" stroke-width="16" fill="none"/>
      <path d="M1175 455 h26 M1175 625 h26" stroke="#121a12" stroke-width="12" fill="none"/>
      <path d="M800 510 h80 l20 30 l-20 30 h-80 z" fill="#121a12"/>
      <ellipse cx="930" cy="540" rx="86" ry="104" fill="#ffffff" stroke="#121a12" stroke-width="6"/>
      <path d="M965 470 L1150 470 M965 610 L1150 610" stroke="#121a12" stroke-width="12" fill="none"/>
      <circle cx="1000" cy="540" r="40" fill="#ffffff" stroke="#121a12" stroke-width="6"/>
    </g>
    <text x="1350" y="552" font-family="Inter, sans-serif" font-size="34" font-weight="600" fill="#3a4637">le vélo, vu de dessus</text>
    <g class="ph-g">
      <path class="dist" d="M960 252 V470" stroke="#5e6a5b" stroke-width="5" stroke-dasharray="14 12" fill="none"/>
      <circle cx="960" cy="190" r="56" fill="#ffffff" stroke="#121a12" stroke-width="6"/>
      <rect x="920" y="168" width="80" height="44" rx="10" fill="#121a12"/>
      <text x="1050" y="205" font-family="Space Grotesk, sans-serif" font-size="56" font-weight="650" fill="#121a12">Profil gauche</text>
    </g>
    <g class="ph-d">
      <path class="dist" d="M960 610 V828" stroke="#5e6a5b" stroke-width="5" stroke-dasharray="14 12" fill="none"/>
      <circle cx="960" cy="890" r="56" fill="#b8f34a" stroke="#121a12" stroke-width="6"/>
      <rect x="920" y="868" width="80" height="44" rx="10" fill="#121a12"/>
      <text x="1050" y="905" font-family="Space Grotesk, sans-serif" font-size="56" font-weight="650" fill="#121a12">Profil droit</text>
    </g>
    <text class="dist" x="600" y="410" font-family="Inter, sans-serif" font-size="38" font-weight="600" fill="#3a4637" text-anchor="end">2,5 à 3 m de chaque côté</text>
  </svg>
</div>"""


def scene(cid: str, total: float, body: list[str], js: list[str]) -> None:
    html = f"""<template>
  <style>{CSS}  </style>
  <div id="root" data-composition-id="{cid}" data-width="1920" data-height="1080">
    {chr(10).join("    " + b for b in body).strip()}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
{"".join("    " + l + chr(10) for l in "".join(js).splitlines())}    window.__timelines["{cid}"] = tl;
  </script>
</template>
"""
    (TUTO / "compositions" / f"{cid}.html").write_text(html, encoding="utf-8")
    SCENES.append((cid, total))


SCENES: list[tuple[str, float]] = []


def photo_block(start: float, dur: float) -> tuple[str, str]:
    """Photo d'étalonnage (cycliste réel + carrés) : chaque pastille est cerclée quand la voix la nomme."""
    info = json.loads((TUTO / "assets" / "etalonnage.json").read_text())
    k = 1080 / info["hauteur"]
    ox = (info["largeur"] * k - 1920) / 2

    def pos(pt):
        return pt[0] * k - ox, pt[1] * k

    rings, js = [], []
    order = [("epaule", "b"), ("hanche", "b"), ("genou", "b"), ("cheville", "b"), ("coude", "b"), ("poignet", "b"),
             ("talon", "b"), ("metatarse", "b"), ("pedale", "p"), ("pedalier", "p")]
    for n, (name, kind) in enumerate(order):
        x, y = pos(info["corps"][name] if kind == "b" else info["velo"][name])
        color = "#5f87e6" if kind == "b" else "#e65fc2"
        rings.append(f'<div class="pr" id="c2-pr{n}" style="left:{x - 26:.0f}px;top:{y - 26:.0f}px;border-color:{color}"></div>')
        t = start + (0.5 + n * 0.32 if kind == "b" else 3.9 + (n - 8) * 0.35)
        js.append(f'tl.fromTo("#c2-pr{n}", {{scale: 2.2, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.35, ease: "power3.out"}}, {t:.2f});\n')
    legend = ('<div id="c2-legend" style="position:absolute;left:96px;top:96px;padding:30px 40px;border-radius:28px;background:#fff;'
              'box-shadow:0 18px 50px rgba(18,26,18,.18);display:flex;flex-direction:column;gap:22px">'
              '<div id="c2-lb" style="display:flex;gap:20px;align-items:center"><span style="width:44px;height:44px;border-radius:10px;background:#5f87e6"></span>'
              '<div><div style="font-family:Space Grotesk,sans-serif;font-size:52px;font-weight:650;letter-spacing:-.02em">Le corps</div>'
              '<div style="font-size:30px;font-weight:500;color:#3a4637">épaule, hanche, genou, cheville…</div></div></div>'
              '<div id="c2-lp" style="display:flex;gap:20px;align-items:center"><span style="width:44px;height:44px;border-radius:10px;background:#e65fc2"></span>'
              '<div><div style="font-family:Space Grotesk,sans-serif;font-size:52px;font-weight:650;letter-spacing:-.02em">Le vélo</div>'
              '<div style="font-size:30px;font-weight:500;color:#3a4637">une autre couleur, bien différente</div></div></div></div>')
    js.append(f'tl.fromTo("#c2-legend", {{opacity: 0, x: -40}}, {{opacity: 1, x: 0, duration: 0.3, ease: "power3.out"}}, {start + 0.1});\n')
    js.append(f'tl.fromTo("#c2-lp", {{opacity: 0.3}}, {{opacity: 0.3, duration: 0.01}}, {start});\n')
    js.append(f'tl.to("#c2-lp", {{opacity: 1, duration: 0.3, ease: "power2.out"}}, {start + 3.7});\n')
    html = (f'<div id="c2-photo" class="clip" data-start="{start}" data-duration="{dur}" data-layout-allow-overflow data-layout-allow-overlap>'
            f'<img id="c2-photo-img" src="assets/etalonnage.jpg" alt="" style="position:absolute;left:{-ox:.0f}px;top:0;height:1080px;transform-origin:50% 45%">'
            + "".join(rings) + legend + "</div>")
    return html, "".join(js)


def build() -> None:
    # c0 — ouverture
    d0 = 6.0
    c, j = card("c0", "Étude posturale vélo", "Régler son vélo<br>chez soi", "Une séance complète, en six étapes", 0.4, d0 - 0.4, exit=False)
    scene("c0", d0, [video("c0", 1, "assets/ltx_s/intro.mp4", 0, d0), c, voice("c0", "c0", 0.4)], [j])

    # c1 — matériel : plan LTX puis la page Mon équipement (début du clic sur l'éclairage)
    d1 = 10.6
    c, j = card("c1", "Étape 1 sur 6", "Le matériel", "", 0.2, 2.8)
    r, rj = ring("c1", 1, 396, 728, 1104, 92, 4.5, 2.8, "Pas d'éclairage ? L'outil s'adapte.", (900, 840))
    scene("c1", d1, [video("c1", 1, "assets/ltx_s/materiel.mp4", 0, 3.0), video("c1", 2, "assets/ecran/equipement.mp4", 3.0, d1 - 3.0, 0.9),
                     c, r, voice("c1", "c1a", 0.2), voice("c1", "c1b", 3.3)], [j, rj])

    # c2 — pastilles : plan LTX, photo annotée, étalonnage dans l'app
    d2 = 18.4
    c, j = card("c2", "Étape 2 sur 6", "Les pastilles", "", 0.2, 4.6)
    ph, pj = photo_block(5.0, 7.0)
    scene("c2", d2, [video("c2", 1, "assets/ltx_s/pastille.mp4", 0, 5.0), ph,
                     video("c2", 2, "assets/ecran/pastilles.mp4", 12.0, d2 - 12.0, 0.6), c,
                     voice("c2", "c2a", 0.2), voice("c2", "c2b", 5.1), voice("c2", "c2c", 12.4)], [j, pj])

    # c3 — téléphones : QR agrandi, schéma vu de dessus (un téléphone de chaque côté), vignettes en direct agrandies
    d3 = 11.4
    c, j = card("c3", "Étape 3 sur 6", "Les téléphones", "", 0.2, 2.3)
    r1, r1j = ring("c3", 1, 1300, 176, 506, 294, 2.9, 1.95, "Scanne-le avec chaque téléphone", (760, 500))
    r2, r2j = ring("c3", 2, 1290, 688, 590, 180, 8.4, 2.9, "Leur image, en direct sur le PC", (700, 905))
    zj = zoom("c3", 2, 2.6, 1.8, 1553, 323, 0.6) + zoom("c3", 3, 8.0, 1.7, 1585, 640, 0.6)
    tj = ('tl.fromTo("#c3-top", {opacity: 0}, {opacity: 1, duration: 0.25, ease: "power2.out"}, 4.9);\n'
          'tl.fromTo("#c3-top .ph-g", {y: -60, opacity: 0}, {y: 0, opacity: 1, duration: 0.35, ease: "power3.out"}, 5.5);\n'
          'tl.fromTo("#c3-top .ph-d", {y: 60, opacity: 0}, {y: 0, opacity: 1, duration: 0.35, ease: "power3.out"}, 6.2);\n'
          'tl.fromTo("#c3-top .dist", {opacity: 0}, {opacity: 1, duration: 0.3, ease: "power2.out"}, 6.8);\n')
    scene("c3", d3, [video("c3", 1, "assets/ltx_s/telephone.mp4", 0, 2.6),
                     video("c3", 2, "assets/ecran/qr.mp4", 2.6, 2.3, 0.4), TOPVIEW,
                     video("c3", 3, "assets/ecran/qr.mp4", 8.0, 3.4, 8.0), c, r1, r2,
                     voice("c3", "c3a", 0.2), voice("c3", "c3b", 4.9)], [j, zj, r1j, r2j, tj])

    # c4 — cadrage
    d4 = 8.9
    c, j = card("c4", "Étape 4 sur 6", "Le cadrage", "", 0.2, 3.6)
    scene("c4", d4, [video("c4", 1, "assets/ecran/cadrage.mp4", 0, d4, 1.0), c, voice("c4", "c4a", 0.2), voice("c4", "c4b", 4.1)], [j])

    # c5 — enregistrement
    d5 = 10.6
    c, j = card("c5", "Étape 5 sur 6", "L'enregistrement", "", 0.2, 4.6)
    scene("c5", d5, [video("c5", 1, "assets/ecran/guidee_prise.mp4", 0, 5.4, 0.9), video("c5", 2, "assets/ltx_s/profil.mp4", 5.4, d5 - 5.4), c,
                     voice("c5", "c5a", 0.2), voice("c5", "c5b", 5.6)], [j])

    # c6 — résultats
    d6 = 15.4
    c, j = card("c6", "Étape 6 sur 6", "Les résultats", "", 0.2, 4.0)
    fin, fj = card("c6f", "À retenir", "Un réglage à la fois,<br>puis on vérifie.", "", 10.7, round(d6 - 10.7, 2), exit=False)
    zj = zoom("c6", 1, 4.6, 1.7, 735, 395)
    scene("c6", d6, [video("c6", 1, "assets/ecran/resultats.mp4", 0, 10.4), video("c6", 2, "assets/ltx_s/selle.mp4", 10.4, d6 - 10.4), c, fin,
                     voice("c6", "c6a", 0.2), voice("c6", "c6b", 5.5), voice("c6", "c6c", 10.9)], [j, zj, fj])

    # racine
    t, hosts = 0.0, []
    for i, (cid, d) in enumerate(SCENES):
        hosts.append(f'      <div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
                     f'data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="1" data-track-kind="graphics" '
                     f'data-width="1920" data-height="1080"></div>')
        t += d
    index = f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #f3f5f2; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{t:.2f}" data-width="1920" data-height="1080">
{chr(10).join(hosts)}
      <audio id="musique" class="clip" src="assets/musique.m4a" data-start="0" data-duration="{t:.2f}" data-volume="0.28"
        data-fade-in="1" data-fade-out="2.5" data-track-index="5"></audio>
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
    (TUTO / "index.html").write_text(index, encoding="utf-8")
    print("durée totale", round(t, 2), "s :", ", ".join(f"{c} {d}" for c, d in SCENES))


if __name__ == "__main__":
    build()
