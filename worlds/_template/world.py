from harness import *

META = {
    "title": "World Title",
    "description": "One sentence for the gallery card.",
    "tags": [],
    "seed": 1,
    # Optional viewer overrides: {"bloom": 0.8, "exposure": 1.1}
}


def height(x, y):
    return 2 * fbm(x, y, scale=30, seed=1)


def build(ctx):
    rng = ctx.rng  # use this for all randomness so rebuilds are identical

    grass = material("grass", "#6e9a45", roughness=0.85)
    rock = material("rock", "#8a8580", roughness=0.95)
    terrain("Ground", size=200, resolution=96, height=height,
            bands=[(1.5, grass), (99, rock)])

    stone = prefab(sphere("Stone", radius=1, subdivisions=1, smooth=False, material=rock))
    for i, (x, y, z) in enumerate(scatter(rng, 40, 80, height, min_dist=4)):
        instance(stone, f"Stone.{i}", (x, y, z), (0, 0, rng.uniform(0, 360)),
                 rng.uniform(0.5, 1.5), collection="Stones")

    sun(elevation=40, azimuth=135)
    sky("#9cc7f0")
    camera((120, -120, 70), (0, 0, 0))
