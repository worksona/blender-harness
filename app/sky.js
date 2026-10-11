// Shared sky model: the dome draws it, the ocean reflects it, so they always agree.
import * as THREE from 'three';

export const skyUniforms = {
  uSkyTop: { value: new THREE.Color() },
  uSkyHorizon: { value: new THREE.Color() },
  uSunDir: { value: new THREE.Vector3(0, 1, 0) },
  uSunColor: { value: new THREE.Color() },
  uSunStrength: { value: 1 },
};

export const SKY_GLSL = /* glsl */ `
uniform vec3 uSkyTop;
uniform vec3 uSkyHorizon;
uniform vec3 uSunDir;
uniform vec3 uSunColor;
uniform float uSunStrength;

vec3 skyColor(vec3 dir) {
  float up = clamp(dir.y, 0.0, 1.0);
  // Narrow horizon band, then the zenith color.
  vec3 col = mix(uSkyHorizon, uSkyTop, 1.0 - exp(-up * 7.0));
  float s = max(dot(dir, uSunDir), 0.0);
  // Warm glow around the sun (wider when the sun is low), then the ~0.5 degree disc.
  float lowSun = 1.0 - clamp(uSunDir.y * 2.5, 0.0, 1.0);
  float horizonBias = 1.0 - smoothstep(0.0, 0.5, up);
  col += uSunColor * uSunStrength * 0.25 *
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
