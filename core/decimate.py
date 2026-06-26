# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Quadric edge-collapse decimation via trimesh + fast-simplification."""
from typing import Optional

import trimesh


def decimate(
    mesh: trimesh.Trimesh,
    percent: Optional[float] = None,
    target_count: Optional[int] = None,
) -> trimesh.Trimesh:
    """Reduce triangle count, preserving overall shape.

    Args:
        mesh: input mesh.
        percent: fraction of faces to keep (0 < percent <= 1). Ignored if
            ``target_count`` is given.
        target_count: absolute target face count.

    Raises:
        ValueError: if neither ``percent`` nor ``target_count`` is provided,
            or the resolved target is not positive.
    """
    if target_count is None:
        if percent is None:
            raise ValueError("Provide either percent or target_count")
        target_count = round(len(mesh.faces) * percent)
    if target_count <= 0:
        raise ValueError("target_count must be positive")
    if target_count >= len(mesh.faces):
        return mesh
    return mesh.simplify_quadric_decimation(face_count=target_count)
