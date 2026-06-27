# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Emboss/engrave a shape onto a mesh by booleaning an extruded prism."""
from typing import Tuple

import numpy
import trimesh

from .stamp import make_prism

_EMBED = 0.5                       # mm the prism sinks past the surface
_ENGINES = ["manifold", "blender", None]


def nearest_face_normal(mesh: trimesh.Trimesh, point) -> numpy.ndarray:
    """Normal of the face whose centroid is nearest ``point``.

    Centroid-nearest (no rtree). The click point lies on the surface, so the
    nearest face's normal is the local surface orientation.
    """
    point = numpy.asarray(point, dtype=float)
    centroids = mesh.triangles_center
    idx = int(numpy.argmin(numpy.linalg.norm(centroids - point, axis=1)))
    return numpy.asarray(mesh.face_normals[idx], dtype=float)


def _try_boolean(op, a: trimesh.Trimesh, b: trimesh.Trimesh):
    for engine in _ENGINES:
        try:
            res = op([a, b], engine=engine) if engine else op([a, b])
            if res is not None and len(res.faces) > 0:
                return res
        except Exception:
            continue
    return None


def emboss(mesh, point, normal, outline_2d, depth, mode) -> Tuple[trimesh.Trimesh, bool]:
    """Raise (emboss) or cut (engrave) the outline at ``point``.

    Returns ``(result_mesh, ok)``; ``(mesh, False)`` unchanged on any failure.
    """
    normal = numpy.asarray(normal, dtype=float)
    nn = float(numpy.linalg.norm(normal))
    depth = float(depth)
    if nn < 1e-9 or depth <= 0.0:
        return mesh, False
    normal = normal / nn
    point = numpy.asarray(point, dtype=float)

    try:
        prism = make_prism(outline_2d, depth + 2.0 * _EMBED)
    except Exception:
        return mesh, False

    prism.apply_transform(trimesh.geometry.align_vectors([0.0, 0.0, 1.0], normal))

    prepared = mesh.copy()
    prepared.merge_vertices()

    if mode == "engrave":
        prism.apply_translation(point - normal * (depth + _EMBED))
        result = _try_boolean(trimesh.boolean.difference, prepared, prism)
    else:
        prism.apply_translation(point - normal * _EMBED)
        result = _try_boolean(trimesh.boolean.union, prepared, prism)

    if result is None or len(result.faces) == 0:
        return mesh, False
    return result, True
