"""Buildings, vehicles and props for the North Field Build campus. Everything is a MeshBuilder
object or a prefab; world.py places them. Dimensions are metres."""

import math

import numpy as np

from harness import *  # noqa: F403
from harness import industrial as ind


def _ground(name, cells, a, b, size, seed, rough=0.95, fine=0.0):
    """Tileable mottled ground texture (two colours mixed by noise) covering `size` metres."""
    n = 512
    t = fbm_noise(n, cells, 5, seed)
    if fine:
        t = t * (1 - fine) + value_noise(n, 96, seed + 1) * fine
    px = colorize(contrast(t, 0.25, 0.8), a, b)
    return material(name, texture=texture(f"{name}_c", px), texture_size=size, roughness=rough)


def mats():
    M = ind.mats()
    M["gravel"] = _ground("gravel", 5, "#aea797", "#cfc8b9", 6.0, 11, fine=0.5)
    M["grass"] = _ground("grass", 7, "#5f7e3b", "#86a053", 70.0, 5, fine=0.45)
    M["dirt"] = _ground("dirt", 4, "#7c6446", "#a08a6a", 10.0, 9, fine=0.35)
    M["spoil"] = material("spoil", "#6e5a42", roughness=0.95)
    M["liner"] = material("liner_white", "#dcdcd8", roughness=0.45, metallic=0.2)
    M["liner_blue"] = material("liner_blue", "#3a5f9a", roughness=0.45, metallic=0.2)
    M["trim"] = material("trim_blue", "#2c4a7c", roughness=0.5)
    M["office_wall"] = material("office_wall", "#d8d3c8", roughness=0.8)
    M["window"] = material("window", "#2a3f5a", roughness=0.1, metallic=0.6)
    M["door"] = material("door_grey", "#9ea4a8", roughness=0.4, metallic=0.5)
    M["rollup"] = material("rollup_door", "#c4c7c9", roughness=0.35, metallic=0.7)
    M["trailer"] = material("trailer_white", "#ecebe6", roughness=0.55)
    M["trailer_trim"] = material("trailer_trim", "#8a2b22", roughness=0.6)
    M["timber"] = material("timber", "#a07c4f", roughness=0.9)
    M["cs_pipe"] = material("cs_pipe_black", "#2e2f31", roughness=0.55, metallic=0.4)
    M["primer"] = material("primer_red", "#8f3b2c", roughness=0.6)
    M["fence"] = material("fence_galv", "#9da3a6", roughness=0.4, metallic=0.8)
    M["excavator"] = material("excavator_yellow", "#e0a419", roughness=0.45)
    M["truck_red"] = material("truck_red", "#a8261f", roughness=0.35, metallic=0.4)
    M["pickup"] = material("pickup_white", "#eceef0", roughness=0.35, metallic=0.5)
    M["tape"] = material("warning_tape", "#f0c020", roughness=0.6)
    M["cone"] = material("traffic_cone", "#ff6a1a", roughness=0.6)
    M["pole"] = material("light_pole", "#7a7f83", roughness=0.5, metallic=0.6)
    M["lamp_head"] = material("lamp_head", "#2a2d30", roughness=0.5)
    M["mesh"] = material("fence_mesh", "#aeb4b8", roughness=0.5, metallic=0.6, alpha=0.35)
    M["concrete"] = material("concrete", "#a7a39a", roughness=0.9)
    M["asphalt"] = _ground("asphalt_road", 3, "#3a3b3d", "#4a4a4c", 8.0, 2, rough=0.8, fine=0.6)
    M["tree_leaves"] = material("leaves", "#5f7a3c", roughness=0.85)
    return M


def patch(name, x0, y0, x1, y1, height, mat, step=1.0, lift=0.02, collection="Ground"):
    """Rectangular heightfield patch following `height`, slightly above the terrain (the
    field site's dirt, with the trench cut through it)."""
    import bmesh
    from harness.core import _from_bmesh, _place
    nx, ny = max(1, int((x1 - x0) / step)), max(1, int((y1 - y0) / step))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
        v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
        v.co.z = height(v.co.x, v.co.y) + lift
    obj = _from_bmesh(name, bm, mat, False)
    return _place(obj, (0, 0, 0), (0, 0, 0), (1, 1, 1), collection)


def sign(name, text, width, location, rotation, color="#1d3b6b", collection="Signs"):
    """Lettering on a wall (text_image -> decal). rotation picks the facing: (90,0,0) south,
    (90,0,180) north, (90,0,90) east, (90,0,-90) west."""
    px = text_image(text, color=color, height=96, bold=True)
    img = texture(f"sign_{name}", px)
    h, w = px.shape[:2]
    return decal(f"Sign_{name}", img, (width, width * h / w), location, rotation, collection=collection)


# ------------------------------------------------------------------ buildings

def office(M, centre, size=(34, 18), storeys=2, collection="Office"):
    """Two-storey office: pale walls, window bands, a canopy over the north door."""
    x, y = centre
    w, d = size
    H = 3.6 * storeys
    mb = MeshBuilder("Office")
    mb.box((x, y, H / 2), (w, d, H), M["office_wall"])
    mb.box((x, y, H + 0.25), (w + 0.8, d + 0.8, 0.5), M["roof"])
    mb.box((x, y, H + 0.9), (6, 4, 0.9), M["roof"])            # roof-top units
    for s in range(storeys):
        z = 3.6 * s + 1.9
        for side in (-1, 1):
            mb.box((x, y + side * d / 2, z), (w - 4, 0.12, 1.5), M["window"])
            mb.box((x + side * w / 2, y, z), (0.12, d - 4, 1.5), M["window"])
    mb.box((x, y + d / 2, 1.1), (2.4, 0.2, 2.2), M["door"])
    mb.box((x, y + d / 2 + 1.5, 2.9), (6, 3.2, 0.2), M["trim"])  # canopy
    for px in (-2.6, 2.6):
        mb.rod((x + px, y + d / 2 + 2.9, 0), (x + px, y + d / 2 + 2.9, 2.9), 0.08, M["trim"])
    mb.slab(x - w / 2 - 1, y - d / 2 - 1, x + w / 2 + 1, y + d / 2 + 3, 0.05, 0.1, M["concrete"])
    obj = mb.build(collection=collection)
    sign("office", "PURNELL ENERGY SERVICES", 16, (x, y + d / 2 + 0.02, H - 0.8), (90, 0, 180))
    return obj


def warehouse(M, centre, size=(52, 28), height=9.0, label="VENDOR", door_side=-1, collection="Vendor"):
    """Steel-clad warehouse with a roll-up dock door on the south (door_side=-1) wall."""
    x, y = centre
    w, d = size
    mb = MeshBuilder(f"Warehouse_{label}")
    mb.box((x, y, height / 2), (w, d, height), M["liner"])
    mb.box((x, y, 1.0), (w + 0.1, d + 0.1, 2.0), M["liner_blue"])        # wainscot band
    mb.box((x, y, height + 0.3), (w + 1.0, d + 1.0, 0.6), M["roof"])
    # Roll-up doors and a man door on the dock wall.
    yd = y + door_side * d / 2
    for dx in (-10, 0, 10):
        mb.box((x + dx, yd + door_side * 0.08, 2.6), (6, 0.16, 5.2), M["rollup"])
    mb.box((x + 16, yd + door_side * 0.08, 1.1), (1.0, 0.16, 2.2), M["door"])
    mb.slab(x - w / 2, yd + door_side * 8, x + w / 2, yd, 0.05, 0.1, M["concrete"])
    obj = mb.build(collection=collection)
    sign(label.lower(), label, 14, (x, yd + door_side * 0.02, height - 1.4), (90, 0, 0 if door_side < 0 else 180))
    return obj


def fab_shop(M, centre, collection="Fab shop"):
    """Purnell's shop footprint: a 50 x 100 ft bay (15.24 x 30.48 m), eave 9.1 m, white liner,
    with two sectional doors on the south end, a rolling door on the east wall, and a bridge
    crane runway inside (the same proportions as worlds/purnell-test-shop)."""
    x, y = centre
    W, L, H = 15.24, 30.48, 9.1
    mb = MeshBuilder("FabShop")
    mb.box((x, y, H / 2), (W, L, H), M["liner"])
    mb.box((x, y, 0.9), (W + 0.1, L + 0.1, 1.8), M["liner_blue"])
    # Low-pitch gable roof
    for s in (-1, 1):
        mb.box((x + s * W / 4, y, H + 0.45), (W / 2 + 0.6, L + 0.8, 0.3), M["roof"],
               rotation=(0, -s * 6, 0))
    ys = y - L / 2
    for dx in (-3.8, 3.8):
        mb.box((x + dx, ys - 0.09, 2.5), (4.3, 0.18, 5.0), M["rollup"])
    mb.box((x + W / 2 + 0.09, y + 6, 2.6), (0.18, 5.0, 5.2), M["rollup"])
    mb.box((x - W / 2 - 0.09, y - 10, 1.1), (0.18, 1.0, 2.2), M["door"])
    # Apron and the yard where spools are fitted and tested.
    mb.slab(x - W / 2 - 6, ys - 24, x + W / 2 + 6, ys, 0.05, 0.1, M["concrete"])
    obj = mb.build(collection=collection)
    sign("fab", "FAB SHOP", 8, (x, ys - 0.02, H - 1.5), (90, 0, 0))
    sign("fab_east", "PURNELL", 9, (x + W / 2 + 0.02, y - 6, H - 1.6), (90, 0, 90))
    return obj


def trailer(M, name, centre, yaw=0.0, size=(14.6, 3.6, 3.2), label=None, collection="QC"):
    """Site office trailer on blocks, steps up to its door."""
    x, y = centre
    w, d, h = size
    mb = MeshBuilder(name)
    mb.box((0, 0, 0.6 + h / 2), (w, d, h), M["trailer"])
    mb.box((0, 0, 0.6 + 0.25), (w + 0.05, d + 0.05, 0.5), M["trailer_trim"])
    mb.box((0, 0, 0.6 + h + 0.08), (w + 0.3, d + 0.3, 0.16), M["roof"])
    for bx in (-w / 3, 0, w / 3):
        mb.box((bx, 0, 0.3), (0.5, d - 0.4, 0.6), M["dark"])
    for wx in (-w / 2 + 2.5, -w / 2 + 6.0, w / 2 - 2.5):
        mb.box((wx, -d / 2 - 0.03, 0.6 + h * 0.6), (1.4, 0.06, 1.0), M["window"])
    mb.box((w / 2 - 5.0, -d / 2 - 0.05, 0.6 + 1.05), (0.9, 0.1, 2.1), M["door"])
    for i in range(3):   # steps
        mb.box((w / 2 - 5.0, -d / 2 - 0.5 - i * 0.3, 0.6 - i * 0.2 - 0.1), (1.0, 0.3, 0.2), M["grating"])
    obj = mb.build(location=(x, y, 0), rotation=(0, 0, yaw), collection=collection)
    if label:
        sign(name.lower(), label, 5, (x - 1.5, y - d / 2 - 0.04, 0.6 + h - 0.5), (90, 0, 0), color="#8a2b22")
    return obj


# ------------------------------------------------------------------ vehicles

def flatbed_prefab(M, name="Flatbed", color=None):
    """Tandem flatbed truck, cab at +X; the deck top is at z = 1.25."""
    paint = color or M["truck_red"]
    mb = MeshBuilder(name)
    mb.box((5.6, 0, 2.0), (2.4, 2.5, 2.6), paint)                 # cab
    mb.box((5.2, 0, 2.9), (0.9, 2.3, 0.9), M["glass"])              # windscreen
    mb.box((7.0, 0, 1.3), (0.5, 2.5, 1.0), paint)                   # hood
    mb.box((0.8, 0, 1.15), (12.0, 2.55, 0.2), M["dark"])            # deck
    mb.box((0.8, 0, 0.75), (11.5, 1.0, 0.6), M["dark"])             # frame
    for wx in (-4.5, -3.1, 4.6, 6.4):
        for wy in (-1.05, 1.05):
            mb.rod((wx, wy - 0.3, 0.52), (wx, wy + 0.3, 0.52), 0.52, M["fan"], 16)
    for s in (-1, 1):   # stake pockets
        for sx in (-4, -1, 2, 5):
            mb.box((sx, s * 1.2, 1.5), (0.1, 0.1, 0.5), M["steel"])
    return prefab(mb.build())


def pickup_prefab(M, name="Pickup", color=None):
    paint = color or M["pickup"]
    mb = MeshBuilder(name)
    mb.box((0.4, 0, 0.95), (5.6, 2.0, 0.7), paint)
    mb.box((1.2, 0, 1.6), (1.9, 1.85, 0.65), paint)
    mb.box((1.9, 0, 1.6), (0.3, 1.7, 0.55), M["glass"])
    mb.box((-1.4, 0, 1.4), (2.3, 1.85, 0.25), M["dark"])            # box sides top
    for wx in (-1.6, 1.7):
        for wy in (-0.9, 0.9):
            mb.rod((wx, wy - 0.15, 0.4), (wx, wy + 0.15, 0.4), 0.4, M["fan"], 14)
    return prefab(mb.build())


def excavator(M, location, yaw, boom_down=True, collection="Field"):
    """Tracked excavator; the boom reaches over the trench when boom_down."""
    mb = MeshBuilder("Excavator")
    for s in (-1, 1):
        mb.box((0, s * 1.4, 0.55), (4.6, 0.9, 1.1), M["dark"])
    mb.box((0, 0, 1.25), (2.6, 2.2, 0.4), M["dark"])
    mb.box((-0.4, 0, 2.15), (3.6, 2.8, 1.4), M["excavator"])
    mb.box((1.1, 0.9, 2.5), (1.5, 1.1, 1.9), M["glass"])
    mb.box((-2.0, 0, 2.0), (1.2, 2.6, 1.2), M["excavator"])          # counterweight
    a = (1.2, -0.3, 2.6)
    b = (4.8, -0.3, 5.2)
    c = (7.8, -0.3, 2.2) if boom_down else (8.4, -0.3, 4.4)
    mb.beam(a, b, 0.55, M["excavator"])
    mb.beam(b, c, 0.4, M["excavator"])
    mb.box(c, (1.0, 1.2, 1.0), M["dark"])                             # bucket
    return mb.build(location=location, rotation=(0, 0, yaw), collection=collection)


# ------------------------------------------------------------------ props

def pipe_joint_prefab(M, nps_od=0.273, length=12.0, mat=None, name="PipeJoint"):
    mb = MeshBuilder(name)
    mb.rod((0, 0, 0), (length, 0, 0), nps_od / 2, mat or M["cs_pipe"], 24)
    return prefab(mb.build())


def pipe_rack(M, origin, yaw, length=12.4, levels=3, collection="Vendor"):
    """A-frame pipe rack with pipe joints stacked on it (the vendor's yard)."""
    mb = MeshBuilder("PipeRack")
    for ux in (0.0, length / 2, length):
        for s in (-1, 1):
            mb.rod((ux, s * 1.4, 0), (ux, s * 0.3, 3.2), 0.07, M["steel"], 8)
        for lv in range(levels):
            z = 0.7 + lv * 0.9
            mb.box((ux, 0, z), (0.15, 2.4 - lv * 0.5, 0.15), M["steel"])
    rack = mb.build(location=origin, rotation=(0, 0, yaw), collection=collection)
    return rack


def stack_pipes(M, joint, origin, yaw, levels=3, per_level=(5, 4, 3), length=12.0, collection="Vendor"):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    k = 0
    for lv in range(levels):
        n = per_level[min(lv, len(per_level) - 1)]
        for i in range(n):
            vy = (i - (n - 1) / 2) * 0.32
            z = 0.78 + lv * 0.9 + 0.14
            x = origin[0] + 0.2 * c - vy * s
            y = origin[1] + 0.2 * s + vy * c
            instance(joint, f"Pipe_{origin[0]:.0f}_{origin[1]:.0f}_{k}", (x, y, z), (0, 0, yaw), collection=collection)
            k += 1


def skid_prefab(M):
    mb = MeshBuilder("Skid")
    mb.box((0, 0, 0.1), (0.25, 1.4, 0.2), M["timber"])
    mb.box((0, 0, 0.3), (0.25, 1.4, 0.2), M["timber"])
    return prefab(mb.build())


def stand_prefab(M):
    """Pipe stand: a cone base with a saddle (like the shop's), saddle at 0.55 m."""
    mb = MeshBuilder("Stand")
    mb.cylinder((0, 0, 0), 0.32, 0.45, M["steel"], segments=16, radius_top=0.12)
    mb.rod((0, 0, 0.45), (0, 0, 0.5), 0.1, M["steel"], 12)
    mb.box((0, 0, 0.53), (0.35, 0.12, 0.06), M["steel"])
    return prefab(mb.build())


def light_pole_prefab(M, height=10.0):
    mb = MeshBuilder("LightPole")
    mb.rod((0, 0, 0), (0, 0, height), 0.12, M["pole"], 10, radius_b=0.08)
    mb.beam((0, 0, height), (1.6, 0, height + 0.2), 0.12, M["pole"])
    mb.box((1.6, 0, height + 0.1), (0.9, 0.4, 0.2), M["lamp_head"])
    return prefab(mb.build())


def fence(M, points, height=1.8, post_step=3.0, collection="Fences"):
    """Chain-link fence along points: posts, top rail and a translucent mesh panel."""
    mb = MeshBuilder("Fence")
    pts = [np.array(p, float) for p in points]
    for a, b in zip(pts, pts[1:]):
        d = b - a
        n = max(1, int(round(np.linalg.norm(d) / post_step)))
        for i in range(n + 1):
            p = a + d * i / n
            mb.rod((p[0], p[1], 0), (p[0], p[1], height), 0.03, M["fence"], 6)
        mb.rod((a[0], a[1], height), (b[0], b[1], height), 0.02, M["fence"], 6)
        mid = (a + b) / 2
        yaw = math.degrees(math.atan2(d[1], d[0]))
        mb.box((mid[0], mid[1], height / 2), (np.linalg.norm(d), 0.01, height - 0.1), M["mesh"],
               rotation=(0, 0, yaw))
    return mb.build(collection=collection)


def cone_prefab(M):
    mb = MeshBuilder("Cone")
    mb.box((0, 0, 0.02), (0.4, 0.4, 0.04), M["dark"])
    mb.cylinder((0, 0, 0.04), 0.15, 0.7, M["cone"], segments=10, radius_top=0.04)
    return prefab(mb.build())


def crate_prefab(M):
    mb = MeshBuilder("Crate")
    mb.box((0, 0, 0.45), (1.6, 1.1, 0.9), M["timber"])
    for dx in (-0.6, 0, 0.6):
        mb.box((dx, 0, 0.45), (0.08, 1.14, 0.94), M["dark"])
    return prefab(mb.build())


def spoil_ridge(M, x0, x1, y, height=1.4, width=4.0, collection="Field"):
    """Excavated material heaped along the trench, as a lumpy ridge of spheres."""
    mb = MeshBuilder("Spoil")
    x = x0
    i = 0
    while x < x1:
        r = width / 2 * (0.85 + 0.3 * math.sin(i * 1.7))
        mb.sphere((x, y + 0.3 * math.sin(i * 2.3), height * 0.25), r, M["spoil"], 2, (1, 1, height / r * 0.6))
        x += r * 0.9
        i += 1
    return mb.build(collection=collection)
