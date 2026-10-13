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


def sky(color="#9cc7f0", strength=1.0, ground="#6b7a5a", glow=None, glow_height=None):
    """Sky light / background. `ground` tints the viewer's hemisphere fill light.
    glow: brightness of the glow around the sun (defaults to sun strength x 0.25); raise it for
    dusk and dawn skies, where the sun is below the horizon but the sky is still on fire.
    glow_height: how far up the glow reaches (sine of the angle; 0.1 = a thin band on the horizon)."""
    world = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = world
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = rgb(color)
    bg.inputs["Strength"].default_value = strength
    STATE["sky"] = {"color": hex_of(color), "ground": hex_of(ground), "strength": strength,
                    "glow": glow, "glow_height": glow_height}
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


def interior(key_direction=(0.25, -0.35, 1.0), key=2.2, key_color="#fff6ea", sky="#eef2f7",
             ground="#a59680", ambient=0.9, env=0.6, exposure=1.0):
    """Viewer lighting for indoor worlds (the Blender render uses the world's own lights).

    The viewer's directional light becomes an overhead key, like rows of high-bay fixtures:
    key_direction points from the scene toward the light (Blender coordinates). Objects marked
    obj["no_cast"] = True (roofs, ceilings, upper walls) don't block it. A neutral room
    environment gives metal and paint their reflections, and a hemisphere fill (sky from above,
    `ground` bounced up from the floor) lifts the shadows. If the viewer's Light panel switches to
    the physical sun, the roof casts shadows again so daylight only enters through openings."""
    from .output import to_gltf
    d = Vector(key_direction).normalized()
    STATE["interior"] = {"key_dir": to_gltf(d), "key": key, "key_color": hex_of(key_color),
                         "sky": hex_of(sky), "ground": hex_of(ground), "ambient": ambient,
                         "env": env, "exposure": exposure}


def photo_camera(photo, location, target, focal_35mm=26.0, roll=0.0, shift=(0.0, 0.0), size=(4, 3)):
    """A camera matched to a reference photo in worlds/<slug>/reference/. Every build renders it
    and writes build/<slug>/compare-<photo name>.jpg (photo left, render right).

    focal_35mm: the photo's 35 mm-equivalent focal length (EXIF FocalLengthIn35mmFormat; phones
    put it there). size: the photo's aspect (w, h). roll: degrees, positive turns the image
    clockwise. shift: lens shift in fractions of the frame width (x) / height (y)."""
    w, h = size
    frame_w = 43.27 * w / math.hypot(w, h)            # 35 mm equivalence is by the diagonal
    cam = bpy.data.cameras.new(f"Ref_{photo}")
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = 36.0
    cam.lens = focal_35mm * 36.0 / frame_w
    cam.shift_x, cam.shift_y = shift
    cam.clip_start, cam.clip_end = 0.05, 5000
    obj = bpy.data.objects.new(f"Ref_{photo}", cam)
    m = look_at_matrix(Vector(location), Vector(target))
    from mathutils import Matrix
    obj.matrix_world = m @ Matrix.Rotation(math.radians(-roll), 4, "Z")
    bpy.context.scene.collection.objects.link(obj)
    STATE.setdefault("ref_views", []).append({"photo": photo, "camera": obj.name, "size": [w, h]})
    return obj
