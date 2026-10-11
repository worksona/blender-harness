"""Check that headless Blender works here: version, Cycles devices, a tiny render, a glTF export.

    scripts/bl tools/doctor.py
"""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import harness as h  # noqa: E402


def main():
    print(f"[doctor] Blender {bpy.app.version_string}")
    print(f"[doctor] Python {sys.version.split()[0]}, {os.cpu_count()} CPUs")
    prefs = bpy.context.preferences.addons.get("cycles")
    if prefs:
        cp = prefs.preferences
        for backend in ("CUDA", "OPTIX", "HIP", "METAL", "ONEAPI"):
            try:
                cp.compute_device_type = backend
                cp.get_devices()
                gpus = [d.name for d in cp.devices if d.type != "CPU"]
                if gpus:
                    print(f"[doctor] GPU ({backend}): {', '.join(gpus)}")
            except TypeError:
                pass
    h.reset()
    h.box("Cube", 1, material=h.material("red", "#cc3333"))
    h.sun()
    h.sky()
    h.camera((3, -3, 2.5), (0, 0, 0.5))
    with tempfile.TemporaryDirectory() as tmp:
        t = time.time()
        h.render(os.path.join(tmp, "doctor.jpg"), (128, 72), samples=4)
        print(f"[doctor] Cycles CPU render OK ({time.time() - t:.1f}s)")
        h.export_glb(os.path.join(tmp, "doctor.glb"))
        print(f"[doctor] glTF export OK ({os.path.getsize(os.path.join(tmp, 'doctor.glb'))} bytes)")
    print("[doctor] all good")


main()
