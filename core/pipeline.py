# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Run the enabled Simplify operations in order and collect statistics."""
from dataclasses import dataclass

import trimesh

from core.cleanup import remove_small_parts
from core.decimate import decimate
from core.smooth import smooth


@dataclass
class SimplifyOptions:
    """User-selected operations and their parameters."""

    do_remove_small: bool = False
    min_pct: float = 1.0
    keep_largest_only: bool = False
    do_decimate: bool = False
    decimate_percent: float = 0.5
    do_smooth: bool = False
    smooth_iterations: int = 10
    smooth_method: str = "taubin"


@dataclass
class SimplifyResult:
    """Result mesh plus before/after statistics."""

    mesh: trimesh.Trimesh
    tris_before: int
    tris_after: int
    parts_removed: int


def run(mesh: trimesh.Trimesh, options: SimplifyOptions) -> SimplifyResult:
    """Apply enabled ops in order: remove-small -> decimate -> smooth."""
    tris_before = len(mesh.faces)
    parts_removed = 0
    work = mesh

    if options.do_remove_small:
        work, parts_removed = remove_small_parts(
            work, min_pct=options.min_pct,
            keep_largest_only=options.keep_largest_only,
        )
    if options.do_decimate:
        work = decimate(work, percent=options.decimate_percent)
    if options.do_smooth:
        work = smooth(work, iterations=options.smooth_iterations,
                      method=options.smooth_method)

    return SimplifyResult(
        mesh=work,
        tris_before=tris_before,
        tris_after=len(work.faces),
        parts_removed=parts_removed,
    )
