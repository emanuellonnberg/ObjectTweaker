# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Cap a single open boundary loop with a planar triangulated patch.

Pure numpy + trimesh: ear-clipping (no triangulation engine, no scipy), with a
fan-from-centroid fallback. Ported from ObjectSplitter's mesh_splitter caps.
"""
from typing import Optional, Tuple

import numpy
import trimesh


def _signed_area_2d(poly: numpy.ndarray) -> float:
    """Signed area of a simple 2D polygon (shoelace)."""
    x = poly[:, 0]
    y = poly[:, 1]
    return 0.5 * float(numpy.sum(x * numpy.roll(y, -1) - numpy.roll(x, -1) * y))


def _point_in_triangle_2d(p, a, b, c, eps: float = 1e-12) -> bool:
    """Point-in-triangle test in 2D, inclusive of edges.

    Inclusive (``>= -eps``) so that a vertex lying exactly on a candidate ear's
    edge counts as "inside" and rejects that ear. A strict test would let an
    ear clip across a reflex vertex that is collinear with the ear tips,
    filling concave notches (area too large).
    """
    v0 = c - a
    v1 = b - a
    v2 = p - a
    den = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(den) <= eps:
        return False
    u = (v2[0] * v1[1] - v1[0] * v2[1]) / den
    v = (v0[0] * v2[1] - v2[0] * v0[1]) / den
    w = 1.0 - u - v
    return (u >= -eps) and (v >= -eps) and (w >= -eps)


def _earclip(poly: numpy.ndarray) -> Optional[numpy.ndarray]:
    """Triangulate a simple 2D polygon by ear clipping.

    Returns face indices (M,3) into ``poly`` or ``None`` on failure.
    """
    n = len(poly)
    if n < 3:
        return None
    area = _signed_area_2d(poly)
    if abs(area) < 1e-12:
        return None

    ccw = area > 0.0
    remaining = list(range(n))
    faces = []
    max_iters = n * n
    iters = 0

    while len(remaining) > 3 and iters < max_iters:
        iters += 1
        ear_found = False
        m = len(remaining)
        for i in range(m):
            ia = remaining[(i - 1) % m]
            ib = remaining[i]
            ic = remaining[(i + 1) % m]
            a = poly[ia]
            b = poly[ib]
            c = poly[ic]

            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if ccw:
                if cross <= 1e-12:
                    continue
            else:
                if cross >= -1e-12:
                    continue

            has_inside = False
            for ip in remaining:
                if ip in (ia, ib, ic):
                    continue
                if _point_in_triangle_2d(poly[ip], a, b, c):
                    has_inside = True
                    break
            if has_inside:
                continue

            faces.append([ia, ib, ic] if ccw else [ia, ic, ib])
            del remaining[i]
            ear_found = True
            break

        if not ear_found:
            return None

    if len(remaining) == 3:
        ia, ib, ic = remaining
        faces.append([ia, ib, ic] if ccw else [ia, ic, ib])

    if not faces:
        return None
    return numpy.asarray(faces, dtype=numpy.int32)


def _sanitize_loop(loop_3d: numpy.ndarray) -> Optional[numpy.ndarray]:
    """Drop the closure-duplicate and consecutive duplicate points."""
    pts = numpy.asarray(loop_3d, dtype=numpy.float64)
    if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 3:
        return None
    if len(pts) >= 2 and numpy.linalg.norm(pts[0] - pts[-1]) <= 1e-8:
        pts = pts[:-1]
    if len(pts) < 3:
        return None
    dedup = [pts[0]]
    for p in pts[1:]:
        if numpy.linalg.norm(p - dedup[-1]) > 1e-8:
            dedup.append(p)
    pts = numpy.asarray(dedup, dtype=numpy.float64)
    return pts if len(pts) >= 3 else None


def _fit_plane(loop_3d: numpy.ndarray):
    """Best-fit plane basis ``(origin, u, v)`` via SVD, or ``None``."""
    origin = loop_3d.mean(axis=0)
    centered = loop_3d - origin
    try:
        _, _, vh = numpy.linalg.svd(centered, full_matrices=False)
    except Exception:
        return None
    if vh.shape[0] < 2:
        return None
    u = vh[0]
    v = vh[1]
    nu = numpy.linalg.norm(u)
    nv = numpy.linalg.norm(v)
    if nu < 1e-12 or nv < 1e-12:
        return None
    u = u / nu
    v = v / nv
    n = numpy.cross(u, v)
    nn = numpy.linalg.norm(n)
    if nn < 1e-12:
        return None
    n = n / nn
    v = numpy.cross(n, u)
    vn = numpy.linalg.norm(v)
    if vn < 1e-12:
        return None
    return origin, u, v / vn


def _fan(loop_2d: numpy.ndarray) -> Tuple[Optional[numpy.ndarray], Optional[numpy.ndarray]]:
    """Fan-triangulate from the centroid: returns ``(verts_2d, faces)``.

    Adds one centroid vertex (index n). Always closes the loop topologically.
    """
    n = len(loop_2d)
    if n < 3:
        return None, None
    centroid = loop_2d.mean(axis=0, keepdims=True)
    verts = numpy.vstack([loop_2d, centroid])
    faces = numpy.asarray([[i, (i + 1) % n, n] for i in range(n)], dtype=numpy.int32)
    return verts, faces


def cap_loop(loop_3d: numpy.ndarray) -> Optional[trimesh.Trimesh]:
    """Triangulate one open boundary loop into a planar cap mesh.

    Returns the cap as a ``trimesh.Trimesh`` (vertices in 3D, faces indexing
    them) or ``None`` if the loop is degenerate or cannot be capped.
    """
    loop = _sanitize_loop(loop_3d)
    if loop is None:
        return None
    basis = _fit_plane(loop)
    if basis is None:
        return None
    origin, u, v = basis
    centered = loop - origin
    loop_2d = numpy.column_stack([centered @ u, centered @ v])

    # Reject degenerate (zero-area / collinear) loops — nothing to cap.
    if abs(_signed_area_2d(loop_2d)) < 1e-9:
        return None

    faces = _earclip(loop_2d)
    if faces is not None:
        verts_2d = loop_2d
    else:
        verts_2d, faces = _fan(loop_2d)
        if faces is None:
            return None

    verts_3d = (
        origin[None, :]
        + verts_2d[:, 0:1] * u[None, :]
        + verts_2d[:, 1:2] * v[None, :]
    )
    # Snap the first len(loop) cap vertices back to exact loop coordinates so
    # the seam stitches cleanly under merge_vertices.
    for i in range(len(loop)):
        verts_3d[i] = loop[i]

    return trimesh.Trimesh(
        vertices=verts_3d.astype(numpy.float64),
        faces=faces.astype(numpy.int64),
        process=False,
        validate=False,
    )
