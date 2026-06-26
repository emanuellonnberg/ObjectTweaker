# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import trimesh

from core.decimate import decimate


def test_decimate_to_target_count_reduces_faces():
    sphere = trimesh.creation.icosphere(subdivisions=4)  # 20480 faces
    out = decimate(sphere, target_count=500)
    assert 0 < len(out.faces) <= 600  # within ~20% of target
    assert len(out.faces) < len(sphere.faces)


def test_decimate_percent_keeps_roughly_that_fraction():
    sphere = trimesh.creation.icosphere(subdivisions=4)
    out = decimate(sphere, percent=0.1)
    assert len(out.faces) <= len(sphere.faces) * 0.15


def test_decimate_preserves_overall_shape():
    sphere = trimesh.creation.icosphere(subdivisions=4)
    out = decimate(sphere, target_count=800)
    # Bounding box stays close to the unit sphere's [-1, 1] extents.
    assert abs(out.bounds[1][0] - 1.0) < 0.1
    assert abs(out.bounds[0][0] + 1.0) < 0.1
