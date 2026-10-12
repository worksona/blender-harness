// Time of day and atmosphere for the viewer: the same model as harness/atmosphere.py.
//
// solarPosition / sunTransmittance / exposure and lamp tables mirror the Python side exactly, so a
// world looks the same in the Blender preview and here. The sky itself is a physically based
// single-scattering atmosphere (Rayleigh + Mie + ozone, with the Earth's shadow for twilight),
// baked into a small equirectangular texture whenever the sun or haze changes. That one texture
// feeds the sky dome, the ocean's reflections and the image-based lighting of every material.

// Keep identical to harness/atmosphere.py.
export const EXPOSURE_EV = [[-12, 6.5], [-8, 5.5], [-4, 3.8], [0, 1.5], [6, 0.4], [15, 0]];
export const LAMP_LEVEL = [[-6, 1], [-1, 0.85], [3, 0.35], [8, 0]];
export const LAMP_GAIN = 0.0015;
export const SUN_ZENITH = 5.0;
export const SKY_SCALE = 0.12;

export function lerpTable(x, table) {
  if (x <= table[0][0]) return table[0][1];
  for (let i = 1; i < table.length; i++) {
    const [x0, y0] = table[i - 1], [x1, y1] = table[i];
    if (x <= x1) return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
  }
  return table[table.length - 1][1];
}

const rad = Math.PI / 180;

/** [elevation, azimuth] in degrees for local solar time; azimuth is a compass bearing. */
export function solarPosition(hours, latitude = 45, day = 172) {
  const decl = 23.44 * rad * Math.sin(2 * Math.PI * (284 + day) / 365);
  const lat = latitude * rad;
  const ha = 15 * (hours - 12) * rad;
  const sinEl = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(ha);
  const el = Math.asin(Math.max(-1, Math.min(1, sinEl)));
  const az = Math.atan2(Math.sin(ha), Math.cos(ha) * Math.sin(lat) - Math.tan(decl) * Math.cos(lat));
  return [el / rad, ((az / rad) + 180 + 360) % 360];
}

/** RGB fraction of sunlight surviving the atmosphere (Rayleigh + aerosol extinction). */
export function sunTransmittance(elevation, haze) {
  const zen = 90 - Math.max(elevation, -2);
  const airmass = 1 / (Math.cos(Math.min(zen, 90) * rad) + 0.50572 * (96.07995 - Math.min(zen, 92)) ** -1.6364);
  const rayleigh = [0.0397, 0.0975, 0.243];
  const beta = 0.02 + 0.28 * haze;
  const aerosol = [0.68, 0.55, 0.44].map((l) => beta * l ** -1.3);
  return rayleigh.map((r, i) => Math.exp(-airmass * (r + aerosol[i])));
}

/** Everything the renderer needs for one time of day. Mirrors atmosphere() in Python. */
export function lightingFor(p) {
  const [elevation, bearing] = solarPosition(p.time, p.latitude, p.day);
  const azimuth = ((bearing - (p.north ?? 0)) % 360 + 360) % 360;
  const t = sunTransmittance(elevation, p.haze);
  const peak = Math.max(...t);
  const fade = Math.max(0, Math.min(1, (elevation + 0.5) / 2));
  const lum = 0.2126 * t[0] + 0.7152 * t[1] + 0.0722 * t[2];
  const lamps = p.lamps === 'on' ? 1 : p.lamps === 'off' ? 0
    : p.lamps === 'auto' || p.lamps === undefined ? lerpTable(elevation, LAMP_LEVEL) : Number(p.lamps);
  // Sun direction in viewer (Y-up) coordinates: Blender (x, y, z) -> (x, z, -y).
  const el = elevation * rad, az = azimuth * rad;
  const bx = Math.sin(az) * Math.cos(el), by = Math.cos(az) * Math.cos(el), bz = Math.sin(el);
  return {
    elevation, azimuth,
    sunDir: [bx, bz, -by],
    sunColor: t.map((c) => c / peak),
    sunStrength: SUN_ZENITH * lum / 0.8 * fade,
    ev: lerpTable(elevation, EXPOSURE_EV) + (p.exposure ?? 0),
    lampLevel: lamps,
    visibility: p.visibility ?? 60000 * (1 - p.haze) ** 2 + 4000,
  };
}

// ---------------------------------------------------------------- physical sky

const R_EARTH = 6360e3, R_ATMO = 6420e3, H_R = 8000, H_M = 1200;
const BETA_R = [5.802e-6, 13.558e-6, 33.1e-6];
// Ozone (Chappuis band: absorbs orange-red about as much as green). Stronger than single-scattering
// physics alone would use: it stands in for the multiple scattering that keeps twilight blue.
const BETA_O = [3.0e-6, 2.6e-6, 0.2e-6];
const SUN_INTENSITY = 300;  // calibrated against Blender's multiple-scattering sky (5-20% match)
// Ozone lives in a layer around 25 km; it absorbs orange light on the long twilight paths,
// which is what keeps the twilight zenith blue.
const ozone = (h) => Math.max(0, 1 - Math.abs(h - 25000) / 15000);

function raySphere(ox, oy, oz, dx, dy, dz, r) {
  const b = ox * dx + oy * dy + oz * dz;
  const c = ox * ox + oy * oy + oz * oz - r * r;
  const disc = b * b - c;
  if (disc < 0) return [-1, -1];
  const s = Math.sqrt(disc);
  return [-b - s, -b + s];
}

/** Sky radiance (scene-referred, before SKY_SCALE) looking along unit `dir` (Y-up). */
export function skyRadiance(dir, sun, haze, steps = 12, lightSteps = 6) {
  const [dx, dy, dz] = dir;
  const oy = R_EARTH + 50;
  let tMax = raySphere(0, oy, 0, dx, dy, dz, R_ATMO)[1];
  const g = raySphere(0, oy, 0, dx, dy, dz, R_EARTH);
  if (g[0] > 0) tMax = Math.min(tMax, g[0]);
  const betaM = 3.996e-6 * (1 + haze * 9);
  const ds = tMax / steps;
  let odR = 0, odM = 0, odO = 0;
  const sumR = [0, 0, 0], sumM = [0, 0, 0];
  for (let i = 0; i < steps; i++) {
    const t = (i + 0.5) * ds;
    const px = dx * t, py = oy + dy * t, pz = dz * t;
    const h = Math.sqrt(px * px + py * py + pz * pz) - R_EARTH;
    const dR = Math.exp(-h / H_R) * ds, dM = Math.exp(-h / H_M) * ds;
    odR += dR; odM += dM; odO += ozone(h) * ds;
    // Light from the sun to this point; skip if the Earth is in the way (twilight shadow).
    const ge = raySphere(px, py, pz, sun[0], sun[1], sun[2], R_EARTH);
    if (ge[0] > 0) continue;
    const lt = raySphere(px, py, pz, sun[0], sun[1], sun[2], R_ATMO)[1];
    const lds = lt / lightSteps;
    let lR = 0, lM = 0, lO = 0;
    for (let j = 0; j < lightSteps; j++) {
      const s = (j + 0.5) * lds;
      const qx = px + sun[0] * s, qy = py + sun[1] * s, qz = pz + sun[2] * s;
      const lh = Math.sqrt(qx * qx + qy * qy + qz * qz) - R_EARTH;
      lR += Math.exp(-lh / H_R) * lds;
      lM += Math.exp(-lh / H_M) * lds;
      lO += ozone(lh) * lds;
    }
    for (let c = 0; c < 3; c++) {
      const tau = BETA_R[c] * (odR + lR) + BETA_O[c] * (odO + lO) + betaM * 1.1 * (odM + lM);
      const att = Math.exp(-tau);
      sumR[c] += att * dR;
      sumM[c] += att * dM;
    }
  }
  const mu = dx * sun[0] + dy * sun[1] + dz * sun[2];
  const phaseR = 3 / (16 * Math.PI) * (1 + mu * mu);
  const gM = 0.76;
  const phaseM = 3 / (8 * Math.PI) * ((1 - gM * gM) * (1 + mu * mu)) /
    ((2 + gM * gM) * (1 + gM * gM - 2 * gM * mu) ** 1.5);
  return [0, 1, 2].map((c) => SUN_INTENSITY * (sumR[c] * BETA_R[c] * phaseR + sumM[c] * betaM * phaseM));
}

const NIGHT_FLOOR = [0.0006, 0.0012, 0.0028];

/**
 * Bake the sky into a Float32 RGBA equirectangular image (width x height, row 0 = straight down).
 * Below the horizon is filled with a dim ground bounce of the horizon colour.
 */
export function bakeSky(sun, haze, width = 128, height = 64) {
  const data = new Float32Array(width * height * 4);
  const horizonRow = Math.floor(height / 2);
  for (let y = horizonRow; y < height; y++) {
    const el = ((y + 0.5) / height - 0.5) * Math.PI;
    const ce = Math.cos(el), se = Math.sin(el);
    for (let x = 0; x < width; x++) {
      const az = ((x + 0.5) / width - 0.5) * 2 * Math.PI;
      const dir = [Math.cos(az) * ce, se, Math.sin(az) * ce];
      const rgb = skyRadiance(dir, sun, haze, y === horizonRow ? 16 : 10, 5);
      const o = (y * width + x) * 4;
      for (let c = 0; c < 3; c++) data[o + c] = rgb[c] + NIGHT_FLOOR[c];
      data[o + 3] = 1;
    }
  }
  for (let y = 0; y < horizonRow; y++) {
    const k = 0.25 * (y / horizonRow) ** 2 + 0.05;
    for (let x = 0; x < width; x++) {
      const src = (horizonRow * width + x) * 4, o = (y * width + x) * 4;
      for (let c = 0; c < 3; c++) data[o + c] = data[src + c] * k;
      data[o + 3] = 1;
    }
  }
  return data;
}

/** Look up the baked sky for a Y-up direction (nearest texel). */
export function sampleSky(data, width, height, dir) {
  const u = Math.atan2(dir[2], dir[0]) / (2 * Math.PI) + 0.5;
  const v = Math.asin(Math.max(-1, Math.min(1, dir[1]))) / Math.PI + 0.5;
  const x = Math.min(width - 1, Math.max(0, Math.floor(u * width)));
  const y = Math.min(height - 1, Math.max(0, Math.floor(v * height)));
  const o = (y * width + x) * 4;
  return [data[o], data[o + 1], data[o + 2]];
}
