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
riding the waves), **Coastal Oil Refinery** (the hi-res showcase: about 1 km of process units,
1.8M triangles, 3 MB Draco-compressed, with a tanker riding the swell), **Low-Poly Island**, and
**Neon City**.

A usage guide (getting started, use cases, limits, and a reference) ships with the app: open
`guide.html`, or follow "How to use the harness" from the gallery.

## Three ways to run it

### 1. Claude Code on the web (claude.ai/code): recommended

1. Push this repo to GitHub.
2. At claude.ai/code, create an **environment** for it:
   - **Setup script**: paste the whole of [`scripts/cloud-env-setup.sh`](scripts/cloud-env-setup.sh).
     It installs Blender **once**. The environment is saved as a snapshot and reused, so sessions
     start with Blender already there; nothing is downloaded per session. It re-runs only if you
     edit the script or the network settings, or after about 7 days, and takes about a minute.
   - **Network access**: choose *Custom* and add `download.blender.org` (keep the defaults) for the
     official build. On the default *Trusted* network it installs Blender from PyPI (`bpy`) instead.
3. Start a session on the repo. If Blender is somehow missing, the SessionStart hook
   ([`.claude/settings.json`](.claude/settings.json)) installs it as a fallback. Claude reads
   [`CLAUDE.md`](CLAUDE.md).

Why not keep Blender in the repo? It's about 380 MB compressed (1 GB installed). GitHub rejects
files over 100 MB, Git LFS is metered, and every session would still download it when it clones
the repo. The cached setup script is the one place it's downloaded only once.
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
make haven                    # Haven Home Assistant bundle with the haven-home model
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

**Live site:** https://worksona-blender-worlds.netlify.app (Netlify, worksona team).
**Every push to `main` deploys automatically.** A GitHub webhook triggers a Netlify build, which
clones the repo with a read-only deploy key and publishes `app/` using `netlify.toml`. Nothing
to compile, since built worlds are committed. `make deploy` still publishes by hand if needed.
Worlds marked `META["private"] = True` are removed from this site on every build.

**Oil and gas worlds, private twins included**, go to a second Netlify project from the same
repo, `blender-harness-twins`: `gas-station`, `oil-refinery`, `refinery-dusk`,
`purnell-test-shop` and `purnell-spools`. It is password-protected in the Netlify dashboard
(*Project configuration → Access & security → Visitor access*).
[`scripts/netlify-build.sh`](scripts/netlify-build.sh) recognises it by its project name (Netlify
sets `SITE_NAME` in every build; `INCLUDE_PRIVATE=true` does the same on any project), publishes
exactly that list (set `TWINS_WORLDS` to change it) and marks the site `noindex`. Every other
project builds the public site, so a misconfigured site publishes less, not more. A misspelt world
in the list fails the build. The first lines of each build log say which build it chose.

### GitHub Pages (alternative)

[`.github/workflows/worlds.yml`](.github/workflows/worlds.yml) rebuilds every world from source
on each push to check that they all still build. Deploying `app/` to GitHub Pages is opt-in:
enable Pages (*Settings → Pages → Source: GitHub Actions*), then set the repository variable
`DEPLOY_PAGES=true` (*Settings → Secrets and variables → Actions → Variables*). Built worlds are
also committed, so the app works straight from a clone with `make serve`.

## Layout

```
harness/      world-building API (core, terrain, water, env, output)
tools/        build_world.py, manifest.py, new_world.py, doctor.py, haven_bundle.py
worlds/       one folder per world; _template/ is the scaffold
app/          index.html, app.js (gallery + viewer), ocean.js, sky.js, worlds/ (built output)
haven/        Haven Home Assistant dashboard that shows worlds/haven-home live (haven/README.md)
scripts/      setup.sh (installer), bl (Blender runner), session-start.sh (cloud hook)
.claude/      settings.json (hook + permissions), skills/build-world, launch.json
```
