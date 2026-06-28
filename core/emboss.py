# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Emboss/engrave a shape onto a mesh by booleaning an extruded prism."""
import json
import logging
import os
from typing import List, Optional, Tuple

import numpy
import trimesh

from .stamp import make_prism

logger = logging.getLogger("ObjectTweaker.emboss")

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


def _prepare_for_boolean(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Return a cleaned copy: merge verts, drop dup/degenerate faces, fix normals."""
    m = mesh.copy()
    try:
        m.merge_vertices()
        m.update_faces(m.unique_faces())
        m.update_faces(m.nondegenerate_faces())
        m.remove_unreferenced_vertices()
        m.fix_normals()
    except Exception as exc:
        logger.debug("prepare_for_boolean partial failure: %s", exc)
    return m


def _try_boolean(op, a: trimesh.Trimesh, b: trimesh.Trimesh) -> Tuple[Optional[trimesh.Trimesh], List[str]]:
    """Try each engine in order; return (result_or_None, per-engine error strings)."""
    errors: List[str] = []
    for engine in _ENGINES:
        try:
            res = op([a, b], engine=engine) if engine else op([a, b])
            if res is not None and len(res.faces) > 0:
                return res, errors
            errors.append(f"{engine or 'default'}: empty result")
        except Exception as exc:
            errors.append(f"{engine or 'default'}: {type(exc).__name__}: {exc}")
    return None, errors


def _capture(capture_dir: str, model: trimesh.Trimesh, prism: trimesh.Trimesh, info: dict) -> None:
    """Dump the boolean inputs + diagnostics for offline replay."""
    try:
        os.makedirs(capture_dir, exist_ok=True)
        base = os.path.join(capture_dir, "emboss_fail")
        model.export(base + "_model.stl")
        prism.export(base + "_prism.stl")
        with open(base + "_info.json", "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=2)
        logger.warning("emboss: wrote failure capture to %s", capture_dir)
    except Exception as exc:
        logger.warning("emboss: capture failed: %s", exc)


def emboss(mesh, point, normal, outline_2d, depth, mode,
           capture_dir: Optional[str] = None) -> Tuple[trimesh.Trimesh, bool, str]:
    """Raise (emboss) or cut (engrave) the outline at ``point``.

    Returns ``(result_mesh, ok, reason)``. On failure returns ``(mesh, False,
    reason)`` with ``mesh`` unchanged and a human-readable reason; when
    ``capture_dir`` is set, the model + prism + diagnostics are written there.
    """
    normal = numpy.asarray(normal, dtype=float)
    nn = float(numpy.linalg.norm(normal))
    depth = float(depth)
    if nn < 1e-9:
        return mesh, False, "degenerate surface normal (zero length)"
    if depth <= 0.0:
        return mesh, False, "depth must be > 0"
    normal = normal / nn
    point = numpy.asarray(point, dtype=float)

    try:
        prism = make_prism(outline_2d, depth + 2.0 * _EMBED)
    except Exception as exc:
        return mesh, False, f"could not build stamp prism: {exc}"

    prism.apply_transform(trimesh.geometry.align_vectors([0.0, 0.0, 1.0], normal))

    prepared = _prepare_for_boolean(mesh)

    if mode == "engrave":
        prism.apply_translation(point - normal * (depth + _EMBED))
        op = trimesh.boolean.difference
    else:
        prism.apply_translation(point - normal * _EMBED)
        op = trimesh.boolean.union

    # Diagnostics computed up front so they are captured even on a throw.
    info = {
        "mode": mode,
        "depth": depth,
        "point": point.tolist(),
        "normal": normal.tolist(),
        "n_outline": int(len(numpy.asarray(outline_2d))),
        "model_faces": int(len(prepared.faces)),
        "model_watertight": bool(prepared.is_watertight),
        "model_winding_consistent": bool(prepared.is_winding_consistent),
        "model_volume": float(prepared.volume) if prepared.is_watertight else None,
        "model_bounds": prepared.bounds.tolist(),
        "prism_watertight": bool(prism.is_watertight),
        "prism_bounds": prism.bounds.tolist(),
        "engine_errors": [],
    }

    result, errors = _try_boolean(op, prepared, prism)
    info["engine_errors"] = errors

    if result is None or len(result.faces) == 0:
        reason = (f"boolean {('difference' if mode == 'engrave' else 'union')} failed "
                  f"(model watertight={info['model_watertight']}); {'; '.join(errors) or 'no engine'}")
        logger.warning("emboss failed: %s | info=%s", reason, info)
        if capture_dir:
            _capture(capture_dir, prepared, prism, info)
        return mesh, False, reason

    logger.info("emboss ok: mode=%s faces %d -> %d", mode, len(prepared.faces), len(result.faces))
    return result, True, ""
