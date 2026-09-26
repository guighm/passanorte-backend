"""T032 [US3] Testes unitários do Haversine (RF32, RNF14).

Borda exata no raio, dentro, fora, anti-podal e mesmo ponto = 0.
Deve falhar antes de T035 (módulo inexistente).
"""

import pytest

from services.validation.app.core.haversine import haversine_m


def test_same_point_is_zero():
    assert haversine_m(-3.4704, -60.0238, -3.4704, -60.0238) == 0.0


def test_short_distance_same_neighborhood():
    # deslocamento de ~200 m na malha de Manaus
    d = haversine_m(-3.4704, -60.0238, -3.4722, -60.0247)
    assert 200 < d < 260


def test_within_tolerance_radius():
    # ~30 m de deslocamento no equador-ish de Manaus (1 grau ≈ 111 km; 0.0003° ≈ 33 m)
    d = haversine_m(-3.4704, -60.0238, -3.4704, -60.0235)
    assert 0 < d < 100


def test_exact_radius_boundary():
    # 1 segundo de latitude ≈ 30,9 m: ponto a ~100 m ao norte
    spot = (-3.4704, -60.0238)
    user = (-3.4704 + 100.0 / 111_320.0, -60.0238)
    d = haversine_m(*spot, *user)
    assert d == pytest.approx(100.0, abs=1.0)


def test_outside_radius():
    d = haversine_m(-3.4704, -60.0238, -3.4704, -60.0100)
    assert d > 1000


def test_antipodal_points():
    d = haversine_m(0.0, 0.0, 0.0, 180.0)
    assert d == pytest.approx(20_015_086, abs=10_000)  # meio círculo máx ≈ 20015 km
