# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import trimesh

from core.cleanup import remove_small_parts


def _two_shell_mesh():
    big = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    small = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    small.apply_translation([50.0, 0.0, 0.0])  # far away, disjoint
    return trimesh.util.concatenate([big, small])


def test_removes_the_small_shell():
    mesh, removed = remove_small_parts(_two_shell_mesh(), min_pct=1.0)
    assert removed == 1
    # Big box has 12 faces; result should be just the big box.
    assert len(mesh.faces) == 12


def test_keep_largest_only_collapses_to_one_component():
    mesh, removed = remove_small_parts(_two_shell_mesh(), keep_largest_only=True)
    assert removed == 1
    assert len(mesh.split(only_watertight=False)) == 1


def test_single_shell_removes_nothing():
    box = trimesh.creation.box(extents=(3.0, 3.0, 3.0))
    mesh, removed = remove_small_parts(box, min_pct=1.0)
    assert removed == 0
    assert len(mesh.faces) == 12
