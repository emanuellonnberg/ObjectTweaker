# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import trimesh

from core.pipeline import SimplifyOptions, SimplifyResult, run


def _two_shell_high_poly():
    big = trimesh.creation.icosphere(subdivisions=4)  # 20480 faces
    small = trimesh.creation.box(extents=(0.2, 0.2, 0.2))
    small.apply_translation([10.0, 0.0, 0.0])
    return trimesh.util.concatenate([big, small])


def test_run_applies_all_enabled_ops_and_reports_stats():
    mesh = _two_shell_high_poly()
    opts = SimplifyOptions(
        do_remove_small=True, min_pct=1.0,
        do_decimate=True, decimate_percent=0.1,
        do_smooth=True, smooth_iterations=5,
    )
    result = run(mesh, opts)
    assert isinstance(result, SimplifyResult)
    assert result.parts_removed == 1
    assert result.tris_before == len(mesh.faces)
    assert result.tris_after < result.tris_before
    assert result.tris_after == len(result.mesh.faces)


def test_run_with_no_ops_enabled_returns_input_unchanged():
    mesh = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    result = run(mesh, SimplifyOptions())
    assert result.parts_removed == 0
    assert result.tris_before == result.tris_after == 12
