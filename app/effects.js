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
      low = new Float32Array(n * 3), high = new Float32Array(n * 3);
    const c = new THREE.Color();
    let i = 0;
    for (const p of plumes) {
      for (let k = 0; k < PER_PLUME; k++, i++) {
        base.set(p.base, i * 3);
        shape.set([p.height, p.radius, k / PER_PLUME + (p.seed ?? 0) * 0.137, Math.min(1, p.density * 2.5)], i * 4);
        drift.set([p.drift[0], p.drift[1], p.rise ?? 4], i * 3);
        c.set(p.low); low.set([c.r, c.g, c.b], i * 3);
        c.set(p.high); high.set([c.r, c.g, c.b], i * 3);
      }
    }
    this.uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uTime: { value: 0 }, uLight: { value: 1 }, uAuthored: { value: 1 },
      uAmbient: { value: new THREE.Color() }, uSunCol: { value: new THREE.Color() }, uGlowAmt: { value: 0 },
    }]);
    this.mesh = new THREE.Mesh(
      billboardGeometry(n, [['aBase', 3, base], ['aShape', 4, shape], ['aDrift', 3, drift],
        ['aLow', 3, low], ['aHigh', 3, high]]),
      new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, fog: true, uniforms: this.uniforms,
        vertexShader: /* glsl */ `
          attribute vec3 aBase; attribute vec4 aShape; attribute vec3 aDrift; attribute vec3 aLow; attribute vec3 aHigh;
          uniform float uTime;
          varying vec2 vUv; varying float vAge; varying vec3 vColor; varying float vDensity; varying float vSeed;
          varying vec3 vLow;
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
            vLow = aLow;
            vec4 mvPosition = viewMatrix * vec4(world, 1.0);
            gl_Position = projectionMatrix * mvPosition;
            #include <fog_vertex>
          }`,
        fragmentShader: /* glsl */ `
          ${NOISE_GLSL}
          uniform float uLight; uniform float uAuthored; uniform vec3 uAmbient; uniform vec3 uSunCol;
          uniform float uGlowAmt;
          varying vec2 vUv; varying float vAge; varying vec3 vColor; varying float vDensity; varying float vSeed;
          varying vec3 vLow;
          #include <fog_pars_fragment>
          void main() {
            vec2 p = vUv - 0.5;
            float d = length(p) * 2.0;
            float n = fbm(vUv * 3.2 + vSeed * 17.0);
            float puff = smoothstep(1.0, 0.25, d + (n - 0.5) * 1.2);
            float life = smoothstep(0.0, 0.06, vAge) * (1.0 - smoothstep(0.35, 1.0, vAge));
            float a = puff * puff * life * vDensity * 0.4;
            vec3 col = uAuthored > 0.5
              ? vColor * uLight * (0.6 + 0.8 * n)
              // Lit by the sky and sun, plus the plant's lights glowing up into the lower plume.
              : uAmbient * (0.7 + 0.6 * n) + uSunCol * (0.4 + 0.6 * n)
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
      u.uAmbient.value.setRGB(...ambient);
      u.uSunCol.value.setRGB(...sunColor);
      u.uGlowAmt.value = glow;
    }
  }
}
