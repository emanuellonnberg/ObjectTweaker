# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.fillholes import fill_holes


def _box_missing_top():
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    zc = box.triangles_center[:, 2]
    keep = zc < (zc.max() - 1e-6)        # drop the 2 top triangles
    box.update_faces(keep)
    box.remove_unreferenced_vertices()
    return box


def _open_tube():
    cyl = trimesh.creation.cylinder(radius=1.0, height=3.0, sections=24)
    nz = numpy.abs(cyl.face_normals[:, 2])
    keep = nz < 0.5                       # drop both end caps, keep side wall
    cyl.update_faces(keep)
    cyl.remove_unreferenced_vertices()
    return cyl


def test_fills_single_hole_and_is_watertight():
    mesh, filled = fill_holes(_box_missing_top())
    assert filled == 1
    assert mesh.is_watertight


def test_fills_both_ends_of_open_tube():
    mesh, filled = fill_holes(_open_tube())
    assert filled == 2


def test_closed_mesh_unchanged():
    sphere = trimesh.creation.icosphere(subdivisions=3)
    mesh, filled = fill_holes(sphere)
    assert filled == 0
    assert len(mesh.faces) == len(sphere.faces)
