"""Coastal refinery at blue hour, seen from a drone. Modelled from reference/photo.jpg.

Measured from the photo (24 mm lens, 612x458): horizon at 36% of frame height -> camera pitched
8.9 deg down; the 45 m foreground tank spans 12% of the frame ~240 m away -> camera ~130 m up.
Every ground position below comes from projecting photo pixels onto the ground plane.

Layout (meters, camera at the origin looking +Y = north):
  foreground right  conifer forest, the lit road, long sheds and a floodlit car park
  foreground left   big white tanks, rail and pipeline corridor, a small steaming unit
  middle            ~40 tanks fanning out left and right
  0.8-1.6 km        the process core: columns, frames, heaters, four tall stacks, steam plumes
  2.6 km+           the bay, and the far shore with its lights
"""

import math

import bpy
from mathutils import Vector

from harness import *
from harness import industrial as ind
from harness.core import STATE
from harness.industrial import fill, Occupancy, pipe_rack, steel_frame, storage_tank, vessel

META = {
    "title": "Refinery at Dusk",
    "description": "A coastal refinery at blue hour from a drone: thousands of lights, steam plumes "
                   "lit from below, tanks, stacks and the bay beyond.",
    "tags": ["industrial", "night", "photo-matched", "aerial"],
    "draft": True,   # ~3 min locally, ~15 min on a 2-CPU CI runner: build it on demand
    "seed": 31,
    "render": {"res": "1440x1078", "samples": 24, "glare": 0.25, "look": "AgX - Punchy"},
    # The photo's teal-and-orange look: a cool white balance and punchier colour.
    "grade": {"gains": [0.64, 1.0, 1.08], "saturation": 1.7},
    "viewer": {"bloom": 0.45, "grade": {"gains": [0.8, 1.0, 1.02], "saturation": 1.2}},
}

GROUND = 2.0
PAD = 2.1
SHORE_Y = 2600.0
ROAD = [(-500, 105), (-30, 165), (240, 300), (700, 520), (1300, 800)]
PARK_C, PARK_ROT = Vector((45, 365)), 26.6


def height(x, y):
    land = GROUND + 1.2 * fbm(x, y, scale=350, seed=3)
    if y > SHORE_Y - 150:  # beach down to the seabed
        land -= min(16.0, (y - (SHORE_Y - 150)) * 0.06)
    far = (y - 6900) * 0.035 + 25 * fbm(x, y, scale=900, seed=8) if y > 6600 else -99
    return max(land, far, -16.0)


def road_y(x):
    for (x0, y0), (x1, y1) in zip(ROAD, ROAD[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return ROAD[-1][1]


def park(local_x, local_y):
    """Car park local coords (along/across the road direction) -> world (x, y)."""
    a = math.radians(PARK_ROT)
    return (PARK_C.x + local_x * math.cos(a) - local_y * math.sin(a),
            PARK_C.y + local_x * math.sin(a) + local_y * math.cos(a))


# ------------------------------------------------------------------ distant (low-detail) kits

def far_kits(M):
    """Low-poly process modules for the core 0.8-1.6 km away, where detail is invisible.
    Dark, low-gloss materials: at dusk the core reads as a dark mass full of lights."""
    M = {**M, "clad": material("far_clad", "#59606a", roughness=0.6, metallic=0.2),
         "pipe_silver": material("far_pipe", "#646a70", roughness=0.6, metallic=0.2),
         "tank": material("far_tank", "#9fa3a6", roughness=0.6)}
    kits = []
    z = PAD
    mb = MeshBuilder("Far_Columns")
    for (x, y, r, h) in ((-2.5, -1.5, 1.6, 28), (2.2, 1.0, 1.2, 20), (-1.0, 3.0, 0.9, 14)):
        mb.rod((x, y, z), (x, y, z + h), r, M["clad"], 10)
        mb.dome((x, y, z + h), r, r * 0.5, M["clad"], 10, 2)
        for k in range(1, int(h / 8) + 1):
            mb.rod((x, y, z + 8 * k), (x, y, z + 8 * k + 0.25), r + 1.1, M["grating"], 10)
    kits.append(prefab(mb.build()))
    mb = MeshBuilder("Far_Frame")
    for x in (-4, 0, 4):
        for y in (-3, 3):
            mb.beam((x, y, z), (x, y, z + 18), 0.5, M["steel"])
    for lv in (6, 12, 18):
        mb.slab(-4.5, -3.5, 4.5, 3.5, z + lv, 0.15, M["grating"])
    mb.rod((0, 0, z + 18), (0, 0, z + 24), 1.4, M["pipe_silver"], 10)
    mb.box((-2, 0, z + 9), (3, 5, 3), M["pipe_grey"])
    kits.append(prefab(mb.build()))
    mb = MeshBuilder("Far_Heater")
    mb.box((0, 0, z + 7), (12, 6, 14), M["heater"])
    mb.rod((0, 0, z + 14), (0, 0, z + 34), 0.9, M["dark"], 8)
    kits.append(prefab(mb.build()))
    mb = MeshBuilder("Far_Drums")
    for k in range(3):
        mb.rod((-4, -3 + 3 * k, z + 1.5), (4, -3 + 3 * k, z + 1.5), 1.1, M["pipe_silver"], 10)
    mb.box((0, 0, z + 5), (9, 1, 0.5), M["steel"])
    kits.append(prefab(mb.build()))
    mb = MeshBuilder("Far_SmallTanks")
    for x in (-3, 3):
        mb.rod((x, 0, z), (x, 0, z + 7), 2.6, M["tank"], 14)
        mb.dome((x, 0, z + 7), 2.6, 0.5, M["tank_roof"], 14, 2)
    kits.append(prefab(mb.build()))
    return kits


def tank_prefabs(M):
    """A handful of tank designs (built once, instanced everywhere)."""
    designs = {}
    for key, (r, h, floating) in {"cone46": (23, 18, False), "cone40": (20, 16, False),
                                  "float44": (22, 17, True), "float72": (36, 19, True),
                                  "cone34": (17, 15, False), "float36": (18, 15, True),
                                  "small30": (15, 13, False)}.items():
        mb = MeshBuilder(f"Tank_{key}")
        storage_tank(mb, M, 0, 0, r, h, floating)
        designs[key] = (prefab(mb.build()), r, h)
    return designs


def place_tank(designs, key, x, y, name, rng, lights=True):
    obj, r, h = designs[key]
    instance(obj, name, (x, y, 0), (0, 0, rng.uniform(0, 360)), collection="Tanks")
    if lights:  # a floodlight on the stair landing and one at the base
        a = rng.uniform(0, math.tau)
        lamp((x + (r + 1) * math.cos(a), y + (r + 1) * math.sin(a), PAD + h + 1.5), "warm", 4500)
        lamp((x + (r + 6) * math.cos(a + 2), y + (r + 6) * math.sin(a + 2), PAD + 8), "sodium", 7500,
             pool_z=PAD)


def dark_stack(mb, M, x, y, h, r):
    mb.rod((x, y, PAD), (x, y, PAD + h), r, M["dark"], 24, radius_b=r * 0.72)
    for zz in (h * 0.55, h * 0.93):
        rr = r - (r - r * 0.72) * zz / h
        mb.ring_platform((x, y, PAD + zz), rr, rr + 1.3, M["grating"], M["steel"], 24)
    mb.rod((x, y, PAD + h), (x, y, PAD + h + 1.5), r * 0.74, M["red"], 24)
    for k in range(4):  # aviation lights
        a = k * math.pi / 2
        lamp((x + r * 0.8 * math.cos(a), y + r * 0.8 * math.sin(a), PAD + h + 1.6), "red", 400, bulb=0.6)
        lamp((x + r * 0.95 * math.cos(a), y + r * 0.95 * math.sin(a), PAD + h * 0.55 + 1.5), "red", 300,
             bulb=0.5)


def conifer_prefab():
    bark = material("bark", "#3b2f25", roughness=0.9)
    needles = material("conifer", "#1b2a21", roughness=0.9)
    mb = MeshBuilder("Conifer")
    mb.rod((0, 0, 0), (0, 0, 3), 0.25, bark, 6)
    for k, (r, z0, h) in enumerate(((4.2, 1.5, 8.0), (3.3, 5.5, 7.0), (2.2, 9.5, 6.0))):
        mb.rod((0, 0, z0), (0, 0, z0 + h), r, needles, 8, radius_b=0.05)
    return prefab(mb.build())


# ------------------------------------------------------------------ build

def build(ctx):
    rng = ctx.rng
    ind.set_pad(PAD)
    M = ind.mats()
    # Dusk palette: matte, darker equipment so the plant reads as a dark mass full of lights.
    M.update(clad=material("dusk_clad", "#6b737b", roughness=0.55, metallic=0.25),
             pipe_silver=material("dusk_pipe", "#70777d", roughness=0.55, metallic=0.25),
             asphalt=material("dusk_asphalt", "#55585b", roughness=0.85))

    seabed = material("seabed", "#2e3330", roughness=0.95)
    shore = material("shore_rock", "#4a4d4c", roughness=0.95)
    ground = material("ground", "#6c7073", roughness=0.92)
    hills = material("far_hills", "#1c221e", roughness=0.95)
    terrain("Land", size=12000, resolution=220, height=height, center=(0, 4500), backdrop=True,
            bands=[(-1.5, seabed), (0.8, shore), (14, ground), (999, hills)])
    ocean(level=0, waves="calm", wind=80, color="#12303f", shallow="#244a5a", foam=0.08, clarity=0.4,
          size=9000, render_detail=0, center=(0, 6000))
    water = material("bay_far", "#1a3546", roughness=0.06)
    plane("BayFar", size=40000, location=(0, 0, -0.15), material=water, backdrop=True)

    occ = Occupancy()

    # ---- roads, car park, sheds ---------------------------------------------------------------
    civil = MeshBuilder("Civil")
    for (x0, y0), (x1, y1) in zip(ROAD, ROAD[1:]):
        civil.beam((x0, y0, GROUND + 0.1), (x1, y1, GROUND + 0.1), 12, M["asphalt"], depth=0.3)
    lamps_along(ROAD, 34, 10, "sodium", 7500, ground=GROUND, offset=8)
    # Plant roads: a grid through the site.
    for x in (-470, -300, -110, 70, 250, 420):
        civil.slab(x - 5, 330, x + 5, 1700, PAD - 0.05, 0.3, M["asphalt"])
        lamps_along([(x, 340), (x, 1700)], 60, 9, "sodium", 6600, ground=PAD, offset=7)
    for y in (680, 790, 1650):
        civil.slab(-800, y - 5, 800, y + 5, PAD - 0.04, 0.3, M["asphalt"])
        lamps_along([(-800, y), (800, y)], 60, 9, "sodium", 6600, ground=PAD, offset=7)
    # Car park: asphalt, rows of cars, floodlight grid.
    civil.box((PARK_C.x, PARK_C.y, GROUND + 0.1), (230, 160, 0.3), M["asphalt"], rotation=(0, 0, PARK_ROT))
    colors = ["#c8ccd0", "#1d2a3a", "#8a1f1f", "#e7e5df", "#3c4d3a", "#5a5d61", "#24262a", "#b9a77f"]
    cars = [ind.car_prefab(M, f"p{i}", c) for i, c in enumerate(colors)]
    n = 0
    for row in range(-9, 10):
        ly = row * 8.0
        for col in range(-24, 25):
            if rng.random() < 0.82 and not (abs(col) < 2 or abs(row) == 4):
                x, y = park(col * 4.6, ly)
                instance(rng.choice(cars), f"Car.{n}", (x, y, GROUND + 0.25),
                         (0, 0, PARK_ROT + 90 + rng.choice((0, 180))), collection="Cars")
                n += 1
    for gx in range(-100, 101, 25):
        for gy in range(-70, 71, 28):
            x, y = park(gx, gy)
            civil.rod((x, y, GROUND), (x, y, GROUND + 16), 0.2, M["steel"], 6)
            lamp((x, y, GROUND + 16.2), "led" if (gx // 25 + gy // 28) % 5 == 0 else "sodium", 26000,
                 bulb=0.6, pool_z=GROUND)
    occ.add(PARK_C.x - 130, PARK_C.y - 110, PARK_C.x + 130, PARK_C.y + 110, 0)
    # Long sheds between the car park and the road, edge-lit.
    for i in range(3):
        for j in range(2):
            lx, ly = 30 + j * 82, -100 - i * 18
            x, y = park(lx, ly)
            civil.box((x, y, GROUND + 3.2), (72, 11, 6.4), M["building"], rotation=(0, 0, PARK_ROT))
            civil.box((x, y, GROUND + 6.55), (73, 12, 0.3), M["roof"], rotation=(0, 0, PARK_ROT))
            for k in range(-3, 4):
                ex, ey = park(lx + k * 11, ly - 6.5)
                lamp((ex, ey, GROUND + 5.5), "warm", 1800, bulb=0.25, pool_z=GROUND)
    civil.build(collection="Civil")

    # Forest below the road (foreground right) and along the plant edge.
    tree = conifer_prefab()
    trees = scatter(rng, 7000, (-20, 1300, 20, 760), height,
                    lambda x, y, z: y < road_y(x) - 14 and x > 0.3 * (200 - y), min_dist=4.2)
    for i, (x, y, z) in enumerate(trees):
        instance(tree, f"Tree.{i}", (x, y, z - 0.3), (0, 0, rng.uniform(0, 360)), rng.uniform(1.0, 1.6),
                 collection="Forest")
    # A few cars on the road, with head and tail lights.
    for i, t in enumerate((0.12, 0.31, 0.55, 0.7)):
        (x0, y0), (x1, y1) = ROAD[1], ROAD[3]
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        instance(cars[i % len(cars)], f"RoadCar.{i}", (x, y + 3 * (-1) ** i, GROUND + 0.25), (0, 0, 26.6 + 180 * (i % 2)),
                 collection="Cars")
        d = 2.6 if i % 2 == 0 else -2.6
        lamp((x + d * 0.9, y + 3 * (-1) ** i + d * 0.45, GROUND + 0.9), "#fff4dc", 300, bulb=0.18, light=False)
        lamp((x - d * 0.9, y + 3 * (-1) ** i - d * 0.45, GROUND + 0.9), "red", 100, bulb=0.15, light=False)

    # ---- tank farms ----------------------------------------------------------------------------
    designs = tank_prefabs(M)
    named = [("cone46", -108, 218), ("cone40", -28, 220), ("cone40", -150, 380), ("float44", -55, 462),
             ("cone34", -245, 520), ("cone34", -125, 560), ("cone34", 55, 530), ("cone40", 100, 470),
             ("float44", 195, 580), ("float72", 245, 385)]
    for i, (key, x, y) in enumerate(named):
        place_tank(designs, key, x, y, f"Tank.{i}", rng)
        r = designs[key][1]
        occ.add(x - r - 8, y - r - 8, x + r + 8, y + r + 8, 0)
    right = [(x, y) for x in (370, 460, 555, 650, 745) for y in (650, 755, 870, 1005, 1150)]
    for i, (x, y) in enumerate(right):
        key = rng.choice(["cone46", "float44", "cone40", "float44"])
        place_tank(designs, key, x + rng.uniform(-8, 8), y + rng.uniform(-8, 8), f"TankR.{i}", rng,
                   lights=rng.random() < 0.6)
    left = [(x, y) for x in range(-800, -370, 68) for y in range(600, 1300, 72)]
    for i, (x, y) in enumerate(left):
        if rng.random() < 0.85:
            place_tank(designs, rng.choice(["small30", "cone34", "float36"]), x, y, f"TankL.{i}", rng,
                       lights=rng.random() < 0.35)

    # ---- rail and pipeline corridor (left) ------------------------------------------------------
    corridor = MeshBuilder("Corridor")
    a, b, c = Vector((-215, 120)), Vector((-400, 640)), Vector((-560, 1150))
    for k in range(8):
        off = Vector((1, 0.36)).normalized() * (k * 4.5 - 16)
        for p, q in ((a, b), (b, c)):
            for rail in (-0.72, 0.72):
                d = (q - p).normalized()
                n = Vector((-d.y, d.x)) * rail
                corridor.beam((*(p + off + n), GROUND + 0.15), (*(q + off + n), GROUND + 0.15), 0.12,
                              M["steel"])
    pipe_rack(corridor, M, rng, (-180, 150), (-370, 640), width=8, tiers=(4.0, 7.5), bay=10)
    pipe_rack(corridor, M, rng, (-300, 700), (420, 700), width=10, tiers=(5.0, 9.0), bay=10)
    corridor.build(collection="Corridor")
    lamps_along([(-180, 150), (-370, 640)], 40, 9, "sodium", 6600, ground=GROUND, offset=6)
    lamps_along([(-300, 700), (420, 700)], 45, 10.5, "sodium", 6600, ground=PAD)

    # Small steaming unit at the left edge.
    lu = MeshBuilder("LeftUnit")
    steel_frame(lu, M, -225, 300, -195, 325, PAD, [6, 12, 18], floors=[6, 12, 18])
    vessel(lu, M, -180, 312, 2.0, 24, ladder_angle=180, seg=20)
    vessel(lu, M, -240, 318, 1.6, 18, ladder_angle=0, seg=20)
    lu.build(collection="LeftUnit")
    for k in range(18):
        lamp((-225 + rng.uniform(0, 30), 300 + rng.uniform(0, 25), PAD + rng.choice((6.5, 12.5, 18.5))),
             rng.choice(("sodium", "warm", "led")), 5400, bulb=0.3)
    plume((-205, 312, PAD + 20), height=45, radius=3.0, drift=(0.6, 0.25), seed=4)
    plume((-430, 395, PAD + 6), height=32, radius=2.2, drift=(0.7, 0.2), seed=5, density=0.18)

    # ---- process core ----------------------------------------------------------------------------
    core = MeshBuilder("ProcessCore")
    columns = [(-200, 900, 4.0, 70), (-170, 930, 3.0, 55), (-60, 980, 3.6, 62), (-20, 1080, 2.8, 48),
               (60, 960, 3.2, 58), (130, 1040, 4.2, 74), (160, 1180, 3.0, 52), (-330, 1050, 3.4, 60),
               (-280, 1180, 2.6, 46), (250, 980, 3.0, 50), (330, 1120, 3.6, 64), (-120, 1250, 3.0, 56),
               (20, 1350, 3.4, 60), (220, 1350, 2.8, 50), (-380, 1350, 3.0, 52)]
    for (x, y, r, h) in columns:
        vessel(core, M, x, y, r, h, ladder_angle=rng.uniform(0, 360), seg=24)
        occ.around(x, y, r + 6)
        for zz in range(12, int(h), 9):  # platform lights up the column
            a_ = rng.uniform(0, math.tau)
            lamp((x + (r + 1.2) * math.cos(a_), y + (r + 1.2) * math.sin(a_), PAD + zz + 1.2),
                 rng.choice(("sodium", "sodium", "warm", "led")), 900, bulb=0.22)
    frames = [(-240, 860, -190, 890, 4), (-90, 940, -40, 975, 5), (80, 900, 140, 935, 4),
              (180, 1080, 230, 1110, 3), (-260, 1100, -210, 1140, 4), (-60, 1150, 0, 1190, 5),
              (260, 1250, 310, 1290, 3), (-200, 1300, -150, 1330, 4)]
    for (x0, y0, x1, y1, levels) in frames:
        lv = [6 * (k + 1) for k in range(levels)]
        steel_frame(core, M, x0, y0, x1, y1, PAD, lv, floors=lv)
        occ.add(x0, y0, x1, y1)
        for z in lv:
            for (lx, ly) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1), ((x0 + x1) / 2, y0)):
                if rng.random() < 0.8:
                    lamp((lx, ly, PAD + z + 2.5), rng.choice(("sodium", "warm", "led")), 700, bulb=0.22)
    for (x, y) in ((-10, 880), (180, 870), (-300, 950), (300, 1180)):
        ind.fired_heater(core, M, x, y, w=30, d=12, h=18, stacks=2)
        occ.add(x - 17, y - 8, x + 17, y + 8)
    for (x, y, h, r) in ((-257, 830, 145, 3.6), (-228, 852, 128, 3.0), (292, 830, 125, 3.2), (30, 1110, 95, 2.6)):
        dark_stack(core, M, x, y, h, r)
        occ.around(x, y, r + 4)
    core.build(collection="ProcessCore")
    kits = far_kits(M)
    before = len(STATE["lamps"])
    for pad in [(-470, 800, 470, 1640), (-620, 1300, -480, 1640)]:
        fill(occ, rng, kits, pad, cell=15.0, chance=0.8, tag="Core")
    # Lights on the infill: one or two per module.
    for obj in list(bpy.data.collections["Infill"].objects):
        for _ in range(rng.choice((1, 1, 2))):
            p = obj.location
            lamp((p.x + rng.uniform(-5, 5), p.y + rng.uniform(-5, 5), PAD + rng.uniform(3, 20)),
                 rng.choice(("sodium", "sodium", "warm", "led")), 350, bulb=0.18,
                 pool_z=PAD if rng.random() < 0.3 else None)
    print(f"[dusk] infill lamps: {len(STATE['lamps']) - before}, total lamps: {len(STATE['lamps'])}")

    # Steam (the photo's plumes all lean right, downwind).
    for (x, y, z, h, r, seed) in ((-80, 905, 32, 170, 7.5, 1), (-30, 1000, 42, 120, 6, 2),
                                  (-150, 885, 26, 80, 4.5, 3), (120, 1050, 30, 70, 4, 6),
                                  (225, 955, 22, 60, 4, 7), (60, 1210, 50, 95, 5, 9),
                                  (-335, 725, 12, 42, 3, 10)):
        plume((x, y, PAD + z), height=h, radius=r, drift=(0.5, 0.18), seed=seed, density=0.2, glow=5.0)

    # ---- far shore lights ------------------------------------------------------------------------
    for i in range(160):
        x = rng.uniform(-9000, 9000)
        y = 7000 + rng.uniform(0, 900) + abs(x) * 0.05
        lamp((x, y, max(height(x, y), 0) + 4), rng.choice(("sodium", "warm", "led")), 10, bulb=3.0,
             light=False)

    # ---- time of day -----------------------------------------------------------------------------
    # Late-June evening on the Swedish west coast: the sun has just set (3.4 deg below the horizon),
    # off to the right of the view, as in the photo. Scene +Y points west-northwest.
    atmosphere(time="21:05", latitude=58.3, day=172, north=286, haze=0.2, visibility=11000,
               lamps=0.3, exposure=0.2)
    pitch = math.radians(8.9)
    camera((0, 0, 130), (0, 1000, 130 - 1000 * math.tan(pitch)), lens=24)

