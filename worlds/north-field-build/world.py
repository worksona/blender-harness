"""North Field Build: Purnell's document-controlled construction process as a campus you can
replay. Five stations (home office, vendor, fab shop, field site, QC) on one site, and one real
spool (control 1 of Pressure Test Pack 1, job 2024-062A for Arc Resources) followed from
isometric to turnover: material shipped, put on hold at receiving for a missing MTR, released,
fabricated, tested, hauled to site, lowered in and inspected. Documents fly between the stations
as they are issued, the spool's record shows which it has at any moment, and the crews walk,
weld and inspect through it all.

The layout is a stylised campus (the real vendor is far away); the spool and its test pack are
real, the schedule around it is reconstructed (see scenario.py).
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
    "description": "Purnell's construction process as a replayable campus: one spool from "
                   "isometric to turnover, through a document hold, fabrication, hydrotest and "
                   "installation, with the crews and paperwork that move it.",
    "tags": ["construction sim", "data twin", "piping", "industrial"],
    "seed": 62,
    "private": True,          # built around a client job
    "render": {"res": "1920x1080", "samples": 64},
    "viewer": {"exposure": 1.0},
}

PAD_MARGIN = 12.0


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


def ground_height(x, y):
    """The grass terrain: like height(), but dropped under the field's dirt patch so its coarser
    grid can't poke through the patch on the trench walls."""
    z = height(x, y)
    x0, y0, x1, y1 = S.STATIONS["field"]["pad"]
    if x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1:
        z -= 0.6
    return z


def height(x, y):
    z = 0.45 * fbm(x, y, scale=60, seed=7) + 0.12 * fbm(x, y, scale=9, seed=3)
    z *= 1.0 - pad_blend(x, y)
    # The open cut: a trench with battered walls along the field site.
    tx0, tx1 = S.TRENCH_X
    ty = S.TRENCH[1]
    if tx0 - 2 <= x <= tx1 + 2 and abs(y - ty) < S.TRENCH_HALF:
        w = min(1.0, (S.TRENCH_HALF - abs(y - ty)) / 1.6)
        ends = min(1.0, (x - tx0 + 2) / 3, (tx1 + 2 - x) / 3)
        z -= S.TRENCH_DEPTH * w * ends
    return z


# ------------------------------------------------------------------ people

PEOPLE = []


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
        PEOPLE.append(p)


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
    # 3 Fab shop: receiving inspector at the dock during the hold, welders around the spool,
    # the NDE tech, and shop hands crossing the yard all the time.
    fx, fy = st["fab"]["centre"]
    sx, sy, _ = S.STAND
    crew("Receiver", 2, [shift(8.25, 12.6, [(sx + 10, 71), (sx + 6, 69), (sx + 8, 66)],
                               {0: (12, "inspect"), 1: (6, "talk"), 2: (5, "inspect")})], rng, vest="#1fb85a")
    crew("Welder", 3, [shift(12.5, 19.0, [(sx - 1.0, sy - 1.3), (sx + 2.6, sy - 1.2), (sx + 3.2, sy + 1.0),
                                          (sx - 1.5, sy + 1.6)],
                             {0: (14, "weld"), 1: (10, "weld"), 2: (9, "weld"), 3: (5, "carry")}),
                       shift(22.0, 28.0, [(sx - 1.0, sy - 1.3), (sx + 2.8, sy - 1.0), (sx - 6, sy - 6)],
                             {0: (8, "carry"), 1: (10, "inspect"), 2: (6, "talk")}),
                       shift(29.0, 31.0, [(sx - 1.2, sy - 1.2), (sx + 2.8, sy - 1.1)], {0: (10, "weld"), 1: (10, "weld")})],
         rng)
    crew("NDE", 1, [shift(19.0, 21.5, [(sx + 1.0, sy - 1.6), (sx + 2.8, sy + 1.6)], {0: (16, "inspect"), 1: (12, "inspect")}),
                    shift(28.0, 28.6, [(sx - 1.5, sy - 2.2)], {0: (60, "inspect")})], rng, vest="#f2f2f2")
    crew("Shop", 4, [shift(0, S.END, [(fx - 12, 62), (fx - 12, 82), (fx + 12, 84), (fx + 22, 80), (fx + 14, 62)],
                           {1: (6, "carry"), 2: (8, "idle"), 3: (5, "talk")})], rng)
    # 4 Field site: surveyors ahead of the pipe, the lowering-in crew, the inspector, tie-in.
    tx, ty, _ = S.TRENCH
    crew("Survey", 3, [shift(20.0, 33.5, [(-40, ty + 9), (-10, ty + 9), (30, ty + 9), (60, ty + 8), (66, ty - 12), (20, ty - 13), (-30, ty - 13)],
                             {0: (10, "survey"), 2: (8, "survey"), 4: (10, "survey"), 6: (6, "talk")})], rng)
    crew("Crew", 8, [shift(33.6, 36.5, [(tx - 8, ty + 10), (tx + 4, ty + 10), (tx + 10, ty + 6), (tx - 4, ty + 6)],
                           {0: (8, "carry"), 1: (6, "carry"), 2: (10, "idle"), 3: (7, "talk")}),
                     shift(36.5, 40.5, [(tx - 3, ty - 0.2, -1.55), (tx + 3.5, ty - 0.3, -1.55), (tx + 6, ty + 4.5),
                                        (tx - 6, ty + 4.5)],
                           {0: (14, "weld"), 1: (12, "weld"), 2: (6, "carry"), 3: (6, "talk")}),
                     shift(40.5, S.END, [(tx - 30, ty + 8), (tx + 40, ty + 8), (tx + 40, ty + 12), (tx - 30, ty + 12)],
                           {1: (6, "idle"), 3: (6, "talk")})], rng)
    crew("Inspector", 1, [shift(38.0, 39.6, [(tx + 1.5, ty + 3.2), (tx - 2.5, ty + 3.2)], {0: (20, "inspect"), 1: (14, "inspect")})],
         rng, vest="#f2f2f2")
    # 5 QC: between the trailers, a lot of talking.
    qx, qy = st["qc"]["centre"]
    crew("QC", 3, [shift(0, S.END, [(qx - 10, qy + 10), (qx + 8, qy + 10), (qx + 8, qy - 4), (qx - 12, qy - 4)],
                         {0: (8, "talk"), 2: (10, "inspect"), 3: (5, "idle")})], rng, vest="#5a6f8a", helmet=None)


# ------------------------------------------------------------------ the spool

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
        "gasket": material("gasket_spiral", "#aeb2b4", roughness=0.35, metallic=0.8),
    }


def build_spool(M, sd):
    sp = piping.Spool("Spool-1", sd["nps"], spool_mats(), sch=sd["sch"])
    sp.walk(sd["route"], direction=sd["start"])
    root = sp.build(collection="Spool")
    twin_tag(root, "spool-1")
    r = piping.OD[sd["nps"]] / 2000
    z_stand = 0.55 + r
    truck = S.TRUCK_2
    keys = [(12.5, (S.STAND[0], S.STAND[1], z_stand), 0), (32.0, (S.STAND[0], S.STAND[1], z_stand), 0)]
    keys += [(t, (p[0], p[1], S.BED_Z + r), yaw) for t, p, yaw in truck[3:7]]
    keys += [(34.0, (S.LAYDOWN[0], S.LAYDOWN[1], 0.3 + r), 0), (36.0, (S.LAYDOWN[0], S.LAYDOWN[1], 0.3 + r), 0),
             (36.5, (S.TRENCH[0], S.TRENCH[1], S.TRENCH[2] + r), 0)]
    twin_motion(root, keys)
    return sp, root


def spool_record(sd):
    size = f'{sd["nps"]}"'
    bw = [w for w in sd["welds"] if w["type"] == "BW"]
    fields = [("Job", f"{pack.REPORT['job']} · {pack.REPORT['customer']}"), ("Line", sd["line"]),
              ("Control no.", sd["ctrl"]), ("Purchase order", S.PO),
              ("Size / schedule", f"{size} Sch {sd['sch']}"), ("Material", "A333-6 / A420-WPL6 / A350-LF2, NACE"),
              ("Butt welds", f"{len(bw)} (100% RT)"), ("Test", "Water, 15,307 kPa min, 15 min hold"),
              ("Hydrotest", "Accepted 2024-04-29 (Pack 1)"), ("Destination", f"{pack.REPORT['site']}, Kakwa")]
    tables = [{"title": "Bill of materials", "columns": ["Item", "Heat no.", "Size", "Description", "Qty"],
               "rows": [[str(i), h, s, d, str(q)] for i, h, s, d, q in sd["bom"]]},
              {"title": "Weld information", "columns": ["Weld", "Size", "Type", "Welder", "X-ray", "MPI", "HT", "VT"],
               "rows": [[w["id"], w["size"], w["type"], w["welder"], w["xray"], w["mpi"], w["ht"], w["vt"]]
                        for w in sd["welds"]]}]
    twin_record("spool-1", sd["iso"], f"Control {sd['ctrl']} · {size} spool · {S.PO}", group="Material",
                fields=fields, tables=tables, color="#9fe39a", docs=S.DOCS,
                images=[{"title": "Isometric drawing", "src": f"docs/iso-ctrl{sd['ctrl']:02d}.png"}],
                notes=["Press ▶ on the replay bar: the spool is shipped, held for its MTR, fabricated, "
                       "tested, hauled to site and installed; its documents arrive as they are issued.",
                       "Isometric, BOM, weld table and hydrotest are from Pressure Test Pack 1; the purchasing, "
                       "shipping, hold and field dates around them are reconstructed."])


# ------------------------------------------------------------------ records

def records(objs):
    R = pack.REPORT
    twin_record("job", f"{R['job']} · {R['project']}", f"{R['company']} for {R['customer']} · {R['site']}",
                overview=True, color="#6cb6ff",
                fields=[("Process", "Home office → vendors → fab shop → field site → QC / turnover"),
                        ("Replay", f"{S.EPOCH} + {S.END:.0f} days; ▶ on the replay bar, drag to scrub"),
                        ("Spool", "Control 1 of Pressure Test Pack 1 (click it, or find it under Material)"),
                        ("Hold", "Day 8: material received without its MTR; released day 12")],
                notes=["Click a building for its station and workload; click the spool, the truck or the "
                       "shipment for its record. Objects glow with their state: orange in progress, red on "
                       "hold, green released, blue turned over.",
                       "Station workloads are illustrative; the spool's documents are the real ones."])
    for key, st in S.STATIONS.items():
        rows = [[name, f"{done} / {total}", f"{round(100 * done / total)}%"] for name, done, total in S.WORKLOAD[key]]
        rid = f"st-{key}"
        twin_record(rid, f"{st['n']} · {st['title']}", group="Stations", color="#ffd56b",
                    fields=[("Station", st["n"]), ("Role", STATION_ROLE[key])],
                    tables=[{"title": "Document workload (illustrative)", "columns": ["Document", "Done", ""], "rows": rows}])
        for o in objs.get(key, []):
            twin_tag(o, rid)
    twin_record("ncr-1", "Document hold: MTR missing", f"{S.PO} · heat AG2198", group="Holds", color="#ff6b5e",
                fields=[("Raised", "Receiving inspection, fab shop, day 8"), ("Reason", "Material test report not in the vendor data book"),
                        ("Action", "Vendor documents requested day 10; MTR received day 12"), ("Released", "Day 12 (4 days held)")],
                docs=[("Vendor data book", 6.5), ("MTR (heat AG2198)", 12.4)])
    twin_record("truck-1", "Flatbed · vendor delivery", f"{S.PO} material to the fab shop", group="Material", color="#ffb36b",
                fields=[("Load", "10\" A333-6 pipe, fittings and flanges for control 1"), ("Leaves vendor", "Day 7"),
                        ("At fab dock", "Day 8.3 (receiving inspection)")])
    twin_record("truck-2", "Flatbed · spool to site", "Primed spool to 10-16-062-04 W6M", group="Material", color="#ffb36b",
                fields=[("Leaves shop", "Day 32"), ("At site", "Day 33.6"), ("Lowered in", "Day 36.5")])
    twin_record("shipment", "Shipment: pipe and fittings", f"{S.PO} · as received", group="Material", color="#ffb36b",
                parent="spool-1", listed=False,
                fields=[("Contents", "Pipe (heat AG2198), elbow, flanges, olets, valves"), ("Status", "Held at the dock until the MTR arrives")])


STATION_ROLE = {
    "office": "Engineering issues isometrics, ITPs and procedures; purchasing issues POs",
    "vendor": "Supplies pipe, fittings and flanges with certificates and MTRs",
    "fab": "Receives material, fabricates, NDE, hydrotest, paint",
    "field": "Receives spools, lowers in, ties in, field inspection",
    "qc": "Closes NCRs, collects test reports, assembles the turnover dossier",
}


def completeness():
    """Document completeness of the spool as a step series (the throughput bar's number)."""
    times, values = [0.0], [0.0]
    n = len(S.DOCS)
    done = 0
    for _, t in sorted(S.DOCS, key=lambda d: d[1]):
        times += [t, t + 0.01]
        values += [values[-1], 0]
        done += 1
        values[-1] = round(100 * done / n, 1)
    times.append(S.END)
    values.append(values[-1])
    # Keep the series strictly increasing in time for the chart.
    times[1] = 0.0
    twin_series("docs", "Spool document completeness", "%", times, values,
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
    terrain("Ground", size=560, resolution=280, height=ground_height, material=M["grass"], center=(0, 10))
    for key, s in st.items():
        x0, y0, x1, y1 = s["pad"]
        if key == "field":
            campus.patch("Pad_field", x0, y0, x1, y1, height, M["dirt"], step=1.0)
            continue
        plane(f"Pad_{key}", ((x1 - x0), (y1 - y0)), ((x0 + x1) / 2, (y0 + y1) / 2, 0.03),
              material=M["gravel"], collection="Ground")
    plane("Road_spine", (420, S.ROAD_W), (0, S.ROAD_Y, 0.05), material=M["asphalt"], collection="Ground")
    for key, s in st.items():
        cx, cy = s["door"][0], s["door"][1]
        y0, y1 = sorted((S.ROAD_Y, cy))
        plane(f"Road_{key}", (S.ROAD_W, y1 - y0), (cx, (y0 + y1) / 2, 0.05), material=M["asphalt"], collection="Ground")
    plane("Backdrop", 3000, (0, 10, -4.0), material=M["grass"], backdrop=True, collection="Ground")   # below the trench floor

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

    # 3 Fab shop
    fx, fy = st["fab"]["centre"]
    objs["fab"] = [campus.fab_shop(M, (fx, fy))]
    stand = campus.stand_prefab(M)
    sx, sy, _ = S.STAND
    for i, dx in enumerate((0.5, 1.5)):
        instance(stand, f"Stand_{i}", (sx + dx, sy, 0), collection="Fab shop")
    for i, (dx, dy) in enumerate(((-12, 4), (-12, 12), (12, 14), (14, 6))):   # other work on the apron
        for j, k in enumerate((2, 9)):
            instance(stand, f"StandB_{i}_{j}", (fx + dx + k, fy - 40 + dy, 0), collection="Fab shop")
        instance(joint, f"Joint_fab_{i}", (fx + dx - 1, fy - 40 + dy, 0.69), collection="Fab shop")
    for (rx, ry) in ((fx - 42, 60), (fx - 42, 67), (fx + 24, 60)):
        campus.pipe_rack(M, (rx, ry, 0), 0)
        campus.stack_pipes(M, joint, (rx, ry, 0), 0, levels=2)
    campus.fence(M, [(fx - 42, 57), (fx - 42, 120), (fx - 14, 120)])
    campus.fence(M, [(fx + 42, 120), (fx + 42, 57), (fx + 16, 57)])
    campus.fence(M, [(fx - 42, 57), (fx - 10, 57)])

    # 4 Field site
    tx0, tx1 = S.TRENCH_X
    ty = S.TRENCH[1]
    campus.spoil_ridge(M, tx0, tx1, ty - 7.0, height=1.8, width=5.0)
    skid = campus.skid_prefab(M)
    for i in range(10):
        x = tx0 + i * 12.6
        instance(joint, f"Strung_{i}", (x, ty + 14, 0.4), collection="Field")
        for k in (2.0, 10.0):
            instance(skid, f"Skid_{i}_{k:.0f}", (x + k, ty + 14, 0), collection="Field")
    for k in (0.5, 1.6):
        instance(skid, f"Skid_lay_{k}", (S.LAYDOWN[0] + k, S.LAYDOWN[1], 0), collection="Field")
    campus.excavator(M, (42, ty - 11, 0), 90)
    campus.excavator(M, (-20, ty + 11, 0), -90, boom_down=False)
    instance(pickup, "Pickup_field_1", (-45, -67, 0), (0, 0, 10), collection="Field")
    instance(pickup, "Pickup_field_2", (-37, -67, 0), (0, 0, -5), collection="Field")
    instance(pickup, "Pickup_field_3", (60, -68, 0), (0, 0, 95), collection="Field")
    cone = campus.cone_prefab(M)
    for i in range(12):
        instance(cone, f"Cone_{i}", (tx0 - 4 + i * 11, ty + 4.5, 0), collection="Field")
        instance(cone, f"ConeS_{i}", (tx0 - 4 + i * 11, ty - 4.5, 0), collection="Field")
    campus.fence(M, [(-72, -60), (-72, -118), (92, -118), (92, -60)], height=1.2, post_step=4)
    objs["field"] = [campus.trailer(M, "FieldOffice", (-52, -110), 0, label="FIELD OFFICE")]

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

    # The material: shipment on truck 1, the spool itself, truck 2.
    flatbed = campus.flatbed_prefab(M)
    t1 = instance(flatbed, "Truck_1", collection="Vehicles")
    twin_tag(t1, "truck-1")
    twin_motion(t1, S.TRUCK_1, hide=False)
    t2 = instance(flatbed, "Truck_2", collection="Vehicles")
    twin_tag(t2, "truck-2")
    twin_motion(t2, S.TRUCK_2, hide=False)
    mb = MeshBuilder("Shipment")
    for dy in (-0.45, 0.0, 0.45):
        mb.rod((-3.5, dy, 0.14), (2.5, dy, 0.14), 0.1365, M["cs_pipe"], 20)
    mb.box((4.0, 0, 0.45), (1.6, 1.1, 0.9), M["timber"])
    shipment = mb.build(collection="Vehicles")
    twin_tag(shipment, "shipment")
    ship_keys = [(t, (p[0], p[1], S.BED_Z), yaw) for t, p, yaw in S.TRUCK_1[:5]]
    ship_keys += [(8.6, (sx + 11, 70, 0), -90)]
    twin_motion(shipment, ship_keys, until=12.5)

    sd = next(s for s in pack.SPOOLS if s["ctrl"] == S.SPOOL_CTRL)
    build_spool(M, sd)
    spool_record(sd)
    records(objs)
    twin_state("spool-1", S.STATE)
    twin_state("ncr-1", [(0, "pending"), (8.4, "hold"), (12.4, "ok")])
    twin_state("truck-1", [(0, "pending"), (7.0, "active"), (8.3, "hold"), (9.0, "pending")])
    twin_state("truck-2", [(0, "pending"), (31.6, "active"), (34.5, "pending")])
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
