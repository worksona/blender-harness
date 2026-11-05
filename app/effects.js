// Night lighting and steam for worlds that use harness lamp() / plume().
//
// Lamps:  every lamp gets a camera-facing halo (additive, one draw call for all of them), and lamps
//         near the ground get a pool of light on the ground, so lots of lights cost almost nothing.
// Plumes: animated soft particles that rise, grow, drift with the wind and fade; colored warm near
//         the source (lit by the plant) and cool up high (lit by the sky).
import * as THREE from 'three';

const NOISE_GLSL = /* glsl */ `
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) {
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; }
  return s;
}
`;

/** Camera-facing quad per instance; `size` is in world meters. */
function billboardGeometry(count, attributes) {
  const geo = new THREE.InstancedBufferGeometry();
  const quad = new THREE.PlaneGeometry(1, 1);
  geo.index = quad.index;
  geo.setAttribute('position', quad.getAttribute('position'));
  for (const [name, size, data] of attributes) {
    geo.setAttribute(name, new THREE.InstancedBufferAttribute(data, size));
  }
  geo.instanceCount = count;
  return geo;
}

const LIVE_LIGHTS = 8;

export class Lamps {
  constructor(lamps) {
    this.lamps = lamps;
    this.group = new THREE.Group();
    this.group.name = 'Lamps';
    // A fixed set of real point lights, moved to the lamps nearest the view so nearby structures
    // get lit (a constant light count avoids shader recompiles).
    this.live = Array.from({ length: Math.min(LIVE_LIGHTS, lamps.length) }, () => {
      const light = new THREE.PointLight(0xffffff, 0, 0, 2);
      this.group.add(light);
      return light;
    });
    this._focus = new THREE.Vector3(Infinity, 0, 0);
    const n = lamps.length;
    const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n);
    const pools = lamps.filter((l) => l[5] !== null && l[5] !== undefined);
    const ppos = new Float32Array(pools.length * 3), pcol = new Float32Array(pools.length * 3),
      psize = new Float32Array(pools.length);
    const c = new THREE.Color();
    lamps.forEach((l, i) => {
      pos.set([l[0], l[1], l[2]], i * 3);
      c.set(l[3]);
      col.set([c.r, c.g, c.b], i * 3);
      size[i] = 0.5 + Math.sqrt(l[4]) * 0.018;           // halo diameter grows gently with power
    });
    pools.forEach((l, i) => {
      const h = Math.max(l[1] - l[5], 1);
      ppos.set([l[0], l[5] + 0.08, l[2]], i * 3);
      c.set(l[3]);
      const k = l[4] / (4 * Math.PI * h * h) * 0.375;   // irradiance under the lamp x ground albedo
      pcol.set([c.r * k, c.g * k, c.b * k], i * 3);
      psize[i] = h * 2.6 + 6;                             // light cone footprint on the ground
    });

    const halo = new THREE.Mesh(
      billboardGeometry(n, [['aPos', 3, pos], ['aColor', 3, col], ['aSize', 1, size]]),
      new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
        uniforms: { uGain: { value: 1 } },
        vertexShader: /* glsl */ `
          attribute vec3 aPos; attribute vec3 aColor; attribute float aSize;
          varying vec2 vUv; varying vec3 vColor; varying float vFade;
          void main() {
            vec3 right = vec3(viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0]);
            vec3 up = vec3(viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1]);
            vec4 mv = viewMatrix * vec4(aPos, 1.0);
            // Keep far lights visible as small sparkles instead of shrinking to nothing.
            float dist = -mv.z;
            float s = max(aSize, dist * 0.0025);
            vec3 world = aPos + (right * position.x + up * position.y) * s;
            vUv = position.xy;
            vColor = aColor;
            vFade = 1.0 - smoothstep(4000.0, 9000.0, dist);
            gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
          }`,
        fragmentShader: /* glsl */ `
          uniform float uGain;
          varying vec2 vUv; varying vec3 vColor; varying float vFade;
          void main() {
            float d = length(vUv) * 2.0;
            float core = exp(-d * d * 30.0) * 2.0;
            float glow = exp(-d * 5.0) * 0.35;
            float a = (core + glow) * (1.0 - smoothstep(0.7, 1.0, d)) * vFade * uGain;
            gl_FragColor = vec4(vColor * a, a);
          }`,
      }),
    );
    halo.frustumCulled = false;
    this.halo = halo;
    this.scale = 1;   // lamp level x gain: watts -> scene units
    halo.renderOrder = 2;
    this.group.add(halo);

    if (pools.length) {
      const pool = new THREE.Mesh(
        billboardGeometry(pools.length, [['aPos', 3, ppos], ['aColor', 3, pcol], ['aSize', 1, psize]]),
        new THREE.ShaderMaterial({
          transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: true,
          polygonOffset: true, polygonOffsetFactor: -4,
          uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, { uGain: { value: 1 } }]),
          vertexShader: /* glsl */ `
            attribute vec3 aPos; attribute vec3 aColor; attribute float aSize;
            varying vec2 vUv; varying vec3 vColor;
            #include <fog_pars_vertex>
            void main() {
              vec3 world = aPos + vec3(position.x, 0.0, -position.y) * aSize;
              vUv = position.xy; vColor = aColor;
              vec4 mvPosition = viewMatrix * vec4(world, 1.0);
              gl_Position = projectionMatrix * mvPosition;
              #include <fog_vertex>
            }`,
          fragmentShader: /* glsl */ `
            uniform float uGain;
            varying vec2 vUv; varying vec3 vColor;
            #include <fog_pars_fragment>
            void main() {
              float d = length(vUv) * 2.0;
              float a = pow(max(1.0 - d, 0.0), 2.2) * uGain;
              gl_FragColor = vec4(vColor * a, a);
              #include <fog_fragment>
            }`,
        }),
      );
      pool.frustumCulled = false;
      pool.renderOrder = 1;
      this.group.add(pool);
      this.pool = pool;
    }
  }

  /** level: 0 (off) .. 1. gain: watts -> scene units (1 for authored worlds, LAMP_GAIN for the
   *  physical sky). exposure: current exposure scale; halos are divided by it so they look the
   *  same at noon and at night. */
  setLevel(level, gain, exposure) {
    this.scale = level * gain;
    this.halo.material.uniforms.uGain.value = 2.5 * level / exposure;
    if (this.pool) this.pool.material.uniforms.uGain.value = this.scale;
    this._focus.set(Infinity, 0, 0);   // re-light the live point lights
  }

  /** Re-target the live point lights at the lamps nearest `focus` (call when the view moves). */
  update(focus) {
    if (!this.live.length || this._focus.distanceToSquared(focus) < 400) return;
    this._focus.copy(focus);
    const near = this.lamps
      .map((l, i) => [(l[0] - focus.x) ** 2 + (l[1] - focus.y) ** 2 + (l[2] - focus.z) ** 2, i])
      .sort((a, b) => a[0] - b[0])
      .slice(0, this.live.length);
    near.forEach(([, i], k) => {
      const l = this.lamps[i];
      const light = this.live[k];
      light.position.set(l[0], l[1], l[2]);
      light.color.set(l[3]);
      light.intensity = 0.06 * l[4] * this.scale;   // Blender watts -> three.js candela (as the sun)
    });
  }
}

const PER_PLUME = 160;

export class Plumes {
  constructor(plumes, fogUniforms) {
    const n = plumes.length * PER_PLUME;
    const base = new Float32Array(n * 3), shape = new Float32Array(n * 4), drift = new Float32Array(n * 3),
      low = new Float32Array(n * 3), high = new Float32Array(n * 3), albedo = new Float32Array(n);
    const c = new THREE.Color();
    let i = 0;
    for (const p of plumes) {
      for (let k = 0; k < PER_PLUME; k++, i++) {
        base.set(p.base, i * 3);
        shape.set([p.height, p.radius, k / PER_PLUME + (p.seed ?? 0) * 0.137, Math.min(1, p.density * 2.5)], i * 4);
        drift.set([p.drift[0], p.drift[1], p.rise ?? 4], i * 3);
        c.set(p.low).multiplyScalar(p.glow ?? 1); low.set([c.r, c.g, c.b], i * 3);
        c.set(p.high); high.set([c.r, c.g, c.b], i * 3);
        albedo[i] = p.albedo ?? 1;
      }
    }
    this.uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uTime: { value: 0 }, uLight: { value: 1 }, uAuthored: { value: 1 },
      uAmbient: { value: new THREE.Color() }, uSunCol: { value: new THREE.Color() }, uGlowAmt: { value: 0 },
    }]);
    this.mesh = new THREE.Mesh(
      billboardGeometry(n, [['aBase', 3, base], ['aShape', 4, shape], ['aDrift', 3, drift],
        ['aLow', 3, low], ['aHigh', 3, high], ['aAlbedo', 1, albedo]]),
      new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, fog: true, uniforms: this.uniforms,
        vertexShader: /* glsl */ `
          attribute vec3 aBase; attribute vec4 aShape; attribute vec3 aDrift; attribute vec3 aLow; attribute vec3 aHigh;
          attribute float aAlbedo;
          uniform float uTime;
          varying vec2 vUv; varying float vAge; varying vec3 vColor; varying float vDensity; varying float vSeed;
          varying vec3 vLow; varying float vAlbedo;
          #include <fog_pars_vertex>
          void main() {
            float height = aShape.x, radius = aShape.y, seed = aShape.z;
            // Each particle loops through the plume; travel time = height / rise speed.
            float age = fract(uTime * aDrift.z / height + seed);
            float t = pow(age, 0.85);
            vec3 c = aBase + vec3(0.0, t * height, 0.0)
                   + vec3(aDrift.x, 0.0, aDrift.y) * pow(t, 1.4) * height;
            float swirl = seed * 91.7;
            c.x += sin(swirl + uTime * 0.21 + t * 7.0) * radius * 0.9 * t;
            c.z += cos(swirl * 1.3 + uTime * 0.17 + t * 5.0) * radius * 0.9 * t;
            float size = radius * (1.1 + t * 4.2) * (0.6 + 0.7 * fract(seed * 7.31));
            vec3 right = vec3(viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0]);
            vec3 up = vec3(viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1]);
            float a = swirl + uTime * 0.04 * (fract(seed * 3.7) - 0.5);
            vec2 q = mat2(cos(a), -sin(a), sin(a), cos(a)) * position.xy;
            vec3 world = c + (right * q.x + up * q.y) * size;
            vUv = position.xy + 0.5;
            vAge = age; vSeed = seed; vDensity = aShape.w;
            vColor = mix(aLow, aHigh, smoothstep(0.0, 0.55, t));
            vLow = aLow; vAlbedo = aAlbedo;
            vec4 mvPosition = viewMatrix * vec4(world, 1.0);
            gl_Position = projectionMatrix * mvPosition;
            #include <fog_vertex>
          }`,
        fragmentShader: /* glsl */ `
          ${NOISE_GLSL}
          uniform float uLight; uniform float uAuthored; uniform vec3 uAmbient; uniform vec3 uSunCol;
          uniform float uGlowAmt;
          varying vec2 vUv; varying float vAge; varying vec3 vColor; varying float vDensity; varying float vSeed;
          varying vec3 vLow; varying float vAlbedo;
          #include <fog_pars_fragment>
          void main() {
            vec2 p = vUv - 0.5;
            float d = length(p) * 2.0;
            float n = fbm(vUv * 3.2 + vSeed * 17.0);
            float puff = smoothstep(1.0, 0.25, d + (n - 0.5) * 1.2);
            float life = smoothstep(0.0, 0.06, vAge) * (1.0 - smoothstep(0.35, 1.0, vAge));
            // Dark smoke (low albedo) is more opaque than steam of the same density.
            float a = min(1.0, puff * puff * life * vDensity * 0.4 * (1.0 + 2.6 * (1.0 - vAlbedo)));
            vec3 col = uAuthored > 0.5
              ? vColor * uLight * (0.6 + 0.8 * n)
              // Lit by the sky and sun, plus the plant's lights glowing up into the lower plume.
              : (uAmbient * (0.7 + 0.6 * n) + uSunCol * (0.4 + 0.6 * n)) * vAlbedo
                + vLow * uGlowAmt * (1.0 - smoothstep(0.0, 0.6, vAge));
            gl_FragColor = vec4(col, a);
            #include <tonemapping_fragment>
            #include <colorspace_fragment>
            #include <fog_fragment>
          }`,
      }),
    );
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 3;
    this.mesh.name = 'Plumes';
  }

  update(time) {
    this.uniforms.uTime.value = time;
  }

  /** ambient/sunColor: scene-referred RGB from the physical sky, or null for authored colours. */
  setLight({ ambient, sunColor, glow }) {
    const u = this.uniforms;
    u.uAuthored.value = ambient ? 0 : 1;
    if (ambient) {
      // Steam scatters the whole sky: mostly its brightness, only a hint of its colour.
      const lum = 0.2126 * ambient[0] + 0.7152 * ambient[1] + 0.0722 * ambient[2];
      u.uAmbient.value.setRGB(...ambient.map((c) => lum * 0.8 + c * 0.2));
      u.uSunCol.value.setRGB(...sunColor);
      u.uGlowAmt.value = glow;
    }
  }
}

const PER_FIRE = 110, PER_FLASH = 36;

/** Fires and muzzle flashes (harness fire() / muzzle_flash()): additive flame particles plus a
 *  flickering point light each. Fires burn continuously; flashes fire every `period` seconds. */
export class Fires {
  constructor(fires) {
    this.fires = fires;
    this.group = new THREE.Group();
    this.group.name = 'Fires';
    const counts = fires.map((f) => (f.dir ? PER_FLASH : PER_FIRE));
    const n = counts.reduce((a, b) => a + b, 0);
    const base = new Float32Array(n * 3), dir = new Float32Array(n * 4), shape = new Float32Array(n * 4),
      col = new Float32Array(n * 3), core = new Float32Array(n * 3);
    const c = new THREE.Color();
    let i = 0;
    fires.forEach((f, fi) => {
      const d = f.dir ?? [0, 1, 0];
      for (let k = 0; k < counts[fi]; k++, i++) {
        base.set(f.base, i * 3);
        // w = period (0 for a continuous fire)
        dir.set([d[0], d[1], d[2], f.period ?? 0], i * 4);
        shape.set([f.height, f.radius, k / counts[fi] + (f.seed ?? 0) * 0.173, fi * 0.61 + (f.seed ?? 0) * 0.29], i * 4);
        c.set(f.color); col.set([c.r, c.g, c.b], i * 3);
        c.set(f.core); core.set([c.r, c.g, c.b], i * 3);
      }
    });
    this.uniforms = { uTime: { value: 0 }, uGain: { value: 1 } };
    this.mesh = new THREE.Mesh(
      billboardGeometry(n, [['aBase', 3, base], ['aDir', 4, dir], ['aShape', 4, shape], ['aColor', 3, col],
        ['aCore', 3, core]]),
      new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
        uniforms: this.uniforms,
        vertexShader: /* glsl */ `
          attribute vec3 aBase; attribute vec4 aDir; attribute vec4 aShape; attribute vec3 aColor; attribute vec3 aCore;
          uniform float uTime;
          varying vec2 vUv; varying vec3 vCol; varying float vHeat; varying float vSeed;
          float h1(float x) { return fract(sin(x * 91.345) * 47453.21); }
          void main() {
            float height = aShape.x, radius = aShape.y, seed = aShape.z, fseed = aShape.w;
            float period = aDir.w;
            vec3 c; float size; float heat;
            vec3 up = normalize(aDir.xyz);
            vec3 side = normalize(cross(up, abs(up.y) > 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0)));
            vec3 side2 = cross(up, side);
            float r1 = h1(seed * 13.1), r2 = h1(seed * 7.7 + 3.0), r3 = h1(seed * 3.3 + 9.0);
            if (period > 0.0) {
              // Muzzle flash: a burst every period seconds, gone in a fifth of a second.
              float phase = mod(uTime + fseed * period, period);
              float env = exp(-phase * 16.0) * step(0.0, phase);
              float along = pow(r1, 1.6);
              float spread = (1.0 - along) * 0.6 + 0.25;
              float ang = r2 * 6.2832;
              c = aBase + up * along * height * (0.7 + phase * 4.0)
                + (side * cos(ang) + side2 * sin(ang)) * radius * spread * r3;
              size = radius * (2.2 - along * 1.4) * env;
              heat = (1.0 - along * 0.7) * env;
            } else {
              // Flame: particles loop upward, quick and turbulent, shrinking and cooling as they rise.
              float age = fract(uTime * (0.9 + 0.5 * r1) / max(height * 0.35, 0.5) + seed);
              float ang = r2 * 6.2832 + uTime * (r3 - 0.5) * 2.0;
              float rad = radius * 0.8 * sqrt(r3) * (1.0 - age * 0.7);
              c = aBase + up * age * height
                + (side * cos(ang) + side2 * sin(ang)) * rad
                + side * sin(uTime * 5.0 + seed * 40.0) * 0.12 * radius * age;
              size = radius * (0.95 - age * 0.65) * (0.6 + 0.6 * r1);
              heat = (1.0 - age) * (0.75 + 0.25 * sin(uTime * 17.0 + seed * 60.0));
            }
            vec3 right = vec3(viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0]);
            vec3 vup = vec3(viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1]);
            // Flames are taller than wide; flash puffs stay round.
            float tall = period > 0.0 ? 1.0 : 1.7;
            vec3 world = c + (right * position.x + vup * position.y * tall) * size;
            vUv = position.xy + 0.5;
            vHeat = heat; vSeed = seed;
            vCol = mix(aColor * vec3(0.7, 0.2, 0.1), mix(aColor, aCore, smoothstep(0.6, 0.98, heat)), smoothstep(0.1, 0.55, heat));
            gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
          }`,
        fragmentShader: /* glsl */ `
          ${NOISE_GLSL}
          uniform float uGain;
          varying vec2 vUv; varying vec3 vCol; varying float vHeat; varying float vSeed;
          void main() {
            vec2 p = vUv - 0.5;
            float d = length(p) * 2.0;
            float n = fbm(vUv * 3.0 + vSeed * 23.0);
            float a = smoothstep(1.0, 0.1, d + (n - 0.5) * 1.3) * vHeat;
            if (a < 0.003) discard;
            gl_FragColor = vec4(vCol * uGain * a, a);
          }`,
      }),
    );
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 4;
    this.group.add(this.mesh);
    this.lights = fires.map((f) => {
      const l = new THREE.PointLight(new THREE.Color(f.color), 0, 0, 2);
      const d = f.dir ?? [0, 1, 0];
      const k = f.dir ? 0.3 : 0.35;
      l.position.set(f.base[0] + d[0] * f.height * k, f.base[1] + d[1] * f.height * k, f.base[2] + d[2] * f.height * k);
      this.group.add(l);
      return l;
    });
    this.scale = 1;
  }

  /** Fire burns whatever the lamp switch says; its light uses the lamps' watts-to-viewer gain. */
  setLevel(level, gain, exposure) {
    this.scale = gain;
    this.uniforms.uGain.value = 0.7 / exposure;
  }

  update(time) {
    this.uniforms.uTime.value = time;
    this.fires.forEach((f, i) => {
      let k;
      if (f.period) {
        const phase = (time + (i * 0.61 + (f.seed ?? 0) * 0.29) * f.period) % f.period;
        k = Math.exp(-phase * 16);
      } else {
        const s = (f.seed ?? 0) * 10 + i;
        k = 0.78 + 0.12 * Math.sin(time * 9.1 + s) + 0.07 * Math.sin(time * 23.7 + s * 2) + 0.05 * Math.sin(time * 3.3 + s);
      }
      this.lights[i].intensity = 0.06 * f.power * this.scale * k;
    });
  }
}

/** Falling snow around the view (harness snowfall()). */
export class Snowfall {
  constructor(opts) {
    const n = Math.round(9000 * (opts.rate ?? 1));
    const area = opts.area ?? 60;
    const pos = new Float32Array(n * 3), rnd = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      pos.set([(Math.random() - 0.5) * area, Math.random() * area * 0.5, (Math.random() - 0.5) * area], i * 3);
      rnd[i] = Math.random();
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('aRnd', new THREE.BufferAttribute(rnd, 1));
    this.uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uTime: { value: 0 }, uCenter: { value: new THREE.Vector3() }, uArea: { value: area },
      uWind: { value: new THREE.Vector3(opts.wind?.[0] ?? 0, -(opts.speed ?? 1), opts.wind?.[1] ?? 0) },
      uSize: { value: (opts.size ?? 0.025) }, uScale: { value: 800 }, uColor: { value: new THREE.Color(1, 1, 1) },
    }]);
    this.points = new THREE.Points(geo, new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, fog: true, uniforms: this.uniforms,
      vertexShader: /* glsl */ `
        attribute float aRnd;
        uniform float uTime; uniform vec3 uCenter; uniform float uArea; uniform vec3 uWind; uniform float uSize; uniform float uScale;
        varying float vA;
        #include <fog_pars_vertex>
        void main() {
          vec3 half_ = vec3(uArea * 0.5, uArea * 0.25, uArea * 0.5);
          vec3 p = position + uWind * uTime * (0.75 + 0.5 * aRnd);
          p.x += sin(uTime * (0.6 + aRnd) + aRnd * 30.0) * 0.4;
          p.z += cos(uTime * (0.5 + aRnd) + aRnd * 50.0) * 0.4;
          vec3 box = vec3(uArea, uArea * 0.5, uArea);
          p = mod(p - uCenter + half_, box) - half_ + uCenter;
          vec4 mvPosition = viewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mvPosition;
          gl_PointSize = clamp(uSize * (0.6 + 0.8 * aRnd) * uScale / -mvPosition.z, 1.0, 12.0);
          vA = smoothstep(1.5, 4.0, -mvPosition.z);
          #include <fog_vertex>
        }`,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor;
        varying float vA;
        #include <fog_pars_fragment>
        void main() {
          float d = length(gl_PointCoord - 0.5) * 2.0;
          float a = smoothstep(1.0, 0.2, d) * 0.85 * vA;
          if (a < 0.01) discard;
          gl_FragColor = vec4(uColor, a);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
          #include <fog_fragment>
        }`,
    }));
    this.points.frustumCulled = false;
    this.points.renderOrder = 5;
    this.points.name = 'Snowfall';
  }

  update(time, camera, target, height) {
    this.uniforms.uTime.value = time;
    // Center the snow box between the camera and what it looks at.
    this.uniforms.uCenter.value.copy(camera.position).lerp(target, 0.5);
    this.uniforms.uScale.value = height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
  }

  /** ambient: scene-referred sky light (physical sky) or null. */
  setLight({ ambient, sunColor }) {
    if (ambient) {
      const c = ambient.map((a, i) => a * 0.9 + sunColor[i] * 0.5);
      this.uniforms.uColor.value.setRGB(...c);
    } else {
      this.uniforms.uColor.value.setRGB(1, 1, 1);
    }
  }
}
