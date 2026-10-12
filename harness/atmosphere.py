"""Time of day and atmosphere.

One call sets up physically based daylight for a world, consistently for the Blender render and the
web viewer:

    atmosphere(time="18:40", latitude=58.3, day=172, haze=0.35)

- sun position from the real solar geometry (time, latitude, day of year, which way is north)
- sun colour and strength from atmospheric extinction (low sun turns orange and red, then sets)
- a physical sky (Blender's multiple-scattering sky; the viewer computes the same kind of sky)
- distance haze from `haze` / `visibility`
- automatic exposure (twilight and night are brightened like a camera would) plus your EV offset
- lamps placed with lamp() switch on at dusk (lamps="auto"), or are forced on/off/dimmed

The viewer gets the same parameters in meta.json and exposes them as live controls (time slider,
haze, visibility, exposure, lamps), so a world can be explored at any time of day.
The build tool can override them: build_world.py <slug> --time 06:30 --haze 0.6
"""

import math

import bpy

from .core import STATE, hex_of

OVERRIDES = {}  # filled from build_world.py --time / --haze / --lamps / --ev

SKY_SCALE = 0.12      # physical sky radiance -> scene units (balances sky against a strength-5 sun)
SUN_ZENITH = 5.0      # sun strength (W/m^2 in Blender units) for a high sun in clean air


def _hours(time):
    if isinstance(time, (int, float)):
        return float(time) % 24
    hh, _, mm = str(time).partition(":")
    return (int(hh) + int(mm or 0) / 60.0) % 24


def solar_position(hours, latitude=45.0, day=172):
    """(elevation, azimuth) in degrees for local solar time. Azimuth is a compass bearing."""
    decl = math.radians(23.44) * math.sin(2 * math.pi * (284 + day) / 365.0)
    lat = math.radians(latitude)
    ha = math.radians(15.0 * (hours - 12.0))
    sin_el = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    el = math.asin(max(-1.0, min(1.0, sin_el)))
    az = math.atan2(math.sin(ha), math.cos(ha) * math.sin(lat) - math.tan(decl) * math.cos(lat))
    return math.degrees(el), (math.degrees(az) + 180.0) % 360.0


def sun_transmittance(elevation, haze):
    """RGB fraction of sunlight that survives the atmosphere (Rayleigh + aerosol extinction)."""
    zen = 90.0 - max(elevation, -2.0)
    # Kasten-Young air mass, softened below the horizon.
    airmass = 1.0 / (math.cos(math.radians(min(zen, 90.0))) + 0.50572 * (96.07995 - min(zen, 92.0)) ** -1.6364)
    rayleigh = (0.0397, 0.0975, 0.243)              # optical depth at ~680, 550, 440 nm
    beta = 0.02 + 0.28 * haze                       # Angstrom turbidity
    aerosol = tuple(beta * lam ** -1.3 for lam in (0.68, 0.55, 0.44))
    return tuple(math.exp(-airmass * (r + a)) for r, a in zip(rayleigh, aerosol))


def _lerp_table(x, table):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


# Shared with app/atmosphere.js: keep these two tables identical.
EXPOSURE_EV = [(-12.0, 6.5), (-8.0, 5.5), (-4.0, 3.8), (0.0, 1.5), (6.0, 0.4), (15.0, 0.0)]
# Lamp watts as placed by worlds are scaled by this when atmosphere() is used, so a lamp is
# ~1/400 of a high sun: invisible at noon, a soft glow at dusk, the main light at night.
LAMP_GAIN = 0.0015
LAMP_LEVEL = [(-6.0, 1.0), (-1.0, 0.85), (3.0, 0.35), (8.0, 0.0)]


def auto_exposure(elevation):
    return _lerp_table(elevation, EXPOSURE_EV)


def lamp_level(elevation):
    return _lerp_table(elevation, LAMP_LEVEL)


def atmosphere(time="12:00", latitude=45.0, day=172, north=0.0, haze=0.3, visibility=None,
               exposure=0.0, lamps="auto"):
    """Physically based time of day. Replaces sun() + sky() + fog().

    time:       "HH:MM" local solar time, or hours as a float.
    latitude:   degrees, positive north.        day: day of year (172 = June solstice).
    north:      compass bearing the scene's +Y axis points to (0 = +Y is north).
    haze:       0 = crystal clear .. 1 = thick haze (affects sky, sun colour and distance haze).
    visibility: meters until distant things fade into the haze (default from `haze`).
    exposure:   EV added to the automatic exposure.
    lamps:      "auto" (on at dusk), "on", "off", or a level 0..1.
    """
    time = OVERRIDES.get("time", time)
    haze = float(OVERRIDES.get("haze", haze))
    lamps = OVERRIDES.get("lamps", lamps)
    exposure = float(OVERRIDES.get("ev", exposure))
    hours = _hours(time)
    elevation, bearing = solar_position(hours, latitude, day)
    azimuth = (bearing - north) % 360.0           # relative to the scene's +Y
    if visibility is None:
        visibility = 60000.0 * (1.0 - haze) ** 2 + 4000.0
    if lamps == "auto":
        level = lamp_level(elevation)
    elif lamps == "on":
        level = 1.0
    elif lamps == "off":
        level = 0.0
    else:
        level = max(0.0, min(1.0, float(lamps)))

    # Sun lamp: coloured by extinction, fading out as it sets.
    from .env import sun
    t = sun_transmittance(elevation, haze)
    peak = max(t)
    color = tuple(c / peak for c in t) if peak > 0 else (1.0, 0.5, 0.2)
    fade = max(0.0, min(1.0, (elevation + 0.5) / 2.0))
    lum = 0.2126 * t[0] + 0.7152 * t[1] + 0.0722 * t[2]
    strength = SUN_ZENITH * lum / 0.8 * fade
    sun(elevation=elevation, azimuth=azimuth, strength=strength,
        color=hex_of(tuple(c ** (1 / 2.2) for c in color)), angle=0.545)

    # Physical sky in Blender, plus a faint night floor so it never goes fully black.
    world = bpy.data.worlds.new("Atmosphere")
    bpy.context.scene.world = world
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = True
    sky.sun_size = math.radians(0.545)
    sky.sun_elevation = math.radians(elevation)
    sky.sun_rotation = math.radians(azimuth)
    sky.air_density = 1.0
    sky.aerosol_density = 0.6 + haze * 5.0
    sky.ozone_density = 1.0
    night = nt.nodes.new("ShaderNodeMix")
    night.data_type = "RGBA"
    night.blend_type = "ADD"
    night.inputs["Factor"].default_value = 1.0
    night.inputs["B"].default_value = (0.0006, 0.0012, 0.0028, 1.0)
    nt.links.new(sky.outputs["Color"], night.inputs["A"])
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = SKY_SCALE
    nt.links.new(night.outputs["Result"], bg.inputs["Color"])

    # Approximate horizon colour, for the Blender render's distance haze and older code paths:
    # pale blue by day, tinted toward the sun colour as it gets low, dimming through twilight.
    day_amt = max(0.0, min(1.0, (elevation + 8.0) / 18.0))
    warm = max(0.0, min(1.0, 1.0 - elevation / 12.0)) * day_amt
    base = (0.62, 0.74, 0.92)
    horizon = tuple((base[i] * (1 - 0.5 * warm) + color[i] * 0.5 * warm) * (0.03 + 0.97 * day_amt)
                    for i in range(3))
    STATE["sky"] = {"color": hex_of(tuple(c ** (1 / 2.2) for c in (0.18 * day_amt, 0.36 * day_amt, 0.75 * day_amt + 0.02))),
                    "ground": "#4a4a44", "strength": SKY_SCALE * 8, "glow": None, "physical": True}
    STATE["fog"] = {"color": hex_of(tuple(min(1.0, c) ** (1 / 2.2) for c in horizon)),
                    "near": visibility * 0.05, "far": visibility}
    STATE["atmosphere"] = {
        "time": round(hours, 3), "latitude": latitude, "day": day, "north": north, "haze": haze,
        "visibility": round(visibility), "exposure": exposure, "lamps": lamps if isinstance(lamps, str) else level,
        "elevation": round(elevation, 2), "azimuth": round(azimuth, 2),
        "ev": round(auto_exposure(elevation) + exposure, 3), "lamp_level": round(level, 3),
    }
    return STATE["atmosphere"]
