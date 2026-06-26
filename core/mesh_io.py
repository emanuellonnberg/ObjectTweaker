# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Convert between raw vertex/face arrays and trimesh objects.

This is the only boundary that touches mesh array layout. It never imports
Cura; ``ObjectTweaker.py`` is responsible for ``MeshData`` <-> ndarray.
"""
from typing import Tuple

import numpy
import trimesh


def to_trimesh(vertices: numpy.ndarray, faces: numpy.ndarray) -> trimesh.Trimesh:
    """Build a trimesh from vertex/face arrays, deduplicating shared vertices.

    Cura frequently stores meshes as "triangle soup" with no shared vertices;
    ``merge_vertices`` rebuilds adjacency so ``split`` and decimation work.
    """
    verts = numpy.asarray(vertices, dtype=numpy.float64)
    if verts.ndim == 1:
        verts = verts.reshape(-1, 3)
    faces_arr = numpy.asarray(faces, dtype=numpy.int64)
    if faces_arr.ndim == 1:
        faces_arr = faces_arr.reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces_arr, process=False)
    mesh.merge_vertices()
    return mesh


def from_trimesh(
    mesh: trimesh.Trimesh,
) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    """Return ``(vertices f32, faces i32, vertex_normals f32)`` for Cura.

    Vertex normals are returned so the adapter can skip Cura's slow pure-Python
    normal recomputation.
    """
    verts = numpy.asarray(mesh.vertices, dtype=numpy.float32)
    faces = numpy.asarray(mesh.faces, dtype=numpy.int32)
    normals = numpy.asarray(mesh.vertex_normals, dtype=numpy.float32)
    return verts, faces, normals
