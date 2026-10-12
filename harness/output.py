"""Render previews, export glTF, collect stats."""

import math
import os

import bpy
from mathutils import Vector

from .core import STATE, bounds, rgb


def to_gltf(v):
    """Blender Z-up (x, y, z) -> glTF/three.js Y-up (x, z, -y)."""
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


def ensure_defaults():
    """Fill in sun, sky and camera if the world didn't set them."""
    from .env import camera, sky, sun
    if STATE.get("sun") is None:
        sun()
    if STATE.get("sky") is None:
        sky()
    _sky_gradient()
    if STATE.get("camera") is None:
        lo, hi = bounds()
        center = (lo + hi) / 2
        radius = max((hi - lo).length / 2, 1.0)
        camera(center + Vector((radius * 1.1, -radius * 1.4, radius * 0.9)), center)


def _sky_gradient():
    """Blend the world background from the fog/horizon color up to the sky color, like the viewer."""
    sky_state, fog = STATE["sky"], STATE.get("fog") or {}
    horizon = fog.get("color") or sky_state["color"]
    nt = bpy.context.scene.world.node_tree
    if "SkyRamp" in nt.nodes:
        return
    coords = nt.nodes.new("ShaderNodeTexCoord")
    xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.name = "SkyRamp"
    ramp.color_ramp.interpolation = "EASE"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = rgb(horizon)
    ramp.color_ramp.elements[1].position = 0.3
    ramp.color_ramp.elements[1].color = rgb(sky_state["color"])
    nt.links.new(coords.outputs["Generated"], xyz.inputs[0])
    nt.links.new(xyz.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Background"].inputs["Color"])


def render(path, resolution=(1280, 720), samples=24, camera=None):
    """Cycles CPU render (works headless with no GPU). Writes JPEG unless path ends in .png."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 4
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    is_png = path.lower().endswith(".png")
    scene.render.image_settings.file_format = "PNG" if is_png else "JPEG"
    if not is_png:
        scene.render.image_settings.quality = 88
    previous = scene.camera
    if camera is not None:
        scene.camera = camera
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
    scene.camera = previous
    return path


def top_camera():
    """Orthographic camera looking straight down over the whole scene, for layout checks."""
    lo, hi = bounds()
    center = (lo + hi) / 2
    cam = bpy.data.cameras.new("_TopCam")
    cam.type = "ORTHO"
    cam.ortho_scale = max(hi.x - lo.x, hi.y - lo.y) * 1.05 or 10
    cam.clip_end = 10000
    obj = bpy.data.objects.new("_TopCam", cam)
    obj.location = (center.x, center.y, hi.z + 100)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def export_glb(path, draco=False):
    """Export the visible scene (meshes + materials) as a binary glTF for the web app.

    draco=True compresses meshes (typically 5-10x smaller; the viewer decodes it). Positions are
    quantized to 20 bits so fine detail like ladder rungs survives on kilometer-wide meshes.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # Objects the viewer replaces with its own version (e.g. the ocean) stay out of the .glb.
    replaced = [o for o in bpy.context.scene.objects if o.get("viewer")]
    for o in replaced:
        o.hide_set(True)
    opts = dict(
        filepath=os.path.abspath(path),
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_cameras=False,
        export_lights=False,  # the viewer lights the scene from meta.json instead
        export_extras=True,
        use_visible=True,
    )
    if draco:
        opts.update(export_draco_mesh_compression_enable=True,
                    export_draco_mesh_compression_level=7,
                    export_draco_position_quantization=20,
                    export_draco_normal_quantization=10)
    bpy.ops.export_scene.gltf(**opts)
    for o in replaced:
        o.hide_set(False)
    return path


def save_blend(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
    return path


def stats():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    unique = {o.data.name: o.data for o in meshes}
    def tris(me):
        return sum(len(p.vertices) - 2 for p in me.polygons)
    lo, hi = bounds()
    return {
        "objects": len(meshes),
        "unique_meshes": len(unique),
        "triangles_drawn": sum(tris(o.data) for o in meshes),
        "triangles_stored": sum(tris(m) for m in unique.values()),
        "materials": len({m.name for o in meshes for m in o.data.materials if m}),
        "bounds_min": [round(c, 2) for c in lo],
        "bounds_max": [round(c, 2) for c in hi],
    }


def viewer_meta():
    """Everything the web viewer needs that isn't in the .glb, in Y-up coordinates."""
    lo, hi = bounds()
    cam = STATE["camera"]
    sky = STATE["sky"]
    fog = STATE.get("fog")
    size = (hi - lo).length
    return {
        "camera": {
            "position": to_gltf(cam["location"]),
            "target": to_gltf(cam["target"]),
            "fov": round(math.degrees(2 * math.atan(18 / cam["lens"] / (16 / 9))), 2),
        },
        "sun": {**STATE["sun"], "direction": to_gltf(STATE["sun"]["direction"])},
        "sky": sky,
        "fog": {"color": (fog or {}).get("color") or sky["color"],
                "near": (fog or {}).get("near", size * 0.6),
                "far": (fog or {}).get("far", size * 2.5)},
        "bounds": {"min": to_gltf((lo.x, hi.y, lo.z)), "max": to_gltf((hi.x, lo.y, hi.z))},
        "ocean": STATE.get("ocean"),
    }
