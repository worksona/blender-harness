"""North Field Build: Purnell's document-controlled construction process as a campus you can
replay. Five stations (home office, vendor, fab shop, field site, QC) on one site, and the 21
spools of Pressure Test Pack 1 (job 2024-062A for Arc Resources) followed from isometric to
delivery: material shipped, put on hold at receiving for missing MTRs, released, fabricated one
after another, NDE'd, hydrotested as one pack, primed, and hauled to 10-16 in three trips.
Documents fly between the stations as they are issued, every spool's record shows which it has
at any moment, and the crews walk, weld and inspect through it all.

The layout is a stylised campus (the real vendor is far away); the spools and their test pack
are real, the schedule around them is reconstructed (see scenario.py). The field site is a
laydown yard: the pack has no drawing of where the spools tie in, so installation is not
modelled until the reference drawings are added.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "purnell-test-shop"))

from mathutils import Vector  # noqa: E402

from harness import *  # noqa: E402,F403
from harness import industrial as ind  # noqa: E402
from harness import piping  # noqa: E402

import campus  # noqa: E402
import pack  # noqa: E402  (../purnell-test-shop: the test pack's data)
import scenario as S  # noqa: E402

META = {
    "title": "North Field Build",
    "description": "Purnell's construction process as a replayable campus: the 21 spools of "
                   "Pressure Test Pack 1 from isometric to delivery, through a document hold, "
                   "fabrication, hydrotest and three trips to site, with the crews and paperwork "
                   "that move them.",
    "tags": ["construction sim", "data twin", "piping", "industrial"],
    "seed": 62,
    "private": True,          # built around a client job
    "render": {"res": "1920x1080", "samples": 64},
    "viewer": {"exposure": 1.0},
}

PAD_MARGIN = 12.0
SPOOL_COLORS = {1: "#9fe39a", 2: "#7fd1ff", 6: "#ffd27a", 8: "#ffb36b", 10: "#ff8a6b", 12: "#f06bd0"}


# ------------------------------------------------------------------ ground

def in_pad(x, y, margin=0.0):
    for st in S.STATIONS.values():
        x0, y0, x1, y1 = st["pad"]
        if x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin:
            return True
    return False


def pad_blend(x, y):
    """1 on a station pad, fading to 0 PAD_MARGIN metres outside it."""
    best = 0.0
    for st in S.STATIONS.values():
        x0, y0, x1, y1 = st["pad"]
        dx = max(x0 - x, 0, x - x1)
        dy = max(y0 - y, 0, y - y1)
        d = math.hypot(dx, dy)
        best = max(best, 1.0 - min(d / PAD_MARGIN, 1.0))
    if abs(y - S.ROAD_Y) < S.ROAD_W:
        best = max(best, 1.0 - max(abs(y - S.ROAD_Y) - S.ROAD_W / 2, 0) / 3.5)
    return best * best * (3 - 2 * best)


def height(x, y):
    z = 0.45 * fbm(x, y, scale=60, seed=7) + 0.12 * fbm(x, y, scale=9, seed=3)
    return z * (1.0 - pad_blend(x, y))


# ------------------------------------------------------------------ people

def crew(prefix, n, shifts, rng, vest=None, helmet="#f2f2f2"):
    """n workers sharing a set of shifts, each starting at a different point of the path so they
    spread out, with their own clothes."""
    vests = [vest] if vest else ["#f28a1a", "#e6d81a", "#f28a1a", "#1fb85a"]
    pants = ["#2d3f6b", "#444a52", "#5a4a3a", "#2d3f6b"]
    skins = ["#c99a73", "#8d5a3c", "#e0b48f", "#6b4a30"]
    for i in range(n):
        my = []
        for s in shifts:
            path = list(s["path"])
            k = (i * 2) % max(len(path), 1)
            if s.get("loop", True) and len(path) > 1:
                path = path[k:] + path[:k]
                tasks = {(j - k) % len(path): v for j, v in (s.get("tasks") or {}).items()}
            else:
                tasks = dict(s.get("tasks") or {})
            my.append(dict(s, path=path, tasks=tasks))
        p = person(f"{prefix}{i + 1}", vest=vests[i % len(vests)], shirt=rng.choice(["#3b4a5a", "#5a3b3b", "#2f4f3f"]),
                   pants=pants[i % len(pants)], skin=skins[(i + len(prefix)) % len(skins)], helmet=helmet,
                   location=my[0]["path"][0] if my else (0, 0, 0))
        twin_actor(p, my, speed=rng.uniform(1.0, 1.3))


def shift(start, end, path, tasks=None, loop=True):
    return dict(start=start, end=end, path=path, tasks=tasks or {}, loop=loop)


def people(rng):
    st = S.STATIONS
    # 1 Home office: staff between the door, the car park and the smokers' corner.
    ox, oy = st["office"]["centre"]
    crew("Office", 6, [shift(0, S.END, [(ox, oy + 11), (ox + 6, oy + 18), (ox + 22, oy + 24), (ox + 12, oy + 30),
                                       (ox - 14, oy + 26), (ox - 8, oy + 14)],
                             {1: (6, "talk"), 2: (5, "idle"), 4: (8, "talk")})], rng,
         vest="#5a6f8a", helmet=None)
    # 2 Vendor yard: pickers between the racks, loaders at the dock while the truck is there.
    vx, vy = st["vendor"]["centre"]
    crew("Yard", 5, [shift(0, S.END, [(vx - 44, 66), (vx - 20, 66), (vx - 20, 80), (vx + 10, 80), (vx + 24, 66),
                                      (vx + 44, 74), (vx + 10, 84)], {1: (7, "carry"), 3: (6, "carry"), 4: (5, "inspect")})], rng)
    crew("Loader", 3, [shift(6.0, 7.1, [(vx - 5, 78), (vx + 5, 78), (vx + 5, 82), (vx - 8, 82)],
                             {0: (5, "carry"), 2: (6, "carry")}),
                       shift(9.9, 11.5, [(vx - 5, 78), (vx + 5, 78), (vx + 5, 82), (vx - 8, 82)],
                             {1: (6, "inspect"), 3: (5, "talk")})], rng, vest="#e6d81a")
    # 3 Fab shop: receiving inspectors at the dock during the hold, welders and the NDE tech
    # moving down the rows of spools as each comes up, shop hands crossing the yard all the time.
    fx, fy = st["fab"]["centre"]
    slots = [S.yard_slot(i) for i in range(len(S.CTRLS))]
    crew("Receiver", 2, [shift(8.25, 12.6, [(120, 71), (116, 69), (118, 66)],
                               {0: (12, "inspect"), 1: (6, "talk"), 2: (5, "inspect")})], rng, vest="#1fb85a")
    weld_shifts = []
    for i, (x, y, _) in enumerate(slots):
        fs, fe = S.fab_window(i)
        weld_shifts.append(shift(fs, fe, [(x - 1.6, y - 1.4), (x + 1.8, y - 1.4), (x + 1.8, y + 1.4), (x - 1.6, y + 1.4)],
                                 {0: (12, "weld"), 1: (9, "weld"), 2: (10, "weld"), 3: (5, "carry")}))
    crew("Welder", 3, weld_shifts + [
        shift(S.HYDROTEST[0] - 1.5, S.PAINTED, [(74, 86), (144, 86), (144, 58), (74, 58)],
              {0: (8, "carry"), 1: (10, "inspect"), 2: (6, "talk"), 3: (6, "carry")})], rng)
    nde_shifts = [shift(*S.nde_window(i), [(x + 1.0, y - 1.8), (x + 2.4, y + 1.6)], {0: (16, "inspect"), 1: (12, "inspect")})
                  for i, (x, y, _) in enumerate(slots)]
    crew("NDE", 1, nde_shifts + [shift(S.HYDROTEST[0], S.HYDROTEST[1] + 0.3, [(108, 64)], {0: (60, "inspect")})],
         rng, vest="#f2f2f2")
    crew("Shop", 4, [shift(0, S.END, [(fx - 12, 62), (fx - 12, 82), (fx + 12, 84), (fx + 22, 80), (fx + 14, 62)],
                           {1: (6, "carry"), 2: (8, "idle"), 3: (5, "talk")})], rng)
    # 4 Field site: a site survey before the pack comes, receiving crews for each trip, then a
    # couple of hands checking the laydown while the tie-ins wait.
    lx, ly = 10, -90
    crew("Survey", 3, [shift(20.0, 30.0, [(-50, -72), (-10, -72), (30, -72), (70, -74), (66, -112), (20, -114), (-30, -112)],
                             {0: (10, "survey"), 2: (8, "survey"), 4: (10, "survey"), 6: (6, "talk")})], rng)
    recv = []
    for k, tr in enumerate(S.TRIPS):
        t0 = tr["t0"] + S.TRIP_DRIVE - 0.2
        pts = [S.laydown_slot(i) for i in tr["spools"]]
        path = [(lx - 8, -78), (lx + 8, -78)] + [(p[0], p[1] + 3) for p in pts[::2]]
        recv.append(shift(t0, t0 + S.TRIP_UNLOAD + 0.6, path, {0: (6, "carry"), 1: (8, "inspect"), 3: (6, "carry"), 5: (6, "inspect")}))
    crew("Crew", 6, recv + [shift(S.delivered_at(20) + 0.5, S.END, [(-60, -76), (80, -76), (80, -110), (-60, -110)],
                                  {1: (6, "inspect"), 3: (6, "talk")})], rng)
    crew("Inspector", 1, [shift(S.delivered_at(k * 7) - 0.1, S.delivered_at(k * 7) + 0.9,
                                [(S.laydown_slot(i)[0], S.laydown_slot(i)[1] - 2.5) for i in tr["spools"]],
                                {j: (10, "inspect") for j in range(0, 7, 2)}) for k, tr in enumerate(S.TRIPS)],
         rng, vest="#f2f2f2")
    # 5 QC: between the trailers, a lot of talking.
    qx, qy = st["qc"]["centre"]
    crew("QC", 3, [shift(0, S.END, [(qx - 10, qy + 10), (qx + 8, qy + 10), (qx + 8, qy - 4), (qx - 12, qy - 4)],
                         {0: (8, "talk"), 2: (10, "inspect"), 3: (5, "idle")})], rng, vest="#5a6f8a", helmet=None)


# ------------------------------------------------------------------ the spools

def spool_mats():
    return {
        "pipe": material("pipe_black", "#2c2d30", roughness=0.4, metallic=0.3),
        "fitting": material("fitting_black", "#34363a", roughness=0.42, metallic=0.3),
        "flange": material("flange_forged", "#6d6a66", roughness=0.5, metallic=0.5),
        "weld": material("weld_bead", "#40372f", roughness=0.6, metallic=0.5),
        "olet": material("olet_forged", "#57534d", roughness=0.45, metallic=0.6),
        "valve": material("valve_blue", "#2c5fae", roughness=0.35, metallic=0.1),
        "lever": material("valve_lever", "#141414", roughness=0.5),
        "plug": material("plug_steel", "#8d8a84", roughness=0.4, metallic=0.75),
        "blind": material("blind_green", "#3f7a3c", roughness=0.5),
        "blind_paint": material("blind_green", "#3f7a3c", roughness=0.5),
        "cap": material("thread_cap", "#c8322a", roughness=0.6),
        "gasket": material("gasket_spiral", "#aeb2b4", roughness=0.35, metallic=0.8),
    }


def rotz(p, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2])


def build_spool(i, sd, PM, stand, crib, truck_keys):
    """Build spool i from its isometric route, centre it on its root (origin at the bottom
    centre so it sits on stands, a deck or cribbing), and key its journey: fab yard slot from
    its fabrication start, then its trip on the flatbed, then its laydown slot at 10-16."""
    sid = f"spool-{sd['ctrl']}"
    sp = piping.Spool(f"Spool-{sd['ctrl']}", sd["nps"], PM, sch=sd["sch"], branch_nps=sd.get("branch_nps"),
                      threaded=sd.get("threaded", False))
    sp.walk(sd["route"], direction=sd["start"])
    root = sp.build(collection="Spools")
    twin_tag(root, sid)
    lo, hi = sp.bounds()
    r = piping.OD[sd["nps"]] / 2000
    # Lay the spool out flat, as it would be on stands or cribbing: whichever extent is the
    # smallest becomes vertical (a riser lies down, an L lies on its side).
    ex, ey, ez = hi.x - lo.x, hi.y - lo.y, hi.z - lo.z
    rot = (0, 0, 0)
    if ex < ez and ex <= ey:            # rotate about Y: (x, y, z) -> (z, y, -x)
        rot = (0, math.radians(90), 0)
        lo, hi = Vector((lo.z, lo.y, -hi.x)), Vector((hi.z, hi.y, -lo.x))
    elif ey < ez and ey < ex:           # rotate about X: (x, y, z) -> (x, -z, y)
        rot = (math.radians(90), 0, 0)
        lo, hi = Vector((lo.x, -hi.z, lo.y)), Vector((hi.x, -lo.z, hi.y))
    for rec in sp.parts:
        if rec.get("obj"):
            rec["obj"].rotation_euler = rot
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z - r))
    for rec in sp.parts:
        if rec.get("obj"):
            rec["obj"].location = -centre
    size = (hi.x - lo.x, hi.y - lo.y)
    # Journey
    yard = S.yard_slot(i)
    fs, fe = S.fab_window(i)
    k = S.trip_of(i)
    tr = S.TRIPS[k]
    kth = list(tr["spools"]).index(i)
    off = S.bed_offset(kth)
    t0 = tr["t0"]
    keys = [(fs, (yard[0], yard[1], 0.55), 0), (t0 - 0.01, (yard[0], yard[1], 0.55), 0)]
    for t, p, yaw in truck_keys:
        if t0 <= t <= t0 + S.TRIP_DRIVE:
            o = rotz(off, yaw)
            keys.append((t, (p[0] + o[0], p[1] + o[1], o[2]), yaw))
    lay = S.laydown_slot(i)
    keys += [(t0 + S.TRIP_DRIVE + 0.1 + kth * 0.08, (lay[0], lay[1], 0.4), 0)]
    twin_motion(root, keys)
    # Stands in the yard, cribbing at the laydown (long enough for the spool).
    for j, dx in enumerate((-0.7, 0.7)):
        instance(stand, f"Stand_{sd['ctrl']}_{j}", (yard[0] + dx * max(1, size[0] / 2), yard[1], 0), collection="Fab shop")
        instance(crib, f"Crib_{sd['ctrl']}_{j}", (lay[0] + dx * max(1, size[0] / 2), lay[1], 0), collection="Field")
    return sp, root


def spool_record(i, sd):
    size = f'{sd["nps"]}"'
    sid = f"spool-{sd['ctrl']}"
    bw = [w for w in sd["welds"] if w["type"] == "BW"]
    kind = "Dummy leg" if sd.get("dummy") else "Threaded assembly" if sd.get("threaded") else "Spool"
    fs, fe = S.fab_window(i)
    tr = S.trip_of(i)
    fields = [("Job", f"{pack.REPORT['job']} · {pack.REPORT['customer']}"), ("Line", sd["line"]),
              ("Control no.", sd["ctrl"]), ("Type", kind), ("Purchase order", S.PO),
              ("Size / schedule", f"{size} Sch {sd['sch']}"), ("Insulation", sd["insulation"]),
              ("Butt welds", f"{len(bw)} (100% RT)" if bw else "none"),
              ("Fabricated", f"days {fs:.1f} to {fe:.1f} (reconstructed)"),
              ("Hydrotest", "N/A" if sd.get("dummy") else "Accepted 2024-04-29 (Pack 1)"),
              ("To site", f"trip {tr + 1}, day {S.TRIPS[tr]['t0']:.0f}"),
              ("Installed", "not modelled: no tie-in drawing in the pack")]
    tables = [{"title": "Bill of materials", "columns": ["Item", "Heat no.", "Size", "Description", "Qty"],
               "rows": [[str(a), h, s, d, str(q)] for a, h, s, d, q in sd["bom"]]}]
    if sd["welds"]:
        tables.append({"title": "Weld information", "columns": ["Weld", "Size", "Type", "Welder", "X-ray", "MPI", "HT", "VT"],
                       "rows": [[w["id"], w["size"], w["type"], w["welder"], w["xray"], w["mpi"], w["ht"], w["vt"]]
                                for w in sd["welds"]]})
    twin_record(sid, sd["iso"], f"Control {sd['ctrl']} · {size} {kind.lower()} · {S.PO}", group="Spools",
                fields=fields, tables=tables, color=SPOOL_COLORS.get(sd["nps"], "#6cb6ff"), docs=S.docs_for(i),
                images=[{"title": "Isometric drawing", "src": f"docs/iso-ctrl{sd['ctrl']:02d}.png"}],
                notes=["Isometric, BOM, weld table and hydrotest are from Pressure Test Pack 1; the purchasing, "
                       "shipping, hold and fabrication dates are reconstructed."])


# ------------------------------------------------------------------ records

STATION_ROLE = {
    "office": "Engineering issues isometrics, ITPs and procedures; purchasing issues POs",
    "vendor": "Supplies pipe, fittings and flanges with certificates and MTRs",
    "fab": "Receives material, fabricates, NDE, hydrotest, paint",
    "field": "Receives spools at the laydown; installation waits on the tie-in drawings",
    "qc": "Closes NCRs, collects test reports, assembles the turnover dossier",
}


def records(objs):
    R = pack.REPORT
    twin_record("job", f"{R['job']} · {R['project']}", f"{R['company']} for {R['customer']} · {R['site']}",
                overview=True, color="#6cb6ff",
                fields=[("Process", "Home office → vendors → fab shop → field site → QC / turnover"),
                        ("Replay", f"{S.EPOCH} + {S.END:.0f} days; ▶ on the replay bar, drag to scrub"),
                        ("Spools", "The 21 spools of Pressure Test Pack 1 (under Spools, or click one)"),
                        ("Hold", "Day 8: material received without its MTRs; released day 12"),
                        ("Open", "Installation, field inspection and turnover: the pack has no tie-in drawings")],
                notes=["Click a building for its station and workload; click a spool, truck or the shipment "
                       "for its record. Objects glow with their state: orange in progress, red on hold, "
                       "green released, yellow at risk (waiting), blue turned over.",
                       "Station workloads are illustrative; the spools' documents are the real ones."])
    for key, st in S.STATIONS.items():
        rows = [[name, f"{done} / {total}", f"{round(100 * done / total)}%"] for name, done, total in S.WORKLOAD[key]]
        rid = f"st-{key}"
        twin_record(rid, f"{st['n']} · {st['title']}", group="Stations", color="#ffd56b",
                    fields=[("Station", st["n"]), ("Role", STATION_ROLE[key])],
                    tables=[{"title": "Document workload (illustrative)", "columns": ["Document", "Done", ""], "rows": rows}],
                    notes=(["Placeholder: a laydown yard at 10-16-062-04 W6M. The spools' tie-in points are not "
                            "in the test pack; add the P&IDs, plot plan or tie-in drawings to docs/ to model them."]
                           if key == "field" else []))
        for o in objs.get(key, []):
            twin_tag(o, rid)
    twin_record("ncr-1", "Document hold: MTRs missing", f"{S.PO} · heats AG2198, AG2073", group="Holds", color="#ff6b5e",
                fields=[("Raised", "Receiving inspection, fab shop, day 8"), ("Reason", "Material test reports not in the vendor data book"),
                        ("Action", "Vendor documents requested day 10; MTRs received day 12"), ("Released", "Day 12 (4 days held)")],
                docs=[("Vendor data book", 6.5), ("MTRs", 12.4)])
    twin_record("truck-1", "Flatbed · vendor delivery", f"{S.PO} material to the fab shop", group="Material", color="#ffb36b",
                fields=[("Load", "Pipe, fittings, flanges, olets and valves for 21 spools"), ("Leaves vendor", "Day 7"),
                        ("At fab dock", "Day 8.3 (receiving inspection)")])
    twin_record("truck-2", "Flatbed · spools to site", "Primed spools to 10-16-062-04 W6M, three trips", group="Material",
                color="#ffb36b", fields=[(f"Trip {k + 1}", f"day {tr['t0']:.0f}: spools {', '.join(str(S.CTRLS[i]) for i in tr['spools'])}")
                                         for k, tr in enumerate(S.TRIPS)])
    twin_record("shipment", "Shipment: pipe and fittings", f"{S.PO} · as received", group="Material", color="#ffb36b",
                fields=[("Contents", "Pipe (heats AG2198, AG2073), elbows, flanges, olets, valves"),
                        ("Status", "Held at the dock until the MTRs arrive")])


def completeness():
    """Pack-wide document completeness: the mean over the 21 spools of documents in hand."""
    stamps = sorted({t for i in range(len(S.CTRLS)) for _, t in S.docs_for(i) if t is not None})
    n = len(S.CTRLS) * len(S.docs_for(0))
    times, values = [0.0], [0.0]
    for t in stamps:
        got = sum(1 for i in range(len(S.CTRLS)) for _, dt in S.docs_for(i) if dt is not None and dt <= t + 1e-6)
        before = sum(1 for i in range(len(S.CTRLS)) for _, dt in S.docs_for(i) if dt is not None and dt < t - 1e-6)
        if t > 0:
            times.append(t - 0.005)
            values.append(round(100 * before / n, 1))
        times.append(t + 0.005)
        values.append(round(100 * got / n, 1))
    times.append(S.END)
    values.append(values[-1])
    twin_series("docs", "Pack 1 document completeness", "%", times, values,
                events=S.EVENTS, clock={"epoch": S.EPOCH}, speed=0.35, range=(0, 100))


# ------------------------------------------------------------------ build

def build(ctx):
    rng = ctx.rng
    preview_time(S.PREVIEW_T)
    M = campus.mats()
    st = S.STATIONS
    objs = {}
    pickup = campus.pickup_prefab(M)

    # Ground, pads and roads
    terrain("Ground", size=560, resolution=280, height=height, material=M["grass"], center=(0, 10))
    for key, s in st.items():
        x0, y0, x1, y1 = s["pad"]
        plane(f"Pad_{key}", ((x1 - x0), (y1 - y0)), ((x0 + x1) / 2, (y0 + y1) / 2, 0.03),
              material=M["dirt"] if key == "field" else M["gravel"], collection="Ground")
    plane("Road_spine", (420, S.ROAD_W), (0, S.ROAD_Y, 0.05), material=M["asphalt"], collection="Ground")
    for key, s in st.items():
        cx, cy = s["door"][0], s["door"][1]
        y0, y1 = sorted((S.ROAD_Y, cy))
        plane(f"Road_{key}", (S.ROAD_W, y1 - y0), (cx, (y0 + y1) / 2, 0.05), material=M["asphalt"], collection="Ground")
    plane("Backdrop", 3000, (0, 10, -4.0), material=M["grass"], backdrop=True, collection="Ground")

    # 1 Home office
    ox, oy = st["office"]["centre"]
    objs["office"] = [campus.office(M, (ox, oy))]
    plane("Parking", (70, 16), (ox, oy + 22, 0.06), material=M["asphalt"], collection="Office")
    cars = [ind.car_prefab(M, n, c) for n, c in (("white", "#e8e9ea"), ("grey", "#6f7378"), ("blue", "#2d4f8a"), ("black", "#1e2124"))]
    for i in range(12):
        if rng.random() < 0.75:
            instance(rng.choice(cars), f"Car_{i}", (ox - 30 + i * 5.5, oy + 26, 0.06), (0, 0, 90), collection="Office")
    for i in range(5):
        instance(rng.choice(cars), f"CarS_{i}", (ox - 28 + i * 5.5, oy + 17, 0.06), (0, 0, 90), collection="Office")

    # 2 Vendor
    vx, vy = st["vendor"]["centre"]
    objs["vendor"] = [campus.warehouse(M, (vx, vy))]
    joint = campus.pipe_joint_prefab(M)
    for (rx, ry) in ((vx - 50, 62), (vx - 50, 69), (vx - 36, 62), (vx - 36, 69), (vx + 14, 62), (vx + 14, 69),
                     (vx + 28, 62), (vx + 28, 69)):
        campus.pipe_rack(M, (rx, ry, 0), 0)
        campus.stack_pipes(M, joint, (rx, ry, 0), 0, levels=3 if rng.random() < 0.7 else 2)
    crate = campus.crate_prefab(M)
    for i in range(12):
        instance(crate, f"Crate_v{i}", (vx + 30 + (i % 4) * 2.0, 80 - (i // 4) * 1.6, 0), (0, 0, rng.uniform(-8, 8)), collection="Vendor")
    campus.fence(M, [(vx - 54, 59), (vx - 54, 118), (vx - 30, 118)])
    campus.fence(M, [(vx + 54, 118), (vx + 54, 59), (vx + 20, 59)])
    campus.fence(M, [(vx - 54, 59), (vx - 12, 59)])
    instance(pickup, "Forklift_v", (vx + 10, 78, 0), (0, 0, -30), collection="Vendor")

    # 3 Fab shop: the shop, racks of raw pipe in the north-west corner, the spool yard south.
    fx, fy = st["fab"]["centre"]
    objs["fab"] = [campus.fab_shop(M, (fx, fy))]
    for (rx, ry) in ((fx - 42, 112), (fx - 42, 119), (fx + 28, 119)):
        campus.pipe_rack(M, (rx, ry, 0), 0)
        campus.stack_pipes(M, joint, (rx, ry, 0), 0, levels=2)
    campus.fence(M, [(fx - 42, 57), (fx - 42, 126), (fx - 14, 126)])
    campus.fence(M, [(fx + 42, 126), (fx + 42, 57), (fx + 16, 57)])
    campus.fence(M, [(fx - 42, 57), (fx - 10, 57)])
    plane("FabYard", (84, 30), (fx, 71, 0.05), material=M["concrete"], collection="Fab shop")

    # 4 Field site: the laydown yard at 10-16 (no tie-in drawings: no plant to install into).
    campus.fence(M, [(-72, -60), (-72, -118), (92, -118), (92, -60)], height=1.8, post_step=4)
    instance(pickup, "Pickup_field_1", (-45, -67, 0), (0, 0, 10), collection="Field")
    instance(pickup, "Pickup_field_2", (-37, -67, 0), (0, 0, -5), collection="Field")
    instance(pickup, "Pickup_field_3", (60, -68, 0), (0, 0, 95), collection="Field")
    cone = campus.cone_prefab(M)
    for i in range(8):
        instance(cone, f"Cone_{i}", (-4 + i * 1.5 if i < 4 else 20 - (i - 4) * 1.5, -80, 0), collection="Field")
    for i in range(6):
        instance(crate, f"Crate_f{i}", (70 + (i % 3) * 2.0, -100 - (i // 3) * 1.6, 0), (0, 0, rng.uniform(-8, 8)), collection="Field")
    objs["field"] = [campus.trailer(M, "FieldOffice", (-52, -110), 0, label="FIELD OFFICE 10-16")]
    campus.sign("laydown", "LAYDOWN · TIE-INS PENDING DRAWINGS", 14, (10, -117.9, 1.3), (90, 0, 180), color="#8a2b22")

    # 5 QC / turnover
    qx, qy = st["qc"]["centre"]
    objs["qc"] = [campus.trailer(M, "QCTrailer", (qx, qy + 2), 0, label="QC / TURNOVER"),
                  campus.trailer(M, "DocControl", (qx, qy - 10), 0, label="DOCUMENT CONTROL")]
    instance(pickup, "Pickup_qc", (qx + 18, qy + 14, 0), (0, 0, 80), collection="QC")
    instance(pickup, "Pickup_qc2", (qx + 24, qy + 14, 0), (0, 0, 85), collection="QC")
    plane("QC_parking", (22, 14), (qx + 22, qy + 14, 0.06), material=M["asphalt"], collection="QC")

    # Light poles along the spine road and the pads; campus trees outside the pads.
    pole = campus.light_pole_prefab(M)
    for i, x in enumerate(range(-200, 201, 50)):
        instance(pole, f"Pole_{i}", (x, S.ROAD_Y + 6, 0), (0, 0, -90), collection="Lighting")
        lamp((x, S.ROAD_Y + 4.4, 10.1), color="#ffe6c0", power=2500, pool_z=0.05, light=False)
    for key, s in st.items():
        x0, y0, x1, y1 = s["pad"]
        for j, (px, py) in enumerate(((x0 + 3, y0 + 3), (x1 - 3, y0 + 3), (x0 + 3, y1 - 3), (x1 - 3, y1 - 3))):
            instance(pole, f"Pole_{key}_{j}", (px, py, 0), (0, 0, 45 + j * 90), collection="Lighting")
            lamp((px, py, 10.1), color="#ffe6c0", power=2500, pool_z=0.05, light=False)
    tree = ind.tree_prefab()
    pts = scatter(rng, 420, (-280, 280, -170, 190), height,
                  accept=lambda x, y, z: not in_pad(x, y, 6) and abs(y - S.ROAD_Y) > 9, min_dist=7)
    for i, (x, y, z) in enumerate(pts):
        instance(tree, f"Tree_{i}", (x, y, z - 0.1), (0, 0, rng.uniform(0, 360)), rng.uniform(1.1, 2.2), collection="Trees")

    # The material: shipment on truck 1, the 21 spools, truck 2 on its three trips.
    flatbed = campus.flatbed_prefab(M)
    t1 = instance(flatbed, "Truck_1", collection="Vehicles")
    twin_tag(t1, "truck-1")
    twin_motion(t1, S.TRUCK_1, hide=False)
    t2 = instance(flatbed, "Truck_2", collection="Vehicles")
    twin_tag(t2, "truck-2")
    truck2 = S.truck_2_keys()
    twin_motion(t2, truck2, hide=False)
    mb = MeshBuilder("Shipment")
    for dy in (-0.75, -0.45, -0.15, 0.15, 0.45, 0.75):
        mb.rod((-4.0, dy, 0.14), (2.0, dy, 0.14), 0.1365 if abs(dy) > 0.3 else 0.162, M["cs_pipe"], 20)
    mb.box((4.0, 0, 0.45), (1.6, 1.1, 0.9), M["timber"])
    mb.box((3.2, 0, 1.2), (1.2, 1.0, 0.6), M["timber"])
    shipment = mb.build(collection="Vehicles")
    twin_tag(shipment, "shipment")
    ship_keys = [(t, (p[0], p[1], S.BED_Z), yaw) for t, p, yaw in S.TRUCK_1[:5]]
    ship_keys += [(8.6, (121, 70, 0), -90)]
    twin_motion(shipment, ship_keys, until=12.5)

    PM = spool_mats()
    stand = campus.stand_prefab(M)
    crib = campus.skid_prefab(M)
    by_ctrl = {s["ctrl"]: s for s in pack.SPOOLS}
    for i, ctrl in enumerate(S.CTRLS):
        sd = by_ctrl[ctrl]
        build_spool(i, sd, PM, stand, crib, truck2)
        spool_record(i, sd)
        twin_state(f"spool-{ctrl}", S.state_of(i))
    records(objs)
    twin_state("ncr-1", [(0, "pending"), (8.4, "hold"), (12.4, "ok")])
    twin_state("truck-1", [(0, "pending"), (7.0, "active"), (8.3, "hold"), (9.0, "pending")])
    twin_state("truck-2", [(0, "pending")] + [x for tr in S.TRIPS for x in ((tr["t0"] - 0.5, "active"),
                                                                            (tr["t0"] + S.TRIP_DRIVE + S.TRIP_UNLOAD + 1.2, "pending"))])
    twin_state("shipment", [(0, "pending"), (7.0, "active"), (8.4, "hold"), (12.4, "ok")])
    for label, a, b, t0, t1, color in S.FLOWS:
        da, db = st[a]["door"], st[b]["door"]
        twin_flow(label, (da[0], da[1], 7.0), (db[0], db[1], 7.0), t0, t1, color=color)
    completeness()
    people(rng)

    # Light and camera: a spring morning in the Peace country, seen from the south-west like the board.
    atmosphere(time="10:24", latitude=55.2, day=100, haze=0.25)
    camera((-205, -295, 140), (-8, -4, 0), lens=42)


if __name__ == "__main__":
    print("build with: scripts/bl tools/build_world.py north-field-build")
