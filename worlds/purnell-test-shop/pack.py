"""Pressure Test Pack 1 (Purnell job 2024-062A for Arc Resources), transcribed from
docs/07-02_Pressure_Test_Pack_1.pdf.

Everything here is data: the QF-9 test report, the line list, the calibration certificates, the
SCADA trend, and every spool isometric (bill of materials, weld map, and the route that the
geometry is built from). Values are as written on the documents, including their quirks; see
NOTES for discrepancies found while transcribing.

Routes use the isometric's own axes: N/S/E/W horizontal (north arrow on every sheet), U/D vertical.
Lengths are millimetres. Route steps:
  ("flange",)                      weld-neck flange at an open end (start or finish)
  ("pipe", L, [olets...])          pipe of cut length L (BOM); olets: (offset_from_start, dir, kind)
  ("elbow", dir)                   90 deg LR elbow turning to dir
  ("tee", [(dir, [steps]), ...])   tee; each listed port continues with its own steps
  ("reducer", nps, "conc"|"ecc")   reducer to nps
  ("blind",)                       blind flange used as an end plate (dummy legs)
  ("let",)                         attachment (LET) weld where a dummy leg meets its elbow
Welds are lettered in build order; "weld_order" maps them to the drawing's letters where the
drawing letters them differently (None = a weld the drawing doesn't show).
Olet kinds: vent (TOL + nipple + ball valve + plug), vent_half (1/2" version), tol (TOL only),
wol_flange (WOL + 2" WN flange).
"""

REPORT = {
    "form": "QF-9 Pressure Test Report",
    "company": "Purnell Energy Services",
    "customer": "Arc Resources",
    "project": "10-16 Sales Gas Rerouting (10-16)",
    "job": "2024-062A",
    "site": "10-16-062-04 W6M",
    "package": "1",
    "code": "ASME B31.3",
    "location": "Purnell Shop",
    "flange_rating": "600#",
    "duration": "15 min",
    "design_pressure": "10,200 kPa (1,479 psi)",
    "medium": "Water",
    "test_min": "15,315 kPa (2,221 psi)",
    "test_max": "15,596 kPa (2,262 psi)",
    "deadweight": "0 to 68,948 kPa (0 to 10,000 psi), serial PES: DDW-7",
    "recorder": "0 to 68,948 kPa (0 to 10,000 psi), serial PES: PT-1",
    "purnell_rep": "Cameron Janhsen, April 29, 2024",
    "customer_rep": "Robyn Maloney, April 29, 2024",
    "test_date": "2024-04-29",
}

# Common title-block data on every isometric.
ISO_COMMON = {
    "Design": "10,205 kPa, -45 °C to 38 °C",
    "Min. test": "15,307 kPa, ambient",
    "Test medium": "Water",
    "Service": "NFS",
    "WPS": "PES-1N (Rev. 2)",
    "MPI / X-ray": "100% / 100%",
    "PWHT": "N/A",
    "Gap shot": "10%",
    "Hardness": "Yes",
    "Piping spec": "CLS",
    "Code": "ASME B31.3",
    "Owner": "Arc Resources Ltd.",
    "Project": "2024-062A",
    "Zone": "Kakwa",
    "LSD": "10-16-062-04 W6M",
    "Drafter": "SEC",
}

GASKET = ("GASKET, ASME 600 RF, 3.2mm, FLEXITALLIC 'FLEXICARB' CGI, 304L OR 316L SS WINDINGS AND "
          "INNER RING, FLEXIBLE GRAPHITE FILLER, ASME B16.20")
VALVE = ("VALVE, BALL, 3000 PSI, FNPT, RP, A350-LF2-CL1, 316 SS TRIM, RTFE SEATS, 3 PIECE 4 BOLT "
         "DESIGN, FLOATING, LEAVER OP., NACE, 30BVTT4H")
NIPPLE = "NIPPLE, SMLS, A333-6, NACE, 100mm LG, TBE (100.000 MM LG)"
PLUG = "PLUG, HEX HEAD, THRD, A350-LF2 CL1, NACE"
TOL = "TOL, CL6000, A350-LF2 CL1, NACE"


def pipe(sch):
    return f"PIPE, BE, SCH. {sch}, SMLS, A333-6, NACE"


def elbow(sch):
    return f"ELBOW, 90 LR, SCH. {sch}, BW, A420-WPL6, NACE"


def flange(sch):
    return f"FLANGE, WN, CL600, RF, SCH. {sch}, A350-LF2 CL1, NACE"


def studs(n, length):
    return (f"({n}) STUD BOLTS, ASTM A193-B7M c/w (2 PER STUD) ASTM A194-2HM HEAVY SEMI FINISHED "
            f"HEX NUTS ({length:.3f} MM LG)")


def W(id, size, type_, welder, xray="", mpi="", ht="", vt="DM"):
    return {"id": id, "size": size, "type": type_, "welder": welder, "xray": xray, "mpi": mpi,
            "ht": ht, "vt": vt}


SPOOLS = [
    {
        "ctrl": 1, "iso": "273.0-NG-CLS-720522-38H-A", "line": "273.0-NG-CLS-720522-38H", "rev": 0,
        "nps": 10, "sch": "80", "insulation": "38H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2198", "10", pipe(80), "1729 mm"),
            (2, "51597", "10X1", TOL, 2),
            (3, "533B", "10", elbow(80), 1),
            (4, "I66", "1", NIPPLE, 2),
            (5, "YB0206", "1", PLUG, 2),
            (6, "134005", "10", flange(80), 2),
            (7, "", "10", GASKET, 2),
            (8, "", "1-1/4", studs(16, 220), 2),
            (9, "231008", "1", VALVE, 2),
        ],
        "welds": [W("A", '10"', "BW", "JI", "XF-53"), W("C", '1"', "LET", "JI", mpi="MT-9"),
                  W("D", '10"', "BW", "JI", "XF-52"), W("E", '10"', "BW", "JI", "XF-51", ht="XF-51")],
        "route": [("flange",), ("pipe", 1729, [(1059, "U", "vent"), (1059, "D", "vent")]),
                  ("elbow", "S"), ("flange",)],
        "start": "E",
        "weld_order": ["A", "C", None, "D", "E"],
        "inferred": ["BOM lists two TOL vent assemblies but the sheet shows one at weld C; "
                     "the second is modelled as a drain on the underside at C."],
    },
    {
        "ctrl": 2, "iso": "273.0-NG-CLS-720522-38H-B", "line": "273.0-NG-CLS-720522-38H", "rev": 0,
        "nps": 10, "sch": "80", "insulation": "38H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2198", "10", pipe(80), "1535 mm"),
            (2, "51597", "10X1", TOL, 2),
            (3, "533B", "10", elbow(80), 1),
            (4, "I66", "1", NIPPLE, 2),
            (5, "YB0206", "1", PLUG, 2),
            (6, "22/36388", "10", flange(80), 2),
            (7, "", "10", GASKET, 2),
            (8, "", "1-1/4", studs(16, 220), 2),
            (9, "231008", "1", VALVE, 2),
        ],
        "welds": [W("A", '10"', "BW", "JI", "XF-3", ht="XF-3"), W("B", '1"', "LET", "JI", mpi="MT-1"),
                  W("C", '1"', "LET", "JI", mpi="MT-2"), W("D", '10"', "BW", "JI", "XF-4"),
                  W("E", '10"', "BW", "JI", "XF-5")],
        "route": [("flange",), ("pipe", 1535, [(186, "D", "vent"), (1118, "U", "vent")]),
                  ("elbow", "U"), ("flange",)],
        "start": "S",
    },
    {
        "ctrl": 3, "iso": "60.3-NG-CLS-720540-25H-A", "line": "60.3-NG-CLS-720540-25H", "rev": 0,
        "nps": 2, "sch": "160", "insulation": "25H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2073", "2", pipe(160), "252 mm"),
            (2, "AG2073", "2", pipe(160), "278 mm"),
            (3, "AG2073", "2", pipe(160), "1579 mm"),
            (4, "51597", "2X1", TOL, 1),
            (5, "07VPY, 981B", "2", elbow(160), 2),
            (6, "I66", "1", NIPPLE, 1),
            (7, "YB0206", "1", PLUG, 1),
            (8, "0618", "2", flange(160), 2),
            (9, "", "2", GASKET, 1),
            (10, "", "5/8", studs(8, 115), 1),
            (11, "231008", "1", VALVE, 1),
        ],
        "welds": [W("A", '2"', "BW", "GC", "XF-18", ht="XF-18"), W("B", '2"', "BW", "GC", "XF-19"),
                  W("C", '2"', "BW", "GC", "XF-20"), W("D", '1"', "LET", "GC", mpi="MT-4"),
                  W("E", '2"', "BW", "GC", "XF-21"), W("F", '2"', "BW", "GC", "XF-22"),
                  W("G", '2"', "BW", "GC", "XF-23")],
        "route": [("flange",), ("pipe", 252), ("elbow", "W"), ("pipe", 278, [(139, "U", "vent")]),
                  ("elbow", "S"), ("pipe", 1579), ("flange",)],
        "start": "U",
    },
    {
        "ctrl": 4, "iso": "60.3-NG-CLS-720540-25H-B", "line": "60.3-NG-CLS-720540-25H", "rev": 0,
        "nps": 2, "sch": "160", "insulation": "25H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2073", "2", pipe(160), "5397 mm"),
            (2, "07VPY", "2", elbow(160), 1),
            (3, "0618", "2", flange(160), 2),
            (4, "", "2", GASKET, 1),
            (5, "", "5/8", studs(8, 115), 1),
        ],
        "welds": [W("A", '2"', "BW", "GC", "XF-45", ht="XF-45"), W("B", '2"', "BW", "GC", "XF-46"),
                  W("C", '2"', "BW", "GC", "XF-47")],
        "route": [("flange",), ("pipe", 5397), ("elbow", "D"), ("flange",)],
        "start": "S",
    },
    {
        "ctrl": 5, "iso": "60.3-NG-CLS-720540-25H-C", "line": "60.3-NG-CLS-720540-25H", "rev": 0,
        "nps": 2, "sch": "160", "insulation": "25H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2037", "2", pipe(160), "410 mm"),
            (2, "AG2037", "2", pipe(160), "860 mm"),
            (3, "981B", "2", elbow(160), 1),
            (4, "0618", "2", flange(160), 2),
            (5, "", "2", GASKET, 1),
            (6, "", "5/8", studs(8, 115), 1),
        ],
        "welds": [W("A", '2"', "BW", "GC", "XF-39", ht="XF-39"), W("B", '2"', "BW", "GC", "XF-40"),
                  W("C", '2"', "BW", "GC", "XF-41"), W("D", '2"', "BW", "GC", "XF-42")],
        "route": [("flange",), ("pipe", 410), ("elbow", "W"), ("pipe", 860), ("flange",)],
        "start": "D",
    },
    {
        "ctrl": 6, "iso": "168.3-SP-CLS-725310-38H-A", "line": "168.3-SP-CLS-725310-38H", "rev": 0,
        "nps": 8, "sch": "80", "insulation": "38H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "", "8", pipe(80), "715 mm"),
            (2, "", "8", flange(80), 2),
        ],
        "welds": [W("A", '8"', "BW", "GC", "XF-55"), W("B", '8"', "BW", "GC", "XF-54", ht="XF-54")],
        "route": [("flange",), ("pipe", 715), ("flange",)],
        "start": "S",
        "inferred": ["Line number is 168.3 (6\") but the BOM is 8\" pipe and flanges; modelled as 8\"."],
    },
    {
        "ctrl": 7, "iso": "168.3-SP-CLS-725310-38H-B", "line": "168.3-SP-CLS-725310-38H", "rev": 0,
        "nps": 8, "sch": "80", "insulation": "38H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2266", "6", pipe(80), "831 mm"),
            (2, "9XX", "8X6", "REDUCER, ECC., SCH. 80 x SCH. 80, BW, A420-WPL6, NACE", 1),
            (3, "NEED HT#", "6X1", TOL, 1),
            (4, "6XX", "6", elbow(80), 1),
            (5, "NEED HT#", "1", NIPPLE, 1),
            (6, "NEED HT#", "1", PLUG, 1),
            (7, "2304", "8", flange(80), 1),
            (8, "B2A08425", "6", flange(80), 1),
            (9, "", "6", GASKET, 1),
            (10, "", "1", studs(12, 175), 1),
            (11, "", "1", VALVE, 1),
        ],
        "welds": [W("A", '6"', "BW", "DJM", "XF-9"), W("B", '6"', "BW", "DJM", "XF-8"),
                  W("C", "", "", "", ""), W("D", '6"', "BW", "DJM", "XF-7"),
                  W("E", '8"', "BW", "DJM", "XF-6", ht="XF-6")],
        "route": [("flange",), ("reducer", 6, "ecc"), ("pipe", 831, [(415, "U", "vent")]),
                  ("elbow", "E"), ("flange",)],
        "start": "S",
        "weld_order": ["E", "D", "C", "B", "A"],
        "inferred": ["The TOL vent (items 3, 5, 6, 11) is in the BOM but not drawn and weld C is "
                     "blank; it is placed at mid-length on top of the 6\" pipe."],
    },
    {
        "ctrl": 8, "iso": "168.3-SP-CLS-725310-38H-C", "line": "168.3-SP-CLS-725310-38H", "rev": 0,
        "nps": 6, "sch": "80", "insulation": "38H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2266", "6", pipe(80), "218 mm"),
            (2, "AG2266", "6", pipe(80), "2339 mm"),
            (3, "AG2266", "6", pipe(80), "258 mm"),
            (4, "866", "6X6", "TEE, STR., SCH. 80, BW, A420-WPL6, NACE", 1),
            (5, "6XX", "6", elbow(80), 2),
            (6, "B2A08425", "6", flange(80), 3),
        ],
        "welds": [W(c, '6"', "BW", "DJM", f"XF-{n}", ht="XF-10" if c == "A" else "")
                  for c, n in zip("ABCDEFGH", range(10, 18))],
        "route": [("flange",), ("pipe", 218),
                  ("tee", [("S", [("flange",)]),
                           ("E", [("pipe", 2339), ("elbow", "U"), ("pipe", 258), ("elbow", "E"),
                                  ("flange",)])])],
        "start": "E",
    },
    {
        "ctrl": 9, "iso": "168.3-NG-CLS-725311-38H-A", "line": "168.3-NG-CLS-725311-38H", "rev": 0,
        "nps": 8, "sch": "80", "insulation": "38H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2020", "8", pipe(80), "842 mm"),
            (2, "AG2020", "8", pipe(80), "720 mm"),
            (3, "AG2020", "8", pipe(80), "398 mm"),
            (4, "AG2020", "8", pipe(80), "154 mm"),
            (5, "PK808", "8X8", "TEE, STR., SCH. 80, BW, A420-WPL6, NACE", 1),
            (6, "51413", "8X2", "WOL, SCH. 160, BW, A350-LF2 CL1, NACE", 1),
            (7, "10VPY", "8", elbow(80), 3),
            (8, "2304", "8", flange(80), 3),
            (9, "0618", "2", flange(160), 1),
            (10, "", "8", GASKET, 3),
            (11, "", "2", GASKET, 1),
            (12, "", "1-1/8", studs(12, 200), 3),
            (13, "", "5/8", studs(8, 115), 1),
        ],
        "welds": [W("A", '2"', "BW", "DJM", "XF-66"), W("B", '2"', "LET", "DJM", mpi="MT-10"),
                  W("C", '8"', "BW", "DJM", "XF-57"), W("D", '8"', "BW", "DJM", "XF-63"),
                  W("E", '8"', "BW", "DJM", "XF-64"), W("F", '8"', "BW", "DJM", "XF-65"),
                  W("G", '8"', "BW", "DJM", "XF-60"), W("H", '8"', "BW", "DJM", "XF-61"),
                  W("I", '8"', "BW", "DJM", "XF-62"), W("J", '8"', "BW", "DJM", "XF-58"),
                  W("K", '8"', "BW", "DJM", "XF-57"), W("L", '8"', "BW", "DJM", "XF-56")],
        "route": [("flange",), ("pipe", 720), ("elbow", "S"),
                  ("tee", [("W", [("pipe", 842), ("elbow", "S"), ("flange",)]),
                           ("S", [("pipe", 398, [(199, "U", "wol_flange")]), ("elbow", "D"),
                                  ("pipe", 154), ("flange",)])])],
        "start": "E",
        "weld_order": ["I", "H", "G", "D", "E", "F", "C", "A", "B", "J", "K", "L"],
        "notes": ["Weld K is recorded as XF-57, the same report number as weld C; XF-59 does not "
                  "appear anywhere in the pack."],
    },
    {
        "ctrl": 10, "iso": "168.3-NG-CLS-725311-38H-B", "line": "168.3-NG-CLS-725311-38H", "rev": 1,
        "nps": 8, "sch": "80", "insulation": "N/A", "paint": "PRIME & PAINT", "date": "2024-04-15",
        "dummy": True,
        "bom": [
            (1, "AG2020", "8", pipe(80), "958 mm"),
            (2, "LH8438", "8", "FLG, BLIND, RF, ASME 600, ASTM A350-LF2-CL1", 1),
        ],
        "welds": [W("A", '8"', "LET", "DJM", mpi="MT-3")],
        "route": [("let",), ("pipe", 958), ("blind",)],
        "start": "S",
        "notes": ["Dummy leg: design and test pressure N/A, not part of the hydrotest.",
                  "Line list shows revision 1; the sheet's title block shows REV 0."],
    },
    {
        "ctrl": 11, "iso": "60.3-NG-CLS-730218-25H-A", "line": "60.3-NG-CLS-730218-25H", "rev": 0,
        "nps": 2, "sch": "160", "insulation": "25H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2073", "2", pipe(160), "1064 mm"),
            (2, "AG2073", "2", pipe(160), "1979 mm"),
            (3, "10VPY, 65C01M032-1", "2", elbow(160), 2),
            (4, "0618", "2", flange(160), 2),
            (5, "", "2", GASKET, 1),
            (6, "", "5/8", studs(8, 115), 1),
        ],
        "welds": [W("A", '2"', "BW", "GC", "XF-28"), W("B", '2"', "BW", "GC", "XF-27"),
                  W("C", '2"', "BW", "GC", "XF-26"), W("D", '2"', "BW", "GC", "XF-25"),
                  W("E", '2"', "BW", "GC", "XF-24", ht="XF-24")],
        "route": [("flange",), ("pipe", 1064), ("elbow", "S"), ("pipe", 1979), ("elbow", "E"),
                  ("flange",)],
        "start": "D",
    },
    {
        "ctrl": 12, "iso": "60.3-NG-CLS-730218-25H-B", "line": "60.3-NG-CLS-730218-25H", "rev": 0,
        "nps": 2, "sch": "160", "insulation": "25H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2073", "2", pipe(160), "3453 mm"),
            (2, "0618", "2", flange(160), 2),
            (3, "", "5/8", studs(8, 115), 1),
        ],
        "welds": [W("A", '2"', "BW", "GC", "XF-44"), W("B", '2"', "BW", "GC", "XF-43", ht="XF-43")],
        "route": [("flange",), ("pipe", 3453), ("flange",)],
        "start": "E",
    },
    {
        "ctrl": 13, "iso": "60.3-NG-CLS-730218-25H-C", "line": "60.3-NG-CLS-730218-25H", "rev": 0,
        "nps": 2, "sch": "160", "insulation": "25H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2073", "2", pipe(160), "803 mm"),
            (2, "AG2073", "2", pipe(160), "117 mm"),
            (3, "AG2073", "2", pipe(160), "316 mm"),
            (4, "65E11M220", "2X2", "TEE, STR., SCH. 160, BW, A420-WPL6, NACE", 1),
            (5, "51597", "2X1", TOL, 1),
            (6, "07VPY", "2", elbow(160), 1),
            (7, "0618", "2", flange(160), 3),
            (8, "", "2", GASKET, 2),
            (9, "", "5/8", studs(8, 115), 1),
        ],
        "welds": [W("A", '2"', "BW", "GC", "XF-33"), W("B", '2"', "BW", "GC", "XF-32"),
                  W("C", '2"', "BW", "GC", "XF-31"), W("D", '2"', "BW", "GC", "XF-30", ht="XF-30"),
                  W("E", '2"', "BW", "GC", "XF-29"), W("F", '2"', "BW", "GC", "XF-34"),
                  W("G", '1"', "LET", "GC", mpi="MT-5"), W("H", '2"', "BW", "GC", "XF-35")],
        "route": [("flange",), ("pipe", 117), ("elbow", "S"), ("pipe", 803),
                  ("tee", [("W", [("flange",)]),
                           ("E", [("pipe", 316, [(105, "D", "tol")]), ("flange",)])])],
        "start": "W",
        "weld_order": ["E", "D", "C", "B", "A", "F", "G", "H"],
    },
    {
        "ctrl": 14, "iso": "323.8-NG-CLS-730512-51H-A", "line": "323.8-NG-CLS-730512-51H", "rev": 0,
        "nps": 12, "sch": "80", "insulation": "51H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2172", "12", pipe(80), "730 mm"),
            (2, "AG2172", "12", pipe(80), "119 mm"),
            (3, "AG2172", "12", pipe(80), "580 mm"),
            (4, "UXRN", "12X1", TOL, 1),
            (5, "447A", "12", elbow(80), 2),
            (6, "I66", "1", NIPPLE, 1),
            (7, "YB0206", "1", PLUG, 1),
            (8, "LH8275", "12", flange(80), 2),
            (9, "", "12", GASKET, 2),
            (10, "", "1-1/4", studs(20, 225), 2),
            (11, "231008", "1", VALVE, 1),
        ],
        "welds": [W("A", '12"', "BW", "JI", "XF-83"), W("B", '1"', "LET", "JI", mpi="MT-15"),
                  W("C", '12"', "BW", "JI/DF", "XF-82"), W("D", '12"', "BW", "JI", "XF-81"),
                  W("E", '12"', "BW", "JI", "XF-80"), W("F", '12"', "BW", "JI/DF", "XF-79", ht="XF-79"),
                  W("G", '12"', "BW", "JI", "XF-78")],
        "route": [("flange",), ("pipe", 730, [(451, "U", "vent")]), ("elbow", "D"), ("pipe", 119),
                  ("elbow", "S"), ("pipe", 580), ("flange",)],
        "start": "E",
    },
    {
        "ctrl": 15, "iso": "323.8-NG-CLS-730512-51H-B", "line": "323.8-NG-CLS-730512-51H", "rev": 0,
        "nps": 12, "sch": "80", "insulation": "38H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "AG2172", "12", pipe(80), "429 mm"),
            (2, "437B", "12X12", "TEE, STR., SCH. 80, BW, A420-WPL6, NACE", 1),
            (3, "447A", "12", elbow(80), 1),
            (4, "LH8275", "12", flange(80), 3),
            (5, "", "12", GASKET, 3),
            (6, "", "1-1/4", studs(20, 225), 3),
        ],
        "welds": [W("A", '12"', "BW", "GC", "XF-73"), W("B", '12"', "BW", "GC", "XF-74", ht="XF-74"),
                  W("C", '12"', "BW", "GC", "XF-75"), W("D", '12"', "BW", "GC", "XF-76"),
                  W("E", '12"', "BW", "GC", "XF-77")],
        "route": [("flange",),
                  ("tee", [("E", [("flange",)]),
                           ("N", [("pipe", 429), ("elbow", "E"), ("flange",)])])],
        "start": "N",
    },
    {
        "ctrl": 16, "iso": "323.8-NG-CLS-730512-51H-C", "line": "323.8-NG-CLS-730512-51H", "rev": 0,
        "nps": 12, "sch": "80", "insulation": "51H", "paint": "PRIME", "date": "2024-04-15",
        "bom": [
            (1, "B940", "12", elbow(80), 1),
            (2, "LH8275", "12", flange(80), 2),
            (3, "", "12", GASKET, 1),
            (4, "", "1-1/4", studs(20, 225), 1),
        ],
        "welds": [W("A", '12"', "BW", "GC", "XF-1", ht="XF-1"), W("B", '12"', "BW", "GC", "XF-2")],
        "route": [("flange",), ("elbow", "N"), ("flange",)],
        "start": "U",
    },
    {
        "ctrl": 17, "iso": "323.8-NG-CLS-730512-51H-D", "line": "323.8-NG-CLS-730512-51H", "rev": 1,
        "nps": 12, "sch": "80", "insulation": "51H", "paint": "PRIME", "date": "2024-05-13",
        "bom": [
            (1, "AG2172", "12", pipe(80), "2750 mm"),
            (2, "AG2148", "10", pipe(80), "799 mm"),
            (3, "66A21M015", "12X10", "REDUCER, CONC., SCH. 80 x SCH. 80, BW, A420-WPL6, NACE", 1),
            (4, "51272", "12X2", "WOL, SCH. 160, BW, A350-LF2 CL1, NACE", 1),
            (5, "NO HT #S", "10X1", TOL, 2),
            (6, "533B", "10", elbow(80), 1),
            (7, "I66", "1", "NIPPLE, SCH. XXH, SMLS, A333-6, NACE, 100mm LG, TBE (100.000 MM LG)", 1),
            (8, "YB0206", "1", PLUG, 1),
            (9, "LH8275", "12", flange(80), 1),
            (10, "22/36388", "10", flange(80), 1),
            (11, "0618", "2", flange(160), 1),
            (12, "", "10", GASKET, 1),
            (13, "", "2", GASKET, 1),
            (14, "231008", "1", VALVE, 1),
        ],
        "welds": [W("A", '2"', "BW", "DF", "XF-67"), W("B", '2"', "LET", "DF", mpi="MT-11"),
                  W("C", '12"', "BW", "DF", "XF-71"), W("D", '10"', "BW", "DF", "XF-70"),
                  W("E", '10"', "BW", "DF", "XF-157"), W("F", '1"', "LET", "DF", mpi="MT-12"),
                  W("G", '1"', "LET", "DF", mpi="MT-13"), W("H", '10"', "BW", "DF", "XF-68", ht="XF-68"),
                  W("I", '12"', "BW", "DF", "XF-72")],
        "route": [("flange",), ("pipe", 2750, [(1590, "E", "wol_flange")]), ("reducer", 10, "conc"),
                  ("elbow", "W"), ("pipe", 799, [(213, "D", "vent"), (213, "U", "tol")]),
                  ("flange",)],
        "start": "D",
        "weld_order": ["I", "A", "B", "C", "D", "E", "F", "G", "H"],
        "notes": ["TOL item 5 marked 'NO HT #S' on the sheet."],
    },
    {
        "ctrl": 18, "iso": "323.8-NG-CLS-730512-51H-E", "line": "323.8-NG-CLS-730512-51H", "rev": 2,
        "nps": 10, "sch": "80", "insulation": "51H", "paint": "PRIME", "date": "2024-05-13",
        "bom": [
            (1, "AG2148", "10", pipe(80), "551 mm"),
            (2, "AG2148", "10", pipe(80), "1299 mm"),
            (3, "J5", "8", pipe(80), "283 mm"),
            (4, "EP128", "16X10", "REDUCER, ECC., SCH. 80 x SCH. 80, BW, A420-WPL6, NACE", 1),
            (5, "TLC0035081", "10X8", "TEE, RED., SCH. 80 LE x SCH. 80 SE, A420-WPL6, NACE", 1),
            (6, "51597", "10X1", TOL, 2),
            (7, "AVDY", "10X1/2", TOL, 1),
            (8, "C362", "8", elbow(80), 1),
            (9, "I64", "1/2", "NIPPLE, SCH. XXS, SMLS, A333-6, NACE, 100mm LG, TBE (100.000 MM LG)", 1),
            (10, "YB0150", "1/2", PLUG, 1),
            (11, "10WD8", "16", flange(80), 1),
            (12, "134005", "10", flange(80), 1),
            (13, "D12309367", "8", flange(80), 1),
            (14, "", "16", GASKET, 1),
            (15, "", "10", GASKET, 1),
            (16, "", "8", "GASKET, CL600, FLEXITALLIC 'FLEXICARB' CGI, 316 SS WINDINGS/IR, CS OR, "
                          "OR APPROVED EQUAL", 1),
            (20, "231106", "1/2", VALVE, 1),
        ],
        "welds": [W("A", '10"', "BW", "JI", "XF-50"), W("B", '1"', "LET", "JI", mpi="MT-6"),
                  W("C", '1/2"', "LET", "JI", mpi="MT-7"), W("D", '1"', "LET", "JI", mpi="MT-8"),
                  W("E", '10"', "BW", "CS", "XF-154"), W("F", '8"', "BW", "CS", "XF-153", ht="XF-153"),
                  W("G", '8"', "BW", "CS", "XF-152"), W("H", '8"', "BW", "CS", "XF-151"),
                  W("I", '10"', "BW", "CS", "XF-155"), W("J", '10"', "BW", "CS", "XF-156"),
                  W("K", '16"', "BW", "JI", "XF-48", ht="XF-48")],
        "route": [("flange",),
                  ("pipe", 551, [(66, "U", "tol"), (216, "U", "vent_half"), (451, "U", "tol")]),
                  ("tee", [("N", [("pipe", 283), ("elbow", "W"), ("flange",)]),
                           ("W", [("pipe", 1299), ("reducer", 16, "ecc"), ("flange",)])])],
        "start": "W",
        "branch_nps": 8,
        "notes": ["Photo b-corner-crane-c9610.jpg shows this spool: heat AG2148 is painted on the "
                  "pipe next to the green test blind."],
    },
    {
        "ctrl": 19, "iso": "323.8-NG-CLS-730512-51H-F", "line": "323.8-NG-CLS-730512-51H", "rev": 0,
        "nps": 12, "sch": "80", "insulation": "N/A", "paint": "PRIME & PAINT", "date": "2024-04-15",
        "dummy": True,
        "bom": [
            (1, "AG2172", "12", pipe(80), "1770 mm"),
            (2, "", "12", GASKET, 1),
            (3, "LH8420", "12", "FLANGE, BLIND, CL600, RF, A350-LF2 CL1, NACE", 1),
        ],
        "welds": [W("A", '12"', "LET", "DJM", mpi="MT-14")],
        "route": [("let",), ("pipe", 1770), ("blind",)],
        "start": "S",
        "notes": ["Dummy leg: design and test pressure N/A. Overall length 1843 mm "
                  "(pipe 1770 + gasket + blind flange)."],
    },
    {
        "ctrl": 20, "iso": "60.3-NG-CLS-730513-25H", "line": "60.3-NG-CLS-730513-25H", "rev": 1,
        "nps": 2, "sch": "160", "insulation": "38H", "paint": "PRIME", "date": "2024-05-13",
        "bom": [
            (1, "AG2073", "2", pipe(160), "382 mm"),
            (2, "0618", "2", flange(160), 2),
            (3, "", "2", GASKET, 1),
            (4, "", "5/8", studs(8, 115), 1),
        ],
        "welds": [W("A", '2"', "BW", "GC", "XF-38"), W("B", '2"', "BW", "GC", "XF-37", ht="XF-37")],
        "route": [("flange",), ("pipe", 382), ("flange",)],
        "start": "E",
        "notes": ["Line list shows revision 0; the sheet's title block shows REV 1."],
    },
    {
        "ctrl": 23, "iso": "33.4-NG-CLS-730219-25H", "line": "33.4-NG-CLS-730219-25H", "rev": 0,
        "nps": 1, "sch": "XXH", "insulation": "38H", "paint": "PRIME", "date": "2024-04-18",
        "threaded": True,
        "bom": [
            (1, "T781986", "1", "PIPE, TBE, SCH. XXH, SMLS, A333-6, NACE (205.176 MM LG)", "205 mm"),
            (2, "YB0124", "1X1", "TEE, STR., CL6000, THRD, A350-LF2 CL1, NACE", 2),
            (3, "I66", "1", "NIPPLE, SCH. XXH, SMLS, A333-6, NACE, 76mm LG, TBE (76.000 MM LG)", 6),
            (4, "I66", "1", "NIPPLE, SCH. XXH, SMLS, A333-6, NACE, 100mm LG, TBE (100.000 MM LG)", 2),
            (5, "YB0206", "1", PLUG, 1),
            (6, "BESN", "1", "ELBOW, 90 LR, CL6000, THRD, A350-LF2 CL 1, FS, NACE", 3),
            (7, "BT0170G", "2X1", "FLANGE, RED, HUB, THRD, CL600, RF, A350-LF2 CL1, NACE", 1),
            (8, "", "2", GASKET, 1),
            (9, "", "5/8", studs(8, 115), 1),
            (10, "231008", "1", VALVE, 2),
        ],
        "welds": [],
        # Threaded: lengths are nipple lengths; fittings add their own centre-to-end.
        "route": [("flange",), ("pipe", 76),
                  ("tee", [("D", [("pipe", 100), ("valve",), ("plug",)]),
                           ("S", [("pipe", 76), ("elbow", "E"), ("pipe", 205), ("elbow", "S"),
                                  ("pipe", 76), ("elbow", "D"), ("pipe", 100),
                                  ("tee", [("W", [("pipe", 76), ("valve",), ("pipe", 76)]),
                                           ("E", [("pipe", 76)])])])])],
        "start": "S",
        "notes": ["Threaded assembly, no welds. Control numbers 21 and 22 are not in this pack."],
    },
]

# Line list (QF-9 page 2): line, revision, ISO, control number.
LINE_LIST = [(s["line"], s["iso"], s["ctrl"]) for s in SPOOLS]

CALIBRATION = {
    "DDW-007": {
        "title": "Falcon electronic deadweight DDW-007",
        "fields": [
            ("Certificate", "Burke Calibration, Grande Prairie AB, no. 35706"),
            ("Report no.", "BCL2022-C13455"),
            ("Manufacturer / model", "Calscan Falcon-10K"),
            ("Serial", "35706"),
            ("Range", "0 to 10,000 psi"),
            ("Uncertainty", "±ASME 3A of span (0.25%)"),
            ("Calibrated", "2023-11-28"),
            ("Expires", "2024-05-27"),
            ("As received / as left", "In tolerance / in tolerance"),
            ("Lab conditions", "20-24 °C, 30-35% RH, 100-103 kPa"),
            ("Reference standard", "Crystal Engineering 10KPSIXP2I s/n 545487, report 69253, due 2024-01-11"),
            ("Reading in photo", "2243.5 psi"),
        ],
        "table": {"title": "As found = as left (psi)",
                  "columns": ["Reference", "Gauge", "Tolerance", "Diff", "% of reading", "Result"],
                  "rows": [["0", "0", "25", "0", "", "Pass"], ["1999", "2000", "25", "1", "0.05%", "Pass"],
                           ["3999", "4000", "25", "1", "0.03%", "Pass"], ["5997", "6000", "25", "3", "0.05%", "Pass"],
                           ["7998", "8000", "25", "2", "0.03%", "Pass"], ["9996", "10000", "25", "4", "0.04%", "Pass"]]},
    },
    "PT-1": {
        "title": "PT-1 pressure transmitter",
        "fields": [
            ("Tag", "PT-1 (Hydro Testing\\PLC\\TS1\\TS1 MDBUS\\PT-1)"),
            ("Manufacturer / model", "Rosemount 2051"),
            ("Serial", "245897"),
            ("Range", "0 to 10,000 psi"),
            ("Calibrated by", "ControlTech, 2024-04-16 (next 2025-04-16)"),
            ("Location", "Test Station 1"),
            ("Calibration equipment", "Fluke 7003G1 (2377022, 4811301), Fluke 1551A EX (4199009)"),
            ("Reading in photo", "2242 PSI"),
        ],
        "table": {"title": "Calibration (psi)", "columns": ["%", "Applied", "As found", "As left"],
                  "rows": [["0", "0", "3.12", "0"], ["50", "5000", "5003.71", "4999.94"],
                           ["100", "10000", "10003", "9999.92"]]},
    },
    "TT-1": {
        "title": "TT-1 temperature transmitter",
        "fields": [
            ("Tag", "TT-1"),
            ("Manufacturer / model", "Rosemount 344 (as written)"),
            ("Serial", "118261"),
            ("Calibrated by", "ControlTech, 2024-04-16 (next 2025-04-16)"),
            ("Location", "Test Station 1"),
        ],
        "table": {"title": "Calibration (°C)", "columns": ["%", "Applied", "As found", "As left"],
                  "rows": [["0", "0", "0.31", "0.31"], ["50", "20", "20.3", "20.4"],
                           ["100", "50", "50.2", "50.2"]]},
    },
}

# VTScada historical data, Test Station 1, 2024-04-29: 5-minute averages (grid view).
GRID = [  # (time, PT-1 psi, TT-1 degC)
    ("09:45", 10, 12.67), ("09:50", -1, 12.71), ("09:55", -1, 12.76), ("10:00", -1, 12.79),
    ("10:05", -1, 12.83), ("10:10", -1, 12.85), ("10:15", -1, 12.88), ("10:20", 173, 12.74),
    ("10:25", 745, 12.23), ("10:30", 752, 12.34), ("10:35", 1355, 12.18), ("10:40", 1483, 12.23),
    ("10:45", 1485, 12.28), ("10:50", 1556, 12.33), ("10:55", 2098, 12.20), ("11:00", 2240, 12.28),
    ("11:05", 2241, 12.28), ("11:10", 2241, 12.20), ("11:15", 2241, 12.11), ("11:20", 1720, 11.94),
    ("11:25", 1284, 11.82), ("11:30", 745, 11.76), ("11:35", 95, 11.77), ("11:40", -1, 11.76),
    ("11:45", -1, 11.66),
]

# PT-1 trend digitized from the plot view (its labelled points are exact; the ramps between them
# are read off the curve).
TREND = [
    ("09:45", 0), ("10:15", -0.86), ("10:20", -0.5), ("10:21", 90), ("10:22", 95), ("10:23.5", 400),
    ("10:25", 745), ("10:28", 750.1), ("10:35", 752), ("10:37", 1480), ("10:45", 1495), ("10:45.6", 1400),
    ("10:46.4", 1500), ("10:48", 1504.1), ("10:54", 1506), ("10:55.5", 2000), ("11:00", 2227.8),
    ("11:03", 2238), ("11:08", 2241.5), ("11:15", 2241), ("11:20", 2241), ("11:21", 1494),
    ("11:22", 1493.9), ("11:27.5", 1490), ("11:28.5", 750), ("11:30", 744.5), ("11:34", 742),
    ("11:35.5", 60), ("11:36", -0.73), ("11:45", -1),
]

EVENTS = [
    ("10:20", "Pressurising: first stage"),
    ("10:25", "Hold at ~750 psi (leak check)"),
    ("10:37", "Second stage ~1500 psi"),
    ("10:55", "Raising to test pressure"),
    ("11:00", "At test pressure 2,240 psi: 15 min hold"),
    ("11:15", "Hold complete (min 2,221 psi held)"),
    ("11:20", "Depressurising in stages"),
    ("11:36", "Depressurised, 0 psi"),
]

NOTES = [
    "The three uploaded PDFs are byte-identical copies of the same pack.",
    "Control numbers 21 and 22 are not included in the pack.",
    "Spool 9 (725311-38H-A): weld K recorded as XF-57, duplicating weld C; XF-59 is missing.",
    "Spool 7 (725310-38H-B): three items marked NEED HT# on the BOM; weld C blank.",
    "Spool 17 (730512-51H-D): TOLs marked NO HT #S.",
    "Revision mismatches between the line list and title blocks on 725311-38H-B and 730513-25H.",
    "Photos are time-stamped 08:18-08:39 on test day; the SCADA trend shows the test ran 10:20-11:36.",
]
