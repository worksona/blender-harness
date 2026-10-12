"""Reusable process-plant equipment: vessels, drums, steel frames, pipe racks, air coolers,
storage tanks, LPG spheres, fired heaters, stacks, cooling towers, flares, instanced infill
kits, and vehicles and trees. Used by worlds/oil-refinery and worlds/refinery-dusk.

All builders take a MeshBuilder `mb` and a material dict `M` (see mats()). Heights are relative
to the plant pad, which set_pad(z) moves (default 0).

    from harness import industrial as ind
    ind.set_pad(1.62)
    M = ind.mats()
    mb = MeshBuilder("Unit"); ind.vessel(mb, M, 0, 0, 3.5, 50); mb.build()
"""

import math

from mathutils import Vector

from .builder import MeshBuilder
from .core import instance, material, prefab

PAD = 0.0  # top of the concrete pads equipment stands on


def set_pad(z):
    """Set the plant pad elevation used by every builder here."""
    global PAD
    PAD = z


def mats():
    m = {}
    m["concrete"] = material("concrete", "#a7a39a", roughness=0.9)
    m["asphalt"] = material("asphalt", "#3d3e40", roughness=0.85)
    m["steel"] = material("steel_painted", "#70767c", roughness=0.55, metallic=0.4)
    m["yellow"] = material("safety_yellow", "#e3b52a", roughness=0.5)
    m["grating"] = material("grating", "#55595d", roughness=0.7, metallic=0.5)
    m["clad"] = material("aluminium_cladding", "#c8ccd0", roughness=0.32, metallic=0.75)
    m["tank"] = material("tank_white", "#e4e5e1", roughness=0.45)
    m["tank_roof"] = material("tank_roof", "#a9aaa6", roughness=0.6, metallic=0.2)
    m["skirt"] = material("skirt_grey", "#5c6166", roughness=0.6)
    m["dark"] = material("dark_steel", "#2c2f33", roughness=0.6, metallic=0.3)
    m["heater"] = material("heater_casing", "#4a4f55", roughness=0.6, metallic=0.2)
    m["red"] = material("stack_red", "#b3362b", roughness=0.5)
    m["white"] = material("stack_white", "#ecebe6", roughness=0.5)
    m["green_pipe"] = material("pipe_green", "#4f7a5a", roughness=0.5)
    m["pipe_grey"] = material("pipe_grey", "#8b9096", roughness=0.4, metallic=0.5)
    m["pipe_silver"] = material("pipe_insulated", "#cfd2d4", roughness=0.3, metallic=0.8)
    m["pipe_yellow"] = material("pipe_yellow", "#d9a62a", roughness=0.5)
    m["pipe_brown"] = material("pipe_rust", "#7a5236", roughness=0.8)
    m["fan"] = material("fan_dark", "#1f2124", roughness=0.7)
    m["ct_wall"] = material("cooling_tower_wall", "#7f8c93", roughness=0.7)
    m["building"] = material("building_beige", "#cdbfa4", roughness=0.8)
    m["glass"] = material("glass_dark", "#28323c", roughness=0.08, metallic=0.6)
    m["roof"] = material("roof_grey", "#6a6d70", roughness=0.8)
    m["sphere"] = material("lpg_sphere", "#eceeec", roughness=0.35, metallic=0.1)
    m["flame_o"] = material("flame_outer", "#ff7a1a", emission="#ff6a10", emission_strength=40,
                            alpha=0.9)
    m["flame_i"] = material("flame_inner", "#ffe08a", emission="#ffd36a", emission_strength=80)
    m["warn"] = material("warning_light", "#ff2a1a", emission="#ff2a1a", emission_strength=25)
    m["hull_top"] = material("hull_black", "#1d2226", roughness=0.5)
    m["hull_bot"] = material("hull_red", "#8f2a22", roughness=0.6)
    m["deck"] = material("deck_green", "#4c6b4c", roughness=0.7)
    m["accom"] = material("accommodation_white", "#f0efea", roughness=0.5)
    return m


# ------------------------------------------------------------------ equipment

def vessel(mb, M, x, y, radius, height_, z0=None, skirt=4.0, platform_every=9.0, shell="clad",
           ladder_angle=0.0, head=0.5, sections=None, seg=40):
    """Vertical column/vessel with skirt, insulation bands, platforms, ladder and top head.
    sections: optional [(height, radius), ...] stacked shell courses (for tapered columns)."""
    z0 = PAD if z0 is None else z0
    mb.cylinder((x, y, z0), radius * 0.95, skirt, M["skirt"], seg)
    z = z0 + skirt
    courses = sections or [(height_ - skirt, radius)]
    prev_r = courses[0][1]
    for h, r in courses:
        if abs(r - prev_r) > 0.01:  # conical transition
            mb.rod((x, y, z), (x, y, z + 3), prev_r, M[shell], seg, radius_b=r, caps=False)
            z += 3
        mb.rod((x, y, z), (x, y, z + h), r, M[shell], seg, caps=False)
        for k in range(1, int(h / 3)) if seg >= 32 else ():
            mb.torus((x, y, z + 3 * k), r + 0.02, 0.035, M["pipe_grey"], seg, 4)
        z += h
        prev_r = r
    top = z
    mb.dome((x, y, top), prev_r, prev_r * head, M[shell], seg, 6 if seg >= 32 else 3)
    # Platforms (open ring, gap where the ladder passes) and the ladder itself.
    zr = z0 + skirt + platform_every
    while zr < top - 1:
        r_here = _radius_at(zr - z0 - skirt, courses)
        mb.ring_platform((x, y, zr), r_here, r_here + 1.3, M["grating"], M["yellow"], seg,
                         arc=300, start=ladder_angle + 30)
        zr += platform_every
    r0 = courses[0][1]
    a = math.radians(ladder_angle)
    lx, ly = x + (r0 + 0.6) * math.cos(a), y + (r0 + 0.6) * math.sin(a)
    mb.ladder((lx, ly, z0), top - z0, M["yellow"], facing=ladder_angle)
    mb.ring_platform((x, y, top + prev_r * head * 0.3), 0.0, prev_r * 0.8, M["grating"], M["yellow"],
                     24)
    # Nozzles with flanges.
    for k in range(3):
        nz = z0 + skirt + (k + 1) * (top - z0 - skirt) / 4
        ang = a + math.pi * (0.6 + 0.35 * k)
        r_here = _radius_at(nz - z0 - skirt, courses)
        p0 = Vector((x + r_here * math.cos(ang), y + r_here * math.sin(ang), nz))
        p1 = p0 + Vector((math.cos(ang), math.sin(ang), 0)) * 1.2
        mb.rod(p0, p1, 0.3, M["pipe_grey"], 16)
        mb.rod(p1, p1 + (p1 - p0).normalized() * 0.12, 0.5, M["pipe_grey"], 16)
    return top + prev_r * head


def _radius_at(h, courses):
    for ch, r in courses:
        if h <= ch:
            return r
        h -= ch
    return courses[-1][1]


def drum(mb, M, center, radius, length, axis="x", mat="pipe_silver", saddle_h=1.2):
    """Horizontal vessel on two concrete saddles."""
    cx, cy, cz = center
    d = Vector((1, 0, 0)) if axis == "x" else Vector((0, 1, 0))
    c = Vector(center)
    a, b = c - d * length / 2, c + d * length / 2
    mb.rod(a, b, radius, M[mat], 40, caps=False)
    sc = (0.45, 1, 1) if axis == "x" else (1, 0.45, 1)
    mb.sphere(a, radius, M[mat], 3, sc)
    mb.sphere(b, radius, M[mat], 3, sc)
    saddle = saddle_h + radius * 0.5          # from below the drum up to its lower third
    for t in (-0.3, 0.3):
        s = c + d * length * t
        size = (0.6, radius * 1.6, saddle) if axis == "x" else (radius * 1.6, 0.6, saddle)
        mb.box((s.x, s.y, cz - radius - saddle_h + saddle / 2), size, M["concrete"])
    for k in range(1, int(length / 2.5)):
        p = a + d * 2.5 * k
        mb.rod(p - d * 0.05, p + d * 0.05, radius + 0.04, M["pipe_grey"], 40, caps=False)


def steel_frame(mb, M, x0, y0, x1, y1, z0, levels, bay=6.0, floors=None, brace=True):
    """Open steel structure: columns on a grid, beams at each level, grating floors, X-braces."""
    nx = max(1, round((x1 - x0) / bay))
    ny = max(1, round((y1 - y0) / bay))
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]
    top = z0 + levels[-1]
    for x in xs:
        for y in ys:
            mb.beam((x, y, z0), (x, y, top), 0.45, M["steel"])
            mb.box((x, y, z0 + 0.3), (1.0, 1.0, 0.6), M["concrete"])
    for lv in levels:
        z = z0 + lv
        for y in ys:
            mb.beam((x0, y, z), (x1, y, z), 0.32, M["steel"])
        for x in xs:
            mb.beam((x, y0, z), (x, y1, z), 0.32, M["steel"])
        if floors is None or lv in floors:
            mb.slab(x0 - 0.8, y0 - 0.8, x1 + 0.8, y1 + 0.8, z + 0.2, 0.06, M["grating"])
            mb.railing([(x0 - 0.8, y0 - 0.8, z + 0.2), (x1 + 0.8, y0 - 0.8, z + 0.2),
                        (x1 + 0.8, y1 + 0.8, z + 0.2), (x0 - 0.8, y1 + 0.8, z + 0.2)],
                       M["yellow"], post_step=3.0, closed=True)
    if brace:
        zs = [z0] + [z0 + lv for lv in levels]
        for za, zb in zip(zs, zs[1:]):
            for (xa, ya), (xb, yb) in (((xs[0], y0), (xs[1], y0)), ((xs[-2], y1), (xs[-1], y1)),
                                       ((x0, ys[0]), (x0, ys[1])), ((x1, ys[-2]), (x1, ys[-1]))):
                mb.beam((xa, ya, za), (xb, yb, zb), 0.22, M["steel"])
                mb.beam((xb, yb, za), (xa, ya, zb), 0.22, M["steel"])
    # Stair tower ladder on one corner.
    mb.ladder((x0 - 1.2, y0 + 1.5, z0), levels[-1], M["yellow"], facing=180)


PIPE_SETS = [("pipe_grey", 0.25, 0.55), ("pipe_silver", 0.3, 0.7), ("pipe_yellow", 0.15, 0.3),
             ("green_pipe", 0.2, 0.4), ("pipe_brown", 0.2, 0.45)]


def pipe_rack(mb, M, rng, a, b, z0=None, width=10.0, tiers=(6.0, 10.0, 14.0), bay=8.0):
    """Multi-tier pipe rack from (x, y) a to b, loaded with pipes."""
    z0 = PAD if z0 is None else z0
    a, b = Vector((*a, 0)), Vector((*b, 0))
    d = (b - a).normalized()
    n = Vector((-d.y, d.x, 0))
    length = (b - a).length
    nb = max(1, round(length / bay))
    top = tiers[-1]
    for i in range(nb + 1):
        p = a + d * (length * i / nb)
        c1, c2 = p + n * width / 2, p - n * width / 2
        for c in (c1, c2):
            mb.beam((c.x, c.y, z0), (c.x, c.y, z0 + top + 0.3), 0.42, M["steel"])
            mb.box((c.x, c.y, z0 + 0.25), (0.9, 0.9, 0.5), M["concrete"])
        for t in tiers:
            mb.beam((c1.x, c1.y, z0 + t), (c2.x, c2.y, z0 + t), 0.35, M["steel"])
        for c, s in ((c1, -1), (c2, 1)):  # knee braces under the first tier
            mb.beam((c.x, c.y, z0 + tiers[0] - 1.6),
                    (c.x + n.x * s * 1.6, c.y + n.y * s * 1.6, z0 + tiers[0]), 0.2, M["steel"])
        if i < nb and i % 5 == 2:  # longitudinal X-bracing
            q = a + d * (length * (i + 1) / nb)
            for side in (1, -1):
                pa, pb = p + n * side * width / 2, q + n * side * width / 2
                mb.beam((pa.x, pa.y, z0), (pb.x, pb.y, z0 + tiers[0]), 0.2, M["steel"])
                mb.beam((pb.x, pb.y, z0), (pa.x, pa.y, z0 + tiers[0]), 0.2, M["steel"])
    for t in tiers:
        for side in (1, -1):
            s = n * side * width / 2
            mb.beam((a + s).to_tuple()[:2] + (z0 + t,), (b + s).to_tuple()[:2] + (z0 + t,), 0.3, M["steel"])
        off = -width / 2 + 0.5
        while True:
            mat, rmin, rmax = PIPE_SETS[rng.randrange(len(PIPE_SETS))]
            r = rng.uniform(rmin, rmax)
            if off + 2 * r > width / 2 - 0.4:
                break
            o = n * (off + r)
            zp = z0 + t + 0.175 + r
            mb.rod((a.x + o.x, a.y + o.y, zp), (b.x + o.x, b.y + o.y, zp), r, M[mat], 16, caps=False)
            off += 2 * r + rng.uniform(0.15, 0.5)


def air_coolers(mb, M, x0, y0, x1, y1, z):
    """Bank of fin-fan air coolers on a platform at height z: plenums, fan rings, blades."""
    mb.slab(x0, y0, x1, y1, z, 0.08, M["grating"])
    for xx in (x0, x1):
        for yy in (y0, y1):
            mb.beam((xx, yy, z - 4), (xx, yy, z), 0.35, M["steel"])
    n = max(1, int((x1 - x0) / 5))
    w = (x1 - x0) / n
    for i in range(n):
        cx = x0 + w * (i + 0.5)
        mb.box((cx, (y0 + y1) / 2, z + 1.2), (w - 0.3, y1 - y0 - 1.0, 1.6), M["pipe_grey"])
        mb.box((cx, (y0 + y1) / 2, z + 2.15), (w - 0.2, y1 - y0 - 0.6, 0.3), M["dark"])  # tube bundle
        for j in (-1, 1):
            cy = (y0 + y1) / 2 + j * (y1 - y0) / 4
            fr = min(w, (y1 - y0) / 2) * 0.42
            mb.rod((cx, cy, z + 2.3), (cx, cy, z + 3.1), fr, M["pipe_grey"], 32, caps=False)
            mb.torus((cx, cy, z + 3.1), fr, 0.06, M["pipe_grey"], 32, 4)
            mb.rod((cx, cy, z + 2.5), (cx, cy, z + 2.6), fr * 0.95, M["fan"], 32)
            for k in range(6):
                ang = k * math.pi / 3
                mb.box((cx + math.cos(ang) * fr * 0.45, cy + math.sin(ang) * fr * 0.45, z + 2.7),
                       (fr * 0.85, 0.28, 0.05), M["dark"], rotation=(0, 8, math.degrees(ang)))
            mb.rod((cx, cy, z + 2.6), (cx, cy, z + 2.9), 0.25, M["dark"], 12)
    mb.railing([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], M["yellow"], closed=True,
               post_step=3)
    mb.box((x0 - 0.6, (y0 + y1) / 2, z + 1.2), (0.8, y1 - y0 - 1, 1.4), M["pipe_silver"])  # header


def storage_tank(mb, M, x, y, radius, height_, floating=True):
    """Welded storage tank: shell courses, wind girder, spiral stair, roof."""
    mb.cylinder((x, y, PAD - 0.3), radius + 0.6, 0.5, M["concrete"], 64)  # ring wall
    mb.rod((x, y, PAD), (x, y, PAD + height_), radius, M["tank"], 64, caps=False)
    for k in range(1, int(height_ / 2.4) + 1):
        mb.torus((x, y, PAD + 2.4 * k), radius + 0.02, 0.04, M["tank_roof"], 64, 4)
    mb.torus((x, y, PAD + height_ - 1.0), radius + 0.7, 0.18, M["tank"], 64, 4)  # wind girder
    mb.ring_platform((x, y, PAD + height_ - 0.9), radius, radius + 1.0, M["grating"], M["yellow"],
                     64, arc=360)
    if floating:
        roof_z = PAD + height_ * 0.55
        mb.cylinder((x, y, roof_z), radius - 0.25, 0.8, M["tank_roof"], 64)
        mb.torus((x, y, roof_z + 0.8), radius - 1.6, 0.6, M["tank_roof"], 64, 6)  # pontoon
        mb.beam((x + radius - 0.8, y, PAD + height_), (x + radius * 0.25, y, roof_z + 0.8), 0.6,
                M["steel"])  # rolling ladder
        mb.rod((x, y, PAD + 0.1), (x, y, PAD + 0.12), radius - 0.05, M["tank_roof"], 64)  # floor
    else:
        mb.dome((x, y, PAD + height_), radius, radius * 0.12, M["tank_roof"], 64, 5)
    # Spiral stair around a third of the shell.
    steps = int(height_ / 0.22)
    rail = []
    for s in range(steps + 1):
        t = s / steps
        ang = math.radians(200 + 115 * t)
        r = radius + 0.65
        z = PAD + t * (height_ - 0.9)
        mb.box((x + r * math.cos(ang), y + r * math.sin(ang), z), (0.28, 1.1, 0.05), M["grating"],
               rotation=(0, 0, math.degrees(ang)))
        rail.append((x + (r + 0.55) * math.cos(ang), y + (r + 0.55) * math.sin(ang), z))
    mb.railing(rail[::4] + [rail[-1]], M["yellow"], post_step=6)


def bund(mb, M, x, y, half):
    for (ax, ay), (bx, by) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
        mb.beam((x + ax * half, y + ay * half, PAD), (x + bx * half, y + by * half, PAD), 0.4,
                M["concrete"], depth=2.4)


def lpg_sphere(mb, M, x, y, r):
    cz = PAD + r + 4
    mb.sphere((x, y, cz), r, M["sphere"], 4)
    mb.torus((x, y, cz), r + 0.05, 0.12, M["pipe_grey"], 64, 4)
    legs = 10
    for i in range(legs):
        a = 2 * math.pi * i / legs
        px, py = x + r * math.cos(a), y + r * math.sin(a)
        mb.rod((px, py, PAD), (px, py, cz), 0.35, M["sphere"], 16)
        a2 = 2 * math.pi * (i + 1) / legs
        qx, qy = x + r * math.cos(a2), y + r * math.sin(a2)
        mb.rod((px, py, PAD + 0.5), (qx, qy, cz - r * 0.45), 0.07, M["steel"], 6)
        mb.rod((qx, qy, PAD + 0.5), (px, py, cz - r * 0.45), 0.07, M["steel"], 6)
    mb.ring_platform((x, y, cz + r * 0.98), 0, 2.4, M["grating"], M["yellow"], 24)
    mb.ladder((x + r + 1.2, y, PAD), r + 4, M["yellow"], facing=0)
    # Stair arc from the equator to the top platform.
    pts = []
    for s in range(25):
        t = s / 24
        ang = t * math.pi / 2
        pts.append((x + (r + 0.8) * math.cos(ang * 0.9), y + (r + 0.8) * math.sin(ang * 0.3),
                    cz + (r + 0.8) * math.sin(ang) * 0.98))
    mb.railing(pts, M["yellow"], height=1.0, post_step=2)


def fired_heater(mb, M, x, y, w=30.0, d=13.0, h=20.0, stacks=1):
    mb.box((x, y, PAD + 2 + h / 2), (w, d, h), M["heater"])
    for i in range(int(w / 2) + 1):  # buckstays
        xx = x - w / 2 + i * w / int(w / 2)
        for s in (-1, 1):
            mb.beam((xx, y + s * (d / 2 + 0.15), PAD), (xx, y + s * (d / 2 + 0.15), PAD + 2 + h), 0.3,
                    M["dark"])
    for xx in (x - w / 2 + 1, x + w / 2 - 1):
        for yy in (y - d / 2 + 1, y + d / 2 - 1):
            mb.beam((xx, yy, PAD), (xx, yy, PAD + 2), 0.6, M["dark"])
    mb.box((x, y, PAD + 2 + h + 4), (w * 0.8, d * 0.55, 8), M["heater"])  # convection section
    mb.slab(x - w / 2 - 1.2, y - d / 2 - 1.2, x + w / 2 + 1.2, y + d / 2 + 1.2, PAD + 2 + h, 0.08,
            M["grating"])
    mb.railing([(x - w / 2 - 1.2, y - d / 2 - 1.2, PAD + 2 + h), (x + w / 2 + 1.2, y - d / 2 - 1.2, PAD + 2 + h),
                (x + w / 2 + 1.2, y + d / 2 + 1.2, PAD + 2 + h), (x - w / 2 - 1.2, y + d / 2 + 1.2, PAD + 2 + h)],
               M["yellow"], closed=True, post_step=3)
    for k in range(stacks):
        sx = x + (k - (stacks - 1) / 2) * w * 0.45
        base = PAD + 2 + h + 8
        mb.rod((sx, y, base), (sx, y, base + 48), 1.8, M["dark"], 32, radius_b=1.5)
        mb.ring_platform((sx, y, base + 44), 1.6, 2.8, M["grating"], M["yellow"], 32)
        mb.ladder((sx + 2.2, y, base), 44, M["yellow"])
        mb.sphere((sx, y, base + 48.4), 0.35, M["warn"], 1)
    mb.ladder((x - w / 2 - 0.8, y, PAD), h + 2, M["yellow"], facing=180)


def stack(mb, M, x, y, h=90.0, r=2.6):
    """Red/white banded stack with platforms and aviation lights."""
    band = h / 9
    for i in range(9):
        z = PAD + i * band
        rr = r - (r - r * 0.7) * i / 9
        rn = r - (r - r * 0.7) * (i + 1) / 9
        mb.rod((x, y, z), (x, y, z + band), rr, M["red"] if i >= 6 and i % 2 == 0 or i == 8 else M["white"],
               40, radius_b=rn, caps=False)
    for zz in (h * 0.5, h * 0.92):
        rr = r - (r - r * 0.7) * zz / h
        mb.ring_platform((x, y, PAD + zz), rr, rr + 1.4, M["grating"], M["yellow"], 40)
        mb.sphere((x + rr + 0.2, y, PAD + zz + 1.5), 0.3, M["warn"], 1)
    mb.ladder((x + r + 0.6, y, PAD), h, M["yellow"])


def cooling_tower(mb, M, x0, y, cells=6, cell=14.0, h=11.0):
    w = cells * cell
    mb.box((x0 + w / 2, y, PAD + 1), (w + 2, cell + 2, 2), M["concrete"])
    for i in range(cells):
        cx = x0 + cell * (i + 0.5)
        mb.box((cx, y, PAD + 2 + h / 2), (cell - 0.4, cell, h), M["ct_wall"])
        for s in (-1, 1):  # louvers
            for k in range(7):
                mb.box((cx, y + s * (cell / 2 + 0.25), PAD + 2.5 + k * 0.75), (cell - 1.2, 0.5, 0.12),
                       M["dark"], rotation=(s * 35, 0, 0))
        mb.rod((cx, y, PAD + 2 + h), (cx, y, PAD + 2 + h + 3.8), 5.2, M["ct_wall"], 48, caps=False)
        mb.torus((cx, y, PAD + 2 + h + 3.8), 5.2, 0.12, M["ct_wall"], 48, 4)
        mb.rod((cx, y, PAD + 2 + h + 0.4), (cx, y, PAD + 2 + h + 0.5), 5.0, M["fan"], 48)
        for k in range(8):
            a = k * math.pi / 4
            mb.box((cx + math.cos(a) * 2.3, y + math.sin(a) * 2.3, PAD + 2 + h + 0.7), (4.4, 0.6, 0.06),
                   M["dark"], rotation=(0, 6, math.degrees(a)))
    mb.railing([(x0, y - cell / 2, PAD + 2 + h), (x0 + w, y - cell / 2, PAD + 2 + h),
                (x0 + w, y + cell / 2, PAD + 2 + h), (x0, y + cell / 2, PAD + 2 + h)],
               M["yellow"], closed=True, post_step=3)
    mb.ladder((x0 - 0.7, y, PAD), h + 2, M["yellow"], facing=180)


def flare(mb, M, x, y, h=110.0):
    """Derrick-supported flare stack with a wind-blown flame."""
    legs = [(x + 8 * math.cos(a), y + 8 * math.sin(a)) for a in (0.3, 0.3 + 2.094, 0.3 + 4.189)]
    tops = [(x + 1.6 * math.cos(a), y + 1.6 * math.sin(a)) for a in (0.3, 0.3 + 2.094, 0.3 + 4.189)]
    def leg_at(i, t):
        (bx, by), (tx, ty) = legs[i], tops[i]
        return (bx + (tx - bx) * t, by + (ty - by) * t, PAD + (h - 4) * t)
    for i in range(3):
        mb.beam(leg_at(i, 0), leg_at(i, 1), 0.5, M["red"] if i == 0 else M["white"])
        mb.box((legs[i][0], legs[i][1], PAD + 0.4), (2.0, 2.0, 0.8), M["concrete"])
    levels = 11
    for k in range(levels):
        t0, t1 = k / levels, (k + 1) / levels
        for i in range(3):
            j = (i + 1) % 3
            mb.beam(leg_at(i, t1), leg_at(j, t1), 0.22, M["steel"])
            mb.beam(leg_at(i, t0), leg_at(j, t1), 0.18, M["steel"])
            mb.beam(leg_at(j, t0), leg_at(i, t1), 0.18, M["steel"])
    mb.rod((x, y, PAD), (x, y, PAD + h), 0.9, M["pipe_grey"], 24)
    mb.rod((x, y, PAD + h), (x, y, PAD + h + 3), 1.25, M["dark"], 24)
    mb.ring_platform((x, y, PAD + h - 4), 1.0, 3.2, M["grating"], M["yellow"], 32)
    tip = Vector((x, y, PAD + h + 3))
    wind = Vector((0.55, 0.25, 1.0)).normalized()
    mb.rod(tip, tip + wind * 16, 2.6, M["flame_o"], 24, radius_b=0.3)
    mb.rod(tip + wind * 0.5, tip + wind * 10, 1.5, M["flame_i"], 24, radius_b=0.2)
    mb.sphere(tip + wind * 1.5, 1.9, M["flame_i"], 2)
    for i in range(3):
        mb.sphere(leg_at(i, 0.98), 0.35, M["warn"], 1)
    # Knock-out drum and header running to the flare.
    drum(mb, M, (x - 3, y + 26, PAD + 3.2), 2.2, 14, "y", "pipe_grey")
    mb.pipe([(x - 3, y + 18, PAD + 3.2), (x - 3, y + 3, PAD + 3.2), (x, y, PAD + 6)], 0.7, M["pipe_grey"], 16)


# ------------------------------------------------------------------ infill equipment kits

class Occupancy:
    """Footprints of placed equipment, so infill kits only go where there's room."""

    def __init__(self):
        self.rects = []

    def add(self, x0, y0, x1, y1, margin=3.0):
        self.rects.append((min(x0, x1) - margin, min(y0, y1) - margin,
                           max(x0, x1) + margin, max(y0, y1) + margin))

    def around(self, x, y, r, margin=3.0):
        self.add(x - r, y - r, x + r, y + r, margin)

    def free(self, x0, y0, x1, y1):
        return not any(a < x1 and x0 < c and b < y1 and y0 < d for a, b, c, d in self.rects)


def kit_prefabs(M):
    """Eight reusable ~10 m equipment modules, each built once and instanced across the plant."""
    kits = []
    z = PAD

    mb = MeshBuilder("Kit_PumpSkid")
    mb.slab(-4, -2, 4, 2, z + 0.3, 0.3, M["concrete"])
    for i, px in enumerate((-2.6, 0, 2.6)):
        mb.rod((px - 0.9, 0, z + 0.85), (px + 0.3, 0, z + 0.85), 0.38, M["green_pipe"], 16)
        mb.sphere((px + 0.75, 0, z + 0.85), 0.5, M["pipe_grey"], 2)
        mb.pipe([(px + 0.75, 0, z + 1.3), (px + 0.75, 0, z + 4.2), (px + 0.75, 1.2, z + 4.2)], 0.15,
                M["pipe_grey"], 10)
        mb.pipe([(px + 1.3, 0, z + 0.85), (px + 1.8, 0, z + 0.85), (px + 1.8, -1.2, z + 3.4)], 0.12,
                M["pipe_yellow"], 10)
    mb.rod((-3.5, 1.2, z + 4.2), (4, 1.2, z + 4.2), 0.3, M["pipe_grey"], 14)
    for px in (-3.5, 0, 3.5):
        mb.beam((px, 1.2, z), (px, 1.2, z + 3.9), 0.2, M["steel"])
    kits.append(prefab(mb.build()))

    mb = MeshBuilder("Kit_Exchangers")
    for k, zz in enumerate((1.6, 3.4)):
        mb.rod((-3.5, 0, z + zz), (3.5, 0, z + zz), 0.8, M["pipe_silver"] if k else M["clad"], 32, caps=False)
        mb.sphere((-3.5, 0, z + zz), 0.85, M["green_pipe"], 2, (0.6, 1, 1))
        mb.sphere((3.5, 0, z + zz), 0.8, M["pipe_silver"], 2, (0.4, 1, 1))
        mb.rod((-2.5, 0, z + zz + 0.8), (-2.5, 0, z + 6.0), 0.22, M["pipe_grey"], 12)
        mb.rod((2.5, 0, z + zz - 0.8 if not k else z + zz + 0.8), (2.5, 0, z + 6.0), 0.22, M["pipe_brown"], 12)
    for px in (-2.4, 2.4):
        mb.box((px, 0, z + 1.2), (0.5, 1.6, 2.4), M["concrete"])
        mb.beam((px, -0.9, z + 2.4), (px, -0.9, z + 4.4), 0.18, M["steel"])
        mb.beam((px, 0.9, z + 2.4), (px, 0.9, z + 4.4), 0.18, M["steel"])
    mb.rod((-4, 0, z + 6.0), (4, 0, z + 6.0), 0.3, M["pipe_grey"], 12)
    kits.append(prefab(mb.build()))

    mb = MeshBuilder("Kit_VesselPair")
    vessel(mb, M, -2.0, 0, 1.3, 12, z0=z, skirt=2, platform_every=5.5, ladder_angle=180, seg=20)
    vessel(mb, M, 2.4, 0.5, 0.9, 8, z0=z, skirt=1.5, platform_every=99, ladder_angle=0, seg=16)
    mb.pipe([(-2.0 + 1.3, 0, z + 9), (0.6, 0, z + 9), (0.6, 0.5, z + 6), (2.4 - 0.9, 0.5, z + 6)], 0.2,
            M["pipe_grey"], 10)
    kits.append(prefab(mb.build()))

    mb = MeshBuilder("Kit_MiniFrame")
    steel_frame(mb, M, -5, -3.5, 5, 3.5, z, [5, 10], floors=[5, 10], brace=True)
    drum(mb, M, (0, 0, z + 10 + 1.6), 1.0, 7, "x", "pipe_silver", saddle_h=0.3)
    drum(mb, M, (0, 0, z + 5 + 1.4), 0.8, 6, "x", "clad", saddle_h=0.3)
    kits.append(prefab(mb.build()))

    mb = MeshBuilder("Kit_Substation")
    mb.box((0, 0, z + 2.6), (12, 7, 5.2), M["building"])
    mb.box((0, 0, z + 5.35), (12.4, 7.4, 0.3), M["roof"])
    mb.box((-3, -3.52, z + 1.1), (1.6, 0.1, 2.2), M["dark"])
    for k in range(3):
        mb.box((-3 + k * 3, 1.5, z + 5.9), (1.8, 1.4, 0.9), M["pipe_grey"])
    mb.rod((5, 0, z + 5.5), (5, 0, z + 8), 0.08, M["steel"], 6)
    kits.append(prefab(mb.build()))

    mb = MeshBuilder("Kit_DayTanks")
    for px in (-2.8, 2.8):
        mb.cylinder((px, 0, z), 2.4, 6, M["tank"], 40)
        mb.dome((px, 0, z + 6), 2.4, 0.5, M["tank_roof"], 40, 4)
        mb.ladder((px + 2.9, 0, z), 6, M["yellow"])
    mb.railing([(-5.8, -3, z), (5.8, -3, z), (5.8, 3, z), (-5.8, 3, z)], M["concrete"], height=0.8,
               post_step=3, closed=True)
    mb.pipe([(-2.8, -2.4, z + 0.7), (-2.8, -3.6, z + 0.7), (2.8, -3.6, z + 0.7), (2.8, -2.4, z + 0.7)], 0.18,
            M["pipe_grey"], 10)
    kits.append(prefab(mb.build()))

    mb = MeshBuilder("Kit_ExchangerBank")
    for k in range(4):
        y = -3 + k * 2
        mb.rod((-4, y, z + 1.4), (4, y, z + 1.4), 0.7, M["pipe_silver"], 28, caps=False)
        mb.sphere((-4, y, z + 1.4), 0.75, M["green_pipe"], 2, (0.6, 1, 1))
        mb.sphere((4, y, z + 1.4), 0.7, M["pipe_silver"], 2, (0.4, 1, 1))
        for px in (-2.5, 2.5):
            mb.box((px, y, z + 0.5), (0.4, 1.2, 1.0), M["concrete"])
        mb.pipe([(-3, y, z + 2.1), (-3, y, z + 5.5), (-3, 4, z + 5.5)], 0.18, M["pipe_brown"], 10)
    mb.rod((-3, -4, z + 5.5), (-3, 4.5, z + 5.5), 0.3, M["pipe_brown"], 12)
    mb.beam((-3, 4.5, z), (-3, 4.5, z + 5.3), 0.25, M["steel"])
    kits.append(prefab(mb.build()))

    mb = MeshBuilder("Kit_Column")
    vessel(mb, M, 0, 0, 1.6, 24, z0=z, skirt=2.5, platform_every=7, ladder_angle=90, seg=20)
    drum(mb, M, (0, -4.5, z + 2.0), 0.9, 5, "x", "pipe_silver", saddle_h=0.8)
    mb.pipe([(0, -1.6, z + 22), (0, -4.5, z + 22), (0, -4.5, z + 2.9)], 0.25, M["pipe_silver"], 12)
    kits.append(prefab(mb.build()))
    return kits


def fill(occ, rng, kits, pad, cell=13.0, chance=0.85, tag="Kit"):
    x0, y0, x1, y1 = pad
    nx, ny = int((x1 - x0) // cell), int((y1 - y0) // cell)
    placed = 0
    for i in range(nx):
        for j in range(ny):
            cx = x0 + (i + 0.5) * (x1 - x0) / nx
            cy = y0 + (j + 0.5) * (y1 - y0) / ny
            h = cell / 2 - 0.5
            if not occ.free(cx - h, cy - h, cx + h, cy + h) or rng.random() > chance:
                continue
            kit = rng.choice(kits)
            instance(kit, f"{tag}.{placed}", (cx, cy, 0), (0, 0, rng.choice((0, 90, 180, 270))),
                     collection="Infill")
            occ.add(cx - h, cy - h, cx + h, cy + h, 0)
            placed += 1
    return placed


# ------------------------------------------------------------------ vehicles, ships, trees

def car_prefab(M, name, color):
    paint = material(f"car_{name}", color, roughness=0.3, metallic=0.6)
    mb = MeshBuilder(f"Car_{name}")
    mb.box((0, 0, 0.6), (4.4, 1.8, 0.75), paint)
    mb.box((-0.2, 0, 1.2), (2.4, 1.6, 0.55), M["glass"])
    for sx in (-1.4, 1.4):
        for sy in (-0.85, 0.85):
            mb.rod((sx, sy - 0.12, 0.33), (sx, sy + 0.12, 0.33), 0.33, M["fan"], 12)
    return prefab(mb.build())


def truck_prefab(M):
    cab = material("truck_cab", "#c9d1d6", roughness=0.4, metallic=0.4)
    mb = MeshBuilder("TankerTruck")
    mb.box((5.4, 0, 1.9), (2.3, 2.5, 2.8), cab)
    mb.box((5.0, 0, 2.6), (0.1, 2.3, 1.0), M["glass"])
    mb.box((0, 0, 0.9), (13, 1.2, 0.35), M["dark"])
    mb.rod((-6.2, 0, 2.4), (4.0, 0, 2.4), 1.25, M["pipe_silver"], 32)
    mb.box((-1, 0, 3.7), (9, 0.6, 0.1), M["grating"])
    for wx in (-5.5, -4.2, -2.9, 3.0, 5.6):
        for wy in (-1.05, 1.05):
            mb.rod((wx, wy - 0.25, 0.5), (wx, wy + 0.25, 0.5), 0.5, M["fan"], 14)
    return prefab(mb.build())


def tree_prefab():
    bark = material("bark", "#5a4632", roughness=0.9)
    leaves = material("leaves", "#5f7a3c", roughness=0.85)
    mb = MeshBuilder("Tree")
    mb.rod((0, 0, 0), (0, 0, 3), 0.18, bark, 8)
    mb.sphere((0, 0, 4.2), 2.2, leaves, 2, (1, 1, 0.85))
    mb.sphere((0.6, 0.4, 5.3), 1.4, leaves, 1)
    return prefab(mb.build())
