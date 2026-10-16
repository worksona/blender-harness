"""Assemble the Haven Home Assistant deploy bundle from haven/ and the built haven-home world.

    python3 tools/haven_bundle.py            # -> build/haven/Haven_Realtime_Deploy/ and .zip

Build the model first (make world W=haven-home). The bundle's haven/ folder is what goes into
/config/www/haven/ on the Home Assistant host: the dashboard HTML, the panel adapter, the three.js
renderer for the production model, vendored three.js, and haven-home.glb.
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "haven")
GLB = os.path.join(ROOT, "app", "worlds", "haven-home", "world.glb")
OUT = os.path.join(ROOT, "build", "haven", "Haven_Realtime_Deploy")


def main():
    if not os.path.exists(GLB):
        sys.exit("no model: run `make world W=haven-home` first")
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(os.path.join(SRC, "www"), os.path.join(OUT, "haven"))
    shutil.copy2(GLB, os.path.join(OUT, "haven", "haven-home.glb"))
    for f in ("README.md", "configuration_snippet.yaml"):
        shutil.copy2(os.path.join(SRC, f), os.path.join(OUT, f))
    archive = shutil.make_archive(OUT, "zip", os.path.dirname(OUT), os.path.basename(OUT))
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUT) for f in fs)
    print(f"[haven] {os.path.relpath(OUT, ROOT)}/ ({size / 1e6:.1f} MB)")
    print(f"[haven] {os.path.relpath(archive, ROOT)} ({os.path.getsize(archive) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
