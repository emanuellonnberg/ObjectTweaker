# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import trimesh


def test_trimesh_importable_and_builds_a_box():
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    assert len(mesh.faces) == 12
