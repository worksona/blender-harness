"""Blender world-building harness.

Worlds import everything from here:  `from harness import *`
"""

# bpy must be imported first: with the PyPI `bpy` module, bmesh/mathutils only exist after it.
import bpy  # noqa: F401

from .builder import MeshBuilder
from .core import (bounds, box, collection, cone, cylinder, hex_of, instance, join, material,
                   mesh, plane, prefab, rgb, sphere)
from .core import reset as _reset_scene
from .effects import lamp, lamps_along, plume, reset_effects
from .env import camera, fog, interior, photo_camera, sky, sun
from .output import export_glb, render, save_blend, stats
from .terrain import fbm, island_falloff, scatter, slope, terrain
from .water import bob, ocean
from .atmosphere import atmosphere, solar_position
from . import textures
from .textures import (blur, colorize, contrast, decal, fbm_noise, grime, height_normal,
                       make_tileable, photo_patch, text_atlas, text_image, text_mask, texture,
                       value_noise)
from .twin import twin_record, twin_series, twin_tag, twin_gauge
from .sim import person, preview_time, twin_actor, twin_flow, twin_motion, twin_state


def reset():
    """Start from an empty scene (called by the build tool before each world)."""
    _reset_scene()
    reset_effects()
    textures.reset()


__all__ = [
    "MeshBuilder",
    "bounds", "box", "collection", "cone", "cylinder", "hex_of", "instance", "join", "material",
    "mesh", "plane", "prefab", "reset", "rgb", "sphere",
    "camera", "fog", "interior", "photo_camera", "sky", "sun",
    "export_glb", "render", "save_blend", "stats",
    "fbm", "island_falloff", "scatter", "slope", "terrain",
    "bob", "ocean",
    "lamp", "lamps_along", "plume",
    "atmosphere", "solar_position",
    "textures", "blur", "colorize", "contrast", "decal", "fbm_noise", "grime", "height_normal",
    "make_tileable", "photo_patch", "text_atlas", "text_image", "text_mask", "texture", "value_noise",
    "twin_record", "twin_series", "twin_tag", "twin_gauge",
    "person", "preview_time", "twin_actor", "twin_flow", "twin_motion", "twin_state",
]
