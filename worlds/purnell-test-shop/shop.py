"""The shop building and its fixtures: pre-engineered steel bay with a block wall on the east side,
liner panels elsewhere, open-web joists, two 5-ton bridge cranes, sectional and rolling doors,
LED high-bays and radiant tube heaters.

Shop coordinates (metres): x across the bay (-x = west liner wall, +x = east block wall),
y along the bay (y = 0 near end with two sectional doors, y = L far end with the big open door),
z up from the floor.
"""

from mathutils import Vector

from harness import *

# Measured from the photos (see world.py docstring for how).
W = 15.24          # clear width, wall to wall (50 ft bay)
L = 30.48          # length (100 ft); camera b's view puts the column lines exactly on 25 ft
EAVE = 9.1         # underside of the roof deck
JOIST_Z = 8.35     # joist bottom chord
RUNWAY_Z = 5.75    # crane runway beam underside
CMU_TOP = 6.1      # block wall height on the east wall
COLS_Y = [0.0, 7.62, 15.24, 22.86, L]   # 25 ft frame spacing

# Openings: (wall, centre along wall, width, height, kind)
#   wall "N" far end (y = L), "S" near end (y = 0), "W" liner wall (x = -W/2), "E" block wall.
OPENINGS = [
    ("N", -0.1, 8.5, 5.3, "open_sectional"),
    ("N", 5.8, 0.91, 2.13, "man_door"),
    ("S", 0.85, 3.66, 4.27, "sectional"),      # near-end doors seen in photo b
    ("S", -4.15, 3.66, 4.27, "sectional"),
    ("S", -6.9, 0.91, 2.13, "man_door"),
    ("W", 10.0, 4.0, 4.0, "rolling"),
    ("E", 26.5, 0.91, 2.13, "man_door"),
]


def mats():
    """Building materials; wall textures are generated (ribbed liner, painted block)."""
    import numpy as np
    M = {}
    # Liner panels: white ribbed steel (rib pattern in the normal map), light staining.
    n = 512
    x = np.arange(n) / n
    rib = np.where(((x * 4) % 1.0) < 0.12, 1.0, 0.0) * 0.6 + np.where(((x * 4) % 1.0) < 0.04, 0.4, 0.0)
    h = np.tile(rib[None, :], (n, 1)) + fbm_noise(n, 4, 3, 7) * 0.05
    stain = fbm_noise(n, 3, 5, 11)
    col = colorize(contrast(stain, 0.55, 0.95) * 0.35, "#d3d0c6", "#9a9486")
    col *= (1.0 - 0.10 * np.tile(rib[None, :], (n, 1))[..., None])
    M["liner"] = material("liner", texture=texture("liner_c", col), texture_size=0.914,
                          normal=texture("liner_n", height_normal(h, 6.0), data=True),
                          roughness=0.45, metallic=0.15)
    # CMU block wall painted white: 406 x 203 mm blocks, recessed mortar joints.
    n = 1024
    bx, by = 6, 12      # blocks per tile (tile = 2.436 m square)
    yy, xx = np.mgrid[0:n, 0:n] / n
    row = np.floor(yy * by)
    off = (row % 2) * 0.5
    fx = (xx * bx + off) % 1.0
    fy = (yy * by) % 1.0
    joint = np.minimum(np.minimum(fx, 1 - fx) * 0.406, np.minimum(fy, 1 - fy) * 0.203)
    mortar = np.clip(1 - joint / 0.006, 0, 1)
    pores = fbm_noise(n, 64, 2, 3)
    hgt = 1 - mortar * 0.8 + (pores - 0.5) * 0.08
    dirt = fbm_noise(n, 3, 5, 5)
    base = colorize(contrast(dirt, 0.5, 0.95) * 0.25 + (pores - 0.5) * 0.1, "#dcdad2", "#aca695")
    base *= (1 - mortar[..., None] * 0.12)
    M["cmu"] = material("cmu_painted", texture=texture("cmu_c", base), texture_size=2.436,
                        normal=texture("cmu_n", height_normal(hgt, 4.0), data=True), roughness=0.75)
    M["steel_dark"] = material("steel_dark", "#3c4246", roughness=0.55, metallic=0.5)
    M["joist"] = material("joist_black", "#1c1e20", roughness=0.6, metallic=0.4)
    M["deck"] = material("roof_liner", "#d8d8d2", roughness=0.7)
    M["crane"] = material("crane_yellow", "#e2a91a", roughness=0.45, metallic=0.1)
    M["hoist"] = material("hoist_grey", "#9aa0a3", roughness=0.4, metallic=0.5)
    M["rail"] = material("rail", "#5a5a58", roughness=0.4, metallic=0.8)
    M["conductor"] = material("conductor_orange", "#c8642a", roughness=0.5)
    M["door"] = material("door_panel", "#e6e6e2", roughness=0.4, metallic=0.2)
    M["door_groove"] = material("door_groove", "#9a9a96", roughness=0.5)
    M["glass"] = material("door_glass", "#ffffff", emission="#f4f7ff", emission_strength=4.0)
    M["rolling"] = material("rolling_door", "#b9bcbd", roughness=0.35, metallic=0.75)
    M["man_door"] = material("man_door", "#6f7478", roughness=0.4, metallic=0.4)
    M["led"] = material("led_panel", "#ffffff", emission="#fff8ee", emission_strength=18.0)
    M["led_housing"] = material("led_housing", "#d0d2d4", roughness=0.4, metallic=0.6)
    M["heater"] = material("radiant_tube", "#5b5b57", roughness=0.4, metallic=0.7)
    M["reflector"] = material("heater_reflector", "#c9cbc8", roughness=0.25, metallic=0.9)
    M["duct"] = material("duct_galv", "#b3b6b4", roughness=0.35, metallic=0.85)
    M["yard"] = material("yard_gravel", "#d9d2c4", roughness=0.95)
    M["sign_yellow"] = material("sign_yellow", "#f2d230", roughness=0.5)
    M["exit_green"] = material("exit_green", "#1c8a3c", emission="#25c050", emission_strength=1.5)
    M["red"] = material("alarm_red", "#c3241c", roughness=0.5)
    return M


# ------------------------------------------------------------------ walls

def _wall_with_openings(mb, wall, mat, z0, z1, openings):
    """Wall slab along one side, split around door openings (in that wall's own coordinates)."""
    t = 0.12
    if wall in ("N", "S"):
        y = L if wall == "N" else 0.0
        y += t / 2 if wall == "N" else -t / 2

        def box(a, b, za, zb):
            mb.box(((a + b) / 2, y, (za + zb) / 2), (b - a, t, zb - za), mat)
        lo, hi = -W / 2, W / 2
    else:
        x = -W / 2 - t / 2 if wall == "W" else W / 2 + t / 2

        def box(a, b, za, zb):
            mb.box((x, (a + b) / 2, (za + zb) / 2), (t, b - a, zb - za), mat)
        lo, hi = 0.0, L
    ops = sorted([(c - w / 2, c + w / 2, h) for (wl, c, w, h, k) in openings if wl == wall])
    cursor = lo
    for a, b, h in ops:
        if a > cursor:
            box(cursor, a, z0, z1)
        if z1 > max(h, z0):
            box(a, b, max(h, z0), z1)
        cursor = b
    if cursor < hi:
        box(cursor, hi, z0, z1)


def walls(M):
    mb = MeshBuilder("Walls_Liner")
    for wall in ("N", "S", "W"):
        _wall_with_openings(mb, wall, M["liner"], 0.0, EAVE + 0.4, OPENINGS)
    _wall_with_openings(mb, "E", M["liner"], CMU_TOP, EAVE + 0.4, OPENINGS)
    obj = mb.build(collection="Building")
    cmu = MeshBuilder("Wall_Block")
    _wall_with_openings(cmu, "E", M["cmu"], 0.0, CMU_TOP, OPENINGS)
    # Bond beam cap
    cmu.box((W / 2 + 0.06, L / 2, CMU_TOP + 0.05), (0.32, L, 0.1), M["cmu"])
    cmu_obj = cmu.build(collection="Building")
    for o in (obj, cmu_obj):
        o["no_cast"] = True
    return obj, cmu_obj


def floor(M, floor_mat):
    """Concrete slab with its own UV map: one unique texture over the whole floor."""
    verts = [(-W / 2, 0, 0), (W / 2, 0, 0), (W / 2, L, 0), (-W / 2, L, 0)]
    obj = mesh("Floor", verts, [(0, 1, 2, 3)], material=floor_mat, collection="Building")
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        x, y, _ = me.vertices[loop.vertex_index].co
        uv.data[li].uv = ((x + W / 2) / W, y / L)
    # Yard outside the big door and the near-end doors.
    for name, y0, y1, z1 in (("Yard", L + 0.12, L + 120, -0.6), ("YardSouth", -0.12, -60, -0.3)):
        yard = mesh(name, [(-40, y0, -0.02), (40, y0, -0.02), (40, y1, z1), (-40, y1, z1)],
                    [(0, 1, 2, 3)], material=M["yard"], collection="Building")
        yard["backdrop"] = True
    return obj


# ------------------------------------------------------------------ structure

def columns(M):
    """W-shape columns at every frame line on both side walls, with crane runway brackets."""
    mb = MeshBuilder("Columns")
    for y in COLS_Y:
        yy = min(max(y, 0.18), L - 0.18)
        for side in (-1, 1):
            x = side * (W / 2 - 0.16)
            d, b = 0.30, 0.25        # depth across the wall, flange width
            mb.box((x, yy - b / 2 + 0.008, EAVE / 2), (d, 0.016, EAVE), M["steel_dark"])
            mb.box((x, yy + b / 2 - 0.008, EAVE / 2), (d, 0.016, EAVE), M["steel_dark"])
            mb.box((x, yy, EAVE / 2), (0.012, b, EAVE), M["steel_dark"])
            # Runway bracket
            mb.box((x - side * 0.35, yy, RUNWAY_Z - 0.25), (0.45, 0.25, 0.5), M["steel_dark"])
    # Runway beams with rails
    for side in (-1, 1):
        x = side * (W / 2 - 0.55)
        mb.box((x, L / 2, RUNWAY_Z + 0.22), (0.2, L, 0.44), M["steel_dark"])
        mb.box((x, L / 2, RUNWAY_Z + 0.47), (0.06, L, 0.06), M["rail"])
    # Crane conductor bars (orange, under the runway on both walls; photos a and b)
    for side in (-1, 1):
        mb.box((side * (W / 2 - 0.42), L / 2, RUNWAY_Z - 0.12), (0.05, L - 0.4, 0.07), M["conductor"])
    # Wall girts on the liner walls (visible horizontal members)
    for z in (2.9, 5.6, 7.9):
        mb.box((-W / 2 + 0.08, L / 2, z), (0.1, L, 0.2), M["steel_dark"])
    obj = mb.build(collection="Structure")
    obj["no_cast"] = True
    return obj


def roof(M):
    """Open-web steel joists across the bay every 1.52 m, roof liner above. One joist mesh,
    instanced along the bay."""
    mb = MeshBuilder("Joist")
    depth = EAVE - 0.05 - JOIST_Z
    half = W / 2
    for z in (0.0, depth):
        mb.box((0, 0, z), (W, 0.09, 0.07), M["joist"])
    panel = 0.75
    n = int(W / panel)
    for i in range(n):
        x0 = -half + i * panel
        x1 = x0 + panel
        za, zb = (0.0, depth) if i % 2 == 0 else (depth, 0.0)
        mb.rod((x0, 0, za), (x1, 0, zb), 0.016, M["joist"], 5)
    joist = prefab(mb.build())
    y = 0.76
    while y < L:
        instance(joist, "Joist", (0, y, JOIST_Z), collection="Roof")["ceiling"] = True
        y += 1.524
    deck = MeshBuilder("RoofDeck")
    deck.box((0, L / 2, EAVE + 0.05), (W + 0.3, L + 0.3, 0.1), M["deck"])
    # Bridging lines along the bay under the joists
    for x in (-4.5, 0.0, 4.5):
        deck.box((x, L / 2, JOIST_Z + depth / 2), (0.04, L, 0.04), M["joist"])
    d = deck.build(collection="Roof")
    d["no_cast"] = True
    d["ceiling"] = True
    return d


def lights(M):
    """4-lamp LED high-bay fixtures: emissive panels plus a real area light each for the render
    (the viewer lights the interior with interior() instead)."""
    import bpy
    mb = MeshBuilder("HighBay")
    mb.box((0, 0, 0.06), (1.22, 0.42, 0.1), M["led_housing"])
    mb.box((0, 0, 0.004), (1.16, 0.36, 0.008), M["led"])
    fixture = prefab(mb.build())
    data = bpy.data.lights.new("HighBayLight", "AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y = 1.16, 0.36
    data.energy = 260.0
    data.color = (1.0, 0.97, 0.93)
    spots = []
    for x in (-4.6, 0.0, 4.6):
        y = 3.0
        while y < L - 1:
            spots.append((x, y))
            y += 6.1
    for x, y in spots:
        z = JOIST_Z - 0.55
        instance(fixture, "HighBay", (x, y, z), (0, 0, 90), collection="Lights")["ceiling"] = True
        o = bpy.data.objects.new("HighBayLight", data)
        o.location = (x, y, z - 0.02)
        bpy.context.scene.collection.objects.link(o)
    # Radiant tube heaters along both walls
    hb = MeshBuilder("Heaters")
    for side in (-1, 1):
        x = side * (W / 2 - 1.3)
        for y0 in (2.5, 16.5):
            y1 = y0 + 12
            hb.rod((x, y0, 5.2), (x, y1, 5.2), 0.05, M["heater"], 10)
            hb.box((x, (y0 + y1) / 2, 5.32), (0.38, y1 - y0, 0.02), M["reflector"], rotation=(0, side * 25, 0))
            hb.box((x, y0 - 0.3, 5.2), (0.3, 0.6, 0.35), M["heater"])
    hb.build(collection="Building")


def doors(M):
    """Sectional doors (closed, with two window rows), the raised big door, rolling and man doors."""
    mb = MeshBuilder("Doors")
    t = 0.06
    for wall, c, w, h, kind in OPENINGS:
        if wall in ("N", "S"):
            sgn = 1 if wall == "N" else -1
            y = (L if wall == "N" else 0.0) - sgn * 0.02

            def at(u, z, dy=0.0):
                return (c + u, y + dy, z)

            def size(a, b):
                return (a, t, b)
        else:
            sgn = -1 if wall == "W" else 1
            x = (-W / 2 if wall == "W" else W / 2) - sgn * 0.02

            def at(u, z, dy=0.0):
                return (x + dy, c + u, z)

            def size(a, b):
                return (t, a, b)
        if kind == "sectional":
            panels = 8
            ph = h / panels
            for i in range(panels):
                z = i * ph + ph / 2
                if i in (5, 6):   # two window rows, five lites each
                    lites = 5
                    for k in range(lites):
                        u = -w / 2 + (k + 0.5) * w / lites
                        mb.box(at(u, z), size(w / lites - 0.08, ph - 0.1), M["glass"])
                    for k in range(lites + 1):
                        mb.box(at(-w / 2 + k * w / lites, z, -sgn * 0.005), size(0.08, ph), M["door"])
                    mb.box(at(0, z - ph / 2 + 0.03, -sgn * 0.005), size(w, 0.06), M["door"])
                    mb.box(at(0, z + ph / 2 - 0.03, -sgn * 0.005), size(w, 0.06), M["door"])
                else:
                    mb.box(at(0, z), size(w, ph - 0.012), M["door"])
                    mb.box(at(0, z - ph / 2, sgn * 0.004), size(w, 0.02), M["door_groove"])
            for s in (-1, 1):   # tracks
                mb.box(at(s * (w / 2 + 0.06), h / 2, -sgn * 0.08), size(0.08, h), M["rail"])
            mb.box(at(0, h + 0.4, -sgn * 0.3), size(w + 0.2, 0.06), M["rail"])
        elif kind == "open_sectional":
            # Panels stacked overhead on the horizontal tracks, just inside the header.
            for s in (-1, 1):
                mb.box(at(s * (w / 2 + 0.06), h / 2, -sgn * 0.08), size(0.08, h), M["rail"])
            if wall == "N":
                mb.box((c, L - 2.4, h + 0.35), (w, 4.6, 0.05), M["door"])
                for s in (-1, 1):
                    mb.box((c + s * (w / 2 + 0.06), L - 2.4, h + 0.42), (0.06, 4.8, 0.08), M["rail"])
                mb.box((c, L - 0.05, h + 0.25), (w + 0.4, 0.12, 0.3), M["rail"])   # header
        elif kind == "rolling":
            slat = 0.075
            n = int(h / slat)
            for i in range(n):
                mb.box(at(0, i * slat + slat / 2), size(w, slat - 0.008), M["rolling"])
            mb.rod(Vector(at(-w / 2 - 0.1, h + 0.3, -sgn * 0.2)), Vector(at(w / 2 + 0.1, h + 0.3, -sgn * 0.2)),
                   0.28, M["rolling"], 20)
        elif kind == "man_door":
            mb.box(at(0, h / 2), size(w, h), M["man_door"])
            mb.box(at(w * 0.35, 1.0, -sgn * 0.05), size(0.12, 0.03), M["rail"])
            mb.box(at(0, h + 0.18, -sgn * 0.06), size(0.3, 0.14), M["exit_green"])
    # Louvre above the far man door and the yellow crane-safety sign on the block wall
    mb.box((5.8, L - 0.03, 4.75), (0.8, 0.04, 0.7), M["duct"])
    mb.box((W / 2 - 0.03, 20.5, 3.2), (0.02, 0.6, 1.0), M["sign_yellow"])
    return mb.build(collection="Building")


def crane(M, name, y, hoist_x, label):
    """Single-girder top-running bridge crane: yellow box girder, end trucks, electric hoist and
    hook block, painted ID and capacity."""
    mb = MeshBuilder(name)
    span = W - 1.1
    gz = RUNWAY_Z + 0.55 + 0.32
    mb.box((0, y, gz), (span, 0.38, 0.64), M["crane"])
    for s in (-1, 1):   # end trucks riding the rails
        mb.box((s * span / 2, y, RUNWAY_Z + 0.72), (0.35, 2.6, 0.42), M["crane"])
        for k in (-1, 1):
            mb.cylinder((s * span / 2, y + k * 1.0, RUNWAY_Z + 0.5), 0.12, 0.05, M["rail"], 12)
    # Hoist under the girder
    hx = hoist_x
    mb.box((hx, y, gz - 0.75), (0.9, 0.5, 0.45), M["hoist"])
    mb.cylinder((hx + 0.5, y, gz - 0.95), 0.18, 0.4, M["hoist"], 16)
    hook_z = 2.6
    for s in (-0.06, 0.06):
        mb.rod((hx + s, y, gz - 0.95), (hx + s, y, hook_z + 0.35), 0.006, M["rail"], 4)
    mb.box((hx, y, hook_z + 0.2), (0.22, 0.12, 0.3), M["crane"])
    mb.torus((hx, y, hook_z - 0.05), 0.07, 0.022, M["rail"], 16, 6, arc=270, start=90)
    obj = mb.build(collection="Cranes")
    # Painted lettering on both faces of the girder
    from harness import text_image, texture, decal
    img = texture(f"crane_{label}", text_image(f"{label}            5 TON", "#1d3c78", 96), fmt="png")
    for s in (-1, 1):
        decal(f"{name}_label{s}", img, (span * 0.62, 0.3), (0, y + s * 0.195, gz - 0.03),
              (90, 0, 0 if s < 0 else 180), collection="Cranes")
    return obj
