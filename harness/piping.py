"""Process piping to real dimensions: pipe, LR elbows, tees, reducers, weld-neck flanges, olets,
threaded valves and plugs, bolted joints with studs and nuts, weld beads.

Dimensions follow ASME B36.10 (pipe OD), B16.9 (butt-weld fittings), B16.5 Class 600 (flanges and
bolting) and B16.11 (forged threaded fittings). A spool is described as a route, the same way an
isometric drawing reads, and built into one MeshBuilder:

    sp = Spool("S-1", nps=10, mats=M)
    sp.walk([("flange",), ("pipe", 1729, [(1059, "U", "vent")]), ("elbow", "S"), ("flange",)],
            start=(0, 0, 0), direction="E")
    obj = sp.build(collection="Spools")
    sp.joints   # open flange ends: where test blinds and studs go (see bolt_joint)
    sp.welds    # weld bead positions in route order (A, B, C... on the drawing)

Directions are the drawing's: N=+Y, S=-Y, E=+X, W=-X, U=+Z, D=-Z. Lengths in the route are
millimetres; everything built is in metres.

Materials (dict `mats`): pipe, fitting, flange, weld, olet, valve, lever, plug, blind, gasket.
"""

import math

from mathutils import Vector

from .builder import MeshBuilder

DIRS = {"N": (0, 1, 0), "S": (0, -1, 0), "E": (1, 0, 0), "W": (-1, 0, 0), "U": (0, 0, 1), "D": (0, 0, -1)}

# NPS -> outside diameter (mm), ASME B36.10.
OD = {0.5: 21.3, 0.75: 26.7, 1: 33.4, 1.5: 48.3, 2: 60.3, 3: 88.9, 4: 114.3, 6: 168.3, 8: 219.1,
      10: 273.0, 12: 323.8, 14: 355.6, 16: 406.4}

# ASME B16.5 Class 600 weld-neck flange (mm): O flange OD, T thickness, Y length through hub,
# X hub diameter at the flange, R raised face diameter, BC bolt circle, n bolts, bolt diameter.
CL600 = {
    0.5: dict(O=95.3, T=14.3, Y=52.4, X=38.1, R=34.9, BC=66.7, n=4, d=12.7, L=90),
    1: dict(O=124.0, T=17.5, Y=61.9, X=52.4, R=50.8, BC=88.9, n=4, d=15.9, L=100),
    2: dict(O=165.1, T=25.4, Y=73.0, X=84.1, R=92.1, BC=127.0, n=8, d=15.9, L=115),
    6: dict(O=355.6, T=47.7, Y=117.5, X=206.4, R=215.9, BC=292.1, n=12, d=25.4, L=175),
    8: dict(O=419.1, T=55.6, Y=133.4, X=260.4, R=269.9, BC=349.3, n=12, d=28.6, L=200),
    10: dict(O=508.0, T=63.5, Y=152.4, X=320.7, R=323.9, BC=431.8, n=16, d=31.8, L=220),
    12: dict(O=558.8, T=66.7, Y=155.6, X=374.7, R=381.0, BC=488.9, n=20, d=31.8, L=225),
    16: dict(O=685.8, T=76.2, Y=177.8, X=463.6, R=469.9, BC=603.3, n=20, d=38.1, L=260),
}
RF_HEIGHT = 6.4      # Class 600 raised face (mm)
GASKET_T = 3.2       # spiral wound gasket, as on the BOMs

# B16.9 straight tee centre-to-end (run C = branch M for straight tees), mm.
TEE_C = {2: 64, 3: 86, 4: 105, 6: 143, 8: 178, 10: 216, 12: 254, 16: 305}
TEE_M_REDUCING = {(10, 8): 203, (12, 10): 241, (12, 8): 229, (8, 6): 168}
# B16.9 reducer length H, mm (keyed by the larger size).
REDUCER_H = {(8, 6): 152, (12, 10): 203, (16, 10): 356, (16, 12): 356, (10, 8): 178, (6, 4): 140}
# B16.11 Class 3000/6000 threaded elbow/tee centre-to-end and body OD (mm).
THREADED = {0.5: (25.5, 38.0), 0.75: (28.5, 44.0), 1: (38.0, 57.0), 2: (51.0, 89.0)}
THREAD_ENGAGE = 17.5   # mm of a nipple hidden inside each fitting


def elbow_A(nps):
    """LR 90 elbow centre-to-end (mm): 1.5 x nominal size."""
    return 1.5 * nps * 25.4


def _v(d):
    return Vector(DIRS[d]) if isinstance(d, str) else Vector(d).normalized()


def _perp(d):
    """A unit vector perpendicular to d (stable choice: prefers horizontal, else north)."""
    up = Vector((0, 0, 1))
    p = d.cross(up)
    if p.length < 1e-6:
        p = d.cross(Vector((0, 1, 0)))
    return p.normalized()


class Spool:
    def __init__(self, name, nps, mats, sch="80", segments=None, branch_nps=None, threaded=False):
        self.name = name
        self.nps = nps
        self.M = mats
        self.sch = sch
        self.parts = []      # one per physical component, see part()
        self.part("misc")
        self.branch_nps = branch_nps
        self.threaded = threaded
        self.joints = []     # {"pos", "normal", "nps"} open flange faces (normal points outward)
        self.welds = []      # {"pos", "dir", "nps", "type" (BW/LET), "part"} in route order
        self.olets = []      # {"pos", "dir", "kind", "nps"}
        self.runs = []       # horizontal pipe runs: (a, b, radius) for supports
        self.points = []     # every centreline point, for bounds
        self.seg = segments
        self._first = True

    # ------------------------------------------------------------ helpers

    def part(self, kind, nps=None, **info):
        """Start a new physical component (pipe piece, fitting, flange, weld, valve...). Everything
        drawn until the next part() goes into its own mesh, so each can carry its own twin record.
        Returns the part's record: {"kind", "nps", "info", "mb", "index", "obj" (after build)}."""
        rec = {"kind": kind, "nps": nps, "info": info, "index": len(self.parts),
               "mb": MeshBuilder(f"{self.name}:{kind}{len(self.parts)}")}
        self.parts.append(rec)
        self.mb = rec["mb"]
        return rec

    def r(self, nps):
        return OD[nps] / 2000.0

    def segs(self, nps):
        if self.seg:
            return self.seg
        return 40 if nps >= 10 else 32 if nps >= 6 else 20 if nps >= 2 else 14

    def _ring(self, center, direction, radius, mat, segments):
        d = direction.normalized()
        u = _perp(d)
        v = d.cross(u)
        return [center + (u * math.cos(2 * math.pi * k / segments) + v * math.sin(2 * math.pi * k / segments)) * radius
                for k in range(segments)]

    def _sweep(self, rings, mat, smooth=True):
        bm = self.mb.bm
        idx = self.mb._mat_index(mat)
        vrings = [[bm.verts.new(p) for p in ring] for ring in rings]
        n = len(rings[0])
        for r0, r1 in zip(vrings, vrings[1:]):
            for k in range(n):
                f = bm.faces.new((r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]))
                f.material_index = idx
                f.smooth = smooth

    def weld(self, pos, direction, nps):
        """Weld bead: a low ring a little proud of the pipe."""
        r = self.r(nps)
        d = direction.normalized()
        if any((w["pos"] - pos).length < 0.002 for w in self.welds):
            return   # fitting-to-fitting: one weld, not two
        prev = self.mb
        rec = self.part("weld", nps, type="BW")
        u = _perp(d)
        v = d.cross(u)
        n = self.segs(nps)
        bead = max(0.0025, r * 0.035)
        rings = []
        for j in range(7):
            a = math.pi * j / 6
            off = d * (math.cos(a) * bead * 1.6)
            rad = r + math.sin(a) * bead
            rings.append([pos + off + (u * math.cos(2 * math.pi * k / n) + v * math.sin(2 * math.pi * k / n)) * rad
                          for k in range(n)])
        self._sweep(rings, self.M["weld"])
        self.welds.append({"pos": pos.copy(), "dir": d.copy(), "nps": nps, "type": "BW", "part": rec})
        self.mb = prev

    def let_weld(self, base, out, radius, nps):
        """Fillet weld round the foot of an olet (a 'LET' weld on the drawings)."""
        prev = self.mb
        rec = self.part("weld", nps, type="LET")
        self.mb.torus((0, 0, 0), radius * 1.02, max(0.003, radius * 0.12), self.M["weld"], 24, 6)
        # torus() builds in the XY plane at the origin: move its vertices onto the olet's foot
        q = out.normalized().to_track_quat("Z", "Y").to_matrix()
        for v in self.mb.bm.verts:
            v.co = base + q @ v.co
        self.welds.append({"pos": base.copy(), "dir": out.copy(), "nps": nps, "type": "LET", "part": rec})
        self.mb = prev

    # ------------------------------------------------------------ components

    def pipe(self, a, b, nps, mat=None, length_mm=None):
        self.part("pipe", nps, length=length_mm)
        self.mb.rod(a, b, self.r(nps), mat or self.M["pipe"], self.segs(nps), caps=False)
        if abs((b - a).normalized().z) < 0.2:
            self.runs.append((a.copy(), b.copy(), self.r(nps)))
        self.points += [a.copy(), b.copy()]

    def elbow(self, p, d1, d2, nps, radius=None):
        """LR elbow from p heading d1, turning to d2. Returns the end point."""
        A = (radius if radius is not None else elbow_A(nps)) / 1000.0
        self.part("elbow", nps)
        c = p + d2 * A
        rings = []
        steps = 12 if nps >= 6 else 8
        r = self.r(nps)
        for k in range(steps + 1):
            t = (math.pi / 2) * k / steps
            pt = c + (-d2 * math.cos(t) + d1 * math.sin(t)) * A
            tan = (d1 * math.cos(t) + d2 * math.sin(t)).normalized()
            rings.append(self._ring(pt, tan, r, None, self.segs(nps)))
        self._sweep(rings, self.M["fitting"])
        end = p + d1 * A + d2 * A
        self.points += [p.copy(), p + d1 * A, end.copy()]
        return end

    def threaded_elbow(self, p, d1, d2, nps):
        c2e, body = THREADED[nps]
        self.part("elbow", nps, threaded=True)
        c = p + d1 * (c2e / 1000)
        br = body / 2000
        self.mb.rod(p, c, br, self.M["fitting"], 12)
        self.mb.rod(c, c + d2 * (c2e / 1000), br, self.M["fitting"], 12)
        self.mb.sphere(c, br, self.M["fitting"], 2)
        self.points += [p.copy(), c.copy()]
        return c + d2 * (c2e / 1000)

    def flange_body(self, weld_pt, outward, nps, raised_face=True):
        """WN flange whose hub is welded at weld_pt and whose face points along `outward`.
        Returns the raised-face position (gasket seat)."""
        f = CL600[nps]
        self.part("flange", nps)
        d = outward.normalized()
        hub_len = (f["Y"] - f["T"]) / 1000
        n = max(self.segs(nps), 24)
        back = weld_pt + d * hub_len
        self.mb.rod(weld_pt, back, self.r(nps), self.M["flange"], n, radius_b=f["X"] / 2000, caps=False)
        front = back + d * (f["T"] / 1000 - RF_HEIGHT / 1000)
        self.mb.rod(back, front, f["O"] / 2000, self.M["flange"], max(n, 32))
        face = front + d * (RF_HEIGHT / 1000)
        if raised_face:
            self.mb.rod(front, face, f["R"] / 2000, self.M["flange"], max(n, 32))
        self.points += [weld_pt.copy(), face.copy()]
        return face

    def olet(self, at, along, out, kind, header_nps):
        """Branch fitting on the header surface at `at` (centreline point), pointing `out`."""
        out = out.normalized()
        R = self.r(header_nps)
        base = at + out * (R * 0.92)
        M = self.M
        if kind == "wol_flange":
            h, rb, rt = 0.064, 0.058, 0.040
            top = base + out * h
            self.part("olet", (header_nps, 2), type="WOL")
            self.mb.rod(base, top, rb, M["olet"], 24, radius_b=rt)
            self.weld(top, out, 2)
            self.let_weld(base, out, rb, 2)
            face = self.flange_body(top, out, 2)
            self.joints.append({"pos": face, "normal": out.copy(), "nps": 2})
            self.olets.append({"pos": base, "dir": out, "kind": kind, "nps": 2})
            return
        half = kind == "vent_half"
        branch = 0.5 if half else 1
        h, rb, rt = (0.026, 0.026, 0.019) if half else (0.038, 0.036, 0.028)
        top = base + out * h
        self.part("olet", (header_nps, branch), type="TOL")
        self.mb.rod(base, top, rb, M["olet"], 16, radius_b=rt)
        self.mb.rod(top - out * 0.004, top, rt * 1.02, M["olet"], 6)   # hex-ish land
        self.let_weld(base, out, rb, branch)
        self.olets.append({"pos": base, "dir": out, "kind": kind, "nps": branch})
        if kind == "tol":
            self.plug(top, out, branch, red_cap=True)
            return
        # Vent/drain: nipple, ball valve, hex plug.
        p = top + out * 0.002
        nip = 0.100 - 2 * THREAD_ENGAGE / 1000 + 0.012
        self.part("nipple", branch, length=100)
        self.mb.rod(p, p + out * nip, self.r(branch), M["olet"], 12)
        p = p + out * nip
        p = self.ball_valve(p, out, branch, lever_dir=along)
        self.plug(p, out, branch)

    def ball_valve(self, p, d, nps, lever_dir=None):
        """3-piece threaded ball valve (blue body, black lever); returns the outlet point."""
        M = self.M
        self.part("valve", nps)
        s = 1.0 if nps >= 1 else 0.72
        L = 0.095 * s
        body_r = 0.033 * s
        end_r = 0.024 * s
        q = p + d * L
        mid = p + d * (L / 2)
        self.mb.rod(p, p + d * 0.022 * s, end_r, M["valve"], 6)                 # hex ends
        self.mb.rod(q - d * 0.022 * s, q, end_r, M["valve"], 6)
        self.mb.rod(mid - d * 0.026 * s, mid + d * 0.026 * s, body_r, M["valve"], 16)
        u = _perp(d) if lever_dir is None else (lever_dir - d * lever_dir.dot(d)).normalized()
        stem = d.cross(u).normalized()
        if stem.z < 0:
            stem = -stem
        for k in range(4):   # body bolts
            a = math.pi / 4 + k * math.pi / 2
            off = (u * math.cos(a) + stem * math.sin(a)) * body_r * 0.85
            self.mb.rod(mid + off - d * 0.03 * s, mid + off + d * 0.03 * s, 0.0035 * s, M["plug"], 6)
        top = mid + stem * (body_r + 0.018 * s)
        self.mb.rod(mid + stem * body_r, top, 0.007 * s, M["plug"], 8)
        lever_end = top + u * 0.15 * s + stem * 0.012 * s
        self.mb.beam(top, lever_end, 0.018 * s, M["lever"], 0.006 * s)
        self.mb.rod(lever_end - u * 0.07 * s, lever_end, 0.011 * s, M["lever"], 8)   # grip
        self.points += [p.copy(), q.copy()]
        return q

    def plug(self, p, d, nps, red_cap=False):
        s = 1.0 if nps >= 1 else 0.7
        self.part("cap" if red_cap else "plug", nps)
        if red_cap:   # plastic thread protector on an open TOL
            self.mb.rod(p, p + d * 0.018 * s, 0.021 * s, self.M["cap"], 12)
            return
        self.mb.rod(p, p + d * 0.014 * s, 0.016 * s, self.M["plug"], 12)
        self.mb.rod(p + d * 0.014 * s, p + d * 0.032 * s, 0.021 * s, self.M["plug"], 6)

    def reducer(self, p, d, nps1, nps2, ecc):
        big, small = max(nps1, nps2), min(nps1, nps2)
        H = REDUCER_H.get((big, small), 25.4 * (big - small) * 2) / 1000
        self.part("reducer", (big, small), ecc=ecc)
        r1, r2 = self.r(nps1), self.r(nps2)
        shift = Vector((0, 0, 0))
        if ecc:   # flat on the bottom: the centreline steps by the radius difference
            down = Vector((0, 0, -1))
            if abs(d.dot(down)) > 0.9:
                down = _perp(d)
            shift = -down * (r1 - r2)
        q = p + d * H + shift
        rings = []
        n = self.segs(max(nps1, nps2))
        for k in range(7):
            t = k / 6
            tt = t * t * (3 - 2 * t)
            c = p + d * (H * t) + shift * tt
            rings.append(self._ring(c, d, r1 + (r2 - r1) * tt, None, n))
        self._sweep(rings, self.M["fitting"])
        self.points += [p.copy(), q.copy()]
        return q

    def blind_plate(self, p, d, nps):
        f = CL600[nps]
        self.part("gasket", nps)
        self.mb.rod(p, p + d * (GASKET_T / 1000), f["R"] / 2000 * 1.05, self.M["gasket"], 32)
        q = p + d * (GASKET_T / 1000)
        self.part("blind", nps)
        self.mb.rod(q, q + d * (f["T"] / 1000), f["O"] / 2000, self.M["blind_paint"], 40)
        self.points += [q + d * (f["T"] / 1000)]

    # ------------------------------------------------------------ route walking

    def walk(self, steps, start=(0, 0, 0), direction="E", nps=None, _pos=None):
        """Build the route. The first ("flange",) puts the flange FACE at `start` and the run heads
        along `direction`; routes that begin with a pipe start with that pipe's end at `start`."""
        pos = Vector(start) if _pos is None else _pos
        d = _v(direction)
        nps = nps or self.nps
        thr = self.threaded
        for i, step in enumerate(steps):
            kind = step[0]
            if kind == "flange":
                if self._first and _pos is None and i == 0:
                    f = CL600[2 if thr else nps]
                    face = pos.copy()
                    weld_pt = face + d * (f["Y"] / 1000)
                    self.flange_body(weld_pt, -d, 2 if thr else nps)
                    self.joints.append({"pos": face, "normal": -d, "nps": 2 if thr else nps})
                    pos = weld_pt
                    if not thr:
                        self.weld(pos, d, nps)
                    else:   # threaded hub flange: the 1" nipple screws into its hub
                        pos = weld_pt - d * 0.01
                else:
                    if not thr:
                        self.weld(pos, d, nps)
                    face = self.flange_body(pos, d, nps)
                    self.joints.append({"pos": face, "normal": d.copy(), "nps": nps})
                    pos = face
            elif kind == "flange_pair":
                # Two spools bolted together: flange, gasket, mating flange (bolted, no blind).
                self.weld(pos, d, nps)
                face = self.flange_body(pos, d, nps)
                f = CL600[nps]
                g = face + d * (GASKET_T / 1000)
                self.part("gasket", nps)
                self.mb.rod(face, g, f["R"] / 2000 * 1.08, self.M["gasket"], 32)
                other_weld = g + d * (f["Y"] / 1000)
                self.flange_body(other_weld, -d, nps)
                self.joints.append({"pos": face, "normal": d.copy(), "nps": nps, "mated": True,
                                    "mate_t": f["T"] / 1000})
                pos = other_weld
                self.weld(pos, d, nps)
            elif kind == "pipe":
                L = step[1] / 1000
                if thr:
                    L -= 2 * THREAD_ENGAGE / 1000 - 0.012
                end = pos + d * L
                self.pipe(pos, end, nps, length_mm=step[1])
                for off, odir, okind in (step[2] if len(step) > 2 else []):
                    self.olet(pos + d * (off / 1000), d, _v(odir), okind, nps)
                pos = end
            elif kind == "elbow":
                d2 = _v(step[1])
                if thr:
                    pos = self.threaded_elbow(pos, d, d2, nps)
                else:
                    self.weld(pos, d, nps)
                    pos = self.elbow(pos, d, d2, nps)
                    self.weld(pos, d2, nps)
                d = d2
            elif kind == "reducer":
                nps2 = step[1]
                self.weld(pos, d, nps)
                pos = self.reducer(pos, d, nps, nps2, step[2] == "ecc")
                nps = nps2
                self.weld(pos, d, nps)
            elif kind == "tee":
                self._tee(pos, d, nps, step[1])
                return pos
            elif kind == "blind":
                self.blind_plate(pos, d, nps)
            elif kind == "let":
                self.let_weld(pos, d, self.r(nps), nps)
            elif kind == "valve":
                pos = self.ball_valve(pos, d, nps)
            elif kind == "plug":
                self.plug(pos, d, nps)
            self._first = False
        return pos

    def _tee(self, pos, d, nps, ports):
        """Tee entered at `pos` travelling `d`. Ports: [(dir, steps), (dir, steps)]."""
        outs = [_v(p[0]) for p in ports]
        back = -d
        # The run is the collinear pair among the three ports; the odd one out is the branch.
        dirs = [back] + outs
        branch_i = None
        for i in range(3):
            others = [dirs[j] for j in range(3) if j != i]
            if others[0].dot(others[1]) < -0.99:
                branch_i = i
        run_nps = nps
        bnps = self.branch_nps or nps
        if branch_i == 0:          # entering through the branch
            run_nps, bnps = nps, nps
        c_run = (THREADED[nps][0] if self.threaded else TEE_C.get(nps, 25.4 * nps * 1.1)) / 1000
        c_br = c_run
        if bnps != run_nps:
            c_br = TEE_M_REDUCING.get((run_nps, bnps), c_run * 1000 * 0.94) / 1000

        def port_len(i):
            return c_br if i == branch_i else c_run

        if not self.threaded:
            self.weld(pos, d, nps)
        center = pos + d * port_len(0)
        mat = self.M["fitting"]
        self.part("tee", (run_nps, bnps), threaded=self.threaded)
        # Body: run and branch as rods meeting at the centre, plus a blend sphere.
        ends = [center + dirs[i] * port_len(i) for i in range(3)]
        run_ends = [ends[i] for i in range(3) if i != branch_i]
        rr = self.r(run_nps) * (1.7 if self.threaded else 1)
        if self.threaded:
            rr = THREADED[nps][1] / 2000
        self.mb.rod(run_ends[0], run_ends[1], rr, mat, self.segs(run_nps))
        br_r = self.r(bnps) if not self.threaded else rr
        self.mb.rod(center, ends[branch_i], br_r, mat, self.segs(bnps), caps=False)
        self.mb.sphere(center, min(rr, br_r) * 1.02, mat, 2)
        self.points += [center.copy()] + [e.copy() for e in ends]
        for k, (pdir, steps) in enumerate(ports):
            i = k + 1
            pn = bnps if i == branch_i else run_nps
            start = ends[i]
            if not self.threaded:
                self.weld(start, dirs[i], pn)
            if steps and steps[0][0] == "flange":
                face = self.flange_body(start, dirs[i], pn)
                self.joints.append({"pos": face, "normal": dirs[i].copy(), "nps": pn})
                steps = steps[1:]
                start = face
                if not steps:
                    continue
            self._first = False
            self.walk(steps, direction=pdir, nps=pn, _pos=start)

    def build(self, location=(0, 0, 0), rotation=(0, 0, 0), collection=None):
        """One object per component, parented to an empty named after the spool (move the empty
        to place the spool). Each part record gets its object as part["obj"]."""
        import bpy
        from .core import _place
        root = _place(bpy.data.objects.new(self.name, None), location, rotation, (1, 1, 1), collection)
        root.empty_display_size = 0.3
        for rec in self.parts:
            if not rec["mb"].bm.verts:
                rec["mb"].bm.free()
                rec["obj"] = None
                continue
            obj = rec["mb"].build(collection=collection)
            obj.parent = root
            rec["obj"] = obj
        return root

    def bounds(self):
        lo = Vector((min(p.x for p in self.points), min(p.y for p in self.points), min(p.z for p in self.points)))
        hi = Vector((max(p.x for p in self.points), max(p.y for p in self.points), max(p.z for p in self.points)))
        return lo, hi


# ---------------------------------------------------------------- bolting

def stud_prefab(nps, mats):
    """One stud with a heavy hex nut at each end, along local Z, centred on the origin.
    Length and diameter from the Class 600 table (BOM stud lengths)."""
    from .core import prefab
    f = CL600[nps]
    d = f["d"] / 1000
    L = f["L"] / 1000
    mb = MeshBuilder(f"Stud_{nps}in")
    mb.rod((0, 0, -L / 2), (0, 0, L / 2), d / 2 * 0.93, mats["stud"], 8)
    nut_h = d * 1.0
    nut_r = d * 0.92   # across corners of a heavy hex nut ~1.84 d
    gap = L / 2 - nut_h - d * 0.35
    for s in (-1, 1):
        a = s * gap
        b = s * (gap + nut_h)
        mb.rod((0, 0, min(a, b)), (0, 0, max(a, b)), nut_r, mats["nut"], 6)
    return prefab(mb.build()), gap


def bolt_joint(face, normal, nps, prefab_info, blind_t, name, collection=None, twin=None):
    """Instance the studs of a flange joint whose gasket seat is at `face` (facing `normal`).
    blind_t: thickness (m) of what's bolted on the other side (a mating flange or a test blind).
    Studs straddle the centrelines, as drilled. Returns the instances."""
    from .core import instance
    pre, _ = prefab_info
    f = CL600[nps]
    n = normal.normalized()
    T = f["T"] / 1000
    # Joint centre: midway between the flange's back face and the blind's back face.
    flange_back = face - n * (T)
    blind_back = face + n * (GASKET_T / 1000 + blind_t)
    centre = (flange_back + blind_back) / 2
    u = _perp(n)
    v = n.cross(u)
    rot = n.to_track_quat("Z", "Y").to_euler()
    out = []
    for k in range(f["n"]):
        a = 2 * math.pi * (k + 0.5) / f["n"]
        p = centre + (u * math.cos(a) + v * math.sin(a)) * (f["BC"] / 2000)
        o = instance(pre, name, location=p, rotation=[math.degrees(x) for x in rot], collection=collection)
        if twin:
            o["twin"] = twin
        out.append(o)
    return out


def test_blind(target, face, normal, nps, mats, paint="blind", vent=False):
    """Test blind (blind flange) plus gasket bolted onto an open flange face. target: a Spool
    (gasket and blind become separate parts) or a MeshBuilder. Returns the blind's thickness (m)."""
    f = CL600[nps]
    n = normal.normalized()
    spool = target if isinstance(target, Spool) else None
    if spool:
        spool.part("gasket", nps, test=True)
    mb = spool.mb if spool else target
    mb.rod(face, face + n * (GASKET_T / 1000), f["R"] / 2000 * 1.08, mats["gasket"], 32)
    if spool:
        spool.part("test_blind", nps)
        mb = spool.mb
    p = face + n * (GASKET_T / 1000)
    T = f["T"] / 1000
    mb.rod(p, p + n * T, f["O"] / 2000, mats[paint], 40)
    if vent:   # fill/vent connection: half coupling, nipple and a small needle valve
        q = p + n * T
        mb.rod(q, q + n * 0.03, 0.022, mats["olet"], 12)
        mb.rod(q + n * 0.03, q + n * 0.09, 0.0107, mats["olet"], 10)
        mb.rod(q + n * 0.09, q + n * 0.13, 0.016, mats["plug"], 6)
        u = _perp(n)
        mb.beam(q + n * 0.11, q + n * 0.11 + u * 0.07, 0.01, mats["lever"], 0.005)
    return T
