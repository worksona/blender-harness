// Shared sky model: the dome draws it, the ocean reflects it, so they always agree.
import * as THREE from 'three';

export const skyUniforms = {
  uSkyTop: { value: new THREE.Color() },
  uSkyHorizon: { value: new THREE.Color() },
  uSunDir: { value: new THREE.Vector3(0, 1, 0) },
  uSunColor: { value: new THREE.Color() },
  uSunStrength: { value: 1 },
  uGlow: { value: 0.25 },     // glow around the sun; stays on at dusk when the sun is below the horizon
  uGlowHeight: { value: 0.5 }, // how far up the horizon glow reaches (sine of the angle)
  // Physical mode: the baked atmosphere (equirectangular, see lighting.js) replaces the gradient.
  uPhysical: { value: 0 },
  uSkyTex: { value: null },
  uSkyScale: { value: 0.12 },
};

export const SKY_GLSL = /* glsl */ `
uniform vec3 uSkyTop;
uniform vec3 uSkyHorizon;
uniform vec3 uSunDir;
uniform vec3 uSunColor;
uniform float uSunStrength;
uniform float uGlow;
uniform float uGlowHeight;
uniform float uPhysical;
uniform sampler2D uSkyTex;
uniform float uSkyScale;

vec3 physicalSky(vec3 dir) {
  vec2 uv = vec2(atan(dir.z, dir.x) / 6.2831853 + 0.5, asin(clamp(dir.y, -1.0, 1.0)) / 3.1415927 + 0.5);
  vec3 col = texture2D(uSkyTex, uv).rgb * uSkyScale;
  float s = max(dot(dir, uSunDir), 0.0);
  // Sun disc (0.53 deg), coloured by the atmosphere, hidden once it sets.
  col += uSunColor * uSunStrength * smoothstep(0.99996, 0.99999, s) * 6000.0 * step(-0.01, uSunDir.y);
  return col;
}

vec3 skyColor(vec3 dir) {
  if (uPhysical > 0.5) return physicalSky(dir);
  float up = clamp(dir.y, 0.0, 1.0);
  // Narrow horizon band, then the zenith color.
  vec3 col = mix(uSkyHorizon, uSkyTop, 1.0 - exp(-up * 7.0));
  float s = max(dot(dir, uSunDir), 0.0);
  // Warm glow around the sun (wider when the sun is low), then the ~0.5 degree disc.
  float lowSun = 1.0 - clamp(uSunDir.y * 2.5, 0.0, 1.0);
  float horizonBias = 1.0 - smoothstep(0.0, uGlowHeight, up);
  col += uSunColor * uGlow *
         (pow(s, 10.0) * 0.35 * lowSun * horizonBias + pow(s, 90.0) * 0.5 + pow(s, 900.0) * 1.5);
  col += uSunColor * smoothstep(0.99990, 0.99996, s) * 30.0;
  return col;
}
`;

export function createSkyDome() {
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(9000, 48, 24),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false, uniforms: skyUniforms,
      vertexShader: /* glsl */ `
        varying vec3 vDir;
        void main() {
          vDir = normalize(position);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        ${SKY_GLSL}
        varying vec3 vDir;
        void main() {
          gl_FragColor = vec4(skyColor(normalize(vDir)), 1.0);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`,
    }),
  );
  mesh.renderOrder = -1;
  mesh.frustumCulled = false;
  return mesh;
}
