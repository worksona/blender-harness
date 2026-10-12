// Animated ocean for worlds that call ocean() in Blender.
//
// Geometry: a camera-following grid, dense near the viewer and coarse at the horizon, displaced
// by a sum of Gerstner waves (same parameters the harness writes to meta.json).
// Shading: sky reflection with Fresnel, sun glitter, sub-surface glow in backlit crests,
// refraction + depth absorption from a pre-pass of the scene without the water, crest foam
// where the waves fold, shoreline foam where the water is shallow.
import * as THREE from 'three';
import { SKY_GLSL, skyUniforms } from './sky.js';

const MAX_WAVES = 8;
const G = 9.81;

const vertexShader = /* glsl */ `
#define MAX_WAVES ${MAX_WAVES}
uniform float uTime;
uniform vec4 uWaves[MAX_WAVES];   // dir.x, dir.z, wavenumber k, steepness q
uniform int uWaveCount;
uniform float uLevel;
uniform vec2 uCenter;
uniform float uExtent;
varying vec3 vWorld;
varying vec3 vNormalW;
varying float vFold;
varying float vHeight;
varying float vViewZ;
#include <fog_pars_vertex>

vec3 gerstner(vec2 p, float fade, out vec3 normal, out float fold) {
  vec3 disp = vec3(0.0);
  vec3 T = vec3(1.0, 0.0, 0.0);
  vec3 B = vec3(0.0, 0.0, 1.0);
  float jxx = 1.0, jzz = 1.0, jxz = 0.0;
  for (int i = 0; i < MAX_WAVES; i++) {
    if (i >= uWaveCount) break;
    vec4 w = uWaves[i];
    vec2 d = w.xy;
    float k = w.z;
    float q = w.w * fade;
    float a = q / k;
    float f = k * dot(d, p) - sqrt(${G} * k) * uTime;
    float c = cos(f), s = sin(f);
    disp += vec3(d.x * a * c, a * s, d.y * a * c);
    T += vec3(-d.x * d.x * q * s, d.x * q * c, -d.x * d.y * q * s);
    B += vec3(-d.x * d.y * q * s, d.y * q * c, -d.y * d.y * q * s);
    jxx -= d.x * d.x * q * s;
    jzz -= d.y * d.y * q * s;
    jxz -= d.x * d.y * q * s;
  }
  normal = normalize(cross(B, T));
  fold = jxx * jzz - jxz * jxz;
  return disp;
}

void main() {
  // Warp the [-1, 1] grid so vertices bunch up under the camera.
  vec2 g = vec2(position.x, -position.y);
  vec2 warped = g * (0.02 + 0.98 * g * g);
  vec2 p = uCenter + warped * uExtent;
  float fade = 1.0 - smoothstep(500.0, 1800.0, length(warped * uExtent));
  vec3 n;
  float fold;
  vec3 disp = gerstner(p, fade, n, fold);
  vec3 world = vec3(p.x, uLevel, p.y) + disp;
  vWorld = world;
  vNormalW = n;
  vFold = fold;
  vHeight = disp.y;
  vec4 mvPosition = viewMatrix * vec4(world, 1.0);
  vViewZ = mvPosition.z;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}
`;

const fragmentShader = /* glsl */ `
uniform float uTime;
uniform sampler2D tScene;
uniform sampler2D tDepth;
uniform float uHasScene;
uniform vec2 uResolution;
uniform float uNear;
uniform float uFar;
uniform vec3 uDeep;
uniform vec3 uShallow;
uniform float uFoam;
uniform float uClarity;
uniform float uLight;
uniform float uMaxHeight;
varying vec3 vWorld;
varying vec3 vNormalW;
varying float vFold;
varying float vHeight;
varying float vViewZ;
#include <packing>
#include <fog_pars_fragment>
${SKY_GLSL}

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

// Short wind waves, evaluated per pixel: slope (dh/dx, dh/dz). Each wave fades out before it
// gets smaller than a pixel (no moire), and gusty patches modulate the whole field.
vec2 ripples(vec2 p, float t, float dist) {
  vec2 g = vec2(0.0);
  float lambda = 7.0;
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float ang = hash(vec2(fi, 1.7)) * 6.28318;
    vec2 d = vec2(cos(ang), sin(ang));
    float k = 6.28318 / lambda;
    float f = k * dot(d, p) - sqrt(${G} * k) * t + hash(vec2(fi, 3.1)) * 6.28;
    float fade = 1.0 - smoothstep(lambda * 25.0, lambda * 70.0, dist);
    g += d * 0.05 * cos(f) * fade;
    lambda *= 0.78;
  }
  float gust = vnoise(p * 0.018 + vec2(t * 0.03, -t * 0.02)) * 0.7
             + vnoise(p * 0.07 - vec2(t * 0.05, t * 0.04)) * 0.3;
  return g * (0.35 + 1.1 * gust);
}

void main() {
  float dist = length(cameraPosition - vWorld);
  vec2 rip = ripples(vWorld.xz, uTime, dist);
  vec3 N = normalize(vNormalW + vec3(-rip.x, 0.0, -rip.y));
  vec3 V = normalize(cameraPosition - vWorld);
  float NdV = max(dot(N, V), 0.0);
  float fresnel = 0.02 + 0.98 * pow(1.0 - NdV, 5.0);

  // Reflection of the same sky the dome draws.
  vec3 R = reflect(-V, N);
  R.y = abs(R.y);
  vec3 reflection = skyColor(normalize(R));

  // Sun glitter: a sharp lobe for sparkles, a wide one for the sheen path.
  vec3 H = normalize(V + uSunDir);
  float NdH = max(dot(N, H), 0.0);
  float sunUp = smoothstep(-0.03, 0.04, uSunDir.y);
  vec3 glitter = uSunColor * uSunStrength * sunUp * (pow(NdH, 900.0) * 60.0 + pow(NdH, 120.0) * 1.2);

  // What's under the surface: refracted scene, absorbed with depth.
  vec2 suv = gl_FragCoord.xy / uResolution;
  float waterZ = -vViewZ;
  float thickness = 1e4;
  vec3 below = uDeep * uLight;
  if (uHasScene > 0.5) {
    float sceneZ = -perspectiveDepthToViewZ(texture2D(tDepth, suv).x, uNear, uFar);
    thickness = max(sceneZ - waterZ, 0.0);
    vec2 ruv = suv + N.xz * 0.035 * clamp(thickness * 0.3, 0.0, 1.0);
    float refrZ = -perspectiveDepthToViewZ(texture2D(tDepth, ruv).x, uNear, uFar);
    if (refrZ < waterZ) ruv = suv;   // don't refract things that are in front of the water
    else thickness = max(refrZ - waterZ, 0.0);
    below = texture2D(tScene, ruv).rgb;
  }
  float clarity = max(uClarity, 0.05);
  vec3 absorb = exp(-thickness * vec3(0.42, 0.11, 0.08) / clarity);
  vec3 body = mix(uShallow * uLight * 0.4, uDeep * uLight * 0.8, 1.0 - exp(-thickness * 0.12 / clarity));
  vec3 water = below * absorb + body * (1.0 - absorb);

  // Light passing through thin wave crests when you look toward the sun.
  float crestH = clamp(vHeight / max(uMaxHeight, 0.01) * 0.6 + 0.4, 0.0, 1.0);
  float toward = pow(max(dot(normalize(vec3(-V.x, 0.0, -V.z)), normalize(vec3(uSunDir.x, 0.0, uSunDir.z))), 0.0), 3.0);
  vec3 sss = uShallow * uSunColor * uSunStrength * sunUp * crestH * crestH * (0.015 + 0.13 * toward) * (1.0 - fresnel);

  vec3 col = mix(water + sss, reflection, fresnel) + glitter;

  // Foam: crests where the surface folds over, and the shoreline.
  float crest = smoothstep(0.62, 0.2, vFold);
  float shore = 1.0 - smoothstep(0.0, 1.8, thickness);
  float shoreBands = 0.55 + 0.45 * sin(uTime * 1.6 - thickness * 5.0);
  float n = vnoise(vWorld.xz * 0.45 + vec2(uTime * 0.21, uTime * 0.13)) * 0.6
          + vnoise(vWorld.xz * 1.7 - vec2(uTime * 0.3, -uTime * 0.17)) * 0.4;
  float foamAmt = clamp(crest * 1.3 + shore * shoreBands, 0.0, 1.5) * uFoam;
  float foam = smoothstep(1.0 - foamAmt, 1.25 - foamAmt * 0.6, n) * (1.0 - smoothstep(150.0, 600.0, dist) * 0.7);
  vec3 foamCol = vec3(0.92, 0.95, 0.97) * (uLight * 0.7 + uSunColor * uSunStrength * max(uSunDir.y, 0.0) * 0.45);
  col = mix(col, foamCol, clamp(foam, 0.0, 1.0));

  gl_FragColor = vec4(col, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
  #include <fog_fragment>
}
`;

export class Ocean {
  constructor(params, { sunStrength = 1, sunElevation = 0.5, skyStrength = 1 } = {}) {
    this.params = params;
    this.waves = params.waves.slice(0, MAX_WAVES).map((w) => {
      const k = (2 * Math.PI) / w.wavelength;
      const [dx, dz] = w.direction;
      const len = Math.hypot(dx, dz) || 1;
      return { dx: dx / len, dz: dz / len, k, q: w.steepness, omega: Math.sqrt(G * k) };
    });
    const maxHeight = this.waves.reduce((s, w) => s + w.q / w.k, 0);
    const light = Math.min(1.0, 0.35 * skyStrength + 0.55 * sunStrength * Math.max(sunElevation, 0));
    this.authoredLight = light;

    this.uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uTime: { value: 0 },
      uWaves: { value: Array.from({ length: MAX_WAVES }, (_, i) => {
        const w = this.waves[i];
        return w ? new THREE.Vector4(w.dx, w.dz, w.k, w.q) : new THREE.Vector4();
      }) },
      uWaveCount: { value: this.waves.length },
      uLevel: { value: params.level },
      uCenter: { value: new THREE.Vector2() },
      uExtent: { value: 6000 },
      tScene: { value: null },
      tDepth: { value: null },
      uHasScene: { value: 0 },
      uResolution: { value: new THREE.Vector2(1, 1) },
      uNear: { value: 0.1 },
      uFar: { value: 1000 },
      uDeep: { value: new THREE.Color(params.color) },
      uShallow: { value: new THREE.Color(params.shallow) },
      uFoam: { value: params.foam ?? 0.6 },
      uClarity: { value: params.clarity ?? 1 },
      uLight: { value: light },
      uMaxHeight: { value: maxHeight },
    }]);
    // The sky uniforms are shared objects, so the ocean always reflects the current sky.
    Object.assign(this.uniforms, skyUniforms);

    const geometry = new THREE.PlaneGeometry(2, 2, 600, 600);
    this.mesh = new THREE.Mesh(geometry, new THREE.ShaderMaterial({
      uniforms: this.uniforms, vertexShader, fragmentShader, fog: true,
    }));
    this.mesh.frustumCulled = false;
    this.mesh.name = 'Ocean';
  }

  /** Brightness of the water body: a value from the physical sky, or null for the authored one. */
  setLight(level) {
    this.uniforms.uLight.value = level === null ? this.authoredLight : Math.min(1.2, level);
  }

  /** Called every frame, before rendering. */
  update(time, camera, prepass) {
    const u = this.uniforms;
    u.uTime.value = time;
    // Snap the grid's center to a fixed step so vertices don't crawl as the camera moves.
    const step = 8;
    u.uCenter.value.set(Math.round(camera.position.x / step) * step,
      Math.round(camera.position.z / step) * step);
    u.uNear.value = camera.near;
    u.uFar.value = camera.far;
    if (prepass) {
      u.tScene.value = prepass.texture;
      u.tDepth.value = prepass.depthTexture;
      u.uResolution.value.set(prepass.width, prepass.height);
      u.uHasScene.value = 1;
    }
  }

  /** Gerstner displacement and surface normal at undisplaced point (x, z). */
  sample(x, z, time) {
    let px = 0, py = 0, pz = 0;
    let tx = 1, ty = 0, tz = 0, bx = 0, by = 0, bz = 1;
    for (const w of this.waves) {
      const f = w.k * (w.dx * x + w.dz * z) - w.omega * time;
      const c = Math.cos(f), s = Math.sin(f), a = w.q / w.k;
      px += w.dx * a * c; py += a * s; pz += w.dz * a * c;
      tx -= w.dx * w.dx * w.q * s; ty += w.dx * w.q * c; tz -= w.dx * w.dz * w.q * s;
      bx -= w.dx * w.dz * w.q * s; by += w.dz * w.q * c; bz -= w.dz * w.dz * w.q * s;
    }
    const normal = new THREE.Vector3(by * tz - bz * ty, bz * tx - bx * tz, bx * ty - by * tx).normalize();
    return { dx: px, dy: py, dz: pz, normal };
  }

  /** Water height and normal at world (x, z): inverts the horizontal Gerstner displacement. */
  surfaceAt(x, z, time) {
    let sx = x, sz = z, s;
    for (let i = 0; i < 4; i++) {
      s = this.sample(sx, sz, time);
      sx = x - s.dx;
      sz = z - s.dz;
    }
    s = this.sample(sx, sz, time);
    return { y: this.params.level + s.dy, normal: s.normal };
  }
}

/** Make objects tagged with bob (via harness.bob()) ride the waves. */
export class Floaters {
  constructor(root, ocean) {
    this.ocean = ocean;
    this.items = [];
    const up = new THREE.Vector3(0, 1, 0);
    root.traverse((o) => {
      if (o.userData?.bob) {
        this.items.push({ o, amount: o.userData.bob, draft: o.userData.draft ?? 0,
          base: o.position.clone(), quat: o.quaternion.clone(), tilt: null });
      }
    });
    this._up = up;
    this._tilt = new THREE.Quaternion();
    this._n = new THREE.Vector3();
  }

  update(time) {
    // Ease toward the wave's tilt so hulls feel heavy instead of snapping to every ripple.
    const dt = Math.min(Math.max(time - (this._last ?? time), 0), 0.1);
    this._last = time;
    const ease = 1 - Math.exp(-dt * 3);
    for (const it of this.items) {
      const { o, base } = it;
      const s = this.ocean.surfaceAt(base.x, base.z, time);
      o.position.set(base.x, base.y + (s.y - this.ocean.params.level) * it.amount - it.draft, base.z);
      this._n.copy(this._up).lerp(s.normal, 0.5 * it.amount).normalize();
      this._tilt.setFromUnitVectors(this._up, this._n);
      it.tilt = it.tilt ? it.tilt.slerp(this._tilt, ease) : this._tilt.clone();
      o.quaternion.copy(it.tilt).multiply(it.quat);
    }
  }
}
