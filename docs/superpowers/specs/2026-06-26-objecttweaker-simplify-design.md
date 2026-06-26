# ObjectTweaker — Design Spec (MVP: Simplify)

**Date:** 2026-06-26
**Author:** Emanuel Lönnberg
**Status:** Approved design, pending implementation plan

## 1. Summary

ObjectTweaker is a Cura plugin that *modifies* the geometry of a selected
model in place (as opposed to ObjectSplitter, which slices a model into
multiple parts). It is built as a Cura **Tool** and follows ObjectSplitter's
proven architecture: all computational logic lives in a pure-Python `core/`
package that is testable outside Cura, and a thin `ObjectTweaker.py` adapter
wires Cura UI events to that core.

The MVP ships a single user-facing feature — **Simplify** — composed of three
independently-toggleable operations:

1. **Decimate** — reduce triangle count via quadric edge collapse.
2. **Smooth** — Taubin/Laplacian surface smoothing.
3. **Remove small parts** — delete tiny disconnected shells (debris).

Future features (fill holes, emboss/engrave, add text to surface) are out of
scope for this spec and will each get their own spec → plan → implementation
cycle.

### Non-goals (MVP)

- Hole filling / watertight repair (deferred; requires cap generation).
- Emboss, engrave, and text-on-surface (deferred; require triangulation).
- Multi-select / batch operation across several models (single selected
  model only).

## 2. Architecture

Module layout mirrors ObjectSplitter:

```
ObjectTweaker/
  __init__.py            Plugin registration, lib/ path injection,
                         conditional Cura imports (so core/ imports clean
                         outside Cura for tests).
  ObjectTweaker.py       Cura Tool adapter: selection handling,
                         preview/apply/reset, undo integration, QML wiring.
  plugin.json            api 8, supported_sdk_versions 8.x, min Cura 5.0.0.
  icon.svg
  core/                  Pure Python, no Cura dependencies. Unit-tested.
    mesh_io.py           Convert Cura MeshData <-> trimesh (vertices/faces
                         ndarrays). Single conversion boundary.
    decimate.py          Quadric decimation to a target face count / percent.
    smooth.py            Taubin (default) / Laplacian smoothing.
    cleanup.py           Remove small disconnected shells.
    pipeline.py          Orchestrate enabled ops in fixed order; return the
                         result mesh plus a stats dict.
  qml/   ObjectTweaker.qml   UM 1.5 / Qt5 (Cura 4.x compat panel)
  qt6/   ObjectTweaker.qml   UM 1.6 / Qt6 (Cura 5.x panel) — kept in sync
  tests/                 pytest suite over core/ with synthetic meshes.
  scripts/
    bundle_deps.py       Vendor non-Cura deps into lib/.
    build_curapackage.py Build the installable .curapackage from plugin.json.
  lib/                   Bundled runtime deps (trimesh, fast-simplification).
```

### Design rationale

- **core/ is Cura-free.** Each `core/` module has one purpose, communicates
  through plain ndarray/`trimesh.Trimesh` interfaces, and is tested without a
  running Cura. This is the same separation that makes ObjectSplitter's logic
  testable.
- **mesh_io.py is the only conversion boundary.** All `MeshData` ↔ trimesh
  translation happens in one place so the op modules never import Cura types.
- **Dual QML.** `qml/` (UM 1.5) and `qt6/` (UM 1.6) must stay in sync; the only
  intended difference is the `import UM` version line, matching ObjectSplitter's
  convention.

## 3. Core operations

All three operations avoid generating new faces, so Cura's missing
triangulation engine (`mapbox_earcut` / `triangle`) is a non-issue — the single
hardest constraint ObjectSplitter hit does not apply here.

### 3.1 Decimate (`core/decimate.py`)

- Engine: `trimesh.Trimesh.simplify_quadric_decimation(face_count=N)`.
- Backend dependency: `fast-simplification` (small package with prebuilt
  wheels), bundled into `lib/`.
- Input: either a target **percent reduction** (e.g. keep 25%) or an absolute
  **target triangle count**. The UI exposes percent; the core accepts either
  and resolves to a face count.
- Output: new `trimesh.Trimesh` with ≈ target face count.

### 3.2 Smooth (`core/smooth.py`)

- Engine: `trimesh.smoothing.filter_taubin` (default) with `filter_laplacian`
  available as an alternative. Pure numpy/scipy — **no new dependency**.
- Input: iteration count (and, for Taubin, the standard lambda/nu factors with
  sensible defaults; UI exposes a single "strength"/iterations slider).
- Output: mesh with the same topology, smoothed vertex positions. Taubin is
  chosen as default because it resists the volumetric shrinkage that plain
  Laplacian smoothing causes.

### 3.3 Remove small parts (`core/cleanup.py`)

- Engine: `mesh.split(only_watertight=False)` to enumerate connected
  components.
- Selection: keep components whose size is above a threshold, where size is
  measured by **bounding-box volume as a percentage of the largest component**
  (e.g. drop any shell under 1% of the biggest). Bounding-box volume, not face
  count: a physically tiny cube and a huge cube both have 12 faces, so face
  count is a poor "small part" proxy. A "keep largest only" toggle
  short-circuits to keeping the single largest component.
- Output: a single merged mesh of the surviving components.

### 3.4 Pipeline (`core/pipeline.py`)

Runs the **enabled** operations in a fixed order:

```
remove small parts  →  decimate  →  smooth
```

Rationale: drop debris first (so it does not consume the decimation budget or
get smoothed), then reduce triangle count, then polish the reduced surface.

Returns the result mesh plus a stats dict:

```python
{
  "tris_before": int,
  "tris_after": int,
  "parts_removed": int,
}
```

## 4. Cura adapter and interaction flow (Approach A: staged compute)

`ObjectTweaker.py` is a Cura `Tool`. Interaction:

1. **Tool activated / selection changed.** Capture the single selected
   `SceneNode` and cache a reference to its original `MeshData`.
2. **Preview.** Convert the node's mesh to trimesh via `mesh_io`, run
   `pipeline` in a **daemon thread with a hard timeout** and a `cancel_event`
   (the exact pattern ObjectSplitter uses for its expensive algorithms). On
   success, swap the node's displayed mesh to the computed result and push the
   stats to QML (`tris: before → after`, parts removed). A parameter change
   re-triggers preview (debounced) and discards the prior preview result.
3. **Apply.** Commit the previewed result as an **undoable Operation** on
   Cura's `OperationStack`, so the change participates in undo/redo.
4. **Reset, or tool deactivation without Apply.** Restore the cached original
   `MeshData` to the node.

Only the single selected mesh is operated on. If nothing (or more than one
mesh) is selected, the panel disables Preview/Apply and shows a hint.

### Error handling

- Compute runs off the UI thread; a timeout or exception leaves the original
  mesh untouched and surfaces a message in the panel (and a `Logger.log` entry).
- Conversion failures (degenerate/empty mesh) are caught in `mesh_io` and
  reported, never crash the tool.
- If decimation's backend is unavailable at runtime, the tool reports it
  cleanly rather than raising (mirrors ObjectSplitter's graceful-fallback
  ethos).

## 5. UI (QML, both `qml/` and `qt6/`)

A single tool panel:

- One **enable checkbox per operation**: Decimate, Smooth, Remove small parts.
- **Decimate:** target-percent slider (e.g. "Keep 25%").
- **Smooth:** iterations / strength slider.
- **Remove small parts:** size-threshold slider + "keep largest only" checkbox.
- **Stat line:** `tris: 240k → 60k`, plus parts-removed count when relevant.
- **Buttons:** Preview, Apply, Reset.
- **Busy indicator** shown while the background compute runs.
- Controls/buttons disable when there is no valid single-mesh selection.

QML-exposed properties follow ObjectSplitter's convention: each is registered
in `setExposedProperties()` with a `getFoo` getter and a guarded `setFoo`
setter that emits `propertyChanged`.

## 6. Dependencies

- **Bundled in `lib/`:** `trimesh` (and its required transitive deps),
  `fast-simplification` (decimation backend).
- **From Cura:** `numpy`, `scipy`.
- **Not needed for MVP:** `manifold3d`, `networkx`, `rtree`, `shapely`.

`scripts/bundle_deps.py` vendors only the non-Cura packages, keeping the plugin
ABI-correct across Cura updates (same rationale as ObjectSplitter).

## 7. Testing

pytest over `core/` with synthetic meshes, no Cura required:

- **Decimate:** start from a high-poly sphere; assert the result face count is
  within tolerance of the requested target and that the shape is preserved
  (bounding box / volume within tolerance).
- **Smooth:** start from a noisy mesh; assert a reduction in vertex-normal
  variance (or surface roughness metric) with topology unchanged.
- **Remove small parts:** build a mesh with one large shell + one tiny shell;
  assert the tiny shell is removed and `parts_removed == 1`.
- **Pipeline:** assert op ordering and the stats dict contents on a combined
  run.

CI runs pytest on push/PR across py3.10–3.12 (Linux) + py3.12 (Windows),
matching ObjectSplitter's workflow.

## 8. Future work (out of scope, noted for direction)

- Fill holes / watertight repair (needs cap generation via the scipy-based
  triangulation fallback, since Cura lacks an earcut/triangle engine).
- Emboss / engrave a surface region.
- Add text to a surface.
- Multi-select / batch tweak.

Each becomes its own feature behind the same Tool, added the way ObjectSplitter
adds cut modes.
