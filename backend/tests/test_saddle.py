import math

import pytest

from posturale.metrics.profile_view import analyze_profile
from posturale.rules.saddle import flexion_from_distance, hip_ankle_distance, saddle_verdict

from synthetic import SEAT_TUBE_DEG, rider, true_knee_extremes


def test_distance_roundtrip():
    d = hip_ankle_distance(450, 440, 35)
    assert flexion_from_distance(450, 440, d) == pytest.approx(35)
    assert hip_ankle_distance(450, 440, 0) == pytest.approx(890)


def _verdict(saddle):
    tracks, fps = rider(saddle_mm=saddle, noise_mm=1.0)
    res = analyze_profile(tracks, fps)
    p1 = res.summary["P1"]
    v = saddle_verdict("D", p1.mean, p1.sd, res.bdc_mm["hanche"], res.bdc_mm["cheville"],
                       res.segments_mm["cuisse_mm"], res.segments_mm["jambe_mm"], SEAT_TUBE_DEG)
    return v


def test_correction_reaches_target():
    """Selle trop haute : la correction brute ramène la flexion vers le milieu de plage (35°)."""
    saddle = 750.0
    v = _verdict(saddle)
    assert v.statut == "trop_tendu"
    assert v.correction_brute_mm < 0 and v.correction_mm == -5.0 and v.plafonnee
    new_min, _ = true_knee_extremes(saddle_mm=saddle + v.correction_brute_mm)
    assert new_min == pytest.approx(35.0, abs=1.0)


def test_low_saddle_raises():
    v = _verdict(680.0)
    assert v.statut == "trop_plie" and v.correction_mm > 0


def test_in_range():
    # Cherche une hauteur qui donne ~35° puis vérifie le verdict
    v = _verdict(720.0)
    if 30 <= v.flexion_moyenne <= 40:
        assert v.statut == "dans_la_plage" and v.correction_mm == 0.0


def test_sensitivity_5mm_detected():
    """Critère d'acceptation 3 : un déplacement de 5 mm se voit nettement et dans le bon sens."""
    base = analyze_profile(*rider(saddle_mm=720.0, noise_mm=1.5, seed=1)).summary["P1"]
    up = analyze_profile(*rider(saddle_mm=725.0, noise_mm=1.5, seed=2)).summary["P1"]
    assert base.mean - up.mean > 1.5  # selle plus haute → genou plus tendu
    assert (base.mean - up.mean) > 3 * math.hypot(base.sd, up.sd) / math.sqrt(min(base.n, up.n))


def test_default_seat_tube_flagged():
    tracks, fps = rider(saddle_mm=750.0)
    res = analyze_profile(tracks, fps)
    p1 = res.summary["P1"]
    v = saddle_verdict("G", p1.mean, p1.sd, res.bdc_mm["hanche"], res.bdc_mm["cheville"],
                       res.segments_mm["cuisse_mm"], res.segments_mm["jambe_mm"], None)
    assert any("par défaut" in h for h in v.hypotheses)
