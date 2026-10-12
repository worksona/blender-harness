"""Gas processing station, modelled from reference/photo.jpg.

Layout (meters, camera near the origin looking +Y): a horizontal filter-separator with sump in the
middle, a smaller horizontal vessel and a bullet tank to its left, three vertical scrubbers with
round top platforms to the right, a caged ladder tower, a raised steel deck at the back left, a
light mast, an electrical cabinet in front right, and big yellow pipe loops tying it together.
"""

import math

from mathutils import Matrix, Vector

from harness import *

META = {
    "title": "Gas Processing Station",
    "description": "Filter-separators, scrubbers and big yellow pipe loops, matched to a reference photo.",
    "tags": ["industrial", "photo-matched", "pipelines"],
    "seed": 5,
    "render": {"res": "1100x750", "samples": 64, "view": "Standard"},
    "viewer": {"tone": "neutral"},
}

YAW = 50.0           # the horizontal vessels' common heading (degrees; right ends recede)
PIPE_R = 0.30        # big yellow process pipe radius


def placer(origin, yaw=YAW):
    """local (x along the vessel axis, y, z) -> world point, for a vessel placed at origin/yaw."""
    m = Matrix.Translation(origin) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    return lambda x, y=0.0, z=0.0: m @ Vector((x, y, z))


def mats():
    return {
        "vessel": material("vessel_grey", "#717c86", roughness=0.22, metallic=0.3),
        "tank": material("bullet_grey", "#b7bcc0", roughness=0.35, metallic=0.2),
        "yellow": material("pipe_yellow", "#ffb200", roughness=0.25),
        "dark": material("platform_dark", "#33383d", roughness=0.6, metallic=0.3),
        "galv": material("galvanized", "#8f9599", roughness=0.4, metallic=0.7),
        "steel": material("steel_grey", "#5e656b", roughness=0.5, metallic=0.4),
        "concrete": material("concrete", "#b9b4a8", roughness=0.9),
        "cabinet": material("cabinet_beige", "#d6d1bf", roughness=0.55),
        "red": material("valve_red", "#c62a22", roughness=0.4),
        "blue": material("cable_blue", "#2e5ea8", roughness=0.6),
        "lamp": material("lamp_white", "#eef0f2", roughness=0.4),
    }


def horizontal_vessel(name, M, origin, radius, length, mat, saddles=2, closure=True, yaw=YAW):
    """Horizontal vessel along local X centered on origin. Returns (object, to_world)."""
    mb = MeshBuilder(name)
    half = length / 2
    mb.rod((-half, 0, 0), (half, 0, 0), radius, M[mat], 48, caps=False)
    mb.sphere((-half, 0, 0), radius, M[mat], 4, (0.42, 1, 1))
    mb.sphere((half, 0, 0), radius, M[mat], 4, (0.42, 1, 1))
    for k in (-1, 1):  # girth seams
        mb.rod((k * half * 0.98 - 0.02, 0, 0), (k * half * 0.98 + 0.02, 0, 0), radius + 0.015, M[mat], 48,
               caps=False)
    if closure:  # quick-opening closure ring on the left head
        mb.rod((-half - radius * 0.38, 0, 0), (-half - radius * 0.46, 0, 0), radius * 0.62, M[mat], 40)
        mb.torus((-half - radius * 0.42, 0, 0), radius * 0.62, 0.05, M[mat], 40, 6)
    ground, saddle_top = -origin[2], -radius * 0.55   # local z of grade and of the saddle's top
    for i in range(saddles):
        x = -half * 0.6 + i * (1.2 * half) / max(1, saddles - 1)
        mb.box((x, 0, (ground + 0.4 + saddle_top) / 2), (0.35, radius * 1.5, saddle_top - ground - 0.4),
               M["steel"])
        mb.box((x, 0, ground + 0.2), (0.9, radius * 1.9, 0.4), M["concrete"])
    obj = mb.build(location=origin, rotation=(0, 0, yaw), collection="Vessels")
    return obj, placer(origin, yaw)


def vertical_scrubber(mb, M, x, y, radius, shell_top, platform_z, platform_r):
    """Vertical vessel on a short skirt with a round top platform, yellow rail and fascia."""
    mb.cylinder((x, y, 0), radius * 0.9, 1.2, M["steel"], 40)
    mb.box((x, y, 0.15), (radius * 2.6, radius * 2.6, 0.3), M["concrete"])
    mb.rod((x, y, 1.2), (x, y, shell_top), radius, M["vessel"], 48, caps=False)
    mb.dome((x, y, 1.2), radius, -radius * 0.5, M["vessel"], 48, 6)
    mb.dome((x, y, shell_top), radius, radius * 0.5, M["vessel"], 48, 6)
    for z in (1.6, shell_top - 0.3):
        mb.torus((x, y, z), radius + 0.01, 0.02, M["vessel"], 48, 4)
    # Platform: dark deck, yellow fascia band and rails, brackets down to the shell.
    mb.cylinder((x, y, platform_z - 0.25), platform_r, 0.25, M["dark"], 48)
    mb.rod((x, y, platform_z - 0.05), (x, y, platform_z + 0.12), platform_r + 0.02, M["yellow"], 48,
           caps=False)
    mb.ring_platform((x, y, platform_z + 0.05), radius * 0.4, platform_r, M["dark"], M["yellow"], 40)
    mb.torus((x, y, platform_z + 0.75), platform_r - 0.05, 0.02, M["yellow"], 40, 4)
    for k in range(6):
        a = math.tau * k / 6
        p0 = Vector((x + radius * math.cos(a), y + radius * math.sin(a), platform_z - 1.7))
        p1 = Vector((x + platform_r * 0.92 * math.cos(a), y + platform_r * 0.92 * math.sin(a),
                     platform_z - 0.25))
        mb.beam(p0, p1, 0.12, M["dark"])
    # Instruments and small valves on the deck.
    for k, (dx, dy) in enumerate(((0.6, -0.3), (-0.5, 0.4), (0.2, 0.7))):
        base = Vector((x + dx, y + dy, platform_z + 0.05))
        mb.rod(base, base + Vector((0, 0, 0.6)), 0.05, M["galv"], 8)
        mb.box(base + Vector((0, 0, 0.7)), (0.22, 0.18, 0.2), M["red"] if k == 1 else M["galv"])
        mb.handwheel(base + Vector((0, 0, 0.95)), (0, 0, 1), 0.12, M["yellow"] if k else M["red"], M["galv"])


def build(ctx):
    M = mats()

    gravel = material("gravel", "#a48f70", roughness=0.95)
    plane("Yard", size=600, material=gravel, backdrop=True)

    # Positions below were measured off the reference photo: camera 2.2 m up, pitched 6 deg,
    # 22 mm lens; each object's distance from its known size and its share of the frame.

    # ---- horizontal vessels -------------------------------------------------------------
    H1_R, H1_L = 1.1, 4.6
    H2_R, H2_L = 0.8, 3.6
    h1_obj, h1 = horizontal_vessel("FilterSeparator", M, (-0.6, 8.6, 2.1), H1_R, H1_L, "vessel")
    h2_obj, h2 = horizontal_vessel("InletVessel", M, (-3.6, 9.6, 1.85), H2_R, H2_L, "vessel")
    horizontal_vessel("BulletTank", M, (-9.4, 13.0, 2.2), 1.7, 10.0, "tank", saddles=3, closure=False,
                      yaw=28.0)

    pipes = MeshBuilder("ProcessPiping")
    # Sump barrel under the filter-separator, with its two down-comers.
    sump_a, sump_b = h1(-1.0, 0, -1.45), h1(2.2, 0, -1.45)
    pipes.rod(sump_a, sump_b, 0.38, M["vessel"], 40, caps=False)
    pipes.sphere(sump_a, 0.38, M["vessel"], 3)
    pipes.sphere(sump_b, 0.38, M["vessel"], 3)
    for lx in (-0.5, 1.7):
        pipes.rod(h1(lx, 0, -1.2), h1(lx, 0, -0.9), 0.16, M["vessel"], 20)
        pipes.flange(h1(lx, 0, -1.05), (0, 0, 1), 0.16, M["vessel"])

    # Left heads: grey neck, yellow flange, then the big yellow line sweeping toward the
    # camera and out of frame at the lower left.
    for to_w, r_vessel, half, exit_xy in ((h1, H1_R, H1_L / 2, (-5.0, 2.6)),
                                         (h2, H2_R, H2_L / 2, (-8.0, 4.4))):
        x_head = -half - r_vessel * 0.46
        neck0, neck1 = to_w(x_head), to_w(x_head - 0.5)
        pipes.rod(neck0, neck1, PIPE_R * 1.05, M["vessel"], 32)
        pipes.flange(neck1, neck1 - neck0, PIPE_R, M["yellow"], bolts=20)
        out = to_w(x_head - 0.6)
        elbow = to_w(x_head - 1.5)
        down = Vector((elbow.x, elbow.y, 0.7))
        exit_pt = Vector((*exit_xy, 0.6))
        bury = exit_pt + (exit_pt - down).normalized() * 3 + Vector((0, 0, -1.4))
        pipes.tube([out, elbow, down, exit_pt, bury], PIPE_R, M["yellow"], bend_radius=0.9)

    # Inverted-U from the separator's top nozzle, down and across toward the cabinet.
    top = h1(0.4, 0, H1_R)
    pipes.rod(h1(0.4, 0, H1_R - 0.2), top + Vector((0, 0, 0.3)), PIPE_R * 1.05, M["vessel"], 32)
    pipes.flange(top + Vector((0, 0, 0.35)), (0, 0, 1), PIPE_R, M["yellow"], bolts=20)
    pipes.tube([top + Vector((0, 0, 0.42)), Vector((top.x, top.y, 4.9)), Vector((2.4, top.y - 0.6, 4.9)),
                Vector((2.4, top.y - 0.6, 0.9)), Vector((3.4, top.y - 1.6, 0.9))], PIPE_R, M["yellow"],
               bend_radius=0.75)
    pipes.flange((3.45, top.y - 1.65, 0.9), (1, -1, 0), PIPE_R, M["yellow"])

    # Loop from the inlet vessel over to the back of the separator.
    l0 = h2(1.0, 0, H2_R)
    pipes.flange(l0 + Vector((0, 0, 0.1)), (0, 0, 1), PIPE_R * 0.8, M["yellow"])
    pipes.tube([l0 + Vector((0, 0, 0.15)), Vector((l0.x, l0.y, 3.9)), h1(-1.6, 1.6, 1.9),
                h1(-1.6, 1.6, -1.5), h1(0.2, 1.6, -1.5)], PIPE_R * 0.8, M["yellow"], bend_radius=0.6)

    # ---- vertical scrubbers, ladder tower --------------------------------------------------
    V1 = (5.1, 9.1, 0.95, 5.4, 6.1, 1.5)     # x, y, radius, shell top, platform z, platform radius
    V2 = (2.0, 12.4, 0.85, 5.6, 6.3, 1.45)
    V3 = (-0.2, 16.0, 0.7, 6.0, 6.7, 1.2)
    vert = MeshBuilder("Scrubbers")
    for v in (V1, V2, V3):
        vertical_scrubber(vert, M, *v)
    x, y, r = V1[:3]
    vert.rod((x, y - r, 4.3), (x, y - r - 0.4, 4.3), 0.3, M["vessel"], 32)        # manway
    vert.rod((x, y - r - 0.4, 4.3), (x, y - r - 0.5, 4.3), 0.42, M["vessel"], 32)
    vert.torus((x, y - r - 0.51, 4.3), 0.12, 0.03, M["vessel"], 16, 4)
    vert.build(collection="Vessels")

    # Overhead loops from the scrubber tops down to grade.
    for (x, y, r, shell_top, plat_z, plat_r), rise_to, over in ((V1, 8.1, 1.65), (V2, 8.0, 1.05)):
        head = Vector((x, y, shell_top + r * 0.5))
        pipes.flange(head + Vector((0, 0, 0.25)), (0, 0, 1), PIPE_R, M["yellow"])
        pipes.tube([head, Vector((x, y, rise_to)), Vector((x + over, y, rise_to)),
                    Vector((x + over, y, 0.8)), Vector((x + over, y - 2.5, 0.8)),
                    Vector((x + over, y - 3.5, -0.6))], PIPE_R, M["yellow"], bend_radius=0.8)
    # Scrubber bottom nozzle with a yellow elbow running right.
    x, y, r = V1[:3]
    pipes.rod((x + r, y, 2.0), (x + r + 0.4, y, 2.0), PIPE_R, M["vessel"], 32)
    pipes.flange((x + r + 0.45, y, 2.0), (1, 0, 0), PIPE_R, M["yellow"])
    pipes.tube([(x + r + 0.5, y, 2.0), (x + 2.6, y, 2.0), (x + 2.6, y, 0.7), (x + 2.6, y - 3.5, 0.7)],
               PIPE_R, M["yellow"], bend_radius=0.7)
    pipes.build(collection="Piping")

    tower = MeshBuilder("LadderTower")
    tx, ty, th = 3.95, 10.9, 7.4
    corners = [(tx - 0.5, ty - 0.5), (tx + 0.5, ty - 0.5), (tx + 0.5, ty + 0.5), (tx - 0.5, ty + 0.5)]
    for cx_, cy_ in corners:
        tower.rod((cx_, cy_, 0), (cx_, cy_, th), 0.06, M["yellow"], 10)
    for z in [0.4] + [1.2 * k for k in range(1, int(th / 1.2) + 1)]:  # horizontal ties
        for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
            tower.rod((ax, ay, z), (bx, by, z), 0.04, M["yellow"], 8)
    tower.ladder((tx, ty - 0.58, 0), th, M["yellow"], facing=-90, cage=True)
    tower.slab(tx - 0.8, ty - 0.8, tx + 0.8, ty + 0.8, th, 0.08, M["dark"])
    tower.railing([(tx - 0.8, ty - 0.8, th), (tx + 0.8, ty - 0.8, th), (tx + 0.8, ty + 0.8, th),
                   (tx - 0.8, ty + 0.8, th)], M["yellow"], closed=True)
    for (px, py, _r, _top, pz, pr) in (V1, V2):  # walkways to the scrubber decks
        d = Vector((px - tx, py - ty, 0))
        end = Vector((tx, ty, pz)) + d.normalized() * (d.length - pr)
        tower.beam((tx, ty, pz), end, 0.16, M["yellow"])
        tower.beam((tx, ty, pz - 0.9), end + Vector((0, 0, -0.1)), 0.1, M["yellow"])
    tower.build(collection="Structures")

    # ---- raised deck with stair, light mast ------------------------------------------------
    deck = MeshBuilder("RaisedDeck")
    x0, x1, y0, y1, dz = -9.2, -1.2, 14.2, 17.2, 3.5
    for x in (x0, (x0 + x1) / 2, x1):
        for y in (y0, y1):
            deck.beam((x, y, 0), (x, y, dz), 0.22, M["steel"])
    deck.slab(x0, y0, x1, y1, dz, 0.15, M["galv"])
    deck.box(((x0 + x1) / 2, y0, dz - 0.25), (x1 - x0, 0.15, 0.35), M["steel"])
    deck.railing([(x0, y0, dz), (x1, y0, dz), (x1, y1, dz), (x0, y1, dz)], M["galv"], post_step=1.5,
                 closed=True)
    steps = 15
    for s_ in range(steps):  # stair down to the left
        t = (s_ + 0.5) / steps
        deck.box((x0 - 0.2 - t * 3.0, (y0 + y1) / 2, dz * (1 - t)), (0.28, 1.0, 0.05), M["galv"])
    for side in (-0.55, 0.55):
        deck.beam((x0, (y0 + y1) / 2 + side, dz), (x0 - 3.2, (y0 + y1) / 2 + side, 0), 0.12, M["steel"])
        deck.railing([(x0, (y0 + y1) / 2 + side, dz), (x0 - 3.2, (y0 + y1) / 2 + side, 0)], M["galv"],
                     post_step=1.2)
    for bx, mat in ((-8.0, "red"), (-7.1, "galv"), (-4.6, "steel"), (-3.4, "galv")):
        deck.box((bx, 15.6, dz + 0.45), (0.8, 0.7, 0.9), M[mat])
    mast = Vector((-5.3, 25.0, 0))
    deck.rod(mast, mast + Vector((0, 0, 8.0)), 0.16, M["lamp"], 16, radius_b=0.09)
    deck.ring_platform((mast.x, mast.y, 7.0), 0.1, 0.8, M["lamp"], M["lamp"], 16)
    for k in range(4):
        a = math.tau * k / 4
        deck.box((mast.x + 0.5 * math.cos(a), mast.y + 0.5 * math.sin(a), 8.0), (0.45, 0.45, 0.32), M["lamp"])
    deck.rod(mast + Vector((0, 0, 8.0)), mast + Vector((0, 0, 9.0)), 0.04, M["lamp"], 6)
    deck.build(collection="Structures")

    # ---- foreground: cabinet, small lines on sleepers, valve stands ---------------------------
    fg = MeshBuilder("Foreground")
    cx, cy, cw, cz0, cz1 = 3.9, 4.6, 4.6, 0.62, 2.0
    fg.box((cx, cy, (cz0 + cz1) / 2), (cw, 0.9, cz1 - cz0), M["cabinet"])
    for k in range(5):
        fg.box((cx - cw / 2 + k * cw / 4, cy - 0.46, (cz0 + cz1) / 2), (0.05, 0.03, cz1 - cz0), M["galv"])
    for z in (cz0 + 0.03, cz1 - 0.03):
        fg.box((cx, cy - 0.46, z), (cw, 0.04, 0.06), M["galv"])
    for dx in (-cw / 2 + 0.1, cw / 2 - 0.1):
        for dy in (-0.4, 0.4):
            fg.beam((cx + dx, cy + dy, 0), (cx + dx, cy + dy, cz0), 0.08, M["galv"])
    for k in range(14):  # cable tails under the cabinet
        x = cx - 2.0 + k * 0.3
        fg.rod((x, cy + 0.1, cz0), (x + 0.05, cy + 0.1, 0.0), 0.025,
               [M["galv"], M["yellow"], M["blue"], M["red"]][k % 4], 6)
    for (a, b, r, z) in (((-7.0, 4.9), (-0.4, 4.6), 0.13, 0.5), ((0.1, 5.3), (8.0, 5.0), 0.13, 0.42),
                         ((-5.0, 6.6), (6.0, 6.2), 0.08, 0.3)):
        fg.rod((a[0], a[1], z), (b[0], b[1], z), r, M["galv"], 20)
        n = int(abs(b[0] - a[0]) / 2.5)
        for i in range(n + 1):
            t = i / max(n, 1)
            fg.box((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, (z - r) / 2), (0.4, 0.4, z - r),
                   M["concrete"])
    for (vx, vy, red) in ((-1.4, 5.9, False), (-0.5, 6.1, True), (0.5, 5.8, False), (2.4, 7.4, True),
                          (-2.6, 6.5, False)):
        fg.rod((vx, vy, 0), (vx, vy, 1.3), 0.05, M["galv"], 8)
        fg.sphere((vx, vy, 0.9), 0.1, M["red"] if red else M["galv"], 2)
        fg.handwheel((vx, vy, 1.35), (0, 0, 1), 0.14, M["red"] if red else M["yellow"], M["galv"])
        fg.rod((vx, vy, 0.6), (vx + 0.6, vy + 0.3, 0.6), 0.04, M["galv"], 6)
    fg.box((2.45, 7.5, 0.9), (0.45, 0.35, 0.4), M["red"])  # actuator
    fg.build(collection="Foreground")

    # Fair-weather cumulus far off, roughly where they sit in the photo (left and overhead).
    cloud_mat = material("cloud", "#ffffff", roughness=1.0, emission="#eef4ff", emission_strength=0.5,
                         alpha=0.8)
    clouds = MeshBuilder("Clouds")
    rng = ctx.rng
    for (az, el, size) in ((-38, 9, 70), (-30, 6, 45), (-25, 12, 40), (-8, 33, 90), (2, 30, 60),
                           (-45, 3, 60), (12, 34, 50), (-15, 20, 35)):
        dist = 700
        a, e = math.radians(az), math.radians(el)
        c = Vector((dist * math.sin(a) * math.cos(e), dist * math.cos(a) * math.cos(e), 2.2 + dist * math.sin(e)))
        for k in range(14):
            off = Vector((rng.uniform(-1.2, 1.2) * size, rng.uniform(-0.3, 0.3) * size,
                          rng.uniform(-0.05, 0.12) * size))
            clouds.sphere(c + off, size * rng.uniform(0.1, 0.24), cloud_mat, 2, (2.0, 0.8, 0.22))
    clouds.build(collection="Sky")

    sun(elevation=45, azimuth=190, strength=4.0, color="#fff7ea")
    sky("#1f74de", strength=0.8, ground="#a08d6c")
    fog("#a4cdf3", near=150, far=900)
    camera((0.0, 0.0, 2.2), (0.0, 20.0, 2.2 + 20 * math.tan(math.radians(6))), lens=22)
