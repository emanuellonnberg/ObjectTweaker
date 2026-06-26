# ObjectTweaker — Simplify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Cura Tool plugin, ObjectTweaker, whose MVP "Simplify" feature decimates, smooths, and removes small disconnected parts of the selected model in place, with a Preview → Apply → Reset flow.

**Architecture:** Pure-Python `core/` package (no Cura imports, unit-tested with pytest) does all mesh math via `trimesh`. A thin `ObjectTweaker.py` Cura Tool adapter converts the selected node's `MeshData` to/from trimesh, runs the pipeline on a background daemon thread for Preview, swaps the node's displayed mesh, and commits on Apply via an undoable `Operation`. Two QML panels (`qml/` UM 1.5, `qt6/` UM 1.6) stay in sync.

**Tech Stack:** Python 3.10–3.12, trimesh 4.x (bundled), fast-simplification (bundled, decimation backend), numpy/scipy (from Cura), pytest, Cura/Uranium SDK (`UM.*`, `cura.*`), QML.

## Global Constraints

- `plugin.json`: `"api": 8`, `"supported_sdk_versions": ["8.0.0".."8.9.0"]`, `"minimum_cura_version": "5.0.0"`.
- `core/` modules MUST NOT import any `UM.*` or `cura.*` symbol. Cura glue lives only in `ObjectTweaker.py`.
- No code may depend on a triangulation engine (`mapbox_earcut` / `triangle`). The three ops never generate new faces, so this holds by construction — do not introduce capping/`triangulate_polygon`.
- Dual QML: `qml/ObjectTweaker.qml` (UM 1.5) and `qt6/ObjectTweaker.qml` (UM 1.6) must stay byte-identical except the `import UM` version line.
- Every `.py` file starts with the LGPLv3 copyright header (2 lines, see Task 1).
- Style: PEP 8, type hints throughout, Google-style docstrings.
- Bundle only non-Cura deps into `lib/` (`trimesh`, `fast-simplification`). Never bundle numpy/scipy.
- Commit after every task's tests pass.

---

### Task 1: Project scaffold, manifest, and test harness

**Files:**
- Create: `plugin.json`
- Create: `__init__.py`
- Create: `icon.svg`
- Create: `pytest.ini`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`
- Create: `requirements-test.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable `core` package root (added to `sys.path` by `conftest.py`), the `getMetaData()`/`register(app)` plugin entry points, and a green pytest run.

- [ ] **Step 1: Create `core/__init__.py`** (empty file, marks the package)

```python
```

- [ ] **Step 2: Create `tests/conftest.py`** so tests import `core.*` from the project root

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 4: Write the smoke test `tests/test_smoke.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import trimesh


def test_trimesh_importable_and_builds_a_box():
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    assert len(mesh.faces) == 12
```

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS (1 passed). If trimesh is missing, `pip install -r requirements-test.txt` first.

- [ ] **Step 6: Create `requirements-test.txt`**

```text
trimesh>=4.0
fast-simplification
numpy
scipy
pytest
```

- [ ] **Step 7: Create `plugin.json`**

```json
{
    "name": "Object Tweaker",
    "author": "Emanuel Lönnberg",
    "version": "0.1.0",
    "description": "Modify the selected model in place: simplify (decimate), smooth, and remove small disconnected parts.",
    "i18n-catalog": "objecttweaker",
    "api": 8,
    "supported_sdk_versions": ["8.0.0", "8.1.0", "8.2.0", "8.3.0", "8.4.0", "8.5.0", "8.6.0", "8.7.0", "8.8.0", "8.9.0"],
    "minimum_cura_version": "5.0.0"
}
```

- [ ] **Step 8: Create `icon.svg`** (simple placeholder glyph)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <path fill="currentColor" d="M3 17l6-6 4 4 8-8v4h2V3h-7v2h4l-7 7-4-4-8 8z"/>
</svg>
```

- [ ] **Step 9: Create `__init__.py`** (plugin registration; mirrors ObjectSplitter's lib/ injection and conditional Cura import)

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import sys
import os

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir = os.path.join(_plugin_dir, "lib")
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
    # Replace Cura's old trimesh 3.x with the bundled 4.x if present.
    if "trimesh" in sys.modules:
        _old = getattr(sys.modules["trimesh"], "__version__", "0")
        if _old.startswith("3."):
            for _k in [k for k in sys.modules if k == "trimesh" or k.startswith("trimesh.")]:
                del sys.modules[_k]
            import trimesh  # noqa: F401  loads 4.x from lib/

try:
    from . import ObjectTweaker as _ObjectTweakerModule
    from UM.Logger import Logger
    from UM.i18n import i18nCatalog

    _CURA_AVAILABLE = True
    i18n_catalog = i18nCatalog("objecttweaker")
except ImportError:
    _CURA_AVAILABLE = False


def getMetaData():
    if not _CURA_AVAILABLE:
        return {}
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Object Tweaker"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Simplify, smooth, and clean up the selected model."),
            "icon": "icon.svg",
            "tool_panel": "qml/ObjectTweaker.qml",
            "weight": 6
        }
    }


def register(app):
    if not _CURA_AVAILABLE:
        return {}
    tool = _ObjectTweakerModule.ObjectTweaker()
    tool.setPluginId("ObjectTweaker")
    return {"tool": tool}
```

- [ ] **Step 10: Run the full suite**

Run: `pytest -v`
Expected: PASS (1 passed). `__init__.py` is NOT imported by tests (it pulls Cura), so it cannot break the run.

- [ ] **Step 11: Commit**

```bash
git add core/__init__.py tests/conftest.py pytest.ini tests/test_smoke.py requirements-test.txt plugin.json icon.svg __init__.py
git commit -m "feat: scaffold ObjectTweaker plugin manifest and test harness"
```

---

### Task 2: `core/mesh_io.py` — ndarray ↔ trimesh conversion

**Files:**
- Create: `core/mesh_io.py`
- Test: `tests/test_mesh_io.py`

**Interfaces:**
- Consumes: numpy arrays of vertices/faces (the raw form `ObjectTweaker.py` extracts from Cura `MeshData`).
- Produces:
  - `to_trimesh(vertices: numpy.ndarray, faces: numpy.ndarray) -> trimesh.Trimesh`
  - `from_trimesh(mesh: trimesh.Trimesh) -> tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]` returning `(vertices float32 (N,3), faces int32 (M,3), vertex_normals float32 (N,3))`.

- [ ] **Step 1: Write the failing test `tests/test_mesh_io.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.mesh_io import to_trimesh, from_trimesh


def test_to_trimesh_merges_triangle_soup():
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    # Explode into triangle soup: every face gets its own 3 unique vertices.
    soup_verts = box.vertices[box.faces].reshape(-1, 3)
    soup_faces = numpy.arange(len(soup_verts)).reshape(-1, 3)
    mesh = to_trimesh(soup_verts, soup_faces)
    assert len(mesh.faces) == 12
    assert len(mesh.vertices) == 8  # merge_vertices collapsed the soup


def test_from_trimesh_returns_typed_arrays():
    box = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts, faces, normals = from_trimesh(box)
    assert verts.dtype == numpy.float32 and verts.shape[1] == 3
    assert faces.dtype == numpy.int32 and faces.shape[1] == 3
    assert normals.shape == verts.shape
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_io.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.mesh_io'`.

- [ ] **Step 3: Write `core/mesh_io.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Convert between raw vertex/face arrays and trimesh objects.

This is the only boundary that touches mesh array layout. It never imports
Cura; ``ObjectTweaker.py`` is responsible for ``MeshData`` <-> ndarray.
"""
from typing import Tuple

import numpy
import trimesh


def to_trimesh(vertices: numpy.ndarray, faces: numpy.ndarray) -> trimesh.Trimesh:
    """Build a trimesh from vertex/face arrays, deduplicating shared vertices.

    Cura frequently stores meshes as "triangle soup" with no shared vertices;
    ``merge_vertices`` rebuilds adjacency so ``split`` and decimation work.
    """
    verts = numpy.asarray(vertices, dtype=numpy.float64)
    if verts.ndim == 1:
        verts = verts.reshape(-1, 3)
    faces_arr = numpy.asarray(faces, dtype=numpy.int64)
    if faces_arr.ndim == 1:
        faces_arr = faces_arr.reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces_arr, process=False)
    mesh.merge_vertices()
    return mesh


def from_trimesh(
    mesh: trimesh.Trimesh,
) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    """Return ``(vertices f32, faces i32, vertex_normals f32)`` for Cura.

    Vertex normals are returned so the adapter can skip Cura's slow pure-Python
    normal recomputation.
    """
    verts = numpy.asarray(mesh.vertices, dtype=numpy.float32)
    faces = numpy.asarray(mesh.faces, dtype=numpy.int32)
    normals = numpy.asarray(mesh.vertex_normals, dtype=numpy.float32)
    return verts, faces, normals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mesh_io.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/mesh_io.py tests/test_mesh_io.py
git commit -m "feat: add mesh_io ndarray<->trimesh conversion"
```

---

### Task 3: `core/cleanup.py` — remove small disconnected parts

**Files:**
- Create: `core/cleanup.py`
- Test: `tests/test_cleanup.py`

**Interfaces:**
- Consumes: a `trimesh.Trimesh`.
- Produces: `remove_small_parts(mesh: trimesh.Trimesh, min_pct: float = 1.0, keep_largest_only: bool = False) -> tuple[trimesh.Trimesh, int]` returning `(result_mesh, parts_removed)`. `min_pct` is the bounding-box-volume threshold as a percent of the largest component (a shell whose bbox volume is under `min_pct%` of the largest component's is dropped). Bounding-box volume, not face count: a tiny cube and a huge cube both have 12 faces. `keep_largest_only=True` keeps exactly one component.

- [ ] **Step 1: Write the failing test `tests/test_cleanup.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import trimesh

from core.cleanup import remove_small_parts


def _two_shell_mesh():
    big = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    small = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    small.apply_translation([50.0, 0.0, 0.0])  # far away, disjoint
    return trimesh.util.concatenate([big, small])


def test_removes_the_small_shell():
    mesh, removed = remove_small_parts(_two_shell_mesh(), min_pct=1.0)
    assert removed == 1
    # Big box has 12 faces; result should be just the big box.
    assert len(mesh.faces) == 12


def test_keep_largest_only_collapses_to_one_component():
    mesh, removed = remove_small_parts(_two_shell_mesh(), keep_largest_only=True)
    assert removed == 1
    assert len(mesh.split(only_watertight=False)) == 1


def test_single_shell_removes_nothing():
    box = trimesh.creation.box(extents=(3.0, 3.0, 3.0))
    mesh, removed = remove_small_parts(box, min_pct=1.0)
    assert removed == 0
    assert len(mesh.faces) == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cleanup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.cleanup'`.

- [ ] **Step 3: Write `core/cleanup.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Remove tiny disconnected shells (scan/boolean debris) from a mesh."""
from typing import Tuple

import trimesh


def remove_small_parts(
    mesh: trimesh.Trimesh,
    min_pct: float = 1.0,
    keep_largest_only: bool = False,
) -> Tuple[trimesh.Trimesh, int]:
    """Drop small connected components and return ``(mesh, parts_removed)``.

    Args:
        mesh: input mesh.
        min_pct: keep a component only if its face count is at least this
            percent of the largest component's face count.
        keep_largest_only: if True, keep just the single largest component.
    """
    components = mesh.split(only_watertight=False)
    if len(components) <= 1:
        return mesh, 0

    components = sorted(components, key=lambda c: len(c.faces), reverse=True)
    largest_faces = len(components[0].faces)

    if keep_largest_only:
        kept = components[:1]
    else:
        threshold = largest_faces * (min_pct / 100.0)
        kept = [c for c in components if len(c.faces) >= threshold]

    removed = len(components) - len(kept)
    if len(kept) == 1:
        return kept[0], removed
    return trimesh.util.concatenate(kept), removed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cleanup.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/cleanup.py tests/test_cleanup.py
git commit -m "feat: add cleanup.remove_small_parts"
```

---

### Task 4: `core/decimate.py` — quadric decimation

**Files:**
- Create: `core/decimate.py`
- Test: `tests/test_decimate.py`

**Interfaces:**
- Consumes: a `trimesh.Trimesh`.
- Produces: `decimate(mesh: trimesh.Trimesh, percent: float = None, target_count: int = None) -> trimesh.Trimesh`. Exactly one of `percent` (fraction of faces to KEEP, 0 < percent <= 1) or `target_count` (absolute face count) is used; `percent` resolves to `target_count = round(len(mesh.faces) * percent)`. Backed by `trimesh.Trimesh.simplify_quadric_decimation`, which requires the `fast-simplification` package.

- [ ] **Step 1: Write the failing test `tests/test_decimate.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import trimesh

from core.decimate import decimate


def test_decimate_to_target_count_reduces_faces():
    sphere = trimesh.creation.icosphere(subdivisions=4)  # 20480 faces
    out = decimate(sphere, target_count=500)
    assert 0 < len(out.faces) <= 600  # within ~20% of target
    assert len(out.faces) < len(sphere.faces)


def test_decimate_percent_keeps_roughly_that_fraction():
    sphere = trimesh.creation.icosphere(subdivisions=4)
    out = decimate(sphere, percent=0.1)
    assert len(out.faces) <= len(sphere.faces) * 0.15


def test_decimate_preserves_overall_shape():
    sphere = trimesh.creation.icosphere(subdivisions=4)
    out = decimate(sphere, target_count=800)
    # Bounding box stays close to the unit sphere's [-1, 1] extents.
    assert abs(out.bounds[1][0] - 1.0) < 0.1
    assert abs(out.bounds[0][0] + 1.0) < 0.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_decimate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.decimate'`.

- [ ] **Step 3: Write `core/decimate.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_decimate.py -v`
Expected: PASS (3 passed). If it errors with a fast-simplification message, run `pip install fast-simplification`.

- [ ] **Step 5: Commit**

```bash
git add core/decimate.py tests/test_decimate.py
git commit -m "feat: add quadric decimation"
```

---

### Task 5: `core/smooth.py` — Taubin/Laplacian smoothing

**Files:**
- Create: `core/smooth.py`
- Test: `tests/test_smooth.py`

**Interfaces:**
- Consumes: a `trimesh.Trimesh`.
- Produces: `smooth(mesh: trimesh.Trimesh, iterations: int = 10, method: str = "taubin") -> trimesh.Trimesh`. `method` is `"taubin"` (default, volume-preserving) or `"laplacian"`. Returns a smoothed COPY; the input is not mutated. Topology (vertex/face counts) is unchanged.

- [ ] **Step 1: Write the failing test `tests/test_smooth.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.smooth import smooth


def _noisy_sphere(seed: int = 0):
    sphere = trimesh.creation.icosphere(subdivisions=3)
    rng = numpy.random.default_rng(seed)
    sphere.vertices += rng.normal(scale=0.03, size=sphere.vertices.shape)
    return sphere


def _radius_std(mesh):
    radii = numpy.linalg.norm(mesh.vertices - mesh.centroid, axis=1)
    return float(numpy.std(radii))


def test_smoothing_reduces_surface_noise():
    noisy = _noisy_sphere()
    before = _radius_std(noisy)
    out = smooth(noisy, iterations=15)
    assert _radius_std(out) < before


def test_smoothing_preserves_topology_and_does_not_mutate_input():
    noisy = _noisy_sphere()
    original = noisy.vertices.copy()
    out = smooth(noisy, iterations=5)
    assert out.faces.shape == noisy.faces.shape
    assert out.vertices.shape == noisy.vertices.shape
    assert numpy.allclose(noisy.vertices, original)  # input untouched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smooth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.smooth'`.

- [ ] **Step 3: Write `core/smooth.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smooth.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/smooth.py tests/test_smooth.py
git commit -m "feat: add Taubin/Laplacian smoothing"
```

---

### Task 6: `core/pipeline.py` — orchestrate the three ops + stats

**Files:**
- Create: `core/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `core.cleanup.remove_small_parts`, `core.decimate.decimate`, `core.smooth.smooth`, a `trimesh.Trimesh`.
- Produces:
  - `@dataclass SimplifyOptions` with fields: `do_remove_small: bool = False`, `min_pct: float = 1.0`, `keep_largest_only: bool = False`, `do_decimate: bool = False`, `decimate_percent: float = 0.5`, `do_smooth: bool = False`, `smooth_iterations: int = 10`, `smooth_method: str = "taubin"`.
  - `@dataclass SimplifyResult` with fields: `mesh: trimesh.Trimesh`, `tris_before: int`, `tris_after: int`, `parts_removed: int`.
  - `run(mesh: trimesh.Trimesh, options: SimplifyOptions) -> SimplifyResult`. Runs enabled ops in order **remove-small → decimate → smooth**.

- [ ] **Step 1: Write the failing test `tests/test_pipeline.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.pipeline'`.

- [ ] **Step 3: Write `core/pipeline.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full core suite**

Run: `pytest -v`
Expected: PASS (all tasks 1–6 green).

- [ ] **Step 6: Commit**

```bash
git add core/pipeline.py tests/test_pipeline.py
git commit -m "feat: add Simplify pipeline orchestrator with stats"
```

---

### Task 7: `ObjectTweaker.py` — Cura Tool adapter (preview/apply/reset + undo)

**Files:**
- Create: `ObjectTweaker.py`

**Interfaces:**
- Consumes: `core.mesh_io.to_trimesh` / `from_trimesh`, `core.pipeline.SimplifyOptions` / `run`; Cura `Tool`, `Selection`, `MeshData`, `MeshBuilder`, `Operation`, `OperationStack`.
- Produces: the `ObjectTweaker` Tool class referenced by `__init__.register`. Exposes these QML properties (each with a `getX`/`setX` pair, registered via `setExposedProperties`): `DoRemoveSmall`, `MinPct`, `KeepLargestOnly`, `DoDecimate`, `DecimatePercent`, `DoSmooth`, `SmoothIterations`, plus read-only `Busy`, `StatsText`, `HasPreview`, `SelectionValid`. QML slots: `preview()`, `apply()`, `reset()`.

> **Verification note:** this task touches Cura runtime types and cannot be exercised by pytest. Verify manually in Cura per the Manual Test Checklist at the end of this task. The TDD loop here is "load in Cura, exercise the panel."

- [ ] **Step 1: Write `ObjectTweaker.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Cura Tool adapter for ObjectTweaker's Simplify feature."""
import threading
from typing import Optional

import numpy

from UM.Logger import Logger
from UM.Application import Application
from UM.Tool import Tool
from UM.Mesh.MeshData import MeshData
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Scene.Selection import Selection
from UM.Operations.Operation import Operation

from cura.CuraApplication import CuraApplication
from cura.Scene.CuraSceneNode import CuraSceneNode

from core.mesh_io import to_trimesh, from_trimesh
from core.pipeline import SimplifyOptions, run

_COMPUTE_TIMEOUT_S = 30.0


class _SetMeshDataOperation(Operation):
    """Undoable in-place replacement of a node's MeshData."""

    def __init__(self, node: CuraSceneNode, old_mesh: MeshData, new_mesh: MeshData) -> None:
        super().__init__()
        self._node = node
        self._old_mesh = old_mesh
        self._new_mesh = new_mesh

    def undo(self) -> None:
        self._node.setMeshData(self._old_mesh)

    def redo(self) -> None:
        self._node.setMeshData(self._new_mesh)


class ObjectTweaker(Tool):
    def __init__(self) -> None:
        super().__init__()

        self._do_remove_small = False
        self._min_pct = 1.0
        self._keep_largest_only = False
        self._do_decimate = True
        self._decimate_percent = 50.0   # UI percent (keep 50%)
        self._do_smooth = False
        self._smooth_iterations = 10

        self._busy = False
        self._stats_text = ""
        self._has_preview = False

        # Preview state.
        self._target_node: Optional[CuraSceneNode] = None
        self._original_mesh: Optional[MeshData] = None
        self._preview_mesh: Optional[MeshData] = None

        self.setExposedProperties(
            "DoRemoveSmall", "MinPct", "KeepLargestOnly",
            "DoDecimate", "DecimatePercent",
            "DoSmooth", "SmoothIterations",
            "Busy", "StatsText", "HasPreview", "SelectionValid",
        )

        Selection.selectionChanged.connect(self._onSelectionChanged)

    # ---- selection -----------------------------------------------------
    def _onSelectionChanged(self) -> None:
        # Drop any uncommitted preview when the selection changes.
        self._revertPreview()
        self._stats_text = ""
        self._has_preview = False
        self.propertyChanged.emit()

    def _selectedMeshNode(self) -> Optional[CuraSceneNode]:
        if Selection.getCount() != 1:
            return None
        node = Selection.getSelectedObject(0)
        if node is None or node.getMeshData() is None:
            return None
        return node

    def getSelectionValid(self) -> bool:
        return self._selectedMeshNode() is not None

    # ---- exposed scalar properties ------------------------------------
    def getDoRemoveSmall(self) -> bool:
        return self._do_remove_small

    def setDoRemoveSmall(self, value: bool) -> None:
        if value != self._do_remove_small:
            self._do_remove_small = value
            self.propertyChanged.emit()

    def getMinPct(self) -> float:
        return self._min_pct

    def setMinPct(self, value: float) -> None:
        value = float(value)
        if value != self._min_pct:
            self._min_pct = value
            self.propertyChanged.emit()

    def getKeepLargestOnly(self) -> bool:
        return self._keep_largest_only

    def setKeepLargestOnly(self, value: bool) -> None:
        if value != self._keep_largest_only:
            self._keep_largest_only = value
            self.propertyChanged.emit()

    def getDoDecimate(self) -> bool:
        return self._do_decimate

    def setDoDecimate(self, value: bool) -> None:
        if value != self._do_decimate:
            self._do_decimate = value
            self.propertyChanged.emit()

    def getDecimatePercent(self) -> float:
        return self._decimate_percent

    def setDecimatePercent(self, value: float) -> None:
        value = float(value)
        if value != self._decimate_percent:
            self._decimate_percent = value
            self.propertyChanged.emit()

    def getDoSmooth(self) -> bool:
        return self._do_smooth

    def setDoSmooth(self, value: bool) -> None:
        if value != self._do_smooth:
            self._do_smooth = value
            self.propertyChanged.emit()

    def getSmoothIterations(self) -> int:
        return self._smooth_iterations

    def setSmoothIterations(self, value: int) -> None:
        value = int(value)
        if value != self._smooth_iterations:
            self._smooth_iterations = value
            self.propertyChanged.emit()

    def getBusy(self) -> bool:
        return self._busy

    def getStatsText(self) -> str:
        return self._stats_text

    def getHasPreview(self) -> bool:
        return self._has_preview

    # ---- mesh extraction / build (Cura <-> ndarray) -------------------
    def _extractLocal(self, node: CuraSceneNode):
        mesh_data = node.getMeshData()
        vertices = numpy.asarray(mesh_data.getVertices(), dtype=numpy.float64)
        if vertices.ndim == 1:
            vertices = vertices.reshape(-1, 3)
        indices = mesh_data.getIndices()
        if indices is None:
            faces = numpy.arange(len(vertices), dtype=numpy.int32).reshape(-1, 3)
        else:
            faces = numpy.asarray(indices, dtype=numpy.int32)
            if faces.ndim == 1:
                faces = faces.reshape(-1, 3)
        return to_trimesh(vertices, faces)

    def _buildMeshData(self, mesh) -> MeshData:
        verts, faces, normals = from_trimesh(mesh)
        if normals.shape == verts.shape:
            return MeshData(vertices=verts, indices=faces, normals=normals)
        builder = MeshBuilder()
        builder.setVertices(verts)
        builder.setIndices(faces)
        builder.calculateNormals()
        return builder.build()

    def _currentOptions(self) -> SimplifyOptions:
        return SimplifyOptions(
            do_remove_small=self._do_remove_small,
            min_pct=self._min_pct,
            keep_largest_only=self._keep_largest_only,
            do_decimate=self._do_decimate,
            decimate_percent=max(0.01, min(1.0, self._decimate_percent / 100.0)),
            do_smooth=self._do_smooth,
            smooth_iterations=self._smooth_iterations,
            smooth_method="taubin",
        )

    # ---- preview / apply / reset --------------------------------------
    def preview(self) -> None:
        node = self._selectedMeshNode()
        if node is None or self._busy:
            return
        self._revertPreview()
        self._target_node = node
        self._original_mesh = node.getMeshData()
        self._busy = True
        self._stats_text = "Working..."
        self.propertyChanged.emit()
        threading.Thread(target=self._previewWorker, args=(node,), daemon=True).start()

    def _previewWorker(self, node: CuraSceneNode) -> None:
        result_box = {}

        def _compute() -> None:
            mesh = self._extractLocal(node)
            result_box["result"] = run(mesh, self._currentOptions())

        worker = threading.Thread(target=_compute, daemon=True)
        worker.start()
        worker.join(_COMPUTE_TIMEOUT_S)

        def _finish() -> None:
            self._busy = False
            if worker.is_alive() or "result" not in result_box:
                self._stats_text = "Failed (timed out or error)"
                self._has_preview = False
            else:
                result = result_box["result"]
                self._preview_mesh = self._buildMeshData(result.mesh)
                node.setMeshData(self._preview_mesh)
                node.calculateBoundingBoxMesh()
                extra = f", removed {result.parts_removed} part(s)" if result.parts_removed else ""
                self._stats_text = f"tris: {result.tris_before} -> {result.tris_after}{extra}"
                self._has_preview = True
            self.propertyChanged.emit()

        CuraApplication.getInstance().callLater(_finish)

    def _revertPreview(self) -> None:
        if self._target_node is not None and self._original_mesh is not None and self._has_preview:
            self._target_node.setMeshData(self._original_mesh)
            self._target_node.calculateBoundingBoxMesh()
        self._preview_mesh = None
        self._has_preview = False

    def reset(self) -> None:
        self._revertPreview()
        self._target_node = None
        self._original_mesh = None
        self._stats_text = ""
        self.propertyChanged.emit()

    def apply(self) -> None:
        if not self._has_preview or self._target_node is None:
            return
        if self._original_mesh is None or self._preview_mesh is None:
            return
        op = _SetMeshDataOperation(self._target_node, self._original_mesh, self._preview_mesh)
        Application.getInstance().getOperationStack().push(op)
        Logger.log("d", "ObjectTweaker: applied %s", self._stats_text)
        # The committed mesh is now the baseline; clear preview state.
        self._target_node = None
        self._original_mesh = None
        self._preview_mesh = None
        self._has_preview = False
        self.propertyChanged.emit()
```

- [ ] **Step 2: Manual Test Checklist (in Cura)**

Build/install the package (Task 9 provides the build script), then in Cura:
1. Load a model, select it, activate Object Tweaker → panel appears, stats empty.
2. Enable Decimate, set keep 25%, click **Preview** → spinner shows, then mesh visibly coarsens and stat reads `tris: A -> B` with B < A.
3. Click **Reset** → mesh returns to original detail.
4. Preview again, click **Apply** → mesh stays coarse; Ctrl+Z restores original (undo works); Ctrl+Y re-applies.
5. Enable Remove small parts on a model with debris → stat shows `removed N part(s)`.
6. Deselect / select another model mid-preview → preview reverts cleanly, no crash.
7. Check `cura.log` for no tracebacks.

- [ ] **Step 3: Commit**

```bash
git add ObjectTweaker.py
git commit -m "feat: add Cura Tool adapter with preview/apply/reset and undo"
```

---

### Task 8: QML panels (`qml/` and `qt6/`)

**Files:**
- Create: `qml/ObjectTweaker.qml`
- Create: `qt6/ObjectTweaker.qml`

**Interfaces:**
- Consumes: the tool properties/slots from Task 7 via `UM.ActiveToolProxy` (`UM.ActiveTool.properties.getValue("X")`, `UM.ActiveTool.setProperty`, `UM.ActiveTool.triggerAction`).
- Produces: the tool panel UI.

> **Verification note:** QML is verified in Cura (Manual Test Checklist, Task 7). The dual-file sync is the testable invariant here.

- [ ] **Step 1: Write `qt6/ObjectTweaker.qml`** (UM 1.6)

```qml
// Copyright (c) 2026 Emanuel Lönnberg.
// This tool is released under the terms of the LGPLv3 or higher.
import QtQuick 2.10
import QtQuick.Controls 2.15

import UM 1.6 as UM
import Cura 1.0 as Cura

Item {
    id: base
    width: childrenRect.width
    height: childrenRect.height

    property bool selectionValid: UM.ActiveTool.properties.getValue("SelectionValid")
    property bool busy: UM.ActiveTool.properties.getValue("Busy")
    property bool hasPreview: UM.ActiveTool.properties.getValue("HasPreview")

    Column {
        id: items
        spacing: UM.Theme.getSize("default_margin").height

        UM.CheckBox {
            id: decimateCheck
            text: "Decimate (reduce triangles)"
            checked: UM.ActiveTool.properties.getValue("DoDecimate")
            onClicked: UM.ActiveTool.setProperty("DoDecimate", checked)
        }
        Row {
            spacing: UM.Theme.getSize("default_margin").width
            visible: decimateCheck.checked
            UM.Label { text: "Keep %" }
            UM.Slider {
                id: decimateSlider
                width: UM.Theme.getSize("setting_control").width
                from: 1; to: 100
                value: UM.ActiveTool.properties.getValue("DecimatePercent")
                onPressedChanged: if (!pressed) UM.ActiveTool.setProperty("DecimatePercent", value)
            }
            UM.Label { text: Math.round(decimateSlider.value) + "%" }
        }

        UM.CheckBox {
            id: smoothCheck
            text: "Smooth surface"
            checked: UM.ActiveTool.properties.getValue("DoSmooth")
            onClicked: UM.ActiveTool.setProperty("DoSmooth", checked)
        }
        Row {
            spacing: UM.Theme.getSize("default_margin").width
            visible: smoothCheck.checked
            UM.Label { text: "Iterations" }
            UM.Slider {
                id: smoothSlider
                width: UM.Theme.getSize("setting_control").width
                from: 1; to: 50
                value: UM.ActiveTool.properties.getValue("SmoothIterations")
                onPressedChanged: if (!pressed) UM.ActiveTool.setProperty("SmoothIterations", Math.round(value))
            }
            UM.Label { text: Math.round(smoothSlider.value) }
        }

        UM.CheckBox {
            id: cleanupCheck
            text: "Remove small parts"
            checked: UM.ActiveTool.properties.getValue("DoRemoveSmall")
            onClicked: UM.ActiveTool.setProperty("DoRemoveSmall", checked)
        }
        UM.CheckBox {
            visible: cleanupCheck.checked
            text: "Keep largest only"
            checked: UM.ActiveTool.properties.getValue("KeepLargestOnly")
            onClicked: UM.ActiveTool.setProperty("KeepLargestOnly", checked)
        }

        UM.Label {
            text: UM.ActiveTool.properties.getValue("StatsText")
            visible: text.length > 0
        }

        Row {
            spacing: UM.Theme.getSize("default_margin").width
            Cura.SecondaryButton {
                text: "Preview"
                enabled: base.selectionValid && !base.busy
                onClicked: UM.ActiveTool.triggerAction("preview")
            }
            Cura.PrimaryButton {
                text: "Apply"
                enabled: base.hasPreview && !base.busy
                onClicked: UM.ActiveTool.triggerAction("apply")
            }
            Cura.SecondaryButton {
                text: "Reset"
                enabled: base.hasPreview && !base.busy
                onClicked: UM.ActiveTool.triggerAction("reset")
            }
        }
    }
}
```

- [ ] **Step 2: Create `qml/ObjectTweaker.qml`** identical to `qt6/ObjectTweaker.qml` except change the single line `import UM 1.6 as UM` to `import UM 1.5 as UM`. Copy the file, then edit only that line.

- [ ] **Step 3: Verify the two files differ only on the UM import line**

Run: `diff qml/ObjectTweaker.qml qt6/ObjectTweaker.qml`
Expected: exactly one differing line — `import UM 1.5 as UM` vs `import UM 1.6 as UM`.

- [ ] **Step 4: Commit**

```bash
git add qml/ObjectTweaker.qml qt6/ObjectTweaker.qml
git commit -m "feat: add Simplify tool panel (qml + qt6)"
```

---

### Task 9: Bundle/build scripts, CI, and docs

**Files:**
- Create: `scripts/bundle_deps.py`
- Create: `scripts/build_curapackage.py`
- Create: `requirements-bundle.txt`
- Create: `.github/workflows/tests.yml`
- Create: `README.md`
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: `plugin.json` (version/sdk), `core/` (tested by CI).
- Produces: a vendored `lib/`, a `dist/ObjectTweaker-<version>.curapackage`, and a green CI run.

- [ ] **Step 1: Create `requirements-bundle.txt`**

```text
trimesh>=4.0
fast-simplification
```

- [ ] **Step 2: Create `scripts/bundle_deps.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Vendor non-Cura runtime deps into lib/ (trimesh, fast-simplification).

numpy/scipy are intentionally NOT bundled — they come from Cura, so bundling
them would risk ABI mismatches across Cura updates.
"""
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIB = os.path.join(_ROOT, "lib")
_REQ = os.path.join(_ROOT, "requirements-bundle.txt")


def main() -> None:
    os.makedirs(_LIB, exist_ok=True)
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "-r", _REQ, "--target", _LIB, "--upgrade",
    ])
    print(f"Bundled deps into {_LIB}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `scripts/build_curapackage.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Build dist/ObjectTweaker-<version>.curapackage from plugin.json.

A .curapackage is a zip with an OPC-style layout. Runtime files only — no
tests/docs/scripts.
"""
import json
import os
import zipfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUNTIME = ["__init__.py", "ObjectTweaker.py", "plugin.json", "icon.svg", "qml", "qt6", "core", "lib"]


def _iter_files():
    for entry in _RUNTIME:
        path = os.path.join(_ROOT, entry)
        if os.path.isfile(path):
            yield path
        elif os.path.isdir(path):
            for base, _dirs, files in os.walk(path):
                if "__pycache__" in base:
                    continue
                for f in files:
                    if f.endswith((".pyc", ".pyo")):
                        continue
                    yield os.path.join(base, f)


def main() -> None:
    with open(os.path.join(_ROOT, "plugin.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    version = meta["version"]
    sdk = meta["supported_sdk_versions"][-1]
    dist = os.path.join(_ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, f"ObjectTweaker-{version}.curapackage")

    package_json = {
        "package_id": "ObjectTweaker",
        "package_type": "plugin",
        "display_name": meta["name"],
        "package_version": version,
        "sdk_version": sdk,
        "website": "https://github.com/emanuellonnberg/ObjectTweaker",
        "author": {"author_id": "emanuellonnberg", "display_name": meta["author"]},
        "description": meta["description"],
    }

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml",
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="json" ContentType="application/json"/>'
                    '<Default Extension="py" ContentType="text/x-python"/>'
                    '<Default Extension="qml" ContentType="text/plain"/>'
                    '<Default Extension="svg" ContentType="image/svg+xml"/>'
                    '</Types>')
        zf.writestr("package.json", json.dumps(package_json, indent=2))
        prefix = "files/plugins/ObjectTweaker/"
        for path in _iter_files():
            zf.write(path, prefix + os.path.relpath(path, _ROOT).replace(os.sep, "/"))
    print(f"Built {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create `.github/workflows/tests.yml`**

```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest]
        python-version: ["3.10", "3.11", "3.12"]
        include:
          - os: windows-latest
            python-version: "3.12"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements-test.txt
      - run: pytest -v
```

- [ ] **Step 5: Create `README.md`**

```markdown
# Object Tweaker

A Cura plugin that modifies the selected model in place. MVP feature
**Simplify**: decimate (reduce triangles), smooth the surface, and remove
small disconnected parts. Sibling to
[ObjectSplitter](https://github.com/emanuellonnberg/ObjectSplitter).

## Usage

Select a model, open the Object Tweaker tool, enable the operations you want,
click **Preview**, then **Apply** (or **Reset**). Apply is undoable.

## Development

```bash
pip install -r requirements-test.txt
pytest -v
python scripts/bundle_deps.py        # vendor trimesh + fast-simplification into lib/
python scripts/build_curapackage.py  # -> dist/ObjectTweaker-<version>.curapackage
```

All mesh logic lives in `core/` (pure Python, no Cura). `ObjectTweaker.py` is
the Cura adapter. See `docs/superpowers/` for the design spec and plan.
```

- [ ] **Step 6: Create `CLAUDE.md`**

```markdown
# ObjectTweaker - Claude Code Project Guide

Cura plugin that edits the selected model in place. Logic in `core/` (pure
Python, no Cura), wired to Cura by `ObjectTweaker.py`.

## Architecture
- `core/mesh_io.py`   MeshData<->trimesh array conversion (only conversion boundary)
- `core/decimate.py`  quadric decimation (needs fast-simplification)
- `core/smooth.py`    Taubin/Laplacian smoothing
- `core/cleanup.py`   remove small disconnected shells
- `core/pipeline.py`  run enabled ops (remove-small -> decimate -> smooth) + stats
- `ObjectTweaker.py`  Cura Tool: selection, preview thread, apply (undoable), reset
- `qml/` (UM 1.5) + `qt6/` (UM 1.6)  panels, keep in sync (only the import line differs)

## Tests
`pytest -v` — core/ only, no Cura needed. CI: py3.10-3.12 Linux + py3.12 Windows.

## Gotchas (inherited from ObjectSplitter)
- No triangulation engine in Cura. The three ops never generate new faces, so
  this is a non-issue — do NOT add capping/triangulate_polygon.
- Bundle only non-Cura deps (trimesh, fast-simplification). numpy/scipy come
  from Cura.
- QML-exposed property = instance var + entry in setExposedProperties() +
  getX/setX (setter guards `if value != old`, emits propertyChanged) + control
  in BOTH qml/ and qt6/.

## Build
`python scripts/bundle_deps.py` then `python scripts/build_curapackage.py`.
```

- [ ] **Step 7: Run the full suite once more**

Run: `pytest -v`
Expected: PASS (all core tests green).

- [ ] **Step 8: Commit**

```bash
git add scripts/bundle_deps.py scripts/build_curapackage.py requirements-bundle.txt .github/workflows/tests.yml README.md CLAUDE.md
git commit -m "build: add bundle/package scripts, CI, and docs"
```

---

## Self-Review Notes

- **Spec coverage:** §2 layout → Task 1+files; §3.1 decimate → Task 4; §3.2 smooth → Task 5; §3.3 remove-small → Task 3; §3.4 pipeline+stats → Task 6; §4 preview/apply/reset+undo → Task 7; §5 UI → Task 8; §6 deps → Tasks 1/9; §7 testing → Tasks 2–6 + CI Task 9. All covered.
- **Triangulation constraint:** honored — no op caps or triangulates.
- **Type consistency:** `SimplifyOptions`/`SimplifyResult` field names match between Task 6 definition and Task 7 usage (`do_remove_small`, `min_pct`, `keep_largest_only`, `do_decimate`, `decimate_percent`, `do_smooth`, `smooth_iterations`, `smooth_method`; result `mesh`/`tris_before`/`tris_after`/`parts_removed`). `decimate(percent=...)` expects a 0–1 fraction; adapter converts UI percent /100 in `_currentOptions`. `remove_small_parts(min_pct=...)` expects a 0–100 percent; adapter passes `self._min_pct` directly (also 0–100). Consistent.
- **Known follow-up:** `core/` has no test for the `__init__.py` lib injection (it imports Cura); acceptable — verified manually in Cura per Task 7.
```