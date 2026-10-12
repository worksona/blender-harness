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
| Detailed structures | `MeshBuilder(name)` assembles hundreds of parts into one object: `box`, `slab`, `beam(a, b)`, `rod(a, b)`, `cylinder`, `sphere`, `dome`, `torus`, `pipe(points)` (ball elbows), `tube(points, bend_radius=)` (smooth real pipe bends), `flange`, `handwheel`, `ladder(cage=True)`, `railing`, `ring_platform`, then `.build()`. Use it for frames, pipework, and vessels. `worlds/oil-refinery` shows it at scale |
| Terrain | `terrain(name, size, resolution, height=f(x, y), bands=[(max_z, mat), ...], center=, backdrop=)`, `fbm`, `island_falloff`, `scatter(rng, n, area, height, accept, min_dist)`, `slope` |
| Water | `ocean(level, waves='calm'|'moderate'|'rough', wind, color, shallow, foam, clarity)`, `bob(obj, amount, draft)` makes an object float on the viewer's waves |
| Time of day | `atmosphere(time="18:40", latitude, day, north, haze, visibility, exposure, lamps)`: real solar position, sun colour from atmospheric extinction, a physical sky, distance haze, automatic exposure, and lamps that switch on at dusk. Prefer it over manual `sun`/`sky`/`fog` |
| Night and effects | `lamp(location, color, power, pool_z=, light=)`, `lamps_along(points, spacing, height)`, `plume(base, height, radius, drift)` (steam: volumetric in Blender, animated particles in the viewer) |
| Environment (manual) | `sun(elevation, azimuth, strength, color)`, `sky(color, strength, ground, glow, glow_height)`, `fog(color, near, far)`, `camera(location, target, lens)` |
| Plant equipment | `from harness import industrial as ind`: `vessel`, `drum`, `steel_frame`, `pipe_rack`, `air_coolers`, `storage_tank`, `lpg_sphere`, `fired_heater`, `stack`, `cooling_tower`, `flare`, and instanced infill `kit_prefabs` + `fill` |
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

## Time of day and lighting

`atmosphere()` drives everything from one set of numbers, and the Blender render and the web
viewer use the same model. The sky is calibrated so both agree within about 20% from noon to
twilight. Lamp watts are scaled so a lamp is about 1/600 of a high sun.

- Preview another time without changing the world:
  `scripts/bl tools/build_world.py <slug> --time 21:30 [--haze 0.6] [--lamps on] [--ev 0.5]`
  writes `build/<slug>/time2130.jpg`.
- In the viewer, the Light button (key L) gives a time slider, a ▶ button to play through the
  day, season, latitude, haze, visibility, exposure and lamps. The URL keeps the state
  (`#/w/<slug>?t=21.5&haze=0.3...`). Worlds with hand-set lighting switch to the physical sky
  as soon as you move a control.
- `META["draft"] = True` keeps a work-in-progress world out of `--all` and CI.

## Building from a reference photo

Put the photo(s) in `worlds/<slug>/reference/`. Every build then writes
`build/<slug>/compare.jpg` with the first photo on the left and the render on the right.
`worlds/gas-station` is the worked example. The loop:

1. Read the photo and list the equipment, materials, sky and light, and roughly where the camera is.
2. Set `META["render"]["res"]` to the photo's aspect ratio. For saturated, camera-like
   colours add `"view": "Standard"` (and `"viewer": {"tone": "neutral"}` for the web app).
3. Measure; don't guess. The horizon's height in the frame gives the camera pitch. An object
   of known size (vessel diameter, ladder 0.5 m wide, handrail 1.1 m, truck 12 m) gives its
   distance from the share of the frame it covers (22 mm lens: horizontal tan = 0.818 per
   half-frame). Place things at those distances. Get the camera right first, because
   everything else depends on it.
4. Build at low samples, Read `compare.jpg`, fix the biggest difference, and repeat. Then
   do a final build at full quality.
5. Accept what one photo can't give you: hidden sides, exact dimensions, untraceable pipe
   routes. Make them plausible, and tell the user which parts are inferred.

## Web app

`make serve` runs it at http://localhost:8000. `tools/serve.py` disables caching, so a reload
picks up your edits. The gallery reads `app/worlds/index.json`.
Opening `#/w/<slug>` loads that world's `meta.json` (camera, sun, sky, fog, ocean) plus
`world.glb`. Per-world viewer overrides go in `META["viewer"]`: `bloom`, `exposure`, and `tone`
(`"agx"`, the default, or `"neutral"` for saturated photo-matched colours).
`window.viewer` exposes `{scene, camera, controls, renderer, ocean}` for debugging. For example,
`viewer.renderer.info.render.calls` gives the draw-call count. Shadows follow the orbit target
and scale with zoom. three.js
is pinned to 0.170.0 via the import map in `app/index.html`.

The ocean shader lives in `app/ocean.js`. The sky model is shared between the dome and the
reflections in `app/sky.js`.
