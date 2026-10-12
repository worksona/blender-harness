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


# ---------------------------------------------------------------- sky radiance (port of app/atmosphere.js)
# Same single-scattering model the viewer bakes into its sky texture; used here for the colour of
# the distance haze so it matches the sky behind it. Directions are Z-up (Blender).

_R_EARTH, _R_ATMO, _H_R, _H_M = 6360e3, 6420e3, 8000.0, 1200.0
_BETA_R = (5.802e-6, 13.558e-6, 33.1e-6)
_BETA_O = (3.0e-6, 2.6e-6, 0.2e-6)
_SUN_INTENSITY = 300.0


def _ozone(h):
    return max(0.0, 1.0 - abs(h - 25000.0) / 15000.0)


def _ray_sphere(o, d, r):
    b = o[0] * d[0] + o[1] * d[1] + o[2] * d[2]
    c = o[0] ** 2 + o[1] ** 2 + o[2] ** 2 - r * r
    disc = b * b - c
    if disc < 0:
        return -1.0, -1.0
    s = math.sqrt(disc)
    return -b - s, -b + s


def sky_radiance(direction, sun_dir, haze, steps=16, light_steps=8):
    """Scene-referred sky radiance (before SKY_SCALE) along a Z-up unit direction."""
    o = (0.0, 0.0, _R_EARTH + 50.0)
    t_max = _ray_sphere(o, direction, _R_ATMO)[1]
    g = _ray_sphere(o, direction, _R_EARTH)
    if g[0] > 0:
        t_max = min(t_max, g[0])
    beta_m = 3.996e-6 * (1 + haze * 9)
    ds = t_max / steps
    od_r = od_m = od_o = 0.0
    sum_r, sum_m = [0.0] * 3, [0.0] * 3
    for i in range(steps):
        t = (i + 0.5) * ds
        p = tuple(o[k] + direction[k] * t for k in range(3))
        h = math.sqrt(sum(c * c for c in p)) - _R_EARTH
        d_r, d_m = math.exp(-h / _H_R) * ds, math.exp(-h / _H_M) * ds
        od_r += d_r
        od_m += d_m
        od_o += _ozone(h) * ds
        if _ray_sphere(p, sun_dir, _R_EARTH)[0] > 0:
            continue  # in the Earth's shadow
        lt = _ray_sphere(p, sun_dir, _R_ATMO)[1]
        lds = lt / light_steps
        l_r = l_m = l_o = 0.0
        for j in range(light_steps):
            q = tuple(p[k] + sun_dir[k] * (j + 0.5) * lds for k in range(3))
            lh = math.sqrt(sum(c * c for c in q)) - _R_EARTH
            l_r += math.exp(-lh / _H_R) * lds
            l_m += math.exp(-lh / _H_M) * lds
            l_o += _ozone(lh) * lds
        for c in range(3):
            tau = _BETA_R[c] * (od_r + l_r) + _BETA_O[c] * (od_o + l_o) + beta_m * 1.1 * (od_m + l_m)
            att = math.exp(-tau)
            sum_r[c] += att * d_r
            sum_m[c] += att * d_m
    mu = sum(direction[k] * sun_dir[k] for k in range(3))
    phase_r = 3 / (16 * math.pi) * (1 + mu * mu)
    gm = 0.76
    phase_m = 3 / (8 * math.pi) * ((1 - gm * gm) * (1 + mu * mu)) / ((2 + gm * gm) * (1 + gm * gm - 2 * gm * mu) ** 1.5)
    return tuple(_SUN_INTENSITY * (sum_r[c] * _BETA_R[c] * phase_r + sum_m[c] * beta_m * phase_m) for c in range(3))


def haze_color(view_dir):
    """Scene-linear haze colour when looking along `view_dir` (Z-up). Aerial haze gathers light
    from the whole sky, so it blends the horizon straight ahead with the average horizon all the
    way round (app/lighting.js does the same)."""
    atmo = STATE["atmosphere"]
    el, az = math.radians(atmo["elevation"]), math.radians(atmo["azimuth"])
    sun = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))

    def horizon(a):
        return sky_radiance((math.sin(a) * 0.9995, math.cos(a) * 0.9995, 0.03), sun, atmo["haze"], 12, 6)

    ahead = horizon(math.atan2(view_dir[0], view_dir[1]))
    ring = [horizon(k * math.pi / 4) for k in range(8)]
    avg = tuple(sum(r[c] for r in ring) / 8 for c in range(3))
    return tuple((0.5 * ahead[c] + 0.5 * avg[c] + n) * SKY_SCALE
                 for c, n in enumerate((0.0006, 0.0012, 0.0028)))


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
