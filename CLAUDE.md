# Blender world harness

This repo builds 3D worlds in headless Blender from Python and shows them all in one web app.

- `worlds/<slug>/world.py`: one world as code (the source of truth).
- `harness/`: the API worlds use (`from harness import *`).
- `tools/build_world.py`: runs a world → `app/worlds/<slug>/world.glb`, `preview.jpg`, `meta.json`.
- `app/`: static three.js app (gallery + viewer + animated ocean). No build step.

## Setup

In Claude Code cloud sessions Blender is normally already installed: the environment's setup
script (`scripts/cloud-env-setup.sh`, pasted into the environment settings) installs it once, and
the environment snapshot is reused across sessions. If it's missing anyway, the SessionStart hook
installs it. The hook's status line is in your context at session start. If Blender is missing, run `scripts/setup.sh`, then
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
| Materials | `material(name, color, roughness, metallic, emission, emission_strength, alpha, texture=, texture_size=, normal=, roughness_map=, cutout=)` |
| Textures | `texture(name, pixels, data=)` turns numpy pixels into an image that is embedded in the .glb. Generators: `fbm_noise`, `value_noise`, `grime`, `height_normal`, `colorize`, `contrast`, `blur`, `make_tileable`, `photo_patch(photo, box)` (tileable crop of a reference photo), `text_image`/`text_mask`/`text_atlas` (lettering in Blender's font). `decal(name, image, size, ..., wrap_radius=, uv=)` places lettering, signs or labels, flat or wrapped around a pipe |
| Primitives | `box`, `sphere`, `cylinder`, `cone`, `plane`, `mesh(verts, faces)` |
| Prefabs | `join(name, parts)` merges parts into one mesh, `prefab(obj)` hides the template, `instance(prefab, ...)` places linked copies that cost nothing extra in the .glb |
| Detailed structures | `MeshBuilder(name)` assembles hundreds of parts into one object: `box`, `slab`, `beam(a, b)`, `rod(a, b)`, `cylinder`, `sphere`, `dome`, `torus(rotation=)`, `pipe(points)` (ball elbows), `tube(points, bend_radius=)` (smooth real pipe bends), `flange`, `handwheel`, `ladder(cage=True)`, `railing`, `ring_platform`, then `.build(sharp_angle=)`. Use it for frames, pipework, and vessels. `worlds/oil-refinery` shows it at scale |
| Furniture and products | `MeshBuilder` also has `rounded_box(center, size, mat, radius, puff=)` (bevelled cabinets, worktops; `puff` bulges cushions, mattresses, pillows), `rounded_slab(center, size, corner)` (round-cornered tops, rugs), `lathe(base, [(r, z), ...], scale=)` (vases, shades, bowls, glasses, basins, oval tubs) and `faces(verts, faces)` (leaves, drapes). Build with `sharp_angle=50` so lathe rims stay crisp. `worlds/haven-home` is the worked example |
| Terrain | `terrain(name, size, resolution, height=f(x, y), bands=[(max_z, mat), ...], center=, backdrop=)`, `fbm`, `island_falloff`, `scatter(rng, n, area, height, accept, min_dist)`, `slope` |
| Water | `ocean(level, waves='calm'|'moderate'|'rough', wind, color, shallow, foam, clarity)`, `bob(obj, amount, draft)` makes an object float on the viewer's waves |
| Time of day | `atmosphere(time="18:40", latitude, day, north, haze, visibility, exposure, lamps)`: real solar position, sun colour from atmospheric extinction, a physical sky, distance haze, automatic exposure, and lamps that switch on at dusk. Prefer it over manual `sun`/`sky`/`fog` |
| Night and effects | `lamp(location, color, power, pool_z=, light=)`, `lamps_along(points, spacing, height)`, `plume(base, height, radius, drift)` (steam: volumetric in Blender, animated particles in the viewer) |
| Environment (manual) | `sun(elevation, azimuth, strength, color)`, `sky(color, strength, ground, glow, glow_height)`, `fog(color, near, far)`, `camera(location, target, lens)` |
| Process piping | `from harness import piping`: `Spool(name, nps, mats).walk(route, direction=)` builds a spool from an isometric-style route (`flange`, `pipe` with olets, `elbow`, `tee`, `reducer`, `flange_pair`, `blind`, `let`) at ASME B16.5/B16.9/B16.11 Class 600 dimensions. Each piece and weld is its own part (`sp.parts`, `sp.welds`) under one parent object, so each can carry a twin record; `test_blind`, `stud_prefab` and `bolt_joint` add test blinds and instanced studs. `worlds/purnell-test-shop/spools.py` matches parts to BOM items and welds to the drawing's weld table |
| Data twin | `twin_record(id, title, group=, fields=, tables=, notes=, images=, parent=, listed=)`, `twin_tag(obj, id)` (click it in the viewer: the first click selects the outermost record, the next drills into the part; table `row_ids` make rows clickable), `twin_series(id, title, unit, times, values, events=, tint_group=)` (replayable data with a chart), `twin_gauge(label, location, series)` (live readout floating in 3D) |
| Interiors and photo cameras | `interior(key_direction, key, ambient, env)` lights indoor worlds in the viewer (objects with `obj["no_cast"] = True`, such as roofs, don't block the key light). `photo_camera(photo, location, target, focal_35mm=, size=)` matches one reference photo, and each build writes `build/<slug>/compare-<photo>.jpg` |
| Plant equipment | `from harness import industrial as ind`: `vessel`, `drum`, `steel_frame`, `pipe_rack`, `air_coolers`, `storage_tank`, `lpg_sphere`, `fired_heater`, `stack`, `cooling_tower`, `flare`, and instanced infill `kit_prefabs` + `fill` |
| Grouping | `collection="Name"` on any object call |

## Rules

- Blender is Z-up, in meters, with the ground at z=0. Azimuth 0 = +Y (north), 90 = +X (east).
  The viewer converts to Y-up automatically.
- Principled BSDF color, roughness, metallic, emission and alpha survive glTF export, and so do
  image textures made with `harness.textures` (colour, normal and roughness maps, cutouts).
  Textured meshes get box-projected UVs automatically at the material's `texture_size`. Don't use
  Blender procedural texture nodes for anything the web app must show: bake them into pixels
  with `texture()` instead. Keep textures at 512 to 1024 px (one unique 2048x4096 floor is fine);
  they count toward the .glb size.
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
- `META["private"] = True` keeps a world (for example one built from client documents) out of
  every public deploy: Netlify, `make deploy` and GitHub Pages all run `tools/strip_private.py`.
  It still builds, and shows in the local app with a "private" tag. The password-protected
  Netlify project `blender-harness-twins` publishes the oil and gas worlds, private ones
  included (`scripts/netlify-build.sh` recognises it by its project name; the list is there
  too). Add a new oil and gas world to that list to publish it there.
- Objects with `obj["ceiling"] = True` (roofs, joists, ceiling lights) are left out of the top view.
- Documents a world shows in its twin go in `worlds/<slug>/docs/`. Each build copies the PNG and
  JPEG files to `app/worlds/<slug>/docs/`, and records refer to them as `docs/<file>`.

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

Several photos of one place: add a `photo_camera(photo, location, target, focal_35mm=, size=)`
per photo. Phones store the 35 mm-equivalent focal length in EXIF. Each build writes
`build/<slug>/compare-<photo>.jpg`; `--views a.jpg b.jpg` renders only those, `--no-views` none.
Solve the cameras against each other: a feature seen in two photos pins both, and column
spacing, door sizes and keystoning (how much verticals lean) give pitch and scale. Objects of
known size measure distance: a pipe's OD in pixels at several points along it gives the camera's
height and pitch (f_px = lens / 36 x image width). Then place things with
`python3 tools/photo_measure.py <slug> <photo> --px u,v [--z h]`, which projects photo pixels onto
the floor (or a plane at height h) through the solved camera (`--pt x,y,z` goes the other way;
the build writes the cameras to `build/<slug>/cameras.json`). Floor contacts (stand feet, pipe
ends lying down) are the most reliable; check a point seen in two photos against both.
`worlds/purnell-test-shop` is the worked example: three photos plus a test pack of drawings
(`worlds/purnell-spools` shows the same 21 spools on their own).

## Haven (Home Assistant dashboard)

`haven/` is the Haven Home Assistant dashboard, which shows `worlds/haven-home` live: its lamps, TV,
blinds and fan follow Home Assistant state. The world tags those parts with glTF extras
(`haven_room`, `haven_light`, `haven_glow`, `haven_role`, `haven_cutaway`; see `haven/README.md`),
and the plan uses the dashboard's room coordinates (Blender y = -Haven z). After changing the world,
`make haven` writes the deployable folder and zip to `build/haven/`. Keep its export Draco-free
(`META["export"]["draco"] = False`): the panel ships no Draco decoder.

## Web app

`make serve` runs it at http://localhost:8000. `tools/serve.py` disables caching, so a reload
picks up your edits. The gallery reads `app/worlds/index.json`.
Opening `#/w/<slug>` loads that world's `meta.json` (camera, sun, sky, fog, ocean) plus
`world.glb`. Per-world viewer overrides go in `META["viewer"]`: `bloom`, `exposure`, and `tone`
(`"agx"`, the default, or `"neutral"` for saturated photo-matched colours).
Worlds with twin records get a Twin button (key T): a searchable list of records, a card per
record (fields, tables, drawings), click-to-inspect in 3D (click again to drill into a part),
and a replay bar for time series with
gauges floating at instruments. `window.viewer` exposes `{scene, camera, controls, renderer, twin,
ocean}` for debugging. For example,
`viewer.renderer.info.render.calls` gives the draw-call count. Shadows follow the orbit target
and scale with zoom. three.js
is pinned to 0.170.0 via the import map in `app/index.html`.

The ocean shader lives in `app/ocean.js`. The sky model is shared between the dome and the
reflections in `app/sky.js`.
