"""Lighting, sky, fog and camera. These drive both the Blender render and the web viewer."""

import math

import bpy
from mathutils import Euler, Vector

from .core import STATE, hex_of, look_at_matrix, rgb


def sun(elevation=45.0, azimuth=135.0, strength=4.0, color="#fff4e0", angle=1.0):
    """Directional light. elevation/azimuth in degrees (azimuth 0 = +Y/north, 90 = +X/east)."""
    light = bpy.data.lights.new("Sun", "SUN")
    light.energy = strength
    light.color = rgb(color)[:3]
    light.angle = math.radians(angle)
    obj = bpy.data.objects.new("Sun", light)
    # Rotate the light's -Z axis to point from the sun toward the ground.
    obj.rotation_euler = Euler((math.radians(90 - elevation), 0, math.radians(-azimuth + 180)))
    bpy.context.scene.collection.objects.link(obj)
    to_sun = -(obj.rotation_euler.to_matrix() @ Vector((0, 0, -1)))
    STATE["sun"] = {"direction": list(to_sun), "color": hex_of(color), "strength": strength}
    return obj


def sky(color="#9cc7f0", strength=1.0, ground="#6b7a5a"):
    """Uniform sky light / background. `ground` tints the viewer's hemisphere fill light."""
    world = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = world
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = rgb(color)
    bg.inputs["Strength"].default_value = strength
    STATE["sky"] = {"color": hex_of(color), "ground": hex_of(ground), "strength": strength}
    return world


def fog(color=None, near=50.0, far=400.0):
    """Distance fog in the web viewer (not rendered in Blender previews)."""
    STATE["fog"] = {"color": hex_of(color) if color else None, "near": near, "far": far}


def camera(location, target=(0, 0, 0), lens=30.0, name="Camera"):
    """Hero camera: used for the preview render and as the viewer's starting view."""
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_end = 5000
    obj = bpy.data.objects.new(name, cam)
    obj.matrix_world = look_at_matrix(Vector(location), Vector(target))
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.camera = obj
    STATE["camera"] = {"location": list(location), "target": list(target), "lens": lens}
    return obj
