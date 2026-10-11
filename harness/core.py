"""Scene, material and mesh helpers. Blender is Z-up, units are meters, ground is z=0."""

import math

import bpy  # noqa: I001  (before bmesh/mathutils, required by the bpy module)
import bmesh
from mathutils import Matrix, Vector

# Things the viewer needs that glTF doesn't carry (sun, sky, fog, start camera).
STATE = {}


def reset():
    """Start from an empty scene. Called by the build tool before each world."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    STATE.clear()
    STATE.update(sun=None, sky=None, fog=None, camera=None, ocean=None)
    _MATERIALS.clear()


# ---------------------------------------------------------------- colors

def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(color):
    """'#rrggbb' or (r, g, b) in 0..1 sRGB -> linear RGBA tuple for Blender sockets."""
    if isinstance(color, str):
        s = color.lstrip("#")
        color = tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    r, g, b = (_srgb_to_linear(c) for c in color[:3])
    return (r, g, b, 1.0)


def hex_of(color):
    if isinstance(color, str):
        return "#" + color.lstrip("#").lower()
    return "#" + "".join(f"{round(c * 255):02x}" for c in color[:3])


# ---------------------------------------------------------------- materials

_MATERIALS = {}


def material(name, color="#cccccc", roughness=0.6, metallic=0.0,
             emission=None, emission_strength=1.0, alpha=1.0):
    """Principled BSDF material. Only these inputs survive glTF export, so stick to them."""
    if name in _MATERIALS:
        return _MATERIALS[name]
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgb(color)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = rgb(emission)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = "BLENDED"
    mat.diffuse_color = rgb(color)
    _MATERIALS[name] = mat
    return mat


# ---------------------------------------------------------------- objects

def collection(name):
    """Get or create a top-level collection (becomes a group node in glTF)."""
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _place(obj, location, rotation, scale, coll):
    obj.location = location
    obj.rotation_euler = [math.radians(a) for a in rotation]
    obj.scale = scale if isinstance(scale, (tuple, list)) else (scale,) * 3
    (coll if isinstance(coll, bpy.types.Collection) else
     collection(coll) if coll else bpy.context.scene.collection).objects.link(obj)
    return obj


def _from_bmesh(name, bm, mat, smooth, lift=0.0):
    if lift:
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, lift))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat is not None:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    return bpy.data.objects.new(name, me)


def box(name, size=(1, 1, 1), location=(0, 0, 0), rotation=(0, 0, 0), material=None,
        anchor="bottom", collection=None):
    """Box of `size` meters. anchor='bottom' puts the origin on the base face."""
    sx, sy, sz = size if isinstance(size, (tuple, list)) else (size,) * 3
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    obj = _from_bmesh(name, bm, material, False, sz / 2 if anchor == "bottom" else 0)
    return _place(obj, location, rotation, (1, 1, 1), collection)


def sphere(name, radius=1.0, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0, material=None,
           subdivisions=2, smooth=True, collection=None):
    """Icosphere centered on location. subdivisions 1 = faceted low-poly, 3 = smooth."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius)
    obj = _from_bmesh(name, bm, material, smooth)
    return _place(obj, location, rotation, scale, collection)


def cylinder(name, radius=0.5, height=1.0, location=(0, 0, 0), rotation=(0, 0, 0),
             radius_top=None, segments=16, material=None, smooth=False, anchor="bottom",
             collection=None):
    """Cylinder; set radius_top=0 for a cone. anchor='bottom' puts the origin on the base."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                          radius2=radius if radius_top is None else radius_top, depth=height)
    obj = _from_bmesh(name, bm, material, smooth, height / 2 if anchor == "bottom" else 0)
    return _place(obj, location, rotation, (1, 1, 1), collection)


def cone(name, radius=0.5, height=1.0, **kw):
    return cylinder(name, radius=radius, height=height, radius_top=0.0, **kw)


def plane(name, size=10.0, location=(0, 0, 0), rotation=(0, 0, 0), material=None,
          backdrop=False, collection=None):
    """Flat quad. backdrop=True (seas, endless ground) leaves it out of framing and shadow bounds."""
    sx, sy = size if isinstance(size, (tuple, list)) else (size, size)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
    obj = _from_bmesh(name, bm, material, False)
    if backdrop:
        obj["backdrop"] = True
    return _place(obj, location, rotation, (1, 1, 1), collection)


def mesh(name, verts, faces, material=None, location=(0, 0, 0), smooth=False, collection=None):
    """Raw mesh from vertex and face index lists."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # winding order doesn't matter
    bm.to_mesh(me)
    bm.free()
    if material is not None:
        me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = smooth
    return _place(bpy.data.objects.new(name, me), location, (0, 0, 0), (1, 1, 1), collection)


def join(name, parts, collection=None):
    """Merge objects into one mesh (keeps each part's material). Use for prefabs you'll instance."""
    bm = bmesh.new()
    mats = []
    for part in parts:
        part_bm = bmesh.new()
        part_bm.from_mesh(part.data)
        part_bm.transform(part.matrix_basis)
        offset = len(mats)
        mats.extend(part.data.materials)
        for f in part_bm.faces:
            f.material_index += offset
        tmp = bpy.data.meshes.new("_tmp")
        part_bm.to_mesh(tmp)
        part_bm.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for part in parts:
        old = part.data
        bpy.data.objects.remove(part)
        if old.users == 0:
            bpy.data.meshes.remove(old)
    return _place(bpy.data.objects.new(name, me), (0, 0, 0), (0, 0, 0), (1, 1, 1), collection)


def prefab(obj):
    """Hide a template object from render/export; place copies of it with instance()."""
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    obj.name = "_prefab_" + obj.name
    return obj


def instance(src, name=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0, collection=None):
    """Linked duplicate: shares mesh data with `src`, so 500 trees cost one tree in the .glb."""
    obj = bpy.data.objects.new(name or src.name.replace("_prefab_", ""), src.data)
    return _place(obj, location, rotation, scale, collection)


def bounds(objects=None):
    """World-space (min, max) Vectors over the scene's meshes, ignoring backdrop objects."""
    objs = objects or [o for o in bpy.context.scene.objects
                       if o.type == "MESH" and not o.get("backdrop")]
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in objs:
        for corner in o.bound_box:
            p = o.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    if lo.x == math.inf:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return lo, hi


def look_at_matrix(location, target):
    direction = Vector(target) - Vector(location)
    rot = direction.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation(location) @ rot
