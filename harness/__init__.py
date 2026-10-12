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
from .env import camera, fog, sky, sun
from .output import export_glb, render, save_blend, stats
from .terrain import fbm, island_falloff, scatter, slope, terrain
from .water import bob, ocean
from .atmosphere import atmosphere, solar_position


def reset():
    """Start from an empty scene (called by the build tool before each world)."""
    _reset_scene()
    reset_effects()


__all__ = [
    "MeshBuilder",
    "bounds", "box", "collection", "cone", "cylinder", "hex_of", "instance", "join", "material",
    "mesh", "plane", "prefab", "reset", "rgb", "sphere",
    "camera", "fog", "sky", "sun",
    "export_glb", "render", "save_blend", "stats",
    "fbm", "island_falloff", "scatter", "slope", "terrain",
    "bob", "ocean",
    "lamp", "lamps_along", "plume",
    "atmosphere", "solar_position",
]
