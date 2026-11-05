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

TRACK_Y = 1.31          # track centre line, either side
TRACK_W = 0.56
LINK_PITCH = 0.16
LINK_T = 0.08           # link thickness (to the guide-horn base)
WHEEL_R = 0.36
WHEEL_X = (-2.35, -1.41, -0.47, 0.47, 1.41, 2.35)
WHEEL_Z = WHEEL_R + LINK_T
SPROCKET = (-3.12, 0.60, 0.34)   # rear drive sprocket: x, z, pitch radius
IDLER = (3.16, 0.56, 0.32)
ROLLERS = ((-1.88, 0.80, 0.09), (0.0, 0.82, 0.09), (1.88, 0.80, 0.09))
DECK_Z = 1.50
SPONSON_Z = 1.02
TURRET_X = 0.35
GUN_Z = 0.38            # gun axis above the turret ring
GLACIS_A = (3.50, 0.70)  # glacis bottom (x, z) and top: long and shallow
GLACIS_B = (2.20, DECK_Z)
GUN_LEN = 6.4           # muzzle ahead of the turret ring
REAR_X = -3.40


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
        paint_img = texture("tank_paint", _paint_pixels("#2f3b33", "#161b18", 11))
        cast_img = texture("tank_cast", _paint_pixels("#2e3a32", "#161b18", 12))
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
    for dy in (-0.16, 0.16):
        outer = (dy * side) > 0
        m = Matrix.Translation((cx, cy + dy, cz)) @ AXIS_Y
        if side < 0:
            m = m @ Matrix.Rotation(math.pi, 4, "X")   # face outward on the right side too
        k = WHEEL_R / 0.40
        m = m @ Matrix.Diagonal((k, k, 1, 1))           # profile below is drawn for a 0.40 m wheel
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




def chamfer_box(mb, center, size, mat, ch=0.04, matrix=None):
    """Box with every edge chamfered by `ch`: the softened-square look of welded armour."""
    hx, hy, hz = (s / 2 for s in size)
    c = min(ch, hx * 0.45, hy * 0.45, hz * 0.45)
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                for dx, dy, dz in ((0, c, c), (c, 0, c), (c, c, 0)):
                    pts.append((center[0] + sx * (hx - dx), center[1] + sy * (hy - dy), center[2] + sz * (hz - dz)))
    convex(mb, pts, mat, matrix)


def mirrored(levels):
    """[(z, [(x, y), ...]), ...] -> 3D points mirrored across y = 0."""
    return [(x, sy * y, z) for z, ring in levels for x, y in ring for sy in (-1, 1)]


def hull(M, name, burnt=False, rng=None):
    mb = MeshBuilder(name)
    P = M["paint"]
    S = M["steel"]
    # -- lower tub between the tracks
    tub = []
    for y in (-1.02, 1.02):
        for x, z in ((REAR_X + 0.1, 0.42), (3.0, 0.40), (GLACIS_A[0], GLACIS_A[1]), (2.98, SPONSON_Z),
                     (REAR_X, SPONSON_Z), (REAR_X - 0.02, 0.62)):
            tub.append((x, y, z))
    convex(mb, tub, M["mud"])
    # -- upper hull: long shallow glacis, low flat deck, gently sloped sides with chamfered edges
    upper = mirrored([
        (SPONSON_Z, [(REAR_X, 1.70), (2.98, 1.70)]),
        (DECK_Z - 0.06, [(REAR_X + 0.10, 1.60), (2.29, 1.60)]),
        (DECK_Z, [(REAR_X + 0.16, 1.53), (GLACIS_B[0], 1.53)]),
        (GLACIS_A[1], [(GLACIS_A[0], 1.02)]),
    ])
    convex(mb, upper, P)
    # Weld beads along the plate joints.
    for s in (-1, 1):
        mb.rod((2.98, 1.70 * s, SPONSON_Z), (2.29, 1.60 * s, DECK_Z - 0.06), 0.014, P, 5, caps=False)
        mb.rod((REAR_X, 1.70 * s, SPONSON_Z + 0.005), (2.98, 1.70 * s, SPONSON_Z + 0.005), 0.014, P, 5, caps=False)
    mb.rod((GLACIS_B[0], -1.5, DECK_Z), (GLACIS_B[0], 1.5, DECK_Z), 0.016, P, 5, caps=False)

    # -- fenders front and rear, with mudguards
    for s in (-1, 1):
        yc, yw = 1.37 * s, 0.70
        for (xa, za), (xb, zb) in (((2.98, SPONSON_Z + 0.008), (3.66, 0.84)),
                                   ((REAR_X, SPONSON_Z + 0.008), (-3.66, 0.98))):
            mid = ((xa + xb) / 2, yc, (za + zb) / 2)
            ln = math.hypot(xb - xa, zb - za)
            ang = math.degrees(math.atan2(zb - za, xb - xa))
            mb.box(mid, (ln, yw, 0.014), P, rotation=(0, -ang, 0))
        mb.box((3.65, yc, 0.76), (0.014, yw, 0.16), M["canvas"])
        mb.box((-3.65, yc, 0.9), (0.014, yw, 0.16), M["canvas"])

    # -- armoured side skirts: five bolted panels hiding the upper run of the track
    for s in (-1, 1):
        y = 1.735 * s
        x0, w = -3.10, 6.05 / 5
        for k in range(5):
            xa = x0 + k * w + 0.015
            xb = xa + w - 0.03
            bottom = 0.66 if 0 < k < 4 else 0.72
            chamfer_box(mb, ((xa + xb) / 2, y, (bottom + 1.0) / 2), (xb - xa, 0.03, 1.0 - bottom), P, 0.012)
            for b in range(5):   # bolt row along the top edge
                bx = xa + 0.1 + b * (xb - xa - 0.2) / 4
                mb.rod((bx, y, 0.95), (bx, y + 0.025 * s, 0.95), 0.018, P, 6)
        mb.box((-0.05, 1.71 * s, 1.005), (6.1, 0.06, 0.03), P)   # skirt hanger rail

    # -- running gear
    path = track_path()
    for s in (-1, 1):
        y = TRACK_Y * s
        for k, (x, z, tx, tz) in enumerate(path):
            t = Vector((tx, 0, tz))
            n = Vector((tz, 0, -tx))   # path is counter-clockwise in (x, z): outward is (tz, -tx)
            track_link(mb, M, frame((x, y, z), t, n), horn=(k % 2 == 0))
        for x in WHEEL_X:
            road_wheel(mb, M, (x, y, WHEEL_Z), s)
            px = x + 0.38
            mb.beam((px, 0.98 * s, 0.64), (x, (TRACK_Y - 0.32) * s, WHEEL_Z), 0.1, M["mud"], 0.08)
            mb.rod((px, 0.98 * s, 0.64), (px, 1.06 * s, 0.64), 0.08, M["mud"], 10)
        for x, z, r in ROLLERS:
            m = Matrix.Translation((x, y, z)) @ AXIS_Y
            lathe(mb, [(0.0, -0.2), (r, -0.2), (r, 0.2), (0.0, 0.2)], m, M["rubber"], 14)
            mb.rod((x, 1.0 * s, z), (x, (y - 0.2 * s), z), 0.035, M["mud"], 8)
        sprocket(mb, M, s)
        idler(mb, M, s)
        mb.rod((SPROCKET[0], 0.98 * s, SPROCKET[1]), (SPROCKET[0], (TRACK_Y - 0.36) * s, SPROCKET[1]), 0.22,
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

    glen = (b - a).length
    # Splash board: a low V-shaped ridge that throws water and snow off the glacis.
    for s in (-1, 1):
        p0, p1 = G(glen * 0.62, 0.0, 0.05), G(glen * 0.45, 1.45 * s, 0.05)
        mb.beam(p0, p1, 0.04, P, 0.1)
    # Spare track links bolted across the lower glacis.
    for yy in (-1.2, -0.75, -0.3, 0.3, 0.75, 1.2):
        track_link(mb, M, frame(G(0.3, yy, 0.05), g, n) @ Matrix.Rotation(math.pi / 2, 4, "Z"), horn=False)
    # Headlights in boxy guards at the glacis corners, and red convoy lamps.
    for s in (-1, 1):
        hp = G(glen * 0.8, 1.3 * s, 0.12)
        chamfer_box(mb, tuple(hp), (0.2, 0.22, 0.16), P, 0.03)
        mb.rod(hp + Vector((0.09, 0, 0)), hp + Vector((0.115, 0, 0)), 0.07, M["lens"], 14)
        mb.pipe([hp + Vector((0.02, -0.14, 0.1)), hp + Vector((0.18, -0.14, 0.1)), hp + Vector((0.18, 0.14, 0.1)),
                 hp + Vector((0.02, 0.14, 0.1))], 0.012, S, 6)
        mb.box((3.58, 1.62 * s, 0.86), (0.04, 0.06, 0.05), M["red"])
        tp = Vector((3.42, 0.7 * s, 0.6))   # tow hooks
        mb.torus(tuple(tp), 0.09, 0.03, S, 14, 5)
        chamfer_box(mb, tuple(tp + Vector((-0.08, 0, 0))), (0.14, 0.08, 0.18), M["mud"], 0.02)
    # Driver's hatch on the front deck, with three periscopes.
    chamfer_box(mb, (1.85, 0.0, DECK_Z + 0.03), (0.55, 0.62, 0.06), P, 0.02)
    for dy in (-0.2, 0.0, 0.2):
        chamfer_box(mb, (2.08, dy, DECK_Z + 0.07), (0.1, 0.14, 0.1), P, 0.015)
        mb.box((2.131, dy, DECK_Z + 0.08), (0.004, 0.1, 0.04), M["glass"])
    mb.rod((1.62, -0.25, DECK_Z + 0.07), (1.62, 0.25, DECK_Z + 0.07), 0.03, S, 8)

    # -- deck: turret ring collar, engine deck with grilles, hatches
    mb.cylinder((TURRET_X, 0, DECK_Z), 1.08, 0.05, P, 48)
    chamfer_box(mb, (-2.05, 0, DECK_Z + 0.05), (2.3, 2.5, 0.1), P, 0.03)       # raised engine deck
    for s in (-1, 1):
        # Air intake grille: a dark well under a row of slats.
        mb.box((-2.15, 0.78 * s, DECK_Z + 0.09), (1.7, 0.72, 0.03), M["dark"])
        for k in range(14):
            mb.box((-2.95 + k * 0.122, 0.78 * s, DECK_Z + 0.115), (0.03, 0.7, 0.04), P)
        mb.box((-2.15, (0.78 + 0.37) * s, DECK_Z + 0.12), (1.72, 0.03, 0.05), P)
        mb.box((-2.15, (0.78 - 0.37) * s, DECK_Z + 0.12), (1.72, 0.03, 0.05), P)
    chamfer_box(mb, (-1.05, 0.0, DECK_Z + 0.11), (0.55, 0.7, 0.04), P, 0.015)    # engine access hatch
    for dy in (-0.2, 0.2):
        mb.pipe([(-1.15, dy, DECK_Z + 0.13), (-1.15, dy, DECK_Z + 0.18), (-0.95, dy, DECK_Z + 0.18),
                 (-0.95, dy, DECK_Z + 0.13)], 0.012, S, 6)
    # Rear plate: boxed exhaust silencers with slotted guards, tail lights, towing pintle.
    for s in (-1, 1):
        c = Vector((-3.52, 1.05 * s, 1.18))
        chamfer_box(mb, tuple(c), (0.28, 0.6, 0.32), M["soot"], 0.04)
        for k in range(4):
            mb.box(tuple(c + Vector((-0.15, -0.22 + k * 0.145, 0))), (0.02, 0.03, 0.34), P)
        mb.rod(c + Vector((0, 0.3 * s, -0.05)), c + Vector((0, 0.42 * s, -0.12)), 0.05, M["dark"], 10)
        chamfer_box(mb, (-3.43, 1.45 * s, 0.98), (0.08, 0.14, 0.1), P, 0.015)
        mb.box((-3.475, 1.45 * s, 0.98), (0.01, 0.08, 0.05), M["red"])
    chamfer_box(mb, (-3.5, 0, 0.62), (0.2, 0.28, 0.2), M["mud"], 0.03)
    mb.torus((-3.62, 0, 0.62), 0.07, 0.025, S, 12, 5)
    # Unditching log on the rear deck with chains, and two external fuel drums behind it.
    mb.rod((-3.1, -1.4, DECK_Z + 0.27), (-3.1, 1.4, DECK_Z + 0.27), 0.15, M["wood"], 14)
    for dy in (-0.95, 0.95):
        mb.torus((-3.1, dy, DECK_Z + 0.27), 0.17, 0.012, S, 16, 4)
    # Stowage boxes on the sponson edges, tow cable along the hull side.
    for s in (-1, 1):
        for x in (-0.7, 0.5):
            chamfer_box(mb, (x, 1.42 * s, DECK_Z + 0.12), (0.95, 0.26, 0.24), P, 0.025)
            mb.box((x, (1.42 + 0.131) * s, DECK_Z + 0.16), (0.1, 0.01, 0.05), S)
    side_pts = [(2.2, 1.66, 1.22), (0.4, 1.66, 1.24), (-1.5, 1.66, 1.24), (-3.0, 1.66, 1.2), (-3.2, 1.66, 1.12),
                (-3.0, 1.67, 1.08), (-1.2, 1.67, 1.1), (0.8, 1.67, 1.1), (2.1, 1.67, 1.1)]
    mb.tube(side_pts, 0.022, S, bend_radius=0.06, segments=8, arc_steps=4)
    for p in (side_pts[0], side_pts[-1]):
        mb.torus(p, 0.06, 0.018, S, 10, 4)

    # -- snow dusting where it lodges (not on the burnt-out wreck: the fire melted it)
    if not burnt and rng is not None:
        for s in (-1, 1):
            for x0, x1 in ((-2.9, -2.1), (-0.4, 0.8), (1.3, 2.4)):
                mb.sphere((rng.uniform(x0, x1), 1.66 * s, SPONSON_Z + 0.005), 1.0, M["snow"], 2,
                          (rng.uniform(0.3, 0.5), 0.05, 0.02))
            mb.sphere((-1.5, 1.2 * s, DECK_Z + 0.105), 1.0, M["snow"], 2, (0.6, 0.06, 0.012))
    return finish(mb)


# ---------------------------------------------------------------- turret

TURRET_PLAN = [   # (z, [(x, y), ...]) half-plan, mirrored across y: a low angular welded turret
    (0.00, [(1.30, 0.45), (0.85, 1.08), (-0.95, 1.12), (-1.55, 0.90)]),
    (0.10, [(1.55, 0.50), (0.95, 1.24), (-1.00, 1.28), (-1.72, 1.00)]),
    (0.56, [(1.32, 0.46), (0.82, 1.12), (-0.98, 1.17), (-1.70, 0.95)]),
    (0.66, [(1.14, 0.41), (0.73, 1.00), (-0.95, 1.05), (-1.63, 0.86)]),
    (0.70, [(1.02, 0.36), (0.66, 0.92), (-0.90, 0.97), (-1.56, 0.79)]),
]
ROOF = 0.70


def turret(M, name, burnt=False, rng=None, hatch_open=False):
    mb = MeshBuilder(name)
    P, S, D = M["paint"], M["steel"], M["dark"]
    convex(mb, mirrored(TURRET_PLAN), M["cast"])
    # Weld seam where the side plates meet the roof.
    ring = [(x, y, ROOF - 0.04) for x, y in TURRET_PLAN[3][1]]
    for s in (-1, 1):
        pts = [(x, s * y, z) for x, y, z in ring]
        mb.pipe(pts, 0.012, P, 5, elbows=False)

    # Mantlet: a chamfered armour block carrying the gun, coax MG and sight aperture.
    chamfer_box(mb, (1.68, 0, GUN_Z), (0.38, 0.8, 0.5), M["cast"], 0.06)
    mb.rod((1.86, 0, GUN_Z), (2.35, 0, GUN_Z), 0.15, P, 10, radius_b=0.12)   # faceted gun sleeve
    mb.rod((1.86, 0.28, GUN_Z + 0.03), (1.95, 0.28, GUN_Z + 0.03), 0.03, D, 8)
    mb.box((1.875, -0.27, GUN_Z + 0.12), (0.02, 0.14, 0.08), M["glass"])
    # Long barrel: taper, thermal-sleeve straps, fume extractor, slotted box muzzle brake.
    L = GUN_LEN
    mb.rod((2.35, 0, GUN_Z), (L - 0.45, 0, GUN_Z), 0.078, P, 20, radius_b=0.064, caps=False)
    for x in (2.9, 4.6, 5.3):
        mb.rod((x, 0, GUN_Z), (x + 0.04, 0, GUN_Z), 0.083 - (x - 2.35) * 0.004, P, 20)
    lathe(mb, [(0.074, 0.0), (0.11, 0.08), (0.112, 0.6), (0.075, 0.7)],
          Matrix.Translation((3.5, 0, GUN_Z)) @ Matrix.Rotation(math.pi / 2, 4, "Y"), P, 20)
    chamfer_box(mb, (L - 0.22, 0, GUN_Z), (0.44, 0.22, 0.17), P, 0.03)
    for dx in (-0.1, 0.08):
        for s in (-1, 1):
            mb.box((L - 0.22 + dx, 0.111 * s, GUN_Z), (0.08, 0.004, 0.11), D)
    mb.rod((L + 0.001, 0, GUN_Z), (L - 0.03, 0, GUN_Z), 0.05, D, 16)

    # Commander's cupola: a low octagonal drum with periscopes and a roof MG.
    cx, cy = -0.5, 0.5
    lathe(mb, [(0.0, 0.0), (0.38, 0.0), (0.38, 0.17), (0.34, 0.2), (0.0, 0.2)],
          Matrix.Translation((cx, cy, ROOF - 0.01)) @ Matrix.Rotation(math.pi / 8, 4, "Z"), M["cast"], 8, smooth=False)
    for k in range(8):
        a = 2 * math.pi * k / 8
        mm = frame((cx + 0.355 * math.cos(a), cy + 0.355 * math.sin(a), ROOF + 0.1),
                   Vector((-math.sin(a), math.cos(a), 0)), Vector((math.cos(a), math.sin(a), 0)))
        stamp_box(mb, mm, (0.12, 0.05, 0.035), M["glass"])
    if hatch_open:
        mb.box((cx - 0.35, cy, ROOF + 0.48), (0.04, 0.5, 0.5), P)
        mb.cylinder((cx, cy, ROOF + 0.19), 0.28, 0.02, D, 16)
    else:
        lathe(mb, [(0.0, 0.0), (0.3, 0.0), (0.28, 0.05), (0.0, 0.06)],
              Matrix.Translation((cx, cy, ROOF + 0.19)), P, 8, smooth=False, cap0=True)
        # Roof machine gun on a pintle.
        mb.rod((cx + 0.2, cy - 0.22, ROOF + 0.2), (cx + 0.2, cy - 0.22, ROOF + 0.42), 0.025, S, 6)
        chamfer_box(mb, (cx + 0.3, cy - 0.22, ROOF + 0.46), (0.36, 0.08, 0.1), D, 0.015)
        mb.rod((cx + 0.48, cy - 0.22, ROOF + 0.47), (cx + 1.25, cy - 0.22, ROOF + 0.47), 0.018, D, 6)
        chamfer_box(mb, (cx + 0.3, cy - 0.12, ROOF + 0.4), (0.18, 0.1, 0.14), P, 0.01)
    # Loader's hatch, gunner's sight box, ventilator, lifting eyes.
    lx, ly = -0.35, -0.5
    if hatch_open:
        mb.box((lx, ly, ROOF + 0.01), (0.55, 0.55, 0.02), D)
        mb.box((lx, ly - 0.3, ROOF + 0.28), (0.55, 0.04, 0.55), P)
    else:
        chamfer_box(mb, (lx, ly, ROOF + 0.02), (0.58, 0.58, 0.05), P, 0.015)
        mb.pipe([(lx - 0.12, ly, ROOF + 0.04), (lx - 0.12, ly, ROOF + 0.1), (lx + 0.12, ly, ROOF + 0.1),
                 (lx + 0.12, ly, ROOF + 0.04)], 0.012, S, 6)
    chamfer_box(mb, (0.62, -0.5, ROOF + 0.09), (0.36, 0.22, 0.18), M["cast"], 0.03)
    mb.box((0.801, -0.5, ROOF + 0.11), (0.004, 0.16, 0.08), M["glass"])
    chamfer_box(mb, (0.15, 0.25, ROOF + 0.03), (0.3, 0.3, 0.06), P, 0.02)
    for x, y in ((0.75, 0.75), (0.75, -0.75), (-1.3, 0.75), (-1.3, -0.75)):
        mb.torus((x, y, ROOF + 0.04), 0.05, 0.015, S, 10, 4)
    # Smoke grenade dischargers on the front cheeks: three angled tubes a side.
    for s in (-1, 1):
        base = Vector((0.95, 1.12 * s, 0.5))
        for k in range(3):
            p0 = base + Vector((-0.12 * k, 0.03 * k * s, 0.0))
            d = Vector((0.75, 0.45 * s, 0.5)).normalized()
            mb.rod(p0, p0 + d * 0.22, 0.04, P, 10)
            mb.rod(p0 + d * 0.22, p0 + d * 0.225, 0.033, D, 10)
        chamfer_box(mb, tuple(base + Vector((-0.12, 0.0, -0.06))), (0.38, 0.1, 0.06), P, 0.01)
    # Side stowage bins and a rail basket round the bustle.
    for s in (-1, 1):
        chamfer_box(mb, (-0.75, 1.24 * s, 0.38), (1.1, 0.16, 0.38), P, 0.025)
        for x in (-1.15, -0.35):
            mb.box((x, 1.325 * s, 0.38), (0.06, 0.01, 0.06), S)
    rail = [(-1.6, 0.95, 0.62), (-2.05, 0.95, 0.62), (-2.05, -0.95, 0.62), (-1.6, -0.95, 0.62)]
    mb.pipe(rail, 0.018, S, 6)
    mb.pipe([(x, y, z - 0.38) for x, y, z in rail], 0.018, S, 6)
    for x, y, z in rail:
        mb.rod((x, y, z), (x, y, z - 0.38), 0.016, S, 6)
    for k in range(5):
        y = -0.8 + k * 0.4
        mb.rod((-2.05, y, 0.24), (-2.05, y, 0.62), 0.012, S, 5)
    if not burnt:
        chamfer_box(mb, (-1.85, 0.4, 0.4), (0.38, 0.6, 0.34), M["canvas"], 0.06)
        mb.rod((-1.85, -0.85, 0.42), (-1.85, -0.05, 0.42), 0.15, M["canvas"], 12)
        chamfer_box(mb, (-1.85, -0.45, 0.32), (0.3, 0.5, 0.18), P, 0.02)
        for y in (-0.55, -0.85):   # two whip antennas
            mb.cylinder((-1.3, y, ROOF - 0.02), 0.045, 0.1, S, 10)
            mb.rod((-1.3, y, ROOF + 0.06), (-1.45, y, ROOF + 2.4), 0.007, D, 4, radius_b=0.003)
    return finish(mb)


def gun_muzzle(turret_matrix):
    """World position and direction of the muzzle for a turret object's matrix_world."""
    return turret_matrix @ Vector((GUN_LEN, 0, GUN_Z)), (turret_matrix.to_3x3() @ Vector((1, 0, 0))).normalized()
