"""Procedural terrain, noise and scattering."""

import math

import bpy  # noqa: I001  (before bmesh/mathutils, required by the bpy module)
import bmesh
from mathutils import Vector, noise

from .core import _from_bmesh, _place


def fbm(x, y, scale=40.0, octaves=5, seed=0, lacunarity=2.0, gain=0.5):
    """Fractal noise in roughly [-1, 1]. `scale` is the feature size in meters."""
    total, amp, freq, norm = 0.0, 1.0, 1.0 / scale, 0.0
    for i in range(octaves):
        total += amp * noise.noise(Vector((x * freq, y * freq, seed * 17.13 + i * 3.7)))
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


def island_falloff(x, y, radius):
    """1 at the center, 0 at `radius`, smooth in between. Multiply heights by it."""
    d = math.hypot(x, y) / radius
    return max(0.0, 1.0 - d * d) ** 1.5


def terrain(name, size=200.0, resolution=128, height=lambda x, y: 0.0, bands=None,
            material=None, smooth=False, center=(0.0, 0.0), backdrop=False, collection=None):
    """Heightfield grid of `size` meters centered on `center` (x, y).

    backdrop=True for landscape that surrounds the subject (keeps framing and shadows tight).

    height: f(x, y) -> z in meters.
    bands:  [(max_z, material), ...] ascending; each face gets the first band its center is under.
            Gives sand/grass/rock/snow looks that export cleanly to glTF.
    """
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=resolution, y_segments=resolution, size=size / 2)
    for v in bm.verts:
        v.co.x += center[0]
        v.co.y += center[1]
        v.co.z = height(v.co.x, v.co.y)
    obj = _from_bmesh(name, bm, None, smooth)
    me = obj.data
    if bands:
        for _, mat in bands:
            me.materials.append(mat)
        for poly in me.polygons:
            z = poly.center.z
            poly.material_index = next(
                (i for i, (top, _) in enumerate(bands) if z <= top), len(bands) - 1)
    elif material is not None:
        me.materials.append(material)
    if backdrop:
        obj["backdrop"] = True
    return _place(obj, (0, 0, 0), (0, 0, 0), (1, 1, 1), collection)


def scatter(rng, count, area, height=lambda x, y: 0.0, accept=None, min_dist=0.0,
            max_tries=None):
    """Random points on a surface.

    area:   (xmin, xmax, ymin, ymax) rectangle, or a float radius for a disc.
    accept: optional f(x, y, z) -> bool to reject points (e.g. underwater, too steep).
    Returns a list of (x, y, z).
    """
    pts = []
    tries = max_tries or count * 30
    cell = min_dist / math.sqrt(2) if min_dist else 0
    grid = {}
    while len(pts) < count and tries > 0:
        tries -= 1
        if isinstance(area, (int, float)):
            r = area * math.sqrt(rng.random())
            a = rng.random() * math.tau
            x, y = r * math.cos(a), r * math.sin(a)
        else:
            x, y = rng.uniform(area[0], area[1]), rng.uniform(area[2], area[3])
        z = height(x, y)
        if accept and not accept(x, y, z):
            continue
        if cell:
            gx, gy = int(x // cell), int(y // cell)
            near = (grid.get((gx + i, gy + j)) for i in range(-2, 3) for j in range(-2, 3))
            if any(p and math.hypot(p[0] - x, p[1] - y) < min_dist for p in near):
                continue
            grid[(gx, gy)] = (x, y)
        pts.append((x, y, z))
    return pts


def slope(height, x, y, eps=0.5):
    """Steepness in degrees of a height function at (x, y)."""
    dx = (height(x + eps, y) - height(x - eps, y)) / (2 * eps)
    dy = (height(x, y + eps) - height(x, y - eps)) / (2 * eps)
    return math.degrees(math.atan(math.hypot(dx, dy)))
