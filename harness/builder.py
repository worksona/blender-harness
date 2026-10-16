"""MeshBuilder: assemble many parts into one mesh, for detailed structures (steel frames, pipework,
vessels with platforms and ladders) without thousands of separate objects.

    mb = MeshBuilder("Frame")
    mb.beam((0, 0, 0), (0, 0, 20), 0.4, steel)          # column from a to b
    mb.pipe([(0, 0, 5), (10, 0, 5), (10, 8, 5)], 0.3, grey)
    frame = mb.build(collection="Units")                 # -> one object, one material slot per material

Positions are in the builder's local space; place the built object like any other, or make it
a prefab and instance() it.
"""

import math

import bpy  # noqa: I001  (before bmesh/mathutils, required by the bpy module)
import bmesh
from mathutils import Euler, Matrix, Vector

from .core import _place


# Unit primitives (cube, cone, icosphere) built once with bmesh ops on a tiny mesh, then stamped
# into builders by copying transformed vertices. Calling the ops directly on a big builder mesh
# gets slower as the mesh grows (quadratic overall): a 10,000-pipe plant took over a minute.
_TEMPLATES = {}


def _template(kind, *params):
    key = (kind,) + params
    t = _TEMPLATES.get(key)
    if t is None:
        bm = bmesh.new()
        if kind == "cube":
            bmesh.ops.create_cube(bm, size=1.0)
        elif kind == "cone":
            segments, caps, ratio = params
            bmesh.ops.create_cone(bm, cap_ends=caps, segments=segments, radius1=1.0, radius2=ratio, depth=1.0)
        elif kind == "ico":
            bmesh.ops.create_icosphere(bm, subdivisions=params[0], radius=1.0)
        bm.verts.index_update()
        t = _TEMPLATES[key] = ([v.co.copy() for v in bm.verts],
                               [tuple(v.index for v in f.verts) for f in bm.faces])
        bm.free()
    return t


def _rounded_template(size, radius, segments, puff, flat):
    """Unit-free rounded box (cube-sphere corners, even bevel angles), optionally puffed: the flat
    part of every face bulges out by `puff` meters at its centre, like a cushion."""
    h = [s / 2 for s in size]
    r = min(radius, min(h) * 0.98)
    inner = [hk - r for hk in h]

    def cuts(k):
        edge = [-h[k] + r - r * math.tan(i / segments * math.pi / 4) for i in range(segments, 0, -1)]
        mid = [-inner[k] + 2 * inner[k] * i / (flat + 1) for i in range(flat + 2)]
        return edge + mid + [-e for e in reversed(edge)]
    bm = bmesh.new()
    index = {}

    def vert(p):
        key = tuple(round(c, 6) for c in p)
        v = index.get(key)
        if v is None:
            v = index[key] = bm.verts.new(p)
        return v
    for axis in range(3):
        a, b = (axis + 1) % 3, (axis + 2) % 3
        us, vs = cuts(a), cuts(b)
        for sign in (-1, 1):
            grid = []
            for u in us:
                row = []
                for v in vs:
                    p = [0.0, 0.0, 0.0]
                    p[axis], p[a], p[b] = sign * h[axis], u, v
                    core = [max(-inner[k], min(inner[k], p[k])) for k in range(3)]
                    off = Vector(p) - Vector(core)
                    n = off.normalized() if off.length > 1e-9 else Vector([0, 0, 0])
                    q = Vector(core) + n * r
                    if puff:
                        w = 1.0
                        for k in (a, b):
                            t = core[k] / inner[k] if inner[k] > 1e-6 else 0.0
                            w *= max(0.0, 1.0 - t * t)
                        q[axis] += sign * puff * w
                    row.append(vert(q))
                grid.append(row)
            for i in range(len(us) - 1):
                for j in range(len(vs) - 1):
                    quad = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
                    if len(set(quad)) == 4:
                        try:
                            bm.faces.new(quad)
                        except ValueError:
                            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.verts.index_update()
    t = ([v.co.copy() for v in bm.verts], [tuple(v.index for v in f.verts) for f in bm.faces])
    bm.free()
    return t


def _align_z(a, b):
    """Matrix that maps a unit Z-axis primitive centered on the origin onto segment a -> b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    length = d.length
    if length < 1e-6:
        return None, 0.0
    rot = d.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation((a + b) / 2) @ rot, length


class MeshBuilder:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.materials = []

    # ------------------------------------------------------------ internals

    def _mat_index(self, mat):
        if mat is None:
            return 0
        if mat not in self.materials:
            self.materials.append(mat)
        return self.materials.index(mat)

    def _stamp(self, template, matrix, mat, smooth):
        """Add a transformed copy of a unit primitive."""
        coords, faces = template
        new_vert, new_face = self.bm.verts.new, self.bm.faces.new
        vs = [new_vert(matrix @ c) for c in coords]
        idx = self._mat_index(mat)
        for f in faces:
            face = new_face([vs[i] for i in f])
            face.material_index = idx
            # Smooth curved sides, keep flat caps (n-gons) flat so they shade cleanly.
            face.smooth = smooth and (smooth == "all" or len(f) <= 4)
        return self

    # ------------------------------------------------------------ primitives

    def box(self, center, size, mat, rotation=(0, 0, 0)):
        """Box centered on `center`; size (x, y, z); rotation in degrees."""
        sx, sy, sz = size if isinstance(size, (tuple, list)) else (size,) * 3
        m = (Matrix.Translation(center) @ Euler([math.radians(r) for r in rotation]).to_matrix().to_4x4()
             @ Matrix.Diagonal((sx, sy, sz, 1)))
        return self._stamp(_template("cube"), m, mat, False)

    def rounded_box(self, center, size, mat, radius=0.02, segments=3, rotation=(0, 0, 0), puff=0.0,
                    flat=None):
        """Box with rounded edges and corners (furniture, upholstery, worktops, appliances).
        puff: the faces bulge out by this many meters at their centres (cushions, mattresses,
        pillows); flat: extra cuts across each flat face so the bulge is smooth (default 4 when
        puffed, else 0). Shaded smooth. Identical sizes share one cached template."""
        sx, sy, sz = size if isinstance(size, (tuple, list)) else (size,) * 3
        flat = (4 if puff else 0) if flat is None else flat
        key = ("rbox", round(sx, 4), round(sy, 4), round(sz, 4), round(radius, 4), segments,
               round(puff, 4), flat)
        t = _TEMPLATES.get(key)
        if t is None:
            t = _TEMPLATES[key] = _rounded_template((sx, sy, sz), radius, segments, puff, flat)
        m = Matrix.Translation(center) @ Euler([math.radians(r) for r in rotation]).to_matrix().to_4x4()
        return self._stamp(t, m, mat, "all")

    def rounded_slab(self, center, size, corner, mat, segments=6, rotation=(0, 0, 0)):
        """Slab whose corners are rounded in plan (table tops, rugs, mirrors, trays): size (x, y,
        thickness), corner = plan radius. Edges stay crisp; centre is the middle of the slab."""
        sx, sy, sz = size
        c = min(corner, sx / 2 * 0.999, sy / 2 * 0.999)
        ring = []
        for cx, cy, a0 in ((sx / 2 - c, sy / 2 - c, 0), (-sx / 2 + c, sy / 2 - c, 90),
                           (-sx / 2 + c, -sy / 2 + c, 180), (sx / 2 - c, -sy / 2 + c, 270)):
            for i in range(segments + 1):
                a = math.radians(a0 + 90 * i / segments)
                ring.append((cx + c * math.cos(a), cy + c * math.sin(a)))
        n = len(ring)
        verts = [(x, y, -sz / 2) for x, y in ring] + [(x, y, sz / 2) for x, y in ring]
        faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        m = Matrix.Translation(center) @ Euler([math.radians(r) for r in rotation]).to_matrix().to_4x4()
        return self._stamp(([Vector(v) for v in verts], faces), m, mat, False)

    def lathe(self, base, profile, mat, segments=32, scale=(1, 1), rotation=(0, 0, 0), cap=True):
        """Surface of revolution around a vertical axis standing on `base` (vases, lamp shades,
        bowls, plates, glasses, table pedestals, basins). profile: [(radius, z), ...] from bottom
        to top; a radius of 0 closes that end to a point. scale (sx, sy) stretches it into an
        oval (bathtubs, oval tables). Open ends get flat caps unless cap=False. Shaded smooth:
        build with sharp_angle to keep creases (rims, steps) crisp."""
        sx, sy = scale
        verts, faces, rings = [], [], []
        for r, z in profile:
            if r <= 1e-6:
                rings.append([len(verts)])
                verts.append(Vector((0, 0, z)))
                continue
            ring = []
            for i in range(segments):
                a = 2 * math.pi * i / segments
                ring.append(len(verts))
                verts.append(Vector((r * math.cos(a) * sx, r * math.sin(a) * sy, z)))
            rings.append(ring)
        for lo, hi in zip(rings, rings[1:]):
            if len(lo) == 1 and len(hi) == 1:
                continue
            for i in range(segments):
                j = (i + 1) % segments
                if len(lo) == 1:
                    faces.append((lo[0], hi[i], hi[j]))
                elif len(hi) == 1:
                    faces.append((lo[i], lo[j], hi[0]))
                else:
                    faces.append((lo[i], lo[j], hi[j], hi[i]))
        m = Matrix.Translation(base) @ Euler([math.radians(r) for r in rotation]).to_matrix().to_4x4()
        self._stamp((verts, faces), m, mat, "all")
        for ring, flip in ((rings[0], True), (rings[-1], False)):
            if cap and len(ring) > 1:   # separate verts, so the cap's edge stays crisp
                face = tuple(range(len(ring)))
                self._stamp(([verts[i] for i in ring], [face[::-1] if flip else face]), m, mat, False)
        return self

    def faces(self, verts, faces, mat, smooth=True, matrix=None):
        """Raw geometry (leaves, drapes, custom shapes): vertex list + face index tuples, in the
        builder's space (or transformed by `matrix`)."""
        m = matrix or Matrix.Identity(4)
        return self._stamp(([Vector(v) for v in verts], [tuple(f) for f in faces]), m, mat,
                           "all" if smooth else False)

    def slab(self, x0, y0, x1, y1, z, thickness, mat):
        """Horizontal plate from corner (x0, y0) to (x1, y1), top surface at z."""
        return self.box(((x0 + x1) / 2, (y0 + y1) / 2, z - thickness / 2),
                        (abs(x1 - x0), abs(y1 - y0), thickness), mat)

    def beam(self, a, b, width, mat, depth=None):
        """Square-section member from point a to point b (columns, beams, braces)."""
        m, length = _align_z(a, b)
        if m is None:
            return self
        m = m @ Matrix.Diagonal((width, depth or width, length, 1))
        return self._stamp(_template("cube"), m, mat, False)

    def rod(self, a, b, radius, mat, segments=12, radius_b=None, caps=True):
        """Round member from a to b (pipes, posts, rungs). radius_b tapers it."""
        m, length = _align_z(a, b)
        if m is None:
            return self
        if radius <= 0:
            return self
        ratio = 1.0 if radius_b is None else round(radius_b / radius, 3)
        m = m @ Matrix.Diagonal((radius, radius, length, 1))
        return self._stamp(_template("cone", segments, bool(caps), ratio), m, mat, True)

    def cylinder(self, base, radius, height, mat, segments=32, radius_top=None):
        """Vertical cylinder standing on `base` (x, y, z)."""
        x, y, z = base
        return self.rod((x, y, z), (x, y, z + height), radius, mat, segments, radius_top)

    def sphere(self, center, radius, mat, subdivisions=3, scale=(1, 1, 1)):
        m = Matrix.Translation(center) @ Matrix.Diagonal((scale[0] * radius, scale[1] * radius,
                                                          scale[2] * radius, 1))
        return self._stamp(_template("ico", subdivisions), m, mat, "all")

    def dome(self, center, radius, height, mat, segments=32, rings=6):
        """Elliptical cap (vessel heads, tank roofs) sitting on `center`, bulging up by `height`."""
        cx, cy, cz = center
        rows = []
        for r in range(rings + 1):
            t = r / rings * math.pi / 2
            rr, zz = radius * math.cos(t), height * math.sin(t)
            if r == rings:
                rows.append([self.bm.verts.new((cx, cy, cz + height))])
                break
            rows.append([self.bm.verts.new((cx + rr * math.cos(2 * math.pi * s / segments),
                                            cy + rr * math.sin(2 * math.pi * s / segments), cz + zz))
                         for s in range(segments)])
        new = []
        for r in range(len(rows) - 1):
            lo, hi = rows[r], rows[r + 1]
            for s in range(segments):
                s2 = (s + 1) % segments
                quad = [lo[s], lo[s2], hi[s2 % len(hi)], hi[s % len(hi)]]
                quad = list(dict.fromkeys(quad))
                new.append(self.bm.faces.new(quad))
        idx = self._mat_index(mat)
        for f in new:
            f.material_index = idx
            f.smooth = True
        return self

    def torus(self, center, major, minor, mat, major_segments=48, minor_segments=6, arc=360.0,
              start=0.0, rotation=(0, 0, 0)):
        """Ring in the XY plane (handrails, stiffener rings). arc < 360 makes an open ring
        running from `start` degrees. rotation (degrees) tilts it about its centre (mirror
        frames, fan guards)."""
        tilt = Euler([math.radians(r) for r in rotation]).to_matrix()
        c0 = Vector(center)
        closed = arc >= 360
        n = major_segments if closed else major_segments + 1
        rings = []
        for i in range(n):
            u = math.radians(start) + math.radians(arc) * i / major_segments
            ring = []
            for j in range(minor_segments):
                v = 2 * math.pi * j / minor_segments
                r = major + minor * math.cos(v)
                local = Vector((r * math.cos(u), r * math.sin(u), minor * math.sin(v)))
                ring.append(self.bm.verts.new(c0 + tilt @ local))
            rings.append(ring)
        idx = self._mat_index(mat)
        for i in range(major_segments if closed else n - 1):
            a, b = rings[i], rings[(i + 1) % n]
            for j in range(minor_segments):
                j2 = (j + 1) % minor_segments
                f = self.bm.faces.new((a[j], b[j], b[j2], a[j2]))
                f.material_index = idx
                f.smooth = True
        return self

    def pipe(self, points, radius, mat, segments=12, elbows=True):
        """Pipe along a polyline, with spherical elbows at the bends."""
        pts = [Vector(p) for p in points]
        for a, b in zip(pts, pts[1:]):
            self.rod(a, b, radius, mat, segments, caps=False)
        if elbows:
            for p in pts[1:-1]:
                self.sphere(p, radius, mat, subdivisions=1 if segments <= 8 else 2)
        return self

    def tube(self, points, radius, mat, bend_radius=None, segments=24, arc_steps=10, caps=True):
        """Pipe swept along a polyline with smooth circular bends at the corners (real pipe bends,
        not ball joints). bend_radius defaults to 1.5x the pipe diameter (a long-radius elbow).
        Returns the path's corner tangent points, handy for placing flanges."""
        pts = [Vector(p) for p in points]
        R = bend_radius or radius * 3.0
        path = [pts[0]]
        for i in range(1, len(pts) - 1):
            a = (pts[i] - pts[i - 1]).normalized()
            b = (pts[i + 1] - pts[i]).normalized()
            cos_phi = max(-1.0, min(1.0, a.dot(b)))
            phi = math.acos(cos_phi)
            if phi < 1e-3:
                path.append(pts[i])
                continue
            t = min(R * math.tan(phi / 2), (pts[i] - pts[i - 1]).length * 0.49,
                    (pts[i + 1] - pts[i]).length * 0.49)
            r = t / math.tan(phi / 2)
            n = (b - a * cos_phi).normalized()
            start = pts[i] - a * t
            center = start + n * r
            for k in range(arc_steps + 1):
                al = phi * k / arc_steps
                path.append(center + (-n * math.cos(al) + a * math.sin(al)) * r)
        path.append(pts[-1])
        # Drop duplicate points, then sweep a circle with parallel-transported frames.
        clean = [path[0]]
        for p in path[1:]:
            if (p - clean[-1]).length > 1e-4:
                clean.append(p)
        tangents = []
        for i in range(len(clean)):
            prev = clean[max(i - 1, 0)]
            nxt = clean[min(i + 1, len(clean) - 1)]
            tangents.append((nxt - prev).normalized())
        t0 = tangents[0]
        normal = t0.orthogonal().normalized()
        rings = []
        for i, (p, t) in enumerate(zip(clean, tangents)):
            if i:
                normal = (tangents[i - 1].rotation_difference(t) @ normal).normalized()
            binormal = t.cross(normal)
            rings.append([self.bm.verts.new(p + (normal * math.cos(2 * math.pi * s / segments) +
                                                 binormal * math.sin(2 * math.pi * s / segments)) * radius)
                          for s in range(segments)])
        idx = self._mat_index(mat)
        for r0, r1 in zip(rings, rings[1:]):
            for s in range(segments):
                s2 = (s + 1) % segments
                f = self.bm.faces.new((r0[s], r0[s2], r1[s2], r1[s]))
                f.material_index = idx
                f.smooth = True
        if caps:
            for ring, rev in ((rings[0], True), (rings[-1], False)):
                f = self.bm.faces.new(list(reversed(ring)) if rev else ring)
                f.material_index = idx
        return clean

    def flange(self, center, direction, pipe_radius, mat, bolts=16, bolt_mat=None):
        """Bolted flange pair on a pipe at `center`, facing along `direction`."""
        d = Vector(direction).normalized()
        c = Vector(center)
        fr = pipe_radius * 1.55
        self.rod(c - d * 0.09, c + d * 0.09, fr, mat, 32)
        self.rod(c - d * 0.13, c + d * 0.13, pipe_radius * 1.12, mat, 32)  # weld necks
        u = d.orthogonal().normalized()
        v = d.cross(u)
        for k in range(bolts):
            ang = 2 * math.pi * k / bolts
            p = c + (u * math.cos(ang) + v * math.sin(ang)) * fr * 0.84
            self.rod(p - d * 0.16, p + d * 0.16, min(0.035, pipe_radius * 0.09), bolt_mat or mat, 6)
        return self

    def handwheel(self, center, direction, radius, mat, stem_mat=None):
        """Valve handwheel: rim, spokes and stem, facing along `direction`."""
        d = Vector(direction).normalized()
        c = Vector(center)
        u = d.orthogonal().normalized()
        v = d.cross(u)
        rim = []
        for k in range(17):
            ang = 2 * math.pi * k / 16
            rim.append(c + (u * math.cos(ang) + v * math.sin(ang)) * radius)
        for a, b in zip(rim, rim[1:]):
            self.rod(a, b, radius * 0.07, mat, 6, caps=False)
        for k in range(4):
            ang = math.pi / 2 * k
            self.rod(c, c + (u * math.cos(ang) + v * math.sin(ang)) * radius, radius * 0.05, mat, 6)
        self.rod(c, c - d * radius * 1.2, radius * 0.08, stem_mat or mat, 8)
        return self

    def ladder(self, bottom, height, mat, facing=0.0, width=0.5, rung_step=0.3, cage=False):
        """Vertical ladder: two rails plus rungs. facing = direction the climber's back points
        (degrees). cage=True adds safety hoops and bars from 2.5 m up."""
        bx, by, bz = bottom
        f = math.radians(facing)
        side = Vector((-math.sin(f), math.cos(f), 0)) * width / 2
        out = Vector((math.cos(f), math.sin(f), 0))
        base = Vector((bx, by, bz))
        for s in (side, -side):
            self.rod(base + s, base + s + Vector((0, 0, height)), 0.03, mat, 6)
        z = rung_step
        while z < height:
            self.rod(base + side + Vector((0, 0, z)), base - side + Vector((0, 0, z)), 0.018, mat, 5,
                     caps=False)
            z += rung_step
        if cage and height > 3:
            hoop_r = 0.38
            center = base + out * hoop_r
            start = math.degrees(f) + 180 + 55   # open on the ladder side
            hz = []
            z = 2.5
            while z < height + 0.9:
                self.torus((center.x, center.y, bz + z), hoop_r, 0.025, mat, 18, 4, arc=250.0,
                           start=start)
                hz.append(bz + z)
                z += 0.9
            for k in range(5):
                ang = math.radians(start + 250 * (k + 0.5) / 5)
                p = center + Vector((math.cos(ang), math.sin(ang), 0)) * hoop_r
                self.rod((p.x, p.y, hz[0]), (p.x, p.y, hz[-1]), 0.02, mat, 4, caps=False)
        return self

    def railing(self, points, mat, height=1.1, post_step=2.0, closed=False):
        """Handrail with mid-rail and posts along a polyline at the polyline's height."""
        pts = [Vector(p) for p in points] + ([Vector(points[0])] if closed else [])
        up = Vector((0, 0, height))
        for a, b in zip(pts, pts[1:]):
            self.rod(a + up, b + up, 0.03, mat, 6, caps=False)
            self.rod(a + up * 0.5, b + up * 0.5, 0.025, mat, 6, caps=False)
            n = max(1, int((b - a).length / post_step))
            for i in range(n):
                p = a.lerp(b, i / n)
                self.rod(p, p + up, 0.03, mat, 6)
        return self

    def ring_platform(self, center, inner, outer, mat_floor, mat_rail, segments=32, arc=360.0,
                      start=0.0):
        """Circular walkway around a vessel at height center.z, with an outer handrail."""
        cx, cy, cz = center
        n = segments if arc >= 360 else segments + 1
        outer_v, inner_v = [], []
        for i in range(n):
            u = math.radians(start + arc * i / segments)
            outer_v.append(self.bm.verts.new((cx + outer * math.cos(u), cy + outer * math.sin(u), cz)))
            inner_v.append(self.bm.verts.new((cx + inner * math.cos(u), cy + inner * math.sin(u), cz)))
        idx = self._mat_index(mat_floor)
        for i in range(segments if arc >= 360 else n - 1):
            j = (i + 1) % n
            f = self.bm.faces.new((inner_v[i], outer_v[i], outer_v[j], inner_v[j]))
            f.material_index = idx
        rail_r = outer - 0.05
        self.torus((cx, cy, cz + 1.1), rail_r, 0.03, mat_rail, segments, 5, arc=arc, start=start)
        self.torus((cx, cy, cz + 0.55), rail_r, 0.025, mat_rail, segments, 5, arc=arc, start=start)
        for i in range(0, n, 2):
            u = math.radians(start + arc * i / segments)
            p = Vector((cx + rail_r * math.cos(u), cy + rail_r * math.sin(u), cz))
            self.rod(p, p + Vector((0, 0, 1.1)), 0.03, mat_rail, 5)
        return self

    # ------------------------------------------------------------ output

    def build(self, location=(0, 0, 0), rotation=(0, 0, 0), collection=None, sharp_angle=None):
        """sharp_angle (degrees): smooth-shaded faces meeting at more than this angle get a crisp
        edge (lathe rims, rounded_box seams on puffed cushions); the .glb keeps the split normals."""
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        if sharp_angle is not None:
            me.set_sharp_from_angle(angle=math.radians(sharp_angle))
        for m in self.materials:
            me.materials.append(m)
        obj = bpy.data.objects.new(self.name, me)
        return _place(obj, location, rotation, (1, 1, 1), collection)
