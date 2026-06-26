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
