import numpy as np
import pytest

from posturale.kinematics.cycles import detect_cycles, normalize_cycle, value_at_crank
from posturale.kinematics.geometry import crank_angle, flexion, image_to_bike
from posturale.kinematics.signal import fill_gaps, lowpass
from posturale.kinematics.stats import summarize
from posturale.metrics.profile_view import analyze_profile

from synthetic import rider, true_knee_extremes


def test_flexion_convention():
    hip, knee = np.array([0.0, 0.0]), np.array([0.0, -1.0])
    assert flexion(hip, knee, np.array([0.0, -2.0])) == pytest.approx(0.0)
    assert flexion(hip, knee, np.array([1.0, -1.0])) == pytest.approx(90.0)


def test_crank_angle_convention():
    bb = np.zeros(2)
    assert crank_angle(bb, np.array([0.0, 175.0])) == pytest.approx(0.0)    # haut
    assert crank_angle(bb, np.array([175.0, 0.0])) == pytest.approx(90.0)   # avant
    assert crank_angle(bb, np.array([0.0, -175.0])) == pytest.approx(180.0)  # bas


def test_image_to_bike_flips_axes():
    pts = np.array([[10.0, 20.0]])
    assert image_to_bike(pts, 2.0, "right").tolist() == [[20.0, -40.0]]
    assert image_to_bike(pts, 2.0, "left").tolist() == [[-20.0, -40.0]]


def test_fill_gaps_only_short():
    x = np.array([0, 1, np.nan, 3, np.nan, np.nan, np.nan, np.nan, 8], float)
    out = fill_gaps(x, fps=100, max_gap_ms=20)  # 2 images max
    assert out[2] == pytest.approx(2.0)
    assert np.isnan(out[4:8]).all()


def test_lowpass_keeps_slow_signal():
    fps = 120
    t = np.arange(0, 5, 1 / fps)
    slow = np.sin(2 * np.pi * 1.5 * t)
    noisy = slow + 0.2 * np.sin(2 * np.pi * 30 * t)
    out = lowpass(noisy, fps, 6)
    assert np.max(np.abs(out[50:-50] - slow[50:-50])) < 0.02


def test_cycles_count_and_value_at_crank():
    tracks, fps = rider(seconds=20, cadence_rpm=90)
    theta = crank_angle(tracks["axe_pedalier"], tracks["axe_pedale"])
    cycles = detect_cycles(theta)
    assert len(cycles) in (28, 29)  # 30 tours, bords exclus
    assert all(abs(c.length - fps * 60 / 90) <= 1 for c in cycles)
    x = tracks["axe_pedale"][:, 0]
    assert value_at_crank(x, theta, cycles[3], 90.0) == pytest.approx(175.0, abs=0.5)
    assert normalize_cycle(x, theta, cycles[3]).shape == (360,)


def test_summarize_rejects_outlier():
    s = summarize([35.0, 35.5, 34.8, 35.2, 60.0])
    assert s.n == 4 and s.n_rejected == 1
    assert s.mean == pytest.approx(35.125)


@pytest.mark.parametrize("saddle", [700.0, 720.0, 740.0])
def test_profile_metrics_match_truth(saddle):
    true_min, true_max = true_knee_extremes(saddle_mm=saddle)
    tracks, fps = rider(saddle_mm=saddle, noise_mm=1.0, seconds=30)
    res = analyze_profile(tracks, fps)
    assert res.quality["Q4_ok"]
    assert res.summary["P1"].mean == pytest.approx(true_min, abs=0.7)
    assert res.summary["P2"].mean == pytest.approx(true_max, abs=0.7)
    assert res.summary["P1"].sd < 1.0
    assert res.segments_mm["cuisse_mm"] == pytest.approx(460, abs=2)
    assert {"P4", "P5", "P6", "P7", "P8", "P9", "P10"} <= set(res.summary)


def test_missing_landmarks_reject_cycles():
    tracks, fps = rider(seconds=20)
    tracks["epicondyle_femoral"][300:420] = np.nan  # 1 s masquée : trop long pour être comblé
    res = analyze_profile(tracks, fps)
    assert res.quality["cycles_rejetes"] >= 1
    assert not np.isnan(res.summary["P1"].mean)
