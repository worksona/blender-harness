from harness import *

META = {
    "title": "Golden Harbor",
    "description": "Low sun over a rolling sea: sailboats and buoys ride the swell past a lighthouse islet.",
    "tags": ["ocean", "sunset", "showcase"],
    "seed": 11,
    "viewer": {"exposure": 1.05},
}

ISLET = (40.0, 150.0)


def islet_height(x, y):
    dx, dy = x - ISLET[0], y - ISLET[1]
    base = island_falloff(dx, dy * 1.4, 46)
    return -3 + base * (16 + 7 * fbm(x, y, scale=14, seed=5)) + 1.5 * fbm(x, y, scale=4, seed=9)


def sailboat(name, hull_color, sail_color):
    hull = material(f"hull_{name}", hull_color, roughness=0.45)
    deck = material("deck_wood", "#a77b4f", roughness=0.7)
    sail = material(f"sail_{name}", sail_color, roughness=0.8)
    mast = material("mast", "#d8d2c4", roughness=0.5)
    verts = [(-4, -1.1, 1.0), (0, -1.35, 1.0), (4.2, 0, 1.15), (0, 1.35, 1.0), (-4, 1.1, 1.0),
             (-3.8, -0.55, 0.15), (0, -0.75, -0.35), (0, 0.75, -0.35), (-3.8, 0.55, 0.15)]
    sides = [(0, 5, 6, 1), (1, 6, 2), (4, 3, 7, 8), (3, 2, 7), (5, 8, 7, 6), (6, 7, 2), (0, 4, 8, 5)]
    return join(f"Sailboat_{name}", [
        mesh("hull", verts, sides, material=hull),
        mesh("deck", verts[:5], [(0, 1, 2, 3, 4)], material=deck),
        cylinder("mast", radius=0.09, height=10, segments=6, location=(0.6, 0, 1), material=mast),
        mesh("main", [(0.45, 0, 1.7), (0.45, 0, 10.4), (-3.6, 0, 1.7)], [(0, 1, 2)], material=sail),
        mesh("jib", [(0.75, 0, 9.8), (4.0, 0, 1.3), (0.75, 0, 1.5)], [(0, 1, 2)], material=sail),
    ])


def build(ctx):
    rng = ctx.rng

    ocean(level=0, waves="moderate", wind=20, color="#06324a", shallow="#2fa39b",
          foam=0.55, clarity=0.9)

    sand = material("sand", "#d9c08a", roughness=0.95)
    rock = material("rock", "#6f6a66", roughness=0.95)
    moss = material("moss", "#58703c", roughness=0.9)
    terrain("Islet", size=130, resolution=96, height=islet_height, center=ISLET,
            bands=[(1.0, sand), (4.5, rock), (11, moss), (99, rock)], collection="Islet")

    # Lighthouse on the islet's highest point.
    top = max(scatter(rng, 600, (ISLET[0] - 30, ISLET[0] + 30, ISLET[1] - 25, ISLET[1] + 25),
                      islet_height), key=lambda p: p[2])
    x, y, z = top
    white = material("paint_white", "#f2efe8", roughness=0.5)
    red = material("paint_red", "#b8322a", roughness=0.5)
    lamp = material("lamp", "#fff2b0", emission="#ffcf6a", emission_strength=14)
    cylinder("Lighthouse", radius=2.2, radius_top=1.5, height=13, segments=14,
             location=(x, y, z - 1), material=white, collection="Islet")
    for k in range(3):
        cylinder(f"Lighthouse.band{k}", radius=2.0 - 0.2 * k, radius_top=1.95 - 0.2 * k,
                 height=1.2, segments=14, location=(x, y, z + 1.5 + 3.6 * k), material=red,
                 collection="Islet")
    cylinder("Lighthouse.lamp", radius=1.1, height=1.6, segments=14, location=(x, y, z + 12),
             material=lamp, collection="Islet")
    cone("Lighthouse.roof", radius=1.7, height=1.8, segments=14, location=(x, y, z + 13.6),
         material=red, collection="Islet")

    # Sailboats, floating on the viewer's waves.
    palette = [("#f4f1ea", "#f7f3e8"), ("#1f3b5c", "#efe6d2"), ("#9c2f2a", "#f4efe2"),
               ("#2f5a46", "#f2ead8")]
    designs = [prefab(sailboat(str(i), h, s)) for i, (h, s) in enumerate(palette)]
    spots = [(-22, 40), (18, 70), (-48, 95), (70, 60), (-5, 120), (95, 110)]
    for i, (bx, by) in enumerate(spots):
        boat = instance(designs[i % len(designs)], f"Sailboat.{i}", (bx, by, 0),
                        (0, 0, rng.uniform(0, 360)), rng.uniform(0.85, 1.15), collection="Boats")
        bob(boat, amount=1.0, draft=0.35)

    # Channel buoys.
    buoy_red = material("buoy_red", "#c8342b", roughness=0.4)
    buoy_green = material("buoy_green", "#2c8a4b", roughness=0.4)
    for i in range(8):
        side = i % 2
        bx = -40 + 14 * i
        by = 18 + (10 if side else -6) + 3 * i
        b = join(f"Buoy.{i}", [
            cylinder("float", radius=0.7, radius_top=0.45, height=1.4, segments=10,
                     material=buoy_green if side else buoy_red),
            cone("top", radius=0.45, height=1.0, segments=10, location=(0, 0, 1.4),
                 material=buoy_green if side else buoy_red),
        ], collection="Buoys")
        b.location = (bx, by, 0)
        bob(b, amount=1.0, draft=0.5)

    sun(elevation=7, azimuth=12, strength=3.2, color="#ffb27a", angle=2.0)
    sky("#4f78ad", strength=0.75, ground="#3a3f4a")
    fog("#f0b48c", near=200, far=1400)
    camera((-8, -55, 7), (10, 80, 4), lens=28)
