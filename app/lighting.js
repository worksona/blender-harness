// Lighting for the viewer: either the world's authored look (sun/sky/fog from meta.json), or the
// physical time-of-day model (atmosphere.js). One place drives every light-dependent thing:
// sky texture + image-based lighting, sun, exposure, haze colour, lamps, bulbs, steam, ocean.
import * as THREE from 'three';
import { bakeSky, LAMP_GAIN, lightingFor, sampleSky, SKY_SCALE, solarPosition } from './atmosphere.js';
import { skyUniforms } from './sky.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const SKY_W = 128, SKY_H = 64;
const rad = Math.PI / 180;

export const DEFAULTS = { time: 12, latitude: 45, day: 172, north: 0, haze: 0.3, exposure: 0, lamps: 'auto' };

export class Lighting {
  constructor({ renderer, scene, sun, hemi, onSunDir }) {
    Object.assign(this, { renderer, scene, sun, hemi, onSunDir });
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.skyData = new Float32Array(SKY_W * SKY_H * 4);          // CPU copy, for haze colour lookups
    this.skyHalf = new Uint16Array(SKY_W * SKY_H * 4);           // half floats filter on every GPU
    this.skyTex = new THREE.DataTexture(this.skyHalf, SKY_W, SKY_H, THREE.RGBAFormat, THREE.HalfFloatType);
    this.skyTex.mapping = THREE.EquirectangularReflectionMapping;
    this.skyTex.magFilter = this.skyTex.minFilter = THREE.LinearFilter;
    this.skyTex.wrapS = THREE.RepeatWrapping;
    skyUniforms.uSkyTex.value = this.skyTex;
    this.envRT = null;
    this.params = null;      // physical-mode parameters, or null for the authored look
    this.defaults = null;    // the world's own atmosphere() parameters, if it has them
    this.state = null;       // last lightingFor() result
    this.dirty = false;
    this.world = null;
    this._fogDir = [0, 0, 1];
    this._v = new THREE.Vector3();
  }

  /** New world loaded. parts: { meta, root, ocean, lamps, plumes }. */
  setWorld(parts) {
    this.world = parts;
    const a = parts.meta.viewer.atmosphere;
    this.defaults = a ? { time: a.time, latitude: a.latitude, day: a.day, north: a.north, haze: a.haze,
      visibility: a.visibility, exposure: a.exposure ?? 0, lamps: a.lamps ?? 'auto' } : null;
    this.params = this.defaults ? { ...this.defaults } : null;
    // Remember each bulb material's authored glow so the lamp level can scale it.
    parts.root.traverse((o) => {
      for (const m of [].concat(o.material || [])) {
        if (m.name?.startsWith('bulb_') && m.userData.baseGlow === undefined) {
          m.userData.baseGlow = Math.min(m.emissiveIntensity ?? 1, 8);
        }
      }
    });
    this.apply();
  }

  get physical() { return this.params !== null; }

  /** Change physical parameters (switches an authored world to the physical model). */
  set(partial) {
    if (!this.params) this.params = { ...this.fromAuthored(), ...partial };
    else Object.assign(this.params, partial);
    this.dirty = true;
  }

  /** Back to the world's own lighting. */
  reset() {
    this.params = this.defaults ? { ...this.defaults } : null;
    this.dirty = true;
  }

  /** Physical parameters that roughly reproduce an authored world's sun direction. */
  fromAuthored() {
    const v = this.world.meta.viewer;
    const [x, y, z] = v.sun.direction;
    const elev = Math.asin(Math.max(-1, Math.min(1, y))) / rad;
    const bearing = (Math.atan2(x, -z) / rad + 360) % 360;
    let best = 12, err = Infinity;
    for (let h = 4; h <= 12; h += 0.05) {   // morning hour with the same sun height
      const e = Math.abs(solarPosition(h, DEFAULTS.latitude, DEFAULTS.day)[0] - elev);
      if (e < err) { err = e; best = h; }
    }
    const solarBearing = solarPosition(best, DEFAULTS.latitude, DEFAULTS.day)[1];
    return { ...DEFAULTS, time: +best.toFixed(2), north: (solarBearing - bearing + 360) % 360 };
  }

  /** Call once per frame (cheap unless something changed). */
  update(camera) {
    if (this.dirty) { this.dirty = false; this.apply(); }
    if (!this.physical || !this.scene.fog) return;
    // Haze takes the colour of the sky near the horizon in the direction you're looking.
    // ...blended with the average horizon all round, as aerial haze gathers light from the
    // whole sky (harness/atmosphere.py haze_color does the same).
    camera.getWorldDirection(this._v);
    const h = Math.hypot(this._v.x, this._v.z) || 1;
    const c = sampleSky(this.skyData, SKY_W, SKY_H, [this._v.x / h, 0.03, this._v.z / h]);
    const a = this.horizonAvg;
    this.scene.fog.color.setRGB((c[0] + a[0]) * 0.5 * SKY_SCALE, (c[1] + a[1]) * 0.5 * SKY_SCALE,
      (c[2] + a[2]) * 0.5 * SKY_SCALE);
  }

  apply() {
    if (!this.world) return;
    if (this.physical) this.applyPhysical(); else this.applyAuthored();
    this.applyInterior();
  }

  /** Indoor worlds (META interior()): overhead key light, room reflections, floor bounce. */
  applyInterior() {
    const I = this.world.meta.viewer.interior;
    if (!I) return;
    if (!this.roomEnv) this.roomEnv = this.pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environment = this.roomEnv;
    this.scene.environmentIntensity = I.env;
    this.hemi.color.set(I.sky);
    this.hemi.groundColor.set(I.ground);
    this.hemi.intensity = I.ambient;
    // Authored: the directional light is the overhead key and the roof lets it through.
    // Physical: it is the real sun, so the roof shades the floor except at doors and windows.
    const physical = this.physical;
    if (!physical) {
      this.sun.color.set(I.key_color);
      this.sun.intensity = I.key;
      this.onSunDir(I.key_dir);
      this.renderer.toneMappingExposure = I.exposure;
      this.scene.fog = null;
    }
    this.world.root.traverse((o) => { if (o.userData.no_cast) o.castShadow = physical; });
  }

  applyAuthored() {
    const v = this.world.meta.viewer;
    const fogColor = new THREE.Color(v.fog.color);
    this.scene.fog = new THREE.Fog(fogColor, v.fog.near, v.fog.far);
    this.scene.environment = null;
    skyUniforms.uPhysical.value = 0;
    skyUniforms.uSkyTop.value.set(v.sky.color);
    skyUniforms.uSkyHorizon.value.copy(fogColor);
    skyUniforms.uSunDir.value.set(...v.sun.direction).normalize();
    skyUniforms.uSunColor.value.set(v.sun.color);
    skyUniforms.uSunStrength.value = v.sun.strength;
    skyUniforms.uGlow.value = v.sky.glow ?? v.sun.strength * 0.25;
    skyUniforms.uGlowHeight.value = v.sky.glow_height ?? 0.5;
    this.hemi.color.set(v.sky.color);
    this.hemi.groundColor.set(v.sky.ground);
    this.hemi.intensity = 1.4 * v.sky.strength;
    this.sun.color.set(v.sun.color);
    this.sun.intensity = 0.75 * v.sun.strength;
    this.onSunDir(v.sun.direction);
    const exposure = v.exposure ?? 1;
    this.renderer.toneMappingExposure = exposure;
    this.state = null;
    this.applyToParts({ lampLevel: 1, gain: 1, exposure, ambient: null, sunColor: null });
  }

  applyPhysical() {
    const p = this.params;
    const L = lightingFor(p);
    this.state = L;
    // Bake the sky for this sun and haze; it lights the dome, the ocean and every material.
    this.skyData.set(bakeSky(L.sunDir, p.haze, SKY_W, SKY_H));
    for (let i = 0; i < this.skyData.length; i++) this.skyHalf[i] = THREE.DataUtils.toHalfFloat(this.skyData[i]);
    this.horizonAvg = [0, 0, 0];
    for (let k = 0; k < 8; k++) {
      const s = sampleSky(this.skyData, SKY_W, SKY_H, [Math.cos(k * Math.PI / 4), 0.03, Math.sin(k * Math.PI / 4)]);
      for (let c = 0; c < 3; c++) this.horizonAvg[c] += s[c] / 8;
    }
    this.skyTex.needsUpdate = true;
    this.envRT?.dispose();
    this.envRT = this.pmrem.fromEquirectangular(this.skyTex);
    this.scene.environment = this.envRT.texture;
    this.scene.environmentIntensity = SKY_SCALE;
    this.hemi.intensity = 0;

    skyUniforms.uPhysical.value = 1;
    skyUniforms.uSkyScale.value = SKY_SCALE;
    skyUniforms.uSunDir.value.set(...L.sunDir).normalize();
    skyUniforms.uSunColor.value.setRGB(...L.sunColor);
    skyUniforms.uSunStrength.value = L.sunStrength;
    this.sun.color.setRGB(...L.sunColor);
    this.sun.intensity = 0.75 * L.sunStrength;
    this.onSunDir(L.sunDir);

    const vis = L.visibility;
    this.scene.fog = new THREE.Fog(new THREE.Color(0, 0, 0), vis * 0.05, vis);
    const exposure = 2 ** L.ev * (this.world.meta.viewer.exposure ?? 1);
    this.renderer.toneMappingExposure = exposure;

    const zen = sampleSky(this.skyData, SKY_W, SKY_H, [0, 1, 0]);
    const ambient = zen.map((c) => c * SKY_SCALE * 2.2);
    const sunColor = L.sunColor.map((c) => c * L.sunStrength * 0.18);
    this.applyToParts({ lampLevel: L.lampLevel, gain: LAMP_GAIN, exposure, ambient, sunColor });
  }

  applyToParts({ lampLevel, gain, exposure, ambient, sunColor }) {
    const { lamps, plumes, ocean, root } = this.world;
    lamps?.setLevel(lampLevel, gain, exposure);
    plumes?.setLight({ ambient, sunColor, glow: lampLevel * 0.004 });
    if (ocean) {
      const lum = ambient ? (0.2126 * ambient[0] + 0.7152 * ambient[1] + 0.0722 * ambient[2]) * 3 +
        0.1 * this.sun.intensity : null;
      ocean.setLight(lum);
    }
    root.traverse((o) => {
      for (const m of [].concat(o.material || [])) {
        if (m.userData.baseGlow !== undefined) m.emissiveIntensity = m.userData.baseGlow * lampLevel / exposure;
      }
    });
  }

  /** Readout for the UI. */
  describe() {
    const L = this.state;
    if (!L) return 'Authored lighting';
    const sunTxt = L.elevation > 0 ? `sun ${L.elevation.toFixed(0)}° up` : `sun ${(-L.elevation).toFixed(0)}° below`;
    return `${sunTxt} · EV ${L.ev.toFixed(1)} · lamps ${Math.round(L.lampLevel * 100)}%`;
  }
}
