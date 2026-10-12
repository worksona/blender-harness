"""Night lighting and steam.

lamp():  a real point light in the Blender render, plus a glowing bulb. In the web viewer it gets a
         halo and, when near the ground, a pool of light on the ground (lights are listed in meta.json).
plume(): volumetric steam in the Blender render; in the viewer an animated particle plume that rises,
         billows and drifts with the wind (the volume mesh itself is not exported).
"""

import math
import random

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
    for obj in _PUFFS.values():
        for mat in obj.data.materials:
            vol = mat.node_tree.nodes["Principled Volume"]
            vol.inputs["Emission Strength"].default_value = STEAM_GLOW * level * gain / 0.0015


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
         collection="Lamps"):
    """Point light at `location`. power in watts (Blender units). pool_z: height of the ground
    under it, which gives the viewer a pool of light there (omit for lights high on structures).
    light=False: bulb and viewer halo only, no real light (distant sparkle lights)."""
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


def _steam_material(density):
    """Volume material for one puff (a unit sphere scaled per puff): density fades from the
    puff's center to its edge, broken up by world-space noise so neighbouring puffs merge."""
    name = f"steam_{density:.3f}"
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
    vol.inputs["Anisotropy"].default_value = 0.5
    # Steam over a plant glows: a little warm self-light stands in for all the lamps below it.
    vol.inputs["Emission Color"].default_value = (1.0, 0.72, 0.45, 1)
    vol.inputs["Emission Strength"].default_value = 0.08
    coords = nt.nodes.new("ShaderNodeTexCoord")
    falloff = nt.nodes.new("ShaderNodeTexGradient")
    falloff.gradient_type = "SPHERICAL"
    nt.links.new(coords.outputs["Object"], falloff.inputs["Vector"])
    soft = nt.nodes.new("ShaderNodeMath")
    soft.operation = "POWER"
    soft.inputs[1].default_value = 1.6
    nt.links.new(falloff.outputs["Fac"], soft.inputs[0])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.09
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Distortion"].default_value = 0.5
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    shape = nt.nodes.new("ShaderNodeMapRange")
    shape.inputs["From Min"].default_value = 0.3
    shape.inputs["From Max"].default_value = 0.75
    nt.links.new(noise.outputs["Fac"], shape.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(soft.outputs["Value"], mul.inputs[0])
    nt.links.new(shape.outputs["Result"], mul.inputs[1])
    dens = nt.nodes.new("ShaderNodeMath")
    dens.operation = "MULTIPLY"
    dens.inputs[1].default_value = density
    nt.links.new(mul.outputs["Value"], dens.inputs[0])
    nt.links.new(dens.outputs["Value"], vol.inputs["Density"])
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


_PUFFS = {}


def _puff(density):
    if density not in _PUFFS:
        mb = MeshBuilder(f"SteamPuff_{density:.3f}")
        mb.sphere((0, 0, 0), 1.0, _steam_material(density), 2)
        _PUFFS[density] = prefab(mb.build())
    return _PUFFS[density]


def plume(base, height=100.0, radius=6.0, drift=(0.5, 0.15), density=0.35, rise=4.0,
          low="#ffd7a8", high="#9aaabb", seed=0, name="Plume"):
    """Steam plume rising from `base` (x, y, z).

    drift:  horizontal travel per meter of rise (x, y), i.e. the wind.
    rise:   rise speed in m/s in the viewer animation.
    low/high: colour near the source (usually lit by the plant) and up high (sky-lit).
    """
    bx, by, bz = base
    puff = _puff(round(density, 3))
    rnd = random.Random(seed)
    # Overlapping soft puffs along the drifting path: many small ones near the source, fewer
    # and bigger as the plume spreads.
    for k in range(int(14 + height / radius * 1.6)):
        t = rnd.random() ** 1.4
        r = radius * (1.2 + 3.4 * t) * rnd.uniform(0.75, 1.15)
        spread = radius * (0.25 + 1.4 * t)
        c = (bx + drift[0] * height * t ** 1.4 + rnd.uniform(-1, 1) * spread,
             by + drift[1] * height * t ** 1.4 + rnd.uniform(-1, 1) * spread * 0.6,
             bz + height * t + rnd.uniform(-0.4, 0.4) * radius)
        obj = instance(puff, f"{name}.{k}", c, (rnd.uniform(0, 360), rnd.uniform(0, 360), 0), r,
                       collection="Steam")
        obj["viewer"] = "plume"   # the viewer animates its own particle plume instead
        obj["backdrop"] = True
    STATE.setdefault("plumes", []).append({
        "base": [round(bx, 2), round(by, 2), round(bz, 2)], "height": height, "radius": radius,
        "drift": [drift[0], drift[1]], "density": density, "rise": rise,
        "low": hex_of(low), "high": hex_of(high), "seed": seed,
    })


def reset_effects():
    _LIGHT_DATA.clear()
    _BULBS.clear()
    _PUFFS.clear()
