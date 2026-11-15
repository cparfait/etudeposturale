"""Prépare les plans LTX pour le montage : 1920x1080, 30 i/s (images intermédiaires calculées), ralentis pour couvrir
la durée du plan dans le film, sans son. assets/ltx/<nom>.mp4 -> assets/ltx_s/<nom>.mp4"""
import subprocess
import sys
from pathlib import Path

TUTO = Path(__file__).resolve().parent.parent
SRC, DST = TUTO / "assets" / "ltx", TUTO / "assets" / "ltx_s"
NEED = {"intro": 6.0, "materiel": 3.0, "pastille": 5.0, "telephone": 2.6, "profil": 5.2, "selle": 5.0}  # secondes à couvrir
TRIM = {"pastille": (0.0, 2.6), "selle": (0.0, 2.4), "telephone": (0.0, 1.6)}  # (début, durée) gardés : la suite du plan dérive


def dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout)


DST.mkdir(parents=True, exist_ok=True)
for name, need in NEED.items():
    if sys.argv[1:] and name not in sys.argv[1:]:
        continue
    src = SRC / f"{name}.mp4"
    if not src.exists():
        print("manque", name)
        continue
    t0, tl = TRIM.get(name, (0.0, dur(src)))
    k = max(1.0, (need + 0.15) / tl)
    vf = (f"setpts={k:.4f}*PTS,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1,"
          "scale=-2:1080:flags=lanczos,crop=1920:1080,format=yuv420p")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(tl), "-i", str(src), "-an", "-vf", vf, "-c:v", "libx264", "-crf", "16",
                    "-preset", "slow", "-movflags", "+faststart", str(DST / f"{name}.mp4")], check=True)
    print(f"{name}: x{k:.2f} -> {dur(DST / f'{name}.mp4'):.2f} s")
