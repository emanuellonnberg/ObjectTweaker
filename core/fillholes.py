# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Detect every open boundary loop of a mesh and cap them watertight."""
from collections import defaultdict
from typing import List, Tuple

import numpy
import trimesh

from .cap import cap_loop


def _edge_key(a: int, b: int):
    return (a, b) if a < b else (b, a)


def _boundary_loops(mesh: trimesh.Trimesh) -> List[numpy.ndarray]:
    """Return open boundary loops as a list of (N,3) polylines.

    A boundary edge is one used by exactly one face. Boundary edges are chained
    into loops by walking the boundary-edge graph (each boundary vertex of a
    simple hole has degree two). Pure numpy + stdlib — no networkx, which
    trimesh's ``outline().discrete`` would otherwise require.
    """
    edges = numpy.asarray(mesh.edges_sorted)
    if len(edges) == 0:
        return []
    uniq, counts = numpy.unique(edges, axis=0, return_counts=True)
    boundary = uniq[counts == 1]
    if len(boundary) == 0:
        return []

    adj = defaultdict(list)
    for a, b in boundary:
        adj[int(a)].append(int(b))
        adj[int(b)].append(int(a))

    visited = set()
    loops: List[numpy.ndarray] = []
    for sa, sb in boundary:
        sa, sb = int(sa), int(sb)
        if _edge_key(sa, sb) in visited:
            continue
        visited.add(_edge_key(sa, sb))
        loop = [sa, sb]
        prev, cur = sa, sb
        while True:
            nxt = None
            for n in adj[cur]:
                if _edge_key(cur, n) not in visited:
                    nxt = n
                    break
            if nxt is None:
                break
            visited.add(_edge_key(cur, nxt))
            if nxt == loop[0]:
                break
            loop.append(nxt)
            prev, cur = cur, nxt
        if len(loop) >= 3:
            loops.append(numpy.asarray(mesh.vertices[loop], dtype=numpy.float64))
    return loops


def fill_holes(mesh: trimesh.Trimesh) -> Tuple[trimesh.Trimesh, int]:
    """Cap all open boundary loops and return ``(filled_mesh, holes_filled)``."""
    loops = _boundary_loops(mesh)
    caps = [cap_loop(loop) for loop in loops]
    caps = [c for c in caps if c is not None]
    if not caps:
        return mesh, 0

    combined = trimesh.util.concatenate([mesh] + caps)
    try:
        combined.merge_vertices(digits_vertex=7)
        combined.remove_unreferenced_vertices()
    except Exception:
        pass
    try:
        combined.fix_normals()
    except Exception:
        pass
    return combined, len(caps)
