"""Collect app/worlds/*/meta.json into app/worlds/index.json (plain Python, no Blender needed)."""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_WORLDS = os.path.join(ROOT, "app", "worlds")


def write_manifest():
    worlds = []
    for slug in sorted(os.listdir(APP_WORLDS)):
        meta = os.path.join(APP_WORLDS, slug, "meta.json")
        if os.path.exists(meta):
            with open(meta) as f:
                m = json.load(f)
            entry = {k: m[k] for k in ("slug", "title", "description", "tags", "preview")}
            if m.get("private"):
                entry["private"] = True
            worlds.append(entry)
    with open(os.path.join(APP_WORLDS, "index.json"), "w") as f:
        json.dump({"worlds": worlds}, f, indent=2)
    print(f"[manifest] {len(worlds)} worlds -> app/worlds/index.json")
    return worlds


if __name__ == "__main__":
    write_manifest()
