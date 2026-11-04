"""A generic mid-century medium tank, modelled part by part.

Local frame: +X forward, +Y to the left, Z up, origin on the ground under the hull centre.
The hull (with running gear) and the turret are separate meshes so every tank on the field can
traverse its turret independently while both stay instanced prefabs.

Main dimensions (m): hull 6.1 long, 3.1 wide over the tracks, deck at 1.62; turret ring centre
0.55 ahead of the hull centre; gun axis 2.02 above the ground; barrel reaches 5.6 ahead of the
turret ring.
"""

import math

import bmesh
import numpy as np
from mathutils import Euler, Matrix, Vector

from harness import MeshBuilder, material, texture
from harness.builder import _template
from harness.textures import blur, colorize, contrast, fbm_noise, height_normal, value_noise

TRACK_Y = 1.27          # track centre line, either side
TRACK_W = 0.52
LINK_PITCH = 0.165
LINK_T = 0.08           # link thickness (to the guide-horn base)
WHEEL_R = 0.40
WHEEL_X = (-1.96, -0.98, 0.0, 0.98, 1.96)
WHEEL_Z = WHEEL_R + LINK_T
SPROCKET = (-2.80, 0.64, 0.36)   # rear drive sprocket: x, z, pitch radius
IDLER = (2.82, 0.58, 0.34)
ROLLERS = ((-1.47, 0.86, 0.10), (0.0, 0.88, 0.10), (1.47, 0.86, 0.10))
DECK_Z = 1.62
SPONSON_Z = 1.05
TURRET_X = 0.55
GUN_Z = 0.40            # gun axis above the turret ring
GLACIS_A = (3.08, 0.78)  # glacis bottom (x, z) and top
GLACIS_B = (2.00, DECK_Z)


# ---------------------------------------------------------------- materials

def _paint_pixels(base, dirt, seed, size=512):
    """Worn field paint: mottled fading, darker grime, chipped edges and vertical streaks."""
    big = fbm_noise(size, 3, 6, seed)
    fine = fbm_noise(size, 24, 3, seed + 3)
    chips = contrast(fbm_noise(size, 40, 2, seed + 5), 0.78, 0.83) * 0.8
    # Long vertical rain/grime streaks: fine noise smeared down the plate (wrapping, so it tiles).
    v = value_noise((size, size), 96, seed + 9)
    streak = sum(np.roll(v, k, axis=0) for k in range(0, 48, 3)) / 16
    t = contrast(big, 0.45, 0.85) * 0.55 + (fine - 0.5) * 0.25 + contrast(streak, 0.55, 0.9) * 0.3
    px = colorize(np.clip(t, 0, 1), base, dirt)
    fade = (contrast(big, 0.2, 0.5) * 0.08)[..., None]
    px = px + fade                                                  # sun-faded patches
    px = px * (1 - chips[..., None]) + np.array([0.20, 0.19, 0.17]) * chips[..., None]
    return np.clip(px, 0, 1)


def materials(burnt=False):
    """All tank materials. burnt=True gives the burnt-out wreck's set (same names + _burnt)."""
    sfx = "_burnt" if burnt else ""
    M = {}
    if burnt:
        # Burnt out: paint gone to black char and orange-brown rust, grey ash in patches.
        rust = contrast(fbm_noise(512, 5, 6, 41), 0.35, 0.75)
        px = colorize(rust, "#141210", "#7a3a16")
        ash = contrast(fbm_noise(512, 9, 5, 44), 0.62, 0.85)[..., None]
        px = px * (1 - ash * 0.7) + np.array([0.36, 0.34, 0.32]) * ash * 0.7
        paint_img = texture("tank_paint_burnt", px)
        cast_img = paint_img
    else:
        paint_img = texture("tank_paint", _paint_pixels("#3d4a3f", "#1d2320", 11))
        cast_img = texture("tank_cast", _paint_pixels("#3b483d", "#1d2320", 12))
    rough = texture("tank_rough", 0.5 + 0.35 * fbm_noise(512, 8, 4, 13), data=True)
    plate_n = texture("tank_plate_n", height_normal(fbm_noise(512, 32, 3, 14), 1.2), data=True)
    cast_h = fbm_noise(512, 12, 5, 15) * 0.7 + fbm_noise(512, 64, 2, 16) * 0.3
    cast_n = texture("tank_cast_n", height_normal(cast_h, 5.0), data=True)
    M["paint"] = material("tank_paint" + sfx, texture=paint_img, texture_size=1.6,
                          roughness_map=rough, normal=plate_n, metallic=0.15)
    M["cast"] = material("tank_cast" + sfx, texture=cast_img, texture_size=1.3,
                         roughness_map=rough, normal=cast_n, metallic=0.15)
    if burnt:
        M["mud"] = M["paint"]
        M["track"] = material("track_burnt", "#3a2a20", roughness=0.85, metallic=0.4,
                              texture=texture("rust", _rust_pixels(51)), texture_size=0.6)
        M["rubber"] = material("rubber_burnt", "#2a2724", roughness=0.95, metallic=0.3)
    else:
        slush = fbm_noise(512, 6, 5, 17)
        frost = contrast(fbm_noise(512, 18, 4, 18), 0.55, 0.75)
        px = colorize(contrast(slush, 0.3, 0.8), "#3e4440", "#2f2c27")
        px = px * (1 - frost[..., None] * 0.75) + np.array([0.82, 0.85, 0.9]) * frost[..., None] * 0.75
        M["mud"] = material("tank_mud", texture=texture("tank_mud", px), texture_size=1.2,
                            roughness=0.85, normal=plate_n)
        M["track"] = material("track_steel", texture=texture("track_steel", _track_pixels(19)),
                              texture_size=0.5, roughness=0.6, metallic=0.55)
        M["rubber"] = material("rubber", "#1e1e1c", roughness=0.85)
    M["dark"] = material("gun_dark" + sfx, "#121211", roughness=0.7, metallic=0.3)
    M["glass"] = material("vision_glass" + sfx, "#0f1a22" if not burnt else "#151210",
                          roughness=0.06 if not burnt else 0.9, metallic=0.3)
    M["steel"] = material("bare_steel" + sfx, "#55534e" if not burnt else "#3a2e26", roughness=0.4,
                          metallic=0.8)
    M["soot"] = material("exhaust_soot" + sfx, "#2a2420", roughness=0.9, metallic=0.3)
    M["wood"] = material("log_wood" + sfx,
                         texture=texture("wood" + sfx, _wood_pixels(21, burnt)), texture_size=0.8,
                         roughness=0.9)
    M["canvas"] = material("canvas" + sfx, "#5a5a3e" if not burnt else "#2a2520", roughness=0.95,
                           normal=plate_n)
    M["snow"] = material("snow_crust", "#e6ecf4", roughness=0.55,
                         normal=texture("snow_lumps_n", height_normal(fbm_noise(256, 8, 4, 22), 3.0),
                                        data=True), texture_size=0.8)
    if burnt:
        M["red"] = M["dark"]
        M["lens"] = M["glass"]
    else:
        M["red"] = material("tail_light", "#ff2a12", emission="#ff2a12", emission_strength=3.0)
        M["lens"] = material("head_lens", "#9aa6ae", roughness=0.05, metallic=0.4)
    return M


def _rust_pixels(seed):
    t = fbm_noise(512, 8, 5, seed)
    px = colorize(contrast(t, 0.3, 0.8), "#2a2420", "#6b3a1c")
    return px


def _track_pixels(seed):
    rust = contrast(fbm_noise(512, 10, 5, seed), 0.45, 0.8)
    worn = contrast(fbm_noise(512, 40, 3, seed + 1), 0.7, 0.85)
    px = colorize(rust, "#3c3833", "#5b3c26")
    px = px * (1 - worn[..., None]) + np.array([0.55, 0.55, 0.53]) * worn[..., None]
    return px


def _wood_pixels(seed, burnt):
    grain = value_noise((512, 512), 8, seed)
    lines = np.sin(np.linspace(0, 60 * math.pi, 512))[None, :] * 0.5 + 0.5
    t = np.clip(grain * 0.6 + lines * 0.25 + fbm_noise(512, 30, 3, seed + 1) * 0.3, 0, 1)
    return colorize(t, "#3d2c1d" if not burnt else "#141110", "#76593a" if not burnt else "#2d2620")


# ---------------------------------------------------------------- geometry helpers

def _copy_into(mb, src, mat, smooth):
    """Copy every face of bmesh `src` into builder `mb` with one material."""
    idx = mb._mat_index(mat)
    vmap = {}
    for v in src.verts:
        vmap[v] = mb.bm.verts.new(v.co)
    for f in src.faces:
        nf = mb.bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = idx
        nf.smooth = smooth
    src.free()


def convex(mb, points, mat, matrix=None):
    """Convex solid around `points` (flat armour plates): coplanar triangles merged into n-gons."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(matrix @ Vector(p) if matrix else Vector(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.delete(bm, geom=res["geom_interior"] + res["geom_unused"], context="VERTS")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=bm.verts, edges=bm.edges)
    _copy_into(mb, bm, mat, False)


def loft(mb, rings, mat, cap0=True, cap1=True, smooth=True, closed=True):
    """Skin a list of rings (equal point counts) with quads; caps are n-gons."""
    bm = mb.bm
    idx = mb._mat_index(mat)
    vrings = [[bm.verts.new(Vector(p)) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(vrings, vrings[1:]):
        for j in range(n if closed else n - 1):
            j2 = (j + 1) % n
            f = bm.faces.new((a[j], a[j2], b[j2], b[j]))
            f.material_index = idx
            f.smooth = smooth
    for cap, ring, rev in ((cap0, vrings[0], True), (cap1, vrings[-1], False)):
        if cap:
            f = bm.faces.new(list(reversed(ring)) if rev else ring)
            f.material_index = idx
            f.smooth = False
    return vrings


def lathe(mb, profile, matrix, mat, segments=24, smooth=True, cap0=False, cap1=False):
    """Revolve [(r, z), ...] around the local Z axis, then place with `matrix`."""
    rings = []
    for r, z in profile:
        rings.append([matrix @ Vector((r * math.cos(2 * math.pi * s / segments),
                                       r * math.sin(2 * math.pi * s / segments), z))
                      for s in range(segments)])
    loft(mb, rings, mat, cap0, cap1, smooth)


def stamp_box(mb, matrix, size, mat):
    m = matrix @ Matrix.Diagonal((size[0], size[1], size[2], 1))
    mb._stamp(_template("cube"), m, mat, False)


def frame(origin, x_axis, z_axis):
    """4x4 matrix with origin and orthonormal axes (y = z cross x)."""
    x = Vector(x_axis).normalized()
    z = Vector(z_axis)
    z = (z - x * z.dot(x)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


AXIS_Y = Matrix.Rotation(-math.pi / 2, 4, "X")   # local Z -> +Y (wheels turn about Y)


def _superellipse(z, af, ar, b, n=2.5, segs=56, x0=0.0):
    pts = []
    for s in range(segs):
        a = 2 * math.pi * s / segs
        c, si = math.cos(a), math.sin(a)
        ax = af if c >= 0 else ar
        pts.append((x0 + ax * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(si) ** (2 / n), si), z))
    return pts


# ---------------------------------------------------------------- running gear

def track_path():
    """Closed centre-line of one track loop in (x, z), wrapped round sprocket, idler, wheels and
    return rollers, resampled at the link pitch. Returns [(x, z, tx, tz)] with unit tangents."""
    circles = [(SPROCKET[0], SPROCKET[1], SPROCKET[2] + LINK_T / 2),
               (IDLER[0], IDLER[1], IDLER[2] + LINK_T / 2)]
    circles += [(x, WHEEL_Z, WHEEL_R + LINK_T / 2) for x in WHEEL_X]
    circles += [(x, z, r + LINK_T / 2) for x, z, r in ROLLERS]
    pts = []
    for cx, cz, r in circles:
        for k in range(72):
            a = 2 * math.pi * k / 72
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    pts = np.array(pts)
    hull = _hull2d(pts)
    # Sag the upper run between the return rollers.
    out = []
    for x, z in hull:
        if z > 0.85 and SPROCKET[0] < x < IDLER[0]:
            sup = sorted([SPROCKET[0] + 0.1, IDLER[0] - 0.1] + [r[0] for r in ROLLERS])
            for a, b in zip(sup, sup[1:]):
                if a <= x <= b:
                    z -= 0.035 * math.sin(math.pi * (x - a) / (b - a))
        out.append((x, z))
    out.append(out[0])
    seg = np.diff(np.array(out), axis=0)
    lens = np.hypot(seg[:, 0], seg[:, 1])
    total = lens.sum()
    n = int(round(total / LINK_PITCH))
    cum = np.concatenate([[0], np.cumsum(lens)])
    res = []
    for k in range(n):
        s = k * total / n
        i = min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)
        f = (s - cum[i]) / lens[i]
        x = out[i][0] + seg[i][0] * f
        z = out[i][1] + seg[i][1] * f
        t = seg[i] / lens[i]
        res.append((x, z, t[0], t[1]))
    return res


def _hull2d(points):
    pts = sorted(map(tuple, points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]   # counter-clockwise in (x, z)


def track_link(mb, M, m, horn=True):
    """One cast track link in frame m (x along the track, z outward from the loop)."""
    stamp_box(mb, m @ Matrix.Translation((0, 0, 0)), (LINK_PITCH * 0.86, TRACK_W, 0.045), M["track"])
    # Grouser bars on the ground side, two per link.
    for dx in (-0.035, 0.035):
        stamp_box(mb, m @ Matrix.Translation((dx, 0, 0.03)), (0.022, TRACK_W * 0.96, 0.025), M["track"])
    # Hinge knuckles at the joint.
    mb.rod(m @ Vector((LINK_PITCH / 2, -TRACK_W * 0.48, -0.005)), m @ Vector((LINK_PITCH / 2, TRACK_W * 0.48, -0.005)),
           0.022, M["track"], 6, caps=False)
    if horn:   # guide horn between the twin road wheels (on the inside of the loop)
        stamp_box(mb, m @ Matrix.Translation((0, 0, -0.065)), (0.075, 0.05, 0.09), M["track"])


def road_wheel(mb, M, center, side, detail=True):
    """Twin road wheel with rubber tyres, dished cast discs, ribs, hub and bolts."""
    cx, cy, cz = center
    for k, dy in enumerate((-0.15, 0.15)):
        outer = (dy * side) > 0
        m = Matrix.Translation((cx, cy + dy, cz)) @ AXIS_Y
        if side < 0:
            m = m @ Matrix.Rotation(math.pi, 4, "X")   # face outward on the right side too
        segs = 28 if outer else 18
        # Profile from the inner face to the outer face (z = 0 is the wheel's mid-plane).
        lathe(mb, [(0.08, -0.08), (0.33, -0.08), (0.36, -0.09), (0.395, -0.085), (WHEEL_R, -0.06),
                   (WHEEL_R, 0.06), (0.395, 0.085)], m, M["rubber"], segs)
        lathe(mb, [(0.395, 0.085), (0.355, 0.09), (0.34, 0.075), (0.18, 0.03), (0.12, 0.05),
                   (0.12, 0.09), (0.085, 0.11), (0.06, 0.125), (0.0, 0.128)], m, M["mud" if not outer else "paint"],
              segs)
        if outer and detail:
            for r in range(6):   # radial stiffening ribs on the dish
                a = 2 * math.pi * r / 6 + 0.26
                p0 = m @ Vector((0.14 * math.cos(a), 0.14 * math.sin(a), 0.06))
                p1 = m @ Vector((0.32 * math.cos(a), 0.32 * math.sin(a), 0.08))
                mb.beam(p0, p1, 0.025, M["paint"], 0.03)
            for b in range(8):   # hub bolts
                a = 2 * math.pi * b / 8
                mb.rod(m @ Vector((0.1 * math.cos(a), 0.1 * math.sin(a), 0.1)),
                       m @ Vector((0.1 * math.cos(a), 0.1 * math.sin(a), 0.125)), 0.012, M["steel"], 6)


def sprocket(mb, M, side, detail=True):
    x, z, r = SPROCKET
    y = TRACK_Y * side
    teeth = 13
    for dy in (-0.13, 0.13):
        m = Matrix.Translation((x, y + dy, z)) @ AXIS_Y
        ring = []
        for k in range(teeth * 4):
            a = 2 * math.pi * k / (teeth * 4)
            rr = r + (0.07 if k % 4 in (1, 2) else -0.02)
            ring.append((rr * math.cos(a), rr * math.sin(a)))
        rings = [[m @ Vector((px, py, zz)) for px, py in ring] for zz in (-0.035, 0.035)]
        loft(mb, rings, M["track"], smooth=False)
    m = Matrix.Translation((x, y, z)) @ AXIS_Y
    if side < 0:
        m = m @ Matrix.Rotation(math.pi, 4, "X")
    lathe(mb, [(0.0, -0.2), (0.16, -0.2), (0.3, -0.12), (0.3, 0.12), (0.2, 0.17), (0.14, 0.24),
               (0.1, 0.29), (0.0, 0.3)], m, M["paint"], 28)
    if detail:
        for b in range(10):
            a = 2 * math.pi * b / 10
            mb.rod(m @ Vector((0.22 * math.cos(a), 0.22 * math.sin(a), 0.14)),
                   m @ Vector((0.22 * math.cos(a), 0.22 * math.sin(a), 0.17)), 0.016, M["steel"], 6)


def idler(mb, M, side):
    x, z, r = IDLER
    y = TRACK_Y * side
    m = Matrix.Translation((x, y, z)) @ AXIS_Y
    if side < 0:
        m = m @ Matrix.Rotation(math.pi, 4, "X")
    for dy in (-0.15, 0.15):
        mm = Matrix.Translation((x, y + dy, z)) @ AXIS_Y
        lathe(mb, [(0.1, -0.07), (r, -0.07), (r, 0.07), (0.1, 0.07)], mm, M["track"], 24, cap0=False)
    lathe(mb, [(0.0, -0.22), (0.12, -0.22), (0.14, 0.2), (0.08, 0.26), (0.0, 0.27)], m, M["paint"], 20)
    for k in range(6):   # spokes
        a = 2 * math.pi * k / 6
        mb.beam(m @ Vector((0.1 * math.cos(a), 0.1 * math.sin(a), 0.1)),
                m @ Vector((0.3 * math.cos(a), 0.3 * math.sin(a), 0.1)), 0.05, M["paint"], 0.04)
    # Track-tension crank on the hull nose.
    mb.beam((x - 0.05, y - 0.24 * side, z + 0.05), (x + 0.28, (TRACK_Y - 0.3) * side, z + 0.2), 0.08, M["mud"])


# ---------------------------------------------------------------- hull

def finish(mb):
    """Make face normals consistent (lathed and lofted parts are built in either winding)."""
    bmesh.ops.recalc_face_normals(mb.bm, faces=mb.bm.faces)
    return mb


def hull(M, name, burnt=False, rng=None):
    mb = MeshBuilder(name)
    P = M["paint"]
    # -- lower tub between the tracks
    tub = []
    for y in (-1.0, 1.0):
        for x, z in ((-2.98, 0.40), (2.55, 0.40), (GLACIS_A[0], GLACIS_A[1]), (2.733, SPONSON_Z),
                     (-3.02, SPONSON_Z), (-3.06, 0.62)):
            tub.append((x, y, z))
    convex(mb, tub, M["mud"])
    # -- upper hull over the sponsons: sloped sides, glacis, sloped rear plate
    upper = []
    for s in (-1, 1):
        upper += [(2.733, 1.56 * s, SPONSON_Z), (-3.02, 1.56 * s, SPONSON_Z),
                  (GLACIS_B[0], 1.30 * s, DECK_Z), (-2.62, 1.30 * s, DECK_Z),
                  (GLACIS_A[0], 1.0 * s, GLACIS_A[1])]
    convex(mb, upper, P)
    # Plate seams: weld beads along the glacis and side edges.
    for s in (-1, 1):
        for a, b in (((GLACIS_A[0], 1.0 * s, GLACIS_A[1]), (2.733, 1.56 * s, SPONSON_Z)),
                     ((2.733, 1.56 * s, SPONSON_Z), (GLACIS_B[0], 1.30 * s, DECK_Z)),
                     ((GLACIS_B[0], 1.30 * s, DECK_Z), (-2.62, 1.30 * s, DECK_Z)),
                     ((-3.02, 1.56 * s, SPONSON_Z), (-2.62, 1.30 * s, DECK_Z))):
            mb.rod(a, b, 0.018, P, 5, caps=False)
    mb.rod((GLACIS_B[0], -1.30, DECK_Z), (GLACIS_B[0], 1.30, DECK_Z), 0.018, P, 5, caps=False)
    mb.rod((-2.62, -1.30, DECK_Z), (-2.62, 1.30, DECK_Z), 0.018, P, 5, caps=False)

    # -- fenders front and rear (the sponson covers the middle) with a turned-down lip
    for s in (-1, 1):
        y0, y1 = 0.98 * s, 1.60 * s
        yc, yw = (y0 + y1) / 2, abs(y1 - y0)
        for (xa, za), (xb, zb) in ((((2.733, SPONSON_Z + 0.01), (3.36, 0.93))),
                                   (((-3.02, SPONSON_Z + 0.01), (-3.28, 1.0)))):
            mid = ((xa + xb) / 2, yc, (za + zb) / 2)
            ln = math.hypot(xb - xa, zb - za)
            ang = math.degrees(math.atan2(zb - za, xb - xa))
            mb.box(mid, (ln, yw, 0.012), P, rotation=(0, -ang, 0))
        mb.box((0.0, 1.585 * s, SPONSON_Z - 0.03), (6.0, 0.012, 0.07), P)     # side skirt lip
        # Mudflap on the front fender
        mb.box((3.35, yc, 0.86), (0.012, yw, 0.16), M["canvas"])

    # -- running gear
    path = track_path()
    for s in (-1, 1):
        y = TRACK_Y * s
        for k, (x, z, tx, tz) in enumerate(path):
            t = Vector((tx, 0, tz))
            # Outward normal: the path runs counter-clockwise in (x, z), so outward is (tz, -tx).
            n = Vector((tz, 0, -tx))
            m = frame((x, y, z), t, n)
            track_link(mb, M, m, horn=(k % 2 == 0))
        for x in WHEEL_X:
            road_wheel(mb, M, (x, y, WHEEL_Z), s)
            # Trailing suspension arm and bump stop.
            px = x + 0.42
            mb.beam((px, 0.98 * s, 0.70), (x, (TRACK_Y - 0.3) * s, WHEEL_Z), 0.11, M["mud"], 0.09)
            mb.rod((px, 0.98 * s, 0.70), (px, 1.08 * s, 0.70), 0.09, M["mud"], 10)
            mb.box((x - 0.25, 1.04 * s, 0.98), (0.14, 0.1, 0.12), M["mud"])
        for x, z, r in ROLLERS:
            m = Matrix.Translation((x, y, z)) @ AXIS_Y
            lathe(mb, [(0.0, -0.18), (r, -0.18), (r, 0.18), (0.0, 0.18)], m, M["rubber"], 14)
            mb.rod((x, 1.0 * s, z), (x, (y - 0.18 * s), z), 0.04, M["mud"], 8)
        sprocket(mb, M, s)
        idler(mb, M, s)
        # Final drive housing behind the sprocket.
        mb.rod((SPROCKET[0], 0.98 * s, SPROCKET[1]), (SPROCKET[0], (TRACK_Y - 0.34) * s, SPROCKET[1]), 0.24,
               M["mud"], 20)

    # -- glacis furniture
    a = Vector((GLACIS_A[0], 0, GLACIS_A[1]))
    b = Vector((GLACIS_B[0], 0, GLACIS_B[1]))
    g = (b - a).normalized()
    n = Vector((-g.z, 0, g.x))
    if n.x < 0:
        n = -n

    def G(u, y, h=0.0):
        return a + g * u + Vector((0, y, 0)) + n * h

    def Gm(u, y, h=0.0):
        return frame(G(u, y, h), Vector((0, -1, 0)), n)   # x across the plate, z = plate normal

    # Driver's hatch with two periscopes and hinges.
    stamp_box(mb, Gm(1.0, 0.42, 0.04), (0.62, 0.55, 0.08), P)
    stamp_box(mb, Gm(1.0, 0.42, 0.09), (0.56, 0.49, 0.03), P)
    for dy in (0.27, 0.57):
        stamp_box(mb, Gm(1.22, dy, 0.13) , (0.13, 0.08, 0.1), P)
        stamp_box(mb, Gm(1.22, dy, 0.13) @ Matrix.Translation((0, 0.041, 0)), (0.1, 0.004, 0.05), M["glass"])
    for dy in (0.2, 0.64):
        mb.rod(G(0.66, dy, 0.06), G(0.66, dy + 0.08, 0.06), 0.03, P, 8)
    # Hull machine-gun ball mount.
    mb.sphere(G(0.85, -0.5, 0.0), 0.17, M["cast"], 2, (1, 1, 0.75))
    mb.rod(G(0.85, -0.5, 0.05), G(0.85, -0.5, 0.05) + (n * 0.6 + g * -0.25).normalized() * 0.55, 0.025,
           M["dark"], 8)
    mb.torus(tuple(G(0.85, -0.5, 0.08)), 0.18, 0.025, M["cast"], 20, 5)
    # Spare track links bolted across the lower glacis.
    for yy in (-0.95, -0.62, 0.62, 0.95):
        track_link(mb, M, frame(G(0.22, yy, 0.05), g, n) @ Matrix.Rotation(math.pi / 2, 4, "Z") @
                   Matrix.Scale(0.95, 4), horn=False)
    # Headlights on the fenders: housing, lens, blackout hood.
    for s in (-1, 1):
        base = Vector((2.95, 1.25 * s, 1.05))
        mb.rod(base, base + Vector((0, 0, 0.12)), 0.025, M["steel"], 6)
        hp = base + Vector((0, 0, 0.2))
        mb.rod(hp + Vector((-0.12, 0, 0)), hp + Vector((0.06, 0, 0)), 0.095, P, 16)
        mb.rod(hp + Vector((0.06, 0, 0)), hp + Vector((0.075, 0, 0)), 0.08, M["lens"], 16)
        mb.box(hp + Vector((0.02, 0, 0.1)), (0.2, 0.2, 0.02), P)
        # Red convoy marker lamps on the front fender edge (lit in the reference).
        mb.box((3.2, 1.45 * s, 0.98), (0.04, 0.06, 0.05), M["red"])
    # Tow hooks on the nose.
    for s in (-1, 1):
        hp = Vector((3.02, 0.72 * s, 0.62))
        mb.torus(tuple(hp), 0.09, 0.03, M["steel"], 14, 5)
        mb.box(hp + Vector((-0.08, 0, 0)), (0.12, 0.06, 0.16), M["mud"])

    # -- deck: turret ring, hatches, engine louvres
    mb.cylinder((TURRET_X, 0, DECK_Z), 1.0, 0.05, P, 48)
    # Engine access hatch with bolt ring.
    mb.box((-1.55, 0, DECK_Z + 0.03), (1.05, 0.95, 0.06), P)
    for k in range(18):
        a = 2 * math.pi * k / 18
        mb.rod((-1.55 + 0.47 * math.cos(a) * 1.05, 0.42 * math.sin(a), DECK_Z + 0.06),
               (-1.55 + 0.47 * math.cos(a) * 1.05, 0.42 * math.sin(a), DECK_Z + 0.08), 0.015, P, 6)
    # Louvred air intakes either side.
    for s in (-1, 1):
        mb.box((-1.55, 0.85 * s, DECK_Z + 0.015), (1.4, 0.48, 0.03), M["dark"])
        for k in range(11):
            x = -2.2 + k * 0.13
            mb.box((x, 0.85 * s, DECK_Z + 0.05), (0.03, 0.46, 0.06), P, rotation=(0, 30, 0))
        mb.box((-1.55, 0.85 * s + 0.25 * s, DECK_Z + 0.05), (1.42, 0.03, 0.08), P)
        mb.box((-1.55, 0.85 * s - 0.25 * s, DECK_Z + 0.05), (1.42, 0.03, 0.08), P)
    # Rear plate: radiator grille, exhausts, tail lights, tow pintle.
    rear_a = Vector((-3.02, 0, SPONSON_Z))
    rear_b = Vector((-2.62, 0, DECK_Z))
    rg = (rear_b - rear_a).normalized()
    rn = Vector((rg.z, 0, -rg.x))
    if rn.x > 0:
        rn = -rn

    def R(u, y, h=0.0):
        return rear_a + rg * u + Vector((0, y, 0)) + rn * h
    for k in range(9):
        u = 0.12 + k * 0.06
        stamp_box(mb, frame(R(u, 0, 0.02), Vector((0, 1, 0)), rn), (1.6, 0.025, 0.04), P)
    for s in (-1, 1):
        ex = Vector((-3.0, 0.55 * s, 0.78))
        mb.rod(ex + Vector((0.2, 0, 0)), ex + Vector((-0.22, 0, -0.08)), 0.085, M["soot"], 14)
        mb.rod(ex + Vector((-0.22, 0, -0.08)), ex + Vector((-0.25, 0, -0.085)), 0.075, M["dark"], 14)
        mb.box((-3.065, 1.2 * s, 0.98), (0.05, 0.08, 0.06), M["red"])
    mb.box((-3.1, 0, 0.55), (0.14, 0.2, 0.18), M["mud"])
    mb.torus((-3.18, 0, 0.55), 0.07, 0.025, M["steel"], 12, 5)
    # External fuel drums on brackets at the rear.
    for s in (-1, 1):
        c = Vector((-3.32, 0.68 * s, 1.18))
        mb.rod(c + Vector((0, -0.42, 0)), c + Vector((0, 0.42, 0)), 0.29, P, 24)
        for dy in (-0.25, 0.25):
            mb.rod(c + Vector((0, dy - 0.012, 0)), c + Vector((0, dy + 0.012, 0)), 0.3, P, 24)
        mb.beam(c + Vector((0.28, 0, -0.25)), c + Vector((0.0, 0, -0.32)), 0.06, M["steel"])
    # Unditching log across the rear deck with chains.
    mb.rod((-2.45, -1.35, DECK_Z + 0.16), (-2.45, 1.35, DECK_Z + 0.16), 0.15, M["wood"], 14)
    for dy in (-0.9, 0.9):
        mb.torus((-2.45, dy, DECK_Z + 0.16), 0.17, 0.012, M["steel"], 16, 4)

    # -- stowage on the sponsons: fuel cells (right), toolbox and tools (left), tow cable
    for k, x in enumerate((-1.95, -1.15, -0.35)):
        c = Vector((x, -1.4, SPONSON_Z + 0.42))
        mb.rod(c + Vector((-0.34, 0, 0)), c + Vector((0.34, 0, 0)), 0.17, P, 20)
        mb.sphere(c + Vector((0.34, 0, 0)), 0.17, P, 2, (0.25, 1, 1))
        mb.sphere(c + Vector((-0.34, 0, 0)), 0.17, P, 2, (0.25, 1, 1))
        for dx in (-0.2, 0.2):   # straps
            mb.rod(c + Vector((dx - 0.02, 0, 0)), c + Vector((dx + 0.02, 0, 0)), 0.178, M["dark"], 20)
        mb.box((x, -1.4, SPONSON_Z + 0.17), (0.6, 0.3, 0.06), M["steel"])
    mb.box((-1.6, 1.38, SPONSON_Z + 0.2), (0.95, 0.32, 0.3), P)          # toolbox
    mb.box((-1.6, 1.38, SPONSON_Z + 0.36), (0.97, 0.34, 0.03), P)
    for dx in (-0.3, 0.3):
        mb.box((-1.6 + dx, 1.54, SPONSON_Z + 0.25), (0.06, 0.02, 0.04), M["steel"])
    # Shovel and pry bar on the left sponson slope.
    mb.rod((0.0, 1.43, SPONSON_Z + 0.12), (1.1, 1.43, SPONSON_Z + 0.12), 0.02, M["wood"], 6)
    mb.box((1.25, 1.43, SPONSON_Z + 0.12), (0.3, 0.2, 0.015), M["steel"], rotation=(80, 0, 0))
    mb.rod((-0.1, 1.48, SPONSON_Z + 0.06), (1.6, 1.48, SPONSON_Z + 0.06), 0.018, M["steel"], 6)
    # Tow cable looped along the left upper hull side.
    side_pts = [(2.1, 1.38, 1.45), (0.4, 1.38, 1.45), (-1.0, 1.4, 1.42), (-2.3, 1.42, 1.38),
                (-2.5, 1.42, 1.3), (-2.3, 1.43, 1.25), (-0.8, 1.45, 1.27), (0.7, 1.45, 1.3), (2.0, 1.44, 1.32)]
    mb.tube(side_pts, 0.022, M["steel"], bend_radius=0.07, segments=8, arc_steps=4)
    for p in (side_pts[0], side_pts[-1]):
        mb.torus(p, 0.06, 0.018, M["steel"], 10, 4)
    # Grab handles along the upper hull sides.
    for s in (-1, 1):
        for x in (1.2, 0.0, -1.2):
            y = 1.32 * s
            mb.pipe([(x - 0.18, y, DECK_Z - 0.05), (x - 0.18, y + 0.06 * s, DECK_Z - 0.02),
                     (x + 0.18, y + 0.06 * s, DECK_Z - 0.02), (x + 0.18, y, DECK_Z - 0.05)], 0.012, M["steel"], 6)

    # -- snow dusting in the corners where it lodges (not on the burnt-out wreck: the fire melted it)
    if not burnt and rng is not None:
        for s in (-1, 1):
            for x0, x1 in ((-2.9, -2.1), (-0.2, 0.9), (1.4, 2.5)):     # along the sponson/hull angle
                x = rng.uniform(x0, x1)
                mb.sphere((x, 1.5 * s, SPONSON_Z + 0.01), 1.0, M["snow"], 2,
                          (rng.uniform(0.25, 0.45), 0.07, 0.025))
            mb.sphere((3.05, 1.3 * s, 0.975), 1.0, M["snow"], 2, (0.2, 0.2, 0.02))   # front fender
            mb.sphere((-3.15, 1.3 * s, 1.0), 1.0, M["snow"], 2, (0.12, 0.2, 0.015))   # rear fender
        for x, y in ((-2.0, 0.85), (-1.1, -0.85), (-2.55, 0.3)):                    # deck corners
            mb.sphere((x, y, DECK_Z + 0.04), 1.0, M["snow"], 2, (0.22, 0.14, 0.02))
    return finish(mb)


# ---------------------------------------------------------------- turret

def turret(M, name, burnt=False, rng=None, hatch_open=False):
    mb = MeshBuilder(name)
    C, P = M["cast"], M["paint"]
    rings = [
        _superellipse(0.0, 1.06, 1.12, 1.04, 2.6),
        _superellipse(0.12, 1.20, 1.36, 1.15, 2.6),
        _superellipse(0.30, 1.22, 1.44, 1.16, 2.5),
        _superellipse(0.48, 1.14, 1.40, 1.10, 2.4),
        _superellipse(0.64, 0.98, 1.30, 0.98, 2.3),
        _superellipse(0.75, 0.80, 1.17, 0.84, 2.2),
        _superellipse(0.80, 0.62, 1.04, 0.72, 2.2),
    ]
    loft(mb, rings, C, cap0=True, cap1=True)
    top = 0.80
    # Casting parting line around the waist.
    mb.tube([p for p in _superellipse(0.30, 1.235, 1.455, 1.175, 2.5, 56)] + [_superellipse(0.30, 1.235, 1.455, 1.175, 2.5, 56)[0]],
            0.012, C, segments=5, arc_steps=1, caps=False)

    # Mantlet: a rounded shield across the turret front, with the gun sleeve.
    mx = 1.1
    lathe(mb, [(0.0, -0.62), (0.26, -0.62), (0.31, -0.55), (0.31, 0.55), (0.26, 0.62), (0.0, 0.62)],
          Matrix.Translation((mx, 0, GUN_Z)) @ AXIS_Y, C, 28)
    mb.box((mx + 0.12, 0, GUN_Z), (0.25, 1.05, 0.5), C)
    mb.rod((mx + 0.25, 0, GUN_Z), (mx + 0.7, 0, GUN_Z), 0.15, C, 24, radius_b=0.125)
    # Barrel: tapering tube, a reinforcing collar, muzzle swell and a dark bore.
    L = 5.6
    mb.rod((mx + 0.7, 0, GUN_Z), (L - 0.3, 0, GUN_Z), 0.078, P, 20, radius_b=0.062, caps=False)
    mb.rod((mx + 1.9, 0, GUN_Z), (mx + 2.0, 0, GUN_Z), 0.085, P, 20)
    lathe(mb, [(0.062, 0.0), (0.085, 0.06), (0.088, 0.26), (0.08, 0.3), (0.045, 0.3), (0.045, 0.28)],
          Matrix.Translation((L - 0.3, 0, GUN_Z)) @ Matrix.Rotation(math.pi / 2, 4, "Y"), P, 20)
    mb.rod((L - 0.02, 0, GUN_Z), (L - 0.05, 0, GUN_Z), 0.046, M["dark"], 16)
    # Coaxial MG port and the gunner's sight aperture.
    mb.rod((mx + 0.25, 0.3, GUN_Z + 0.02), (mx + 0.42, 0.3, GUN_Z + 0.02), 0.03, M["dark"], 8)
    mb.rod((mx + 0.22, -0.3, GUN_Z + 0.08), (mx + 0.3, -0.3, GUN_Z + 0.08), 0.04, M["glass"], 10)

    # Commander's cupola with vision blocks and a domed hatch.
    cx, cy = -0.35, 0.42
    m = Matrix.Translation((cx, cy, top - 0.03))
    lathe(mb, [(0.0, 0.0), (0.38, 0.0), (0.38, 0.06), (0.35, 0.08), (0.35, 0.24), (0.37, 0.26),
               (0.37, 0.3), (0.0, 0.3)], m, C, 32)
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.3
        mm = frame((cx + 0.355 * math.cos(a), cy + 0.355 * math.sin(a), top + 0.13),
                   Vector((-math.sin(a), math.cos(a), 0)), Vector((math.cos(a), math.sin(a), 0)))
        stamp_box(mb, mm, (0.13, 0.05, 0.035), M["glass"])
    hatch_m = Matrix.Translation((cx, cy, top + 0.27))
    if hatch_open:   # burnt wreck: hatch flung open and standing up
        hatch_m = (Matrix.Translation((cx - 0.33, cy, top + 0.3)) @ Matrix.Rotation(math.radians(-100), 4, "Y")
                   @ Matrix.Translation((0.33, 0, 0)))
    lathe(mb, [(0.0, 0.0), (0.33, 0.0), (0.33, 0.04), (0.25, 0.09), (0.0, 0.11)], hatch_m, C, 28,
          cap0=True)
    mb.pipe([hatch_m @ Vector(p) for p in ((-0.12, 0, 0.1), (-0.12, 0, 0.15), (0.12, 0, 0.15), (0.12, 0, 0.1))],
            0.012, M["steel"], 6)
    # Loader's hatch, periscopes, ventilator, lifting eyes, antenna.
    lh = Vector((-0.15, -0.42, top))
    if hatch_open:
        mb.cylinder((lh.x, lh.y, top), 0.3, 0.02, M["dark"], 24)
        mb.box((lh.x - 0.05, lh.y - 0.33, top + 0.3), (0.55, 0.05, 0.6), C)
    else:
        mb.cylinder((lh.x, lh.y, top - 0.01), 0.3, 0.05, C, 28)
        mb.pipe([(lh.x - 0.1, lh.y, top + 0.04), (lh.x - 0.1, lh.y, top + 0.09), (lh.x + 0.1, lh.y, top + 0.09),
                 (lh.x + 0.1, lh.y, top + 0.04)], 0.012, M["steel"], 6)
    for x, y in ((0.25, 0.35), (0.25, -0.35), (-0.6, -0.65)):
        mb.box((x, y, top + 0.06), (0.16, 0.12, 0.13), C)
        mb.box((x + 0.081, y, top + 0.08), (0.004, 0.09, 0.05), M["glass"])
        mb.box((x, y, top + 0.135), (0.2, 0.15, 0.025), C)
    mb.cylinder((0.45, 0.0, top), 0.13, 0.06, C, 16)
    mb.dome((0.45, 0.0, top + 0.06), 0.17, 0.08, C, 16, 3)
    for x, y in ((0.6, 0.62), (0.6, -0.62), (-0.85, 0.6), (-0.85, -0.6)):
        mb.torus((x, y, top + 0.04), 0.05, 0.015, M["steel"], 10, 4)
    mb.cylinder((-0.95, -0.25, top - 0.02), 0.05, 0.1, M["steel"], 10)
    if not burnt:
        mb.rod((-0.95, -0.25, top + 0.06), (-1.15, -0.25, top + 2.6), 0.007, M["dark"], 4, radius_b=0.003)
    # Grab rails around the turret sides.
    for s in (-1, 1):
        pts = [(0.75, 1.02 * s, 0.53), (0.75, 1.1 * s, 0.53), (-0.9, 1.25 * s, 0.53), (-0.9, 1.17 * s, 0.53)]
        mb.pipe(pts, 0.016, M["steel"], 6)
    # Rear stowage bin on the bustle.
    mb.box((-1.55, 0, 0.42), (0.36, 1.5, 0.42), P)
    mb.box((-1.55, 0, 0.645), (0.39, 1.53, 0.03), P)
    for dy in (-0.5, 0.5):
        mb.beam((-1.4, dy, 0.25), (-1.3, dy, 0.25), 0.05, M["steel"])
    if not burnt:
        mb.box((-1.55, 0.0, 0.67), (0.34, 1.4, 0.05), M["canvas"])    # rolled tarp on the bin
        mb.rod((-1.48, -0.7, 0.75), (-1.48, 0.7, 0.75), 0.11, M["canvas"], 14)
        if rng is not None:   # snow lodged against the cupola and bin
            mb.sphere((-0.35, 0.0, top + 0.005), 1.0, M["snow"], 2, (0.25, 0.12, 0.015))
            mb.sphere((-1.1, 0.3, top - 0.03), 1.0, M["snow"], 2, (0.12, 0.3, 0.02))
    return finish(mb)


def gun_muzzle(turret_matrix):
    """World position and direction of the muzzle for a turret object's matrix_world."""
    return turret_matrix @ Vector((5.6, 0, GUN_Z)), (turret_matrix.to_3x3() @ Vector((1, 0, 0))).normalized()
