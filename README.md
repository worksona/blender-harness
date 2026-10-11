# Blender world harness

Build 3D worlds with **Claude + headless Blender** in the cloud, and ship them all in **one
web app**.

Each world is a Python file. The harness runs it in Blender, exports a `.glb`, and renders a
preview that Claude looks at to check its own work. The three.js app turns every built world
into a gallery card and an explorable scene. Worlds with water get a live animated ocean with
floating objects.

```
worlds/<slug>/world.py  ──scripts/bl──▶  Blender (headless, Cycles CPU)
                                           ├─ app/worlds/<slug>/world.glb    geometry + materials
                                           ├─ app/worlds/<slug>/preview.jpg  hero render (Claude reviews it)
                                           ├─ app/worlds/<slug>/meta.json    camera, sun, sky, fog, ocean
                                           └─ build/<slug>/top.jpg           layout check (not committed)
app/  ──▶  gallery of every world + three.js viewer (orbit, shadows, bloom, animated ocean)
```

Included worlds: **Golden Harbor** (the ocean showcase: sunset swell, sailboats and buoys
riding the waves), **Low-Poly Island**, and **Neon City**.

## Three ways to run it

### 1. Claude Code on the web (claude.ai/code): recommended

1. Push this repo to GitHub.
2. At claude.ai/code, create an **environment** for it:
   - **Network access**: choose *Custom* and add `download.blender.org` (keep the defaults).
     That gets the official Blender build. If you stay on the default *Trusted* network, setup
     installs Blender from PyPI (`bpy`) instead, which is also fine.
   - **Setup script** (optional, speeds up every session): paste the contents of
     [`scripts/setup.sh`](scripts/setup.sh). The installed Blender is then cached with the
     environment.
3. Start a session on the repo. The SessionStart hook ([`.claude/settings.json`](.claude/settings.json))
   installs Blender if it isn't there yet (about 1–2 min), then Claude reads [`CLAUDE.md`](CLAUDE.md).
4. Ask for a world: *"Make a foggy pine valley at dawn with a wooden cabin and a river."*
   Claude scaffolds it, builds it, looks at the renders, iterates, and commits.

Cloud sessions have about 4 vCPU, 16 GB RAM, and no GPU. Previews render with Cycles on CPU
in seconds.

### 2. Docker: any cloud VM, or locally

```bash
docker compose build            # Ubuntu 24.04 + Blender 5.2.2 + Claude Code (linux/amd64)
make docker-claude              # Claude Code inside the container, repo mounted at /workspace
make docker-shell               # or a shell; then: make worlds && make serve
```
The image is x86_64. On Apple Silicon it runs under emulation, which works but is slower.

### 3. Devcontainer / GitHub Codespaces

Open the repo in Codespaces (or *Reopen in Container* in VS Code). It uses the same
Dockerfile, forwards port 8000, and runs `make doctor` on start.

## Commands

```bash
make setup                    # install headless Blender (idempotent)
make doctor                   # check version, Cycles render, glTF export
make new NAME="Desert Canyon" # scaffold worlds/desert-canyon/world.py
make world W=desert-canyon    # build one world (+ top-down view)
make worlds                   # build all
make serve                    # app at http://localhost:8000
```

## Writing a world

```python
from harness import *

META = {"title": "Pine Cove", "description": "...", "tags": ["nature"], "seed": 3}

def height(x, y):
    return island_falloff(x, y, 80) * 20 * (0.6 + 0.4 * fbm(x, y, scale=30))

def build(ctx):
    grass, rock = material("grass", "#6e9a45"), material("rock", "#8a8580")
    terrain("Land", size=200, height=height, bands=[(10, grass), (99, rock)])
    ocean(level=0, waves="moderate", wind=30)

    pine = prefab(join("Pine", [cylinder("trunk", 0.25, 1.6), cone("top", 1.6, 4, location=(0, 0, 1.2))]))
    for i, (x, y, z) in enumerate(scatter(ctx.rng, 200, 80, height, lambda x, y, z: z > 1.5, min_dist=3)):
        instance(pine, f"Pine.{i}", (x, y, z), (0, 0, ctx.rng.uniform(0, 360)))

    sun(elevation=30, azimuth=200); sky("#9cc7f0"); camera((140, -140, 70), (0, 0, 5))
```

See [`CLAUDE.md`](CLAUDE.md) for the full API and the rules (Z-up, glTF-safe materials,
budgets).

## Publishing the app

[`.github/workflows/worlds.yml`](.github/workflows/worlds.yml) rebuilds every world from source
on each push and deploys `app/` to GitHub Pages. Turn it on once under
*Settings → Pages → Source: GitHub Actions*. Built worlds are also committed, so the app works
straight from a clone with `make serve`.

## Layout

```
harness/      world-building API (core, terrain, water, env, output)
tools/        build_world.py, manifest.py, new_world.py, doctor.py
worlds/       one folder per world; _template/ is the scaffold
app/          index.html, app.js (gallery + viewer), ocean.js, sky.js, worlds/ (built output)
scripts/      setup.sh (installer), bl (Blender runner), session-start.sh (cloud hook)
.claude/      settings.json (hook + permissions), skills/build-world, launch.json
```
