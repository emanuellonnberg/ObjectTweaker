# ObjectTweaker - Claude Code Project Guide

Cura plugin that edits the selected model in place. Logic in `core/` (pure
Python, no Cura), wired to Cura by `ObjectTweaker.py`.

## Architecture
- `core/mesh_io.py`   MeshData<->trimesh array conversion (only conversion boundary)
- `core/decimate.py`  quadric decimation (needs fast-simplification)
- `core/smooth.py`    Taubin/Laplacian smoothing
- `core/cleanup.py`   remove small disconnected shells (bbox-volume metric)
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
- "Remove small parts" ranks components by bounding-box volume, not face count
  (a tiny cube and a huge cube both have 12 faces).
- **Imports must be relative inside the plugin.** Cura loads the plugin as the
  package `ObjectTweaker`, so `core` is only reachable as `.core`. Use
  `from .core.pipeline import ...` in `ObjectTweaker.py` and `from .cleanup
  import ...` between `core/` modules. Absolute `from core.X import ...` works
  in pytest (conftest puts the root on sys.path) but raises ImportError in
  Cura — the plugin then silently fails to register ("did not return any
  objects to register"). Test files themselves keep `from core.X` (top-level).
- **Tool panel uses plain QtQuick.Controls, not `UM.*` controls.** `UM.Slider`
  is not a type in Cura 5.13 and a single unknown type blanks the entire panel
  (silent — only a `__onQmlWarning` "X is not a type" in cura.log). Use bare
  `CheckBox` / `Label` / `Slider` / `Button` from `QtQuick.Controls 2.15` (the
  set ObjectSplitter uses). Buttons dispatch actions via write-only exposed
  properties (`TriggerPreview`/`TriggerApply`/`TriggerReset`) set with
  `UM.ActiveTool.setProperty(...)`, NOT `triggerAction()`.

## Build
`python scripts/bundle_deps.py` then `python scripts/build_curapackage.py`.
