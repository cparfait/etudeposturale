import numpy as np
import pytest

from posturale.analysis.pipeline import analyze_profile_video
from posturale.capture.video import probe
from posturale.pose.markers import GREEN, ORANGE, detect_blobs, locate_bb

from synthetic import true_knee_extremes
from synthetic_video import FakeEngine, render


@pytest.fixture(scope="module")
def video_right(tmp_path_factory):
    path = tmp_path_factory.mktemp("v") / "profil_D.mp4"
    px = render(path, saddle_mm=720.0, forward="right")
    return path, px


def test_probe(video_right):
    meta = probe(video_right[0])
    assert meta.fps == pytest.approx(60, abs=0.5)
    assert meta.width == 1280 and meta.n_frames == 840


def test_blob_detection(video_right):
    import cv2

    cap = cv2.VideoCapture(str(video_right[0]))
    frames = [cap.read()[1] for _ in range(30)]
    cap.release()
    assert len(detect_blobs(frames[0], GREEN)) >= 7  # deux pastilles proches peuvent se toucher sur une image
    assert len(detect_blobs(frames[0], ORANGE)) == 2
    # le pédalier est la pastille orange immobile, la pédale tourne
    assert locate_bb([detect_blobs(f, ORANGE) for f in frames]) == pytest.approx([560, 560], abs=1.5)


def test_end_to_end_profile(video_right):
    """Vidéo → pastilles nommées par un modèle imprécis → angles : on retrouve la vérité à ~1°."""
    path, px = video_right
    res = analyze_profile_video(str(path), FakeEngine(px), crank_mm=175.0, seat_tube_deg=73.5, start_s=0.0, duration_s=None)
    true_min, true_max = true_knee_extremes(saddle_mm=720.0)
    assert res["cote"] == "D"
    assert res["echelle"]["pedalier"] == "pastilles"
    assert res["echelle"]["mm_par_px"] == pytest.approx(1 / 0.55, rel=0.02)
    assert res["metriques"]["P1"]["moyenne"] == pytest.approx(true_min, abs=1.2)
    assert res["metriques"]["P2"]["moyenne"] == pytest.approx(true_max, abs=1.2)
    assert res["qualite"]["Q4_cycles"] >= 15
    assert res["fusion"]["epicondyle_femoral"]["pastille_pct"] > 95
    assert res["verdict_selle"]["statut"] == "dans_la_plage"
    assert len(res["courbes"]["genou_flexion"]["moyenne"]) == 90


def test_left_side_and_high_saddle(tmp_path):
    path = tmp_path / "profil_G.mp4"
    px = render(path, saddle_mm=750.0, forward="left", seconds=10)
    res = analyze_profile_video(str(path), FakeEngine(px, seed=3), start_s=0.0, duration_s=None)
    assert res["cote"] == "G"
    v = res["verdict_selle"]
    assert v["statut"] == "trop_tendu" and v["correction_mm"] == -5.0
    true_min, _ = true_knee_extremes(saddle_mm=750.0)
    assert res["metriques"]["P1"]["moyenne"] == pytest.approx(true_min, abs=1.2)
