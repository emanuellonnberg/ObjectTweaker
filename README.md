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
