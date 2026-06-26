# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Remove tiny disconnected shells (scan/boolean debris) from a mesh."""
from typing import Tuple

import numpy
import trimesh


def _bbox_volume(component: trimesh.Trimesh) -> float:
    """Physical size proxy: product of the component's bounding-box extents."""
    return float(numpy.prod(component.extents))


def remove_small_parts(
    mesh: trimesh.Trimesh,
    min_pct: float = 1.0,
    keep_largest_only: bool = False,
) -> Tuple[trimesh.Trimesh, int]:
    """Drop small connected components and return ``(mesh, parts_removed)``.

    Size is measured by bounding-box volume (so a physically tiny shell is
    dropped even if it has the same face count as the main body, e.g. two
    cubes). Face count is a poor proxy here — a tiny cube and a huge cube both
    have 12 faces.

    Args:
        mesh: input mesh.
        min_pct: keep a component only if its bounding-box volume is at least
            this percent of the largest component's bounding-box volume.
        keep_largest_only: if True, keep just the single largest component.
    """
    components = mesh.split(only_watertight=False)
    if len(components) <= 1:
        return mesh, 0

    components = sorted(components, key=_bbox_volume, reverse=True)
    largest_size = _bbox_volume(components[0])

    if keep_largest_only or largest_size <= 0.0:
        kept = components[:1]
    else:
        threshold = largest_size * (min_pct / 100.0)
        kept = [c for c in components if _bbox_volume(c) >= threshold]

    removed = len(components) - len(kept)
    if len(kept) == 1:
        return kept[0], removed
    return trimesh.util.concatenate(kept), removed
