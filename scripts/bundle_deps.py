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
