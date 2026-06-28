# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.stamp import shape_outline
from core.emboss import emboss, nearest_face_normal


def test_nearest_face_normal_top_of_box():
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    n = nearest_face_normal(box, [0.0, 0.0, 5.0])
    assert numpy.allclose(numpy.abs(n), [0.0, 0.0, 1.0], atol=1e-6)


def test_emboss_circle_on_box_increases_volume():
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    out = shape_outline("circle", {"diameter": 3.0})
    res, ok, reason = emboss(box, [0.0, 0.0, 5.0], [0.0, 0.0, 1.0], out, depth=1.0, mode="emboss")
    assert ok is True, reason
    assert res.is_watertight
    assert res.volume > box.volume


def test_engrave_circle_on_box_decreases_volume():
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    out = shape_outline("circle", {"diameter": 3.0})
    res, ok, reason = emboss(box, [0.0, 0.0, 5.0], [0.0, 0.0, 1.0], out, depth=1.0, mode="engrave")
    assert ok is True, reason
    assert res.volume < box.volume


def test_degenerate_normal_returns_unchanged():
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    out = shape_outline("circle", {"diameter": 3.0})
    res, ok, reason = emboss(box, [0.0, 0.0, 5.0], [0.0, 0.0, 0.0], out, depth=1.0, mode="emboss")
    assert ok is False
    assert res is box
