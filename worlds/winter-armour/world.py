"""Winter armour: a column of medium tanks advancing across a snowfield at blue hour, one of
them burning. Built from reference/photo.jpg (a high three-quarter view over the field).

Layout (metres, +Y north, camera south of the field looking north and down): thirteen tanks
spread over about 50 x 50 m, most heading east-north-east with their guns traversed toward a
threat on the right; two of them firing; one knocked-out tank burning on the right with black
smoke rolling away downwind. Frosted shrubs dot the snow, bare frosted trees stand at the
field's edges and a dark treeline closes the horizon.

The tank (tank.py) is modelled part by part: tracks link by link round the sprocket, idler, twin
road wheels and return rollers; welded hull with glacis furniture, louvres, fuel cells, tools and
tow cable; cast turret with mantlet, cupola, periscopes and stowage. Hull and turret are separate
prefabs so every turret can traverse while both stay instanced.

Light: about half an hour after sunset in January at 54 N (sun 4 degrees down in the
south-west): cold blue sky light, a faint warm afterglow on the western horizon, the fire's
orange light pooling on the snow, and two muzzle flashes. Snow falls in the viewer.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

from harness import *  # noqa: E402

import tank as T  # noqa: E402

META = {
    "title": "Winter Armour",
    "description": "A tank column crosses a snowfield at blue hour: one tank burning, two firing, snow falling.",
    "tags": ["military", "winter", "dusk", "fire", "photo-matched", "showcase"],
    "seed": 44,
    "render": {"res": "1600x1000", "samples": 64, "glare": 0.5},
    "viewer": {"bloom": 0.55},
    # Cold blue-cyan twilight grade, as in the reference.
    "grade": {"gains": [0.8, 1.0, 1.14], "saturation": 1.1},
}

FIELD = 160.0      # unique-textured snowfield (m)
TEX = 2048
WIND = (0.55, 0.22)   # smoke drift per metre of rise, toward the east-north-east


def height(x, y):
    h = 0.9 * fbm(x, y, scale=55, octaves=4, seed=3) + 0.22 * fbm(x, y, scale=14, octaves=3, seed=4)
    return h


# (x, y, hull heading deg, turret traverse deg relative to the hull, role)
TANKS = [
    (-10.0, 2.5, 18, 12, ""),
    (-1.0, 9.0, 12, 6, ""),
    (10.5, 2.5, 152, -6, ""),
    (14.0, 13.5, 168, -14, ""),
    (-17.0, 16.0, 142, 4, ""),
    (-6.5, 20.0, 34, -10, ""),
    (5.0, 20.5, 4, 2, "fire"),
    (-13.5, 31.0, 14, 22, ""),
    (-2.5, 33.5, 22, 18, ""),
    (9.0, 38.0, 186, 4, "fire"),
    (-24.0, 25.0, 40, 10, ""),
    (-7.0, 46.0, 12, 30, ""),
    (20.0, 44.0, 196, -12, ""),
]
WRECK = (16.5, 24.5, 208)


def ground_matrix(x, y, heading):
    """Hull matrix sitting on the snow: yaw to the heading, pitch and roll to the ground."""
    h = math.radians(heading)
    fx, fy = math.cos(h), math.sin(h)
    lx, ly = -fy, fx
    hf, hb = height(x + 2.6 * fx, y + 2.6 * fy), height(x - 2.6 * fx, y - 2.6 * fy)
    hl, hr = height(x + 1.3 * lx, y + 1.3 * ly), height(x - 1.3 * lx, y - 1.3 * ly)
    pitch = -math.atan2(hf - hb, 5.2)
    roll = math.atan2(hl - hr, 2.6)
    z = (hf + hb + hl + hr) / 4 - 0.04   # settle a few cm into the snow
    return Matrix.Translation((x, y, z)) @ Euler((roll, pitch, h), "XYZ").to_matrix().to_4x4()


def tank_path(rng, x, y, heading, length=60.0, step=0.05):
    """Where a tank came from: a gently curving line back from its position."""
    pts = []
    h = math.radians(heading + 180)
    curve = rng.uniform(-0.012, 0.012)
    px, py = x, y
    for k in range(int(length / step)):
        pts.append((px, py, h))
        h += curve * step
        px += math.cos(h) * step
        py += math.sin(h) * step
    return pts


# ---------------------------------------------------------------- snowfield texture

def snow_maps(rng, paths, scorch, craters):
    """Unique colour and normal maps for the snowfield: wind-rippled snow, tread ruts with grouser
    marks and pushed-up berms, a scorched melt patch round the wreck, and shell craters."""
    N, S = TEX, FIELD
    # World coordinates of each pixel (box UVs map u = x / S, v = y / S, wrapping).
    xs = (((np.arange(N) + 0.5) / N * S + S / 2) % S) - S / 2
    ys = (((1 - (np.arange(N) + 0.5) / N) * S + S / 2) % S) - S / 2
    X, Y = np.meshgrid(xs, ys)

    ripples = fbm_noise(N, 96, 3, 61)
    drifts = fbm_noise(N, 8, 5, 62)
    hgt = ripples * 0.35 + drifts * 1.2
    rut = np.zeros((N, N), np.float32)
    berm = np.zeros((N, N), np.float32)
    px_per_m = N / S

    across = np.linspace(-0.40, 0.40, 21)
    along = np.array([-0.03, 0.0, 0.03])
    A, C = np.meshgrid(along, across)
    A, C = A.ravel(), C.ravel()
    inside = np.abs(C) < 0.27
    for pts in paths:
        p = np.array(pts)
        s = np.arange(len(p)) * 0.05
        fade = np.clip(1.0 - s / (len(p) * 0.05), 0.25, 1.0)   # older track = drifted over a bit
        for side in (-1, 1):
            hx, hy = np.cos(p[:, 2]), np.sin(p[:, 2])
            cx = p[:, 0] - hy * T.TRACK_Y * side
            cy = p[:, 1] + hx * T.TRACK_Y * side
            wx = cx[:, None] + hx[:, None] * A[None] - hy[:, None] * C[None]
            wy = cy[:, None] + hy[:, None] * A[None] + hx[:, None] * C[None]
            j = (((wx / S) % 1) * N).astype(int) % N
            i = ((1 - (wy / S) % 1) * N).astype(int) % N
            grouser = 0.75 + 0.25 * np.cos(2 * np.pi * (s[:, None] + A[None]) / T.LINK_PITCH)
            depth = np.where(inside[None], -grouser, 0.0) * fade[:, None]
            bump = np.where(inside[None], 0.0, 1.0 - (np.abs(C[None]) - 0.27) / 0.13) * fade[:, None]
            np.minimum.at(rut, (i.ravel(), j.ravel()), depth.ravel().astype(np.float32))
            np.maximum.at(berm, (i.ravel(), j.ravel()), bump.ravel().astype(np.float32))
    rut = blur(rut[..., None], 1)[..., 0]
    berm = blur(berm[..., None], 2)[..., 0]
    hgt = hgt + rut * 1.0 + berm * 0.45

    # Shell craters: a dark pit, a raised rim and soot thrown out in rays.
    crater_mask = np.zeros((N, N), np.float32)
    soot = np.zeros((N, N), np.float32)
    ang_noise = value_noise((N, N), 40, 63)
    for cx, cy, r in craters:
        d = np.hypot(X - cx, Y - cy)
        pit = np.clip(1 - d / r, 0, 1)
        hgt += -pit ** 0.7 * 3.0 + np.exp(-((d - r) / (0.35 * r)) ** 2) * 1.2
        crater_mask = np.maximum(crater_mask, contrast(pit, 0.0, 0.5))
        theta = np.arctan2(Y - cy, X - cx)
        rays = 0.5 + 0.5 * np.sin(theta * 9 + ang_noise * 6)
        soot = np.maximum(soot, np.clip(1 - d / (r * 3.2), 0, 1) ** 1.5 * (0.4 + 0.6 * rays))
    # The wreck: snow melted to dark wet earth around it, soot beyond.
    wx, wy, wr = scorch
    d = np.hypot(X - wx, Y - wy) + (drifts - 0.5) * 3.0
    melt = contrast(np.clip(1 - d / wr, 0, 1), 0.25, 0.7)
    soot = np.maximum(soot, np.clip(1 - d / (wr * 2.4), 0, 1) ** 1.3)

    # Colour: fine sparkle variation, compacted grey-blue snow in the ruts with grit, soot, earth.
    snow = colorize(contrast(ripples * 0.5 + drifts * 0.5, 0.2, 0.8), "#e3e9f1", "#f4f7fb")
    packed = colorize(fbm_noise(N, 64, 3, 64), "#c8cfd8", "#dbe0e7")
    grit = contrast(fbm_noise(N, 160, 2, 65), 0.66, 0.78) * 0.35
    rut_t = np.clip(-rut, 0, 1)[..., None]
    px = snow * (1 - rut_t * 0.85) + packed * rut_t * 0.85
    px = px * (1 - (grit * rut_t[..., 0])[..., None]) + np.array([0.42, 0.39, 0.35]) * (grit * rut_t[..., 0])[..., None]
    # Dark flecks: dead grass and stubble poking through the snow.
    fleck = contrast(value_noise(N, 700, 68), 0.86, 0.95) * contrast(fbm_noise(N, 10, 3, 69), 0.4, 0.7)
    px = px * (1 - fleck[..., None] * 0.7) + np.array([0.33, 0.30, 0.28]) * fleck[..., None] * 0.7
    soot_c = np.array([0.24, 0.22, 0.21])
    st = (soot * 0.8)[..., None]
    px = px * (1 - st) + soot_c * st
    earth = colorize(fbm_noise(N, 48, 4, 66), "#1f1b17", "#3a3128")
    em = np.maximum(melt, crater_mask)[..., None]
    px = px * (1 - em) + earth * em
    hgt += melt * (fbm_noise(N, 120, 2, 67) - 0.5) * 2.0
    # Fade to plain snow toward the field edge so it meets the tiled backdrop snow cleanly.
    edge = np.clip((np.maximum(np.abs(X), np.abs(Y)) - (S / 2 - 14)) / 12, 0, 1)[..., None]
    px = px * (1 - edge) + np.array([0.93, 0.95, 0.97]) * edge
    col = texture("snowfield", np.clip(px, 0, 1), quality=88)
    nrm = texture("snowfield_n", height_normal(hgt, 0.9), data=True, quality=90)
    return col, nrm


# ---------------------------------------------------------------- vegetation

def shrub_prefab(rng, name, mats):
    """Dry frosted shrub: a clump of thin stems that fork twice and end in frosted twigs."""
    mb = MeshBuilder(name)
    stems = rng.randint(14, 22)
    for k in range(stems):
        a = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.3, 1.3)
        p0 = Vector((rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), -0.05))
        d = Vector((math.cos(a) * lean, math.sin(a) * lean, 1)).normalized()
        L = rng.uniform(0.35, 0.75)
        _branch(mb, rng, p0, d, L, 0.016, 0, mats)
    return prefab(mb.build())


def _branch(mb, rng, p, d, L, r, depth, mats):
    q = p + d * L
    mb.rod(p, q, r, mats[min(depth, len(mats) - 1)], 3 if depth else 4, radius_b=r * 0.6, caps=False)
    if depth >= 2:
        return
    for _ in range(3 if depth else rng.randint(3, 4)):
        nd = (d + Vector((rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), rng.uniform(0.0, 0.6)))).normalized()
        start = p + d * L * rng.uniform(0.5, 0.95)
        _branch(mb, rng, start, nd, L * rng.uniform(0.55, 0.8), r * 0.6, depth + 1, mats)


def tree_prefab(rng, name, mats, h):
    """Bare deciduous tree, frost on the fine twigs: a tapering trunk forking into four levels."""
    mb = MeshBuilder(name)

    def grow(p, d, L, r, depth):
        q = p + d * L
        segs = (8, 6, 5, 4, 4)[depth]
        mb.rod(p, q, r, mats[depth], segs, radius_b=r * 0.72, caps=depth == 0)
        if depth == 4:
            return
        n = 2 if depth == 0 else rng.randint(2, 4)
        for k in range(n):
            nd = (d * (1.2 if depth == 0 else 0.8) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1),
                                                              rng.uniform(-0.1, 0.7)))).normalized()
            t = rng.uniform(0.55, 1.0) if depth else rng.uniform(0.75, 1.0)
            grow(p + d * L * t, nd, L * rng.uniform(0.5, 0.72), r * 0.6, depth + 1)
    grow(Vector((0, 0, -0.3)), Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 1)).normalized(),
         h * 0.42, 0.11 + h * 0.012, 0)
    return prefab(mb.build())


def conifer_prefab(name, mats, h):
    """Snow-laden spruce for the distant treeline: stacked dark tiers with snow on top."""
    mb = MeshBuilder(name)
    mb.rod((0, 0, 0), (0, 0, h * 0.2), h * 0.03, mats["bark"], 6)
    tiers = 4
    for k in range(tiers):
        z0 = h * (0.12 + 0.2 * k)
        r = h * 0.3 * (1 - k / (tiers + 0.6))
        mb.cylinder((0, 0, z0), r, h * 0.32, mats["needles"], 8, radius_top=0.0)
        mb.cylinder((0, 0, z0 + h * 0.1), r * 0.72, h * 0.23, mats["snow"], 8, radius_top=0.0)
    return prefab(mb.build())


# ---------------------------------------------------------------- build

def build(ctx):
    rng = ctx.rng

    # -- tanks first (the ground texture needs their tracks)
    M = T.materials()
    MB = T.materials(burnt=True)
    hull_p = prefab(T.hull(M, "TankHull", rng=rng).build())
    turret_p = prefab(T.turret(M, "TankTurret", rng=rng).build())
    wreck_h = prefab(T.hull(MB, "WreckHull", burnt=True).build())
    wreck_t = prefab(T.turret(MB, "WreckTurret", burnt=True, hatch_open=True).build())

    paths = []
    firing = []
    for k, (x, y, hd, tr, role) in enumerate(TANKS):
        hm = ground_matrix(x, y, hd)
        h = instance(hull_p, f"Tank{k + 1:02d}", collection="Tanks")
        h.matrix_world = hm
        tm = hm @ Matrix.Translation((T.TURRET_X, 0, T.DECK_Z + 0.05)) @ Matrix.Rotation(math.radians(tr), 4, "Z")
        t = instance(turret_p, f"Tank{k + 1:02d}Turret", collection="Tanks")
        t.matrix_world = tm
        paths.append(tank_path(rng, x, y, hd))
        if role == "fire":
            firing.append(tm)
    wx, wy, whd = WRECK
    hm = ground_matrix(wx, wy, whd)
    w = instance(wreck_h, "Wreck", collection="Tanks")
    w.matrix_world = hm
    # The turret has been lifted off its ring by the blast and sits askew.
    tm = (hm @ Matrix.Translation((T.TURRET_X - 0.25, 0.35, T.DECK_Z + 0.12)) @
          Matrix.Rotation(math.radians(38), 4, "Z") @ Matrix.Rotation(math.radians(-7), 4, "X") @
          Matrix.Rotation(math.radians(5), 4, "Y"))
    wt = instance(wreck_t, "WreckTurret", collection="Tanks")
    wt.matrix_world = tm
    paths.append(tank_path(rng, wx, wy, whd, length=40))
    # Older tracks from the tanks that went through earlier, crossing the field.
    for k in range(2):
        x0 = rng.uniform(-35, 35)
        paths.append(tank_path(rng, x0, rng.uniform(55, 70), rng.uniform(250, 290), length=90))

    craters = [(rng.uniform(-28, 28), rng.uniform(-5, 55), rng.uniform(0.8, 1.3)) for _ in range(4)]
    craters.append((wx + 4.5, wy - 3.0, 1.6))

    # -- snowfield
    col, nrm = snow_maps(rng, paths, (wx, wy, 4.2), craters)
    snow_mat = material("snowfield", texture=col, normal=nrm, texture_size=FIELD, roughness=0.62)
    terrain("Snowfield", size=FIELD, resolution=256, height=height, material=snow_mat, smooth=True,
            collection="Ground")
    far_px = colorize(fbm_noise(512, 6, 5, 70), "#e2e8f0", "#f3f6fa")
    far_n = height_normal(fbm_noise(512, 48, 3, 71) * 0.4 + fbm_noise(512, 6, 4, 72), 0.8)
    far_mat = material("snow_far", texture=texture("snow_far", far_px), texture_size=12.0,
                       normal=texture("snow_far_n", far_n, data=True), roughness=0.62)

    def far_height(x, y):
        r = max(abs(x), abs(y))
        dip = 0.3 * (1 - min(1.0, max(0.0, (r - FIELD / 2 + 3) / 6)))
        hills = 30 * max(0.0, min(1.0, (math.hypot(x, y) - 160) / 500)) ** 1.5 * (0.6 + fbm(x, y, 260, 4, 9))
        return height(x, y) - dip + hills
    terrain("SnowBackdrop", size=1800, resolution=120, height=far_height, material=far_mat, smooth=True,
            backdrop=True, collection="Ground")

    # -- vegetation
    twig = material("twig", "#5b5048", roughness=0.9)
    twig_frost = material("twig_frost", "#9d9aa0", roughness=0.8)
    frost = material("frost", "#d9dee6", roughness=0.7)
    shrubs = [shrub_prefab(rng, f"Shrub{k}", [twig, twig_frost, frost]) for k in range(5)]
    tank_pts = [(x, y) for x, y, *_ in TANKS] + [(wx, wy)]
    path_pts = [(p[0], p[1]) for path in paths for p in path[::40]]

    def clear(x, y):
        if any((x - a) ** 2 + (y - b) ** 2 < 20 for a, b in tank_pts):
            return False
        return not any((x - a) ** 2 + (y - b) ** 2 < 3.2 for a, b in path_pts)
    for i, (x, y, z) in enumerate(scatter(rng, 300, (-50, 50, -16, 72), height,
                                          accept=lambda x, y, z: clear(x, y), min_dist=2.2)):
        s = rng.uniform(1.0, 2.0)
        instance(rng.choice(shrubs), f"Shrub.{i}", (x, y, z), (0, 0, rng.uniform(0, 360)),
                 (s, s, s * rng.uniform(0.7, 1.2)), collection="Shrubs")
    bark = material("bark", "#4a4440", roughness=0.9)
    bark_frost = material("bark_frost", "#a9acb2", roughness=0.85)
    trees = [tree_prefab(rng, f"Tree{k}", [bark, bark_frost, twig_frost, frost, frost], h)
             for k, h in enumerate((9.0, 11.0, 7.5))]
    groves = [(-30, 46, 8), (-36, 8, 5), (30, 58, 5), (34, 18, 3), (-12, 64, 5), (12, 70, 6)]
    k = 0
    for gx, gy, n in groves:
        for _ in range(n):
            x, y = gx + rng.uniform(-7, 7), gy + rng.uniform(-6, 6)
            if not clear(x, y):
                continue
            s = rng.uniform(0.75, 1.25)
            instance(rng.choice(trees), f"Tree.{k}", (x, y, height(x, y)), (0, 0, rng.uniform(0, 360)), s,
                     collection="Trees")
            k += 1
    cm = {"bark": bark, "needles": material("spruce", "#1d2a24", roughness=0.85),
          "snow": material("spruce_snow", "#dfe6ee", roughness=0.7)}
    spruces = [conifer_prefab(f"Spruce{k}", cm, h) for k, h in enumerate((11.0, 14.0, 17.0))]
    k = 0
    for x in np.arange(-260, 260, 3.2):   # the treeline on the far side of the field
        for row in range(3):
            y = 105 + row * 7 + 10 * math.sin(x / 37.0) + 6 * fbm(x, row, 20, 2, 5) + rng.uniform(-2, 2)
            if rng.random() < 0.18:
                continue
            o = instance(rng.choice(spruces), f"Spruce.{k}", (x + rng.uniform(-1, 1), y, far_height(x, y) - 0.3),
                         (0, 0, rng.uniform(0, 360)), rng.uniform(0.8, 1.3), collection="Treeline")
            o["backdrop"] = True
            k += 1
    for x in np.arange(-200, 200, 9.0):   # bare trees in front of the spruces
        y = 96 + rng.uniform(-4, 4)
        o = instance(rng.choice(trees), f"Tree.{k}", (x, y, far_height(x, y)), (0, 0, rng.uniform(0, 360)),
                     rng.uniform(0.9, 1.4), collection="Treeline")
        o["backdrop"] = True
        k += 1

    # -- debris round the wreck: torn plates and a thrown road wheel
    debris_mat = MB["paint"]
    deb = MeshBuilder("Debris")
    for _ in range(14):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(3, 8)
        x, y = wx + math.cos(a) * d, wy + math.sin(a) * d
        deb.box((x, y, height(x, y) + 0.03), (rng.uniform(0.2, 0.7), rng.uniform(0.15, 0.5), 0.03), debris_mat,
                rotation=(rng.uniform(-15, 15), rng.uniform(-15, 15), rng.uniform(0, 180)))
    T.road_wheel(deb, MB, (wx - 5.0, wy + 2.5, height(wx - 5, wy + 2.5) + 0.15), 1, detail=False)
    deb.build(collection="Tanks")

    # -- fire, smoke and gunfire
    eng = hm @ Vector((-1.4, 0, T.DECK_Z))
    fire(tuple(eng), radius=2.7, height=3.8, power=90000.0, brightness=0.22, color="#ff3a00",
         core="#ffa424", seed=1)
    fire(tuple(tm @ Vector((-0.2, 0.42, 0.95))), radius=0.5, height=1.8, power=12000.0, brightness=0.3, color="#ff3a00", core="#ffa424",
         seed=2, lights=1)
    plume(tuple(eng + Vector((0, 0, 2.0))), height=40, radius=3.2, drift=(0.35, 0.12), density=2.0, rise=3.0,
          low="#3a2a22", high="#151515", glow=0.4, albedo=0.03, seed=3, name="Smoke")
    for k, tmx in enumerate(firing):
        mz, d = T.gun_muzzle(tmx)
        muzzle_flash(tuple(mz), tuple(d), length=1.8, radius=0.5, power=8000.0, brightness=0.6, color="#ff7a1a", core="#ffd890",
                     period=6.0 + 2.5 * k, seed=k)
        plume(tuple(mz + d * 1.5), height=4.5, radius=0.6, drift=(0.5, 0.2), density=0.2, rise=1.0,
              low="#cfd3d8", high="#9aa2ad", albedo=0.7, glow=0.2, seed=10 + k, name="GunSmoke")

    # -- light and camera
    atmosphere(time="16:30", latitude=54.0, day=20, haze=0.6, visibility=700, exposure=2.2, lamps="on")
    snowfall(rate=1.0, size=0.03, speed=1.0, wind=(0.6, 0.25), area=70)
    camera((-2.0, -19.0, 19.5), (1.5, 18.0, 0.0), lens=30)
