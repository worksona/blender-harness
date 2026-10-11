from harness import *

META = {
    "title": "Low-Poly Island",
    "description": "A faceted island with pine forests, boulders and a lighthouse on the point.",
    "tags": ["nature", "stylized", "day"],
    "seed": 7,
}

RADIUS = 90
SEA = 0.0


def height(x, y):
    base = island_falloff(x, y, RADIUS)
    return -4 + base * (22 + 14 * fbm(x, y, scale=35, seed=3)) + 3 * fbm(x, y, scale=9, seed=8)


def build(ctx):
    rng = ctx.rng

    sand = material("sand", "#e3cf98", roughness=0.9)
    grass = material("grass", "#6e9a45", roughness=0.85)
    grass_dark = material("grass_dark", "#4f7a36", roughness=0.85)
    rock = material("rock", "#8a8580", roughness=0.95)
    snow = material("snow", "#f4f6f8", roughness=0.7)
    terrain("Island", size=2 * RADIUS + 40, resolution=110, height=height,
            bands=[(1.2, sand), (8, grass), (15, grass_dark), (22, rock), (99, snow)])

    ocean(level=SEA, waves="calm", wind=200, color="#0d4f78", shallow="#3fc2c0",
          foam=0.7, clarity=1.4)

    # Pine prefab: trunk + two stacked cones, joined into one mesh, instanced many times.
    bark = material("bark", "#6b4a2f", roughness=0.9)
    needles = material("needles", "#2f5d34", roughness=0.8)
    pine = prefab(join("Pine", [
        cylinder("trunk", radius=0.25, height=1.6, segments=6, material=bark),
        cone("lower", radius=1.6, height=3.0, segments=7, location=(0, 0, 1.2), material=needles),
        cone("upper", radius=1.1, height=2.4, segments=7, location=(0, 0, 3.0), material=needles),
    ]))

    def forest_ok(x, y, z):
        return 1.8 < z < 16 and slope(height, x, y) < 32

    for i, (x, y, z) in enumerate(scatter(rng, 260, RADIUS, height, forest_ok, min_dist=2.6)):
        s = rng.uniform(0.7, 1.4)
        instance(pine, f"Pine.{i:03d}", (x, y, z - 0.2), (0, 0, rng.uniform(0, 360)), s,
                 collection="Forest")

    boulder = prefab(sphere("Boulder", radius=1.0, subdivisions=1, smooth=False, material=rock))
    for i, (x, y, z) in enumerate(scatter(rng, 70, RADIUS, height,
                                          lambda x, y, z: z > 0.3, min_dist=3)):
        s = rng.uniform(0.4, 1.8)
        instance(boulder, f"Boulder.{i:03d}", (x, y, z), (rng.uniform(0, 40), 0, rng.uniform(0, 360)),
                 (s * rng.uniform(0.8, 1.4), s, s * rng.uniform(0.5, 0.9)), collection="Rocks")

    # Lighthouse on the most south-easterly point of land.
    spot = max(scatter(rng, 400, RADIUS, height, lambda x, y, z: z > 2.5), key=lambda p: p[0] - p[1])
    x, y, z = spot
    white = material("paint_white", "#f2efe8", roughness=0.5)
    red = material("paint_red", "#c0392b", roughness=0.5)
    lamp = material("lamp", "#fff2b0", emission="#ffd76a", emission_strength=8)
    cylinder("Lighthouse.base", radius=2.0, radius_top=1.4, height=9, segments=12,
             location=(x, y, z - 0.5), material=white, collection="Lighthouse")
    cylinder("Lighthouse.band", radius=1.45, radius_top=1.35, height=1.5, segments=12,
             location=(x, y, z + 5), material=red, collection="Lighthouse")
    cylinder("Lighthouse.lamp", radius=1.0, height=1.4, segments=12,
             location=(x, y, z + 8.5), material=lamp, collection="Lighthouse")
    cone("Lighthouse.roof", radius=1.5, height=1.6, segments=12,
         location=(x, y, z + 9.9), material=red, collection="Lighthouse")

    sun(elevation=38, azimuth=220, strength=4.5, color="#fff1d6")
    sky("#9ccbf0", strength=0.9, ground="#5d7d4a")
    fog("#bcdcf2", near=180, far=700)
    camera((150, -150, 85), (0, 0, 4), lens=32)
