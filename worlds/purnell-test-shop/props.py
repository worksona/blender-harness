"""Shop props: polyethylene pipe stands, flange racks, the hydrotest station, the deadweight
tester, bolt pallets, cribbing, grating, hoses and the usual shop furniture."""

import math

import numpy as np
from mathutils import Vector

from harness import *
from harness.textures import load_pixels, resize

import shop




# ------------------------------------------------------------------ textures

def stand_texture(name, base, seed):
    """Polyethylene stand skin: base colour, blotchy grey paint where pipes have rested (upper
    half), black marker scribbles, scuffs and dirt toward the foot. Side faces map v to height
    (1 m per tile), so row position in the image is height on the stand."""
    n = 512
    yy = np.linspace(1, 0, n)[:, None] * np.ones((1, n))        # v (height in m) per pixel row
    smear = fbm_noise(n, 3, 6, seed)
    blot = fbm_noise(n, 10, 4, seed + 1)
    grey_mask = contrast(smear * 0.7 + blot * 0.5 + (yy - 0.55) * 1.1, 0.62, 0.7)
    drips = contrast(fbm_noise(n, 40, 2, seed + 5), 0.7, 0.75) * contrast(yy, 0.35, 0.6)
    grey_mask = np.maximum(grey_mask, drips * 0.8)
    dirt = contrast(fbm_noise(n, 6, 4, seed + 2) + (0.18 - yy) * 2.0, 0.6, 0.95) * 0.55
    scuff = contrast(fbm_noise(n, 20, 3, seed + 3), 0.66, 0.85) * 0.3
    marks = contrast(fbm_noise(n, 24, 2, seed + 4), 0.82, 0.83) * contrast(fbm_noise(n, 5, 2, seed + 6), 0.7, 0.75) * 0.5
    col = colorize(np.zeros((n, n)), base, base)
    col = col * (1 - grey_mask[..., None]) + np.array([0.58, 0.6, 0.6]) * grey_mask[..., None]
    col = col * (1 - dirt[..., None]) + np.array([0.33, 0.29, 0.22]) * dirt[..., None]
    col = col * (1 - scuff[..., None] * 0.45) * (1 - marks[..., None] * 0.8)
    return texture(name, np.clip(col, 0, 1))


# ------------------------------------------------------------------ pipe stands

def _loft(mb, profiles, mat, cap_top=True, smooth=False):
    """Skin a list of closed rings (lists of 3D points, same count) into the builder."""
    bm = mb.bm
    idx = mb._mat_index(mat)
    rings = [[bm.verts.new(p) for p in ring] for ring in profiles]
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            f.material_index = idx
            f.smooth = smooth
    if cap_top:
        f = bm.faces.new(rings[-1])
        f.material_index = idx
    return rings


def cone_stand(name, mat, hole_mat, H=0.76, saddle=0.07):
    """Tapered round PE pipe stand with a saddle-cut top, a side hole and a rolled foot lip.
    The pipe rests along local Y at height H - saddle."""
    mb = MeshBuilder(name)
    n = 28
    prof = []
    for z, r in ((0.0, 0.40), (0.035, 0.40), (0.045, 0.36), (H * 0.5, 0.27), (None, 0.17)):
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            zz = H - saddle * abs(math.sin(a)) if z is None else z    # V saddle, low along +-Y
            ring.append(Vector((r * math.cos(a), r * math.sin(a), zz)))
        prof.append(ring)
    _loft(mb, prof, mat, cap_top=False, smooth=True)
    # Top: a V trough across Y (two sloped planes) closing the rim
    bm = mb.bm
    top = prof[-1]
    c = bm.verts.new((0, 0, H - saddle - 0.01))
    rim = [bm.verts.new(p) for p in top]
    idx = mb._mat_index(mat)
    for k in range(n):
        f = bm.faces.new((rim[k], rim[(k + 1) % n], c))
        f.material_index = idx
    # Hole on the +X side near the top (dark disc set into the wall)
    z = H - 0.17
    r = 0.17 + (0.27 - 0.17) * (H - z) / (H * 0.5)
    mb.rod((r - 0.014, 0, z), (r + 0.003, 0, z), 0.045, hole_mat, 14)
    return prefab(mb.build())


def star_stand(name, mat, H=0.58):
    """Fluted four-rib PE stand (the 'star' stands under the big spools): a ribbed tapered
    column on a round foot, with a V-saddle block on top. Pipe runs along local Y."""
    mb = MeshBuilder(name)
    pts = 16

    def star(r_out, r_in, z):
        ring = []
        for k in range(pts):
            a = 2 * math.pi * k / pts
            r = r_out if k % 4 in (0, 1) else r_in if k % 4 == 2 else (r_out + r_in) / 2
            r = r_out if k % 4 == 0 else r_in if k % 4 == 2 else (r_out * 0.6 + r_in * 0.4)
            ring.append(Vector((r * math.cos(a + math.pi / 4), r * math.sin(a + math.pi / 4), z)))
        return ring
    _loft(mb, [star(0.34, 0.24, 0.03), star(0.31, 0.21, 0.06), star(0.16, 0.12, H - 0.08),
               star(0.15, 0.115, H - 0.05)], mat, cap_top=True)
    mb.cylinder((0, 0, 0), 0.42, 0.03, mat, 28)                       # foot
    # Saddle block with a V groove along Y
    w, d, t = 0.34, 0.22, 0.07
    z0 = H - 0.06
    for s in (-1, 1):
        mb.box((s * w * 0.3, 0, z0 + t / 2), (w * 0.4, d, t), mat, rotation=(0, -s * 14, 0))
    return prefab(mb.build())


# ------------------------------------------------------------------ racks and flanges

def flange_prefabs(M, rng):
    """A few loose flanges for the racks (WN, slip-on and blinds in common sizes)."""
    out = []
    specs = [(0.165, 0.025, 0.06, "rusty"), (0.216, 0.03, 0.07, "black"), (0.273, 0.035, 0.0, "rusty"),
             (0.356, 0.045, 0.1, "black"), (0.152, 0.022, 0.05, "galv"), (0.419, 0.055, 0.12, "rusty"),
             (0.254, 0.032, 0.07, "green")]
    for i, (od, t, hub, finish) in enumerate(specs):
        mb = MeshBuilder(f"RackFlange{i}")
        mat = M[f"flange_{finish}"]
        mb.rod((0, 0, -t / 2), (0, 0, t / 2), od / 2, mat, 24)
        if hub:
            mb.rod((0, 0, t / 2), (0, 0, t / 2 + hub), od * 0.32, mat, 16, radius_b=od * 0.2)
        mb.rod((0, 0, -t / 2 - 0.002), (0, 0, t / 2 + hub + 0.002), od * 0.16, M["bore"], 12, caps=False)
        out.append(prefab(mb.build()))
    return out


def flange_rack(M, flanges, rng, origin, yaw, length=4.6, levels=3, collection="Racks"):
    """Cantilever-style steel rack with flanges standing on edge in rows on each shelf."""
    ox, oy = origin
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def P(u, v, z):
        return (ox + u * c - v * s, oy + u * s + v * c, z)
    mb = MeshBuilder("FlangeRack")
    depth = 0.5
    for u in (0.0, length / 2, length):
        for v in (0.0, depth):
            mb.beam(P(u, v, 0), P(u, v, 1.85), 0.05, M["rack"])
    shelves = [0.25 + i * 0.58 for i in range(levels)]
    for z in shelves:
        for v in (0.02, depth - 0.02):
            mb.beam(P(0, v, z), P(length, v, z), 0.05, M["rack"], 0.08)
        for k in range(int(length / 0.6) + 1):
            mb.beam(P(k * 0.6, 0, z), P(k * 0.6, depth, z), 0.04, M["rack"])
    mb.build(collection=collection)
    for z in shelves:
        u = 0.1
        while u < length - 0.1:
            f = flanges[rng.randrange(len(flanges))]
            od = f.dimensions.x if f.dimensions.x > 0 else 0.25
            if z + od / 2 + 0.04 > 2.0:
                od = 0.2
            instance(f, "RackFlange", P(u, depth / 2, z + 0.04 + od / 2),
                     (90, 0, yaw + rng.uniform(-6, 6)), collection=collection)
            u += 0.07 + rng.uniform(0.0, 0.05)


# ------------------------------------------------------------------ test station

def screen_texture(name, page_png, box, size):
    """Crop an image (fractions x0, y0, x1, y1 from top-left) into a texture, e.g. the VTScada
    screen from the test pack or a gauge face from a photo."""
    px = load_pixels(page_png)
    H, W = px.shape[:2]
    x0, y0, x1, y1 = box
    crop = px[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W), :3]
    return texture(name, np.clip(resize(crop, size), 0, 1))


def test_station(M, name, label, origin, wall_normal, docs, collection="Test station"):
    """Wall-mounted hydrotest station: grey enclosure with the HMI, labelled plate, transmitter
    manifold (PT-1 pressure and TT-1 temperature, Rosemount blue), gauges and supply piping.
    Returns {part: object} for twin tagging, and anchor points for gauges."""
    ox, oy = origin
    n = Vector(wall_normal)
    u = Vector((-n.y, n.x, 0))          # along the wall
    base = Vector((ox, oy, 0))

    def P(a, b, h):                      # a along wall, b out from wall, h up
        return base + u * a + n * b + Vector((0, 0, h))
    yaw = math.degrees(math.atan2(n.y, n.x)) + 90    # decals' faces point along the wall normal
    out = {}
    mb = MeshBuilder(f"{name}_Panel")
    mb.box(P(0, 0.12, 1.55), (0.6, 0.25, 0.75), M["enclosure"], rotation=(0, 0, yaw))
    for a in (-0.32, 0.32):
        mb.box(P(a, 0.02, 1.0), (0.04, 0.04, 2.0), M["unistrut"], rotation=(0, 0, yaw))
    out["panel"] = mb.build(collection=collection)
    # HMI screen showing the test pack's VTScada trend
    hmi = screen_texture(f"{name}_hmi", docs["scada"], (0.0, 0.0, 1.0, 1.0), (384, 288))
    decal(f"{name}_HMI", hmi, (0.3, 0.225), P(-0.08, 0.249, 1.62), (90, 0, yaw),
                   material_name=f"{name}_hmi_m")
    # Label plate
    img = texture(f"{name}_label", text_image(label, "#ffffff", 64, background="#c3241c"))
    decal(f"{name}_Label", img, (0.2, 0.2 * img.size[1] / img.size[0]), P(0.18, 0.249, 1.45),
          (90, 0, yaw))
    # Transmitter manifold: vertical stainless tubing with two Rosemount housings
    tm = MeshBuilder(f"{name}_Transmitters")
    tm.rod(P(-0.42, 0.18, 0.5), P(-0.42, 0.18, 1.9), 0.008, M["stainless"], 8)
    tm.rod(P(-0.42, 0.18, 1.2), P(-0.25, 0.18, 1.2), 0.008, M["stainless"], 8)
    for h, tag in ((1.32, "PT-1"), (1.0, "TT-1")):
        c = P(-0.42, 0.3, h)
        tm.rod(P(-0.42, 0.18, h), c, 0.012, M["stainless"], 8)
        tm.rod(c - n * 0.06, c + n * 0.06, 0.045, M["rosemount"], 20)          # electronics housing
        tm.rod(c + n * 0.06, c + n * 0.075, 0.04, M["rosemount"], 20)
        tm.rod(c - Vector((0, 0, 0.12)), c - Vector((0, 0, 0.03)), 0.03, M["rosemount"], 12)
    out["transmitters"] = tm.build(collection=collection)
    # LCD faces from the close-up photo of PT-1 (reads 2242 PSI)
    lcd = screen_texture(f"{name}_lcd", docs["pt1_photo"], (0.3, 0.27, 0.7, 0.72), (256, 256))
    decal(f"{name}_PT1_LCD", lcd, (0.07, 0.07), P(-0.42, 0.377, 1.32), (90, 0, yaw))
    out["anchors"] = {"PT-1": P(-0.42, 0.42, 1.42), "TT-1": P(-0.42, 0.42, 1.08),
                      "hose": P(-0.25, 0.25, 0.4)}
    return out


def deadweight(M, name, location, yaw, docs, collection="Test station"):
    """Calscan Falcon electronic deadweight (DDW-007) lying on the floor on its hose."""
    mb = MeshBuilder(name)
    x, y, z = location
    mb.rod((x, y, z), (x, y, z + 0.06), 0.08, M["falcon_blue"], 28)
    mb.rod((x, y, z + 0.06), (x, y, z + 0.068), 0.074, M["falcon_white"], 28)
    mb.rod((x + 0.09, y, z + 0.03), (x + 0.16, y, z + 0.03), 0.012, M["stainless"], 10)
    obj = mb.build(collection=collection)
    face = screen_texture(f"{name}_face", docs["ddw_photo"], (0.12, 0.16, 0.95, 0.98), (256, 256))
    decal(f"{name}_Face", face, (0.15, 0.15), (x, y, z + 0.0685), (0, 0, yaw))
    return obj


# ------------------------------------------------------------------ shop furniture

def stud_pallet(M, stud_pre, origin, yaw, rng, rows=2, per_row=12, collection="Props"):
    x, y = origin
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    mb = MeshBuilder("Pallet")
    for k in range(3):
        v = -0.45 + k * 0.45
        mb.box((x - s * v, y + c * v, 0.05), (0.09, 1.0, 0.1), M["wood"], rotation=(0, 0, yaw + 90))
    for k in range(7):
        v = -0.5 + k * (1.0 / 6)
        mb.box((x + c * v, y + s * v, 0.115), (0.1, 1.0, 0.025), M["wood"], rotation=(0, 0, yaw + 90))
    mb.box((x, y, 0.131), (1.05, 0.95, 0.004), M["cardboard"], rotation=(0, 0, yaw))
    mb.build(collection=collection)
    for r in range(rows):
        for i in range(per_row):
            u = -0.45 + i * 0.075
            v = -0.3 + r * 0.32
            px, py = x + c * u - s * v, y + s * u + c * v
            instance(stud_pre, "LooseStud", (px, py, 0.16), (90, 0, yaw + rng.uniform(-3, 3)), collection=collection)


def cribbing(M, origin, yaw, length=1.4, collection="Props"):
    x, y = origin
    mb = MeshBuilder("Cribbing")
    for k, dz in enumerate((0.0, 0.09)):
        mb.box((x, y + k * 0.12, 0.045 + dz), (length, 0.14, 0.09), M["wood"], rotation=(0, 0, yaw))
    return mb.build(collection=collection)


def grating(M, origin, size, yaw, collection="Props"):
    """Expanded-metal floor grating panel: textured cutout so the diamond mesh shows."""
    n = 256
    yy, xx = np.mgrid[0:n, 0:n] / n * 8
    d = np.abs((xx + yy) % 1 - 0.5) + np.abs((xx - yy) % 1 - 0.5)
    a = (d > 0.38).astype(np.float32)
    rgba = np.zeros((n, n, 4), np.float32)
    rgba[..., :3] = [0.32, 0.28, 0.24]
    rgba[..., 3] = a
    tex = texture("grating_c", rgba, fmt="png")
    mat = material("grating", texture=tex, texture_size=0.6, cutout=True, roughness=0.6, metallic=0.6)
    w, h = size
    x, y = origin
    return plane("Grating", (w, h), (x, y, 0.012), (0, 0, yaw), material=mat, collection=collection)


def hose(M, name, points, radius=0.012, mat_key="hose", collection="Hoses"):
    """Flexible hose along a smooth path through `points` (lies on the floor where z = 0)."""
    mb = MeshBuilder(name)
    pts = [Vector(p) for p in points]
    # Catmull-Rom through the points
    dense = []
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        for k in range(8):
            t = k / 8
            t2, t3 = t * t, t * t * t
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                                (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    dense.append(pts[-1])
    for p in dense:
        p.z = max(p.z, radius)
    mb.tube(dense, radius, M[mat_key], bend_radius=radius * 2, segments=8, arc_steps=2)
    return mb.build(collection=collection)


def jack_stand(M, location, height=0.75, collection="Props"):
    """Red tripod pipe jack stand with a threaded post."""
    x, y = location
    mb = MeshBuilder("JackStand")
    top = Vector((x, y, height * 0.55))
    for k in range(3):
        a = 2 * math.pi * k / 3
        mb.rod((x + 0.32 * math.cos(a), y + 0.32 * math.sin(a), 0.01), top, 0.012, M["red"], 6)
    mb.rod(top - Vector((0, 0, 0.05)), Vector((x, y, height)), 0.016, M["steel_dark"], 8)
    mb.box((x, y, height), (0.12, 0.05, 0.03), M["steel_dark"])
    return mb.build(collection=collection)


def booth(M, origin, size, collection="Props"):
    """White storage room/booth in the far corner (seen past the spread in photo a)."""
    x, y = origin
    w, d, h = size
    mb = MeshBuilder("Booth")
    mb.box((x, y, h / 2), (w, d, h), M["booth"])
    mb.box((x, y, h + 0.05), (w + 0.1, d + 0.1, 0.1), M["steel_dark"])
    return mb.build(collection=collection)


def cabinet(M, origin, yaw, color_key="cabinet_yellow", size=(0.9, 0.5, 1.65), collection="Props"):
    x, y = origin
    w, d, h = size
    mb = MeshBuilder("Cabinet")
    mb.box((x, y, h / 2), (w, d, h), M[color_key], rotation=(0, 0, yaw))
    return mb.build(collection=collection)


def bench(M, origin, yaw, length=2.4, collection="Props"):
    x, y = origin
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    mb = MeshBuilder("Bench")
    mb.box((x, y, 0.9), (length, 0.75, 0.05), M["steel_dark"], rotation=(0, 0, yaw))
    for u in (-length / 2 + 0.05, length / 2 - 0.05):
        for v in (-0.33, 0.33):
            mb.box((x + c * u - s * v, y + s * u + c * v, 0.45), (0.05, 0.05, 0.9), M["steel_dark"])
    mb.box((x, y, 0.15), (length - 0.1, 0.7, 0.03), M["steel_dark"], rotation=(0, 0, yaw))
    # bins and tools on the bench
    for k, col in enumerate(("bin_blue", "red", "bin_blue", "steel_dark")):
        u = -length / 2 + 0.35 + k * 0.5
        mb.box((x + c * u, y + s * u, 0.99), (0.36, 0.22, 0.14), M[col], rotation=(0, 0, yaw))
    return mb.build(collection=collection)


def welder(M, origin, yaw, collection="Props"):
    x, y = origin
    mb = MeshBuilder("Welder")
    mb.box((x, y, 0.45), (0.55, 0.8, 0.7), M["cabinet_yellow"], rotation=(0, 0, yaw))
    mb.box((x, y, 0.06), (0.6, 0.9, 0.06), M["steel_dark"], rotation=(0, 0, yaw))
    return mb.build(collection=collection)


def duct(M, collection="Building"):
    """Galvanized supply duct along the upper west wall (photo a, top left)."""
    mb = MeshBuilder("Duct")
    x = -shop.W / 2 + 0.9
    mb.box((x, 9.0, 7.35), (1.2, 16.0, 0.75), M["duct"])
    for y in (2.5, 7.0, 11.5, 15.5):
        mb.box((x + 0.62, y, 7.2), (0.05, 0.6, 0.35), M["steel_dark"])
    return mb.build(collection=collection)
