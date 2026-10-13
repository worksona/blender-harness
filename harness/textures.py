"""Image textures that survive glTF export, so the web viewer shows the same surfaces as the render.

    grime = texture("floor", concrete(1024, seed=3))                 # numpy pixels -> image
    floor = material("floor", texture=grime, texture_size=4.0,       # one tile covers 4 x 4 m
                     normal=texture("floor_n", height_normal(h), data=True))
    patch = photo_patch("worlds/x/reference/photo.jpg", (0.1, 0.7, 0.3, 0.9), 512)  # tileable crop

Pixels are numpy arrays (H, W, 3 or 4), sRGB 0..1, row 0 at the TOP (like a photo).
Every mesh that uses a textured material gets box-projected UVs automatically before export
(ensure_uvs), scaled by the material's texture_size in meters. Meshes that already have a UV map
(decals, text) keep theirs.

Everything here is deterministic: generators take a seed, and photo crops are plain pixel copies.
"""

import math
import os

import bpy  # noqa: I001  (before bmesh/mathutils, required by the bpy module)
import numpy as np

# Where generated images are written before export (the build tool points it at build/<slug>/tex).
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "_textures")
_IMAGES = {}
_PHOTOS = {}


def reset():
    _IMAGES.clear()


# ---------------------------------------------------------------- images

def texture(name, pixels, data=False, fmt="jpg", quality=90):
    """Turn pixels (H, W, 3|4) into a Blender image saved under CACHE, ready for material().
    data=True for normal and roughness maps (no colour management). fmt 'png' keeps alpha."""
    if name in _IMAGES:
        return _IMAGES[name]
    px = np.asarray(pixels, dtype=np.float32)
    if px.ndim == 2:
        px = np.repeat(px[..., None], 3, axis=2)
    h, w, c = px.shape
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :c] = np.clip(px, 0, 1)
    img = bpy.data.images.new(name, w, h, alpha=(c == 4))
    if data:
        img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(rgba[::-1].ravel())     # Blender stores the bottom row first
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{name}.{fmt}")
    img.filepath_raw = path
    img.file_format = "PNG" if fmt == "png" else "JPEG"
    img.save(quality=quality) if fmt != "png" else img.save()
    _IMAGES[name] = img
    return img


def load_pixels(path):
    """Read an image file into (H, W, 4) float sRGB pixels, top row first."""
    path = os.path.abspath(path)
    if path not in _PHOTOS:
        img = bpy.data.images.load(path)
        img.colorspace_settings.name = "Non-Color"     # raw sRGB values, no conversion
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        _PHOTOS[path] = px.reshape(h, w, 4)[::-1]
    return _PHOTOS[path]


def resize(px, size):
    """Area-average / bilinear resize to (h, w) (size may be an int for square)."""
    h, w = (size, size) if isinstance(size, int) else size
    H, W = px.shape[:2]
    if (H, W) == (h, w):
        return px
    # Box-filter down first so big reductions don't alias, then bilinear to the exact size.
    k = max(1, min(H // h, W // w))
    if k > 1:
        H2, W2 = H // k * k, W // k * k
        px = px[:H2, :W2].reshape(H2 // k, k, W2 // k, k, -1).mean(axis=(1, 3))
        H, W = px.shape[:2]
    ys = np.clip((np.arange(h) + 0.5) * H / h - 0.5, 0, H - 1)
    xs = np.clip((np.arange(w) + 0.5) * W / w - 0.5, 0, W - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, H - 1), np.minimum(x0 + 1, W - 1)
    fy, fx = (ys - y0)[:, None, None], (xs - x0)[None, :, None]
    top = px[y0][:, x0] * (1 - fx) + px[y0][:, x1] * fx
    bot = px[y1][:, x0] * (1 - fx) + px[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


def blur(px, radius):
    """Wrapping box blur (twice, close to Gaussian). Works on (H, W) or (H, W, C)."""
    r = max(1, int(radius))
    out = px.astype(np.float32)
    for _ in range(2):
        for axis in (0, 1):
            acc = np.zeros_like(out)
            for d in range(-r, r + 1):
                acc += np.roll(out, d, axis=axis)
            out = acc / (2 * r + 1)
    return out


def make_tileable(px, border=0.25):
    """Cross-fade the image with a half-offset copy of itself so its edges wrap seamlessly."""
    h, w = px.shape[:2]
    rolled = np.roll(px, (h // 2, w // 2), axis=(0, 1))
    wy = np.minimum(np.arange(h), np.arange(h)[::-1]) / (h * border)
    wx = np.minimum(np.arange(w), np.arange(w)[::-1]) / (w * border)
    m = np.clip(np.minimum(wy[:, None], wx[None, :]), 0, 1)
    m = m * m * (3 - 2 * m)
    if px.ndim == 3:
        m = m[..., None]
    return px * m + rolled * (1 - m)


def flatten_light(px, radius=None, strength=1.0):
    """Remove large-scale shading from a photo crop (lighting gradients, vignetting) while
    keeping its texture and average colour, so it tiles without visible bright/dark bands."""
    h, w = px.shape[:2]
    rgb = px[..., :3]
    low = blur(rgb, radius or max(h, w) // 6)
    mean = rgb.reshape(-1, 3).mean(axis=0)
    out = rgb / np.maximum(low, 1e-3) * mean
    out = rgb + (out - rgb) * strength
    return np.concatenate([out, px[..., 3:]], axis=2) if px.shape[2] == 4 else out


def photo_patch(path, box, size=512, tileable=True, flat=True):
    """Crop a reference photo into a texture. box = (x0, y0, x1, y1) as fractions of the photo,
    measured from its top-left corner. Returns (size, size, 3) pixels (or (h, w) if size is a tuple)."""
    px = load_pixels(path)
    H, W = px.shape[:2]
    x0, y0, x1, y1 = box
    crop = px[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W), :3]
    crop = resize(crop, size)
    if flat:
        crop = flatten_light(crop)
    if tileable:
        crop = make_tileable(crop)
    return np.clip(crop, 0, 1)


# ---------------------------------------------------------------- procedural generators

def value_noise(size, cells, seed=0):
    """Tileable smooth value noise in 0..1: `cells` random values per side, smoothly interpolated.
    size may be (h, w) for a rectangle; cells then counts along the shorter side."""
    h, w = (size, size) if isinstance(size, int) else size
    ch = max(1, round(cells * h / min(h, w)))
    cw = max(1, round(cells * w / min(h, w)))
    rng = np.random.default_rng(seed)
    grid = rng.random((ch, cw)).astype(np.float32)

    def axis(n, c):
        t = (np.arange(n) + 0.5) * c / n
        i0 = np.floor(t).astype(int) % c
        f = t - np.floor(t)
        return i0, (i0 + 1) % c, (f * f * (3 - 2 * f)).astype(np.float32)
    y0, y1, fy = axis(h, ch)
    x0, x1, fx = axis(w, cw)
    rows0, rows1 = grid[y0], grid[y1]
    a = rows0[:, x0] * (1 - fx) + rows0[:, x1] * fx
    b = rows1[:, x0] * (1 - fx) + rows1[:, x1] * fx
    return a * (1 - fy[:, None]) + b * fy[:, None]


def fbm_noise(size, cells=4, octaves=5, seed=0, gain=0.5):
    """Tileable fractal noise in 0..1 (cells doubles each octave). size: int or (h, w)."""
    h, w = (size, size) if isinstance(size, int) else size
    total, amp, norm = np.zeros((h, w), np.float32), 1.0, 0.0
    for o in range(octaves):
        c = cells * 2 ** o
        if c > min(h, w):
            break
        total += amp * value_noise((h, w), c, seed * 101 + o)
        norm += amp
        amp *= gain
    return total / norm


def contrast(x, lo, hi):
    """Remap x so lo -> 0 and hi -> 1, clipped, with a smooth step."""
    t = np.clip((x - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def colorize(t, a, b):
    """Blend between two '#rrggbb' colours by t (H, W) -> (H, W, 3)."""
    ca, cb = _rgb(a), _rgb(b)
    return ca + (cb - ca) * t[..., None]


def _rgb(c):
    if isinstance(c, str):
        s = c.lstrip("#")
        return np.array([int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
    return np.array(c[:3], np.float32)


def height_normal(height, strength=2.0):
    """Tangent-space normal map pixels from a tileable height field (0..1)."""
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * strength
    n = np.stack([-dx, dy, np.ones_like(height)], axis=-1)   # +Y up in the image (OpenGL style)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def grime(size=512, base="#808080", dirt="#3a352e", amount=0.5, seed=0, cells=3):
    """Mottled wear: base colour with soft patches of dirt and fine speckle."""
    big = fbm_noise(size, cells, 6, seed)
    fine = fbm_noise(size, cells * 16, 3, seed + 7)
    t = contrast(big, 0.62 - amount * 0.3, 0.9 - amount * 0.2) * 0.85 + (fine - 0.5) * 0.25
    return np.clip(colorize(np.clip(t, 0, 1), base, dirt), 0, 1)


def rasterize(tris, size, bounds, supersample=3):
    """Coverage mask (h, w) of 2D triangles [(3, 2) arrays] inside bounds (x0, y0, x1, y1).
    Row 0 is the top (max y)."""
    w, h = size
    W, H = w * supersample, h * supersample
    mask = np.zeros((H, W), np.float32)
    x0, y0, x1, y1 = bounds
    sx, sy = W / (x1 - x0), H / (y1 - y0)
    for t in tris:
        p = np.column_stack([(t[:, 0] - x0) * sx, (y1 - t[:, 1]) * sy])
        lo = np.floor(p.min(axis=0)).astype(int)
        hi = np.ceil(p.max(axis=0)).astype(int)
        lo = np.maximum(lo, 0)
        hi = np.minimum(hi, (W, H))
        if hi[0] <= lo[0] or hi[1] <= lo[1]:
            continue
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0]) + 0.5, np.arange(lo[1], hi[1]) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = p
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        mask[lo[1]:hi[1], lo[0]:hi[0]][inside] = 1.0
    return mask.reshape(h, supersample, w, supersample).mean(axis=(1, 3))


def text_mask(text, height=64, pad=0.15, font=None, bold=False, italic=0.0, jitter=0.0, seed=0):
    """Antialiased coverage mask (h, w) of `text` in Blender's built-in font (or a .ttf path).
    height: pixels per line. italic: shear (0.2 = slanted like hand lettering). jitter: per-glyph
    wobble in em, for paint-marker writing. Multi-line text uses '\\n'."""
    curve = bpy.data.curves.new("_text", "FONT")
    curve.body = text
    if font:
        curve.font = bpy.data.fonts.load(os.path.abspath(font), check_existing=True)
    curve.shear = italic
    curve.offset_x = 0
    if bold:
        curve.offset = 0.02
    obj = bpy.data.objects.new("_text", curve)
    bpy.context.scene.collection.objects.link(obj)
    dg = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    co = np.array([v.co[:2] for v in me.vertices], np.float32)
    tris = [co[list(t.vertices)] for t in me.loop_triangles]
    obj.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(obj)
    bpy.data.curves.remove(curve)
    if not tris:
        return np.zeros((height, height), np.float32)
    if jitter:
        rng = np.random.default_rng(seed)
        # Wobble each glyph-sized cluster: offset by a smooth function of x.
        phase = rng.random(4) * 6.28
        tris = [t + np.array([0, jitter * (math.sin(t[:, 0].mean() * 3.1 + phase[0]) +
                                           0.5 * math.sin(t[:, 0].mean() * 7.3 + phase[1]))])
                for t in tris]
    allp = np.concatenate(tris)
    lines = text.count("\n") + 1
    x0, y0 = allp.min(axis=0) - pad
    x1, y1 = allp.max(axis=0) + pad
    px_per_unit = height * lines / (y1 - y0)
    w = max(1, int(round((x1 - x0) * px_per_unit)))
    return rasterize(tris, (w, height * lines), (x0, y0, x1, y1))


def text_image(text, color="#ffffff", height=64, background=None, **kw):
    """RGBA pixels of text in `color` on transparent (or `background`) for decals and signs."""
    m = text_mask(text, height, **kw)
    rgb = np.broadcast_to(_rgb(color), m.shape + (3,))
    if background is None:
        return np.concatenate([rgb, m[..., None]], axis=2)
    bg = _rgb(background)
    return bg + (rgb - bg) * m[..., None]


# ---------------------------------------------------------------- UVs

def box_uvs(me, sizes):
    """Box-project UVs onto mesh `me` in its local space. sizes[i] = meters per texture tile for
    material slot i (faces of untextured slots still get UVs; they're harmless)."""
    n_loops = len(me.loops)
    if not n_loops:
        return
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    vidx = np.empty(n_loops, np.int32)
    me.loops.foreach_get("vertex_index", vidx)
    npoly = len(me.polygons)
    start = np.empty(npoly, np.int32)
    total = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_start", start)
    me.polygons.foreach_get("loop_total", total)
    normals = np.empty(npoly * 3, np.float32)
    me.polygons.foreach_get("normal", normals)
    normals = normals.reshape(-1, 3)
    mats = np.empty(npoly, np.int32)
    me.polygons.foreach_get("material_index", mats)
    poly_of_loop = np.repeat(np.arange(npoly), total)
    n = normals[poly_of_loop]
    p = co[vidx]
    axis = np.abs(n).argmax(axis=1)
    sign = np.sign(n[np.arange(n_loops), axis])
    sign[sign == 0] = 1
    u = np.where(axis == 0, p[:, 1] * sign, np.where(axis == 1, -p[:, 0] * sign, p[:, 0] * sign))
    v = np.where(axis == 2, p[:, 1] * sign, p[:, 2])
    scale = np.asarray(sizes, np.float32)[np.clip(mats[poly_of_loop], 0, len(sizes) - 1)]
    uv = np.column_stack([u / scale, v / scale]).astype(np.float32)
    layer = me.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", uv.ravel())


def ensure_uvs():
    """Give every mesh with a textured material a box-projected UV map (before export/render)."""
    done = 0
    for me in bpy.data.meshes:
        if me.uv_layers or not me.users:
            continue
        sizes = [float(m.get("tex_size", 0)) if m else 0.0 for m in me.materials]
        if not any(sizes):
            continue
        box_uvs(me, [s or 1.0 for s in sizes])
        done += 1
    return done


# ---------------------------------------------------------------- decals

def decal(name, image, size, location=(0, 0, 0), rotation=(0, 0, 0), color=None, wrap_radius=None,
          segments=12, roughness=0.6, collection=None, uv=(0.0, 0.0, 1.0, 1.0), material_name=None):
    """A flat (or cylinder-wrapped) quad showing `image` with its alpha as a cutout: lettering,
    signs, paint-marker writing, stickers. It lies in its local XY plane facing +Z, image x along
    local X. wrap_radius bends it around a cylinder whose axis is parallel to local X and lies
    wrap_radius below the decal (for writing on pipes: put location on the pipe's surface).
    uv: the part of the image to show (u0, v0, u1, v1), for many decals sharing one atlas image
    (give them the same material_name so they share one material too)."""
    from .core import _place, material
    w, h = size
    mat = material(material_name or f"decal_{name}", color, roughness=roughness, texture=image, cutout=True)
    u0, v0, u1, v1 = uv
    rows = segments if wrap_radius else 1
    verts, uvs = [], []
    for j in range(rows + 1):
        t = j / rows
        y = (t - 0.5) * h
        if wrap_radius:
            a = y / wrap_radius
            yy, zz = wrap_radius * math.sin(a), wrap_radius * math.cos(a) - wrap_radius
        else:
            yy, zz = y, 0.0
        for i in (0, 1):
            verts.append(((i - 0.5) * w, yy, zz + 0.0015))   # lift a little off the surface
            uvs.append((u0 + (u1 - u0) * i, v0 + (v1 - v0) * t))
    faces = [(2 * j, 2 * j + 1, 2 * j + 3, 2 * j + 2) for j in range(rows)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[me.loops[li].vertex_index]
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = bool(wrap_radius)
    obj = bpy.data.objects.new(name, me)
    obj["decal"] = True
    return _place(obj, location, rotation, (1, 1, 1), collection)


def text_atlas(lines, height=48, color="#ffffff", width=None, **kw):
    """Render many text lines into one RGBA image (one line per row band) for decals.
    Returns (pixels, {line: (u0, v0, u1, v1)}) with UVs in Blender's convention (v up)."""
    masks = [text_mask(t, height, **kw) for t in lines]
    W = width or max(m.shape[1] for m in masks)
    H = height * len(lines)
    rgba = np.zeros((H, W, 4), np.float32)
    rgba[..., :3] = _rgb(color)
    rects = {}
    for i, (t, m) in enumerate(zip(lines, masks)):
        w = min(W, m.shape[1])
        rgba[i * height:(i + 1) * height, :w, 3] = m[:, :w]
        rects[t] = (0.0, 1 - (i + 1) * height / H, w / W, 1 - i * height / H)
    return rgba, rects
