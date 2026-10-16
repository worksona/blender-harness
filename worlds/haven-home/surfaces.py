"""Baked surfaces for the Haven home: every pattern is numpy pixels, so the .glb carries it.

Colour maps are near-neutral where a material comes in several tints (fabric, rugs, wood), and
material() multiplies them by its colour, so one image serves many materials.
"""

import numpy as np

from harness import (blur, colorize, contrast, fbm_noise, height_normal, material, texture,
                     value_noise)


def _stretch(size, cells, seed, octaves=4):
    """Tileable noise stretched 16x along x (wood grain, slubs): `cells` along x, 16x across."""
    h, w = size
    base = fbm_noise((h, max(8, w // 16)), cells, octaves, seed)
    xs = np.linspace(0, base.shape[1], w, endpoint=False)
    i0 = np.floor(xs).astype(int) % base.shape[1]
    f = (xs - np.floor(xs)).astype(np.float32)
    return base[:, i0] * (1 - f) + base[:, (i0 + 1) % base.shape[1]] * f


def grain(size, seed, rings=16.0, warp_amount=0.9, phase=None):
    """Wood figure 0..1 along x: thin latewood lines that drift and pinch, long streaks and pores.
    phase (H, W) shifts the rings per board, so neighbouring boards don't line up."""
    h, w = size
    y = np.arange(h, dtype=np.float32)[:, None] / h
    slow = _stretch((h, w), 1, seed + 5, octaves=3)
    wobble = fbm_noise((h, w), 3, 4, seed)
    p = 0.0 if phase is None else phase
    ring = (0.5 + 0.5 * np.sin(2 * np.pi * (rings * y + warp_amount * (slow - 0.5) * 2 + 0.6 * wobble + p))) ** 2.2
    vary = contrast(fbm_noise((h, w), 2, 3, seed + 2), 0.2, 0.8)
    streaks = _stretch((h, w), 1, seed + 8, octaves=6)
    pores = _stretch((h, w), 4, seed + 3, octaves=3)
    return np.clip(0.38 * ring * (0.5 + vary) + 0.4 * streaks + 0.22 * pores, 0, 1)


def plank_floor(size=1024, boards=12, seed=11, light="#d3ae82", dark="#9a7151"):
    """Tileable plank floor: `boards` rows per tile, staggered butt joints, per-board tone and
    grain phase, bevelled seams."""
    rng = np.random.default_rng(seed)
    h = w = size
    bh = h // boards
    seams = np.zeros((h, w), np.float32)
    tone = np.zeros((h, w), np.float32)
    phase = np.zeros((h, w), np.float32)
    for row in range(boards):
        y0, y1 = row * bh, (row + 1) * bh
        x = int(rng.integers(0, w))
        cuts, total = [], 0
        while total < w * 0.9:
            cuts.append((x + total) % w)
            total += int(rng.integers(int(w * 0.3), int(w * 0.55)))
        cuts = sorted(cuts)
        for i, c0 in enumerate(cuts):
            c1 = cuts[(i + 1) % len(cuts)]
            cols = np.arange(c0, c1 if c1 > c0 else c1 + w) % w
            tone[y0:y1, cols] = rng.normal(0, 1)
            phase[y0:y1, cols] = rng.uniform(0, 1)
            seams[y0:y1, c0] = 1.0
        seams[y0, :] = 1.0
    seams = np.maximum(seams, 0.5 * (np.roll(seams, 1, axis=0) + np.roll(seams, 1, axis=1)))
    figure = grain((h, w), seed, rings=boards * 3.0, warp_amount=0.6, phase=phase)
    t = np.clip(figure * 0.7 + tone * 0.11 + 0.15, 0, 1)
    col = colorize(t, light, dark)
    col *= (1 - 0.6 * seams)[..., None]
    height = 1 - seams * 0.9 - figure * 0.05
    rough = np.clip(0.45 + 0.15 * figure + 0.3 * seams + 0.05 * tone, 0.25, 0.95)
    return np.clip(col, 0, 1), height_normal(blur(height, 1), 3.0), rough


def wood(size=512, seed=21):
    """Neutral-warm furniture wood (tint per species with the material colour)."""
    figure = grain((size, size), seed, rings=16.0, warp_amount=0.9)
    col = colorize(figure, "#f2dcc2", "#ae876a")
    rough = np.clip(0.38 + 0.25 * figure, 0, 1)
    return col, height_normal(figure, 0.6), rough


def marble(size=1024, seed=31, base="#efede8", vein="#8d8a86", gold=None):
    """Tileable veined marble: diagonal veins warped by fractal noise."""
    h = w = size
    v, u = np.mgrid[0:h, 0:w].astype(np.float32) / size
    warp = fbm_noise(size, 3, 6, seed)
    a = np.abs(np.sin(np.pi * (2 * u + 1 * v + 2.6 * warp)))
    b = np.abs(np.sin(np.pi * (1 * u - 2 * v + 3.4 * fbm_noise(size, 4, 6, seed + 1))))
    veins = np.maximum(1 - contrast(a, 0.0, 0.06), 0.55 * (1 - contrast(b, 0.0, 0.035)))
    cloud = fbm_noise(size, 5, 6, seed + 2)
    col = colorize(np.clip(veins * 0.85 + (cloud - 0.5) * 0.18, 0, 1), base, vein)
    if gold:
        col = col * (1 - 0.25 * veins[..., None]) + np.array(
            [int(gold[i:i + 2], 16) / 255 for i in (1, 3, 5)]) * 0.25 * veins[..., None]
    rough = np.clip(0.12 + 0.12 * cloud + 0.1 * veins, 0, 1)
    return np.clip(col, 0, 1), rough


def tiles(size=512, n=4, seed=41, base="#dfe5e3", grout="#a9aeac", gap=0.018):
    """n x n square tiles per image with grout lines and gentle per-tile tone."""
    rng = np.random.default_rng(seed)
    v, u = np.mgrid[0:size, 0:size].astype(np.float32) / size * n
    fu, fv = u - np.floor(u), v - np.floor(v)
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    g = 1 - contrast(edge, gap * 0.6, gap * 1.4)
    shade = rng.normal(0, 1, (n, n))[np.floor(v).astype(int) % n, np.floor(u).astype(int) % n]
    col = colorize(np.zeros_like(u), base, base) * (1 + 0.025 * shade)[..., None]
    col = col * (1 - g[..., None]) + colorize(np.zeros_like(u), grout, grout) * g[..., None]
    col *= (0.97 + 0.06 * fbm_noise(size, 8, 4, seed))[..., None]
    rough = np.clip(0.18 + 0.6 * g, 0, 1)
    return np.clip(col, 0, 1), height_normal(blur(1 - g, 1), 2.5), rough


def plaster(size=512, seed=51):
    n = fbm_noise(size, 6, 6, seed)
    fine = fbm_noise(size, 48, 3, seed + 1)
    col = colorize(np.clip(n * 0.6 + fine * 0.4, 0, 1), "#ffffff", "#e9e5df")
    return col, height_normal(n * 0.5 + fine * 0.5, 0.8)


def weave(size=512, threads=56, seed=61, slub=0.35):
    """Near-white upholstery weave (basket weave with slubs); tint with the material colour."""
    v, u = np.mgrid[0:size, 0:size].astype(np.float32) / size * threads
    warp = 0.5 + 0.5 * np.sin(2 * np.pi * u) * np.sign(np.sin(np.pi * v))
    weft = 0.5 + 0.5 * np.sin(2 * np.pi * v) * np.sign(np.sin(np.pi * u))
    cloth = np.maximum(warp, weft)
    slubs = _stretch((size, size), 2, seed) * slub
    h = np.clip(cloth * 0.8 + slubs, 0, 1)
    col = colorize(h, "#cfcac2", "#ffffff")
    return col, height_normal(h, 1.6)


def rug_pile(size=512, seed=71):
    """Wool rug: mottled pile with a soft woven texture."""
    n = fbm_noise(size, 10, 5, seed)
    v, u = np.mgrid[0:size, 0:size].astype(np.float32) / size * 90
    knots = 0.5 + 0.25 * np.sin(2 * np.pi * u) + 0.25 * np.sin(2 * np.pi * v)
    h = np.clip(0.55 * knots + 0.45 * n, 0, 1)
    col = colorize(h, "#c6c1b8", "#ffffff")
    return col, height_normal(h, 2.0)


def stone(size=512, seed=81):
    n = fbm_noise(size, 4, 6, seed)
    speck = contrast(fbm_noise(size, 64, 2, seed + 1), 0.55, 0.8)
    col = colorize(np.clip(n * 0.7 + speck * 0.3, 0, 1), "#d9d4ca", "#a9a398")
    return col, height_normal(n, 1.0)


def painting(size=512, seed=91, palette=("#e8e0d2", "#b4673f", "#d7a35c", "#40546a", "#7d8d74")):
    """Soft abstract canvas: overlapping colour fields with brushy edges."""
    rng = np.random.default_rng(seed)
    v, u = np.mgrid[0:size, 0:size].astype(np.float32) / size
    pal = [np.array([int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32) for c in palette]
    col = np.ones((size, size, 3), np.float32) * pal[0]
    brush = fbm_noise(size, 6, 5, seed)
    for k in range(5):
        cx, cy = rng.uniform(0.2, 0.8, 2)
        rx, ry = rng.uniform(0.12, 0.32, 2)
        d = ((u - cx) / rx) ** 2 + ((v - cy) / ry) ** 2 + (brush - 0.5) * 0.9
        m = 1 - contrast(d, 0.8, 1.05)
        col = col * (1 - m[..., None] * 0.92) + pal[1 + k % 4] * m[..., None] * 0.92
    col *= (0.94 + 0.12 * fbm_noise(size, 40, 3, seed + 4))[..., None]
    return np.clip(col, 0, 1)


def build_materials():
    """All Haven materials, by short name."""
    M = {}
    # Floors.
    col, nrm, rough = plank_floor()
    M["oak_floor"] = material("oak_floor", "#ffffff", texture=texture("oak_floor", col),
                              texture_size=2.4, normal=texture("oak_floor_n", nrm, data=True),
                              roughness_map=texture("oak_floor_r", rough, data=True))
    col, rough = marble(seed=31)
    marble_tex, marble_r = texture("marble", col), texture("marble_r", rough, data=True)
    M["marble"] = material("marble", "#ffffff", texture=marble_tex, texture_size=1.4,
                           roughness_map=marble_r)
    col, rough = marble(seed=37, vein="#b7b3ad")
    M["marble_floor"] = material("marble_floor", "#f3f1ed", texture=texture("marble_floor", col),
                                 texture_size=3.2, roughness_map=texture("marble_floor_r", rough, data=True))
    col, nrm, rough = tiles()
    M["tile"] = material("tile", "#ffffff", texture=texture("tile", col), texture_size=1.2,
                         normal=texture("tile_n", nrm, data=True),
                         roughness_map=texture("tile_r", rough, data=True))
    col, nrm, rough = tiles(n=8, seed=42, base="#3d4a4f", grout="#59666a", gap=0.03)
    M["tile_dark"] = material("tile_dark", "#ffffff", texture=texture("tile_dark", col),
                              texture_size=0.8, normal=texture("tile_dark_n", nrm, data=True),
                              roughness_map=texture("tile_dark_r", rough, data=True))

    # Walls and the plinth.
    col, nrm = plaster()
    plaster_tex, plaster_n = texture("plaster", col), texture("plaster_n", nrm, data=True)
    M["plaster"] = material("plaster", "#ece7df", roughness=0.92, texture=plaster_tex,
                            texture_size=2.0, normal=plaster_n, normal_strength=0.6)
    M["plaster_warm"] = material("plaster_warm", "#d9cbb8", roughness=0.92, texture=plaster_tex,
                                 texture_size=2.0, normal=plaster_n, normal_strength=0.6)
    M["cut"] = material("wall_cut", "#2a2d31", roughness=0.85)
    col, nrm = stone()
    stone_tex, stone_n = texture("stone", col), texture("stone_n", nrm, data=True)
    M["limestone"] = material("limestone", "#ffffff", roughness=0.8, texture=stone_tex,
                              texture_size=3.0, normal=stone_n)
    M["plinth"] = material("plinth", "#8a8174", roughness=0.85, texture=stone_tex,
                           texture_size=3.0, normal=stone_n)
    M["studio"] = material("studio_floor", "#0a0c0f", roughness=0.95)

    # Woods (one figure image, tinted per species).
    col, nrm, rough = wood()
    wtex, wn, wr = texture("wood", col), texture("wood_n", nrm, data=True), texture("wood_r", rough, data=True)
    for name, tint in (("oak", "#d9b48c"), ("walnut", "#7a5440"), ("ash", "#efe0cb"),
                       ("smoked", "#5b4a40")):
        M[name] = material(name, tint, texture=wtex, texture_size=0.9, normal=wn, roughness_map=wr)

    # Upholstery and soft goods (one weave, tinted).
    col, nrm = weave()
    ftex, fn = texture("weave", col), texture("weave_n", nrm, data=True)
    for name, tint, r in (("sofa", "#b9b3a6", 0.95), ("linen", "#ece6da", 0.95),
                          ("cream", "#e3dccd", 0.95), ("rust", "#b4673f", 0.9),
                          ("moss", "#7c8a63", 0.9), ("ink", "#3f4f63", 0.9),
                          ("clay", "#b88f74", 0.92), ("sand", "#cdb79a", 0.95),
                          ("charcoal", "#55585b", 0.95), ("blush", "#d6b2a2", 0.95),
                          ("towel", "#f1ece2", 1.0)):
        M[name] = material(name, tint, roughness=r, texture=ftex, texture_size=0.22, normal=fn)
    col, nrm = rug_pile()
    rtex, rn = texture("rug", col), texture("rug_n", nrm, data=True)
    for name, tint in (("rug_living", "#a39f92"), ("rug_dining", "#9c8a78"),
                       ("rug_bed", "#cdbfac"), ("rug_hall", "#8f6f5c"), ("rug_office", "#8d9a98")):
        M[name] = material(name, tint, roughness=1.0, texture=rtex, texture_size=0.6, normal=rn)

    # Metals, glass, ceramics, plastics.
    M["brass"] = material("brass", "#c9a467", roughness=0.28, metallic=1.0)
    M["bronze"] = material("bronze", "#9a7348", roughness=0.35, metallic=1.0)
    M["chrome"] = material("chrome", "#e4e6e8", roughness=0.08, metallic=1.0)
    M["steel"] = material("steel", "#b9bcbe", roughness=0.32, metallic=1.0)
    M["black_metal"] = material("black_metal", "#26282a", roughness=0.45, metallic=0.8)
    M["mirror"] = material("mirror", "#f2f4f5", roughness=0.02, metallic=1.0)
    M["glass"] = material("glass", "#b4ccd4", roughness=0.03, alpha=0.14)
    M["glass_smoke"] = material("glass_smoke", "#7f8c8f", roughness=0.05, alpha=0.35)
    M["water"] = material("water", "#9cc8d0", roughness=0.03, alpha=0.55)
    M["porcelain"] = material("porcelain", "#f4f2ee", roughness=0.12)
    M["ceramic"] = material("ceramic", "#e8e2d8", roughness=0.35)
    M["terracotta"] = material("terracotta", "#b07a5a", roughness=0.85)
    M["stoneware"] = material("stoneware", "#5d6460", roughness=0.7)
    M["lacquer"] = material("lacquer", "#ebe6dd", roughness=0.35)
    M["lacquer_sage"] = material("lacquer_sage", "#9aa592", roughness=0.4)
    M["lacquer_ink"] = material("lacquer_ink", "#2f3a46", roughness=0.4)
    M["matte_black"] = material("matte_black", "#1c1e20", roughness=0.6)
    M["black_glass"] = material("black_glass", "#0d0f11", roughness=0.06)
    M["rubber"] = material("rubber", "#2a2a2a", roughness=0.9)
    M["paper"] = material("paper", "#f3efe6", roughness=0.9)
    M["leaf"] = material("leaf", "#4e6e45", roughness=0.55)
    M["leaf_light"] = material("leaf_light", "#7a9a5e", roughness=0.55)
    M["leaf_dark"] = material("leaf_dark", "#33503a", roughness=0.5)
    M["soil"] = material("soil", "#3b2e25", roughness=1.0)
    M["fruit_orange"] = material("fruit_orange", "#e08a2e", roughness=0.5)
    M["fruit_green"] = material("fruit_green", "#9bb04a", roughness=0.45)
    # Emitters (the Haven viewer drives these with live Home Assistant state).
    M["bulb"] = material("bulb", "#fff1d6", emission="#ffd9a0", emission_strength=12.0)
    M["shade_glow"] = material("shade_glow", "#f3e6cf", roughness=0.9, emission="#ffcf8f",
                               emission_strength=1.2)
    M["led"] = material("led_strip", "#ffe2b0", emission="#ffcf8a", emission_strength=6.0)
    M["screen"] = material("tv_screen", "#0b0f14", roughness=0.05, emission="#2a4a66",
                           emission_strength=0.0)
    M["monitor"] = material("monitor_screen", "#11161c", roughness=0.08, emission="#3d5a75",
                            emission_strength=0.15)
    M["book"] = [material(f"book_{i}", c, roughness=0.8) for i, c in enumerate(
        ("#8c3b2e", "#2f4a5f", "#d8cfbd", "#55704f", "#c79a52", "#3b3b3b", "#a65f45", "#e8e2d5"))]
    return M


def art_textures():
    return [texture("art_a", painting(seed=91)),
            texture("art_b", painting(seed=97, palette=("#efe9de", "#3f5568", "#9fb0b8", "#c48a5a", "#2d3540"))),
            texture("art_c", painting(seed=103, palette=("#ede4d4", "#7d8d74", "#c9b48d", "#a35d3d", "#566a5f")))]
