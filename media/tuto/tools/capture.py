"""Filme l'app de démo (https://localhost:5181) pour le tutoriel : une vidéo par scène dans assets/ecran/.

- enregistrement par le protocole Chrome (screencast JPEG) puis assemblage ffmpeg à 30 i/s ;
- curseur visible et onde au clic, ajoutés dans la page (le screencast ne montre pas le vrai curseur) ;
- caméra simulée : le plan LTX « profil » sert de webcam (Cadrage) ;
- téléphones simulés : rejoignent la séance par l'API, envoient l'aperçu (images du plan « profil ») et
  réagissent aux commandes d'enregistrement.

Usage : python capture.py [scene ...]   scènes : equipement pastilles qr cadrage guidee resultats
"""
from __future__ import annotations

import asyncio
import base64
import json
import ssl
import subprocess
import sys
import time
from pathlib import Path

import cv2
import httpx
import websockets
from playwright.async_api import async_playwright

BASE = "https://localhost:5181"
TUTO = Path(__file__).resolve().parent.parent
LTX = TUTO / "assets" / "ltx"
OUT = TUTO / "assets" / "ecran"
WORK = TUTO / "work" / "frames"
Y4M = TUTO / "work" / "camera_profil.y4m"

CURSOR_JS = r"""
(() => {
  const add = () => {
    if (document.getElementById('tuto-cursor')) return;
    const st = document.createElement('style');
    st.textContent = `#tuto-cursor{position:fixed;z-index:2147483647;left:0;top:0;width:22px;height:22px;margin:-3px 0 0 -3px;pointer-events:none;transition:transform .06s linear}
      #tuto-cursor svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
      .tuto-ripple{position:fixed;z-index:2147483646;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;border:3px solid #9ad83a;pointer-events:none;animation:tutorip .6s ease-out forwards}
      @keyframes tutorip{to{transform:scale(4.2);opacity:0}}`;
    document.head.appendChild(st);
    const c = document.createElement('div');
    c.id = 'tuto-cursor';
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2l15 9-6.5 1.5L8 19z" fill="#0f150e" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    addEventListener('mousemove', e => { c.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`; }, true);
    addEventListener('mousedown', e => {
      const r = document.createElement('div'); r.className = 'tuto-ripple';
      r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
      document.body.appendChild(r); setTimeout(() => r.remove(), 700);
    }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', add); else add();
})();
"""

ctx_ssl = ssl.create_default_context()
ctx_ssl.check_hostname = False
ctx_ssl.verify_mode = ssl.CERT_NONE


# ---------- enregistrement ----------
class Rec:
    def __init__(self, page, name: str):
        self.page, self.name = page, name
        self.dir = WORK / name
        self.frames: list[tuple[float, Path]] = []

    async def start(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        for f in self.dir.glob("*.jpg"):
            f.unlink()
        self.cdp = await self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(self._frame(ev)))
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1})
        self.t0 = time.time()

    async def _frame(self, ev):
        p = self.dir / f"{len(self.frames):05d}.jpg"
        p.write_bytes(base64.b64decode(ev["data"]))
        self.frames.append((ev["metadata"]["timestamp"], p))
        try:
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        except Exception:
            pass

    async def stop(self):
        await self.cdp.send("Page.stopScreencast")
        end = time.time()
        await asyncio.sleep(0.3)
        lines = []
        fr = sorted(self.frames)
        for i, (ts, p) in enumerate(fr):
            nxt = fr[i + 1][0] if i + 1 < len(fr) else end
            lines.append(f"file '{p.as_posix()}'\nduration {max(0.001, nxt - ts):.4f}")
        lines.append(f"file '{fr[-1][1].as_posix()}'")
        lst = self.dir / "list.txt"
        lst.write_text("\n".join(lines), encoding="utf-8")
        OUT.mkdir(parents=True, exist_ok=True)
        dst = OUT / f"{self.name}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-crf", "15",
                        "-preset", "slow", "-movflags", "+faststart", str(dst)], check=True)
        print(f"{self.name}: {len(fr)} images, {end - self.t0:.1f} s -> {dst}", flush=True)


async def glide(page, x, y, steps=28):
    await page.mouse.move(x, y, steps=steps)


async def click(page, locator, pause=0.35):
    box = await locator.bounding_box()
    await glide(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    await asyncio.sleep(pause)
    await locator.click()


async def smooth_scroll(page, dy, ms=900):
    await page.evaluate("""([dy, ms]) => new Promise(r => {
      const el = document.scrollingElement, y0 = el.scrollTop, t0 = performance.now();
      const f = t => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2*k*k : 1 - Math.pow(-2*k + 2, 2) / 2;
        el.scrollTop = y0 + dy * e; k < 1 ? requestAnimationFrame(f) : r(); };
      requestAnimationFrame(f); })""", [dy, ms])


# ---------- téléphone simulé ----------
def phone_frames(src: Path, flip=False, step=2) -> list[bytes]:
    cap = cv2.VideoCapture(str(src))
    out, i = [], 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if i % step == 0:
            img = cv2.resize(img, (960, int(img.shape[0] * 960 / img.shape[1])))
            if flip:
                img = cv2.flip(img, 1)
            out.append(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes())
        i += 1
    return out


async def fake_phone(code: str, name: str, frames: list[bytes], stop: asyncio.Event, role: str | None = None):
    async with httpx.AsyncClient(base_url=BASE + "/api", verify=False) as h:
        j = (await h.post(f"/remote/{code}/join", json={"nom": name, "secure": True})).json()
        did = j["appareil"]
        if role:
            await h.put(f"/remote/{code}/appareils/{did}", json={"role": role})
        state, rec_end, ws, k, last_cmd = "pret", 0.0, None, 0, None
        while not stop.is_set():
            if state == "enregistre" and time.time() > rec_end:
                state = "envoye"
            r = (await h.post(f"/remote/{code}/poll", json={"appareil": did, "etat": state, "fps": 60, "largeur": 1920, "hauteur": 1080})).json()
            cmd = r.get("commande")
            if cmd and cmd["id"] != last_cmd:
                last_cmd = cmd["id"]
                if cmd["action"] == "start":
                    state, rec_end = "enregistre", time.time() + cmd["duree_s"]
                elif cmd["action"] == "stop":
                    state = "envoye"
            if r.get("apercu") and ws is None:
                ws = await websockets.connect(f"wss://localhost:5181/api/remote/{code}/flux/{did}", ssl=ctx_ssl)
            for _ in range(10):
                if ws is not None:
                    await ws.send(frames[k % len(frames)])
                    k += 1
                await asyncio.sleep(0.1)
        if ws is not None:
            await ws.close()


# ---------- scènes ----------
async def sc_equipement(page):
    async with httpx.AsyncClient(base_url=BASE + "/api", verify=False) as h:
        eq = (await h.get("/equipment")).json()
        items = eq["items"] | {"eclairage": None}
        await h.put("/equipment", json={"items": items, "onboarding_fait": True})
    await page.goto(BASE + "/equipement", wait_until="networkidle")
    await page.wait_for_timeout(800)
    await page.mouse.move(1500, 300)
    rec = Rec(page, "equipement")
    await rec.start()
    await page.wait_for_timeout(1200)
    groups = page.locator("[role=radiogroup]")
    n = await groups.count()
    target = None
    for i in range(n):
        if "clairage" in (await groups.nth(i).get_attribute("aria-label") or ""):
            target = groups.nth(i)
    await target.scroll_into_view_if_needed()
    await page.wait_for_timeout(400)
    await click(page, target.locator("button.no"))
    await page.wait_for_timeout(2600)
    await click(page, target.locator("button.yes"))
    await page.wait_for_timeout(1500)
    await smooth_scroll(page, 520, 1400)
    await page.wait_for_timeout(2200)
    await rec.stop()


async def sc_pastilles(page):
    info = json.loads((TUTO / "work" / "etalonnage.json").read_text())
    await page.goto(BASE + "/pastilles", wait_until="networkidle")
    await page.wait_for_timeout(1500)
    await page.mouse.move(1400, 700)
    rec = Rec(page, "pastilles")
    await rec.start()
    await page.wait_for_timeout(600)
    drop = page.get_by_text("Déposer une photo")
    await glide(page, *(lambda b: (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2))(await drop.bounding_box()))
    await page.wait_for_timeout(300)
    await page.locator('input[type=file]').first.set_input_files(str(TUTO / "work" / "etalonnage.jpg"))
    await page.wait_for_selector(".mk-stage img", timeout=20000)
    await page.wait_for_timeout(1600)
    stage = await page.locator(".mk-stage").bounding_box()

    def at(pt):
        return stage["x"] + pt[0] / info["largeur"] * stage["width"], stage["y"] + pt[1] / info["hauteur"] * stage["height"]
    await click(page, page.get_by_role("button", name="Pipette").first)
    await page.wait_for_timeout(500)
    x, y = at(info["corps"]["genou"])
    await glide(page, x, y, 30)
    await page.wait_for_timeout(350)
    await page.mouse.click(x, y)
    await page.wait_for_timeout(1300)
    await click(page, page.get_by_role("button", name="Pipette").nth(1))
    await page.wait_for_timeout(500)
    x, y = at(info["velo"]["pedale"])
    await glide(page, x, y, 30)
    await page.wait_for_timeout(350)
    await page.mouse.click(x, y)
    await page.wait_for_timeout(2600)
    await rec.stop()


async def sc_qr(page, frames_d, frames_g):
    await page.goto(BASE + "/seance/1", wait_until="networkidle")
    await page.wait_for_selector(".pp-code b", timeout=15000)
    await page.wait_for_function("document.querySelector('.pp-qr img') !== null", timeout=15000)
    code = (await page.locator(".pp-code b").inner_text()).strip()
    pp = page.locator(".pp").first
    await pp.scroll_into_view_if_needed()
    await page.mouse.move(1500, 500)
    rec = Rec(page, "qr")
    await rec.start()
    await page.wait_for_timeout(1800)
    box = await page.locator(".pp-qr img").bounding_box()
    await glide(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, 30)
    stop = asyncio.Event()
    t1 = asyncio.ensure_future(fake_phone(code, "Pixel 10 Pro", frames_d, stop))
    await page.wait_for_timeout(3500)
    t2 = asyncio.ensure_future(fake_phone(code, "Galaxy S25", frames_g, stop))
    await page.wait_for_timeout(6500)
    await rec.stop()
    stop.set()
    await asyncio.gather(t1, t2)


async def sc_cadrage(page):
    await page.goto(BASE + "/cadrage", wait_until="networkidle")
    await page.wait_for_function("document.querySelector('.live video')?.readyState >= 2", timeout=60000)
    await page.wait_for_timeout(1500)
    rec = Rec(page, "cadrage")
    await rec.start()
    await page.mouse.move(1500, 600)
    await page.wait_for_timeout(12000)
    await rec.stop()


async def sc_guidee(page, frames_d, frames_g):
    await page.evaluate("localStorage.removeItem('posturale.guide.v1')")
    await page.goto(BASE + "/seance-guidee", wait_until="networkidle")
    await page.wait_for_timeout(1500)
    rec = Rec(page, "guidee_debut")
    await rec.start()
    await page.wait_for_timeout(800)
    await click(page, page.get_by_role("button", name="Commencer la séance"))
    await page.wait_for_timeout(2500)
    await rec.stop()
    # jusqu'à l'étape des téléphones, puis à la prise (hors caméra)
    stop = asyncio.Event()
    tasks = []
    for _ in range(14):
        title = await page.locator("main h2, .gd-step h2, h2").first.inner_text()
        if await page.locator(".pp-code b").count() and not tasks:
            code = (await page.locator(".pp-code b").inner_text()).strip()
            tasks = [asyncio.ensure_future(fake_phone(code, "Pixel 10 Pro", frames_d, stop, "profil_D")),
                     asyncio.ensure_future(fake_phone(code, "Galaxy S25", frames_g, stop, "profil_G"))]
            await page.wait_for_timeout(4000)
        if await page.get_by_role("button", name="C'est parti").count():
            break
        await page.get_by_role("button", name="Suivant").click()
        await page.wait_for_timeout(700)
    await page.wait_for_timeout(1500)
    await page.mouse.move(1500, 400)
    rec = Rec(page, "guidee_prise")
    await rec.start()
    await page.wait_for_timeout(1500)
    await click(page, page.get_by_role("button", name="C'est parti"))
    await page.wait_for_timeout(8000)
    await rec.stop()
    stop.set()
    if tasks:
        await asyncio.gather(*tasks)


async def sc_resultats(page):
    await page.goto(BASE + "/analyse/1", wait_until="networkidle")
    await page.wait_for_timeout(2500)
    await page.mouse.move(1500, 900)
    rec = Rec(page, "resultats")
    await rec.start()
    await page.wait_for_timeout(1000)
    await glide(page, 760, 300, 40)
    await page.wait_for_timeout(1800)
    await glide(page, 740, 395, 30)
    await page.wait_for_timeout(2000)
    await glide(page, 720, 720, 40)
    await page.wait_for_timeout(5500)
    await rec.stop()


def ensure_y4m():
    if not Y4M.exists():
        Y4M.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "3", "-i", str(LTX / "profil.mp4"),
                        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=60", "-pix_fmt", "yuv420p", str(Y4M)], check=True)


async def main(scenes: list[str]):
    frames_d = frames_g = []
    if (LTX / "profil.mp4").exists():   # plan LTX : webcam simulée et aperçu des téléphones
        ensure_y4m()
        frames_d = phone_frames(LTX / "profil.mp4")
        frames_g = phone_frames(LTX / "profil.mp4", flip=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=[
            "--ignore-certificate-errors", "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
            f"--use-file-for-fake-video-capture={Y4M}", "--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1, ignore_https_errors=True,
                                  permissions=["camera", "microphone"], locale="fr-FR")
        await ctx.add_init_script(CURSOR_JS)
        page = await ctx.new_page()
        await page.goto(BASE + "/", wait_until="networkidle")
        for s in scenes:
            if s == "equipement":
                await sc_equipement(page)
            elif s == "pastilles":
                await sc_pastilles(page)
            elif s == "qr":
                await sc_qr(page, frames_d, frames_g)
            elif s == "cadrage":
                await sc_cadrage(page)
            elif s == "guidee":
                await sc_guidee(page, frames_d, frames_g)
            elif s == "resultats":
                await sc_resultats(page)
        await b.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["equipement", "pastilles", "qr", "cadrage", "guidee", "resultats"]))
