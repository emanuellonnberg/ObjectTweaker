# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Surface smoothing via trimesh's Taubin/Laplacian filters."""
import trimesh
from trimesh.smoothing import filter_laplacian, filter_taubin


def smooth(
    mesh: trimesh.Trimesh,
    iterations: int = 10,
    method: str = "taubin",
) -> trimesh.Trimesh:
    """Return a smoothed copy of ``mesh``.

    Args:
        mesh: input mesh (not mutated).
        iterations: number of smoothing passes.
        method: ``"taubin"`` (volume-preserving) or ``"laplacian"``.

    Raises:
        ValueError: if ``method`` is unknown.
    """
    work = mesh.copy()
    if method == "taubin":
        filter_taubin(work, iterations=iterations)
    elif method == "laplacian":
        filter_laplacian(work, iterations=iterations)
    else:
        raise ValueError("method must be 'taubin' or 'laplacian'")
    return work
