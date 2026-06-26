# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.mesh_io import to_trimesh, from_trimesh


def test_to_trimesh_merges_triangle_soup():
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    # Explode into triangle soup: every face gets its own 3 unique vertices.
    soup_verts = box.vertices[box.faces].reshape(-1, 3)
    soup_faces = numpy.arange(len(soup_verts)).reshape(-1, 3)
    mesh = to_trimesh(soup_verts, soup_faces)
    assert len(mesh.faces) == 12
    assert len(mesh.vertices) == 8  # merge_vertices collapsed the soup


def test_from_trimesh_returns_typed_arrays():
    box = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts, faces, normals = from_trimesh(box)
    assert verts.dtype == numpy.float32 and verts.shape[1] == 3
    assert faces.dtype == numpy.int32 and faces.shape[1] == 3
    assert normals.shape == verts.shape
