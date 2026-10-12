# Blender world harness

This repo builds 3D worlds in headless Blender from Python and shows them all in one web app.

- `worlds/<slug>/world.py`: one world as code (the source of truth).
- `harness/`: the API worlds use (`from harness import *`).
- `tools/build_world.py`: runs a world → `app/worlds/<slug>/world.glb`, `preview.jpg`, `meta.json`.
- `app/`: static three.js app (gallery + viewer + animated ocean). No build step.

## Setup

In Claude Code cloud sessions the SessionStart hook installs Blender automatically. Its status
line is in your context at session start. If Blender is missing, run `scripts/setup.sh`, then
`make doctor`. If setup fails on network, tell the user to allow `download.blender.org` (or
PyPI + GitHub) in the environment's network settings.

Always run Blender through `scripts/bl <script.py> [args]`. It works with either the Blender
binary or the `bpy` module, and fails the command when the script raises an error.

## Building a world: the loop

1. `make new NAME="Desert Canyon"` scaffolds `worlds/desert-canyon/world.py`.
2. Write `build(ctx)`. Use `ctx.rng` for every random choice.
3. `make world W=desert-canyon` builds it, renders the hero preview, and renders a top-down
   view at `build/desert-canyon/top.jpg` (~5–30 s on 4 CPUs).
4. **Look at the renders** with the Read tool: `app/worlds/<slug>/preview.jpg` and
   `build/<slug>/top.jpg`. Check composition, scale, floating or buried objects, empty areas,
   and lighting. Read the printed stats (objects, triangles, glb MB).
5. Iterate until it looks right, then commit `worlds/<slug>/` and `app/worlds/<slug>/`, plus
   `app/worlds/index.json`. Never commit `build/`.

For faster iterations use `scripts/bl tools/build_world.py <slug> --samples 8 --res 640x360`.
To build without rendering, add `--no-render`.

## Harness API (see harness/*.py docstrings)

| Area | Functions |
|---|---|
| Materials | `material(name, color, roughness, metallic, emission, emission_strength, alpha)` |
| Primitives | `box`, `sphere`, `cylinder`, `cone`, `plane`, `mesh(verts, faces)` |
| Prefabs | `join(name, parts)` merges parts into one mesh, `prefab(obj)` hides the template, `instance(prefab, ...)` places linked copies that cost nothing extra in the .glb |
| Detailed structures | `MeshBuilder(name)` assembles hundreds of parts into one object: `box`, `slab`, `beam(a, b)`, `rod(a, b)`, `cylinder`, `sphere`, `dome`, `torus`, `pipe(points)`, `ladder`, `railing`, `ring_platform`, then `.build()`. Use it for frames, pipework, and vessels. `worlds/oil-refinery` shows it at scale |
| Terrain | `terrain(name, size, resolution, height=f(x, y), bands=[(max_z, mat), ...], center=, backdrop=)`, `fbm`, `island_falloff`, `scatter(rng, n, area, height, accept, min_dist)`, `slope` |
| Water | `ocean(level, waves='calm'|'moderate'|'rough', wind, color, shallow, foam, clarity)`, `bob(obj, amount, draft)` makes an object float on the viewer's waves |
| Environment | `sun(elevation, azimuth, strength, color)`, `sky(color, strength, ground)`, `fog(color, near, far)`, `camera(location, target, lens)` |
| Grouping | `collection="Name"` on any object call |

## Rules

- Blender is Z-up, in meters, with the ground at z=0. Azimuth 0 = +Y (north), 90 = +X (east).
  The viewer converts to Y-up automatically.
- Only Principled BSDF color, roughness, metallic, emission, and alpha survive glTF export.
  Don't use procedural textures or node tricks for anything the web app must show. Use face
  bands, separate materials, or geometry instead.
- Repeated objects go through `prefab` + `instance`, never copies. The viewer turns them into GPU
  instances (one draw call per mesh and material), so a kit repeated 500 times costs little.
- Budgets per world: about 300k triangles drawn for ordinary worlds. Hi-res worlds can reach
  about 2M drawn if most of that comes from instances. Keep unique (stored) triangles under
  about 600k.
- An export over 10 MB is re-exported with Draco compression automatically (the viewer decodes
  it). Force it on or off with `META["export"] = {"draco": True/False}`.
- Preview render settings per world: `META["render"] = {"res": "1920x1080", "samples": 48}`.
  `--res` and `--samples` on the command line override them.
- Mark huge surroundings as backdrop (`plane(..., backdrop=True)`, `terrain(..., backdrop=True)`)
  so they don't distort framing, the top view, or shadows.
- `ocean()` is replaced in the viewer by an endless animated ocean with refraction, foam, and
  floating objects. The Blender preview shows an FFT ocean modifier instead.
- Previews render with Cycles on CPU (there is no GPU in the cloud). EEVEE and Workbench need
  a GPU, so don't use them.
- Keep worlds deterministic: the same seed must give the same world.

## Web app

`make serve` runs it at http://localhost:8000. The gallery reads `app/worlds/index.json`.
Opening `#/w/<slug>` loads that world's `meta.json` (camera, sun, sky, fog, ocean) plus
`world.glb`. Per-world viewer overrides go in `META["viewer"]` (`bloom`, `exposure`).
`window.viewer` exposes `{scene, camera, controls, renderer, ocean}` for debugging. For example,
`viewer.renderer.info.render.calls` gives the draw-call count. Shadows follow the orbit target
and scale with zoom. three.js
is pinned to 0.170.0 via the import map in `app/index.html`.

The ocean shader lives in `app/ocean.js`. The sky model is shared between the dome and the
reflections in `app/sky.js`.
