"""Night lighting and steam.

lamp():  a real point light in the Blender render, plus a glowing bulb. In the web viewer it gets a
         halo and, when near the ground, a pool of light on the ground (lights are listed in meta.json).
plume(): volumetric steam in the Blender render; in the viewer an animated particle plume that rises,
         billows and drifts with the wind (the volume mesh itself is not exported).
"""

import math

import bpy  # noqa: I001  (before mathutils, required by the bpy module)
from mathutils import Vector

from .builder import MeshBuilder
from .core import STATE, _place, hex_of, instance, material, prefab, rgb

LAMP_COLORS = {
    "sodium": "#ffa64d",   # high-pressure sodium, the orange of most plant and road lighting
    "warm": "#ffd29a",
    "led": "#dce7ff",      # cool white floodlights
    "red": "#ff2a1a",      # aviation warning
}
_LIGHT_DATA = {}
_BULBS = {}
# Bulbs are tiny, so in the Blender render they need a very bright emission to register (and bloom)
# from far away. The viewer clamps emission and draws its own halos instead.
BULB_GLOW = 400.0
STEAM_GLOW = 0.0012   # steam self-light at full lamp level, on the atmosphere() lamp scale


def apply_lamp_level(level, gain=1.0):
    """Dim every lamp's light and bulb (0 = off, 1 = as placed). Used by atmosphere(), which also
    passes a gain that puts lamp watts on the same scale as its physical sun."""
    for data in _LIGHT_DATA.values():
        data.energy = data.get("base_energy", data.energy) * level * gain
    for (color_hex, _), obj in _BULBS.items():
        for mat in obj.data.materials:
            mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = BULB_GLOW * level
    # Steam glows from the plant lights below it, so its self-light follows the lamps too.
    for mat in _STEAM_MATS:
        mat.node_tree.nodes["SteamGlow"].outputs[0].default_value = (
            STEAM_GLOW * mat.get("glow", 1.0) * level * gain / 0.0015)


def _bulb(color_hex, radius):
    key = (color_hex, round(radius, 2))
    if key not in _BULBS:
        # Very bright so even sub-pixel bulbs register (and bloom) in distant views.
        mat = material(f"bulb_{color_hex.lstrip('#')}", color_hex, emission=color_hex, emission_strength=BULB_GLOW)
        mb = MeshBuilder(f"Bulb_{color_hex.lstrip('#')}_{radius:.2f}")
        mb.sphere((0, 0, 0), radius, mat, 1)
        _BULBS[key] = prefab(mb.build())
    return _BULBS[key]


def lamp(location, color="sodium", power=4000.0, bulb=0.35, pool_z=None, light=True,
         collection="Lamps", viewer=True):
    """Point light at `location`. power in watts (Blender units). pool_z: height of the ground
    under it, which gives the viewer a pool of light there (omit for lights high on structures).
    light=False: bulb and viewer halo only, no real light (distant sparkle lights).
    viewer=False: Blender only (for lights the viewer animates itself, such as fire)."""
    c = hex_of(LAMP_COLORS.get(color, color))
    obj = None
    if light:
        key = (c, round(power))
        if key not in _LIGHT_DATA:  # lamps of one color and power share their light data
            data = bpy.data.lights.new(f"Lamp_{c.lstrip('#')}_{round(power)}", "POINT")
            data.energy = power
            data.color = rgb(c)[:3]
            data.shadow_soft_size = 0.5
            data["base_energy"] = power
            _LIGHT_DATA[key] = data
        obj = bpy.data.objects.new("Lamp", _LIGHT_DATA[key])
        # Lamps don't light steam volumes directly (the steam's own glow stands in for them):
        # with thousands of lamps, volume light sampling would multiply render times.
        obj.visible_volume_scatter = False
        _place(obj, location, (0, 0, 0), (1, 1, 1), collection)
    if bulb:
        instance(_bulb(c, bulb), "Bulb", location, collection=collection)
    if viewer:
        STATE.setdefault("lamps", []).append(
            [round(location[0], 2), round(location[1], 2), round(location[2], 2), c, round(power),
             None if pool_z is None else round(pool_z, 2)])
    return obj


def lamps_along(points, spacing, height, color="sodium", power=4000.0, ground=0.0, offset=0.0):
    """Street/rack lighting: a pole-top lamp every `spacing` meters along a polyline."""
    pts = [Vector(p[:2]) for p in points]
    placed = []
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a)
        length = seg.length
        d = seg.normalized()
        side = Vector((-d.y, d.x)) * offset
        t = carry
        while t <= length:
            p = a + d * t + side
            placed.append(lamp((p.x, p.y, ground + height), color, power, pool_z=ground))
            t += spacing
        carry = t - length
    return placed


_STEAM_MATS = []
WIDEN = 5.5   # how much wider a plume is at the top than at its source, in source radii


def _steam_material(name, height, radius, drift, density, glow=1.0, albedo=1.0):
    """Volume material for one plume. The plume's shape lives in the shader: density falls off
    with distance from the drifting centre-line (radius widening with height), fades in at the
    source and out at the top, and is broken up by noise. The mesh is just a container, so each
    plume is a single volume object (Blender precomputes a density grid per volume object, so
    hundreds of small puffs made renders take many minutes)."""
    mat = bpy.data.materials.new(f"steam_{name}")
    _STEAM_MATS.append(mat)
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def math(op, a, b=None, value=None):
        n = N("ShaderNodeMath")
        n.operation = op
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L(x, n.inputs[i])
        return n.outputs[0]

    def remap(x, a, b, c, d):
        n = N("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        n.clamp = True
        for key, v in (("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)):
            n.inputs[key].default_value = v
        L(x, n.inputs["Value"])
        return n.outputs["Result"]

    coords = N("ShaderNodeTexCoord").outputs["Object"]   # object origin = plume base
    xyz = N("ShaderNodeSeparateXYZ")
    L(coords, xyz.inputs[0])
    x, y, z = xyz.outputs["X"], xyz.outputs["Y"], xyz.outputs["Z"]
    t = math("MINIMUM", math("MAXIMUM", math("DIVIDE", z, height), 0.0), 1.0)
    tp = math("POWER", t, 1.4)
    ex = math("SUBTRACT", x, math("MULTIPLY", tp, drift[0] * height))
    ey = math("SUBTRACT", y, math("MULTIPLY", tp, drift[1] * height))
    dist = math("SQRT", math("ADD", math("MULTIPLY", ex, ex), math("MULTIPLY", ey, ey)))
    r = math("ADD", math("MULTIPLY", t, WIDEN * radius), 1.3 * radius)
    # Lumpy, cauliflower outline: large-scale noise pushes the edge in and out.
    lumps = N("ShaderNodeTexNoise")
    lumps.inputs["Scale"].default_value = 1.0 / (radius * 3.0)
    lumps.inputs["Detail"].default_value = 4.0
    L(coords, lumps.inputs["Vector"])
    edge = math("ADD", math("DIVIDE", dist, r), math("MULTIPLY", math("SUBTRACT", lumps.outputs["Fac"], 0.5), 1.1))
    shape = remap(edge, 0.2, 1.0, 1.0, 0.0)
    ends = math("MULTIPLY", remap(t, 0.0, 0.05, 0.0, 1.0), remap(t, 0.7, 1.0, 1.0, 0.0))
    noise = N("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0 / (radius * 1.2)
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Distortion"].default_value = 0.6
    L(coords, noise.inputs["Vector"])
    billow = remap(noise.outputs["Fac"], 0.3, 0.7, 0.25, 1.0)
    dens = math("MULTIPLY", math("MULTIPLY", math("MULTIPLY", shape, ends), billow), density)

    vol = N("ShaderNodeVolumePrincipled")
    # albedo < 1 makes smoke: the Principled Volume absorbs what it doesn't scatter.
    vol.inputs["Color"].default_value = (albedo, albedo, albedo, 1)
    vol.inputs["Anisotropy"].default_value = 0.5
    # Steam over a plant glows: a little warm self-light stands in for all the lamps below it.
    vol.inputs["Emission Color"].default_value = (1.0, 0.72, 0.45, 1)
    # Emission isn't scaled by density in the Principled Volume, so scale it here; otherwise
    # the whole (invisible) container glows. "SteamGlow" is set by apply_lamp_level().
    level = N("ShaderNodeValue")
    level.name = "SteamGlow"
    level.outputs[0].default_value = 0.08
    mat["glow"] = glow
    L(math("MULTIPLY", math("DIVIDE", dens, density), level.outputs[0]), vol.inputs["Emission Strength"])
    L(dens, vol.inputs["Density"])
    out = N("ShaderNodeOutputMaterial")
    L(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def plume(base, height=100.0, radius=6.0, drift=(0.5, 0.15), density=0.35, rise=4.0,
          low="#ffd7a8", high="#9aaabb", seed=0, glow=1.0, albedo=1.0, name="Plume"):
    """Steam plume rising from `base` (x, y, z).

    drift:  horizontal travel per meter of rise (x, y), i.e. the wind.
    rise:   rise speed in m/s in the viewer animation.
    glow:   how strongly the plant's lights glow up into the steam at night (1 = default).
    albedo: 1 = white steam; ~0.05 = black oily smoke (absorbs light instead of scattering it).
    low/high: colour near the source (usually lit by the plant) and up high (sky-lit).
    """
    bx, by, bz = base
    mat = _steam_material(f"{name}_{seed}", height, radius, drift, density, glow, albedo)
    # Container: a closed tapered tube that follows the drifting plume, a bit wider than it.
    mb = MeshBuilder(name)
    bm, idx = mb.bm, mb._mat_index(mat)
    rings, seg = 18, 16
    loops = []
    for k in range(rings + 1):
        t = -0.03 + 1.06 * k / rings
        tc = max(t, 0.0)
        cx, cy = drift[0] * height * tc ** 1.4, drift[1] * height * tc ** 1.4
        r = radius * (1.3 + WIDEN * tc) * 1.7 + 1.0   # roomy: the lumpy edge can bulge out
        loops.append([bm.verts.new((cx + r * math.cos(2 * math.pi * j / seg),
                                    cy + r * math.sin(2 * math.pi * j / seg), height * t))
                      for j in range(seg)])
    faces = [bm.faces.new(list(reversed(loops[0]))), bm.faces.new(loops[-1])]
    for a, b in zip(loops, loops[1:]):
        faces += [bm.faces.new((a[j], a[(j + 1) % seg], b[(j + 1) % seg], b[j])) for j in range(seg)]
    for f in faces:
        f.material_index = idx
    obj = mb.build(location=(bx, by, bz), collection="Steam")
    obj["viewer"] = "plume"   # the viewer animates its own particle plume instead
    obj["backdrop"] = True
    STATE.setdefault("plumes", []).append({
        "base": [round(bx, 2), round(by, 2), round(bz, 2)], "height": height, "radius": radius,
        "drift": [drift[0], drift[1]], "density": density, "rise": rise,
        "low": hex_of(low), "high": hex_of(high), "seed": seed, "glow": glow, "albedo": albedo,
    })
    return obj


def _fire_material(name, height, radius, brightness, core, edge_col, flash_dir=None):
    """Emission-only volume shaped like a flame (or, with flash_dir, a muzzle blast): bright
    yellow-white near the base and the axis, deep orange at the ragged edges and tips."""
    mat = bpy.data.materials.new(f"fire_{name}")
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def m(op, a, b=None):
        n = N("ShaderNodeMath")
        n.operation = op
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L(x, n.inputs[i])
        return n.outputs[0]

    def remap(x, a, b, c, d):
        n = N("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        n.clamp = True
        for key, v in (("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)):
            n.inputs[key].default_value = v
        L(x, n.inputs["Value"])
        return n.outputs["Result"]

    coords = N("ShaderNodeTexCoord").outputs["Object"]
    xyz = N("ShaderNodeSeparateXYZ")
    L(coords, xyz.inputs[0])
    x, y, z = xyz.outputs["X"], xyz.outputs["Y"], xyz.outputs["Z"]
    # The container is built along local +Z for both kinds (a flash is rotated to its direction).
    t = m("MINIMUM", m("MAXIMUM", m("DIVIDE", z, height), 0.0), 1.0)
    dist = m("SQRT", m("ADD", m("MULTIPLY", x, x), m("MULTIPLY", y, y)))
    if flash_dir is None:   # flame: widest a little above the base, licking to a point
        r = m("MULTIPLY", m("POWER", m("SUBTRACT", 1.0, t), 0.8), radius)
        r = m("MULTIPLY", r, remap(t, 0.0, 0.12, 0.7, 1.0))
    else:                   # muzzle blast: a fat bulb near the muzzle that narrows to a spike
        r = m("MULTIPLY", m("ADD", m("MULTIPLY", m("POWER", m("SUBTRACT", 1.0, t), 2.0), 0.85), 0.15), radius)
    def noise(scale, detail, stretch_z, rough=0.6, distortion=0.8):
        n = N("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        st = N("ShaderNodeVectorMath")
        st.operation = "MULTIPLY"
        st.inputs[1].default_value = (1.0, 1.0, stretch_z)
        L(coords, st.inputs[0])
        L(st.outputs[0], n.inputs["Vector"])
        return n.outputs["Fac"]
    # Big licking tongues (stretched upward) broken up by fine turbulence.
    tongues = noise(1.0 / max(radius * 0.5, 0.05), 6.0, 0.4)
    turb = noise(1.0 / max(radius * 0.16, 0.02), 4.0, 0.7, 0.7, 0.4)
    edge = m("ADD", m("DIVIDE", dist, m("MAXIMUM", r, 0.001)),
             m("ADD", m("MULTIPLY", m("SUBTRACT", tongues, 0.5), 2.4),
               m("MULTIPLY", m("SUBTRACT", turb, 0.5), 0.9)))
    shape = remap(edge, 0.55, 0.85, 1.0, 0.0)
    heat = m("MULTIPLY", shape, remap(t, 0.0, 0.04, 0.0, 1.0))
    heat = m("MULTIPLY", heat, remap(m("ADD", t, m("MULTIPLY", tongues, 0.35)), 0.5, 1.1, 1.0, 0.0))
    # Break up the inside too, so a thick fire isn't one solid glow: hot pockets and darker gaps.
    pockets = noise(1.0 / max(radius * 0.28, 0.03), 3.0, 0.6, 0.5, 0.3)
    heat = m("MULTIPLY", heat, remap(pockets, 0.3, 0.7, 0.2, 1.0))
    ramp = N("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = rgb(core)
    deep = cr.elements.new(0.2)
    deep.color = (0.35, 0.03, 0.0, 1)
    mid = cr.elements.new(0.6)
    mid.color = rgb(edge_col)
    L(heat, ramp.inputs["Fac"])
    emit = N("ShaderNodeEmission")
    L(ramp.outputs["Color"], emit.inputs["Color"])
    L(m("MULTIPLY", m("POWER", heat, 2.5), brightness), emit.inputs["Strength"])
    out = N("ShaderNodeOutputMaterial")
    L(emit.outputs[0], out.inputs["Volume"])
    return mat


def _volume_container(name, mat, height, radius, collection):
    """Closed cylinder from z=0 to z=height around the local Z axis, holding a volume material."""
    mb = MeshBuilder(name)
    mb.rod((0, 0, -0.02 * height), (0, 0, height * 1.02), radius * 1.6 + 0.05, mat, 16)
    return mb


def fire(base, radius=1.2, height=4.0, power=60000.0, brightness=12.0, color="#ff6a1a",
         core="#ffe2a0", seed=0, lights=2, name="Fire"):
    """Burning fire at `base` (x, y, z): an emissive flame volume and flickering-orange point
    lights in the Blender render; animated additive flame particles with a flickering light in
    the viewer. power: total light in Blender watts (on the same scale as lamp(), so it follows
    the atmosphere() lamp gain and the viewer's lamp switch)."""
    bx, by, bz = base
    mat = _fire_material(f"{name}_{seed}", height, radius, brightness, core, color)
    obj = _volume_container(name, mat, height, radius, "Fire").build(location=(bx, by, bz),
                                                                       collection="Fire")
    obj["viewer"] = "fire"
    obj["backdrop"] = True
    for k in range(lights):   # spread a little so the light wraps around what's burning
        a = 2 * math.pi * (k + 0.5 * seed) / max(1, lights)
        off = 0.35 * radius if lights > 1 else 0.0
        lt = lamp((bx + off * math.cos(a), by + off * math.sin(a), bz + height * 0.35), color,
                  power / lights, bulb=0, collection="Fire", viewer=False)
        lt.visible_volume_scatter = True   # firelight on the underside of its own smoke
    _soften_lights(color, power / lights, radius)
    STATE.setdefault("fires", []).append({
        "base": [round(bx, 2), round(by, 2), round(bz, 2)], "radius": radius, "height": height,
        "power": power, "color": hex_of(color), "core": hex_of(core), "seed": seed,
    })
    return obj


def muzzle_flash(muzzle, direction, length=2.4, radius=0.5, power=30000.0, brightness=40.0,
                 period=7.0, seed=0, color="#ff8a2a", core="#fff1c4", name="Flash"):
    """A gun firing: a blast of flame out of `muzzle` along `direction`, plus a bright light.
    The Blender render freezes the moment of firing; the viewer fires it every `period`
    seconds (staggered by seed): a short burst of flame and light."""
    d = Vector(direction).normalized()
    mat = _fire_material(f"{name}_{seed}", length, radius, brightness, core, color, flash_dir=d)
    rot = d.to_track_quat("Z", "Y").to_euler()
    obj = _volume_container(name, mat, length, radius, "Fire").build(
        location=muzzle, rotation=tuple(math.degrees(a) for a in rot), collection="Fire")
    obj["viewer"] = "flash"
    obj["backdrop"] = True
    c = Vector(muzzle) + d * length * 0.3
    lamp(tuple(c), color, power, bulb=0, collection="Fire", viewer=False)
    _soften_lights(color, power, radius)
    STATE.setdefault("fires", []).append({
        "base": [round(v, 2) for v in muzzle], "dir": [round(v, 3) for v in d], "radius": radius,
        "height": length, "power": power, "color": hex_of(color), "core": hex_of(core),
        "seed": seed, "period": period,
    })
    return obj


def _soften_lights(color, power, radius):
    data = _LIGHT_DATA.get((hex_of(LAMP_COLORS.get(color, color)), round(power)))
    if data:
        data.shadow_soft_size = max(0.3, radius * 0.6)


def snowfall(rate=1.0, size=0.025, speed=1.1, wind=(0.4, 0.15), area=60.0):
    """Falling snow in the viewer (particles around the view; nothing in the Blender render).
    rate: 0..2 density; wind: horizontal drift in m/s (x, y)."""
    STATE["snowfall"] = {"rate": rate, "size": size, "speed": speed, "wind": list(wind), "area": area}


def reset_effects():
    _LIGHT_DATA.clear()
    _BULBS.clear()
    _STEAM_MATS.clear()
