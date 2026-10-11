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
from manifest import write_manifest  # noqa: E402

WORLDS = os.path.join(ROOT, "worlds")
APP_WORLDS = os.path.join(ROOT, "app", "worlds")
BUILD = os.path.join(ROOT, "build")


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
    mod.build(Context(slug, meta, args))
    output.ensure_defaults()
    t_build = time.time() - t0

    out = os.path.join(APP_WORLDS, slug)
    output.export_glb(os.path.join(out, "world.glb"))
    st = output.stats()
    st["glb_bytes"] = os.path.getsize(os.path.join(out, "world.glb"))

    renders = []
    if not args.no_render:
        renders.append(output.render(os.path.join(out, "preview.jpg"),
                                     args.res, args.samples))
        if args.top:
            renders.append(output.render(os.path.join(BUILD, slug, "top.jpg"), (1024, 1024),
                                         max(8, args.samples // 2), camera=output.top_camera()))
    if args.blend:
        output.save_blend(os.path.join(BUILD, slug, f"{slug}.blend"))

    record = {
        "slug": slug,
        "title": meta.get("title", slug.replace("-", " ").title()),
        "description": meta.get("description", ""),
        "tags": meta.get("tags", []),
        "seed": meta.get("seed", 1),
        "glb": f"worlds/{slug}/world.glb",
        "preview": f"worlds/{slug}/preview.jpg",
        "viewer": {**output.viewer_meta(), **meta.get("viewer", {})},
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


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser(prog="build_world")
    p.add_argument("slugs", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--no-render", action="store_true", help="export only, skip preview render")
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--res", default="1280x720")
    p.add_argument("--top", action="store_true", help="also render a top-down layout view")
    p.add_argument("--blend", action="store_true", help="also save build/<slug>/<slug>.blend")
    args = p.parse_args(argv)
    args.res = tuple(int(v) for v in args.res.lower().split("x"))

    slugs = args.slugs
    if args.all:
        slugs = sorted(d for d in os.listdir(WORLDS)
                       if not d.startswith(("_", ".")) and
                       os.path.exists(os.path.join(WORLDS, d, "world.py")))
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
