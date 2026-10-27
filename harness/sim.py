"""Construction sim layer: material that moves, people who work, and document states that change,
all replayed on the twin's timeline in the web viewer.

Two clocks. The timeline (a `twin_series` with `clock=`) runs in days: trucks, spools and
document flows move in sim time, so a two-day shipment takes a couple of seconds of replay.
People walk in real seconds: an actor has shifts (sim-time windows) and in each shift a path it
patrols at walking pace, pausing at task points to weld, inspect or carry. Outside its shifts it
is not there.

    p = person("W1", vest="#f28a1a", location=(10, 5, 0))
    twin_actor(p, shifts=[dict(start=12, end=19, path=[(10, 5), (14, 5), (14, 9)],
                               tasks={1: (6, "weld")})])
    twin_motion(truck, keys=[(8.0, (-60, 80, 0), -90), (8.4, (-60, 20, 0), 0), (9.0, (130, 20, 0), 90)])
    twin_flow("Purchase order", office_door, vendor_door, 1.0, 2.0, color="#6cb6ff")
    twin_state("spool-1", [(0, "pending"), (8.4, "hold"), (12, "active"), (28, "ok"), (42, "done")])

The Blender render is a still: `preview_time(t)` places everything where it is at that moment.
"""

import math

import bpy
from mathutils import Vector

from .core import _place, instance, material, mesh, prefab
from .output import to_gltf
from .twin import _twin

PREVIEW_T = 0.0


def preview_time(t):
    """Sim time (days) the Blender render shows: moving things are posed there."""
    global PREVIEW_T
    PREVIEW_T = float(t)


# ---------------------------------------------------------------- people

_PARTS = {}


def _hang_box(name, sx, sy, length, mat, z0=0.0):
    """Box hanging below its origin (a limb: origin at the joint), from z0 down to z0 - length."""
    hx, hy = sx / 2, sy / 2
    v = [(-hx, -hy, z0 - length), (hx, -hy, z0 - length), (hx, hy, z0 - length), (-hx, hy, z0 - length),
         (-hx, -hy, z0), (hx, -hy, z0), (hx, hy, z0), (-hx, hy, z0)]
    f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return mesh(name, v, f, material=mat)


def _part_prefab(kind, color):
    """Shared mesh per (part, colour): every worker's left leg in blue jeans is one mesh."""
    key = (kind, color)
    if key in _PARTS:
        return _PARTS[key]
    mat = material(f"person_{kind}_{color.lstrip('#')}", color, roughness=0.85)
    name = f"Person_{kind}_{color.lstrip('#')}"
    if kind == "torso":        # hi-vis vest over the shirt, shoulders at 1.42 m
        obj = _hang_box(name, 0.26, 0.42, 0.58, mat, z0=1.44)
    elif kind == "head":
        obj = _hang_box(name, 0.2, 0.2, 0.22, mat, z0=1.68)
    elif kind == "helmet":
        from .builder import MeshBuilder
        mb = MeshBuilder(name)
        mb.dome((0, 0, 1.6), 0.135, 0.11, mat, segments=14, rings=4)
        mb.box((0.03, 0, 1.6), (0.32, 0.27, 0.02), mat)
        obj = mb.build()
    elif kind == "arm":
        obj = _hang_box(name, 0.1, 0.1, 0.64, mat)
    elif kind == "leg":
        obj = _hang_box(name, 0.14, 0.16, 0.86, mat)
    else:
        raise ValueError(kind)
    _PARTS[key] = prefab(obj)
    return _PARTS[key]


def person(name, vest="#f28a1a", shirt="#3b4a5a", pants="#2d3f6b", skin="#c99a73", helmet="#f2f2f2",
           location=(0, 0, 0), yaw=0.0, collection="People"):
    """A 1.8 m worker facing +X: an empty root with limb children whose origins sit at the joints,
    so the viewer can swing them. Parts are instanced, so a crew of 50 costs one set of meshes."""
    location = tuple(location) + (0.0,) * (3 - len(location))
    root = _place(bpy.data.objects.new(name, None), location, (0, 0, yaw), (1, 1, 1), collection)
    root.empty_display_size = 0.2
    root["actor"] = True
    parts = [("torso", vest, (0, 0, 0)), ("head", skin, (0, 0, 0)), ("helmet", helmet, (0, 0, 0)),
             ("arm_l", shirt, (0, 0.27, 1.42)), ("arm_r", shirt, (0, -0.27, 1.42)),
             ("leg_l", pants, (0, 0.1, 0.86)), ("leg_r", pants, (0, -0.1, 0.86))]
    for part, color, offset in parts:
        if color is None:                   # e.g. helmet=None for office staff
            continue
        kind = part.split("_")[0]
        obj = instance(_part_prefab(kind, color), f"{name}_{part}", location=offset, collection=collection)
        obj.parent = root
    return root


# ---------------------------------------------------------------- timeline hooks

def _sim():
    t = _twin()
    t.setdefault("motions", [])
    t.setdefault("actors", [])
    t.setdefault("flows", [])
    t.setdefault("states", {})
    return t


def _key_at(keys, t):
    """Position and yaw at sim time t from [(t, (x, y, z), yaw), ...] (held outside the keys)."""
    if t <= keys[0][0]:
        return keys[0][1], keys[0][2]
    for (ta, pa, ya), (tb, pb, yb) in zip(keys, keys[1:]):
        if t <= tb:
            f = (t - ta) / (tb - ta) if tb > ta else 1.0
            p = Vector(pa).lerp(Vector(pb), f)
            return p, ya + (yb - ya) * f
    return keys[-1][1], keys[-1][2]


def twin_motion(obj, keys, hide=True, until=None):
    """Move an object along keys [(t, (x, y, z), yaw_degrees), ...] in sim time. Between keys it
    travels in a straight line; before the first and after the last it stays put. hide=True keeps
    it invisible before its first key (a spool that doesn't exist yet); until=t hides it after t
    (a crate that has been unpacked). The object (and anything under it) stays its own mesh in
    the viewer, so give moving things their own prefab."""
    obj["motion"] = True
    p, yaw = _key_at(keys, PREVIEW_T)
    obj.location = p
    obj.rotation_euler = (0, 0, math.radians(yaw))
    if (hide and PREVIEW_T < keys[0][0]) or (until is not None and PREVIEW_T > until):
        obj.hide_render = True          # (viewport visibility would drop it from the export)
        for c in obj.children_recursive:
            c.hide_render = True
    _sim()["motions"].append({"node": obj.name, "hide": hide, "until": until,
                              "keys": [[round(float(t), 4), to_gltf(p), round(float(y), 2)] for t, p, y in keys]})
    return obj


def twin_actor(root, shifts, speed=1.1):
    """Animate a person() in the viewer. shifts: [{"start": t0, "end": t1, "path": [(x, y[, z]), ...],
    "tasks": {point_index: (seconds, kind)}, "loop": True}] in sim days; the path is walked in real
    time at `speed` m/s, pausing at task points (kinds: weld, inspect, carry, idle, talk).
    A one-point path is a person who stands there and does their task."""
    out = []
    for s in shifts:
        path = [Vector((p[0], p[1], p[2] if len(p) > 2 else 0.0)) for p in s["path"]]
        tasks = {str(k): [float(v[0]), v[1]] for k, v in (s.get("tasks") or {}).items()}
        out.append({"start": float(s["start"]), "end": float(s["end"]), "loop": s.get("loop", True),
                    "path": [to_gltf(p) for p in path], "tasks": tasks})
    # Pose for the render: at the first point of the shift active at the preview time.
    active = next((s for s in shifts if s["start"] <= PREVIEW_T < s["end"]), None)
    if active is None:
        root.hide_render = True
        for c in root.children_recursive:
            c.hide_render = True
    else:
        pts = [Vector((p[0], p[1], p[2] if len(p) > 2 else 0.0)) for p in active["path"]]
        root.location = pts[0]
        if len(pts) > 1:
            d = pts[1] - pts[0]
            root.rotation_euler = (0, 0, math.atan2(d.y, d.x))
    _sim()["actors"].append({"node": root.name, "speed": speed, "shifts": out})
    return root


def twin_flow(label, a, b, t0, t1, color="#6cb6ff", kind="doc"):
    """A document (or request) travelling from point a to point b between sim times t0 and t1,
    shown as a labelled packet arcing between them."""
    _sim()["flows"].append({"label": label, "a": to_gltf(a), "b": to_gltf(b), "t0": float(t0),
                            "t1": float(t1), "color": color, "kind": kind})


def twin_state(record_id, keys):
    """Record state over sim time: [(t, state), ...]. States: pending (not started), active (work in
    progress), ok (released), at_risk, hold (blocked), done (turned over). The record's objects are
    tinted with the state at the playhead, and its card shows it."""
    _sim()["states"][record_id] = [[round(float(t), 4), s] for t, s in keys]
