"""Remove private worlds (META["private"] = True) from a copy of the app before publishing it.

    python3 tools/strip_private.py <app dir>

Used by every public deploy (Netlify build command, `make deploy`, the GitHub Pages job), so a
world built from client documents stays in the repository and the local app but never reaches
the public site. Plain Python, no Blender needed.
"""

import json
import os
import shutil
import sys


def strip(app_dir):
    worlds_dir = os.path.join(app_dir, "worlds")
    removed = []
    for slug in sorted(os.listdir(worlds_dir)):
        meta = os.path.join(worlds_dir, slug, "meta.json")
        if not os.path.exists(meta):
            continue
        with open(meta) as f:
            if json.load(f).get("private"):
                shutil.rmtree(os.path.join(worlds_dir, slug))
                removed.append(slug)
    index = os.path.join(worlds_dir, "index.json")
    if os.path.exists(index):
        with open(index) as f:
            data = json.load(f)
        data["worlds"] = [w for w in data["worlds"] if w["slug"] not in removed and not w.get("private")]
        with open(index, "w") as f:
            json.dump(data, f, indent=2)
    print(f"[strip_private] removed {len(removed)} private world(s): {', '.join(removed) or '-'}")
    return removed


if __name__ == "__main__":
    strip(sys.argv[1] if len(sys.argv) > 1 else "app")
