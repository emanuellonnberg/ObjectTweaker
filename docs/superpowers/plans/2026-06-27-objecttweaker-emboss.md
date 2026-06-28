# Emboss / Engrave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Emboss feature to the ObjectTweaker Cura tool: click a point on the model, pick a 2D shape (circle/rectangle/star), and raise it out of (emboss) or cut it into (engrave) the surface by a depth, via a boolean stamp.

**Architecture:** Two new pure-Python `core/` modules — `stamp.py` (shape outlines + extruded prism, reusing `core.cap._earclip`) and `emboss.py` (nearest-face normal, prism orientation, boolean union/difference via manifold3d). The `ObjectTweaker.py` adapter adds the `emboss` feature, stamp parameters, and mouse-pick handling (`event()` + `PickingPass`). The QML panel gains an Emboss control group.

**Tech Stack:** Python 3.10–3.12, trimesh 4.x, numpy, manifold3d (boolean engine, newly bundled), pytest, Cura/Uranium SDK, QML.

## Global Constraints

- `core/` modules MUST NOT import any `UM.*` or `cura.*` symbol.
- Imports inside the plugin are RELATIVE (`from .core.emboss import ...` in the adapter, `from .cap import ...` between `core/` modules). Test files use top-level `from core.X import ...`.
- No triangulation engine (`mapbox_earcut`/`triangle`), no scipy, **no rtree** — the surface normal is computed by a pure-numpy nearest-face helper, not `mesh.nearest.on_surface` (which needs rtree).
- New bundled dep: **manifold3d**, Python-3.12 wheel (matches Cura 5.13). Bundle only non-Cura deps.
- QML uses plain `QtQuick.Controls` types only (no `UM.*` control types). Buttons use the existing `TriggerPreview`/`TriggerApply`/`TriggerReset` write-only properties.
- Dual QML: `qml/ObjectTweaker.qml` and `qt6/ObjectTweaker.qml` stay identical except the `import UM` version line.
- Every `.py` file starts with the 2-line LGPLv3 header. PEP 8, type hints, Google-style docstrings.
- Commit after every task's tests pass. Tests run with `./.venv/Scripts/python.exe -m pytest`.

---

### Task 1: `core/stamp.py` — shape outlines + extruded prism

**Files:**
- Create: `core/stamp.py`
- Test: `tests/test_stamp.py`

**Interfaces:**
- Consumes: `core.cap._earclip`.
- Produces:
  - `shape_outline(kind: str, params: dict) -> numpy.ndarray` — `(N,2)` CCW outline centered at origin. `kind` in `"circle"|"rectangle"|"star"`.
  - `make_prism(outline_2d: numpy.ndarray, height: float) -> trimesh.Trimesh` — watertight prism, base at `z=0`, top at `z=height`.

- [ ] **Step 1: Write the failing test `tests/test_stamp.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy

from core.stamp import shape_outline, make_prism


def test_circle_outline_has_48_points_on_radius():
    out = shape_outline("circle", {"diameter": 4.0})
    assert out.shape == (48, 2)
    radii = numpy.linalg.norm(out, axis=1)
    assert numpy.allclose(radii, 2.0, atol=1e-6)


def test_star_outline_has_two_points_per_tip():
    out = shape_outline("star", {"diameter": 4.0, "points": 5})
    assert out.shape == (10, 2)


def test_rectangle_outline_has_four_corners():
    out = shape_outline("rectangle", {"width": 6.0, "height": 2.0})
    assert out.shape == (4, 2)
    assert abs(out[:, 0].max() - 3.0) < 1e-6
    assert abs(out[:, 1].max() - 1.0) < 1e-6


def test_make_prism_is_watertight_with_expected_height():
    square = numpy.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], dtype=float)
    prism = make_prism(square, height=3.0)
    assert prism.is_watertight
    assert abs(prism.bounds[1][2] - prism.bounds[0][2] - 3.0) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_stamp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.stamp'`.

- [ ] **Step 3: Write `core/stamp.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_stamp.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add core/stamp.py tests/test_stamp.py
git commit -m "feat: add shape outlines + extruded prism (core/stamp.py)"
```

---

### Task 2: `core/emboss.py` — nearest-face normal + boolean stamp

**Files:**
- Create: `core/emboss.py`
- Modify: `requirements-test.txt`
- Test: `tests/test_emboss.py`

**Interfaces:**
- Consumes: `core.stamp.make_prism`, `core.stamp.shape_outline` (tests), trimesh boolean (manifold3d).
- Produces:
  - `nearest_face_normal(mesh: trimesh.Trimesh, point) -> numpy.ndarray` — unit-ish normal of the face whose centroid is closest to `point`.
  - `emboss(mesh, point, normal, outline_2d, depth, mode) -> tuple[trimesh.Trimesh, bool]` — `mode` in `"emboss"|"engrave"`; returns `(result, ok)`. On failure returns `(mesh, False)` unchanged.

- [ ] **Step 1: Add manifold3d to `requirements-test.txt`.** Append the line:

```text
manifold3d
```

- [ ] **Step 2: Write the failing test `tests/test_emboss.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.stamp import shape_outline
from core.emboss import emboss, nearest_face_normal


def test_nearest_face_normal_top_of_box():
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    n = nearest_face_normal(box, [0.0, 0.0, 5.0])
    assert numpy.allclose(numpy.abs(n), [0.0, 0.0, 1.0], atol=1e-6)


def test_emboss_circle_on_box_increases_volume():
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    out = shape_outline("circle", {"diameter": 3.0})
    res, ok = emboss(box, [0.0, 0.0, 5.0], [0.0, 0.0, 1.0], out, depth=1.0, mode="emboss")
    assert ok is True
    assert res.is_watertight
    assert res.volume > box.volume


def test_engrave_circle_on_box_decreases_volume():
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    out = shape_outline("circle", {"diameter": 3.0})
    res, ok = emboss(box, [0.0, 0.0, 5.0], [0.0, 0.0, 1.0], out, depth=1.0, mode="engrave")
    assert ok is True
    assert res.volume < box.volume


def test_degenerate_normal_returns_unchanged():
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    out = shape_outline("circle", {"diameter": 3.0})
    res, ok = emboss(box, [0.0, 0.0, 5.0], [0.0, 0.0, 0.0], out, depth=1.0, mode="emboss")
    assert ok is False
    assert res is box
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_emboss.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.emboss'`.

- [ ] **Step 4: Write `core/emboss.py`**

```python
# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Emboss/engrave a shape onto a mesh by booleaning an extruded prism."""
from typing import Tuple

import numpy
import trimesh

from .stamp import make_prism

_EMBED = 0.5                       # mm the prism sinks past the surface
_ENGINES = ["manifold", "blender", None]


def nearest_face_normal(mesh: trimesh.Trimesh, point) -> numpy.ndarray:
    """Normal of the face whose centroid is nearest ``point``.

    Centroid-nearest (no rtree). The click point lies on the surface, so the
    nearest face's normal is the local surface orientation.
    """
    point = numpy.asarray(point, dtype=float)
    centroids = mesh.triangles_center
    idx = int(numpy.argmin(numpy.linalg.norm(centroids - point, axis=1)))
    return numpy.asarray(mesh.face_normals[idx], dtype=float)


def _try_boolean(op, a: trimesh.Trimesh, b: trimesh.Trimesh):
    for engine in _ENGINES:
        try:
            res = op([a, b], engine=engine) if engine else op([a, b])
            if res is not None and len(res.faces) > 0:
                return res
        except Exception:
            continue
    return None


def emboss(mesh, point, normal, outline_2d, depth, mode) -> Tuple[trimesh.Trimesh, bool]:
    """Raise (emboss) or cut (engrave) the outline at ``point``.

    Returns ``(result_mesh, ok)``; ``(mesh, False)`` unchanged on any failure.
    """
    normal = numpy.asarray(normal, dtype=float)
    nn = float(numpy.linalg.norm(normal))
    depth = float(depth)
    if nn < 1e-9 or depth <= 0.0:
        return mesh, False
    normal = normal / nn
    point = numpy.asarray(point, dtype=float)

    try:
        prism = make_prism(outline_2d, depth + 2.0 * _EMBED)
    except Exception:
        return mesh, False

    prism.apply_transform(trimesh.geometry.align_vectors([0.0, 0.0, 1.0], normal))

    prepared = mesh.copy()
    prepared.merge_vertices()

    if mode == "engrave":
        prism.apply_translation(point - normal * (depth + _EMBED))
        result = _try_boolean(trimesh.boolean.difference, prepared, prism)
    else:
        prism.apply_translation(point - normal * _EMBED)
        result = _try_boolean(trimesh.boolean.union, prepared, prism)

    if result is None or len(result.faces) == 0:
        return mesh, False
    return result, True
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_emboss.py -v`
Expected: PASS (4 passed). If it errors with a missing boolean engine, run `./.venv/Scripts/python.exe -m pip install manifold3d`.

- [ ] **Step 6: Run the full core suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (19 prior + stamp 4 + emboss 4 = 27).

- [ ] **Step 7: Commit**

```bash
git add core/emboss.py tests/test_emboss.py requirements-test.txt
git commit -m "feat: add emboss/engrave boolean stamp (core/emboss.py)"
```

---

### Task 3: Adapter — emboss feature, params, and mouse picking

**Files:**
- Modify: `ObjectTweaker.py`

**Interfaces:**
- Consumes: `core.stamp.shape_outline`, `core.emboss.emboss`, `core.emboss.nearest_face_normal`; Cura `Event`, `MouseEvent`, `PickingPass`.
- Produces: feature `"emboss"`, exposed stamp props (`Shape`, `Diameter`, `RectWidth`, `RectHeight`, `StarPoints`, `StarInnerRatio`, `Rotation`, `Depth`, `EmbossMode`), and an `event()` that records the local pick point.

> **Verification note:** Cura runtime — verify with `py_compile` here and the Manual Cura Checklist in Task 4.

- [ ] **Step 1: Add imports.** After the line `from cura.Scene.CuraSceneNode import CuraSceneNode`, add:

```python
from UM.Event import Event, MouseEvent
from cura.PickingPass import PickingPass
```

And after `from .core.fillholes import fill_holes`, add:

```python
from .core.stamp import shape_outline
from .core.emboss import emboss, nearest_face_normal
```

- [ ] **Step 2: Add instance state + controller.** In `__init__`, immediately after the line `self._feature = "simplify"   # "simplify" | "fillholes"`, add:

```python
        self._shape = "circle"           # "circle" | "rectangle" | "star"
        self._diameter = 10.0
        self._rect_width = 10.0
        self._rect_height = 10.0
        self._star_points = 5
        self._star_inner_ratio = 0.5
        self._rotation = 0.0
        self._depth = 1.0
        self._emboss_mode = "emboss"     # "emboss" | "engrave"
        self._pick_point = None
        self._has_pick = False
        self._controller = self.getController()
```

- [ ] **Step 3: Expose the new properties.** Replace the line:

```python
            "Feature",
```

with:

```python
            "Feature",
            "Shape", "Diameter", "RectWidth", "RectHeight",
            "StarPoints", "StarInnerRatio", "Rotation", "Depth", "EmbossMode",
```

- [ ] **Step 4: Clear the pick when feature changes.** Replace the existing `setFeature`:

```python
    def setFeature(self, value: str) -> None:
        if value != self._feature:
            self._feature = value
            self.propertyChanged.emit()
```

with:

```python
    def setFeature(self, value: str) -> None:
        if value != self._feature:
            self._feature = value
            self._has_pick = False
            self._pick_point = None
            self.propertyChanged.emit()
```

- [ ] **Step 5: Clear the pick when selection changes.** In `_onSelectionChanged`, immediately after the line `self._revertPreview()`, add:

```python
        self._has_pick = False
        self._pick_point = None
```

- [ ] **Step 6: Add the stamp getters/setters.** Immediately before the line `def getDoRemoveSmall(self) -> bool:`, add:

```python
    def getShape(self) -> str:
        return self._shape

    def setShape(self, value: str) -> None:
        if value != self._shape:
            self._shape = value
            self.propertyChanged.emit()

    def getDiameter(self) -> float:
        return self._diameter

    def setDiameter(self, value: float) -> None:
        value = float(value)
        if value != self._diameter:
            self._diameter = value
            self.propertyChanged.emit()

    def getRectWidth(self) -> float:
        return self._rect_width

    def setRectWidth(self, value: float) -> None:
        value = float(value)
        if value != self._rect_width:
            self._rect_width = value
            self.propertyChanged.emit()

    def getRectHeight(self) -> float:
        return self._rect_height

    def setRectHeight(self, value: float) -> None:
        value = float(value)
        if value != self._rect_height:
            self._rect_height = value
            self.propertyChanged.emit()

    def getStarPoints(self) -> int:
        return self._star_points

    def setStarPoints(self, value: int) -> None:
        value = int(value)
        if value != self._star_points:
            self._star_points = value
            self.propertyChanged.emit()

    def getStarInnerRatio(self) -> float:
        return self._star_inner_ratio

    def setStarInnerRatio(self, value: float) -> None:
        value = float(value)
        if value != self._star_inner_ratio:
            self._star_inner_ratio = value
            self.propertyChanged.emit()

    def getRotation(self) -> float:
        return self._rotation

    def setRotation(self, value: float) -> None:
        value = float(value)
        if value != self._rotation:
            self._rotation = value
            self.propertyChanged.emit()

    def getDepth(self) -> float:
        return self._depth

    def setDepth(self, value: float) -> None:
        value = float(value)
        if value != self._depth:
            self._depth = value
            self.propertyChanged.emit()

    def getEmbossMode(self) -> str:
        return self._emboss_mode

    def setEmbossMode(self, value: str) -> None:
        if value != self._emboss_mode:
            self._emboss_mode = value
            self.propertyChanged.emit()

```

- [ ] **Step 7: Add `_shapeParams` + emboss branch to the dispatcher.** Replace the whole `_computeForFeature` method:

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

with:

```python
    def _shapeParams(self) -> dict:
        return {
            "diameter": self._diameter,
            "width": self._rect_width,
            "height": self._rect_height,
            "points": self._star_points,
            "inner_ratio": self._star_inner_ratio,
            "rotation": self._rotation,
        }

    def _computeForFeature(self, mesh):
        """Run the active feature; return (result_mesh, stats_text)."""
        if self._feature == "fillholes":
            filled, n = fill_holes(mesh)
            return filled, f"holes filled: {n}"
        if self._feature == "emboss":
            if not self._has_pick or self._pick_point is None:
                return mesh, "click the model to place"
            outline = shape_outline(self._shape, self._shapeParams())
            normal = nearest_face_normal(mesh, self._pick_point)
            res, ok = emboss(mesh, self._pick_point, normal, outline,
                             depth=self._depth, mode=self._emboss_mode)
            if not ok:
                return mesh, "boolean failed - try Fill Holes"
            return res, "engraved" if self._emboss_mode == "engrave" else "embossed"
        result = run(mesh, self._currentOptions())
        extra = f", removed {result.parts_removed} part(s)" if result.parts_removed else ""
        return result.mesh, f"tris: {result.tris_before} -> {result.tris_after}{extra}"
```

- [ ] **Step 8: Add the `event` handler.** Immediately before the line `def _computeForFeature(self, mesh):` (now after `_shapeParams`), add the mouse-pick handler:

```python
    def event(self, event) -> bool:
        result = super().event(event)
        if self._feature != "emboss":
            return result
        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons:
            node = self._selectedMeshNode()
            if node is None:
                return result
            camera = self._controller.getScene().getActiveCamera()
            if camera is None:
                return result
            picking_pass = PickingPass(camera.getViewportWidth(), camera.getViewportHeight())
            picking_pass.render()
            world = picking_pass.getPickedPosition(event.x, event.y)
            if world is None:
                return result
            matrix = numpy.asarray(node.getWorldTransformation().getData(), dtype=numpy.float64)
            inv = numpy.linalg.inv(matrix)
            local = inv @ numpy.array([world.x, world.y, world.z, 1.0])
            self._pick_point = local[:3] / local[3]
            self._has_pick = True
            self._stats_text = "placed - click Preview"
            self.propertyChanged.emit()
        return result

```

- [ ] **Step 9: Verify it compiles**

Run: `./.venv/Scripts/python.exe -m py_compile ObjectTweaker.py`
Expected: no output (success).

- [ ] **Step 10: Verify the full suite still passes**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (27 passed).

- [ ] **Step 11: Commit**

```bash
git add ObjectTweaker.py
git commit -m "feat: add emboss feature, stamp params, and mouse picking to adapter"
```

---

### Task 4: QML Emboss panel + docs

**Files:**
- Modify: `qt6/ObjectTweaker.qml`
- Modify: `qml/ObjectTweaker.qml`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the emboss properties from Task 3.
- Produces: the Emboss control group.

> **Verification note:** QML verified in Cura (Manual Cura Checklist). Dual-file identity is the testable invariant.

- [ ] **Step 1: Add "Emboss" to the feature ComboBox in `qt6/ObjectTweaker.qml`.** Replace:

```qml
            model: ["Simplify", "Fill Holes"]
            currentIndex: base.feature === "fillholes" ? 1 : 0
            onActivated: if (UM.ActiveTool) UM.ActiveTool.setProperty("Feature", currentIndex === 1 ? "fillholes" : "simplify")
```

with:

```qml
            model: ["Simplify", "Fill Holes", "Emboss"]
            currentIndex: base.feature === "emboss" ? 2 : (base.feature === "fillholes" ? 1 : 0)
            onActivated: if (UM.ActiveTool) UM.ActiveTool.setProperty("Feature", currentIndex === 2 ? "emboss" : (currentIndex === 1 ? "fillholes" : "simplify"))
```

- [ ] **Step 2: Add the Emboss group in `qt6/ObjectTweaker.qml`.** Immediately after the closing `}` of the `// ---- Fill Holes ----` `Column { ... }` block and before the `// ---- Shared: stats + actions ----` comment, insert:

```qml
        // ---- Emboss ----
        Column {
            visible: base.feature === "emboss"
            spacing: UM.Theme.getSize("default_margin").height

            property string shape: base.val("Shape", "circle")

            Label {
                text: "Click the model to place the stamp."
                wrapMode: Text.WordWrap
                width: UM.Theme.getSize("setting_control").width
            }

            ComboBox {
                id: shapeCombo
                width: UM.Theme.getSize("setting_control").width
                model: ["Circle", "Rectangle", "Star"]
                currentIndex: parent.shape === "star" ? 2 : (parent.shape === "rectangle" ? 1 : 0)
                onActivated: if (UM.ActiveTool) UM.ActiveTool.setProperty("Shape", currentIndex === 2 ? "star" : (currentIndex === 1 ? "rectangle" : "circle"))
            }

            RowLayout {
                visible: parent.shape === "circle" || parent.shape === "star"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Diameter " + Math.round(diaSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: diaSlider
                    from: 1; to: 100; stepSize: 1
                    value: base.val("Diameter", 10)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("Diameter", value)
                }
            }
            RowLayout {
                visible: parent.shape === "rectangle"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Width " + Math.round(wSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: wSlider
                    from: 1; to: 100; stepSize: 1
                    value: base.val("RectWidth", 10)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("RectWidth", value)
                }
            }
            RowLayout {
                visible: parent.shape === "rectangle"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Height " + Math.round(hSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: hSlider
                    from: 1; to: 100; stepSize: 1
                    value: base.val("RectHeight", 10)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("RectHeight", value)
                }
            }
            RowLayout {
                visible: parent.shape === "star"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Points " + Math.round(ptSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: ptSlider
                    from: 3; to: 12; stepSize: 1
                    value: base.val("StarPoints", 5)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("StarPoints", Math.round(value))
                }
            }

            RowLayout {
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Rotation " + Math.round(rotSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: rotSlider
                    from: 0; to: 360; stepSize: 1
                    value: base.val("Rotation", 0)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("Rotation", value)
                }
            }
            RowLayout {
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Depth " + depthSlider.value.toFixed(1); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: depthSlider
                    from: 0.2; to: 10; stepSize: 0.2
                    value: base.val("Depth", 1.0)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("Depth", value)
                }
            }
            CheckBox {
                text: "Engrave (recess instead of raise)"
                checked: base.val("EmbossMode", "emboss") === "engrave"
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("EmbossMode", checked ? "engrave" : "emboss")
            }
        }

```

- [ ] **Step 3: Copy `qt6/ObjectTweaker.qml` to `qml/ObjectTweaker.qml`** so they are byte-identical (both import `UM 1.5`).

- [ ] **Step 4: Verify the two QML files are identical (or differ only on the UM import line)**

Run: `diff qml/ObjectTweaker.qml qt6/ObjectTweaker.qml`
Expected: no output (identical).

- [ ] **Step 5: Check brace balance of both QML files**

Run: `for f in qml/ObjectTweaker.qml qt6/ObjectTweaker.qml; do echo "$f open=$(tr -cd '{' < "$f" | wc -c) close=$(tr -cd '}' < "$f" | wc -c)"; done`
Expected: each file reports equal open/close counts.

- [ ] **Step 6: Update `CLAUDE.md`.** After the line:

```markdown
- `core/fillholes.py` detect open loops (single-use-edge chaining, no networkx) + cap all
```

add:

```markdown
- `core/stamp.py`     2D shape outlines + extruded prism (reuses cap._earclip)
- `core/emboss.py`    nearest-face normal + boolean stamp (manifold3d), emboss/engrave
```

And replace the `ObjectTweaker.py` line:

```markdown
- `ObjectTweaker.py`  Cura Tool: Feature selector (Simplify|Fill Holes), selection, preview thread, apply (undoable), reset
```

with:

```markdown
- `ObjectTweaker.py`  Cura Tool: Feature selector (Simplify|Fill Holes|Emboss), selection, mouse-pick (PickingPass) for emboss, preview thread, apply (undoable), reset
```

Then add a gotcha under the Gotchas list:

```markdown
- Emboss needs a boolean engine (manifold3d, bundled) and a watertight-ish
  model. Surface normal at the click is the nearest-face-by-centroid normal
  (pure numpy — avoids rtree, which trimesh's nearest.on_surface needs).
```

- [ ] **Step 7: Manual Cura Checklist** (junction already in place; restart Cura 5.13)

1. Select a model → dropdown now lists **Simplify / Fill Holes / Emboss**.
2. Choose **Emboss** → shape controls + "Click the model to place" hint show.
3. Click the model → stat reads `placed - click Preview`.
4. **Preview** → a raised circle appears at the click; stat `embossed`.
5. Toggle **Engrave**, Preview → a recess appears; stat `engraved`.
6. **Apply** → committed; Ctrl+Z undoes. Try Rectangle and Star shapes.
7. If a Preview reports `boolean failed - try Fill Holes`, run Fill Holes first, then emboss.
8. Confirm Simplify + Fill Holes still work. Check `cura.log` for no ObjectTweaker tracebacks.

- [ ] **Step 8: Run the full suite once more**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (27 passed).

- [ ] **Step 9: Commit**

```bash
git add qml/ObjectTweaker.qml qt6/ObjectTweaker.qml CLAUDE.md
git commit -m "feat: add Emboss panel (qml + qt6) + docs"
```

---

### Task 5: Bundle manifold3d + CI

**Files:**
- Modify: `requirements-bundle.txt`
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: nothing new.
- Produces: `manifold3d` in the bundled `lib/` and in CI.

- [ ] **Step 1: Add manifold3d to `requirements-bundle.txt`.** Append:

```text
manifold3d
```

- [ ] **Step 2: Re-bundle deps into `lib/`**

Run: `./.venv/Scripts/python.exe scripts/bundle_deps.py`
Expected: prints "Bundled deps into ... lib"; `lib/manifold3d*.pyd` exists afterward.

- [ ] **Step 3: Ensure CI installs the test deps (already does).** Confirm `.github/workflows/tests.yml` runs `pip install -r requirements-test.txt` (which now includes manifold3d). No change needed if that line is present; if the workflow pins specific packages instead, add `manifold3d` to the install line.

- [ ] **Step 4: Run the full suite once more**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (27 passed).

- [ ] **Step 5: Commit**

```bash
git add requirements-bundle.txt .github/workflows/tests.yml
git commit -m "build: bundle manifold3d for the Emboss boolean engine"
```

---

## Self-Review Notes

- **Spec coverage:** §2.1 stamp + emboss → Tasks 1–2; §2.2 manifold3d dep → Tasks 2/5; §3.1 outlines → Task 1; §3.2 prism → Task 1; §3.3 orient+boolean → Task 2; §4 adapter (feature, params, picking) → Task 3; §5 UI → Task 4; §6 deps → Tasks 2/5; §7 testing → Tasks 1–2. All covered.
- **Normal without rtree:** §4 said `mesh.nearest.on_surface`, but that needs rtree (not shipped). Plan uses `nearest_face_normal` (centroid-nearest, pure numpy) instead — a deliberate, documented deviation (CLAUDE.md gotcha in Task 4). Behaviorally equivalent for a click that lands on the surface.
- **Placeholder scan:** none — every code step is complete; QML insertions give full blocks.
- **Type consistency:** `shape_outline(kind, params)` and `make_prism(outline, height)` (Task 1) consumed by `emboss` (Task 2) and the adapter (Task 3). `emboss(mesh, point, normal, outline_2d, depth, mode) -> (mesh, ok)` consumed by `_computeForFeature` (Task 3). Exposed property names (`Shape`, `Diameter`, `RectWidth`, `RectHeight`, `StarPoints`, `StarInnerRatio`, `Rotation`, `Depth`, `EmbossMode`) match between `setExposedProperties`, the getters/setters (Task 3), and the QML `setProperty` calls (Task 4). `_shapeParams` dict keys (`diameter`, `width`, `height`, `points`, `inner_ratio`, `rotation`) match `shape_outline`'s reads.
```