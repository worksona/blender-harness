from harness import *

META = {
    "title": "Neon City",
    "description": "A night-time grid of towers with glowing window bands and lit streets.",
    "tags": ["urban", "sci-fi", "night"],
    "seed": 42,
    "viewer": {"bloom": 0.45},
}

BLOCKS = 7       # blocks per side
BLOCK = 24.0     # block size in meters
STREET = 8.0


def build(ctx):
    rng = ctx.rng
    span = BLOCKS * (BLOCK + STREET)

    asphalt = material("asphalt", "#1b1c22", roughness=0.6)
    plane("Ground", size=span * 2.2, material=asphalt, backdrop=True)

    sidewalk = material("sidewalk", "#3a3c46", roughness=0.8)
    concrete = [material(f"tower_{i}", c, roughness=0.4, metallic=0.3)
                for i, c in enumerate(["#2a2f3d", "#343a4a", "#22252e", "#3d3546"])]
    neon = [material(f"neon_{i}", c, emission=c, emission_strength=6)
            for i, c in enumerate(["#ff3fa4", "#2ff3ff", "#8a5cff", "#ffb13b"])]
    street_light = material("street_light", "#e8f0ff", emission="#cfe0ff", emission_strength=10)

    origin = -span / 2 + STREET / 2
    for bx in range(BLOCKS):
        for by in range(BLOCKS):
            cx = origin + bx * (BLOCK + STREET) + BLOCK / 2
            cy = origin + by * (BLOCK + STREET) + BLOCK / 2
            box(f"Block.{bx}{by}", (BLOCK, BLOCK, 0.3), (cx, cy, 0), material=sidewalk,
                collection="Blocks")
            # Taller towers toward the center.
            centrality = 1 - (abs(bx - BLOCKS // 2) + abs(by - BLOCKS // 2)) / BLOCKS
            n = rng.choice([1, 2, 4])
            sub = BLOCK / (2 if n > 1 else 1)
            cells = [(0, 0)] if n == 1 else [(-1, -1), (1, -1), (-1, 1), (1, 1)][:n]
            for k, (ox, oy) in enumerate(cells):
                w = sub * rng.uniform(0.6, 0.85)
                h = rng.uniform(10, 25) + centrality ** 2 * rng.uniform(40, 110)
                x, y = cx + ox * sub / 2, cy + oy * sub / 2
                box(f"Tower.{bx}{by}.{k}", (w, w, h), (x, y, 0.3),
                    material=rng.choice(concrete), collection="Towers")
                glow = rng.choice(neon)
                for b in range(int(h // 9)):
                    if rng.random() < 0.55:
                        box(f"Band.{bx}{by}.{k}.{b}", (w + 0.3, w + 0.3, 0.5),
                            (x, y, 0.3 + 4 + b * 9), material=glow, collection="Neon")
                if h > 60:
                    cylinder(f"Spire.{bx}{by}.{k}", radius=0.4, height=h * 0.15, segments=6,
                             location=(x, y, 0.3 + h), material=glow, collection="Neon")

    pole = prefab(join("StreetLamp", [
        cylinder("pole", radius=0.12, height=6, segments=6, material=sidewalk),
        box("head", (1.2, 0.4, 0.25), (0.5, 0, 6), material=street_light),
    ]))
    lamp_i = 0
    for i in range(BLOCKS + 1):
        line = origin - STREET / 2 + i * (BLOCK + STREET)
        for j in range(BLOCKS * 2):
            t = origin + j * (BLOCK + STREET) / 2 + 6
            instance(pole, f"Lamp.{lamp_i}", (line, t, 0), (0, 0, 0), collection="Lamps")
            lamp_i += 1

    sun(elevation=25, azimuth=300, strength=0.25, color="#8fa6ff")
    sky("#0b0f24", strength=0.6, ground="#141022")
    fog("#121633", near=120, far=520)
    camera((190, -210, 130), (0, 0, 20), lens=30)
