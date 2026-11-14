import cv2
import numpy as np
import pytest

from posturale.calibration.charuco import apply_h, detect, load_board, plane_from_frames
from posturale.config import repo_root
from posturale.metrics.frontal import front_metrics, rear_metrics


def _board_view(scale: float, skew: float = 0.0):
    """Mire A3 réelle (PNG 300 dpi) réduite et légèrement mise en perspective."""
    img = cv2.imread(str(repo_root() / "calibration" / "charuco_A3.png"))
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[0, 0], [w, skew * h], [w, h - skew * h], [0, h]]) * scale + 100
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (int(w * scale) + 200, int(h * scale) + 200), borderValue=(90, 90, 90)), scale


def test_charuco_plane_scale():
    board = load_board("A3")
    frame, scale = _board_view(0.25)
    c, ids = detect(frame, board)
    assert ids is not None and len(ids) >= 20
    plane = plane_from_frames([frame], board)
    px_per_mm_true = scale * 300 / 25.4
    assert plane.mm_per_px == pytest.approx(1 / px_per_mm_true, rel=0.02)


def test_charuco_homography_corrects_perspective():
    board = load_board("A3")
    frame, _ = _board_view(0.25, skew=0.06)
    plane = plane_from_frames([frame], board)
    c, ids = detect(frame, board)
    mm = apply_h(plane.H, c)
    # deux coins voisins sur une même ligne sont à une case (50 mm) l'un de l'autre, même en perspective
    d = np.linalg.norm(mm[1] - mm[0])
    assert d == pytest.approx(50.0, abs=1.0)


def _cyclic(fps=60, seconds=12, rpm=90):
    t = np.arange(0, seconds, 1 / fps)
    w = 2 * np.pi * rpm / 60 * t
    return t, w


def test_front_knee_excursion():
    t, w = _cyclic()
    tr = {
        "hanche_G": np.c_[np.full_like(t, -100), np.full_like(t, 0)],
        "hanche_D": np.c_[np.full_like(t, 100), np.full_like(t, 0)],
        "cheville_G": np.c_[np.full_like(t, -110), 400 + 40 * np.cos(w)],
        "cheville_D": np.c_[np.full_like(t, 110), 400 + 40 * np.cos(w + np.pi)],
        # genou droit : 20 px de va-et-vient latéral ; gauche : 8 px
        "genou_G": np.c_[-105 + 4 * np.sin(w), 200 + 60 * np.cos(w)],
        "genou_D": np.c_[105 + 10 * np.sin(w + np.pi), 200 + 60 * np.cos(w + np.pi)],
    }
    m = front_metrics(tr, 60)
    assert m["unite"] == "% bassin"
    assert m["cotes"]["D"]["F1"]["moyenne"] == pytest.approx(10.0, abs=1.0)  # 20 px / 200 px
    assert m["cotes"]["G"]["F1"]["moyenne"] == pytest.approx(4.0, abs=1.0)
    assert m["F3"] == pytest.approx(6.0, abs=1.5)
    assert m["cotes"]["D"]["n_cycles"] >= 15


def test_rear_pelvic_roll():
    t, w = _cyclic()
    roll = np.radians(3) * np.sin(w)  # ± 3° de roulis
    tr = {
        "hanche_G": np.c_[-100 * np.cos(roll), -100 * np.sin(roll)],
        "hanche_D": np.c_[100 * np.cos(roll), 100 * np.sin(roll)],
        "genou_G": np.c_[np.full_like(t, -100), 200 + 60 * np.cos(w)],
        "genou_D": np.c_[np.full_like(t, 100), 200 + 60 * np.cos(w + np.pi)],
    }
    m = rear_metrics(tr, 60)
    assert m["D1"]["moyenne"] == pytest.approx(6.0, abs=0.5)
    assert abs(m["D3"]) < 0.5
