"""Scaffold worlds/<slug>/world.py from the template (plain Python, no Blender needed).

    python3 tools/new_world.py "Desert Canyon"
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: python3 tools/new_world.py "World Title"')
    title = " ".join(sys.argv[1:]).strip()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    dest = os.path.join(ROOT, "worlds", slug)
    if os.path.exists(dest):
        sys.exit(f"worlds/{slug} already exists")
    with open(os.path.join(ROOT, "worlds", "_template", "world.py")) as f:
        src = f.read()
    os.makedirs(dest)
    with open(os.path.join(dest, "world.py"), "w") as f:
        f.write(src.replace("World Title", title))
    print(f"created worlds/{slug}/world.py")
    print(f"build it:  scripts/bl tools/build_world.py {slug} --top")


if __name__ == "__main__":
    main()
