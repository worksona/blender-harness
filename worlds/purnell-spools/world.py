"""Pressure Test Pack 1, spool by spool: all 21 spools of the pack laid out in drawing
orientation (north up the rows) on their stands, each with a floor placard, and the same
component-level twin as the shop world: click a spool, then a pipe piece, fitting, flange or weld.

Geometry, data and markings come from ../purnell-test-shop (pack.py, spools.py).
"""

import os
import sys

SHOP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "purnell-test-shop")
sys.path.insert(0, SHOP)

from harness import *  # noqa: E402
from harness import piping  # noqa: E402

import pack  # noqa: E402
import props  # noqa: E402
import spools  # noqa: E402
import world as shop_world  # noqa: E402  (materials shared with the shop)

META = {
    "title": "Purnell Pack 1 Spools",
    "description": "All 21 spools of Pressure Test Pack 1 in drawing orientation: every pipe piece, "
                   "fitting, flange and weld with its heat number and NDT record.",
    "tags": ["piping", "data twin", "catalog"],
    "seed": 2024,
    "private": True,      # client documents: never published to the public site
    "render": {"res": "1600x1000", "samples": 32, "view": "Standard"},
    "viewer": {"tone": "neutral"},
}

COLS = 5
CELL = (6.2, 4.6)     # metres per spool cell (x, y)


def build(ctx):
    rng = ctx.rng
    M = shop_world.piping_mats()
    PM = shop_world.prop_mats()
    shop_world.PM = PM
    PM["steel_dark"] = material("steel_dark", "#3c4246", roughness=0.55, metallic=0.5)

    rows = (len(pack.SPOOLS) + COLS - 1) // COLS
    W, D = COLS * CELL[0], rows * CELL[1]
    floor = material("catalog_floor", texture=texture("catalog_floor_c", grime(1024, "#7d776b", "#56503f", 0.4, 5, 3)),
                     texture_size=9.0, roughness=0.8)
    plane("Floor", (W + 6, D + 6), (W / 2 - CELL[0] / 2, -(D / 2 - CELL[1] / 2), 0), material=floor)

    stands = {
        "cone": [props.cone_stand(f"Cone_{c}{i}", PM[f"pe_{c}"], PM["hole"]) for i, c in
                 enumerate(("yellow", "yellow2", "yellow", "grey"))],
        "star": [props.star_stand(f"Star_{c}{i}", PM[f"pe_{c}"]) for i, c in enumerate(("yellow", "yellow2"))],
    }
    studs = {n: piping.stud_prefab(n, M) for n in (2, 6, 8, 10, 12, 16)}
    px, rects = text_atlas(spools.marking_lines(pack.SPOOLS), 40, "#ecebe6", italic=0.12, jitter=0.012)
    atlas = (texture("marker_atlas", px, fmt="png"), rects, px.shape[1] / px.shape[0])

    def crib(xy, yaw):
        props.cribbing(PM, xy, yaw, 0.9)

    for i, sd in enumerate(pack.SPOOLS):
        cx, cy = (i % COLS) * CELL[0], -(i // COLS) * CELL[1]
        place = dict(xy=(cx, cy), rot=(0, 0, 0))
        if sd["ctrl"] == 17:
            place["rot"] = (90, 0, 0)          # laid on its side, as for the test
        spools.build_spool(sd, M, place, studs, stands, atlas, rng, cribbing=crib)
        spools.spool_record(sd)
        # Floor placard: control number and ISO
        img = texture(f"placard_{sd['ctrl']}", text_image(f"{sd['ctrl']:>2}  {sd['iso']}", "#1d1d1d", 64,
                                                          background="#f1efe8"))
        w = 2.4
        decal(f"Placard_{sd['ctrl']}", img, (w, w * img.size[1] / img.size[0]),
              (cx, cy - CELL[1] / 2 + 0.45, 0.002), collection="Placards")
    spools.test_equipment_record()
    twin_record("catalog", "Pressure Test Pack 1: spools", "Arc Resources · 10-16 Sales Gas Rerouting",
                group="Pack", overview=True, color="#ffd27a",
                fields=[("Spools", f"{len(pack.SPOOLS)} (control numbers 1-20 and 23)"),
                        ("Orientation", "As drawn: the drawings' north is up the rows (+y)"),
                        ("How to use", "Click a spool for its BOM, welds and drawing; click it again to pick "
                                       "a piece. Filter by heat number or X-ray report."),
                        ("Shop world", "The same spools on the test floor: Purnell Test Shop")],
                notes=pack.NOTES)

    atmosphere(time="13:30", latitude=55.2, day=120, haze=0.25, exposure=-0.4)
    camera((W * 0.78, -D * 1.02, 9.5), (W / 2 - 3.2, -D / 2 + 1.2, 0.5), 30)
