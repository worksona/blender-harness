"""The scenario: one spool's life from drawings to turnover, as data.

Everything the sim shows comes from here: where the five stations are, the timeline of events
(sim time in days from EPOCH), which documents the spool needs and when each arrived, and the
state the spool is in at every point. world.py turns it into geometry, motion and twin records;
a real system would export this file.

The job is Purnell's 2024-062A for Arc Resources (10-16 sales gas rerouting, Kakwa). The spool
is control 1 of Pressure Test Pack 1 (its isometric, BOM and weld table come from the test pack,
see ../purnell-test-shop/pack.py); the hydrotest date is the real one (29 April 2024). The
purchasing, shipping, hold and field dates around it are a plausible reconstruction, not records.
"""

EPOCH = "2024-04-01"
END = 44.0
PREVIEW_T = 8.45         # what the still render shows: the truck at the fab dock, on hold

# ------------------------------------------------------------------ stations (Blender metres)

STATIONS = {
    "office": dict(n=1, title="Home office / Engineering", pad=(-204, -106, -116, -38),
                   centre=(-160, -74), door=(-160, -62, 0)),
    "vendor": dict(n=2, title="Global vendors", pad=(-110, 58, 0, 134),
                   centre=(-55, 100), door=(-55, 85, 0), dock=(-55, 74)),
    "fab": dict(n=3, title="Fab shop", pad=(66, 56, 154, 134),
                centre=(110, 100), door=(110, 84.5, 0), dock=(110, 72)),
    "field": dict(n=4, title="Field site", pad=(-72, -118, 92, -60),
                  centre=(10, -90), door=(10, -70, 0)),
    "qc": dict(n=5, title="QC / Reporting / Turnover", pad=(110, -112, 190, -48),
               centre=(150, -82), door=(150, -68, 0)),
}

ROAD_Y = 12.0                 # the spine road; each station has a spur down to it
ROAD_W = 7.0

# ------------------------------------------------------------------ the spool

SPOOL_CTRL = 1
PO = "PO-7842-33"
STAND = (110, 64, 0.0)        # where the spool is fabricated and tested (fab yard, by the doors)
LAYDOWN = (10, -85, 0.0)      # strung out beside the trench
TRENCH = (10, -92, -1.55)     # installed
TRENCH_X = (-50, 70)          # the open cut
TRENCH_DEPTH = 2.4
TRENCH_HALF = 3.4        # half width at grade (battered walls)

# Documents the spool needs (the eight columns of the document workflow) and when each arrived.
DOCS = [
    ("Drawings / revisions (ISO rev 0)", 0.0),
    ("Purchase order " + PO, 1.0),
    ("Vendor data book (shipping docs, certificates)", 6.5),
    ("Material test report (MTR)", 12.4),
    ("Weld / NDE records (RT, MT, hardness)", 21.0),
    ("Pressure test package (QF-9, Pack 1)", 28.5),
    ("Field inspection report", 39.0),
    ("Turnover dossier", 41.5),
]

# Spool state over time (harness.sim.twin_state).
STATE = [(0.0, "pending"), (7.0, "active"), (8.4, "hold"), (12.4, "active"), (31.0, "ok"),
         (34.0, "active"), (39.0, "ok"), (41.5, "done")]

# Timeline events (the replay bar's markers; "hold" shows the banner until `until`).
EVENTS = [
    dict(t=0.0, label="Isometrics issued (rev 0)"),
    dict(t=1.0, label=f"{PO} issued to vendor"),
    dict(t=7.0, label="Material shipped from vendor"),
    dict(t=8.4, label="DOCUMENT HOLD: MTR missing", kind="hold", until=12.4,
         detail=f"{PO} · 10\" CS pipe spool · MTR not received from vendor · fabrication on hold"),
    dict(t=10.0, label="Vendor documents requested"),
    dict(t=12.4, label="MTR received, hold released"),
    dict(t=12.5, label="Fabrication starts"),
    dict(t=19.0, label="NDE: 100% RT, MT on LET welds"),
    dict(t=28.35, label="Hydrotest Pack 1 accepted (15,315 kPa, 15 min)"),
    dict(t=31.0, label="Primed, released for shipment"),
    dict(t=33.6, label="Spool delivered to site"),
    dict(t=36.5, label="Lowered in and tied in"),
    dict(t=39.0, label="Field inspection signed off"),
    dict(t=41.5, label="Turnover dossier issued"),
]

# Document flows between stations: (label, from, to, t0, t1, colour).
FLOWS = [
    ("Isometrics", "office", "fab", 0.0, 1.0, "#6cb6ff"),
    (PO, "office", "vendor", 1.0, 2.0, "#6cb6ff"),
    ("Shipping docs", "vendor", "fab", 6.5, 7.5, "#ffd56b"),
    ("Request: MTR", "fab", "vendor", 10.0, 11.0, "#ff8a6b"),
    ("MTR (heat AG2198)", "vendor", "fab", 11.5, 12.4, "#5fd38a"),
    ("RT / MT reports", "fab", "qc", 21.0, 22.0, "#6cb6ff"),
    ("QF-9 test report", "fab", "qc", 28.5, 29.5, "#6cb6ff"),
    ("Installation record", "field", "qc", 39.0, 40.0, "#6cb6ff"),
    ("Turnover dossier", "qc", "office", 41.5, 42.5, "#5fd38a"),
]

# Material moves (sim days): the shipment from the vendor, and the finished spool to site.
# A truck faces +X at yaw 0; it drives dock -> spine road -> dock.
_VD = STATIONS["vendor"]["dock"]
_FD = STATIONS["fab"]["dock"]
_FX = STATIONS["field"]["door"][0]
_QX = STATIONS["qc"]["door"][0]
TRUCK_1 = [(6.8, (*_VD, 0), -90), (7.0, (*_VD, 0), -90), (7.3, (_VD[0], ROAD_Y, 0), 0),
           (8.0, (_FD[0], ROAD_Y, 0), 90), (8.3, (*_FD, 0), 90), (9.0, (*_FD, 0), 90),
           (9.3, (_FD[0], ROAD_Y, 0), 180), (10.0, (_VD[0], ROAD_Y, 0), 90), (10.3, (*_VD, 0), 90)]
TRUCK_2 = [(31.0, (_FD[0] + 18, _FD[1] - 8, 0), 90), (31.3, (_FD[0] + 18, _FD[1] - 8, 0), 90),
           (31.6, (*_FD, 0), -90), (32.2, (*_FD, 0), -90), (32.5, (_FD[0], ROAD_Y, 0), 180),
           (33.2, (_FX, ROAD_Y, 0), -90), (33.6, (_FX, -74, 0), -90), (34.5, (_FX, -74, 0), -90),
           (34.8, (_FX, ROAD_Y, 0), 0), (35.4, (_QX, ROAD_Y, 0), -90), (35.8, (_QX, -60, 0), -90)]
BED_Z = 1.25

# Illustrative station workloads from the AIMQC concept board (not from Purnell's records).
WORKLOAD = {
    "office": [("Drawings / revisions", 18, 20), ("ITPs", 12, 12), ("Procedures", 10, 10), ("Approvals", 8, 10)],
    "vendor": [("Purchase orders", 6, 6), ("Shipping docs", 5, 6), ("Certificates", 4, 6), ("Material test reports", 3, 6)],
    "fab": [("WPS / PQR", 6, 6), ("Welder quals", 8, 8), ("Weld maps", 5, 6), ("NDE reports", 4, 6)],
    "field": [("Receiving records", 8, 10), ("Installation records", 6, 8), ("Field inspection notes", 4, 6),
              ("Test preparation", 2, 4)],
    "qc": [("NCR closure", 3, 6), ("Test reports", 2, 4), ("Punch items", 1, 4), ("Turnover package", 0, 4)],
}
