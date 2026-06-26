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
