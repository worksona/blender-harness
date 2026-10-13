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
    atmo = STATE.get("atmosphere")
    if atmo:
        from .atmosphere import LAMP_GAIN
        from .effects import apply_lamp_level
        apply_lamp_level(atmo["lamp_level"], LAMP_GAIN)
    else:
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
    # Glow around the sun (also below the horizon at dusk), like the viewer's sky model.
    sun = STATE["sun"]
    glow = sky_state.get("glow")
    glow = sun["strength"] * 0.25 if glow is None else glow
    glow_height = sky_state.get("glow_height") or 0.45   # sine of how high the glow reaches
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = sun["direction"]
    nt.links.new(coords.outputs["Generated"], dot.inputs[0])
    clamp = nt.nodes.new("ShaderNodeMath")
    clamp.operation = "MAXIMUM"
    clamp.inputs[1].default_value = 0.0
    nt.links.new(dot.outputs["Value"], clamp.inputs[0])
    lobe = nt.nodes.new("ShaderNodeMath")
    lobe.operation = "POWER"
    lobe.inputs[1].default_value = 2.0
    nt.links.new(clamp.outputs["Value"], lobe.inputs[0])
    hug = nt.nodes.new("ShaderNodeMapRange")   # strongest at the horizon, gone by ~25 degrees up
    hug.inputs["From Min"].default_value = 0.0
    hug.inputs["From Max"].default_value = glow_height
    hug.inputs["To Min"].default_value = 1.0
    hug.inputs["To Max"].default_value = 0.0
    nt.links.new(xyz.outputs["Z"], hug.inputs["Value"])
    banded = nt.nodes.new("ShaderNodeMath")
    banded.operation = "MULTIPLY"
    nt.links.new(lobe.outputs["Value"], banded.inputs[0])
    nt.links.new(hug.outputs["Result"], banded.inputs[1])
    lobe = banded
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "ADD"
    tint.inputs["B"].default_value = tuple(c * glow for c in rgb(sun["color"])[:3]) + (1.0,)
    nt.links.new(lobe.outputs["Value"], tint.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], tint.inputs["A"])
    nt.links.new(tint.outputs["Result"], nt.nodes["Background"].inputs["Color"])


def _compositor(glare=0.0, haze=None, grade=None):
    """Post effects via the Blender 5 node-group compositor.
    glare: bloom on bright lights. haze: (rgb, near, far) distance haze from the mist pass,
    matching the viewer's fog (used by atmosphere())."""
    scene = bpy.context.scene
    if glare <= 0 and not haze and not grade:
        scene.compositing_node_group = None
        return
    ng = bpy.data.node_groups.get("_Post") or bpy.data.node_groups.new("_Post", "CompositorNodeTree")
    ng.nodes.clear()
    if not ng.interface.items_tree:
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = ng.nodes.new("CompositorNodeRLayers")
    image = layers.outputs["Image"]
    if haze:
        # Haze from the depth pass (not the mist pass, which also fogs the sky background).
        color, near, far = haze
        scene.view_layers[0].use_pass_z = True
        depth = layers.outputs["Depth"]
        ramp = ng.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value = near
        ramp.inputs["From Max"].default_value = far
        ng.links.new(depth, ramp.inputs["Value"])
        curve = ng.nodes.new("ShaderNodeMath")
        curve.operation = "POWER"
        curve.inputs[1].default_value = 1.6
        ng.links.new(ramp.outputs["Result"], curve.inputs[0])
        is_geometry = ng.nodes.new("ShaderNodeMath")   # the sky has "infinite" depth: no haze on it
        is_geometry.operation = "LESS_THAN"
        is_geometry.inputs[1].default_value = 1e8
        ng.links.new(depth, is_geometry.inputs[0])
        factor = ng.nodes.new("ShaderNodeMath")
        factor.operation = "MULTIPLY"
        ng.links.new(curve.outputs["Value"], factor.inputs[0])
        ng.links.new(is_geometry.outputs["Value"], factor.inputs[1])
        mix = ng.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["B"].default_value = (*color, 1.0)
        ng.links.new(factor.outputs["Value"], mix.inputs["Factor"])
        ng.links.new(image, mix.inputs["A"])
        image = mix.outputs["Result"]
    if glare > 0:
        g = ng.nodes.new("CompositorNodeGlare")
        g.inputs["Type"].default_value = "Bloom"
        g.inputs["Threshold"].default_value = 1.0
        g.inputs["Strength"].default_value = glare
        g.inputs["Size"].default_value = 0.7
        ng.links.new(image, g.inputs["Image"])
        image = g.outputs["Image"]
    if grade and grade.get("gains"):  # per-channel colour balance (identical in the viewer)
        gains = ng.nodes.new("ShaderNodeMix")
        gains.data_type = "RGBA"
        gains.blend_type = "MULTIPLY"
        gains.inputs["Factor"].default_value = 1.0
        gains.inputs["B"].default_value = (*grade["gains"], 1.0)
        ng.links.new(image, gains.inputs["A"])
        image = gains.outputs["Result"]
    if grade and grade.get("saturation", 1.0) != 1.0:
        # Saturation only: the compositor runs before exposure, so a contrast curve here would
        # pivot on the wrong grey and crush dim (dusk, night) scenes to black.
        cc = ng.nodes.new("CompositorNodeColorCorrection")
        cc.inputs[2].default_value = grade["saturation"]   # master saturation
        ng.links.new(image, cc.inputs["Image"])
        image = cc.outputs["Image"]
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(image, out.inputs[0])
    scene.compositing_node_group = ng


def render(path, resolution=(1280, 720), samples=24, camera=None, look="None", view="AgX", glare=0.0,
           grade=None):
    """Cycles CPU render (works headless with no GPU). Writes JPEG unless path ends in .png.
    view: "AgX" (filmic, soft highlights) or "Standard" (camera-like, saturated, for photo matching).
    look: an AgX look such as "AgX - Punchy".
    glare: bloom strength around bright lights (0 = off); good for night scenes.
    grade: {"gains": [r, g, b], "saturation": s} photographic colour grade: per-channel colour
           balance (e.g. [0.75, 1, 1] for a cool teal look) and saturation. Applied in
           scene-linear in the compositor; the viewer applies exactly the same grade."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 4
    scene.cycles.volume_bounces = 2   # light bouncing inside steam/cloud volumes keeps them white
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = view
    scene.view_settings.look = look if view == "AgX" else "None"
    atmo = STATE.get("atmosphere")
    scene.view_settings.exposure = atmo["ev"] if atmo else 0.0
    haze = None
    if atmo:
        # Haze takes the colour of the sky near the horizon in the view direction (the same
        # sky model the viewer uses), in scene-linear units like the rest of the image.
        from mathutils import Vector
        from .atmosphere import haze_color
        cam = scene.camera
        view = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        fog = STATE["fog"]
        haze = (haze_color(tuple(view)), fog["near"], fog["far"])
    _compositor(glare, haze, grade)
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
        export_image_format="AUTO",   # keeps JPEG textures as JPEG inside the .glb
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


def side_by_side(left_path, right_path, out_path, height=600):
    """Write left | right as one JPEG, both scaled to `height` (reference photo vs render)."""
    import numpy as np

    halves = []
    for path in (left_path, right_path):
        img = bpy.data.images.load(os.path.abspath(path))
        w, h = img.size
        img.scale(max(1, round(w * height / h)), height)
        px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        halves.append(px.reshape(height, img.size[0], 4))
        bpy.data.images.remove(img)
    gap = np.ones((height, 8, 4), dtype=np.float32)
    combined = np.concatenate([halves[0], gap, halves[1]], axis=1)
    out = bpy.data.images.new("_compare", combined.shape[1], height)
    out.pixels.foreach_set(combined.ravel())
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    out.filepath_raw = os.path.abspath(out_path)
    out.file_format = "JPEG"
    out.save()
    bpy.data.images.remove(out)
    return out_path


def save_blend(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
    return path


def stats():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    images = {i.name: i for i in bpy.data.images if i.users and i.size[0]}
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
        "textures": len(images),
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
        "atmosphere": STATE.get("atmosphere"),
        # Lamps: [x, y, z, color, watts, ground-y-or-null] in viewer coordinates.
        "lamps": [to_gltf(l[:3]) + [l[3], l[4], l[5]] for l in STATE.get("lamps", [])],
        "plumes": [{**p, "base": to_gltf(p["base"]), "drift": [p["drift"][0], -p["drift"][1]]}
                   for p in STATE.get("plumes", [])],
        "interior": STATE.get("interior"),
        "twin": STATE.get("twin"),
    }
