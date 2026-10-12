---
name: build-world
description: Create or iterate on a Blender-built 3D world in this repo — "make a world", "new world", "build a <theme> scene", "add X to the island", "the forest looks sparse", "build this from the photo". Scaffolds worlds/<slug>/world.py, builds it headless, reviews the renders visually (against a reference photo when one is given), and iterates.
---

# Build a world

## 1. Pin down the brief
From the request, settle: theme, time of day, mood, a hero feature, and scale (meters).
Ask only if the theme itself is unclear. Otherwise choose and state your choices.

## 2. Scaffold (new worlds only)
`make new NAME="<Title>"`, then edit `META` (title, one-line description, tags, seed).

### Given a reference photo?
Save it to `worlds/<slug>/reference/photo.jpg` and follow "Building from a reference photo"
in CLAUDE.md. Match the camera first using measured angles. After each build, Read
`build/<slug>/compare.jpg`.

## 3. Write `build(ctx)` in layers
1. Ground: `terrain(...)` with `bands`, or `plane(..., backdrop=True)`. Add water with `ocean(...)`.
2. Landmarks: one or two hero objects that are readable from the hero camera.
3. Set dressing: build prefabs with `join` + `prefab`, place them with `scatter` + `instance`.
4. Light: a `sun` elevation and color that fit the mood, `sky`, `fog`.
5. Camera: a 3/4 hero angle that frames the landmark. Low and close for drama, high for overview.

## 4. Build and look
```bash
make world W=<slug>        # or: scripts/bl tools/build_world.py <slug> --top --samples 8 --res 640x360
```
Then Read both `app/worlds/<slug>/preview.jpg` and `build/<slug>/top.jpg`. Check for:
- objects floating above or buried in the terrain (sample `height(x, y)` when placing)
- empty or overcrowded areas in the top view; a landmark hidden or cropped in the hero view
- scale problems (doors ~2 m, trees 4–15 m, people ~1.8 m)
- lighting that is blown out, too dark, or fighting the mood
- stats over budget (300k triangles drawn, 15 MB glb)

Fix and rebuild. Usually 2–4 rounds.

## 5. Finish
- Do a final build at default quality: `make world W=<slug>`.
- If a browser is available, run `make serve` and open `#/w/<slug>` to check the live viewer.
- Commit `worlds/<slug>/`, `app/worlds/<slug>/`, and `app/worlds/index.json`.
- Report back with the preview image path and the stats line.
