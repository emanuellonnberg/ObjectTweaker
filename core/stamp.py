# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""2D shape outlines and extruded prisms for the Emboss feature."""
import numpy
import trimesh

from .cap import _earclip


def shape_outline(kind: str, params: dict) -> numpy.ndarray:
    """Return an (N,2) CCW outline centered at the origin.

    kind: "circle" (diameter), "rectangle" (width, height),
    "star" (diameter, points, inner_ratio). Optional "rotation" (degrees).
    """
    if kind == "circle":
        r = float(params["diameter"]) / 2.0
        a = numpy.linspace(0.0, 2.0 * numpy.pi, 48, endpoint=False)
        pts = numpy.column_stack([r * numpy.cos(a), r * numpy.sin(a)])
    elif kind == "rectangle":
        w = float(params["width"]) / 2.0
        h = float(params["height"]) / 2.0
        pts = numpy.array([[-w, -h], [w, -h], [w, h], [-w, h]], dtype=float)
    elif kind == "star":
        ro = float(params["diameter"]) / 2.0
        p = int(params.get("points", 5))
        ri = ro * float(params.get("inner_ratio", 0.5))
        rows = []
        for i in range(2 * p):
            ang = numpy.pi / 2.0 + i * numpy.pi / p
            rr = ro if i % 2 == 0 else ri
            rows.append([rr * numpy.cos(ang), rr * numpy.sin(ang)])
        pts = numpy.array(rows, dtype=float)
    else:
        raise ValueError(f"unknown shape {kind!r}")

    rot = float(params.get("rotation", 0.0))
    if rot:
        t = numpy.radians(rot)
        c, s = numpy.cos(t), numpy.sin(t)
        pts = pts @ numpy.array([[c, s], [-s, c]])
    return pts


def make_prism(outline_2d: numpy.ndarray, height: float) -> trimesh.Trimesh:
    """Extrude a 2D outline into a watertight prism (z in [0, height])."""
    outline = numpy.asarray(outline_2d, dtype=float)
    n = len(outline)
    cap_faces = _earclip(outline)
    if cap_faces is None:
        raise ValueError("could not triangulate outline")

    bottom = numpy.column_stack([outline, numpy.zeros(n)])
    top = numpy.column_stack([outline, numpy.full(n, float(height))])
    verts = numpy.vstack([bottom, top])

    faces = []
    for a, b, c in cap_faces:        # bottom cap, reversed winding (faces -Z)
        faces.append([a, c, b])
    for a, b, c in cap_faces:        # top cap, offset into the top ring
        faces.append([a + n, b + n, c + n])
    for i in range(n):               # side walls
        j = (i + 1) % n
        faces.append([i, j, j + n])
        faces.append([i, j + n, i + n])

    mesh = trimesh.Trimesh(vertices=verts, faces=numpy.asarray(faces, dtype=numpy.int64),
                           process=False)
    mesh.fix_normals()
    return mesh
