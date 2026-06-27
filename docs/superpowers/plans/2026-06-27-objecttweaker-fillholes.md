# Fill Holes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Fill Holes feature to the ObjectTweaker Cura tool that caps every open boundary loop of the selected model, behind a Simplify | Fill Holes feature selector.

**Architecture:** Two new pure-Python `core/` modules — `cap.py` (single-loop ear-clip capping, ported from ObjectSplitter) and `fillholes.py` (enumerate boundary loops via `mesh.outline()`, cap each, stitch). The `ObjectTweaker.py` adapter gains a `Feature` property and a `_computeForFeature` dispatcher; the existing Preview/Apply/Reset flow is reused unchanged. The QML panel gains a feature ComboBox that shows the matching control group.

**Tech Stack:** Python 3.10–3.12, trimesh 4.x, numpy (from Cura), pytest, Cura/Uranium SDK, QML.

## Global Constraints

- `core/` modules MUST NOT import any `UM.*` or `cura.*` symbol.
- Imports inside the plugin are RELATIVE: `from .core.fillholes import ...` in `ObjectTweaker.py`, `from .cap import ...` between `core/` modules. Test files use top-level `from core.X import ...`.
- No triangulation engine (`mapbox_earcut`/`triangle`) and **no scipy** — capping is pure-Python ear-clipping. No new bundled dependencies.
- QML uses plain `QtQuick.Controls` types only (no `UM.*` control types). Buttons dispatch via the existing `TriggerPreview`/`TriggerApply`/`TriggerReset` write-only properties.
- Dual QML: `qml/ObjectTweaker.qml` and `qt6/ObjectTweaker.qml` stay identical except the `import UM` version line.
- Every `.py` file starts with the 2-line LGPLv3 header. Style: PEP 8, type hints, Google-style docstrings.
- Commit after every task's tests pass. Run tests with `./.venv/Scripts/python.exe -m pytest`.

---

### Task 1: `core/cap.py` — single-loop ear-clip capping

**Files:**
- Create: `core/cap.py`
- Test: `tests/test_cap.py`

**Interfaces:**
- Consumes: a 3D boundary loop as an `(N,3)` ndarray.
- Produces: `cap_loop(loop_3d: numpy.ndarray) -> Optional[trimesh.Trimesh]` — a triangulated cap mesh for one loop, or `None` if the loop is degenerate/uncappable. Internal helpers: `_signed_area_2d`, `_point_in_triangle_2d`, `_earclip`, `_sanitize_loop`, `_fit_plane`, `_fan`.

- [ ] **Step 1: Write the failing test `tests/test_cap.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy

from core.cap import cap_loop


def test_square_loop_caps_with_two_triangles():
    loop = numpy.array([[0, 0, 5], [1, 0, 5], [1, 1, 5], [0, 1, 5]], dtype=float)
    cap = cap_loop(loop)
    assert cap is not None
    assert len(cap.faces) == 2          # n - 2 for n=4
    assert abs(cap.area - 1.0) < 1e-6   # covers exactly the unit square


def test_concave_L_loop_triangulates_to_n_minus_2_and_covers_area():
    loop = numpy.array([
        [0, 0, 5], [2, 0, 5], [2, 1, 5],
        [1, 1, 5], [1, 2, 5], [0, 2, 5],
    ], dtype=float)
    cap = cap_loop(loop)
    assert cap is not None
    assert len(cap.faces) == 4          # n - 2 for n=6
    assert abs(cap.area - 3.0) < 1e-6   # L area = 2*2 - 1*1


def test_degenerate_collinear_loop_returns_none():
    loop = numpy.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    assert cap_loop(loop) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.cap'`.

- [ ] **Step 3: Write `core/cap.py`**

```python
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
    """Strict point-in-triangle test in 2D (excludes edges)."""
    v0 = c - a
    v1 = b - a
    v2 = p - a
    den = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(den) <= eps:
        return False
    u = (v2[0] * v1[1] - v1[0] * v2[1]) / den
    v = (v0[0] * v2[1] - v2[0] * v0[1]) / den
    w = 1.0 - u - v
    return (u > eps) and (v > eps) and (w > eps)


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cap.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/cap.py tests/test_cap.py
git commit -m "feat: add ear-clip boundary-loop capping (core/cap.py)"
```

---

### Task 2: `core/fillholes.py` — detect + fill all holes

**Files:**
- Create: `core/fillholes.py`
- Test: `tests/test_fillholes.py`

**Interfaces:**
- Consumes: `core.cap.cap_loop`, a `trimesh.Trimesh`.
- Produces: `fill_holes(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, int]` returning `(filled_mesh, holes_filled)`. `holes_filled` is the number of boundary loops successfully capped. Internal helper `_boundary_loops(mesh) -> list[numpy.ndarray]`.

- [ ] **Step 1: Write the failing test `tests/test_fillholes.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.fillholes import fill_holes


def _box_missing_top():
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    zc = box.triangles_center[:, 2]
    keep = zc < (zc.max() - 1e-6)        # drop the 2 top triangles
    box.update_faces(keep)
    box.remove_unreferenced_vertices()
    return box


def _open_tube():
    cyl = trimesh.creation.cylinder(radius=1.0, height=3.0, sections=24)
    nz = numpy.abs(cyl.face_normals[:, 2])
    keep = nz < 0.5                       # drop both end caps, keep side wall
    cyl.update_faces(keep)
    cyl.remove_unreferenced_vertices()
    return cyl


def test_fills_single_hole_and_is_watertight():
    mesh, filled = fill_holes(_box_missing_top())
    assert filled == 1
    assert mesh.is_watertight


def test_fills_both_ends_of_open_tube():
    mesh, filled = fill_holes(_open_tube())
    assert filled == 2


def test_closed_mesh_unchanged():
    sphere = trimesh.creation.icosphere(subdivisions=3)
    mesh, filled = fill_holes(sphere)
    assert filled == 0
    assert len(mesh.faces) == len(sphere.faces)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_fillholes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.fillholes'`.

- [ ] **Step 3: Write `core/fillholes.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Detect every open boundary loop of a mesh and cap them watertight."""
from typing import List, Tuple

import numpy
import trimesh

from .cap import cap_loop


def _boundary_loops(mesh: trimesh.Trimesh) -> List[numpy.ndarray]:
    """Return open boundary loops as a list of (N,3) polylines.

    Uses trimesh's ``outline()`` (the set of edges belonging to a single face).
    A watertight mesh has no outline; failures are treated as no loops.
    """
    try:
        outline = mesh.outline()
    except Exception:
        return []
    if outline is None or not hasattr(outline, "discrete"):
        return []
    loops = outline.discrete
    if loops is None:
        return []
    return [numpy.asarray(loop, dtype=numpy.float64) for loop in loops]


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_fillholes.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full core suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (Simplify's 13 + cap's 3 + fillholes' 3 = 19).

- [ ] **Step 6: Commit**

```bash
git add core/fillholes.py tests/test_fillholes.py
git commit -m "feat: add fill_holes (detect + cap all boundary loops)"
```

---

### Task 3: Adapter — `Feature` property + `_computeForFeature` dispatcher

**Files:**
- Modify: `ObjectTweaker.py`

**Interfaces:**
- Consumes: `core.fillholes.fill_holes`, the existing `core.pipeline.run` / `SimplifyOptions`.
- Produces: a `Feature` exposed property (`"simplify"` | `"fillholes"`) and a `_computeForFeature(mesh) -> tuple[trimesh.Trimesh, str]` dispatcher used by `_previewWorker`.

> **Verification note:** Cura runtime types — not pytest-testable. Verify by `py_compile` here and via the Manual Cura Checklist in Task 4.

- [ ] **Step 1: Add the fillholes import.** In `ObjectTweaker.py`, immediately after the line `from .core.pipeline import SimplifyOptions, run`, add:

```python
from .core.fillholes import fill_holes
```

- [ ] **Step 2: Add the `_feature` instance var.** In `ObjectTweaker.__init__`, immediately after the line `self._smooth_iterations = 10`, add:

```python
        self._feature = "simplify"   # "simplify" | "fillholes"
```

- [ ] **Step 3: Expose the `Feature` property.** In the `setExposedProperties(...)` call, change the first argument line so the list begins with `"Feature"`. Replace:

```python
        self.setExposedProperties(
            "DoRemoveSmall", "MinPct", "KeepLargestOnly",
```

with:

```python
        self.setExposedProperties(
            "Feature",
            "DoRemoveSmall", "MinPct", "KeepLargestOnly",
```

- [ ] **Step 4: Add the getter/setter.** Immediately before the line `def getDoRemoveSmall(self) -> bool:`, add:

```python
    def getFeature(self) -> str:
        return self._feature

    def setFeature(self, value: str) -> None:
        if value != self._feature:
            self._feature = value
            self.propertyChanged.emit()

```

- [ ] **Step 5: Add the dispatcher.** Immediately before the line `def preview(self) -> None:`, add:

```python
    def _computeForFeature(self, mesh):
        """Run the active feature; return (result_mesh, stats_text)."""
        if self._feature == "fillholes":
            filled, n = fill_holes(mesh)
            return filled, f"holes filled: {n}"
        result = run(mesh, self._currentOptions())
        extra = f", removed {result.parts_removed} part(s)" if result.parts_removed else ""
        return result.mesh, f"tris: {result.tris_before} -> {result.tris_after}{extra}"

```

- [ ] **Step 6: Route the preview worker through the dispatcher.** In `_previewWorker`, replace the `_compute` body:

```python
        def _compute() -> None:
            mesh = self._extractLocal(node)
            result_box["result"] = run(mesh, self._currentOptions())
```

with:

```python
        def _compute() -> None:
            mesh = self._extractLocal(node)
            result_box["result"] = self._computeForFeature(mesh)
```

- [ ] **Step 7: Consume the (mesh, stats) tuple in `_finish`.** In `_previewWorker._finish`, replace the `else` branch:

```python
            else:
                result = result_box["result"]
                self._preview_mesh = self._buildMeshData(result.mesh)
                node.setMeshData(self._preview_mesh)
                node.calculateBoundingBoxMesh()
                extra = f", removed {result.parts_removed} part(s)" if result.parts_removed else ""
                self._stats_text = f"tris: {result.tris_before} -> {result.tris_after}{extra}"
                self._has_preview = True
```

with:

```python
            else:
                result_mesh, stats_text = result_box["result"]
                self._preview_mesh = self._buildMeshData(result_mesh)
                node.setMeshData(self._preview_mesh)
                node.calculateBoundingBoxMesh()
                self._stats_text = stats_text
                self._has_preview = True
```

- [ ] **Step 8: Verify it compiles**

Run: `./.venv/Scripts/python.exe -m py_compile ObjectTweaker.py`
Expected: no output (success).

- [ ] **Step 9: Verify the full suite still passes** (core untouched, but confirm nothing broke)

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (19 passed).

- [ ] **Step 10: Commit**

```bash
git add ObjectTweaker.py
git commit -m "feat: add Feature selector + fill-holes compute dispatch to adapter"
```

---

### Task 4: QML feature selector + Fill Holes group + docs

**Files:**
- Modify: `qml/ObjectTweaker.qml`
- Modify: `qt6/ObjectTweaker.qml`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the `Feature` property and existing trigger properties from Task 3.
- Produces: the multi-feature panel.

> **Verification note:** QML verified in Cura (Manual Cura Checklist below). The dual-file identity is the testable invariant.

- [ ] **Step 1: Edit `qt6/ObjectTweaker.qml`.** Replace the entire `Column { ... }` block (from `Column {` through its closing `}`) with the following. The feature ComboBox drives `Feature`; Simplify and Fill Holes groups toggle on it; the stats label and button row are shared.

```qml
    // Active feature ("simplify" | "fillholes").
    property string feature: base.val("Feature", "simplify")

    Column {
        id: items
        spacing: UM.Theme.getSize("default_margin").height

        ComboBox {
            id: featureCombo
            width: UM.Theme.getSize("setting_control").width
            model: ["Simplify", "Fill Holes"]
            currentIndex: base.feature === "fillholes" ? 1 : 0
            onActivated: if (UM.ActiveTool) UM.ActiveTool.setProperty("Feature", currentIndex === 1 ? "fillholes" : "simplify")
        }

        // ---- Simplify ----
        Column {
            visible: base.feature === "simplify"
            spacing: UM.Theme.getSize("default_margin").height

            CheckBox {
                id: decimateCheck
                text: "Decimate (reduce triangles)"
                checked: base.val("DoDecimate", true)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("DoDecimate", checked)
            }
            RowLayout {
                visible: decimateCheck.checked
                spacing: UM.Theme.getSize("default_margin").width
                Label {
                    text: "Keep " + Math.round(decimateSlider.value) + "%"
                    verticalAlignment: Text.AlignVCenter
                }
                Slider {
                    id: decimateSlider
                    from: 1; to: 100; stepSize: 1
                    value: base.val("DecimatePercent", 50)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("DecimatePercent", value)
                }
            }

            CheckBox {
                id: smoothCheck
                text: "Smooth surface"
                checked: base.val("DoSmooth", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("DoSmooth", checked)
            }
            RowLayout {
                visible: smoothCheck.checked
                spacing: UM.Theme.getSize("default_margin").width
                Label {
                    text: "Iterations " + Math.round(smoothSlider.value)
                    verticalAlignment: Text.AlignVCenter
                }
                Slider {
                    id: smoothSlider
                    from: 1; to: 50; stepSize: 1
                    value: base.val("SmoothIterations", 10)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("SmoothIterations", Math.round(value))
                }
            }

            CheckBox {
                id: cleanupCheck
                text: "Remove small parts"
                checked: base.val("DoRemoveSmall", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("DoRemoveSmall", checked)
            }
            CheckBox {
                visible: cleanupCheck.checked
                text: "Keep largest only"
                checked: base.val("KeepLargestOnly", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("KeepLargestOnly", checked)
            }
        }

        // ---- Fill Holes ----
        Column {
            visible: base.feature === "fillholes"
            spacing: UM.Theme.getSize("default_margin").height

            Label {
                text: "Caps all open boundary loops to make the model watertight."
                wrapMode: Text.WordWrap
                width: UM.Theme.getSize("setting_control").width
            }
        }

        // ---- Shared: stats + actions ----
        Label {
            text: base.val("StatsText", "")
            visible: text.length > 0
            wrapMode: Text.WordWrap
        }

        RowLayout {
            width: parent.width
            spacing: UM.Theme.getSize("default_margin").width

            Button {
                text: "Preview"
                enabled: base.val("SelectionValid", false) && !base.val("Busy", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("TriggerPreview", true)
            }
            Button {
                text: "Apply"
                enabled: base.val("HasPreview", false) && !base.val("Busy", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("TriggerApply", true)
            }
            Button {
                text: "Reset"
                enabled: base.val("HasPreview", false) && !base.val("Busy", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("TriggerReset", true)
            }
        }
    }
```

- [ ] **Step 2: Copy `qt6/ObjectTweaker.qml` to `qml/ObjectTweaker.qml`, changing only the UM import.** Make `qml/ObjectTweaker.qml` byte-identical to `qt6/ObjectTweaker.qml`. (Both currently import `UM 1.5`; if you keep them identical, the diff in Step 3 is empty — that is acceptable. If you differentiate, the only allowed difference is the `import UM` version line.)

- [ ] **Step 3: Verify the two QML files differ only on the UM import line (or are identical)**

Run: `diff qml/ObjectTweaker.qml qt6/ObjectTweaker.qml`
Expected: no output, or exactly the one `import UM` line differing.

- [ ] **Step 4: Check brace balance of both QML files**

Run: `for f in qml/ObjectTweaker.qml qt6/ObjectTweaker.qml; do echo "$f open=$(tr -cd '{' < "$f" | wc -c) close=$(tr -cd '}' < "$f" | wc -c)"; done`
Expected: each file reports equal open/close counts.

- [ ] **Step 5: Update `CLAUDE.md`.** Replace the architecture bullet line:

```markdown
- `core/cleanup.py`   remove small disconnected shells (bbox-volume metric)
```

with:

```markdown
- `core/cleanup.py`   remove small disconnected shells (bbox-volume metric)
- `core/cap.py`       ear-clip cap of one boundary loop (pure-Python, no engine)
- `core/fillholes.py` detect open loops via outline() + cap all (watertight)
```

And replace the line:

```markdown
- `ObjectTweaker.py`  Cura Tool: selection, preview thread, apply (undoable), reset
```

with:

```markdown
- `ObjectTweaker.py`  Cura Tool: Feature selector (Simplify|Fill Holes), selection, preview thread, apply (undoable), reset
```

- [ ] **Step 6: Manual Cura Checklist** (build/junction already in place; fully restart Cura 5.13)

1. Select a model → Object Tweaker panel shows a **Simplify / Fill Holes** dropdown at the top; Simplify controls below it.
2. Switch dropdown to **Fill Holes** → Simplify controls hide, description line shows.
3. Use a model with a hole (or delete faces) → **Preview** → stat reads `holes filled: N`, the opening visibly closes.
4. **Apply** → stays closed; Ctrl+Z restores the hole (undo works).
5. Switch back to **Simplify**, Preview/Apply a decimate → still works (no regression).
6. Check `cura.log` for no `__onQmlWarning` / tracebacks mentioning ObjectTweaker.

- [ ] **Step 7: Run the full suite once more**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (19 passed).

- [ ] **Step 8: Commit**

```bash
git add qml/ObjectTweaker.qml qt6/ObjectTweaker.qml CLAUDE.md
git commit -m "feat: add feature selector + Fill Holes panel (qml + qt6)"
```

---

## Self-Review Notes

- **Spec coverage:** §2.1 feature selector → Task 3 (adapter) + Task 4 (QML); §2.2/§3 core cap + fillholes → Tasks 1–2; §4 adapter dispatch → Task 3; §5 UI → Task 4; §6 no new deps → honored (pure numpy/trimesh); §7 testing → Tasks 1–2 tests. All covered.
- **Placeholder scan:** none — every code step shows complete code; QML edits give full block.
- **Type consistency:** `cap_loop(loop_3d) -> Optional[Trimesh]` (Task 1) consumed by `fill_holes` (Task 2). `fill_holes(mesh) -> (Trimesh, int)` (Task 2) consumed by `_computeForFeature` (Task 3), which returns `(mesh, str)` consumed by `_previewWorker._finish` (Task 3 Step 7). `Feature` values `"simplify"`/`"fillholes"` consistent across adapter (Task 3) and QML (Task 4). Trigger properties reused from the merged Simplify work.
- **Engine/deps:** no scipy, no earcut/triangle — ear-clipping only. No new bundled deps.
```