# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy

from core.cap import cap_loop


def test_square_loop_caps_with_two_triangles():
    loop = numpy.array([[0, 0, 5], [1, 0, 5], [1, 1, 5], [0, 1, 5]], dtype=float)
    cap = cap_loop(loop)
    assert cap is not None
    assert len(cap.faces) == 2          # n - 2 for n=4
    assert abs(cap.area - 1.0) < 1e-6   # covers exactly the unit square


def test_concave_L_loop_triangulates_to_n_minus_2_and_covers_area():
    loop = numpy.array([
        [0, 0, 5], [2, 0, 5], [2, 1, 5],
        [1, 1, 5], [1, 2, 5], [0, 2, 5],
    ], dtype=float)
    cap = cap_loop(loop)
    assert cap is not None
    assert len(cap.faces) == 4          # n - 2 for n=6
    assert abs(cap.area - 3.0) < 1e-6   # L area = 2*2 - 1*1


def test_degenerate_collinear_loop_returns_none():
    loop = numpy.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    assert cap_loop(loop) is None
