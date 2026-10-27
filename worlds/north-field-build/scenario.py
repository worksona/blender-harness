"""The scenario: Pressure Test Pack 1's 21 spools from drawings to delivery, as data.

Everything the sim shows comes from here: where the five stations are, the timeline of events
(sim time in days from EPOCH), which documents each spool needs and when it got them, and the
state each spool is in at every point. world.py turns it into geometry, motion and twin records;
a real system would export this file.

The job is Purnell's 2024-062A for Arc Resources (10-16 sales gas rerouting, Kakwa). The spools,
their BOMs, weld tables and the hydrotest (29 April 2024) come from the test pack
(../purnell-test-shop/pack.py). The purchasing, shipping, hold and fabrication dates around them
are a plausible reconstruction, not records.

What the pack does NOT contain is where the spools go: no P&ID, plot plan or tie-in drawing.
So the field station is a laydown yard at 10-16 where the spools arrive and wait, and the
installation, field inspection and turnover steps are left open (their documents never arrive
and the spools stay "at risk"). Add the reference drawings to docs/ to model the tie-ins.
"""

EPOCH = "2024-04-01"
END = 44.0
PREVIEW_T = 30.0         # what the still render shows: the yard full of tested spools

# ------------------------------------------------------------------ stations (Blender metres)

STATIONS = {
    "office": dict(n=1, title="Home office / Engineering", pad=(-204, -106, -116, -38),
                   centre=(-160, -74), door=(-160, -62, 0)),
    "vendor": dict(n=2, title="Global vendors", pad=(-110, 58, 0, 134),
                   centre=(-55, 100), door=(-55, 85, 0), dock=(-55, 74)),
    "fab": dict(n=3, title="Fab shop", pad=(66, 56, 154, 134),
                centre=(110, 100), door=(110, 84.5, 0), dock=(110, 72)),
    "field": dict(n=4, title="Field site (10-16-062-04 W6M)", pad=(-72, -118, 92, -60),
                  centre=(10, -90), door=(10, -70, 0), dock=(10, -76)),
    "qc": dict(n=5, title="QC / Reporting / Turnover", pad=(110, -112, 190, -48),
               centre=(150, -82), door=(150, -68, 0)),
}

ROAD_Y = 12.0                 # the spine road; each station has a spur down to it
ROAD_W = 7.0

# ------------------------------------------------------------------ the spools

PO = "PO-7842-33"
BED_Z = 1.25                  # top of a flatbed's deck

# Fab yard: a 5 x 4 grid of stands south of the shop, one slot per spool (control numbers in
# the pack's order; control 21 and 22 don't exist in the pack).
CTRLS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 23]


def yard_slot(i):
    """Where spool i (0-based) is fabricated and tested: fab yard rows below the shop."""
    cols = 6
    return (76 + (i % cols) * 13.5, 80 - (i // cols) * 7.0, 0.0)


def laydown_slot(i):
    """Where spool i waits at 10-16: rows of cribbing in the laydown yard."""
    cols = 7
    return (-56 + (i % cols) * 20.0, -84 - (i // cols) * 11.0, 0.0)


# Three flatbed trips carry the pack to site (seven spools each); spools are listed by index.
TRIPS = [dict(t0=32.0, spools=range(0, 7)), dict(t0=34.0, spools=range(7, 14)),
         dict(t0=36.0, spools=range(14, 21))]
TRIP_DRIVE = 1.4              # days from leaving the shop to arriving at the site (sim time)
TRIP_UNLOAD = 0.8


def bed_offset(k):
    """Spool k of a trip on the deck (truck frame: +x toward the cab)."""
    return (-4.0 + (k % 4) * 2.3, -0.8 + (k // 4) * 1.0, BED_Z)


def fab_window(i):
    """(start, end) of fabrication for spool i: staggered through the shop after the hold."""
    start = 12.5 + i * 0.55
    return start, start + 4.5


def nde_window(i):
    s, e = fab_window(i)
    return e, e + 1.0


HYDROTEST = (28.0, 28.4)      # Pack 1: 29 April 2024
PAINTED = 31.0

# Documents every spool needs (the eight columns of the document workflow). None = never
# received in this scenario, because the pack has nothing on the field side.
def docs_for(i):
    return [
        ("Drawings / revisions (ISO rev 0)", 0.0),
        ("Purchase order " + PO, 1.0),
        ("Vendor data book (shipping docs, certificates)", 6.5),
        ("Material test reports (heats on the BOM)", 12.4),
        ("Weld / NDE records (RT, MT, hardness)", round(nde_window(i)[1], 2)),
        ("Pressure test package (QF-9, Pack 1)", 28.5),
        ("Field inspection report", None),
        ("Turnover dossier", None),
    ]


def trip_of(i):
    return next(k for k, tr in enumerate(TRIPS) if i in tr["spools"])


def delivered_at(i):
    tr = TRIPS[trip_of(i)]
    return tr["t0"] + TRIP_DRIVE + 0.1


def state_of(i):
    fs, fe = fab_window(i)
    return [(0.0, "pending"), (7.0, "active"), (8.4, "hold"), (12.4, "pending"), (fs, "active"),
            (PAINTED, "ok"), (TRIPS[trip_of(i)]["t0"], "active"), (delivered_at(i), "at_risk")]


# Timeline events (the replay bar's markers; "hold" shows the banner until `until`).
EVENTS = [
    dict(t=0.0, label="Isometrics issued (rev 0), 21 spools"),
    dict(t=1.0, label=f"{PO} issued to vendor"),
    dict(t=7.0, label="Material shipped from vendor"),
    dict(t=8.4, label="DOCUMENT HOLD: MTRs missing", kind="hold", until=12.4,
         detail=f"{PO} · pipe heats AG2198 / AG2073 · MTRs not in the vendor data book · fabrication on hold"),
    dict(t=10.0, label="Vendor documents requested"),
    dict(t=12.4, label="MTRs received, hold released"),
    dict(t=12.5, label="Fabrication starts (control 1)"),
    dict(t=HYDROTEST[0], label="Hydrotest Pack 1: 15,315 kPa, 15 min, accepted"),
    dict(t=PAINTED, label="All 21 spools primed, released for shipment"),
    dict(t=TRIPS[0]["t0"], label="Trip 1 to site (spools 1-7)"),
    dict(t=TRIPS[1]["t0"], label="Trip 2 to site (spools 8-14)"),
    dict(t=TRIPS[2]["t0"], label="Trip 3 to site (spools 15-20, 23)"),
    dict(t=delivered_at(20), label="Pack delivered to the 10-16 laydown; tie-ins await reference drawings"),
]

# Document flows between stations: (label, from, to, t0, t1, colour).
FLOWS = [
    ("Isometrics (21)", "office", "fab", 0.0, 1.0, "#6cb6ff"),
    (PO, "office", "vendor", 1.0, 2.0, "#6cb6ff"),
    ("Shipping docs", "vendor", "fab", 6.5, 7.5, "#ffd56b"),
    ("Request: MTRs", "fab", "vendor", 10.0, 11.0, "#ff8a6b"),
    ("MTRs (AG2198, AG2073…)", "vendor", "fab", 11.5, 12.4, "#5fd38a"),
    ("RT / MT reports", "fab", "qc", 24.0, 25.0, "#6cb6ff"),
    ("QF-9 test report", "fab", "qc", 28.5, 29.5, "#6cb6ff"),
    ("Receiving records", "field", "qc", delivered_at(20), delivered_at(20) + 1.0, "#6cb6ff"),
]

# The vendor delivery (a truck faces +X at yaw 0; it drives dock -> spine road -> dock).
_VD = STATIONS["vendor"]["dock"]
_FD = STATIONS["fab"]["dock"]
_FX = STATIONS["field"]["dock"]
TRUCK_1 = [(6.8, (*_VD, 0), -90), (7.0, (*_VD, 0), -90), (7.3, (_VD[0], ROAD_Y, 0), 0),
           (8.0, (_FD[0], ROAD_Y, 0), 90), (8.3, (*_FD, 0), 90), (9.0, (*_FD, 0), 90),
           (9.3, (_FD[0], ROAD_Y, 0), 180), (10.0, (_VD[0], ROAD_Y, 0), 90), (10.3, (*_VD, 0), 90)]
PARK_2 = (_FD[0] + 18, _FD[1] - 8, 0)


def truck_2_keys():
    """The site truck: parked beside the fab yard, three round trips to 10-16."""
    keys = [(0.0, PARK_2, 90)]
    for tr in TRIPS:
        t = tr["t0"]
        keys += [(t - 0.5, PARK_2, 90), (t - 0.2, (*_FD, 0), -90), (t, (*_FD, 0), -90),
                 (t + 0.3, (_FD[0], ROAD_Y, 0), 180), (t + 1.0, (_FX[0], ROAD_Y, 0), -90),
                 (t + TRIP_DRIVE, (*_FX, 0), -90), (t + TRIP_DRIVE + TRIP_UNLOAD, (*_FX, 0), -90),
                 (t + TRIP_DRIVE + TRIP_UNLOAD + 0.4, (_FX[0], ROAD_Y, 0), 0),
                 (t + TRIP_DRIVE + TRIP_UNLOAD + 1.0, (_FD[0], ROAD_Y, 0), 90),
                 (t + TRIP_DRIVE + TRIP_UNLOAD + 1.2, PARK_2, 90)]
    return keys


# Illustrative station workloads from the AIMQC concept board (not from Purnell's records).
WORKLOAD = {
    "office": [("Drawings / revisions", 21, 21), ("ITPs", 12, 12), ("Procedures", 10, 10), ("Approvals", 8, 10)],
    "vendor": [("Purchase orders", 6, 6), ("Shipping docs", 5, 6), ("Certificates", 4, 6), ("Material test reports", 3, 6)],
    "fab": [("WPS / PQR", 6, 6), ("Welder quals", 8, 8), ("Weld maps", 21, 21), ("NDE reports", 21, 21)],
    "field": [("Receiving records", 21, 21), ("Installation records", 0, 21), ("Field inspection notes", 0, 21),
              ("Tie-in / reference drawings", 0, 1)],
    "qc": [("NCR closure", 1, 1), ("Test reports", 1, 1), ("Punch items", 0, 4), ("Turnover package", 0, 1)],
}
