# ObjectTweaker — Fill Holes Design Spec

**Date:** 2026-06-27
**Author:** Emanuel Lönnberg
**Status:** Approved design, pending implementation plan

## 1. Summary

Add a second feature, **Fill Holes**, to the ObjectTweaker Cura tool. It
detects every open boundary loop on the selected model and caps each one,
turning a non-watertight (un-printable) mesh into a closed one. It reuses
ObjectTweaker's existing Preview → Apply (undoable) → Reset machinery and ports
ObjectSplitter's proven, engine-free boundary-capping helpers.

To host more than one feature under a single tool, ObjectTweaker gains a
**feature selector** (a dropdown: Simplify | Fill Holes). This mirrors
ObjectSplitter's single-tool / multiple-mode structure.

### Scope (MVP)

- Fill **all** detected holes (no per-hole picking, no size threshold).
- Cap method: planar **ear-clip** triangulation per loop (pure Python, no
  triangulation engine, no scipy), with **fan-from-centroid** as a fallback
  when ear-clipping yields nothing.

### Non-goals

- User-selected / click-to-fill individual holes.
- Size-threshold filtering (skip large intentional openings).
- Smooth/curved fills — caps are planar (best-fit plane per loop).

## 2. Architecture

### 2.1 Feature selector refactor

ObjectTweaker becomes multi-feature:

- New exposed property `Feature` (`"simplify"` | `"fillholes"`, default
  `"simplify"`) with `getFeature`/`setFeature`.
- The shared Preview/Apply/Reset flow is **unchanged** — it already swaps the
  node's display mesh to a generic result and commits it via the undoable
  `_SetMeshDataOperation`. Only the *compute* step branches on the feature.
- The adapter's preview worker calls a new dispatcher
  `_computeForFeature(mesh) -> (result_mesh: trimesh.Trimesh, stats_text: str)`:
  - `simplify` → `core.pipeline.run(...)`, stats `"tris: A -> B[, removed N part(s)]"`.
  - `fillholes` → `core.fillholes.fill_holes(...)`, stats `"holes filled: N"`.
- `core/pipeline.py` and the Simplify ops are untouched.

### 2.2 New core modules

```
core/
  cap.py        Single-loop capping: sanitize loop, fit best-fit plane,
                project to 2D, ear-clip triangulate (+ fan fallback),
                orient cap winding. Pure numpy + trimesh, NO scipy, NO
                triangulation engine. Ported from ObjectSplitter's
                mesh_splitter cap helpers.
  fillholes.py  fill_holes(mesh) -> (filled_mesh, holes_filled): enumerate
                boundary loops via mesh.outline(), cap each via cap.py,
                concatenate + merge_vertices to stitch seams, return count.
```

`cap.py` is the only module doing low-level triangulation; `fillholes.py`
orchestrates loops and stitching. Both are Cura-free and unit-tested.

## 3. Core algorithm (`core/cap.py`, `core/fillholes.py`)

### 3.1 Boundary loop detection

`fill_holes` finds boundary edges (each used by exactly one face) and chains
them into loops by walking the boundary-edge graph — each boundary vertex of a
simple hole has degree two. A watertight mesh has no boundary edges, hence no
loops. (We do *not* use trimesh's `outline().discrete`: that pulls in
**networkx**, which Cura does not ship and we do not bundle. Manual chaining is
pure numpy + stdlib.)

### 3.2 Per-loop cap (`core/cap.py`)

For each loop polyline:

1. `_sanitize_loop(loop_3d)` — drop the closure-duplicate point and any
   consecutive duplicates; require ≥ 3 distinct points.
2. `_fit_plane(loop_3d) -> (origin, u, v)` — SVD best-fit plane basis,
   re-orthogonalized. Returns `None` for degenerate (collinear) loops.
3. Project to 2D: `loop_2d = [(p-origin)·u, (p-origin)·v]`.
4. `_earclip(loop_2d) -> faces (M,3) | None` — pure-Python ear-clipping
   triangulation of the simple polygon (handles convex and concave). Ported
   from ObjectSplitter's `_triangulate_polygon_earclip`.
5. If ear-clipping returns `None`/empty → `_fan(loop_2d)`: add a centroid
   vertex and fan triangles to each boundary edge (always closes the loop).
6. Map cap vertices back to 3D (`origin + x·u + y·v`); snap any vertex that
   coincides with an original loop point back to its exact 3D coordinate so the
   seam stitches cleanly under `merge_vertices`.

`cap.py` exposes `cap_loop(loop_3d) -> trimesh.Trimesh | None` returning the
cap mesh for one loop (or `None` if it cannot be capped).

### 3.3 Stitching (`core/fillholes.py`)

```python
def fill_holes(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, int]:
    # mesh.outline().discrete is a list of 3D loop polylines; [] if watertight
    # or if outline() raises (caught and treated as no loops).
    loops = _boundary_loops(mesh)
    caps = [cap_loop(loop) for loop in loops]
    caps = [c for c in caps if c is not None]
    if not caps:
        return mesh, 0
    combined = trimesh.util.concatenate([mesh] + caps)
    combined.merge_vertices(digits_vertex=7)
    combined.remove_unreferenced_vertices()
    try:
        combined.fix_normals()
    except Exception:
        pass
    return combined, len(caps)
```

`holes_filled` is the number of loops successfully capped. Winding is unified
with `fix_normals()` (whole-mesh; acceptable here — Fill Holes is not on the
hot path the way ObjectSplitter's per-cut local orientation was).

## 4. Cura adapter changes (`ObjectTweaker.py`)

- Add `self._feature = "simplify"`, `getFeature`/`setFeature`, and `"Feature"`
  in `setExposedProperties`.
- Add `_computeForFeature(mesh)` dispatcher (§2.1).
- Refactor `_previewWorker` to call `_computeForFeature` instead of calling the
  Simplify pipeline directly. Preview/Apply/Reset, the daemon-thread timeout,
  and `_SetMeshDataOperation` are unchanged.

## 5. UI (`qml/` + `qt6/`, kept in sync)

- A **ComboBox** at the top of the panel: `Simplify`, `Fill Holes`, bound to the
  `Feature` property.
- Simplify's existing controls are wrapped in a group shown only when
  `Feature === "simplify"`.
- A Fill Holes group, shown only when `Feature === "fillholes"`, contains a
  one-line description ("Caps all open boundary loops to make the model
  watertight."). MVP has no parameters.
- The shared stats `Label` and Preview/Apply/Reset `RowLayout` stay at the
  bottom, used by both features.
- Controls remain plain `QtQuick.Controls` (no `UM.*` control types); buttons
  dispatch via the existing `TriggerPreview`/`TriggerApply`/`TriggerReset`
  write-only properties.

## 6. Dependencies

No new dependencies. `core/cap.py` and `core/fillholes.py` use only `numpy` and
`trimesh` (both already available; numpy from Cura, trimesh bundled). scipy is
**not** required — capping uses pure-Python ear-clipping, not Delaunay.

## 7. Testing

pytest over `core/`, no Cura:

- **cap.py** — `cap_loop` on a square loop (4 points) returns a 2-triangle
  cap; on a concave (L-shaped) loop returns a valid triangulation with no
  triangle outside the polygon; on a collinear/degenerate loop returns `None`.
- **fillholes.py**
  - Box with its top face removed (one square hole) → `holes_filled == 1` and
    `result.is_watertight is True`.
  - Open-ended tube (cylinder with both end caps removed) → `holes_filled == 2`.
  - Already-closed sphere → `holes_filled == 0`, face count unchanged.
- Build open meshes by deleting faces from trimesh primitives
  (`mesh.update_faces(mask)`).

CI unchanged (py3.10–3.12 Linux + py3.12 Windows).

## 8. Future work

- Per-hole picking (ray-cast to the nearest boundary loop).
- Size-threshold filter to preserve intentional openings.
- Non-planar/curved caps for saddle-shaped holes.
