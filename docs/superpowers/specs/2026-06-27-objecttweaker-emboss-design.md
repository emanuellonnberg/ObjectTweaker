# ObjectTweaker — Emboss / Engrave Design Spec

**Date:** 2026-06-27
**Author:** Emanuel Lönnberg
**Status:** Approved design, pending implementation plan

## 1. Summary

Add a third feature, **Emboss**, to the ObjectTweaker Cura tool. The user clicks
a point on the selected model, picks a 2D shape (circle, rectangle, or star),
and the shape is raised out of (emboss) or cut into (engrave) the surface by a
given depth. Geometry is created by booleaning an extruded prism of the shape
against the model.

It plugs into the existing Feature selector (Simplify | Fill Holes | **Emboss**)
and reuses the Preview → Apply (undoable) → Reset flow. It is the first feature
that needs **mouse interaction** (to place the stamp) and the first to bundle a
**boolean engine** (manifold3d).

### Scope (MVP)

- Shapes: **circle, rectangle, star** (2D outlines).
- Mode: **Emboss** (raised) or **Engrave** (recessed), chosen by a toggle;
  `depth` is the magnitude.
- Placement: **click the model surface**; the click point and the surface
  normal there orient and position the stamp.
- Boolean: **manifold3d** engine via `trimesh.boolean`, with the
  blender/default fallback chain (graceful failure — mesh untouched on error).

### Non-goals (deferred)

- Image heightmap relief (a separate future feature).
- SVG / custom outlines, and text (the separate "text" feature).
- Multiple stamps per apply; freeform in-plane dragging after placement.

## 2. Architecture

### 2.1 New core modules (pure Python, Cura-free, unit-tested)

```
core/
  stamp.py   shape_outline(kind, params) -> (N,2) outline points;
             make_prism(outline_2d, height) -> trimesh.Trimesh
             (top + bottom caps via the existing core.cap._earclip, plus
             side walls). Pure numpy + trimesh.
  emboss.py  emboss(mesh, point, normal, outline_2d, depth, mode)
             -> (result_mesh, ok): orient the prism so +Z maps to the surface
             normal at point, straddle the surface, boolean union/difference.
```

`stamp.py` reuses `core.cap._earclip` (ported ear-clipping) to triangulate the
shape caps — no new triangulation code. `emboss.py` owns the orientation math
and the boolean (with fallback engines).

### 2.2 Dependency

Bundle **manifold3d** into `lib/` (the boolean backend `trimesh.boolean` uses).
manifold3d ships version-specific wheels (`cp312`), so it must be bundled with
Python 3.12 to match Cura 5.13's interpreter — same constraint already used for
fast-simplification. `requirements-bundle.txt` gains `manifold3d`.

Booleans are most robust on watertight input; the Fill Holes feature already
exists to prepare a model. On boolean failure `emboss` returns `ok=False` and
the UI suggests running Fill Holes first.

## 3. Core algorithm

### 3.1 Shape outlines (`core/stamp.py`)

`shape_outline(kind: str, params: dict) -> numpy.ndarray` returns an `(N,2)`
CCW outline centered at the origin:

- **circle** — `params["diameter"]`; `N = 48` points on the radius.
- **rectangle** — `params["width"]`, `params["height"]`; 4 corners.
- **star** — `params["diameter"]` (outer), `params["points"]` (tips, default 5),
  `params["inner_ratio"]` (inner/outer radius, default 0.5); `2*points`
  alternating outer/inner vertices.

An optional `params["rotation"]` (degrees) rotates the outline about its center.

### 3.2 Prism (`core/stamp.py`)

`make_prism(outline_2d, height) -> trimesh.Trimesh`:

1. Triangulate the outline with `core.cap._earclip` → cap faces.
2. Bottom cap at `z = 0` (outline points), top cap at `z = height`
   (same points), with opposite winding so both face outward.
3. Side walls: for each outline edge `(i, j)`, two triangles joining the
   bottom edge to the top edge.
4. Build a single `trimesh.Trimesh`; result is watertight.

### 3.3 Orientation + boolean (`core/emboss.py`)

`emboss(mesh, point, normal, outline_2d, depth, mode) -> (trimesh.Trimesh, bool)`:

1. Build the prism with `height = depth + 2*EMBED` where `EMBED` (e.g. 0.5 mm)
   is how far the prism is sunk below the surface so the boolean is clean.
2. Rotation `R` aligning prism +Z to the unit `normal`
   (`trimesh.geometry.align_vectors([0,0,1], normal)`); translate so the prism
   base sits `EMBED` below `point` along `-normal`.
   - **Emboss**: the prism protrudes `depth` above the surface → `union`.
   - **Engrave**: place the prism `depth` below the surface (extend inward) →
     `difference`.
3. `result = _try_boolean(mesh_prepared, prism, op)` trying engines
   `["manifold", "blender", None]` in order (mirrors ObjectSplitter's
   `try_boolean_*`). `mesh_prepared` is a merged-vertex copy.
4. On success return `(result, True)`; on any failure return `(mesh, False)`.

## 4. Cura adapter (`ObjectTweaker.py`)

- Add `self._feature` option `"emboss"`, plus stamp params as exposed
  properties: `Shape` (`"circle"|"rectangle"|"star"`), `Diameter`, `RectWidth`,
  `RectHeight`, `StarPoints`, `StarInnerRatio`, `Rotation`, `Depth`,
  `EmbossMode` (`"emboss"|"engrave"`). Each gets a guarded get/set.
- **Mouse picking:** implement `event(self, event)`. On
  `Event.MousePressEvent` with `LeftButton` (and the Emboss feature active),
  run a `PickingPass` (`cura.PickingPass`) to get the world hit position; map it
  to model-local. Store `self._pick_point` (local). The surface **normal** is
  computed at compute time as the normal of the face whose centroid is nearest
  the pick (`core.emboss.nearest_face_normal`, pure numpy — avoids rtree, which
  `mesh.nearest.on_surface` would require). Mark a pick available.
- `_computeForFeature(mesh)` for `"emboss"`: if no pick yet, return
  `(mesh, "click the model to place")`; else build the outline via
  `stamp.shape_outline`, call `emboss.emboss(...)`. On `ok` →
  `"embossed"` / `"engraved"`; on failure → `"boolean failed — try Fill Holes"`.
- Preview/Apply/Reset, the daemon-thread timeout, and `_SetMeshDataOperation`
  are unchanged. Switching feature or selection clears the pick.

## 5. UI (`qml/` + `qt6/`, kept in sync)

The feature ComboBox gains **Emboss**. A new group, visible when
`Feature === "emboss"`:

- A hint Label: "Click the model to place the stamp."
- Shape ComboBox: Circle | Rectangle | Star.
- Shape-specific controls (shown by `Shape`): Circle → Diameter; Rectangle →
  Width, Height; Star → Diameter, Points, Inner ratio.
- Rotation slider (0–360°), Depth slider, and an **Emboss / Engrave** toggle
  (a CheckBox or two-item control bound to `EmbossMode`).
- Shared stats Label + Preview/Apply/Reset row.

Controls remain plain `QtQuick.Controls` (no `UM.*` control types). Buttons use
the existing `TriggerPreview`/`TriggerApply`/`TriggerReset` write-only
properties.

## 6. Dependencies

- New bundled dep: **manifold3d** (boolean engine), Python-3.12 wheel to match
  Cura 5.13. Added to `requirements-bundle.txt` and `requirements-test.txt`.
- Existing: trimesh, numpy. No scipy/networkx.

## 7. Testing

pytest over `core/`, no Cura (test venv must include manifold3d):

- **stamp.py**
  - `shape_outline("circle", {"diameter": 4})` returns 48 points all at
    radius 2 (± tol).
  - `shape_outline("star", {"diameter": 4, "points": 5})` returns 10 points.
  - `make_prism(square_outline, height=3)` is watertight with the expected
    bounding-box height.
- **emboss.py**
  - Emboss a circle onto the top face of a box (point on +Z face, normal +Z) →
    `ok is True`, result watertight, `volume > original`.
  - Engrave the same → `ok is True`, `volume < original`.
  - A pick normal of zero length / degenerate outline → `ok is False`, mesh
    returned unchanged.

CI gains `manifold3d` in the install step.

## 8. Future work

- Image heightmap relief (load PNG → tall stamp / displacement).
- SVG outline import; text-on-surface.
- In-plane drag-to-reposition and live stamp marker before Apply.
