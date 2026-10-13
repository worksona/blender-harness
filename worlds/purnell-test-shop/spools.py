"""The 21 spools of Pressure Test Pack 1 as a component-level data twin.

Every physical piece is its own object with its own record: each pipe piece, elbow, tee, reducer,
flange, olet, nipple, valve, plug and gasket is matched to its bill-of-materials item (heat number,
size, description, which of the item's quantity it is), and every weld bead to its line in the
drawing's weld table (welder, X-ray / MPI report, hardness test, visual). In the viewer a click
selects the spool; a second click on it drills down to the piece under the cursor.
"""

import math
import re

import numpy as np
from mathutils import Euler, Matrix, Vector

from harness import decal, instance, twin_record, twin_tag
from harness import piping

import pack

STAR_TOP = 0.585      # saddle height of the fluted stands
CONE_TOP = 0.69       # where a pipe sits in a cone's V saddle
SPOOL_COLORS = {2: "#7fd1ff", 1: "#9fe39a", 6: "#ffd27a", 8: "#ffb36b", 10: "#ff8a6b", 12: "#f06bd0"}
WELDERS = {"JI": "JI", "GC": "GC", "DJM": "DJM", "DF": "DF", "CS": "CS", "JI/DF": "JI and DF"}

KIND_LABEL = {"pipe": "Pipe", "elbow": "Elbow", "tee": "Tee", "reducer": "Reducer", "flange": "Flange",
              "olet": "Olet", "nipple": "Nipple", "valve": "Ball valve", "plug": "Plug", "gasket": "Gasket",
              "blind": "Blind flange (end plate)"}


def size_str(n):
    return "1/2" if n == 0.5 else str(int(n))


def material_spec(desc):
    m = re.search(r"A\d{3}-[A-Z0-9-]+(?: CL ?1)?", desc)
    return m.group(0) if m else ""


# ------------------------------------------------------------------ text

def label_text(sd):
    heat = next((b[1] for b in sd["bom"] if b[3].startswith("PIPE") and b[1]), "")
    return f"2024-062A  {sd['iso']}  HT {heat}" if heat else f"2024-062A  {sd['iso']}"


def weld_labels(sd):
    return [w["xray"] for w in sd["welds"] if w["type"] == "BW" and w["xray"]]


def marking_lines(spools):
    """Every string painted on the spools, for one shared text atlas."""
    lines = []
    for sd in spools:
        lines.append(label_text(sd))
        lines += weld_labels(sd)
    return list(dict.fromkeys(lines))


# ------------------------------------------------------------------ BOM matching

def match_item(sd, part):
    """The BOM line a built part comes from, or None (test equipment, thread caps)."""
    k, n, info = part["kind"], part["nps"], part["info"]
    thr = sd.get("threaded")
    for item, heat, size, desc, qty in sd["bom"]:
        d = desc.upper()
        if k == "pipe":
            L = info.get("length")
            if thr and L in (76, 100):
                if d.startswith("NIPPLE") and f"{L}MM" in d.replace(" ", ""):
                    return item
            elif d.startswith("PIPE") and size == size_str(n) and str(qty) == f"{L} mm":
                return item
        elif k == "nipple" and d.startswith("NIPPLE") and size == size_str(n):
            return item
        elif k == "elbow" and d.startswith("ELBOW") and size == size_str(n):
            return item
        elif k == "tee" and d.startswith("TEE") and size == f"{size_str(n[0])}X{size_str(n[1])}":
            return item
        elif k == "reducer" and d.startswith("REDUCER") and size == f"{n[0]}X{n[1]}":
            return item
        elif k == "flange":
            if thr and d.startswith("FLANGE, RED"):
                return item
            if d.startswith("FLANGE, WN") and size == size_str(n):
                return item
        elif k == "olet" and d.startswith(info.get("type", "")) and size == f"{size_str(n[0])}X{size_str(n[1])}":
            return item
        elif k == "valve" and d.startswith("VALVE") and size == size_str(n):
            return item
        elif k == "plug" and d.startswith("PLUG") and size == size_str(n):
            return item
        elif k == "gasket" and d.startswith("GASKET") and size == size_str(n):
            return item
        elif k == "blind" and "BLIND" in d:
            return item
    return None


def standard_note(part):
    """The dimensional standard a piece is modelled to, with its key dimensions."""
    k, n = part["kind"], part["nps"]
    if k == "elbow" and not part["info"].get("threaded"):
        return f"ASME B16.9 90° LR elbow, centre-to-end {piping.elbow_A(n):.0f} mm"
    if k == "flange" and n in piping.CL600:
        f = piping.CL600[n]
        return (f"ASME B16.5 Class 600 WN: OD {f['O']:.1f}, thickness {f['T']:.1f}, length through hub "
                f"{f['Y']:.1f} mm, {f['n']} bolts on a {f['BC']:.1f} mm circle")
    if k == "tee" and not part["info"].get("threaded"):
        return f"ASME B16.9 tee, centre-to-end {piping.TEE_C.get(n[0], 0)} mm"
    if k == "reducer":
        return f"ASME B16.9 {'eccentric' if part['info'].get('ecc') else 'concentric'} reducer, " \
               f"length {piping.REDUCER_H.get(tuple(n), 0)} mm"
    if k == "pipe":
        return f"ASME B36.10 OD {piping.OD[n]:.1f} mm"
    return ""


# ------------------------------------------------------------------ build

def build_spool(sd, M, place, studs, stands, atlas, rng, cribbing=None, sid=None):
    """Build one spool component by component, bolt test blinds on its open flanges, set it on
    stands the way it sat for the test, write its paint markings, and create its records.
    Returns the spool's root object."""
    sid = sid or f"spool-{sd['ctrl']}"
    sp = piping.Spool(sd["iso"], sd["nps"], M, sch=sd["sch"], branch_nps=sd.get("branch_nps"),
                      threaded=sd.get("threaded", False))
    sp.walk(sd["route"], direction=sd["start"])
    paints = place.get("blinds") or []
    joints = []
    for k, j in enumerate(sp.joints):
        if j.get("mated"):
            joints.append((j, j["mate_t"]))
            continue
        paint = paints[k] if k < len(paints) else ("black" if rng.random() < 0.6 else "rust")
        t = piping.test_blind(sp, j["pos"], j["normal"], j["nps"], M, paint=paint, vent=(k == 0))
        joints.append((j, t))
    root = sp.build(collection="Spools")
    twin_tag(root, sid)

    # Orient, then sit the lowest horizontal run on its stands (or the whole spool on cribbing).
    R = Euler([math.radians(a) for a in place["rot"]]).to_matrix().to_4x4()
    co = []
    for rec in sp.parts:
        if rec.get("obj"):
            me = rec["obj"].data
            v = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", v)
            rec["bbox"] = (v.reshape(-1, 3).min(axis=0), v.reshape(-1, 3).max(axis=0))
            co.append(v.reshape(-1, 3))
    co = np.concatenate(co) @ np.array(R.to_3x3()).T
    lo, hi = co.min(axis=0), co.max(axis=0)
    runs = [(R @ a, R @ b, r) for a, b, r in sp.runs]
    runs = [(a, b, r) for a, b, r in runs if abs(a.z - b.z) < 0.01]
    if runs:
        base = min(a.z - r for a, b, r in runs)
        low = [(a, b, r) for a, b, r in runs if a.z - r < base + 0.02]
        big = max(r for _, _, r in low) * 2000 / 25.4 > 4      # NPS > 4 sits on star stands
        z_off = (STAR_TOP if big else CONE_TOP) - base
    else:
        low, big = [], True
        z_off = 0.1 - lo[2]
    z_off = max(z_off, 0.03 - lo[2])
    T = Matrix.Translation((place["xy"][0] - (lo[0] + hi[0]) / 2, place["xy"][1] - (lo[1] + hi[1]) / 2, z_off))
    W = T @ R
    root.matrix_world = W

    # Stands under the lowest runs: only runs long enough to carry one (short runs between
    # fittings would put a stand under an elbow or a riser), at least 0.8 m apart.
    long_runs = [q for q in low if (q[1] - q[0]).length >= 0.6] or \
        ([max(low, key=lambda q: (q[1] - q[0]).length)] if low else [])
    placed = []
    for a, b, r in long_runs:
        a, b = T @ a, T @ b
        length = (b - a).length
        n = max(1, math.ceil(length / 2.6))
        d = (b - a).normalized()
        run_yaw = math.degrees(math.atan2(d.y, d.x)) - 90
        kind = "star" if big else "cone"
        for i in range(n):
            p = a + (b - a) * ((i + 0.5) / n)
            if any((p - q).length < 0.8 for q in placed):
                continue
            placed.append(p)
            pre = stands[kind][rng.randrange(len(stands[kind]))]
            instance(pre, "PipeStand", (p.x, p.y, 0), (0, 0, run_yaw + rng.uniform(-4, 4)),
                     collection="Pipe stands")
    if not runs and cribbing:
        cribbing(place["xy"], place["rot"][2])

    stud_ids = stud_records(sd, sid) if "bom" in sd else {}
    sd["_stud_ids"] = stud_ids
    for j, t in joints:                        # studs and nuts on every flange joint
        face = W @ j["pos"]
        normal = (W.to_3x3() @ j["normal"]).normalized()
        piping.bolt_joint(face, normal, j["nps"], studs[j["nps"]], t, "Stud", collection="Bolting",
                          twin=stud_ids.get(j["nps"], sid))

    if "bom" in sd:
        component_records(sd, sid, sp)
        markings(sd, sp, W, runs, T, atlas)
    else:
        for rec in sp.parts:
            if rec.get("obj"):
                twin_tag(rec["obj"], sid)
    return root


STUD_SIZE = {"5/8": 2, "1": 6, "1-1/8": 8, "1-1/4": (10, 12), "1-1/2": 16}


def stud_records(sd, sid):
    """Records for the BOM's stud-bolt sets, keyed by the flange size they bolt up."""
    out = {}
    flange_sizes = sorted({int(b[2]) for b in sd["bom"] if b[3].startswith("FLANGE") and b[2].isdigit()})
    for item, heat, size, desc, qty in sd["bom"]:
        if not desc.startswith("("):
            continue
        fits = STUD_SIZE.get(size)
        fits = fits if isinstance(fits, tuple) else (fits,)
        nps = next((n for n in flange_sizes if n in fits), None)
        if sd.get("threaded"):
            nps = 2
        if nps is None:
            continue
        rid = f"{sid}/studs-{item}"
        n = re.match(r"\((\d+)\)", desc)
        twin_record(rid, f"Stud bolts · item {item}", f'{size}" · {sd["iso"]}', group="Components",
                    parent=sid, listed=False,
                    fields=[("Spool", sd["iso"]), ("BOM item", item), ("Description", desc),
                            ("Sets", qty), ("Per set", f"{n.group(1)} studs, 2 heavy hex nuts each" if n else "-"),
                            ("Fits", f'{nps}" Class 600 flanges'),
                            ("Material", "ASTM A193-B7M studs, A194-2HM nuts")],
                    notes=["In the test the open flanges are closed with test blinds on studs like these."])
        out[nps] = rid
    return out


def component_records(sd, sid, sp):
    """A record per built piece and per weld, tagged on its object."""
    letters = sd.get("weld_order") or [w["id"] for w in sd["welds"]]
    by_letter = {w["id"]: w for w in sd["welds"]}
    weld_ids = {}
    for i, w in enumerate(sp.welds):
        letter = letters[i] if i < len(letters) else None
        rid = f"{sid}/weld-{letter}" if letter else f"{sid}/weld-x{i}"
        weld_ids[id(w["part"])] = rid
        w["letter"] = letter
        w["record"] = rid

    # Which welds join each piece: weld positions touching the piece's bounding box
    def touching(rec):
        lo, hi = rec["bbox"]
        out = []
        for w in sp.welds:
            p = np.array(w["pos"])
            if np.all(p >= lo - 0.006) and np.all(p <= hi + 0.006) and w.get("letter"):
                out.append(w["letter"])
        return sorted(set(out))

    counts = {}
    first_part_of_item = {}
    items = {b[0]: b for b in sd["bom"]}
    for rec in sp.parts:
        obj = rec.get("obj")
        if obj is None:
            continue
        kind = rec["kind"]
        if kind == "weld":
            rid = weld_ids[id(rec)]
            twin_tag(obj, rid)
            continue
        if kind in ("test_blind", "misc") or (kind == "gasket" and rec["info"].get("test") and
                                               match_item(sd, rec) is None):
            twin_tag(obj, "test-equipment")
            continue
        item = match_item(sd, rec)
        rid = f"{sid}/part-{rec['index']}"
        twin_tag(obj, rid)
        label = KIND_LABEL.get(kind, kind.title())
        if kind == "olet":
            label = rec["info"].get("type", "Olet")
        if kind == "cap":
            twin_record(rid, "Thread protector", sd["iso"], group="Components", parent=sid, listed=False,
                        fields=[("What", "Plastic cap on an open TOL thread (not a BOM item)")])
            continue
        if item is None:
            twin_record(rid, label, sd["iso"], group="Components", parent=sid, listed=False,
                        fields=[("BOM item", "none matched"), ("Size", str(rec["nps"]))])
            continue
        _, heat, size, desc, qty = items[item]
        counts[item] = counts.get(item, 0) + 1
        first_part_of_item.setdefault(item, rid)
        qty_n = int(qty) if isinstance(qty, int) else 1
        fields = [
            ("Spool", sd["iso"]),
            ("BOM item", item),
            ("Heat no.", heat or "not recorded"),
            ("Size", f'{size}"'),
            ("Description", desc),
            ("Material", material_spec(desc) or "per description"),
            ("Quantity on spool", qty),
        ]
        if qty_n > 1:
            fields.append(("This piece", f"{counts[item]} of {qty_n}"))
        if kind == "pipe":
            fields.append(("Cut length", f"{rec['info'].get('length')} mm"))
        note = standard_note(rec)
        if note:
            fields.append(("Modelled to", note))
        joined = touching(rec)
        if joined:
            fields.append(("Welds", ", ".join(joined)))
        notes = []
        if heat in ("NEED HT#", "NO HT #S"):
            notes.append(f"Heat number not traced on the drawing ('{heat}').")
        twin_record(rid, f"{label} · item {item}", f'{size}" · heat {heat or "-"} · {sd["iso"]}',
                    group="Components", parent=sid, listed=False, fields=fields, notes=notes,
                    color=SPOOL_COLORS.get(sd["nps"]))

    # Weld records
    xrays = {}
    for s in pack.SPOOLS:
        for w in s["welds"]:
            if w["xray"]:
                xrays.setdefault(w["xray"], []).append(f"{s['iso']} weld {w['id']}")
    for w in sp.welds:
        letter, rid = w.get("letter"), w["record"]
        if not letter:
            twin_record(rid, "Weld (not on the drawing)", sd["iso"], group="Welds", parent=sid, listed=False,
                        fields=[("Type", w["type"]), ("Why it's here", "Modelled for the second TOL in the BOM; "
                                                       "the drawing's weld table doesn't list it.")])
            continue
        wd = by_letter.get(letter, {})
        nde = []
        if wd.get("xray"):
            nde.append(("Radiography", f"100% RT, report {wd['xray']}"))
        if wd.get("mpi"):
            nde.append(("Magnetic particle", f"report {wd['mpi']}"))
        if wd.get("ht"):
            nde.append(("Hardness test", f"report {wd['ht']}"))
        fields = [("Spool", sd["iso"]), ("Weld", letter),
                  ("Joint", "Butt weld (full penetration)" if wd.get("type") == "BW" else
                   "Branch / attachment weld (LET)" if wd.get("type") == "LET" else "not recorded"),
                  ("Size", wd.get("size") or "-"), ("Welder", WELDERS.get(wd.get("welder"), wd.get("welder") or "-")),
                  ("WPS", "PES-1N (Rev. 2)")] + nde + \
                 [("Visual", f"VT by {wd['vt']}" if wd.get("vt") else "-"),
                  ("Pressure test", "N/A (dummy leg)" if sd.get("dummy") else "Pack 1, 2024-04-29, accepted")]
        notes = []
        if wd.get("xray") and len(xrays.get(wd["xray"], [])) > 1:
            notes.append(f"Report {wd['xray']} is also recorded for: " +
                         ", ".join(x for x in xrays[wd["xray"]] if x != f"{sd['iso']} weld {letter}"))
        if not wd.get("type"):
            notes.append("This weld's row is blank on the drawing.")
        title = f"Weld {letter}" + (f" · {wd['xray']}" if wd.get("xray") else f" · {wd['mpi']}" if wd.get("mpi") else "")
        twin_record(rid, title, f"{wd.get('size', '')} {wd.get('type', '')} · {sd['iso']}", group="Welds",
                    parent=sid, listed=False, fields=fields, notes=notes, color="#e8a060")
    for rid in sd.get("_stud_ids", {}).values():
        first_part_of_item.setdefault(int(rid.rsplit("-", 1)[1]), rid)
    sd["_rows"] = {"bom": [first_part_of_item.get(b[0]) for b in sd["bom"]],
                   "welds": [f"{sid}/weld-{w['id']}" if any(x.get("letter") == w["id"] for x in sp.welds) else None
                             for w in sd["welds"]]}


def markings(sd, sp, W, runs, T, atlas):
    """Paint-marker writing: job, line and heat number along the longest run; each butt weld's
    X-ray report number beside it, as the fitters mark them."""
    image, rects, img_aspect = atlas

    def put(text, centre, direction, radius, height, name):
        if text not in rects:
            return
        u0, v0, u1, v1 = rects[text]
        aspect = (u1 - u0) / (v1 - v0) * img_aspect
        decal(name, image, (height * aspect, height), centre + Vector((0, 0, radius)),
              (0, 0, math.degrees(math.atan2(direction.y, direction.x))), wrap_radius=radius,
              collection="Markings", uv=rects[text], material_name="paint_marker")

    text = label_text(sd)
    if runs and text in rects:
        a, b, r = max(runs, key=lambda q: (q[1] - q[0]).length * q[2])
        a, b = T @ a, T @ b
        u0, v0, u1, v1 = rects[text]
        aspect = (u1 - u0) / (v1 - v0) * img_aspect
        h = max(0.03, min(0.07, r * 0.42))
        h = min(h * aspect, (b - a).length * 0.8) / aspect
        put(text, (a + b) / 2, (b - a).normalized(), r, h, f"{sd['iso']}_marking")
    by_letter = {w["id"]: w for w in sd["welds"]}
    for w in sp.welds:
        wd = by_letter.get(w.get("letter"))
        if not wd or wd["type"] != "BW" or not wd["xray"]:
            continue
        d = (W.to_3x3() @ w["dir"]).normalized()
        if abs(d.z) > 0.3:
            continue                           # only on horizontal pipe, where it can be read
        r = piping.OD[w["nps"]] / 2000
        p = W @ w["pos"] + d * (0.07 + r * 0.3)
        put(wd["xray"], p, d, r, 0.03 if w["nps"] <= 2 else 0.05, f"{sd['iso']}_{w['letter']}_mark")


# ------------------------------------------------------------------ spool record

def spool_record(sd):
    sid = f"spool-{sd['ctrl']}"
    size = f'{sd["nps"]}"'
    kind = "Dummy leg" if sd.get("dummy") else "Threaded assembly" if sd.get("threaded") else "Spool"
    bw = [w for w in sd["welds"] if w["type"] == "BW"]
    fields = [
        ("Line", sd["line"]), ("Control no.", sd["ctrl"]), ("Revision", sd["rev"]),
        ("Type", kind), ("Size / schedule", f"{size} Sch {sd['sch']}"),
        ("Insulation spec", sd["insulation"]), ("Painting", sd["paint"]), ("Drawn", f"{sd['date']} (SEC)"),
        ("Butt welds", f"{len(bw)} (100% RT)" if bw else "none (threaded)" if sd.get("threaded") else "0"),
        ("Test", "N/A (not pressure tested)" if sd.get("dummy") else "Water, 15,307 kPa min, 15 min hold"),
        ("Result", "N/A" if sd.get("dummy") else "Accepted 2024-04-29 (Pack 1)"),
    ]
    rows = sd.get("_rows", {})
    tables = [{"title": "Bill of materials", "columns": ["Item", "Heat no.", "Size", "Description", "Qty"],
               "rows": [[str(i), h, s, d, str(q)] for i, h, s, d, q in sd["bom"]],
               "row_ids": rows.get("bom")}]
    if sd["welds"]:
        tables.append({"title": "Weld information",
                       "columns": ["Weld", "Size", "Type", "Welder", "X-ray", "MPI", "HT", "VT"],
                       "rows": [[w["id"], w["size"], w["type"], w["welder"], w["xray"], w["mpi"], w["ht"],
                                 w["vt"]] for w in sd["welds"]],
                       "row_ids": rows.get("welds")})
    notes = [f"Inferred: {n}" for n in sd.get("inferred", [])] + sd.get("notes", [])
    notes.append("Click a BOM or weld row to find that piece; click the spool again in 3D to pick a piece.")
    twin_record(sid, sd["iso"], f"Control {sd['ctrl']} · {size} · {kind}", group="Spools",
                fields=fields, tables=tables, notes=notes, color=SPOOL_COLORS.get(sd["nps"], "#6cb6ff"),
                images=[{"title": "Isometric drawing", "src": f"docs/iso-ctrl{sd['ctrl']:02d}.png"}])


def test_equipment_record():
    twin_record("test-equipment", "Test blinds and temporary fittings", "Hydrotest set-up, not BOM items",
                group="Test", color="#8a8f96",
                fields=[("Test blinds", "Blind flanges bolted on every open flange for the test, with a "
                                        "fill/vent fitting on one per spool"),
                        ("Bolting", "Studs and nuts on test blinds are the shop's test bolting"),
                        ("Thread caps", "Plastic protectors on open TOL threads")])
