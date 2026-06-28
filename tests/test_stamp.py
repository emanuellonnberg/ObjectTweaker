# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy

from core.stamp import shape_outline, make_prism


def test_circle_outline_has_48_points_on_radius():
    out = shape_outline("circle", {"diameter": 4.0})
    assert out.shape == (48, 2)
    radii = numpy.linalg.norm(out, axis=1)
    assert numpy.allclose(radii, 2.0, atol=1e-6)


def test_star_outline_has_two_points_per_tip():
    out = shape_outline("star", {"diameter": 4.0, "points": 5})
    assert out.shape == (10, 2)


def test_rectangle_outline_has_four_corners():
    out = shape_outline("rectangle", {"width": 6.0, "height": 2.0})
    assert out.shape == (4, 2)
    assert abs(out[:, 0].max() - 3.0) < 1e-6
    assert abs(out[:, 1].max() - 1.0) < 1e-6


def test_make_prism_is_watertight_with_expected_height():
    square = numpy.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], dtype=float)
    prism = make_prism(square, height=3.0)
    assert prism.is_watertight
    assert abs(prism.bounds[1][2] - prism.bounds[0][2] - 3.0) < 1e-6
