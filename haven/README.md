# HAVEN REALTIME V3.1: live architectural Home Assistant frontend

An interactive seven-room home model with connected Home Assistant controls. V3.1 replaces the
hand-coded WebGL geometry with a **production 3D model built in Blender** from code
(`worlds/haven-home` in this repo), rendered in the browser with three.js: real furniture and
fixtures, baked PBR textures (plank oak, veined marble, tile, plaster, upholstery weave, wool rugs,
walnut), soft sun shadows, ambient occlusion, image-based reflections and bloom. Everything is still
served locally from Home Assistant: no CDN, no external models or textures.

## Files

The bundle (`make haven` → `build/haven/Haven_Realtime_Deploy.zip`) contains:

- `haven/Haven_3D_Realtime_Ultra.html`: the web app (HA frontend, settings, built-in renderers).
- `haven/haven-glb.js`: the production-model renderer (three.js).
- `haven/haven-home.glb`: the Blender-built home model (about 6 MB).
- `haven/vendor/three/`: three.js 0.170.0 (MIT), vendored so the panel works offline.
- `haven/haven-3d-panel.js`: optional same-origin Home Assistant sidebar panel, which inherits the
  HA login instead of asking for a long-lived token.
- `haven/renderer_source.js`: the built-in procedural renderer's source, for review (already
  embedded in the HTML).
- `configuration_snippet.yaml`: HA sidebar registration.

## Install as a native Home Assistant panel

1. Copy everything in `haven/` (including `vendor/` and `haven-home.glb`) to `/config/www/haven/`
   on the Home Assistant host. `renderer_source.js` is optional.
2. Merge `configuration_snippet.yaml` into `/config/configuration.yaml`. If `panel_custom:` already
   exists, add only the `- name: haven-3d-panel` entry under it.
3. Check the configuration and restart HA. If an old version persists, refresh the browser cache.
4. Open **Haven Realtime** in the sidebar. It uses the HA session; no extra token is needed.
5. In the settings (gear icon), assign discovered entities to the seven model rooms and optionally
   map each scene button to a `scene.*` entity.

Standalone: serve the `haven/` folder over HTTPS (for example from HA's `/local/haven/`) and open
the HTML; enter an HA URL and long-lived token in settings. Opening the HTML from `file://` does
not work, because browsers block module and model loading from local files.

## How the 3D view starts

1. The built-in WebGL2 renderer draws at once, so the panel is never blank.
2. `haven-home.glb` loads in the background (progress shows in the footer), then replaces it.
3. Without WebGL2, the lightweight isometric view loads instead. The HA controls work in all three.

URL options: `?quality=ultra|lite` pins the quality mode (otherwise Ultra drops to Lite once, on
its own, when the first frames run under about 25 fps). `?engine=procedural` skips the production
model. `?model=<url>` loads another .glb that follows the same conventions.

| Mode | What it renders |
|---|---|
| Ultra | 4096 px sun shadows, ambient occlusion (GTAO), one light per lamp (14), up to 2x pixel ratio |
| Lite | 1536 px shadows, no AO, one light per room (7), 1x pixel ratio. For phones and tablets |
| Cinematic | bloom on lamps, screens and the plinth LED (toggle) |

## What Home Assistant drives in the model

The model is driven by the same `devices` state as the device panels. A command doesn't show as
done until HA confirms the new state.

- **Lights**: each room's lamps follow the average brightness of that room's `light` entities.
  Lamp shades, bulbs, the kitchen LED strip and the office monitors glow with them.
- **TV**: the living-room screen lights up when a `media_player` in the living room is on.
- **Blinds**: the bedroom's venetian blinds draw up to the head rail when a bedroom `cover` is open.
- **Fan**: the hall pedestal fan spins when a hall `fan` is on. With no fan mapped, it turns slowly
  as ambient motion.
- **Rooms**: click any surface to select its room; the camera eases in and a gold frame outlines it.
- **Time of day**: the timeline moves the sun from east to west, warms it at golden hour, and
  switches to moonlight at night. Tall walls hide on their own while the camera orbits behind them.

## Changing the model

The model is code: `worlds/haven-home/world.py` (layout and furniture) and
`worlds/haven-home/surfaces.py` (baked textures) in the blender-harness repo. Edit, then:

```
make world W=haven-home     # rebuild the .glb and render a preview (about 30 s)
make haven                  # assemble build/haven/Haven_Realtime_Deploy(.zip)
```

The plan matches the `rooms` table in the HTML exactly (glTF metres, Y up, same x/z), so room
selection, labels and camera focus line up. The renderer finds what HA drives through glTF extras on
objects:

| Extra | Meaning |
|---|---|
| `haven_room: "<room>"` | room floor (also used for `blind`, to name its cover's room) |
| `haven_light: "<room>"`, `haven_power: n` | light anchor: a point light is placed here, scaled by `n` |
| `haven_glow: "<room>"` | emissive part that brightens with the room's lights |
| `haven_role: "tv_screen" \| "blind" \| "fan_rotor" \| "monitor"` | driven parts. `fan_rotor` takes `haven_axis` (local spin axis) |
| `haven_cutaway: "north" \| "west"` | tall wall parts hidden while the camera is behind them |

To match a real residence, rebuild the walls from a dimensioned floor plan in `world.py` and keep
the room ids. Any glTF that uses these extras works with `?model=`.

## Fixed in V3.1

- The V3.0 WebGL2 fragment shader didn't compile in real browsers (`sampler2DShadow` had no
  precision qualifier, and `active` is a reserved word in GLSL ES 3.00), so V3.0 always fell back
  to the 2D isometric view. Both are fixed, and its lamp lighting no longer blows out.

## Tests and limitations

- Tested in headless Chromium (software WebGL2) at 1440 x 900 and 390 x 844: model load, day and
  night lighting, scenes, room selection, TV, blinds, quality modes and the fallback path.
  Real GPU performance and a live Home Assistant connection weren't available in this environment.
- The apartment is an illustrative layout, not a scan of a real residence.
