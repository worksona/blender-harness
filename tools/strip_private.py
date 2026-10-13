"""Remove worlds from a copy of the app before publishing it.

    python3 tools/strip_private.py <app dir>
        removes private worlds (META["private"] = True): every public deploy runs this
        (Netlify, `make deploy`, the GitHub Pages job), so a world built from client documents
        stays in the repository and the local app but never reaches the public site.

    python3 tools/strip_private.py <app dir> --only gas-station,oil-refinery,...
        keeps exactly the listed worlds, private ones included, and removes the rest. Used by
        the password-protected Netlify project (see scripts/netlify-build.sh). Fails if a listed
        world doesn't exist, so a typo can't silently publish a site missing a world.

Plain Python, no Blender needed.
"""

import argparse
import json
import os
import shutil
import sys


def strip(app_dir, only=None):
    worlds_dir = os.path.join(app_dir, "worlds")
    present = sorted(d for d in os.listdir(worlds_dir)
                     if os.path.exists(os.path.join(worlds_dir, d, "meta.json")))
    if only is not None:
        missing = [s for s in only if s not in present]
        if missing:
            sys.exit(f"[strip_private] no such world(s): {', '.join(missing)}")
    removed = []
    for slug in present:
        with open(os.path.join(worlds_dir, slug, "meta.json")) as f:
            private = json.load(f).get("private")
        if (slug not in only) if only is not None else private:
            shutil.rmtree(os.path.join(worlds_dir, slug))
            removed.append(slug)
    index = os.path.join(worlds_dir, "index.json")
    if os.path.exists(index):
        with open(index) as f:
            data = json.load(f)
        data["worlds"] = [w for w in data["worlds"] if w["slug"] not in removed and
                          (only is not None or not w.get("private"))]
        with open(index, "w") as f:
            json.dump(data, f, indent=2)
    what = "world(s) not listed" if only is not None else "private world(s)"
    print(f"[strip_private] removed {len(removed)} {what}: {', '.join(removed) or '-'}")
    return removed


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app_dir", nargs="?", default="app")
    ap.add_argument("--only", help="comma- or space-separated slugs to keep (private ones included)")
    a = ap.parse_args()
    only = [s for s in a.only.replace(",", " ").split() if s] if a.only else None
    if only is not None and not only:
        sys.exit("[strip_private] --only needs at least one world")
    strip(a.app_dir, only)
