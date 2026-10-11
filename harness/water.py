"""Ocean: an FFT ocean in the Blender render, a live Gerstner-wave ocean in the web viewer.

The two are matched in spirit (wave height, direction, color), not vertex-for-vertex.
"""

import math

import bpy

from .core import STATE, _place, hex_of, material

# Longest wavelength (m), total steepness (0..1, higher = choppier), Blender ocean wave scale.
PRESETS = {
    "calm": (22.0, 0.45, 0.6),
    "moderate": (48.0, 0.75, 1.6),
    "rough": (90.0, 0.95, 3.5),
}
# Spectrum shape shared by every preset: relative wavelength, share of steepness, angle off wind.
_SPECTRUM = [(1.0, 0.26, 0), (0.63, 0.20, 24), (0.41, 0.16, -33), (0.27, 0.12, 51),
             (0.18, 0.10, -14), (0.12, 0.07, 72), (0.08, 0.05, -58), (0.05, 0.04, 17)]


def ocean(level=0.0, waves="moderate", wind=45.0, color="#0a3550", shallow="#2a9d9a",
          foam=0.6, clarity=1.0, size=1600.0, render_detail=12):
    """Add an ocean at height `level`.

    waves:   'calm' | 'moderate' | 'rough'.
    wind:    direction the waves travel toward, in degrees (0 = +Y/north, 90 = +X/east).
    color:   deep water color; shallow: color over sand and in back-lit wave crests.
    foam:    0..1 whitecaps and shoreline foam in the viewer.
    clarity: how far you can see into the water (1 = clear tropical, 0.3 = murky).
    size:    extent of the rendered ocean in the Blender preview (viewer ocean is endless).
    """
    longest, steepness, blender_scale = PRESETS[waves]
    wind_rad = math.radians(wind)
    gerstner = []
    for rel, share, angle in _SPECTRUM:
        a = wind_rad + math.radians(angle)
        # Blender (x, y) direction -> three.js (x, z) direction.
        gerstner.append({"wavelength": round(longest * rel, 3),
                         "steepness": round(steepness * share, 4),
                         "direction": [round(math.sin(a), 4), round(-math.cos(a), 4)]})

    water = material("ocean_water", color, roughness=0.04)
    me = bpy.data.meshes.new("Ocean")
    obj = bpy.data.objects.new("Ocean", me)
    obj["viewer"] = "ocean"       # the viewer replaces this object with its animated ocean
    obj["backdrop"] = True
    me.materials.append(water)
    _place(obj, (0, 0, level), (0, 0, 0), (1, 1, 1), None)

    tile = 200
    mod = obj.modifiers.new("Ocean", "OCEAN")
    mod.geometry_mode = "GENERATE"
    mod.spatial_size = tile
    mod.size = 1.0
    mod.repeat_x = mod.repeat_y = max(1, round(size / tile))
    mod.resolution = render_detail
    mod.viewport_resolution = 4
    mod.wave_scale = blender_scale
    mod.choppiness = 0.6 + steepness
    mod.wind_velocity = 10 + 15 * steepness
    mod.wave_direction = math.pi / 2 - wind_rad
    mod.wave_alignment = 0.4
    mod.use_normals = True
    obj.location.x -= tile * mod.repeat_x / 2
    obj.location.y -= tile * mod.repeat_y / 2

    STATE["ocean"] = {
        "level": level,
        "color": hex_of(color),
        "shallow": hex_of(shallow),
        "foam": foam,
        "clarity": clarity,
        "waves": gerstner,
    }
    return obj


def bob(obj, amount=1.0, draft=0.0):
    """Make an object float on the viewer's ocean. draft = how deep it sits (m)."""
    obj["bob"] = amount
    obj["draft"] = draft
    return obj
