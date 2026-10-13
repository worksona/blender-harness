"""Purnell Energy Services fab shop on hydrotest day for Pressure Test Pack 1 (job 2024-062A,
Arc Resources, 10-16 sales gas rerouting), as a data twin.

Sources: docs/07-02_Pressure_Test_Pack_1.pdf (transcribed into pack.py) and the photos in
reference/ (a, b, c: Galaxy S23 FE, 23 mm equivalent, 29 Apr 2024 08:18-08:39; d, e: close-ups).

How it was measured
- Spools: every pipe length, fitting, flange, olet and valve comes from the isometrics and their
  bills of materials, at ASME B16.5/B16.9/B16.11 dimensions (harness/piping.py, spools.py).
- Building: 50 x 100 ft bay with 25 ft column bays, solved from photos a and b (vanishing points,
  doors, columns); camera b's height from the green blind's 559 mm flange in its foreground.
- Photo c's camera: solved from the 2" pipe in it (the apparent width of its 60.3 mm OD at seven
  points along the run, plus the pipe pair's vanishing point): 1.46 m up, 42 deg down. That also
  fixed the stand saddle height (0.55 m) for the whole shop.
- Floor layout: stand feet projected onto the floor through the solved cameras (photos a and c
  agree on them to ~0.15 m); spools 12, 5, 4, 11 and 18 are located that way (SETUP below).
- Inferred: which spool is which where the photos can't tell, the spools not visible in any
  photo, the test header and test blinds (test equipment), and the generic "other work" spools.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from harness import *  # noqa: E402
from harness import piping  # noqa: E402

import pack  # noqa: E402
import props  # noqa: E402
import shop  # noqa: E402
import spools  # noqa: E402

META = {
    "title": "Purnell Test Shop",
    "description": "Hydrotest Pack 1 for Arc Resources' 10-16 sales gas rerouting: all 21 spools, "
                   "test station and shop, twinned from the test pack and its photos.",
    "tags": ["industrial", "photo-matched", "data twin", "piping", "interior"],
    "seed": 2024,
    "private": True,      # client documents: never published to the public site
    "render": {"res": "1600x1200", "samples": 64, "view": "Standard"},
    "viewer": {"tone": "neutral", "exposure": 1.0},
}

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "reference")
DOCS = os.path.join(HERE, "docs")

# Photo cameras (23 mm equivalent). Shop coordinates: x across the bay (+x = block wall),
# y along it (0 = near end with the two sectional doors), z up.
CAMERAS = {
    "a-test-bay-to-door.jpg": dict(location=(0.6, 2.3, 1.35), target=(0.95, 24.3, -1.74), size=(4, 3)),
    # Height from the green blind in the foreground: its 559 mm flange spans 170 px at 2.1 m.
    "b-corner-crane-c9610.jpg": dict(location=(3.66, 10.65, 1.2), target=(-6.49, 2.35, -0.76), size=(4, 3)),
    # Solved from the 2" pipe in the photo (apparent width of its 60.3 mm OD along the run, and
    # the vanishing point of the pipe pair): 0.88 m above the pipe axis, 42 deg down.
    "c-small-bore-runs.jpg": dict(location=(1.50, 5.25, 1.46), target=(2.06, 15.26, -7.54), size=(3, 4)),
}

# Where each spool sits: plan centre (x, y), rotation (degrees: rx, ry, yaw), test-blind paint.
# Yaw 0 keeps the drawing's north along +y.
# How each spool sat for the test, shown on its twin card. "Measured" means located from the photos
# (stand feet projected onto the floor through the solved cameras); the rest is placed to fit.
SETUP = {
    12: "The 2\" run in photo c, on the measured valve stand and second stand; its south flange "
        "bolted to spool 5. Position measured in photos a and c.",
    5: "Bolted to spool 12's south flange: the corner and west leg in photo a, the test header on "
       "its west flange. Position measured in photo a.",
    4: "Lying on the floor east of spool 12 (photos a and c). Position measured in photos a and c.",
    11: "Riser on the large stand at the left of photo c; its 1979 mm run leaves the photo's left "
        "edge. Position measured in photo c.",
    18: "Green test blind on its 10\" end, 2.1 m in front of photo b's camera; the run heads west "
        "(photo c, top). Position measured in photos b and c.",
}

LAYOUT = {
    # Big-bore spread, main runs east-west (photos a and b)
    # Spool 18 (heat AG2148 painted on it, green test blind on its 10" end) runs north from the
    # blind, 2.1 m in front of photo b's camera (from the blind's 559 mm OD in the photo).
    # Its 10" end and three vents face east, 2 m in front of photo b's camera; the run heads west
    # (the second east-west 10" in the top of photo c).
    18: dict(matrix=Matrix.Translation((2.30, 9.85, 0.66)) @ Matrix.Rotation(math.radians(-12), 4, "Z"),
             stands=[(1.76, 9.96, 78.0, "star"), (0.39, 10.26, 78.0, "star")],
             blinds=["green", "black", "rust"]),
    17: dict(xy=(-3.1, 10.6), rot=(90, 0, 0), blinds=["rust", "black", "black"]),
    8: dict(xy=(-2.6, 6.2), rot=(0, 0, 0)),
    1: dict(xy=(-3.5, 13.4), rot=(0, 0, 0)),
    2: dict(xy=(-5.3, 8.4), rot=(0, 0, 90)),
    9: dict(xy=(0.4, 11.6), rot=(0, 0, 0)),
    14: dict(xy=(-1.0, 13.9), rot=(0, 0, 0)),
    15: dict(xy=(-5.7, 5.0), rot=(0, 0, 90)),
    16: dict(xy=(-5.0, 12.2), rot=(0, 0, 0)),
    6: dict(xy=(-4.4, 2.9), rot=(0, 0, 90)),
    7: dict(xy=(-3.8, 3.6), rot=(0, 0, 90)),
    10: dict(xy=(-6.7, 16.3), rot=(0, 0, 0)),
    19: dict(xy=(-6.7, 18.6), rot=(0, 0, 0)),
    # Small-bore (photos a and c): spools 12, 5 and 4 are placed by small_bore_line().
    3: dict(xy=(5.1, 5.9), rot=(0, 0, 90)),
    # Spool 11: riser on the big stand at the left of photo c, its 1979 mm run the pipe that
    # leaves photo c's left edge and ends at a flange near the top.
    11: dict(matrix=Matrix.Translation((0.62, 6.30, 0.58 + 1.213)) @ Matrix.Rotation(math.radians(171), 4, "Z"),
             stands=[(0.66, 6.38, 81.0, "cone_y"), (0.9, 8.1, 81.0, "cone_y")]),
    13: dict(xy=(4.7, 12.6), rot=(0, 0, 0)),
    20: dict(xy=(5.3, 6.8), rot=(0, 0, 90)),
    23: dict(xy=(6.1, 9.9), rot=(0, 0, 0)),
}
# Other work on the floor in the photos (not in Pack 1): generic spools at the same spots, so the
# twin reads like the photographs. They carry one shared "not in this pack" record.
OTHER = [
    # The first east-west 10" at the top of photo c, its east end curving round toward the camera
    dict(name="Other-8in-run-2", nps=8, start="E", xy=(1.42, 9.5), rot=(0, 0, -15),
         route=[("flange",), ("pipe", 1500, [(450, "U", "vent")]), ("elbow", "D"), ("flange",)]),
    dict(name="Other-10in-loop", nps=10, start="E", xy=(-1.2, 12.6), rot=(0, 0, 0),
         route=[("flange",), ("pipe", 900), ("elbow", "U"), ("pipe", 1350), ("elbow", "W"), ("pipe", 700),
                ("flange",)]),
    dict(name="Other-12in-riser", nps=12, start="D", xy=(-1.3, 4.6), rot=(0, 0, 0),
         route=[("flange",), ("pipe", 700, [(250, "N", "vent"), (250, "E", "vent")]), ("elbow", "E"),
                ("pipe", 900), ("flange",)]),
    dict(name="Other-8in-run", nps=8, start="W", xy=(-2.4, 7.4), rot=(0, 0, 0),
         route=[("flange",), ("pipe", 3100, [(800, "U", "vent")]), ("elbow", "N"), ("flange",)]),
    # The long 2" run on cones east of the spread (photo a, right; photo c, top right)
    dict(name="Other-2in-long", nps=2, start="N", xy=(4.35, 9.75), rot=(0, 0, -6.5),
         route=[("flange",), ("pipe", 4100), ("flange_pair",), ("pipe", 4100), ("flange",)]),
]
# Line 720540-25H as it lay for the test: the 5.4 m run of spool 4 heading south toward the
# camera of photo a, an elbow and flange pair turning west into spool 5's riser, and spool 3 at
# the north end. RUN_START is the south end of spool 4's pipe; the run heads RUN_DIR.
RUN_START = Vector((1.55, 5.15, 0.58))
RUN_DIR = Vector((0.040, 1.0, 0.0)).normalized()
PM = None             # prop materials (shared with helpers)


def hours(t):
    h, m = t.split(":")
    return int(h) + float(m) / 60


# ------------------------------------------------------------------ materials

def piping_mats():
    pipe_tex = texture("pipe_c", np.clip(grime(512, "#1f1e1c", "#5d3a22", 0.33, 21, 2) +
                                         (fbm_noise(512, 32, 2, 3)[..., None] - 0.5) * 0.04, 0, 1))
    mill = texture("pipe_n", height_normal(fbm_noise(512, 24, 4, 9), 1.2), data=True)
    forge_tex = texture("forge_c", grime(512, "#24221f", "#6f3c1e", 0.5, 31, 3))
    return {
        "pipe": material("pipe_black", texture=pipe_tex, texture_size=1.1, normal=mill, roughness=0.38, metallic=0.08),
        "fitting": material("fitting_black", "#c8c8c8", texture=pipe_tex, texture_size=0.9, normal=mill,
                            roughness=0.3, metallic=0.08),
        "flange": material("flange_forged", texture=forge_tex, texture_size=0.5, roughness=0.5, metallic=0.45),
        "weld": material("weld_bead", "#40372f", roughness=0.6, metallic=0.5),
        "olet": material("olet_forged", "#57534d", roughness=0.45, metallic=0.6),
        "valve": material("valve_blue", "#2c5fae", roughness=0.35, metallic=0.1),
        "lever": material("valve_lever", "#141414", roughness=0.5),
        "plug": material("plug_steel", "#8d8a84", roughness=0.4, metallic=0.75),
        "black": material("blind_black", texture=forge_tex, texture_size=0.6, roughness=0.5, metallic=0.4),
        "green": material("blind_green", texture=texture("blind_green_c", grime(256, "#5f9a80", "#4b3a2a", 0.4, 7, 3)),
                          texture_size=0.5, roughness=0.6),
        "rust": material("blind_rust", "#d9a88a", texture=forge_tex, texture_size=0.4, roughness=0.6, metallic=0.3),
        "blind_paint": material("dummy_plate", "#8a8984", roughness=0.6, metallic=0.2),
        "gasket": material("gasket_spiral", "#aeb2b4", roughness=0.35, metallic=0.8),
        "cap": material("thread_cap", "#c4231b", roughness=0.5),
        "stud": material("stud_b7m", "#1b1b1b", roughness=0.55, metallic=0.5),
        "nut": material("nut_2hm", "#222220", roughness=0.5, metallic=0.5),
        "bore": material("bore_dark", "#0b0b0b", roughness=0.9),
        "rust_pipe": material("pipe_rust", texture=texture("rust_c", grime(256, "#6b4630", "#3a2a20", 0.45, 13, 3)),
                              texture_size=0.6, roughness=0.6, metallic=0.2),
    }


def prop_mats():
    M = {
        "rack": material("rack_red", "#6b2c20", roughness=0.6, metallic=0.4),
        "flange_rusty": material("loose_flange_rusty", "#6a4a36", roughness=0.7, metallic=0.4),
        "flange_black": material("loose_flange_black", "#2a2826", roughness=0.5, metallic=0.5),
        "flange_galv": material("loose_flange_galv", "#9ea2a2", roughness=0.4, metallic=0.8),
        "flange_green": material("loose_flange_green", "#4f8a62", roughness=0.6, metallic=0.2),
        "enclosure": material("enclosure_grey", "#a9adab", roughness=0.4, metallic=0.4),
        "unistrut": material("unistrut", "#9a9c9a", roughness=0.4, metallic=0.7),
        "stainless": material("stainless", "#c3c7c9", roughness=0.25, metallic=0.9),
        "rosemount": material("rosemount_blue", "#3f7ea3", roughness=0.35, metallic=0.1),
        "falcon_blue": material("falcon_blue", "#2152a8", roughness=0.4),
        "falcon_white": material("falcon_white", "#e6e6e0", roughness=0.5),
        "wood": material("wood", "#9b7a52", roughness=0.85),
        "cardboard": material("cardboard", "#a7845c", roughness=0.9),
        "hose": material("hose_black", "#171717", roughness=0.6),
        "hose_yellow": material("hose_yellow", "#b98f34", roughness=0.6),
        "red": material("paint_red", "#c3241c", roughness=0.5),
        "booth": material("booth_white", "#e5e4de", roughness=0.5, metallic=0.2),
        "cabinet_yellow": material("cabinet_yellow", "#e2ad12", roughness=0.45, metallic=0.2),
        "bin_blue": material("bin_blue", "#2856b0", roughness=0.5),
        "hole": material("stand_hole", "#1a1712", roughness=0.9),
        "bore": material("bore_dark", "#0b0b0b", roughness=0.9),
    }
    for key, base, seed in (("yellow", "#c8bf86", 1), ("grey", "#8b98a6", 2), ("red", "#c27058", 3),
                            ("green", "#6a9a80", 4), ("yellow2", "#c2b886", 5), ("blue", "#7f93ad", 6)):
        M[f"pe_{key}"] = material(f"pe_{key}", texture=props.stand_texture(f"pe_{key}", base, seed),
                                  texture_size=1.0, roughness=0.55)
    return M


def floor_texture():
    """One unique texture over the whole slab: sealed concrete, saw-cut joints every 3.81 m,
    traffic wear, and the water stains under the test spread seen in photos b and c."""
    H, W = 4096, 2048
    big = fbm_noise((H, W), 6, 6, 41)
    fine = fbm_noise((H, W), 160, 2, 42)
    stain = fbm_noise((H, W), 10, 5, 43)
    t = contrast(big, 0.35, 0.8) * 0.5 + (fine - 0.5) * 0.18
    col = colorize(np.clip(t, 0, 1), "#8f877a", "#5a5349")
    yy, xx = np.mgrid[0:H, 0:W]
    ym = (H - yy) / H * shop.L                # metres along the bay (row 0 = far end)
    xm = xx / W * shop.W - shop.W / 2
    wet = np.zeros((H, W), np.float32)        # water stains where spools were filled and drained
    edge = fbm_noise((H, W), 40, 4, 45)       # breaks up the stains' outlines
    for cx, cy, r in ((1.22, 6.5, 0.6), (0.95, 6.35, 0.32), (1.75, 6.68, 0.36), (1.3, 6.12, 0.3),
                      (-3.8, 9.5, 1.5), (3.4, 12.6, 0.9), (-0.2, 3.8, 1.2)):
        d = np.sqrt((xm - cx) ** 2 + (ym - cy) ** 2) / r
        wet = np.maximum(wet, np.clip(1.2 - d - (stain - 0.5) * 1.6 - (edge - 0.5) * 0.9, 0, 1))
    wet = contrast(wet, 0.2, 0.32)             # wet concrete: dark with a fairly crisp edge,
    mottle = 0.32 + 0.28 * fbm_noise((H, W), 60, 3, 46)          # unevenly soaked
    col = col * (1 - wet[..., None] * mottle[..., None]) + np.array([0.02, 0.012, 0.0]) * wet[..., None]
    spots = contrast(fbm_noise((H, W), 90, 2, 44), 0.8, 0.9)     # oil drips and scuffs
    col = col * (1 - spots[..., None] * 0.35)
    gx = np.abs(((xm + shop.W / 2) / 3.81 + 0.5) % 1 - 0.5) * 3.81   # saw-cut control joints
    gy = np.abs((ym / 3.81 + 0.5) % 1 - 0.5) * 3.81
    joint = np.clip(1 - np.minimum(gx, gy) / 0.006, 0, 1)
    col = col * (1 - joint[..., None] * 0.55)
    edge = np.clip(1 - np.minimum(np.abs(xm - shop.W / 2), np.abs(xm + shop.W / 2)) / 0.8, 0, 1)
    col = col * (1 - edge[..., None] * 0.15)  # dust along the walls
    return texture("floor_c", np.clip(col, 0, 1), quality=86)


# ------------------------------------------------------------------ twin records

def overview_record():
    R = pack.REPORT
    twin_record(
        "pack-1", "Pressure Test Pack 1", f"{R['customer']} · {R['project']}", group="Test",
        overview=True, color="#ffd27a",
        fields=[("Form", R["form"]), ("Job", R["job"]), ("Site", R["site"]), ("Package", R["package"]),
                ("Code", R["code"]), ("Location", R["location"]), ("Flange rating", R["flange_rating"]),
                ("Design pressure", R["design_pressure"]),
                ("Test pressure", f"{R['test_min']} to {R['test_max']}"),
                ("Medium / duration", f"{R['medium']}, {R['duration']}"), ("Test date", R["test_date"]),
                ("Deadweight", R["deadweight"]), ("Recorder", R["recorder"]),
                ("Purnell representative", R["purnell_rep"]), ("Customer representative", R["customer_rep"]),
                ("Spools", f"{len(pack.SPOOLS)} (2 dummy legs not tested)")],
        tables=[{"title": "Line list (QF-9 page 2)", "columns": ["Line", "ISO", "Ctrl"],
                 "rows": [[ln, iso, str(c)] for ln, iso, c in pack.LINE_LIST] +
                         [["Assorted threaded nipples, pipe, valves and fittings", "", "N/A"]]},
                {"title": "Test record (VTScada, 5-min averages)", "columns": ["Time", "PT-1 psi", "TT-1 °C"],
                 "rows": [[t, str(p), f"{c:.2f}"] for t, p, c in pack.GRID]}],
        notes=["Data checks while transcribing:"] + pack.NOTES,
        images=[{"title": "QF-9 line list", "src": "docs/qf9-line-list.png"},
                {"title": "VTScada trend, Test Station 1", "src": "docs/scada-trend.png"},
                {"title": "VTScada grid", "src": "docs/scada-grid.png"}])


def instrument_records():
    for key, cal in pack.CALIBRATION.items():
        twin_record(f"inst-{key}", cal["title"], key, group="Instruments", fields=cal["fields"],
                    tables=[cal["table"]], color="#9fe39a",
                    images=[{"title": "Transmitter calibration", "src": "docs/transmitter-calibration.png"}]
                    if key in ("PT-1", "TT-1") else [])
    twin_record("station-1", "Test Station 1", "Hydro testing PLC TS1 (VTScada)", group="Shop equipment",
                fields=[("Pressure", "PT-1 Rosemount 2051, 0-10,000 psi"), ("Temperature", "TT-1"),
                        ("Historian", "VTScada Light, Hydro Testing\\PLC\\TS1\\TS1 MDBUS"),
                        ("Used for", "Pack 1 test, 2024-04-29 10:20-11:36")], color="#9fe39a",
                images=[{"title": "Historical data viewer", "src": "docs/scada-trend.png"}])
    twin_record("station-2", "Test Station #2", "Second hydrotest station (west wall)",
                group="Shop equipment", fields=[("Status", "Not used for Pack 1")], color="#9fe39a")
    for cid, end in (("C9808", "north end"), ("C9610-A", "south end")):
        twin_record(f"crane-{cid}", f"Crane {cid}", "5 ton top-running bridge crane", group="Shop equipment",
                    fields=[("Capacity", "5 ton"), ("Hoist", "GH electric wire-rope hoist"),
                            ("Service", "Competition Crane & Hoist"), ("Parked", end)], color="#ffd27a")


def test_series():
    ev = [{"t": hours(a), "label": b} for a, b in pack.EVENTS]
    twin_series("pt1", "PT-1 pressure (trend)", "psi", [hours(a) for a, _ in pack.TREND],
                [b for _, b in pack.TREND], events=ev, tint_group="Spools", range=(0, 2262))
    g = pack.GRID
    twin_series("pt1-avg", "PT-1 pressure (5-min averages)", "psi", [hours(a) for a, _, _ in g],
                [p for _, p, _ in g], events=ev, tint_group="Spools", range=(0, 2262))
    twin_series("tt1", "TT-1 temperature (5-min averages)", "°C", [hours(a) for a, _, _ in g],
                [c for _, _, c in g], events=ev)


# ------------------------------------------------------------------ the small-bore line

def small_bore_line(M):
    """Placements for the small-bore spools around photo c, bolted the way photos a and c show.

    Spool 12 (3453 mm, flanged both ends) is the 2" run in photo c, heading north from RUN_START
    (its south flange face) to the flange where the run ends at the top of the photo. Spool 5 is
    bolted to its south flange: 410 mm south, the corner elbow turning west, then the 860 mm leg
    running west to the test header (photo a). Spool 4 (5397 mm) is the pipe lying on the floor
    east of the run. Returns {ctrl: place} plus "header": spool 5's west flange (point, normal)."""
    by = {sd["ctrl"]: sd for sd in pack.SPOOLS}

    def probe(sd):
        sp = piping.Spool("probe", sd["nps"], M, sch=sd["sch"])
        sp.walk(sd["route"], direction=sd["start"])
        for rec in sp.parts:
            rec["mb"].bm.free()
        return sp
    g = piping.GASKET_T / 1000
    s5 = probe(by[5])
    yaw = Matrix.Rotation(math.atan2(-RUN_DIR.x, RUN_DIR.y), 4, "Z")
    # Spool 12: drawing east -> along the run.
    T12 = Matrix.Translation(RUN_START) @ yaw @ Matrix.Rotation(math.pi / 2, 4, "Z")
    # Spool 5: drawing up -> north (its first flange faces spool 12), down -> south, west -> west.
    R5 = yaw @ Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).to_4x4()
    T5 = Matrix.Translation(RUN_START - RUN_DIR * g) @ R5
    west = T5 @ s5.joints[-1]["pos"]
    # Spool 4 lying on the floor: drawing south -> north, its elbow's 'down' -> east.
    R4 = Matrix(((0, 0, -1), (0, -1, 0), (-1, 0, 0))).to_4x4()
    T4 = Matrix.Translation((2.62, 5.55, 0.083)) @ Matrix.Rotation(math.radians(5), 4, "Z") @ R4

    yaw_deg = math.degrees(math.atan2(-RUN_DIR.x, RUN_DIR.y))

    def on_run(d, s=0.0, kind="cone"):
        p = RUN_START + RUN_DIR * d + Vector((-RUN_DIR.y, RUN_DIR.x, 0)) * s
        return (p.x, p.y, yaw_deg, kind)
    corner_y = (T5 @ s5.joints[-1]["pos"]).y
    return {
        # Stands measured in photos a and c: the valve stand and the second stand under the run,
        # the stand under the corner and the grey one under the west leg.
        12: {"matrix": T12, "mated": {0: "bolt"},
             "stands": [on_run(0.75, 0.08, "cone_y"), on_run(2.35, 0.06, "cone_y")]},
        5: {"matrix": T5, "mated": {0: None, 1: "bolt"},
            "stands": [(1.62, corner_y, yaw_deg + 90, "cone_y"), (0.92, corner_y, yaw_deg + 90, "cone_grey")]},
        4: {"matrix": T4},
        "header": (west, (T5.to_3x3() @ s5.joints[-1]["normal"]).normalized()),
    }


def test_header(M, joint, studs):
    """The fill/vent header bolted to the west end of spool 5 (photo a): an elbow up, a riser to a
    tee with a ball valve and plug on its branch, and a test blind on top (test equipment, not in
    the pack). joint: (face point, outward normal) of the flange it bolts to."""
    face, normal = joint
    sp = piping.Spool("TestHeader", 2, M, sch="160")
    sp.walk([("flange",), ("pipe", 60), ("elbow", "U"), ("pipe", 150),
             ("tee", [("E", [("pipe", 60), ("valve",), ("plug",)]), ("U", [("pipe", 90), ("flange",)])])],
            start=(0, 0, 0), direction="W")
    j = sp.joints[-1]
    piping.test_blind(sp, j["pos"], j["normal"], 2, M, paint="black", vent=True)
    yaw = math.atan2(normal.y, normal.x) - math.pi     # drawing west -> along `normal`
    root = sp.build(location=face + normal * (piping.GASKET_T / 1000), collection="Test station")
    root.rotation_euler = (0, 0, yaw)
    for rec in sp.parts:
        if rec.get("obj"):
            twin_tag(rec["obj"], "test-equipment")
    twin_tag(root, "test-equipment")
    import bpy
    bpy.context.view_layer.update()
    W = root.matrix_world
    piping.bolt_joint(W @ j["pos"], (W.to_3x3() @ j["normal"]).normalized(), 2, studs[2],
                      piping.CL600[2]["T"] / 1000, "Stud", collection="Bolting", twin="test-equipment")
    return root


# ------------------------------------------------------------------ world

def build(ctx):
    global PM
    rng = ctx.rng
    SM = shop.mats()
    M = piping_mats()
    PM = prop_mats()
    PM["steel_dark"] = SM["steel_dark"]

    # Building
    shop.floor(SM, material("floor_concrete", texture=floor_texture(), roughness=0.78))
    shop.walls(SM)
    shop.columns(SM)
    shop.roof(SM)
    shop.doors(SM)
    shop.lights(SM)
    twin_tag(shop.crane(SM, "Crane_C9808", shop.L - 3.6, 2.2, "C9808"), "crane-C9808")
    twin_tag(shop.crane(SM, "Crane_C9610A", 1.15, -5.2, "C9610-A"), "crane-C9610-A")
    props.duct(SM)

    # Pipe stands and stud prefabs
    stands = {
        "cone": [props.cone_stand(f"Cone_{c}{i}", PM[f"pe_{c}"], PM["hole"]) for i, c in
                 enumerate(("yellow", "yellow2", "yellow", "yellow2", "yellow", "yellow2", "yellow",
                            "grey", "yellow", "yellow2", "grey", "yellow", "red", "yellow2", "green"))],
        "star": [props.star_stand(f"Star_{c}{i}", PM[f"pe_{c}"]) for i, c in
                 enumerate(("yellow", "yellow2", "yellow", "yellow2", "grey"))],
    }
    stands["cone_blue"] = [props.cone_stand("Cone_blue", PM["pe_blue"], PM["hole"])]
    stands["cone_y"] = [stands["cone"][i] for i in (0, 1, 3)]
    stands["cone_grey"] = [props.cone_stand("Cone_grey", PM["pe_grey"], PM["hole"])]
    studs = {n: piping.stud_prefab(n, M) for n in (2, 6, 8, 10, 12, 16)}

    # Paint-marker labels for every spool, in one atlas
    px, rects = text_atlas(spools.marking_lines(pack.SPOOLS), 40, "#ecebe6", italic=0.12, jitter=0.012)
    atlas = (texture("marker_atlas", px, fmt="png"), rects, px.shape[1] / px.shape[0])

    def crib(xy, yaw):
        props.cribbing(PM, xy, yaw, 0.9)
    line = small_bore_line(M)
    for sd in pack.SPOOLS:
        place = line.get(sd["ctrl"]) or LAYOUT[sd["ctrl"]]
        sd["setup"] = SETUP.get(sd["ctrl"], "Placed in the test spread to fit the photos (not "
                                            "individually identifiable in them).")
        spools.build_spool(sd, M, place, studs, stands, atlas, rng, cribbing=crib)
        spools.spool_record(sd)
    spools.test_equipment_record()
    test_header(M, line["header"], studs)
    for od in OTHER:
        sd = dict(od, iso=od["name"], sch="80")
        spools.build_spool(sd, M, od, studs, stands, atlas, rng, cribbing=crib, sid="other-work")
    twin_record("other-work", "Other work in the shop", "Not part of Pressure Test Pack 1", group="Shop",
                color="#8a8f96",
                fields=[("Why it's here", "The photos show more spools on the floor than Pack 1 contains. "
                                          "These generic spools stand in for them so the scene matches "
                                          "the photographs."),
                        ("Data", "None: not in the test pack.")])

    # Test station 1 on the block wall, #2 on the west wall, deadweight on the floor
    docs = {"scada": os.path.join(DOCS, "scada-trend.png"),
            "pt1_photo": os.path.join(REF, "d-pt1-transmitter.jpg"),
            "ddw_photo": os.path.join(REF, "e-ddw-007.jpg")}
    ts1 = props.test_station(PM, "TS1", "TEST STATION #1", (shop.W / 2 - 0.02, 8.4), (-1, 0, 0), docs)
    twin_tag(ts1["panel"], "station-1")
    twin_tag(ts1["transmitters"], "inst-PT-1")
    ts2 = props.test_station(PM, "TS2", "TEST STATION #2", (-shop.W / 2 + 0.02, 4.8), (1, 0, 0), docs)
    twin_tag(ts2["panel"], "station-2")
    twin_tag(props.deadweight(PM, "DDW-007", (6.35, 7.7, 0.0), 20, docs), "inst-DDW-007")
    a = ts1["anchors"]
    twin_gauge("PT-1", a["PT-1"], "pt1", record="inst-PT-1")
    twin_gauge("TT-1", a["TT-1"], "tt1", record="inst-TT-1", digits=1)
    twin_gauge("DDW-007", (6.35, 7.7, 0.25), "pt1", record="inst-DDW-007", digits=1)

    # Test hoses: station to the deadweight and the small-bore line, on to the big-bore spread;
    # the yellow air hose looping on the floor in front of photo b's camera
    props.hose(PM, "TestHose", [a["hose"], (6.9, 8.0, 0.0), (6.35, 7.75, 0.04)], 0.011)
    props.hose(PM, "TestHose2", [(6.35, 7.7, 0.04), (5.2, 7.1, 0.0), (3.4, 6.4, 0.0), (2.2, 5.2, 0.0),
                                 (1.62, 4.6, 0.0), (1.55, 4.35, 0.45)], 0.011)
    props.hose(PM, "TestHose3", [(1.2, 4.6, 0.0), (0.2, 5.5, 0.0), (-0.8, 6.6, 0.0), (-1.6, 7.6, 0.0),
                                 (-1.9, 7.9, 0.52)], 0.011)
    props.hose(PM, "AirHose", [(3.9, 11.3, 0), (3.3, 11.0, 0), (2.95, 10.55, 0), (3.2, 10.2, 0),
                               (3.6, 10.45, 0), (3.3, 10.95, 0), (2.9, 11.4, 0), (2.7, 12.6, 0)], 0.01, "hose_yellow")
    # The 1" test line resting in the same saddles, 0.1 m west of spool 4's run (photos a, c):
    # valve, nipple, elbow and plug at its south end, a plug at the north end
    tl = piping.Spool("TestLine1in", 1, M)
    side = Vector((-RUN_DIR.y, RUN_DIR.x, 0)) * 0.10
    a1 = RUN_START + RUN_DIR * 0.66 + side + Vector((0, 0, -0.013))
    b1 = RUN_START + RUN_DIR * 3.75 + side + Vector((0, 0, -0.013))
    tl.part("pipe", 1)
    tl.mb.rod(a1, b1, 0.0167, M["rust_pipe"], 10)
    p = tl.ball_valve(a1, -RUN_DIR, 1, lever_dir=Vector((-1, 0, 0.6)))
    tl.part("nipple", 1)
    tl.mb.rod(p, p - RUN_DIR * 0.15, 0.0167, M["olet"], 10)
    out = Vector((-0.7, 0, -0.7)).normalized()
    p = tl.threaded_elbow(p - RUN_DIR * 0.15, -RUN_DIR, out, 1)
    tl.plug(p, out, 1)
    p = tl.ball_valve(b1, RUN_DIR, 1, lever_dir=Vector((1, 0, 0.4)))   # its north end (photo c, top)
    tl.plug(p, RUN_DIR, 1)
    root = tl.build(collection="Test station")
    twin_tag(root, "station-1")

    # Racks, pallets and shop furniture
    flanges = props.flange_prefabs(PM, rng)
    props.flange_rack(PM, flanges, rng, (-shop.W / 2 + 0.25, 7.9), 90, 4.4)
    props.flange_rack(PM, flanges, rng, (-shop.W / 2 + 0.25, 2.5), 90, 1.8)
    props.flange_rack(PM, flanges, rng, (shop.W / 2 - 0.75, 13.2), 90, 4.4)
    props.flange_rack(PM, flanges, rng, (shop.W / 2 - 0.75, 18.4), 90, 4.4)
    props.stud_pallet(PM, studs[10][0], (3.5, 7.4), 8, rng)                   # photo b, lower left
    props.stud_pallet(PM, studs[12][0], (2.75, 9.5), -4, rng, rows=1)          # photo c, top
    # Stands measured on the floor in photos a and c (feet, which both photos agree on). The ones
    # in the foreground of photo a are a smaller type: 0.75 of the others, from their size there.
    for x, y, yaw, kind, n, sc in ((2.0, 7.83, -100, "cone", 1, 1.0),        # photo c: the empty one
                                   (-0.46, 4.29, 30, "cone", 3, 0.75), (-0.02, 4.31, 0, "cone_blue", 1, 0.75),
                                   (0.39, 4.09, 20, "star", 1, 0.75), (1.0, 4.08, -103, "cone", 1, 0.75),
                                   (3.1, 8.4, 0, "cone_grey", 1, 1.0)):
        for k in range(n):
            instance(stands[kind][0 if kind != "cone" else 3], "PipeStand", (x, y, k * 0.05 * sc), (0, 0, yaw),
                     scale=sc, collection="Pipe stands")
    props.cribbing(PM, (-1.7, 3.4), 30)
    props.cribbing(PM, (-3.6, 7.4), 80, 1.1)
    props.grating(PM, (-1.6, 6.9), (1.0, 3.2), 0)
    props.grating(PM, (-3.9, 11.2), (1.0, 2.4), 90)
    props.jack_stand(PM, (-1.3, 5.11), 0.9)
    props.booth(PM, (-5.6, 27.6), (3.4, 2.6, 2.7))
    props.cabinet(PM, (4.6, 29.9), 0)
    props.cabinet(PM, (-6.9, 6.0), 90, "enclosure", (0.8, 0.5, 1.0))
    props.bench(PM, (-6.85, 3.6), 90, 2.2)
    props.bench(PM, (6.95, 24.0), 90, 2.4)
    props.welder(PM, (-2.8, 27.8), 0)
    props.welder(PM, (-4.4, 1.0), 90)
    spare = [(-6.3, 1.1), (-5.6, 1.0), (2.2, 1.2), (3.0, 1.3), (-1.8, 2.0), (6.6, 4.4), (6.7, 5.4),
             (2.6, 3.0), (3.4, 2.8), (4.4, 3.4),
             (-6.7, 21.5), (-6.0, 22.2), (5.9, 17.0), (6.3, 16.0), (0.4, 18.6), (-0.6, 19.1), (2.4, 4.4)]
    for i, (x, y) in enumerate(spare):        # spare stands, some stacked, as in the photos
        kind = "cone" if i % 3 else "star"
        pre = stands[kind][rng.randrange(len(stands[kind]))]
        for k in range(1 if i % 4 else 3):
            instance(pre, "SpareStand", (x, y, k * 0.06), (0, 0, rng.uniform(0, 360)), collection="Pipe stands")

    overview_record()
    instrument_records()
    test_series()

    for photo, c in CAMERAS.items():
        photo_camera(photo, c["location"], c["target"], focal_35mm=23, size=c["size"])
    sun(elevation=15.5, azimuth=87, strength=3.0, color="#ffe2bf")
    sky("#e6eef6", 3.0, ground="#a59680")
    fog("#d8d2c6", 40, 160)
    interior(key_direction=(0.15, -0.25, 1.0), key=2.4, ambient=0.95, env=0.7, exposure=1.0)
    a = CAMERAS["a-test-bay-to-door.jpg"]
    camera(a["location"], a["target"], 22.9)
