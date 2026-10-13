"""Build worlds: run worlds/<slug>/world.py, export .glb + preview, update the app manifest.

Run through the wrapper so it works with either the Blender binary or the bpy module:

    scripts/bl tools/build_world.py <slug> [<slug> ...]      # build specific worlds
    scripts/bl tools/build_world.py --all                    # build every world
    options: --no-render  --samples N  --res 1280x720  --top  --blend
"""

import argparse
import importlib.util
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import harness  # noqa: E402
from harness import output  # noqa: E402
from harness.atmosphere import OVERRIDES as ATMOSPHERE_OVERRIDES  # noqa: E402
from harness.core import STATE  # noqa: E402
from manifest import write_manifest  # noqa: E402

EXPLORE = {}  # atmosphere overrides from the command line

WORLDS = os.path.join(ROOT, "worlds")
APP_WORLDS = os.path.join(ROOT, "app", "worlds")
BUILD = os.path.join(ROOT, "build")
DRACO_ABOVE = 10e6  # bytes; bigger exports are re-exported with Draco compression
DRACO_TRIS = 300_000  # unique triangles; above this, export with Draco straight away


class Context:
    """Passed to build(ctx). Use ctx.rng for all randomness so builds are reproducible."""

    def __init__(self, slug, meta, args):
        self.slug = slug
        self.meta = meta
        self.seed = meta.get("seed", 1)
        self.rng = random.Random(self.seed)
        self.quick = args.no_render


def load_world(slug):
    path = os.path.join(WORLDS, slug, "world.py")
    if not os.path.exists(path):
        sys.exit(f"no such world: {path}")
    spec = importlib.util.spec_from_file_location(f"world_{slug.replace('-', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(slug, args):
    t0 = time.time()
    mod = load_world(slug)
    meta = dict(getattr(mod, "META", {}))
    harness.reset()
    harness.textures.CACHE = os.path.join(BUILD, slug, "tex")
    mod.build(Context(slug, meta, args))
    output.ensure_defaults()
    harness.textures.ensure_uvs()
    t_build = time.time() - t0

    if EXPLORE:  # --time/--haze/--lamps/--ev: just render a look at that time of day
        rcfg = meta.get("render", {})
        res = args.res or _parse_res(rcfg.get("res", "1280x720"))
        tag = "-".join(f"{k}{str(v).replace(':', '')}" for k, v in EXPLORE.items())
        path = output.render(os.path.join(BUILD, slug, f"{tag}.jpg"), res,
                             args.samples or rcfg.get("samples", 24), look=rcfg.get("look", "None"),
                             view=rcfg.get("view", "AgX"), glare=rcfg.get("glare", 0.0),
                             grade=meta.get("grade"))
        atmo = STATE.get("atmosphere") or {}
        print(f"[world] {slug} at {EXPLORE}: sun {atmo.get('elevation')} deg, EV {atmo.get('ev')}, "
              f"lamps {atmo.get('lamp_level')} -> {os.path.relpath(path, ROOT)}")
        return None

    out = os.path.join(APP_WORLDS, slug)
    glb = os.path.join(out, "world.glb")
    # Documents the twin shows (drawings, report pages): worlds/<slug>/docs/*.png|jpg -> app.
    docs = os.path.join(WORLDS, slug, "docs")
    if os.path.isdir(docs):
        import shutil
        os.makedirs(os.path.join(out, "docs"), exist_ok=True)
        for f in sorted(os.listdir(docs)):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                shutil.copy2(os.path.join(docs, f), os.path.join(out, "docs", f))
    draco = meta.get("export", {}).get("draco")  # True / False / None = automatic
    if draco is None and output.stats()["triangles_stored"] > DRACO_TRIS:
        draco = True  # clearly big: skip the plain export that would only be thrown away
    output.export_glb(glb, draco=bool(draco))
    if draco is None and os.path.getsize(glb) > DRACO_ABOVE:
        raw = os.path.getsize(glb)
        try:
            output.export_glb(glb, draco=True)
            print(f"[world]   glb {raw / 1e6:.1f} MB > {DRACO_ABOVE / 1e6:.0f} MB, "
                  f"Draco-compressed to {os.path.getsize(glb) / 1e6:.1f} MB")
        except Exception as e:  # a Blender build without Draco: keep the plain export
            print(f"[world]   Draco unavailable ({e}); keeping uncompressed glb")
            output.export_glb(glb)
    st = output.stats()
    st["glb_bytes"] = os.path.getsize(glb)

    # Render settings: command line > META["render"] > defaults.
    rcfg = meta.get("render", {})
    res = args.res or _parse_res(rcfg.get("res", "1280x720"))
    samples = args.samples or rcfg.get("samples", 24)
    renders = []
    if not args.no_render:
        renders.append(output.render(os.path.join(out, "preview.jpg"), res, samples,
                                     look=rcfg.get("look", "None"), view=rcfg.get("view", "AgX"),
                                     glare=rcfg.get("glare", 0.0), grade=meta.get("grade")))
        if args.top:
            # Roofs and ceilings (obj["ceiling"] = True) would hide the layout: leave them out.
            import bpy
            ceiling = [o for o in bpy.context.scene.objects if o.get("ceiling")]
            for o in ceiling:
                o.hide_render = True
            renders.append(output.render(os.path.join(BUILD, slug, "top.jpg"), (1024, 1024),
                                         max(8, samples // 2), camera=output.top_camera()))
            for o in ceiling:
                o.hide_render = False
        # Photo-matched worlds: put each reference photo next to the render for comparison.
        ref_dir = os.path.join(WORLDS, slug, "reference")
        refs = sorted(f for f in os.listdir(ref_dir)
                      if f.lower().endswith((".jpg", ".jpeg", ".png"))) if os.path.isdir(ref_dir) else []
        views = {v["photo"]: v for v in STATE.get("ref_views", [])}
        if views:   # solved cameras, for tools/photo_measure.py
            import bpy
            cams = []
            for name, v in views.items():
                obj = bpy.data.objects[v["camera"]]
                img = bpy.data.images.load(os.path.join(ref_dir, name))
                cams.append({"photo": name, "pixels": list(img.size),
                             "matrix": [list(r) for r in obj.matrix_world],
                             "lens": obj.data.lens, "sensor_width": obj.data.sensor_width,
                             "shift": [obj.data.shift_x, obj.data.shift_y]})
                bpy.data.images.remove(img)
            os.makedirs(os.path.join(BUILD, slug), exist_ok=True)
            with open(os.path.join(BUILD, slug, "cameras.json"), "w") as f:
                json.dump(cams, f, indent=1)
        if refs and refs[0] not in views:
            renders.append(output.side_by_side(os.path.join(ref_dir, refs[0]), renders[0],
                                               os.path.join(BUILD, slug, "compare.jpg")))
        # photo_camera() views: render each from its matched camera, next to its photo.
        if args.views is not False:
            for name, v in views.items():
                if args.views and name not in args.views:
                    continue
                import bpy
                w, h = v["size"]
                long_side = 1200 if samples >= 32 else 720
                vres = (long_side, round(long_side * h / w)) if w >= h else (round(long_side * w / h), long_side)
                stem = os.path.splitext(name)[0]
                shot = output.render(os.path.join(BUILD, slug, f"view-{stem}.jpg"), vres, samples,
                                     camera=bpy.data.objects[v["camera"]], look=rcfg.get("look", "None"),
                                     view=rcfg.get("view", "AgX"), glare=rcfg.get("glare", 0.0),
                                     grade=meta.get("grade"))
                renders.append(output.side_by_side(os.path.join(ref_dir, name), shot,
                                                   os.path.join(BUILD, slug, f"compare-{stem}.jpg"),
                                                   height=vres[1]))
    if args.blend:
        output.save_blend(os.path.join(BUILD, slug, f"{slug}.blend"))

    record = {
        "slug": slug,
        "title": meta.get("title", slug.replace("-", " ").title()),
        "description": meta.get("description", ""),
        "tags": meta.get("tags", []),
        "seed": meta.get("seed", 1),
        "private": bool(meta.get("private")),   # kept out of public deploys (tools/strip_private.py)
        "glb": f"worlds/{slug}/world.glb",
        "preview": f"worlds/{slug}/preview.jpg",
        # META["viewer"]["grade"] can soften the grade for the real-time viewer, whose lighting is
        # already a little more saturated than the path-traced render.
        "viewer": {**output.viewer_meta(), **meta.get("viewer", {}),
                   "grade": meta.get("viewer", {}).get("grade", meta.get("grade"))},
        "stats": st,
        "built_with": __import__("bpy").app.version_string,
    }
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(record, f, indent=2)

    total = time.time() - t0
    print(f"\n[world] {slug}: built in {t_build:.1f}s, total {total:.1f}s")
    print(f"[world]   {st['objects']} objects, {st['triangles_drawn']:,} tris drawn, "
          f"{st['triangles_stored']:,} stored, glb {st['glb_bytes'] / 1e6:.2f} MB")
    for r in renders:
        print(f"[world]   render: {os.path.relpath(r, ROOT)}")
    return record


def _parse_res(text):
    return tuple(int(v) for v in text.lower().split("x"))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser(prog="build_world")
    p.add_argument("slugs", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--no-render", action="store_true", help="export only, skip preview render")
    p.add_argument("--samples", type=int, help="default: META['render']['samples'] or 24")
    p.add_argument("--res", help="WxH; default: META['render']['res'] or 1280x720")
    p.add_argument("--top", action="store_true", help="also render a top-down layout view")
    p.add_argument("--blend", action="store_true", help="also save build/<slug>/<slug>.blend")
    p.add_argument("--views", nargs="*", default=None,
                   help="photo_camera views to render (default all; give names to pick, "
                        "--no-views to skip)")
    p.add_argument("--no-views", dest="views", action="store_false")
    p.add_argument("--time", help="render the world at another time of day, e.g. 06:30 (preview only)")
    p.add_argument("--haze", type=float, help="override atmosphere haze 0..1 (preview only)")
    p.add_argument("--lamps", help="override lamps: auto | on | off | 0..1 (preview only)")
    p.add_argument("--ev", type=float, help="override exposure offset in EV (preview only)")
    args = p.parse_args(argv)
    args.res = _parse_res(args.res) if args.res else None
    for key in ("time", "haze", "lamps", "ev"):
        if getattr(args, key) is not None:
            EXPLORE[key] = getattr(args, key)
    ATMOSPHERE_OVERRIDES.update(EXPLORE)

    slugs = args.slugs
    if args.all:
        slugs = sorted(d for d in os.listdir(WORLDS)
                       if not d.startswith(("_", ".")) and
                       os.path.exists(os.path.join(WORLDS, d, "world.py")) and
                       not getattr(load_world(d), "META", {}).get("draft"))
    if not slugs:
        p.error("give one or more world slugs, or --all")

    failed = []
    for slug in slugs:
        try:
            build(slug, args)
        except Exception:
            import traceback
            traceback.print_exc()
            failed.append(slug)
    write_manifest()
    if failed:
        sys.exit(f"[world] FAILED: {', '.join(failed)}")


if __name__ == "__main__":
    main()
