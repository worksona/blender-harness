import math

import bmesh
from mathutils import Vector

from harness import *
from harness import industrial as ind
from harness.industrial import (Occupancy, air_coolers, bund, car_prefab, cooling_tower, drum,
                                fill, fired_heater, flare, kit_prefabs, lpg_sphere, mats,
                                pipe_rack, stack, steel_frame, storage_tank, tree_prefab,
                                truck_prefab, vessel)

META = {
    "title": "Coastal Oil Refinery",
    "description": "A kilometer of process units, pipe racks, tank farm and a burning flare, "
                   "with a tanker riding the swell at the marine jetty.",
    "tags": ["industrial", "golden hour", "ocean", "hi-res"],
    "seed": 23,
    "viewer": {"bloom": 0.35, "exposure": 1.0},
    "render": {"res": "1920x1080", "samples": 48},
}

GRADE = 1.5          # plant pad elevation (m)
PAD = 1.62           # top of concrete unit pads
COAST_Y = -260.0     # waterline


# ------------------------------------------------------------------ ground

def land(x, y):
    z = 3.4 + 1.6 * fbm(x, y, scale=200, seed=2) + 0.6 * fbm(x, y, scale=45, seed=6)
    z += max(0.0, y - 420) * 0.045 * (0.8 + 0.6 * fbm(x, y, scale=150, seed=4))
    # Flatten the plant site to GRADE, blending out over 70 m.
    dx = max(-500 - x, 0, x - 520)
    dy = max(-245 - y, 0, y - 400)
    w = min(1.0, math.hypot(dx, dy) / 70)
    w = w * w * (3 - 2 * w)
    return GRADE * (1 - w) + z * w


def height(x, y):
    return max(-16.0, min(land(x, y), (y - COAST_Y) * 0.12))


def tanker(M, name="Tanker"):
    """240 m product tanker. Local +X is the bow; origin on the waterline."""
    mb = MeshBuilder(name)
    bm = mb.bm
    # Hull: loft U-shaped sections from stern to bow.
    stations = [(-120, 0.92, -5.0), (-112, 0.98, -10.0), (-100, 1.0, -12.0), (70, 1.0, -12.0),
                (92, 0.86, -11.5), (106, 0.6, -10.0), (115, 0.32, -7.0), (120, 0.08, -3.0)]
    section = [(-20, 10), (-20, -6), (-17, -11), (0, -12), (17, -11), (20, -6), (20, 10)]
    rings = []
    for sx, k, keel in stations:
        ring = []
        for py, pz in section:
            z = pz if pz >= 0 else max(keel, pz * (-keel / 12))
            ring.append(bm.verts.new((sx, py * k, z)))
        rings.append(ring)
    top, bot = mb._mat_index(M["hull_top"]), mb._mat_index(M["hull_bot"])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(len(section) - 1):
            f = bm.faces.new((r0[i], r1[i], r1[i + 1], r0[i + 1]))
            f.material_index = bot if (r0[i].co.z + r0[i + 1].co.z) / 2 < 0.5 else top
    bm.faces.new(list(reversed(rings[0]))).material_index = top           # transom
    f = bm.faces.new(rings[-1]); f.material_index = top                  # bow face
    deck_loop = [r[-1] for r in rings] + [r[0] for r in reversed(rings)]
    f = bm.faces.new(deck_loop); f.material_index = mb._mat_index(M["deck"])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Accommodation block, bridge, funnel.
    mb.box((-104, 0, 10 + 8), (14, 30, 16), M["accom"])
    for k in range(5):
        mb.box((-96.95, 0, 12 + k * 3), (0.1, 28, 1.0), M["glass"])
    mb.box((-102, 0, 26.6), (10, 40, 1.2), M["accom"])                    # bridge wings
    mb.box((-101, 0, 28.5), (8, 20, 3), M["accom"])
    mb.box((-96.95, 0, 28.5), (0.1, 18, 1.4), M["glass"])
    mb.box((-112, 0, 31), (6, 7, 10), M["hull_bot"])                         # funnel
    mb.box((-112, 0, 36.2), (6.2, 7.2, 0.6), M["hull_top"])
    mb.rod((-101, 0, 30), (-101, 0, 38), 0.2, M["accom"], 8)                # radar mast
    mb.box((-101, 0, 37), (0.3, 4, 0.3), M["accom"])
    # Deck piping, catwalk, manifold, cranes, foremast.
    for py in (-6, -3.5, 3.5, 6):
        mb.rod((-90, py, 11.2), (100, py, 11.2), 0.35, M["pipe_grey"], 12)
    for xx in range(-88, 101, 12):
        mb.box((xx, 0, 10.6), (0.4, 14, 1.2), M["steel"])
    mb.slab(-92, -0.8, 102, 0.8, 13.0, 0.08, M["grating"])
    mb.railing([(-92, 0.8, 13.0), (102, 0.8, 13.0)], M["yellow"], post_step=4)
    mb.railing([(-92, -0.8, 13.0), (102, -0.8, 13.0)], M["yellow"], post_step=4)
    for py in range(-16, 17, 4):
        mb.rod((-5, py, 11.6), (5, py, 11.6), 0.3, M["pipe_yellow"], 12)
        mb.rod((0, py, 11.6), (0, py, 13.8), 0.3, M["pipe_yellow"], 12)
    for cx in (-10, 10):
        mb.rod((cx, -14, 10), (cx, -14, 18), 0.6, M["yellow"], 16)
        mb.beam((cx, -14, 17.5), (cx + 12, -14, 21), 0.5, M["yellow"])
    mb.rod((96, 0, 10), (96, 0, 26), 0.4, M["accom"], 12)
    mb.box((110, 0, 11.2), (12, 18, 2.4), M["hull_top"])                     # forecastle
    return mb.build()


# ------------------------------------------------------------------ build

def build(ctx):
    rng = ctx.rng
    ind.set_pad(PAD)
    M = mats()

    sand = material("seabed", "#7d7560", roughness=0.95)
    riprap = material("riprap", "#77746e", roughness=0.95)
    gravel = material("gravel", "#a39a88", roughness=0.95)
    grass = material("dry_grass", "#9c9a5f", roughness=0.9)
    scrub = material("scrub", "#6f7a48", roughness=0.9)
    terrain("Land", size=2800, resolution=240, height=height, center=(0, 400),
            bands=[(-3.0, sand), (1.0, riprap), (1.75, gravel), (8.0, grass), (999, scrub)],
            backdrop=True)
    ocean(level=0, waves="calm", wind=200, color="#0c3c55", shallow="#3a8a86", foam=0.45,
          clarity=0.55, size=3400, render_detail=9)

    # Roads and unit pads.
    civil = MeshBuilder("Civil")
    roads_x = [-475, -135, 205, 470]
    roads_y = [-205, 180, 365]
    for rx in roads_x:
        civil.slab(rx - 5, -205, rx + 5, 365, GRADE + 0.12, 0.25, M["asphalt"])
    for ry in roads_y:
        civil.slab(-475, ry - 5, 470, ry + 5, GRADE + 0.13, 0.25, M["asphalt"])
    civil.slab(145, -260, 155, -205, GRADE + 0.12, 0.25, M["asphalt"])           # jetty approach
    for x0, y0, x1, y1 in [(-120, -150, 58, 150), (84, -150, 196, 170), (216, -150, 455, 165),
                           (-120, 195, -10, 350), (0, 195, 195, 350), (216, 195, 455, 350)]:
        civil.slab(x0, y0, x1, y1, PAD, 0.3, M["concrete"])
    civil.build(collection="Civil")

    # ---------------- tank farm
    tanks = MeshBuilder("TankFarm")
    spec = [(-405, -105, 30, 18, True), (-305, -105, 32, 18, True), (-205, -105, 26, 16, False),
            (-405, -10, 31, 19, True), (-305, -10, 25, 15, False), (-205, -10, 30, 18, True),
            (-405, 85, 28, 17, False), (-305, 85, 32, 19, True), (-205, 85, 30, 18, True),
            (-405, 270, 24, 15, False), (-305, 270, 30, 18, True), (-205, 270, 26, 16, True)]
    for x, y, r, h, floating in spec:
        tanks.slab(x - 42, y - 42, x + 42, y + 42, GRADE + 0.05, 0.1, M["concrete"])
        bund(tanks, M, x, y, 41)
        storage_tank(tanks, M, x, y, r, h, floating)
        # Tank outlet to the pipe-way.
        side = -1 if x > -300 else 1
        tanks.pipe([(x, y - r * 0.7, PAD + 0.8), (x, y - r - 3, PAD + 0.8),
                    (x + side * 50, y - r - 3, PAD + 0.8)], 0.35, M["pipe_grey"], 16)
    for px in (-355, -255):  # ground pipe-ways between tank columns
        for k, mat in enumerate(["pipe_grey", "pipe_grey", "pipe_brown", "pipe_silver"]):
            tanks.rod((px - 1.5 + k, -172, PAD + 0.6), (px - 1.5 + k, 300, PAD + 0.6), 0.32, M[mat], 16,
                      caps=False)
        for yy in range(-170, 301, 10):
            tanks.box((px, yy, PAD + 0.15), (5, 0.4, 0.3), M["concrete"])
    tanks.build(collection="TankFarm")

    # ---------------- LPG spheres
    lpg = MeshBuilder("LPG")
    for x, y in [(-95, 228), (-55, 228), (-95, 280), (-55, 280)]:
        lpg_sphere(lpg, M, x, y, 9.5)
    lpg.pipe([(-115, 254, PAD + 1), (-35, 254, PAD + 1), (-35, 190, PAD + 1)], 0.4, M["pipe_yellow"], 16)
    lpg.build(collection="LPG")

    # ---------------- pipe racks
    racks = MeshBuilder("PipeRacks")
    pipe_rack(racks, M, rng, (-440, -172), (450, -172))
    pipe_rack(racks, M, rng, (70, -167), (70, 185), tiers=(6.0, 10.0, 14.0))
    pipe_rack(racks, M, rng, (210, 60), (440, 60), width=8, tiers=(5.0, 9.0))
    air_coolers(racks, M, 65, -60, 75, 70, PAD + 18.5)
    racks.build(collection="PipeRacks")
    coolers = MeshBuilder("AirCoolers")
    air_coolers(coolers, M, 60, 85, 80, 150, PAD + 18.5)
    coolers.build(collection="PipeRacks")

    # ---------------- crude distillation unit
    cdu = MeshBuilder("CrudeUnit")
    top_atm = vessel(cdu, M, -70, 40, 3.6, 58, ladder_angle=200)
    top_vac = vessel(cdu, M, -30, 40, 4.0, 46, ladder_angle=160,
                     sections=[(10, 4.0), (22, 6.2), (7, 2.6)])
    for i, (sx, sy) in enumerate([(-95, 5), (-95, 25), (-95, 45)]):
        vessel(cdu, M, sx, sy, 1.3, 26 - 2 * i, skirt=2.5, platform_every=8, ladder_angle=180)
    steel_frame(cdu, M, -110, -135, -40, -100, PAD, [6, 12, 18, 24], floors=[6, 12, 24])
    for lx in (-100, -85, -70, -55):
        drum(cdu, M, (lx, -118, PAD + 12 + 1.4), 1.0, 10, "y", "pipe_silver", saddle_h=0.3)
    drum(cdu, M, (-75, -126, PAD + 24 + 1.8), 1.6, 14, "x", "clad", saddle_h=0.3)
    fired_heater(cdu, M, 20, 80, stacks=2)
    fired_heater(cdu, M, 20, 25, w=24, d=11, h=17, stacks=1)
    for k in range(6):  # transfer lines from heaters and columns to the rack
        z = PAD + 6 + 0.6 * k
        cdu.pipe([(-70 + 3.6 * 0.7, 40 - 2.2, PAD + 8 + 6 * k), (-70 + 6, 40 - 2.2, PAD + 8 + 6 * k),
                  (-70 + 6, 40 - 2.2, z), (64, 40 - 2.2 + 0.9 * k, z)], 0.25 + 0.03 * k,
                 M[["pipe_silver", "pipe_grey", "pipe_brown"][k % 3]], 12)
    cdu.pipe([(-70, 40, top_atm), (-70, 40, top_atm + 2), (-50, 40, top_atm + 2), (-50, 40, PAD + 20),
              (64, 30, PAD + 20)], 0.6, M["pipe_silver"], 16)
    cdu.pipe([(-30, 40, top_vac), (-30, 40, top_vac + 1.5), (-10, 40, top_vac + 1.5), (-10, 40, PAD + 15),
              (64, 46, PAD + 15)], 0.9, M["pipe_silver"], 16)
    cdu.build(collection="CrudeUnit")

    # ---------------- fluid catalytic cracker
    fcc = MeshBuilder("FCC")
    steel_frame(fcc, M, 110, 20, 170, 80, PAD, [7.5, 15, 22.5, 30, 37.5, 45, 52.5, 60],
                floors=[7.5, 22.5, 37.5, 52.5, 60])
    rg = (150, 50)
    fcc.rod((*rg, PAD + 22), (*rg, PAD + 26), 3.0, M["clad"], 48, radius_b=8.0)
    fcc.rod((*rg, PAD + 26), (*rg, PAD + 44), 8.0, M["clad"], 48, caps=False)
    fcc.dome((*rg, PAD + 44), 8.0, 4.0, M["clad"], 48, 6)
    for k in range(1, 6):
        fcc.torus((*rg, PAD + 26 + 3 * k), 8.03, 0.06, M["pipe_grey"], 48, 4)
    rx = (125, 45)
    fcc.rod((*rx, PAD + 44), (*rx, PAD + 66), 4.0, M["clad"], 40, caps=False)
    fcc.dome((*rx, PAD + 66), 4.0, 2.2, M["clad"], 40, 6)
    fcc.rod((*rx, PAD + 40), (*rx, PAD + 44), 1.2, M["clad"], 24, radius_b=4.0)
    fcc.pipe([(140, 50, PAD + 24), (128, 47, PAD + 30), (125, 45, PAD + 40)], 1.1, M["clad"], 24)  # riser
    fcc.pipe([(rg[0] + 5, rg[1], PAD + 47), (rg[0] + 5, rg[1], PAD + 58), (185, 140, PAD + 58)], 1.4,
             M["pipe_grey"], 24)  # flue gas to stack
    vessel(fcc, M, 100, 120, 3.5, 62, ladder_angle=0)
    vessel(fcc, M, 135, 130, 2.2, 38, ladder_angle=90)
    vessel(fcc, M, 160, 130, 2.0, 32, ladder_angle=90)
    stack(fcc, M, 185, 140, 92, 2.8)
    fcc.box((150, -10, PAD + 6), (40, 18, 12), M["building"])                    # compressor house
    fcc.box((150, -10, PAD + 12.3), (41, 19, 0.6), M["roof"])
    for k in range(8):
        fcc.box((132 + k * 5, -19.05, PAD + 8), (3, 0.1, 2), M["glass"])
    for k in range(5):
        drum(fcc, M, (100 + k * 9, -60, PAD + 2.4), 1.1, 7, "y", "pipe_silver", saddle_h=0.8)
    fcc.pipe([(100, 116.5, PAD + 40), (80, 116.5, PAD + 40), (75, 110, PAD + 14)], 0.8, M["pipe_silver"], 16)
    fcc.build(collection="FCC")

    # ---------------- hydrotreating / reforming
    ht = MeshBuilder("Hydrotreaters")
    for i in range(4):
        vessel(ht, M, 240 + i * 16, 20, 2.6, 20, skirt=3, platform_every=7, head=0.6, shell="pipe_silver",
               ladder_angle=270)
    vessel(ht, M, 320, 110, 2.4, 44, ladder_angle=180)
    vessel(ht, M, 345, 110, 1.9, 36, ladder_angle=180)
    vessel(ht, M, 370, 110, 1.6, 30, ladder_angle=180)
    vessel(ht, M, 410, 20, 3.0, 50, ladder_angle=270)
    fired_heater(ht, M, 260, 120, w=36, d=12, h=18, stacks=2)
    steel_frame(ht, M, 330, -40, 400, -10, PAD, [6, 12, 18], floors=[6, 18])
    for k in range(4):
        drum(ht, M, (345 + k * 14, -25, PAD + 18 + 1.5), 1.1, 9, "y", "pipe_grey", saddle_h=0.3)
    for k in range(6):
        drum(ht, M, (230 + k * 14, -60, PAD + 2.6), 1.4, 9, "x", ["pipe_silver", "clad"][k % 2], saddle_h=0.9)
    for i in range(4):
        ht.pipe([(240 + i * 16, 20, PAD + 26.5), (240 + i * 16, 20, PAD + 29), (240 + i * 16 + 8, 20, PAD + 29),
                 (240 + i * 16 + 8, 20, PAD + 9.6), (240 + i * 16 + 8, 58, PAD + 9.6)], 0.45, M["pipe_brown"], 16)
    air_coolers(ht, M, 290, 54, 330, 66, PAD + 13)
    ht.build(collection="Hydrotreaters")

    # ---------------- secondary racks and dense infill around the main units
    sec = MeshBuilder("UnitRacks")
    pipe_rack(sec, M, rng, (-115, -80), (60, -80), width=6, tiers=(5.0, 8.5), bay=7)
    pipe_rack(sec, M, rng, (90, -45), (90, 100), width=6, tiers=(5.0, 8.5), bay=7)
    pipe_rack(sec, M, rng, (220, -85), (450, -85), width=6, tiers=(5.0, 8.5), bay=7)
    pipe_rack(sec, M, rng, (330, 195), (330, 340), width=6, tiers=(5.0,), bay=7)
    sec.build(collection="PipeRacks")

    occ = Occupancy()
    for rect in [(-440, -177, 450, -167), (65, -167, 75, 185), (210, 56, 440, 64),           # main racks
                 (-115, -83, 60, -77), (87, -45, 93, 100), (220, -88, 450, -82),               # unit racks
                 (-76, 34, -64, 46), (-38, 32, -22, 48), (-98, 2, -92, 48),                    # CDU columns
                 (-110, -135, -40, -100), (3, 71, 37, 89), (6, 18, 34, 32), (-64, 36, 64, 47),
                 (110, 20, 170, 80), (95, 115, 105, 125), (131, 126, 139, 134), (157, 126, 163, 134),
                 (181, 136, 189, 144), (130, -19, 170, -1), (95, -65, 141, -55), (75, 110, 100, 118),
                 (235, 15, 293, 25), (246, 18, 298, 60), (316, 104, 374, 116), (405, 15, 415, 25),
                 (241, 113, 279, 127), (330, -40, 400, -10), (225, -63, 305, -57),
                 (232, 233, 316, 247), (232, 293, 316, 307), (220, 185, 230, 305), (327, 195, 333, 340)]:
        occ.add(*rect)
    kits = kit_prefabs(M)
    n_kits = 0
    for pad in [(-118, -148, 56, 148), (86, -148, 194, 168), (218, -148, 453, 163), (320, 197, 453, 348)]:
        n_kits += fill(occ, rng, kits, pad, tag=f"Kit{n_kits}")
    print(f"[refinery] placed {n_kits} infill kits")

    # ---------------- cooling towers & flare
    ct = MeshBuilder("CoolingTowers")
    cooling_tower(ct, M, 232, 240)
    cooling_tower(ct, M, 232, 300)
    ct.pipe([(225, 240, PAD + 1.5), (225, 300, PAD + 1.5)], 1.0, M["green_pipe"], 24)
    ct.pipe([(225, 270, PAD + 1.5), (225, 185, PAD + 1.5), (225, 70, PAD + 1.5)], 1.0, M["green_pipe"], 24)
    ct.build(collection="Utilities")
    fl = MeshBuilder("Flare")
    flare(fl, M, 505, -140)
    fl.build(collection="Utilities")

    # ---------------- admin, control room, parking, truck loading
    adm = MeshBuilder("Admin")
    adm.box((40, 220 + 14, PAD + 4.5), (44, 28, 9), M["building"])               # control room
    adm.box((40, 220 + 14, PAD + 9.3), (45, 29, 0.6), M["roof"])
    adm.box((130, 330, PAD + 7), (60, 18, 14), M["building"])                    # offices
    adm.box((130, 330, PAD + 14.3), (61, 19, 0.6), M["roof"])
    for k in range(3):
        adm.box((130, 320.95, PAD + 3 + 4 * k), (56, 0.1, 1.8), M["glass"])
    adm.box((40, 219.95, PAD + 4), (40, 0.1, 1.2), M["glass"])
    adm.slab(90, 215, 190, 300, PAD + 0.05, 0.1, M["asphalt"])                  # car park
    for k in range(11):
        adm.box((95 + k * 9, 257, PAD + 0.07), (0.15, 70, 0.02), M["white"])
    # Truck loading rack.
    adm.slab(-345, 320, -230, 352, PAD + 0.05, 0.1, M["asphalt"])
    adm.box((-288, 336, PAD + 8.5), (112, 28, 0.6), M["roof"])
    for xx in range(-340, -230, 14):
        for yy in (324, 348):
            adm.beam((xx, yy, PAD), (xx, yy, PAD + 8.2), 0.5, M["steel"])
        adm.beam((xx, 324, PAD + 6), (xx, 348, PAD + 6), 0.3, M["steel"])
        adm.rod((xx + 7, 336, PAD + 6), (xx + 7, 336, PAD + 3.5), 0.12, M["pipe_yellow"], 8)
    adm.build(collection="Admin")
    colors = ["#c8ccd0", "#1d2a3a", "#8a1f1f", "#e7e5df", "#3c4d3a", "#5a5d61"]
    cars = [car_prefab(M, str(i), c) for i, c in enumerate(colors)]
    n = 0
    for k in range(11):
        for row in (232, 282):
            if rng.random() < 0.75:
                instance(rng.choice(cars), f"Car.{n}", (99 + k * 9, row, PAD + 0.1),
                         (0, 0, 90 + rng.choice([0, 180])), collection="Vehicles")
                n += 1
    truck = truck_prefab(M)
    for i, xx in enumerate(range(-333, -235, 28)):
        instance(truck, f"Truck.{i}", (xx, 336, PAD + 0.1), (0, 0, 0), collection="Vehicles")
    for i, (x, y) in enumerate([(-170, 365), (60, 365), (300, 180), (-110, -205), (120, -205)]):
        instance(truck, f"TruckRoad.{i}", (x, y, GRADE + 0.25), (0, 0, 0 if i % 2 else 180),
                 collection="Vehicles")
    tree = tree_prefab()
    trees = scatter(rng, 160, (-600, 600, 395, 700), height,
                    lambda x, y, z: z > 3 and not (-480 < x < 480 and y < 380), min_dist=9)
    trees += [(x, 202, PAD) for x in range(0, 200, 12)]
    for i, (x, y, z) in enumerate(trees):
        instance(tree, f"Tree.{i}", (x, y, z - 0.2), (0, 0, rng.uniform(0, 360)), rng.uniform(1.2, 2.0),
                 collection="Trees")

    # ---------------- marine terminal
    jt = MeshBuilder("Jetty")
    deck_z = 6.0
    jt.slab(145, -470, 155, -255, deck_z, 0.6, M["concrete"])                  # trestle
    jt.box((150, -257, 2.0), (14, 10, 8), M["concrete"])                          # abutment
    for yy in range(-462, -255, 12):
        for xx in (146.5, 153.5):
            jt.rod((xx, yy, -16), (xx, yy, deck_z - 0.6), 0.55, M["concrete"], 16)
        jt.beam((146.5, yy, deck_z - 0.8), (153.5, yy, deck_z - 0.8), 0.6, M["concrete"])
    for k, mat in enumerate(["pipe_grey", "pipe_silver", "pipe_yellow", "pipe_grey"]):
        jt.rod((147 + k * 1.1, -462, deck_z + 0.9), (147 + k * 1.1, -205, deck_z + 0.9), 0.35, M[mat], 16)
    for yy in range(-460, -255, 10):
        jt.box((149, yy, deck_z + 0.3), (5, 0.4, 0.6), M["steel"])
    jt.railing([(145, -255, deck_z), (145, -470, deck_z)], M["yellow"], post_step=4)
    jt.slab(118, -505, 182, -455, deck_z, 0.8, M["concrete"])                  # loading platform
    for xx in range(122, 182, 10):
        for yy in range(-500, -455, 10):
            jt.rod((xx, yy, -16), (xx, yy, deck_z - 0.8), 0.6, M["concrete"], 16)
    for i, yy in enumerate((-494, -484, -474, -464)):                            # loading arms
        jt.rod((176, yy, deck_z), (176, yy, deck_z + 14), 0.45, M["pipe_silver"], 16)
        jt.beam((176, yy, deck_z + 14), (183 + (i % 2) * 1.5, yy, deck_z + 18), 0.5, M["yellow"])
        jt.beam((183 + (i % 2) * 1.5, yy, deck_z + 18), (186, yy, deck_z + 9), 0.45, M["yellow"])
        jt.box((172.5, yy, deck_z + 15), (2, 1.2, 1.6), M["dark"])
    for yy in (-575, -535, -405, -365):                                          # breasting dolphins
        jt.box((184, yy, deck_z - 2), (8, 8, 5), M["concrete"])
        for dx in (-2, 2):
            for dy in (-2, 2):
                jt.rod((184 + dx, yy + dy, -16), (184 + dx, yy + dy, deck_z - 4), 0.5, M["concrete"], 12)
        jt.box((189.5, yy, deck_z - 2), (1.6, 6, 4), M["fan"])                  # fenders
    jt.pipe([(180, -470, deck_z), (180, -470, deck_z + 1.2)], 0.3, M["pipe_grey"], 12)
    jt.box((130, -480, deck_z + 2.5), (12, 8, 5), M["building"])                 # jetty control hut
    jt.build(collection="Marine")

    ship = tanker(M)
    ship.location = (212, -470, 0)
    ship.rotation_euler = (0, 0, math.radians(-90))
    bob(ship, amount=0.12, draft=0.0)

    # ---------------- light
    sun(elevation=15, azimuth=232, strength=4.2, color="#ffcf9e", angle=1.5)
    sky("#7ea6d1", strength=0.9, ground="#5e5a48")
    fog("#e8c7a4", near=900, far=3800)
    camera((560, -720, 190), (-60, 10, 10), lens=30)
