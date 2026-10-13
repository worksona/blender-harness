"""Measure a reference photo through its solved camera (plain Python + numpy, no Blender).

Every build writes build/<slug>/cameras.json with the photo_camera() views. With it:

    python3 tools/photo_measure.py <slug> <photo> --px 1720,3810 [--z 0.58] ...
        pixel(s) of the full-size photo -> the point on the plane z (default 0, the floor)
    python3 tools/photo_measure.py <slug> <photo> --pt 1.55,5.9,0.58 ...
        world point(s) -> pixel in the full-size photo

Use it to place things where a photo shows them: pick a stand's foot, a pipe end or a stain in
the photo, project it onto the floor (or onto the height it sits at), and put the object there.
Points on the floor are the most reliable; raised points depend on the camera's height and pitch.
Cross-check a point seen in two photos: if they disagree, refine the camera first.
"""

import argparse
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(slug, photo):
    with open(os.path.join(ROOT, "build", slug, "cameras.json")) as f:
        views = json.load(f)
    for v in views:
        if v["photo"] == photo or os.path.splitext(v["photo"])[0] == os.path.splitext(photo)[0]:
            return v
    raise SystemExit(f"no camera for {photo}; have: {', '.join(v['photo'] for v in views)}")


def basis(v):
    m = np.array(v["matrix"])          # camera-to-world, Blender convention (looks down -Z)
    loc = m[:3, 3]
    R, U, F = m[:3, 0], m[:3, 1], -m[:3, 2]
    return loc, R, U, F


def focal_px(v, width):
    return v["lens"] / v["sensor_width"] * width


def pixel_to_plane(v, u, px_v, width, height, z=0.0):
    loc, R, U, F = basis(v)
    f = focal_px(v, width)
    sx, sy = v.get("shift", (0, 0))
    d = F + ((u - width / 2) / f - sx * width / f) * R + ((height / 2 - px_v) / f + sy * width / f) * U
    t = (z - loc[2]) / d[2]
    return loc + d * t


def point_to_pixel(v, p, width, height):
    loc, R, U, F = basis(v)
    f = focal_px(v, width)
    q = np.asarray(p, float) - loc
    depth = q @ F
    sx, sy = v.get("shift", (0, 0))
    return (width / 2 + f * (q @ R) / depth + sx * width, height / 2 - f * (q @ U) / depth + sy * width)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("photo")
    ap.add_argument("--px", nargs="*", default=[], help="u,v pixels in the full-size photo")
    ap.add_argument("--z", type=float, default=0.0, help="height of the plane for --px (m)")
    ap.add_argument("--pt", nargs="*", default=[], help="x,y,z world points")
    a = ap.parse_args()
    v = load(a.slug, a.photo)
    w, h = v["pixels"]
    for s in a.px:
        u, pv = (float(c) for c in s.split(","))
        p = pixel_to_plane(v, u, pv, w, h, a.z)
        print(f"px ({u:.0f}, {pv:.0f}) at z={a.z:g} -> ({p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f})")
    for s in a.pt:
        p = [float(c) for c in s.split(",")]
        u, pv = point_to_pixel(v, p, w, h)
        print(f"({', '.join(f'{c:g}' for c in p)}) -> px ({u:.0f}, {pv:.0f}) of {w}x{h}")


if __name__ == "__main__":
    main()
