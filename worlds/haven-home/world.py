"""Haven Home: the seven-room apartment behind the Haven Home Assistant dashboard, as a
production-quality cutaway model.

The plan matches Haven's `rooms` table exactly (Blender y = -Haven z, so the exported .glb lands
on Haven's own axes), and every part the dashboard drives from live Home Assistant state carries
glTF extras the Haven viewer looks for:

    haven_room = "<room>"                 room floors (click to select a room)
    haven_light = "<room>", haven_power   light anchors: the viewer puts a point light there
    haven_glow = "<room>"                 emissive parts that brighten with the room's lights
    haven_role = "tv_screen" | "blind" | "fan_rotor" | "monitor"
    haven_cutaway = "north" | "west"      tall wall parts the viewer hides when the camera is behind them
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mathutils import Euler, Matrix, Vector  # noqa: E402

from harness import *  # noqa: E402

import surfaces  # noqa: E402

META = {
    "title": "Haven Home",
    "description": "The seven-room apartment behind the Haven Home Assistant dashboard: a "
                   "furnished architectural cutaway with live-controllable lights, TV, blinds and fan.",
    "tags": ["interior", "architecture", "home-assistant"],
    "seed": 7,
    "render": {"res": "1600x900", "samples": 64, "glare": 0.25},
    "export": {"draco": False},   # the Haven panel ships without a Draco decoder
    "viewer": {"bloom": 0.35},
}

F = 0.02          # finished floor level
WALL_H = 2.7      # full-height exterior walls (north and west)
CUT_H = 1.2       # partitions and near walls are cut here, like an architectural section
X_W, X_A, X_B, X_C, X_E = -7.18, -2.05, 0.83, 3.67, 7.18
Y_S, Y_E, Y_D, Y_N = -5.17, -1.18, -0.19, 5.17

ROOMS = {   # floor regions, bounded by wall centre lines
    "living": (X_W, Y_S, X_A, Y_D), "dining": (X_W, Y_D, X_A, Y_N),
    "hall": (X_A, Y_S, X_B, Y_D), "kitchen": (X_A, Y_D, X_B, Y_N),
    "bedroom": (X_B, Y_E, X_E, Y_N), "bath": (X_B, Y_S, X_C, Y_E), "office": (X_C, Y_S, X_E, Y_E),
}

M = {}
LIGHTS = []   # (room, location, power) for the summary


def tag(obj, **props):
    for k, v in props.items():
        obj[k] = v
    return obj


def rot(deg):
    return Euler((0, 0, math.radians(deg))).to_matrix().to_4x4()


# ------------------------------------------------------------------ architecture

def plinth():
    mb = MeshBuilder("Plinth")
    mb.rounded_box((0, 0, -0.06), (14.56, 10.54, 0.12), M["limestone"], 0.02, 2)
    mb.box((0, 0, -0.155), (14.44, 10.42, 0.07), M["bronze"])
    mb.rounded_box((0, 0, -0.29), (14.62, 10.6, 0.2), M["plinth"], 0.05, 3)
    mb.rounded_box((0, 0, -0.455), (14.3, 10.28, 0.13), M["black_metal"], 0.03, 2)
    mb.build(collection="Architecture")
    led = MeshBuilder("Plinth.LED")
    for y in (-5.215, 5.215):
        led.box((0, y, -0.185), (14.3, 0.012, 0.012), M["led"])
    for x in (-7.225, 7.225):
        led.box((x, 0, -0.185), (0.012, 10.3, 0.012), M["led"])
    led.build(collection="Architecture")
    ground = plane("Studio", (70, 56), (0, 0, -0.9), material=M["studio"], backdrop=True,
                   collection="Architecture")
    return ground


def floors():
    finishes = {"kitchen": M["marble_floor"], "bath": M["tile"]}
    for room, (x0, y0, x1, y1) in ROOMS.items():
        mb = MeshBuilder(f"Floor.{room}")
        mb.box(((x0 + x1) / 2, (y0 + y1) / 2, F / 2), (x1 - x0, y1 - y0, F),
               finishes.get(room, M["oak_floor"]))
        tag(mb.build(collection="Architecture"), haven_room=room)


def wall_run(name, axis, pos, a0, a1, height, thick, openings=(), split=None, mat=None, cap=False,
             cutaway=None):
    """A straight wall along x (axis='x', at y=pos) or y (axis='y', at x=pos) from a0 to a1.
    openings: (c0, c1, sill, head) windows/doors. split: height where the wall divides into a
    lower object and an upper one tagged haven_cutaway. cap: dark section cap on top."""
    mat = mat or M["plaster"]
    cuts = sorted({a0, a1, *[c for o in openings for c in o[:2]]})
    bands = [(0.0, split, ""), (split, height, ".Upper")] if split else [(0.0, height, "")]
    for z0, z1, suffix in bands:
        mb = MeshBuilder(name + suffix)
        for c0, c1 in zip(cuts, cuts[1:]):
            hole = next((o for o in openings if o[0] <= c0 and c1 <= o[1]), None)
            spans = [(0.0, hole[2]), (hole[3], height)] if hole else [(0.0, height)]
            for s0, s1 in spans:
                lo, hi = max(s0, z0), min(s1, z1)
                if hi - lo < 1e-4:
                    continue
                mid, length = (c0 + c1) / 2, c1 - c0
                if axis == "x":
                    mb.box((mid, pos, (lo + hi) / 2), (length, thick, hi - lo), mat)
                else:
                    mb.box((pos, mid, (lo + hi) / 2), (thick, length, hi - lo), mat)
        if cap and not suffix:
            top = z1
            if axis == "x":
                mb.box(((a0 + a1) / 2, pos, top + 0.006), (a1 - a0, thick + 0.004, 0.012), M["cut"])
            else:
                mb.box((pos, (a0 + a1) / 2, top + 0.006), (thick + 0.004, a1 - a0, 0.012), M["cut"])
        obj = mb.build(collection="Architecture")
        if suffix and cutaway:
            tag(obj, haven_cutaway=cutaway)


def window(name, axis, pos, c0, c1, sill, head, inside, cutaway=None, mullions=1):
    """Slim bronze-framed window in a wall opening; `inside` = +1/-1 side of the room."""
    mb = MeshBuilder(name)
    glass = MeshBuilder(name + ".Glass")
    fw, depth = 0.05, 0.07
    w = c1 - c0

    def put(builder, along, z, size_along, size_z, mat, off=0.0, depth_=depth):
        if axis == "x":
            builder.box((along, pos + off, z), (size_along, depth_, size_z), mat)
        else:
            builder.box((pos + off, along, z), (depth_, size_along, size_z), mat)
    mid = (c0 + c1) / 2
    put(mb, mid, head - fw / 2, w, fw, M["bronze"])
    put(mb, mid, sill + fw / 2, w, fw, M["bronze"])
    put(mb, c0 + fw / 2, (sill + head) / 2, fw, head - sill, M["bronze"])
    put(mb, c1 - fw / 2, (sill + head) / 2, fw, head - sill, M["bronze"])
    for i in range(1, mullions + 1):
        put(mb, c0 + w * i / (mullions + 1), (sill + head) / 2, 0.035, head - sill, M["bronze"])
    put(mb, mid, (sill + head) * 0.58, w, 0.03, M["bronze"])          # transom
    put(mb, mid, sill - 0.02, w + 0.1, 0.04, M["limestone"], inside * 0.09, 0.2)   # stone sill
    put(glass, mid, (sill + head) / 2, w - 0.04, head - sill - 0.04, M["glass"], 0, 0.012)
    for b in (mb, glass):
        obj = b.build(collection="Architecture")
        if cutaway and head > CUT_H:
            tag(obj, haven_cutaway=cutaway)


def walls():
    t_ext, t_int = 0.2, 0.12
    # North (full height, windows) and west (full height, one window): the far walls.
    north_windows = [(-5.9, -3.1, 0.5, 2.3), (1.2, 2.6, 0.7, 2.3)]
    wall_run("Wall.North", "x", Y_N, X_W - 0.1, X_E + 0.1, WALL_H, t_ext, north_windows,
             split=CUT_H, cutaway="north")
    window("Window.Dining", "x", Y_N, -5.9, -3.1, 0.5, 2.3, -1, "north", mullions=2)
    window("Window.Bedroom", "x", Y_N, 1.2, 2.6, 0.7, 2.3, -1, "north")
    west_windows = [(-3.9, -1.6, 0.85, 2.3)]
    wall_run("Wall.West", "y", X_W, Y_S - 0.1, Y_N + 0.1, WALL_H, t_ext, west_windows,
             split=CUT_H, cutaway="west")
    window("Window.Living", "y", X_W, -3.9, -1.6, 0.85, 2.3, 1, "west")
    # Near walls, cut low so the camera sees in. The entry is a gap in the south wall.
    wall_run("Wall.South", "x", Y_S, X_W - 0.1, X_E + 0.1, 0.36, t_ext, [(-1.25, -0.05, 0.0, 9)],
             cap=True)
    wall_run("Wall.East", "y", X_E, Y_S - 0.1, Y_N + 0.1, 1.05, t_ext, cap=True)
    # Partitions (cut at CUT_H), with door gaps.
    parts = [
        ("A.Living", "y", X_A, Y_S, -1.25), ("A.Dining1", "y", X_A, -0.35, 0.8),
        ("A.Dining2", "y", X_A, 2.3, Y_N),
        ("B.Bath", "y", X_B, Y_S, -1.05), ("B.Kitchen", "y", X_B, -0.25, Y_N),
        ("C.Office1", "y", X_C, Y_S, -3.45), ("C.Office2", "y", X_C, -2.15, Y_E),
        ("D.Living", "x", Y_D, X_W, -5.2), ("D.Dining", "x", Y_D, -3.84, X_A),
        ("D.Hall1", "x", Y_D, X_A, -0.86), ("D.Hall2", "x", Y_D, 0.19, X_B),
        ("E.Bath", "x", Y_E, X_B, 1.8), ("E.Mid", "x", Y_E, 2.78, 6.35), ("E.Office", "x", Y_E, 7.0, X_E),
    ]
    for name, axis, pos, a0, a1 in parts:
        wall_run(f"Wall.{name}", axis, pos, a0, a1, CUT_H, t_int, cap=True)
    # Skirting along the exterior walls' inner faces.
    sk = MeshBuilder("Skirting")
    for axis, pos, a0, a1, side in (("x", Y_N, X_W, X_E, -1), ("y", X_W, Y_S, Y_N, 1),
                                    ("y", X_E, Y_S, Y_N, -1), ("x", Y_S, X_W, -1.25, 1),
                                    ("x", Y_S, -0.05, X_E, 1)):
        off = pos + side * (t_ext / 2 + 0.008)
        mid, length = (a0 + a1) / 2, a1 - a0
        if axis == "x":
            sk.box((mid, off, F + 0.045), (length, 0.016, 0.09), M["lacquer"])
        else:
            sk.box((off, mid, F + 0.045), (0.016, length, 0.09), M["lacquer"])
    sk.build(collection="Architecture")
    # Entry threshold.
    th = MeshBuilder("Threshold")
    th.box((-0.65, Y_S, F / 2 + 0.004), (1.2, 0.22, F + 0.008), M["limestone"])
    th.build(collection="Architecture")


# ------------------------------------------------------------------ lighting fixtures

def light_anchor(room, location, power, blender_watts, radius=0.045, glow=True, cutaway=None):
    """A bulb: the Haven viewer puts a point light here and drives it from the room's lights.
    In the Blender render it is a real lamp."""
    mb = MeshBuilder(f"Light.{room}.{len([l for l in LIGHTS if l[0] == room])}")
    mb.sphere((0, 0, 0), radius, M["bulb"], 2)
    obj = mb.build(location=location, collection="Lights")
    tag(obj, haven_light=room, haven_power=power, haven_glow=room)
    if cutaway:
        tag(obj, haven_cutaway=cutaway)
    lamp(location, color="#ffcf96", power=blender_watts, bulb=0, collection="Lights")
    LIGHTS.append((room, location, power))
    return obj


def glow_part(name, builder_fn, room, location=(0, 0, 0), rotation=(0, 0, 0)):
    mb = MeshBuilder(name)
    builder_fn(mb)
    return tag(mb.build(location=location, rotation=rotation, collection="Lights"), haven_glow=room)


def drum_shade(mb, z, r_bottom, r_top, height):
    mb.lathe((0, 0, z), [(r_bottom, 0), (r_top, height)], M["shade_glow"], 40, cap=False)
    mb.lathe((0, 0, z), [(r_bottom - 0.004, 0), (r_top - 0.004, height)], M["shade_glow"], 40, cap=False)


def table_lamp(room, x, y, z, rotation=0, base_mat=None):
    base = MeshBuilder(f"TableLamp.{room}.{x:.1f}")
    base.lathe((0, 0, 0), [(0.07, 0), (0.1, 0.06), (0.11, 0.16), (0.08, 0.28), (0.03, 0.33),
                           (0.012, 0.36), (0.012, 0.42)], base_mat or M["ceramic"], 32)
    base.build(location=(x, y, z), collection="Lights", sharp_angle=50)
    glow_part(f"TableLamp.{room}.{x:.1f}.Shade", lambda mb: drum_shade(mb, 0.36, 0.2, 0.16, 0.22),
              room, (x, y, z))
    return light_anchor(room, (x, y, z + 0.47), 0.6, 2600, 0.035)


def floor_lamp(room, x, y, height=1.45, globe=False, power=0.8):
    mb = MeshBuilder(f"FloorLamp.{room}")
    mb.lathe((0, 0, 0), [(0.17, 0), (0.17, 0.012), (0.15, 0.03), (0, 0.035)], M["black_metal"], 40)
    mb.rod((0, 0, 0.03), (0, 0, height - (0.15 if globe else 0.25)), 0.012, M["brass"], 12)
    mb.build(location=(x, y, F), collection="Lights", sharp_angle=50)
    if globe:
        glow_part(f"FloorLamp.{room}.Globe",
                  lambda b: b.sphere((0, 0, 0), 0.15, M["shade_glow"], 3), room, (x, y, F + height))
        return light_anchor(room, (x, y, F + height), power, 3000, 0.03)
    glow_part(f"FloorLamp.{room}.Shade", lambda b: drum_shade(b, 0, 0.24, 0.21, 0.3), room,
              (x, y, F + height - 0.27))
    return light_anchor(room, (x, y, F + height - 0.1), power, 3400, 0.035)


def pendant(room, x, y, z, power, kind="dome", top=WALL_H):
    mb = MeshBuilder(f"Pendant.{room}.{x:.1f}")
    mb.lathe((0, 0, top - 0.02), [(0.06, 0), (0.06, 0.02), (0, 0.02)], M["brass"], 24)   # canopy
    mb.rod((0, 0, z + 0.12), (0, 0, top - 0.02), 0.004, M["matte_black"], 6)
    if kind == "dome":
        mb.lathe((0, 0, z), [(0.2, 0), (0.19, 0.04), (0.14, 0.1), (0.06, 0.15), (0.02, 0.17),
                             (0, 0.17)], M["brass"], 40, cap=False)
        mb.build(location=(x, y, 0), collection="Lights", sharp_angle=60)
        return light_anchor(room, (x, y, z + 0.06), power, 2800, 0.04)
    mb.build(location=(x, y, 0), collection="Lights")
    glow_part(f"Pendant.{room}.{x:.1f}.Globe", lambda b: b.sphere((0, 0, 0), 0.13, M["shade_glow"], 3),
              room, (x, y, z))
    return light_anchor(room, (x, y, z), power, 2600, 0.03)


# ------------------------------------------------------------------ shared pieces

def rug(name, cx, cy, w, d, mat, angle=0):
    mb = MeshBuilder(name)
    mb.rounded_slab((0, 0, 0.007), (w, d, 0.014), 0.04, mat)
    mb.build(location=(cx, cy, F), rotation=(0, 0, angle), collection="Soft")


def leaf_geometry(length, width, bend=0.25, fold=0.25, segs=6):
    verts, faces = [], []
    for i in range(segs + 1):
        t = i / segs
        w = width * math.sin(math.pi * min(1.0, t * 0.95 + 0.03)) ** 0.9
        x, z = length * t, -bend * t * t * length
        for s in (-1, 0, 1):
            verts.append((x, s * w / 2, z + fold * abs(s) * w / 2))
    for i in range(segs):
        for j in range(2):
            a = i * 3 + j
            faces.append((a, a + 3, a + 4, a + 1))
    return verts, faces


def add_leaf(mb, base, azimuth, elevation, length, width, mat, bend=0.25, fold=0.25, roll=0.0):
    v, f = leaf_geometry(length, width, bend, fold)
    m = (Matrix.Translation(base) @ rot(azimuth) @ Euler((roll, -math.radians(elevation), 0)).to_matrix().to_4x4())
    mb.faces(v, f, mat, matrix=m)


def pot(mb, r, h, mat, soil=True):
    mb.lathe((0, 0, 0), [(r * 0.72, 0), (r * 0.8, 0.02), (r, h * 0.92), (r * 1.04, h),
                         (r * 0.95, h), (r * 0.9, h * 0.9)], mat, 36, cap=False)
    mb.lathe((0, 0, 0), [(r * 0.72, 0), (0, 0)], mat, 36, cap=False)
    if soil:
        mb.lathe((0, 0, h * 0.86), [(r * 0.9, 0), (0, 0.01)], M["soil"], 24, cap=False)


def plant_prefabs(rng):
    P = {}
    # Fiddle-leaf fig: a tall trunk with broad, glossy leaves.
    mb = MeshBuilder("Plant.Fiddle")
    pot(mb, 0.21, 0.42, M["stoneware"])
    trunk = [(0, 0, 0.36), (0.02, 0.01, 0.8), (-0.03, 0.02, 1.25), (0.0, -0.02, 1.62)]
    mb.tube(trunk, 0.018, M["walnut"], bend_radius=0.3, segments=8)
    for i in range(30):
        t = 0.35 + 0.65 * (i / 29)
        p = Vector(trunk[1]).lerp(Vector(trunk[3]), t) if t > 0.5 else Vector(trunk[0]).lerp(Vector(trunk[2]), t)
        add_leaf(mb, p, i * 137.5, rng.uniform(5, 40), rng.uniform(0.2, 0.3), rng.uniform(0.15, 0.2),
                 M["leaf"] if i % 3 else M["leaf_dark"], bend=0.35, fold=0.3)
    P["fiddle"] = prefab(mb.build(sharp_angle=70))
    # Snake plant: upright sword leaves.
    mb = MeshBuilder("Plant.Snake")
    pot(mb, 0.16, 0.3, M["terracotta"])
    for i in range(16):
        a = i * 137.5
        r = rng.uniform(0.0, 0.08)
        base = (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0.26)
        add_leaf(mb, base, a, rng.uniform(70, 86), rng.uniform(0.45, 0.8), rng.uniform(0.05, 0.075),
                 M["leaf_dark"] if i % 2 else M["leaf"], bend=-0.05, fold=0.15, roll=rng.uniform(-0.5, 0.5))
    P["snake"] = prefab(mb.build(sharp_angle=70))
    # Small trailing plant (shelves, counters).
    mb = MeshBuilder("Plant.Small")
    pot(mb, 0.08, 0.13, M["ceramic"])
    for i in range(18):
        a = i * 137.5
        add_leaf(mb, (0, 0, 0.12), a, rng.uniform(-30, 45), rng.uniform(0.1, 0.16), rng.uniform(0.05, 0.08),
                 M["leaf_light"] if i % 2 else M["leaf"], bend=0.5, fold=0.2)
    P["small"] = prefab(mb.build(sharp_angle=70))
    return P


def book_prefabs():
    books = []
    for i, (h, d, t) in enumerate(((0.24, 0.17, 0.035), (0.21, 0.15, 0.025), (0.28, 0.2, 0.045),
                                   (0.19, 0.13, 0.02))):
        for c in range(len(M["book"])):
            if (i + c) % 2:
                continue
            mb = MeshBuilder(f"Book.{i}.{c}")
            mb.rounded_box((0, 0, h / 2), (t, d, h), M["book"][c], 0.003, 1)
            mb.box((0.0, 0.006, h / 2), (t - 0.004, d - 0.004, h - 0.008), M["paper"])
            books.append((prefab(mb.build()), h, d, t))
    return books


def shelf_books(books, rng, x0, x1, y, z, facing=0, name="Books", max_h=0.3):
    """Fill a shelf from x0 to x1 (along the shelf's own axis) with instanced books."""
    x = x0
    i = 0
    while True:
        b, h, d, t = books[rng.randrange(len(books))]
        if h > max_h:
            continue
        if x + t > x1:
            break
        lean = 0 if rng.random() > 0.08 else rng.choice((-8, 8))
        local = Vector((x + t / 2, 0, 0))
        world = rot(facing) @ local
        instance(b, f"{name}.{i}", (world.x + y[0], world.y + y[1], z), (0, lean, facing), 1.0,
                 collection="Decor")
        x += t + rng.uniform(0.0, 0.004)
        i += 1
        if rng.random() < 0.06:
            x += rng.uniform(0.05, 0.12)


# ------------------------------------------------------------------ living room

def living(P, rng):
    rug("Rug.Living", -4.65, -2.75, 3.5, 2.9, M["rug_living"])
    # L-shaped sectional in the south-west corner, facing the TV wall.
    sofa = MeshBuilder("Sofa")
    s, frame, legs = M["sofa"], M["sofa"], M["black_metal"]
    x_back, y0, y1 = -7.02, -4.98, -1.35          # main run along the west wall
    y_back, x1 = -4.98, -4.15                     # return along the south wall
    depth, base_h, base_z = 0.98, 0.22, F + 0.07
    sofa.rounded_box((x_back + depth / 2, (y0 + depth + y1) / 2, base_z + base_h / 2),
                     (depth, y1 - y0 - depth, base_h), frame, 0.04, 3)
    sofa.rounded_box(((x_back + x1) / 2, y_back + depth / 2, base_z + base_h / 2),
                     (x1 - x_back, depth, base_h), frame, 0.04, 3)
    for px, py in ((x_back + 0.08, y0 + 0.08), (x_back + 0.08, y1 - 0.08), (x_back + depth - 0.1, y1 - 0.08),
                   (x1 - 0.08, y_back + 0.08), (x1 - 0.08, y_back + depth - 0.1), (x_back + depth - 0.1, y_back + depth - 0.1)):
        sofa.rounded_box((px, py, F + 0.035), (0.05, 0.05, 0.07), legs, 0.01, 1)
    seat_z = base_z + base_h + 0.08
    # Seat cushions: corner, three along the wall run, two on the return.
    run = (y1 - 0.22) - (y0 + depth)
    for i in range(3):
        cy = y0 + depth + run * (i + 0.5) / 3
        sofa.rounded_box((x_back + 0.2 + (depth - 0.2) / 2, cy, seat_z), (depth - 0.24, run / 3 - 0.01, 0.17),
                         s, 0.05, 3, puff=0.025)
    sofa.rounded_box((x_back + 0.2 + (depth - 0.2) / 2, y_back + 0.2 + (depth - 0.2) / 2, seat_z),
                     (depth - 0.24, depth - 0.24, 0.17), s, 0.05, 3, puff=0.025)
    ret = (x1 - 0.22) - (x_back + depth)
    for i in range(2):
        cx = x_back + depth + ret * (i + 0.5) / 2
        sofa.rounded_box((cx, y_back + 0.2 + (depth - 0.2) / 2, seat_z), (ret / 2 - 0.01, depth - 0.24, 0.17),
                         s, 0.05, 3, puff=0.025)
    # Back frame and arms.
    sofa.rounded_box((x_back + 0.1, (y0 + y1 - 0.22) / 2, base_z + 0.36), (0.2, y1 - y0 - 0.22, 0.72), frame, 0.06, 3)
    sofa.rounded_box(((x_back + x1 - 0.22) / 2, y_back + 0.1, base_z + 0.36), (x1 - x_back - 0.22, 0.2, 0.72), frame, 0.06, 3)
    sofa.rounded_box((x_back + depth / 2, y1 - 0.11, base_z + 0.29), (depth, 0.22, 0.58), frame, 0.08, 3)
    sofa.rounded_box((x1 - 0.11, y_back + depth / 2, base_z + 0.29), (0.22, depth, 0.58), frame, 0.08, 3)
    # Back cushions, leaning back.
    for i in range(3):
        cy = y0 + depth + run * (i + 0.5) / 3
        sofa.rounded_box((x_back + 0.3, cy, seat_z + 0.28), (0.2, run / 3 - 0.02, 0.44), s, 0.07, 3,
                         rotation=(0, -9, 0), puff=0.03)
    sofa.rounded_box((x_back + 0.32, y_back + 0.32, seat_z + 0.28), (0.2, 0.5, 0.44), s, 0.07, 3,
                     rotation=(0, -9, 45), puff=0.03)
    for i in range(2):
        cx = x_back + depth + ret * (i + 0.5) / 2
        sofa.rounded_box((cx, y_back + 0.3, seat_z + 0.28), (ret / 2 - 0.02, 0.2, 0.44), s, 0.07, 3,
                         rotation=(9, 0, 0), puff=0.03)
    sofa.build(collection="Furniture", sharp_angle=55)
    # Throw pillows and a blanket over the arm.
    pil = MeshBuilder("Sofa.Pillows")
    for (px, py, rz, mat) in ((-6.55, -2.0, 80, M["rust"]), (-6.6, -3.2, 98, M["linen"]),
                              (-6.45, -4.45, 45, M["moss"]), (-5.3, -4.55, 5, M["ink"]),
                              (-4.75, -4.5, -12, M["linen"])):
        pil.rounded_box((px, py, seat_z + 0.26), (0.46, 0.13, 0.44), mat, 0.06, 3,
                        rotation=(-12, 0, rz), puff=0.05)
    pil.rounded_box((x_back + depth / 2, y1 - 0.13, base_z + 0.6), (depth + 0.02, 0.32, 0.03), M["clay"], 0.012, 2)
    pil.rounded_box((x_back + depth / 2, y1 + 0.005, base_z + 0.33), (0.7, 0.03, 0.52), M["clay"], 0.012, 2)
    pil.build(collection="Soft", sharp_angle=55)
    # Nested coffee tables: walnut and marble.
    ct = MeshBuilder("CoffeeTable")
    ct.lathe((-4.75, -2.6, F), [(0.04, 0), (0.06, 0.02), (0.06, 0.3)], M["black_metal"], 24)
    ct.lathe((-4.75, -2.6, F + 0.3), [(0.52, 0), (0.55, 0.03), (0.55, 0.045), (0.53, 0.06), (0, 0.06)], M["walnut"], 64)
    ct.lathe((-4.12, -1.98, F), [(0.05, 0), (0.05, 0.4)], M["black_metal"], 20)
    ct.lathe((-4.12, -1.98, F + 0.4), [(0.3, 0), (0.33, 0.025), (0.33, 0.035), (0, 0.035)], M["marble"], 56)
    ct.build(collection="Furniture", sharp_angle=50)
    decor = MeshBuilder("CoffeeTable.Decor")
    top = F + 0.36
    for i, (w, d, h, mat) in enumerate(((0.3, 0.22, 0.03, M["book"][2]), (0.27, 0.2, 0.025, M["book"][1]),
                                        (0.24, 0.18, 0.028, M["book"][4]))):
        decor.rounded_box((-4.95, -2.75, top + 0.015 + i * 0.028), (w, d, h), mat, 0.004, 1, rotation=(0, 0, 8 - i * 9))
    decor.lathe((-4.5, -2.45, top), [(0.05, 0), (0.08, 0.05), (0.07, 0.14), (0.03, 0.2), (0.035, 0.24)],
                M["stoneware"], 32, cap=False)
    decor.lathe((-4.12, -1.98, F + 0.435), [(0.11, 0), (0.13, 0.04), (0.12, 0.045)], M["ceramic"], 32)
    for k in range(3):
        decor.sphere((-4.12 + 0.05 * math.cos(k * 2.1), -1.98 + 0.05 * math.sin(k * 2.1), F + 0.5), 0.04,
                     M["fruit_orange"] if k else M["fruit_green"], 2)
    for k in range(5):
        a = k * 72
        decor.rod((-4.5, -2.45, top + 0.2), (-4.5 + 0.12 * math.cos(math.radians(a)), -2.45 + 0.12 * math.sin(math.radians(a)),
                                             top + 0.62 + 0.05 * (k % 2)), 0.004, M["walnut"], 5)
    decor.build(collection="Decor", sharp_angle=50)
    # Media console with fluted doors, and the TV.
    con = MeshBuilder("MediaConsole")
    cx, cy, w, d, h = -2.37, -3.05, 0.44, 2.1, 0.46
    con.rounded_box((cx, cy, F + 0.08 + h / 2), (w, d, h), M["walnut"], 0.015, 2)
    for i in range(42):
        con.rod((cx - w / 2 - 0.004, cy - d / 2 + 0.03 + i * (d - 0.06) / 41, F + 0.11),
                (cx - w / 2 - 0.004, cy - d / 2 + 0.03 + i * (d - 0.06) / 41, F + 0.08 + h - 0.03), 0.012, M["walnut"], 6)
    con.box((cx, cy, F + 0.04), (w - 0.1, d - 0.2, 0.08), M["black_metal"])
    con.build(collection="Furniture")
    tv = MeshBuilder("TV")
    tv_x, tv_z = -2.2, F + 1.05
    tv.rounded_box((tv_x, cy, tv_z), (0.04, 1.45, 0.83), M["matte_black"], 0.008, 2)
    tv.box((-2.24, cy, F + 0.55), (0.02, 0.3, 0.06), M["black_metal"])   # mount
    tv.box((cx - 0.05, cy, F + 0.08 + h + 0.035), (0.09, 0.9, 0.07), M["matte_black"])   # soundbar
    tv.build(collection="Furniture")
    scr = MeshBuilder("TV.Screen")
    scr.box((0, 0, 0), (0.004, 1.41, 0.79), M["screen"])
    tag(scr.build(location=(tv_x - 0.0225, cy, tv_z), collection="Furniture"), haven_role="tv_screen",
        haven_glow="living")
    for i, (x, y, rz) in enumerate(((-2.37, -2.25, 0), (-2.36, -3.8, 20))):
        instance(P["small"], f"Plant.Console.{i}", (x, y, F + 0.54), (0, 0, rz), 0.9, collection="Decor")
    # Lights: an arc lamp over the coffee table and a floor lamp by the TV.
    arc = MeshBuilder("ArcLamp")
    arc.rounded_box((-3.4, -0.55, F + 0.09), (0.3, 0.3, 0.18), M["marble"], 0.01, 2)
    arc.tube([(-3.4, -0.55, F + 0.18), (-3.4, -0.55, 1.6), (-3.75, -1.1, 2.15), (-4.2, -1.85, 2.1),
              (-4.5, -2.4, 1.92)], 0.014, M["brass"], bend_radius=0.4, segments=12)
    arc.lathe((-4.5, -2.4, 1.72), [(0.23, 0), (0.21, 0.04), (0.15, 0.13), (0.03, 0.19), (0, 0.2)],
              M["brass"], 48, cap=False)
    arc.build(collection="Lights", sharp_angle=60)
    light_anchor("living", (-4.5, -2.4, 1.8), 0.96, 4200)
    floor_lamp("living", -2.55, -4.7, 1.5, power=0.9)
    instance(P["fiddle"], "Plant.Living", (-6.6, -0.75, F), (0, 0, 30), 1.0, collection="Decor")


# ------------------------------------------------------------------ dining

def chair_prefab():
    mb = MeshBuilder("DiningChair")
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.rod((sx * 0.18, sy * 0.18, 0), (sx * 0.2, sy * 0.2, 0.42), 0.012, M["walnut"], 10, radius_b=0.019)
    mb.rounded_box((0, 0, 0.44), (0.47, 0.46, 0.06), M["walnut"], 0.012, 2)
    mb.rounded_box((0, 0.01, 0.49), (0.44, 0.42, 0.05), M["clay"], 0.02, 3, puff=0.012)
    for sx in (-1, 1):
        mb.rod((sx * 0.2, -0.2, 0.44), (sx * 0.2, -0.24, 0.84), 0.016, M["walnut"], 10)
    mb.rounded_box((0, -0.235, 0.74), (0.46, 0.05, 0.2), M["walnut"], 0.02, 3, rotation=(-8, 0, 0))
    return prefab(mb.build(sharp_angle=60))


def dining(P, rng):
    rug("Rug.Dining", -4.5, 2.45, 3.3, 3.0, M["rug_dining"])
    cx, cy = -4.5, 2.45
    t = MeshBuilder("DiningTable")
    t.lathe((cx, cy, F), [(0.38, 0), (0.38, 0.02), (0.3, 0.05), (0.12, 0.12), (0.09, 0.5), (0.16, 0.68),
                          (0.2, 0.7)], M["walnut"], 48)
    t.lathe((cx, cy, F + 0.7), [(0.66, 0), (0.7, 0.015), (0.7, 0.035), (0.68, 0.045), (0, 0.045)], M["walnut"], 72)
    t.build(collection="Furniture", sharp_angle=45)
    chair = chair_prefab()
    for i in range(4):
        a = 45 + i * 90
        px = cx + 0.86 * math.cos(math.radians(a))
        py = cy + 0.86 * math.sin(math.radians(a))
        instance(chair, f"DiningChair.{i}", (px, py, F), (0, 0, a + 90), collection="Furniture")
    ware = MeshBuilder("Tableware")
    top = F + 0.745
    for i in range(4):
        a = math.radians(45 + i * 90)
        px, py = cx + 0.48 * math.cos(a), cy + 0.48 * math.sin(a)
        ware.rounded_slab((px, py, top + 0.002), (0.42, 0.3, 0.004), 0.03, M["linen"], rotation=(0, 0, math.degrees(a) + 90))
        ware.lathe((px, py, top + 0.004), [(0.07, 0), (0.11, 0.008), (0.135, 0.018), (0.13, 0.02), (0.1, 0.012),
                                           (0, 0.008)], M["porcelain"], 40, cap=False)
        gx, gy = cx + 0.5 * math.cos(a + 0.42), cy + 0.5 * math.sin(a + 0.42)
        ware.lathe((gx, gy, top), [(0.03, 0), (0.035, 0.005), (0.006, 0.01), (0.006, 0.08), (0.03, 0.1),
                                   (0.04, 0.15), (0.038, 0.155), (0.028, 0.105), (0, 0.1)], M["glass"], 24, cap=False)
        for off in (-0.17, 0.17):
            b = a + off * 1.0
            ware.box((cx + 0.48 * math.cos(b), cy + 0.48 * math.sin(b), top + 0.006), (0.012, 0.16, 0.004),
                     M["brass"], rotation=(0, 0, math.degrees(a) + 90))
    ware.lathe((cx, cy, top), [(0.06, 0), (0.09, 0.08), (0.06, 0.22), (0.04, 0.28), (0.045, 0.3)],
               M["ceramic"], 32, cap=False)
    for k in range(4):
        ang = k * 90 + 20
        ware.rod((cx, cy, top + 0.25), (cx + 0.2 * math.cos(math.radians(ang)), cy + 0.2 * math.sin(math.radians(ang)),
                                        top + 0.6), 0.004, M["walnut"], 5)
        add_leaf(ware, Vector((cx + 0.12 * math.cos(math.radians(ang)), cy + 0.12 * math.sin(math.radians(ang)),
                               top + 0.45)), ang, 30, 0.12, 0.06, M["leaf_light"])
    ware.build(collection="Decor", sharp_angle=50)
    # Ring chandelier.
    ch = MeshBuilder("Chandelier")
    z = 1.68
    ch.torus((cx, cy, z), 0.48, 0.012, M["brass"], 64, 8)
    for k in range(3):
        a = math.radians(k * 120 + 30)
        ch.rod((cx + 0.48 * math.cos(a), cy + 0.48 * math.sin(a), z), (cx, cy, WALL_H - 0.03), 0.003, M["brass"], 5)
    ch.lathe((cx, cy, WALL_H - 0.03), [(0.07, 0), (0.07, 0.02), (0, 0.02)], M["brass"], 24)
    ch.build(collection="Lights", sharp_angle=60)

    def globes(b):
        for k in range(8):
            a = math.radians(k * 45)
            b.sphere((cx + 0.48 * math.cos(a), cy + 0.48 * math.sin(a), z + 0.05), 0.045, M["shade_glow"], 2)
    glow_part("Chandelier.Globes", globes, "dining")
    light_anchor("dining", (cx, cy, z + 0.02), 1.36, 6000, 0.03)
    # Sideboard on the west wall with art above.
    sb = MeshBuilder("Sideboard")
    sx, sy0, sy1 = -6.84, 1.2, 3.7
    sb.rounded_box((sx, (sy0 + sy1) / 2, F + 0.18 + 0.29), (0.46, sy1 - sy0, 0.58), M["walnut"], 0.012, 2)
    for i in range(4):
        y = sy0 + (sy1 - sy0) * (i + 0.5) / 4
        sb.box((sx + 0.231, y, F + 0.47), ((0.006), (sy1 - sy0) / 4 - 0.012, 0.54), M["lacquer_ink"])
        sb.rod((sx + 0.245, y - 0.25 if i % 2 == 0 else y + 0.25, F + 0.36), (sx + 0.245, y - 0.25 if i % 2 == 0 else y + 0.25, F + 0.58),
               0.007, M["brass"], 8)
    for py in (sy0 + 0.1, sy1 - 0.1):
        for px in (sx - 0.16, sx + 0.16):
            sb.rod((px, py, F), (px, py, F + 0.18), 0.014, M["black_metal"], 8, radius_b=0.01)
    sb.lathe((sx, 1.75, F + 0.76), [(0.06, 0), (0.1, 0.1), (0.05, 0.3), (0.035, 0.42)], M["terracotta"], 32, cap=False)
    sb.build(collection="Furniture", sharp_angle=50)
    table_lamp("dining", -6.84, 3.25, F + 0.76, base_mat=M["stoneware"])
    art = surfaces.art_textures()
    frame = MeshBuilder("Art.Dining.Frame")
    frame.box((-7.06, 2.45, 1.62), (0.03, 1.36, 0.92), M["oak"])
    tag(frame.build(collection="Decor"), haven_cutaway="west")
    tag(decal("Art.Dining", art[0], (1.28, 0.84), (-7.04, 2.45, 1.62), (90, 0, 90), roughness=0.85,
              collection="Decor"), haven_cutaway="west")
    instance(P["fiddle"], "Plant.Dining", (-6.6, 4.62, F), (0, 0, 100), 1.15, collection="Decor")
    # Sheer curtains either side of the dining window.
    for x0 in (-6.3, -3.1):
        drape(f"Curtain.Dining.{x0:.0f}", x0, x0 + 0.55, Y_N - 0.18, 2.42, M["linen"])
    return art


def drape(name, x0, x1, y, top, mat, folds=7):
    verts, faces = [], []
    cols, rows = folds * 4, 6
    for j in range(rows + 1):
        z = F + 0.01 + (top - F - 0.01) * j / rows
        for i in range(cols + 1):
            u = i / cols
            verts.append((x0 + (x1 - x0) * u, y + 0.04 * math.sin(u * folds * 2 * math.pi), z))
    for j in range(rows):
        for i in range(cols):
            a = j * (cols + 1) + i
            faces.append((a, a + 1, a + cols + 2, a + cols + 1))
    mb = MeshBuilder(name)
    mb.faces(verts, faces, mat)
    mb.rod((x0 - 0.05, y, top + 0.03), (x1 + 0.05, y, top + 0.03), 0.01, M["brass"], 8)
    tag(mb.build(collection="Soft"), haven_cutaway="north")


# ------------------------------------------------------------------ kitchen

def cabinet_run(mb, x0, x1, y0, y1, h, front_mat, front_side, door_w=0.6, handle="bar", body=None,
                z0=F, kick=0.1):
    """Base or wall cabinets from x0..x1 by y0..y1 (or rotated when front_side is 'x+'/'x-')."""
    body = body or M["lacquer"]
    along_x = front_side in ("y-", "y+")
    length = (x1 - x0) if along_x else (y1 - y0)
    n = max(1, round(length / door_w))
    if kick:
        if along_x:
            inset = 0.06 if front_side == "y-" else -0.06
            mb.box(((x0 + x1) / 2, (y0 + y1) / 2 + inset / 2, z0 + kick / 2), (x1 - x0, y1 - y0 - 0.06, kick), M["matte_black"])
        else:
            inset = 0.06 if front_side == "x-" else -0.06
            mb.box(((x0 + x1) / 2 + inset / 2, (y0 + y1) / 2, z0 + kick / 2), (x1 - x0 - 0.06, y1 - y0, kick), M["matte_black"])
    zb = z0 + kick
    mb.box(((x0 + x1) / 2, (y0 + y1) / 2, zb + (h - kick) / 2), (x1 - x0 - 0.02, y1 - y0 - 0.02, h - kick), body)
    for i in range(n):
        a0 = (x0 if along_x else y0) + length * i / n
        a1 = a0 + length / n
        c = (a0 + a1) / 2
        fz = zb + (h - kick) / 2
        if front_side == "y-":
            mb.rounded_box((c, y0 + 0.01, fz), (length / n - 0.006, 0.02, h - kick - 0.006), front_mat, 0.004, 1)
            hp = (c + (length / n) * 0.3 * (1 if i % 2 else -1), y0 - 0.012)
        elif front_side == "y+":
            mb.rounded_box((c, y1 - 0.01, fz), (length / n - 0.006, 0.02, h - kick - 0.006), front_mat, 0.004, 1)
            hp = (c, y1 + 0.012)
        elif front_side == "x-":
            mb.rounded_box((x0 + 0.01, c, fz), (0.02, length / n - 0.006, h - kick - 0.006), front_mat, 0.004, 1)
            hp = (x0 - 0.012, c + (length / n) * 0.3 * (1 if i % 2 else -1))
        else:
            mb.rounded_box((x1 - 0.01, c, fz), (0.02, length / n - 0.006, h - kick - 0.006), front_mat, 0.004, 1)
            hp = (x1 + 0.012, c)
        if handle == "bar":
            hz = zb + h - kick - 0.08 if z0 < 1 else zb + 0.08
            if along_x:
                mb.rod((hp[0] - 0.08, hp[1], hz), (hp[0] + 0.08, hp[1], hz), 0.006, M["brass"], 8)
            else:
                mb.rod((hp[0], hp[1] - 0.08, hz), (hp[0], hp[1] + 0.08, hz), 0.006, M["brass"], 8)


def kitchen(P, rng):
    sage = M["lacquer_sage"]
    k = MeshBuilder("Kitchen")
    y_wall = Y_N - 0.1
    xw, xe, xf = X_A + 0.06, X_B - 0.06, -1.37    # west face, east face, end of the fridge column
    # North run: base cabinets, marble worktop and splashback, wall cabinets with an LED strip.
    cabinet_run(k, xf, xe, y_wall - 0.6, y_wall, 0.88, sage, "y-")
    k.rounded_box(((xf + xe) / 2, y_wall - 0.31, F + 0.9), (xe - xf, 0.64, 0.04), M["marble"], 0.006, 2)
    k.box(((xf + xe) / 2, y_wall - 0.01, F + 1.18), (xe - xf, 0.02, 0.52), M["marble"])
    cabinet_run(k, xf, xe, y_wall - 0.36, y_wall, 0.72, M["lacquer"], "y-", kick=0, z0=F + 1.44)
    # Tall fridge / oven column at the west end.
    cabinet_run(k, xw, xf, y_wall - 0.62, y_wall, 2.25, sage, "y-", door_w=0.62)
    k.rounded_box(((xw + xf) / 2, y_wall - 0.635, F + 1.12), (0.54, 0.02, 0.5), M["black_glass"], 0.004, 1)
    k.box(((xw + xf) / 2, y_wall - 0.65, F + 1.3), (0.4, 0.006, 0.012), M["brass"])
    # Sink and tap.
    sx = -0.3
    k.rounded_slab((sx, y_wall - 0.31, F + 0.921), (0.56, 0.4, 0.003), 0.04, M["steel"])
    k.rounded_slab((sx, y_wall - 0.31, F + 0.924), (0.5, 0.34, 0.002), 0.035, M["black_metal"])
    k.cylinder((sx, y_wall - 0.08, F + 0.92), 0.025, 0.04, M["brass"], 16)
    k.tube([(sx, y_wall - 0.08, F + 0.95), (sx, y_wall - 0.08, F + 1.3), (sx, y_wall - 0.3, F + 1.3),
            (sx, y_wall - 0.3, F + 1.18)], 0.011, M["brass"], bend_radius=0.1, segments=10)
    # Island: walnut with fluting on the stool side, marble waterfall top, induction hob.
    ix, iy, iw, idp = -0.62, 2.95, 1.7, 0.9
    k.rounded_box((ix, iy, F + 0.45), (iw - 0.08, idp - 0.08, 0.86), M["walnut"], 0.01, 2)
    for i in range(32):
        x = ix - iw / 2 + 0.08 + i * (iw - 0.16) / 31
        k.rod((x, iy - idp / 2 + 0.035, F + 0.12), (x, iy - idp / 2 + 0.035, F + 0.86), 0.011, M["walnut"], 6)
    k.rounded_box((ix, iy, F + 0.9), (iw, idp, 0.04), M["marble"], 0.006, 2)
    for side in (-1, 1):
        k.rounded_box((ix + side * (iw / 2 - 0.02), iy, F + 0.45), (0.04, idp, 0.88), M["marble"], 0.006, 2)
    hx0, hy0 = ix - 0.25, iy + 0.12
    k.rounded_slab((hx0, hy0, F + 0.922), (0.6, 0.5, 0.006), 0.02, M["black_glass"])
    for hx in (hx0 - 0.14, hx0 + 0.14):
        for hy in (hy0 - 0.12, hy0 + 0.12):
            k.torus((hx, hy, F + 0.926), 0.085, 0.003, M["steel"], 32, 4)
    k.build(collection="Furniture", sharp_angle=50)
    # LED strip under the wall cabinets.
    glow_part("Kitchen.LED", lambda b: b.box(((xf + xe) / 2, y_wall - 0.33, F + 1.425), (xe - xf - 0.1, 0.018, 0.008),
                                             M["led"]), "kitchen")
    light_anchor("kitchen", ((xf + xe) / 2, y_wall - 0.4, F + 1.36), 0.7, 2600, 0.02)
    pendant("kitchen", ix - 0.42, iy, 1.62, 0.6)
    pendant("kitchen", ix + 0.42, iy, 1.62, 0.6)
    # Stools.
    st = MeshBuilder("Stool")
    st.lathe((0, 0, 0.66), [(0.17, 0), (0.19, 0.02), (0.19, 0.05), (0.16, 0.06), (0, 0.06)], M["clay"], 40)
    for a in range(4):
        ang = math.radians(a * 90 + 45)
        st.rod((0.07 * math.cos(ang), 0.07 * math.sin(ang), 0.66), (0.19 * math.cos(ang), 0.19 * math.sin(ang), 0.0),
               0.012, M["black_metal"], 8)
    st.torus((0, 0, 0.26), 0.155, 0.008, M["brass"], 32, 6)
    stool = prefab(st.build(sharp_angle=50))
    for i, x in enumerate((ix - 0.55, ix, ix + 0.55)):
        instance(stool, f"Stool.{i}", (x, iy - idp / 2 - 0.3, F), (0, 0, i * 25), collection="Furniture")
    # Counter details: kettle, board, fruit bowl, herbs.
    d = MeshBuilder("Kitchen.Decor")
    top = F + 0.92
    d.lathe((0.42, y_wall - 0.3, top), [(0.09, 0), (0.1, 0.03), (0.09, 0.17), (0.05, 0.22), (0.02, 0.23), (0, 0.23)],
            M["chrome"], 40)
    d.rod((0.52, y_wall - 0.3, top + 0.14), (0.6, y_wall - 0.3, top + 0.2), 0.012, M["chrome"], 8)
    d.rounded_box((-1.05, y_wall - 0.1, top + 0.2), (0.38, 0.025, 0.42), M["oak"], 0.01, 2, rotation=(12, 0, 0))
    d.lathe((ix + 0.5, iy - 0.1, top), [(0.08, 0), (0.15, 0.06), (0.17, 0.09), (0.16, 0.095), (0.07, 0.01)],
            M["stoneware"], 40, cap=False)
    for kk in range(5):
        d.sphere((ix + 0.5 + 0.07 * math.cos(kk * 1.3), iy - 0.1 + 0.07 * math.sin(kk * 1.3), top + 0.09 + 0.02 * (kk % 2)),
                 0.042, M["fruit_orange"] if kk % 3 else M["fruit_green"], 2)
    d.build(collection="Decor", sharp_angle=50)
    instance(P["small"], "Plant.Kitchen", (-0.7, y_wall - 0.25, top), (0, 0, 40), collection="Decor")
    instance(P["small"], "Plant.Kitchen.Shelf", (0.55, y_wall - 0.18, F + 1.44 + 0.72), (0, 0, 10), 0.8,
             collection="Decor")


# ------------------------------------------------------------------ hall

def hall(P, rng):
    rug("Rug.Hall", -0.6, -2.75, 1.05, 2.9, M["rug_hall"])
    rug("Doormat", -0.65, -4.72, 0.95, 0.55, M["charcoal"])
    c = MeshBuilder("Console")
    c.rounded_box((-1.74, -3.3, F + 0.62), (0.4, 1.4, 0.32), M["walnut"], 0.015, 2)
    c.rounded_box((-1.74, -3.3, F + 0.79), (0.42, 1.44, 0.03), M["marble"], 0.005, 1)
    c.lathe((-1.74, -3.75, F + 0.805), [(0.05, 0), (0.09, 0.12), (0.06, 0.3), (0.03, 0.36)], M["ceramic"], 32, cap=False)
    c.lathe((-1.74, -2.95, F + 0.805), [(0.06, 0), (0.12, 0.05), (0.13, 0.06)], M["brass"], 32)
    # Round mirror on a stand behind the console (the partition is cut below it).
    c.lathe((-1.86, -3.3, F + 0.805), [(0.06, 0), (0.06, 0.01), (0, 0.01)], M["brass"], 24)
    c.rod((-1.86, -3.3, F + 0.81), (-1.86, -3.3, F + 1.05), 0.01, M["brass"], 8)
    c.torus((-1.86, -3.3, F + 1.35), 0.3, 0.012, M["brass"], 48, 8, rotation=(0, 90, 0))
    c.build(collection="Furniture", sharp_angle=50)
    mir = MeshBuilder("Console.Mirror")
    mir.lathe((0, 0, 0), [(0.3, 0), (0, 0)], M["mirror"], 48, cap=False)
    mir.build(location=(-1.85, -3.3, F + 1.35), rotation=(0, 90, 0), collection="Furniture")
    # Bench with coat hooks.
    b = MeshBuilder("Bench")
    b.rounded_box((0.56, -3.9, F + 0.42), (0.38, 0.95, 0.05), M["oak"], 0.012, 2)
    b.rounded_box((0.56, -3.9, F + 0.47), (0.36, 0.9, 0.06), M["sand"], 0.025, 3, puff=0.01)
    for py in (-4.3, -3.5):
        b.box((0.56, py, F + 0.2), (0.34, 0.04, 0.4), M["oak"])
    b.rounded_box((0.56, -3.9, F + 0.12), (0.3, 0.8, 0.02), M["oak"], 0.005, 1)
    for py in (-4.25, -3.9, -3.55):
        b.rod((X_B - 0.07, py, 1.0), (X_B - 0.13, py, 1.05), 0.008, M["brass"], 8)
    b.build(collection="Furniture", sharp_angle=50)
    # Pedestal fan; the rotor turns with the hall's fan entity.
    fan = MeshBuilder("Fan")
    fx, fy, fz = -1.6, -1.85, 1.15
    fan.lathe((fx, fy, F), [(0.18, 0), (0.18, 0.015), (0.03, 0.03), (0, 0.03)], M["lacquer"], 40)
    fan.rod((fx, fy, F + 0.03), (fx, fy, fz - 0.08), 0.014, M["steel"], 12)
    face = rot(-45)

    def fp(v):
        return tuple(Vector((fx, fy, fz)) + face @ Vector(v))
    fan.rod(fp((0, 0.08, -0.08)), fp((0, 0.0, 0.0)), 0.03, M["lacquer"], 16)
    fan.rod(fp((0, 0.14, 0)), fp((0, 0.0, 0)), 0.065, M["lacquer"], 20)
    for ring_r in (0.25, 0.17):
        fan.torus(fp((0, -0.06, 0)), ring_r, 0.004, M["steel"], 48, 4, rotation=(90, 0, -45))
    for k in range(16):
        a = math.radians(k * 22.5)
        fan.rod(fp((0, -0.06, 0)), fp((0.25 * math.cos(a), -0.06, 0.25 * math.sin(a))), 0.0018, M["steel"], 4)
    fan.build(collection="Furniture", sharp_angle=50)
    rotor = MeshBuilder("Fan.Rotor")
    rotor.rod((0, -0.02, 0), (0, -0.05, 0), 0.04, M["lacquer"], 16)
    for k in range(5):
        a = k * 72
        v, f = leaf_geometry(0.21, 0.11, bend=0.0, fold=0.06, segs=4)
        m = Euler((0, math.radians(a), 0)).to_matrix().to_4x4() @ Matrix.Translation((0.03, -0.035, 0)) @ \
            Euler((math.radians(110), 0, 0)).to_matrix().to_4x4()
        rotor.faces(v, f, M["lacquer"], matrix=m)
    tag(rotor.build(location=fp((0, 0, 0)), rotation=(0, 0, -45), collection="Furniture"),
        haven_role="fan_rotor", haven_axis=[0.0, 0.0, 1.0])   # glTF local axis (Blender local -Y)
    floor_lamp("hall", 0.5, -2.95, 1.45, globe=True, power=0.9)
    instance(P["snake"], "Plant.Hall", (-1.65, -4.72, F), (0, 0, 15), 1.0, collection="Decor")


# ------------------------------------------------------------------ bedroom

def bedroom(P, rng, art):
    rug("Rug.Bedroom", 4.3, 3.0, 3.5, 3.0, M["rug_bed"])
    bx, head_y, bw, bl = 4.3, Y_N - 0.12, 2.0, 2.2
    foot_y = head_y - bl
    bed = MeshBuilder("Bed")
    bed.rounded_box((bx, (head_y + foot_y) / 2, F + 0.2), (bw, bl, 0.26), M["sand"], 0.05, 3)
    bed.box((bx, (head_y + foot_y) / 2, F + 0.04), (bw - 0.2, bl - 0.2, 0.08), M["matte_black"])
    for i in range(6):
        bed.rounded_box((bx - 1.1 + 0.18 + i * 0.368, head_y + 0.02, F + 0.78), (0.36, 0.14, 1.12), M["sand"], 0.06, 3, puff=0.025)
    bed.build(collection="Furniture", sharp_angle=55)
    linen = MeshBuilder("Bed.Linen")
    mz = F + 0.33
    linen.rounded_box((bx, (head_y + foot_y) / 2 - 0.02, mz + 0.12), (bw - 0.12, bl - 0.14, 0.24), M["linen"], 0.06, 3, puff=0.015)
    linen.rounded_box((bx, foot_y + 0.72, mz + 0.18), (bw + 0.02, 1.5, 0.2), M["cream"], 0.08, 3, puff=0.03)
    linen.rounded_box((bx, foot_y + 1.45, mz + 0.27), (bw - 0.02, 0.32, 0.06), M["cream"], 0.03, 3, puff=0.02)
    linen.rounded_box((bx, foot_y + 0.32, mz + 0.29), (bw + 0.06, 0.5, 0.04), M["rust"], 0.02, 3, puff=0.01)
    for sx in (-0.48, 0.48):
        linen.rounded_box((bx + sx, head_y - 0.33, mz + 0.38), (0.82, 0.18, 0.5), M["linen"], 0.07, 3,
                          rotation=(-18, 0, 0), puff=0.05)
        linen.rounded_box((bx + sx, head_y - 0.52, mz + 0.33), (0.7, 0.16, 0.4), M["cream"], 0.06, 3,
                          rotation=(-14, 0, 0), puff=0.045)
    linen.rounded_box((bx, head_y - 0.68, mz + 0.3), (0.5, 0.14, 0.3), M["blush"], 0.05, 3, rotation=(-10, 0, 0), puff=0.04)
    linen.build(collection="Soft", sharp_angle=55)
    # Nightstands and lamps.
    for nx in (bx - bw / 2 - 0.33, bx + bw / 2 + 0.33):
        ns = MeshBuilder(f"Nightstand.{nx:.1f}")
        ns.rounded_box((nx, head_y - 0.2, F + 0.32), (0.5, 0.4, 0.42), M["walnut"], 0.012, 2)
        ns.box((nx, head_y - 0.405, F + 0.38), (0.44, 0.01, 0.16), M["walnut"])
        ns.rod((nx - 0.06, head_y - 0.415, F + 0.38), (nx + 0.06, head_y - 0.415, F + 0.38), 0.005, M["brass"], 8)
        for px in (nx - 0.2, nx + 0.2):
            for py in (head_y - 0.05, head_y - 0.35):
                ns.rod((px, py, F), (px, py, F + 0.11), 0.01, M["black_metal"], 8)
        ns.build(collection="Furniture")
        table_lamp("bedroom", nx + 0.05, head_y - 0.18, F + 0.53)
        shelf_books(BOOKS, rng, -0.12, 0.08, (nx - 0.12, head_y - 0.3), F + 0.53, 0, f"Books.Night.{nx:.0f}", 0.22)
    # Art above the bed (on the north wall's upper part).
    frame = MeshBuilder("Art.Bedroom.Frame")
    frame.box((bx, Y_N - 0.115, 1.95), (1.5, 0.03, 0.66), M["walnut"])
    tag(frame.build(collection="Decor"), haven_cutaway="north")
    tag(decal("Art.Bedroom", art[1], (1.42, 0.58), (bx, Y_N - 0.132, 1.95), (90, 0, 0), roughness=0.85,
              collection="Decor"), haven_cutaway="north")
    # Bench at the foot of the bed.
    bn = MeshBuilder("Bed.Bench")
    bn.rounded_box((bx, foot_y - 0.32, F + 0.42), (1.5, 0.42, 0.12), M["charcoal"], 0.04, 3, puff=0.015)
    for px in (bx - 0.68, bx + 0.68):
        bn.box((px, foot_y - 0.32, F + 0.18), (0.04, 0.38, 0.36), M["walnut"])
    bn.build(collection="Furniture", sharp_angle=55)
    # Low dresser on the east wall (kept under the section cut), with a lamp and books.
    dr = MeshBuilder("Dresser")
    dx0, dx1, dy0, dy1 = X_E - 0.1 - 0.5, X_E - 0.1, 0.1, 2.3
    dr.rounded_box(((dx0 + dx1) / 2, (dy0 + dy1) / 2, F + 0.5), (0.5, dy1 - dy0, 0.78), M["oak"], 0.012, 2)
    for i in range(3):
        for j in range(3):
            y = dy0 + (dy1 - dy0) * (j + 0.5) / 3
            z = F + 0.2 + i * 0.25
            dr.rounded_box((dx0 - 0.005, y, z), (0.02, (dy1 - dy0) / 3 - 0.012, 0.236), M["oak"], 0.004, 1)
            dr.rod((dx0 - 0.02, y - 0.1, z), (dx0 - 0.02, y + 0.1, z), 0.006, M["brass"], 8)
    for py in (dy0 + 0.06, dy1 - 0.06):
        for px in (dx0 + 0.06, dx1 - 0.06):
            dr.rod((px, py, F), (px, py, F + 0.11), 0.012, M["black_metal"], 8)
    dr.lathe(((dx0 + dx1) / 2, dy0 + 0.35, F + 0.89), [(0.05, 0), (0.09, 0.08), (0.05, 0.24), (0.03, 0.3)],
             M["stoneware"], 32, cap=False)
    dr.build(collection="Furniture", sharp_angle=50)
    shelf_books(BOOKS, rng, -(dy1 - 0.15), -(dy1 - 0.6), ((dx0 + dx1) / 2 + 0.02, 0), F + 0.89, -90, "Books.Dresser", 0.25)
    # Lounge chair, side table and floor lamp under the window.
    ch = MeshBuilder("LoungeChair")
    lx, ly = 1.7, 3.85
    m = rot(-30)

    def lp(v):
        return tuple(Vector((lx, ly, 0)) + m @ Vector(v))
    ch.rounded_box(lp((0, 0, F + 0.3)), (0.82, 0.78, 0.2), M["blush"], 0.08, 3, rotation=(0, 0, -30), puff=0.02)
    ch.rounded_box(lp((0, 0.33, F + 0.6)), (0.82, 0.2, 0.62), M["blush"], 0.09, 3, rotation=(-10, 0, -30), puff=0.03)
    for sx in (-1, 1):
        ch.rounded_box(lp((sx * 0.38, 0.05, F + 0.48)), (0.14, 0.7, 0.3), M["blush"], 0.06, 3, rotation=(0, 0, -30))
        for sy in (-1, 1):
            ch.rod(lp((sx * 0.32, sy * 0.3, F)), lp((sx * 0.3, sy * 0.28, F + 0.2)), 0.013, M["walnut"], 8, radius_b=0.018)
    ch.lathe((2.25, 4.55, F), [(0.13, 0), (0.13, 0.01), (0.02, 0.02), (0.02, 0.5), (0.2, 0.5), (0.2, 0.53), (0, 0.53)],
             M["brass"], 32)
    ch.build(collection="Furniture", sharp_angle=55)
    floor_lamp("bedroom", 1.15, 4.55, 1.5, power=0.5)
    # Venetian blinds: the slats compress to the head rail as the bedroom cover opens.
    rail = MeshBuilder("Blinds.Rail")
    rail.rounded_box((1.9, Y_N - 0.16, 2.32), (1.5, 0.06, 0.05), M["lacquer"], 0.01, 2)
    tag(rail.build(collection="Furniture"), haven_cutaway="north")
    sl = MeshBuilder("Blinds")
    n = 22
    for i in range(n):
        z = -0.05 - i * (2.28 - 0.72) / n
        sl.rounded_box((0, 0, z), (1.42, 0.05, 0.006), M["lacquer"], 0.002, 1, rotation=(-20, 0, 0))
    for x in (-0.5, 0.5):
        sl.rod((x, 0.01, -0.05), (x, 0.01, -(2.28 - 0.72) - 0.05), 0.0015, M["paper"], 4)
    tag(sl.build(location=(1.9, Y_N - 0.16, 2.32), collection="Furniture"), haven_role="blind",
        haven_room="bedroom", haven_cutaway="north")
    instance(P["fiddle"], "Plant.Bedroom", (1.3, 0.35, F), (0, 0, 200), 0.9, collection="Decor")


# ------------------------------------------------------------------ bathroom

def bath(P, rng):
    rug("Rug.Bath", 2.2, -2.42, 0.9, 0.6, M["towel"])
    tub = MeshBuilder("Bathtub")
    tx, ty = 2.35, -3.75
    tub.lathe((tx, ty, F), [(0.3, 0), (0.36, 0.06), (0.4, 0.3), (0.42, 0.56), (0.43, 0.58), (0.4, 0.585),
                            (0.37, 0.56), (0.33, 0.3), (0.26, 0.12), (0, 0.11)], M["porcelain"], 64,
              scale=(1.0, 2.05), cap=False)
    tub.rod((tx, ty + 0.98, F), (tx, ty + 0.98, F + 0.85), 0.016, M["brass"], 12)
    tub.tube([(tx, ty + 0.98, F + 0.85), (tx, ty + 0.98, F + 0.95), (tx, ty + 0.82, F + 0.95), (tx, ty + 0.82, F + 0.88)],
             0.012, M["brass"], bend_radius=0.06, segments=10)
    tub.build(collection="Furniture", sharp_angle=60)
    water = MeshBuilder("Bathtub.Water")
    water.lathe((tx, ty, F + 0.46), [(0.385, 0), (0, 0)], M["water"], 64, scale=(1.0, 2.05), cap=False)
    water.build(collection="Furniture")
    # Floating vanity with a vessel basin and a round mirror on a stand.
    v = MeshBuilder("Vanity")
    vx, vy = X_B + 0.06 + 0.25, -2.3
    v.rounded_box((vx, vy, F + 0.62), (0.5, 1.15, 0.36), M["walnut"], 0.012, 2)
    v.rounded_box((vx, vy, F + 0.815), (0.52, 1.18, 0.03), M["marble"], 0.005, 1)
    v.box((vx + 0.252, vy, F + 0.62), (0.006, 1.0, 0.012), M["brass"])
    v.lathe((vx + 0.02, vy - 0.15, F + 0.83), [(0.08, 0), (0.17, 0.05), (0.19, 0.13), (0.18, 0.135),
                                                (0.16, 0.06), (0, 0.03)], M["porcelain"], 48, cap=False)
    v.rod((vx - 0.17, vy - 0.15, F + 0.83), (vx - 0.17, vy - 0.15, F + 1.08), 0.012, M["brass"], 10)
    v.tube([(vx - 0.17, vy - 0.15, F + 1.08), (vx - 0.17, vy - 0.15, F + 1.12), (vx - 0.04, vy - 0.15, F + 1.12)],
           0.01, M["brass"], bend_radius=0.03, segments=8)
    v.lathe((vx - 0.12, vy + 0.33, F + 0.83), [(0.07, 0), (0.07, 0.01), (0, 0.01)], M["brass"], 24)
    v.rod((vx - 0.12, vy + 0.33, F + 0.83), (vx - 0.12, vy + 0.33, F + 0.98), 0.008, M["brass"], 8)
    v.torus((vx - 0.12, vy + 0.33, F + 1.22), 0.24, 0.01, M["brass"], 48, 8, rotation=(0, 90, 0))
    for k, h in enumerate((0.14, 0.11)):
        v.lathe((vx - 0.02, vy + 0.08 + k * 0.09, F + 0.83), [(0.03, 0), (0.035, h * 0.8), (0.012, h), (0.012, h + 0.03)],
                M["ceramic"] if k else M["stoneware"], 24)
    v.build(collection="Furniture", sharp_angle=55)
    mir = MeshBuilder("Vanity.Mirror")
    mir.lathe((0, 0, 0), [(0.24, 0), (0, 0)], M["mirror"], 48, cap=False)
    mir.build(location=(vx - 0.115, vy + 0.33, F + 1.22), rotation=(0, 90, 0), collection="Furniture")
    pendant("bath", vx + 0.35, vy, 1.85, 0.97, kind="globe")
    # Wall-hung WC on the partition.
    wc = MeshBuilder("WC")
    wc.rounded_box((X_B + 0.12, -4.45, F + 0.5), (0.12, 0.55, 1.0), M["plaster_warm"], 0.01, 2)
    wc.rounded_box((X_B + 0.185, -4.45, F + 0.82), (0.01, 0.22, 0.14), M["brass"], 0.004, 1)
    wc.lathe((X_B + 0.45, -4.45, F + 0.24), [(0.12, 0), (0.17, 0.08), (0.19, 0.16), (0.185, 0.18), (0.15, 0.18), (0, 0.1)],
             M["porcelain"], 40, scale=(1.35, 1.0), cap=False)
    wc.rounded_slab((X_B + 0.47, -4.45, F + 0.43), (0.5, 0.37, 0.02), 0.17, M["porcelain"])
    wc.build(collection="Furniture", sharp_angle=55)
    # Walk-in shower: stone tray, glass screen, brass rain column.
    sh = MeshBuilder("Shower")
    sh.box((3.17, -1.72, F + 0.012), (0.86, 0.9, 0.024), M["tile_dark"])
    sh.rod((3.52, -1.35, F), (3.52, -1.35, 2.1), 0.016, M["brass"], 12)
    sh.tube([(3.52, -1.35, 2.1), (3.52, -1.35, 2.18), (3.28, -1.6, 2.18)], 0.012, M["brass"], bend_radius=0.06, segments=8)
    sh.lathe((3.28, -1.6, 2.13), [(0.13, 0), (0.13, 0.012), (0.02, 0.05)], M["brass"], 40)
    sh.rounded_box((3.52, -1.42, 1.05), (0.04, 0.08, 0.1), M["brass"], 0.01, 2)
    sh.box((2.74, -1.72, 1.04), (0.012, 0.88, 2.0), M["glass"])
    sh.box((2.74, -1.72, 2.04), (0.02, 0.9, 0.02), M["brass"])
    sh.build(collection="Furniture", sharp_angle=60)
    # Towels on a stool and a plant.
    tw = MeshBuilder("Towels")
    tw.lathe((3.35, -4.75, F), [(0.15, 0), (0.15, 0.42), (0.17, 0.44), (0.17, 0.46), (0, 0.46)], M["oak"], 40)
    for i, mat in enumerate((M["towel"], M["clay"], M["towel"])):
        tw.rounded_box((3.35, -4.75, F + 0.5 + i * 0.075), (0.36, 0.28, 0.07), mat, 0.03, 3, rotation=(0, 0, i * 7), puff=0.01)
    tw.build(collection="Decor", sharp_angle=55)
    instance(P["snake"], "Plant.Bath", (1.15, -1.5, F), (0, 0, 60), 0.75, collection="Decor")


# ------------------------------------------------------------------ office

def office(P, rng):
    rug("Rug.Office", 5.35, -3.25, 2.4, 2.1, M["rug_office"])
    dk = MeshBuilder("Desk")
    dy = Y_E - 0.06 - 0.39
    dk.rounded_slab((5.25, dy, F + 0.725), (2.1, 0.78, 0.03), 0.03, M["walnut"])
    for sx in (-1, 1):
        x = 5.25 + sx * 0.95
        dk.beam((x, dy - 0.33, F), (x, dy - 0.33, F + 0.71), 0.04, M["black_metal"])
        dk.beam((x, dy + 0.33, F), (x, dy + 0.33, F + 0.71), 0.04, M["black_metal"])
        dk.beam((x, dy - 0.35, F + 0.7), (x, dy + 0.35, F + 0.7), 0.04, M["black_metal"])
        dk.beam((x, dy - 0.35, F + 0.02), (x, dy + 0.35, F + 0.02), 0.04, M["black_metal"])
    top = F + 0.74
    for mx in (4.82, 5.68):
        dk.rounded_box((mx, dy + 0.22, top + 0.006), (0.24, 0.18, 0.012), M["black_metal"], 0.004, 1)
        dk.beam((mx, dy + 0.24, top), (mx, dy + 0.24, top + 0.3), 0.03, M["black_metal"])
        dk.rounded_box((mx, dy + 0.215, top + 0.42), (0.82, 0.03, 0.48), M["matte_black"], 0.008, 2)
    dk.rounded_box((5.25, dy - 0.14, top + 0.009), (0.44, 0.14, 0.018), M["steel"], 0.004, 1)
    for i in range(14):
        for j in range(4):
            dk.box((5.25 - 0.2 + i * 0.03 + 0.007, dy - 0.19 + j * 0.03 + 0.012, top + 0.02), (0.025, 0.025, 0.006), M["matte_black"])
    dk.rounded_box((5.6, dy - 0.15, top + 0.012), (0.06, 0.1, 0.024), M["matte_black"], 0.012, 2)
    dk.lathe((4.4, dy - 0.05, top), [(0.04, 0), (0.042, 0.1), (0.038, 0.1), (0.036, 0.008), (0, 0.008)], M["ceramic"], 24, cap=False)
    dk.rounded_box((4.62, dy - 0.12, top + 0.008), (0.2, 0.28, 0.016), M["ink"], 0.004, 1, rotation=(0, 0, 12))
    dk.build(collection="Furniture", sharp_angle=50)
    for i, mx in enumerate((4.82, 5.68)):
        s = MeshBuilder(f"Monitor.{i}")
        s.box((0, 0, 0), (0.78, 0.004, 0.44), M["monitor"])
        tag(s.build(location=(mx, dy + 0.198, top + 0.42), collection="Furniture"), haven_role="monitor", haven_glow="office")
    # Architect's desk lamp.
    al = MeshBuilder("DeskLamp")
    lx, ly = 6.12, dy + 0.22
    al.lathe((lx, ly, top), [(0.07, 0), (0.07, 0.02), (0.02, 0.03)], M["black_metal"], 24)
    al.rod((lx, ly, top + 0.02), (lx - 0.05, ly - 0.05, top + 0.38), 0.008, M["black_metal"], 8)
    al.rod((lx - 0.05, ly - 0.05, top + 0.38), (lx - 0.12, ly - 0.25, top + 0.5), 0.008, M["black_metal"], 8)
    al.lathe((lx - 0.12, ly - 0.27, top + 0.33), [(0.08, 0), (0.06, 0.06), (0.025, 0.14), (0, 0.15)], M["black_metal"], 32,
             cap=False)
    al.build(collection="Lights", sharp_angle=55)
    light_anchor("office", (lx - 0.12, ly - 0.27, top + 0.36), 0.6, 2200, 0.025)
    # Office chair.
    oc = MeshBuilder("OfficeChair")
    cx, cy = 5.3, dy - 0.75
    for k in range(5):
        a = math.radians(k * 72 + 90)
        oc.rod((cx, cy, F + 0.09), (cx + 0.3 * math.cos(a), cy + 0.3 * math.sin(a), F + 0.06), 0.018, M["black_metal"], 8)
        oc.sphere((cx + 0.3 * math.cos(a), cy + 0.3 * math.sin(a), F + 0.03), 0.028, M["rubber"], 2)
    oc.rod((cx, cy, F + 0.08), (cx, cy, F + 0.42), 0.025, M["chrome"], 12)
    oc.rounded_box((cx, cy, F + 0.47), (0.5, 0.48, 0.08), M["ink"], 0.035, 3, puff=0.012)
    oc.rod((cx, cy - 0.24, F + 0.45), (cx, cy - 0.3, F + 0.6), 0.02, M["black_metal"], 8)
    oc.rounded_box((cx, cy - 0.3, F + 0.86), (0.46, 0.06, 0.55), M["ink"], 0.03, 3, rotation=(-8, 0, 0), puff=0.012)
    for sx in (-1, 1):
        oc.rod((cx + sx * 0.25, cy - 0.05, F + 0.47), (cx + sx * 0.25, cy - 0.05, F + 0.67), 0.012, M["black_metal"], 8)
        oc.rounded_box((cx + sx * 0.25, cy - 0.02, F + 0.68), (0.07, 0.26, 0.03), M["matte_black"], 0.012, 2)
    oc.build(collection="Furniture", sharp_angle=55)
    # Low bookcase on the east wall (under the section cut), filled with instanced books.
    bc = MeshBuilder("Bookcase")
    bx0, bx1, by0, by1 = X_E - 0.1 - 0.36, X_E - 0.1, -4.85, -2.45
    shelves = [F + 0.05 + i * 0.33 for i in range(3)]
    height = shelves[-1] + 0.02 - F
    for py in (by0, (by0 + by1) / 2, by1):
        bc.box(((bx0 + bx1) / 2, py, F + height / 2), (0.36, 0.03, height), M["oak"])
    for z in shelves:
        bc.box(((bx0 + bx1) / 2, (by0 + by1) / 2, z), (0.36, by1 - by0, 0.025), M["oak"])
    bc.box((bx1 - 0.01, (by0 + by1) / 2, F + height / 2), (0.012, by1 - by0, height), M["walnut"])
    bc.build(collection="Furniture")
    mid = (by0 + by1) / 2
    for i, z in enumerate(shelves[:-1]):
        for a, b in ((by0 + 0.03, mid - 0.03), (mid + 0.03, by1 - 0.03)):
            b2 = b - (0.3 if (i + (a > mid)) % 2 else 0.0)
            shelf_books(BOOKS, rng, -b2, -a, ((bx0 + bx1) / 2 + 0.02, 0), z + 0.0125, -90, f"Books.Case.{i}.{a:.1f}", 0.3)
    instance(P["small"], "Plant.Bookcase", ((bx0 + bx1) / 2, by1 - 0.2, shelves[1] + 0.0125), (0, 0, 0), 0.9,
             collection="Decor")
    instance(P["small"], "Plant.Bookcase.2", ((bx0 + bx1) / 2, by0 + 0.3, shelves[-1] + 0.0125), (0, 0, 90), 1.0,
             collection="Decor")
    bc2 = MeshBuilder("Bookcase.Decor")
    bc2.lathe(((bx0 + bx1) / 2, -3.3, shelves[-1] + 0.0125), [(0.06, 0), (0.1, 0.12), (0.04, 0.3), (0.045, 0.34)],
              M["ceramic"], 32, cap=False)
    for k in range(3):
        bc2.rounded_box(((bx0 + bx1) / 2, -2.75, shelves[-1] + 0.03 + k * 0.035), (0.24, 0.3 - k * 0.03, 0.035),
                        M["book"][(k * 3) % 8], 0.004, 1, rotation=(0, 0, k * 7))
    bc2.build(collection="Decor", sharp_angle=50)
    floor_lamp("office", 3.98, -1.55, 1.4, globe=True, power=0.6)
    instance(P["fiddle"], "Plant.Office", (4.05, -4.65, F), (0, 0, 300), 0.85, collection="Decor")


# ------------------------------------------------------------------ build

BOOKS = []


def build(ctx):
    rng = ctx.rng
    M.update(surfaces.build_materials())
    LIGHTS.clear()
    BOOKS[:] = book_prefabs()
    P = plant_prefabs(rng)
    plinth()
    floors()
    walls()
    living(P, rng)
    art = dining(P, rng)
    kitchen(P, rng)
    hall(P, rng)
    bedroom(P, rng, art)
    bath(P, rng)
    office(P, rng)

    # Golden hour, lamps on: the dashboard's default look.
    atmosphere(time="18:50", latitude=42.0, day=200, north=-20.0, haze=0.35, lamps="on", exposure=0.3)
    camera((14.6, -16.4, 14.2), (0.1, -0.35, 0.1), lens=40)
    print(f"[haven] {len(LIGHTS)} light anchors: " +
          ", ".join(f"{r}" for r, _, _ in LIGHTS))
