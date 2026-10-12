// One app, many worlds: a gallery of every built world plus a three.js viewer.
// Worlds come from worlds/index.json, written by tools/build_world.py.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { createSkyDome, skyUniforms } from './sky.js';
import { Floaters, Ocean } from './ocean.js';

const $ = (id) => document.getElementById(id);
let worlds = [];

async function main() {
  const res = await fetch('worlds/index.json', { cache: 'no-cache' });
  worlds = res.ok ? (await res.json()).worlds : [];
  renderGallery();
  window.addEventListener('hashchange', route);
  route();
}

function route() {
  const m = location.hash.match(/^#\/w\/([\w-]+)/);
  $('gallery').hidden = !!m;
  $('viewer').hidden = !m;
  if (m) viewer.open(m[1]);
  else viewer.close();
}

function renderGallery() {
  const grid = $('grid');
  if (!worlds.length) {
    grid.innerHTML = '<p class="empty">No worlds built yet. Run <code>make worlds</code>.</p>';
    return;
  }
  grid.innerHTML = '';
  for (const w of worlds) {
    const a = document.createElement('a');
    a.className = 'card';
    a.href = `#/w/${w.slug}`;
    a.innerHTML = `<img loading="lazy" alt=""><div class="body"><h3></h3><p></p><div class="tags"></div></div>`;
    a.querySelector('img').src = w.preview;
    a.querySelector('h3').textContent = w.title;
    a.querySelector('p').textContent = w.description;
    for (const t of w.tags || []) {
      const s = document.createElement('span');
      s.textContent = t;
      a.querySelector('.tags').append(s);
    }
    grid.append(a);
  }
}

// ------------------------------------------------------------------ viewer

const viewer = (() => {
  const canvas = $('canvas');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.AgXToneMapping;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.5, 20000);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.495;

  const hemi = new THREE.HemisphereLight();
  const sun = new THREE.DirectionalLight();
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  sun.shadow.bias = -0.0004;
  scene.add(hemi, sun, sun.target);

  // Sky dome; the ocean reflects the same sky via the shared uniforms.
  const skyDome = createSkyDome();
  scene.add(skyDome);

  // Pre-pass of the scene without water: the ocean samples it for refraction and depth.
  const prepass = new THREE.WebGLRenderTarget(1, 1, {
    type: THREE.HalfFloatType,
    depthTexture: new THREE.DepthTexture(1, 1),
  });
  const clock = new THREE.Clock();
  let ocean = null;
  let floaters = null;

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0, 0.35, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  // Large worlds are Draco-compressed by the build; the decoder is only fetched when needed.
  const draco = new DRACOLoader().setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/');
  const loader = new GLTFLoader().setDRACOLoader(draco);
  let current = null;   // { slug, root, meta }
  let running = false;
  let loadToken = 0;

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    const px = renderer.getPixelRatio();
    prepass.setSize(Math.floor(w * px), Math.floor(h * px));
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);

  // The shadow map covers the area around what you're looking at, sized to the zoom level,
  // so close-ups get crisp shadows even in kilometer-wide worlds.
  const shadowFit = { dir: new THREE.Vector3(0, 1, 0), worldRadius: 100, radius: 0,
    center: new THREE.Vector3() };
  function fitShadow() {
    const dist = camera.position.distanceTo(controls.target);
    const r = THREE.MathUtils.clamp(dist * 0.9, 30, shadowFit.worldRadius);
    const moved = shadowFit.center.distanceTo(controls.target);
    if (Math.abs(r - shadowFit.radius) < r * 0.08 && moved < r * 0.08) return;
    shadowFit.radius = r;
    shadowFit.center.copy(controls.target);
    sun.target.position.copy(controls.target);
    sun.position.copy(controls.target).addScaledVector(shadowFit.dir, r * 3);
    Object.assign(sun.shadow.camera, { left: -r, right: r, top: r, bottom: -r, near: 0.1, far: r * 6 });
    sun.shadow.camera.updateProjectionMatrix();
    sun.shadow.normalBias = 0.02 + r * 0.0015;
  }

  function frame() {
    if (!running) return;
    requestAnimationFrame(frame);
    controls.update();
    if (current) fitShadow();
    skyDome.position.copy(camera.position);
    const t = clock.getElapsedTime();
    if (ocean) {
      floaters?.update(t);
      ocean.update(t, camera, prepass);
      ocean.mesh.visible = false;
      renderer.setRenderTarget(prepass);
      renderer.render(scene, camera);
      renderer.setRenderTarget(null);
      ocean.mesh.visible = true;
    }
    composer.render();
  }

  function applyMeta(meta) {
    const v = meta.viewer;
    const fogColor = new THREE.Color(v.fog.color);
    scene.fog = new THREE.Fog(fogColor, v.fog.near, v.fog.far);
    skyUniforms.uSkyTop.value.set(v.sky.color);
    skyUniforms.uSkyHorizon.value.copy(fogColor);
    skyUniforms.uSunDir.value.set(...v.sun.direction).normalize();
    skyUniforms.uSunColor.value.set(v.sun.color);
    skyUniforms.uSunStrength.value = v.sun.strength;

    hemi.color.set(v.sky.color);
    hemi.groundColor.set(v.sky.ground);
    hemi.intensity = 1.4 * v.sky.strength;
    sun.color.set(v.sun.color);
    sun.intensity = 0.75 * v.sun.strength;

    const min = new THREE.Vector3(...v.bounds.min), max = new THREE.Vector3(...v.bounds.max);
    shadowFit.worldRadius = Math.max(max.clone().sub(min).length() / 2, 1);
    shadowFit.dir.set(...v.sun.direction).normalize();
    shadowFit.radius = 0;

    bloom.strength = v.bloom ?? 0;
    bloom.enabled = bloom.strength > 0;
    // "agx" (default, filmic) or "neutral" (keeps saturated colors; good for photo-matched worlds).
    renderer.toneMapping = v.tone === 'neutral' ? THREE.NeutralToneMapping : THREE.AgXToneMapping;
    renderer.toneMappingExposure = v.exposure ?? 1;
    resetView();
  }

  function resetView() {
    const c = current?.meta.viewer.camera;
    if (!c) return;
    camera.fov = c.fov;
    camera.position.set(...c.position);
    controls.target.set(...c.target);
    camera.updateProjectionMatrix();
    controls.update();
  }

  async function open(slug) {
    resize();
    if (!running) { running = true; frame(); }
    if (current?.slug === slug) return;
    const token = ++loadToken;
    $('loading').hidden = false;
    $('loading').textContent = 'Loading…';
    try {
      const meta = await (await fetch(`worlds/${slug}/meta.json`, { cache: 'no-cache' })).json();
      const gltf = await loader.loadAsync(`worlds/${slug}/world.glb`, (e) => {
        if (e.total) $('loading').textContent = `Loading… ${Math.round(100 * e.loaded / e.total)}%`;
      });
      if (token !== loadToken) return;
      if (current) { scene.remove(current.root); dispose(current.root); }
      if (ocean) { scene.remove(ocean.mesh); dispose(ocean.mesh); ocean = floaters = null; }
      if (meta.viewer.ocean) {
        const v = meta.viewer;
        ocean = new Ocean(v.ocean, { sunStrength: v.sun.strength, sunElevation: v.sun.direction[1],
          skyStrength: v.sky.strength });
        scene.add(ocean.mesh);
        floaters = new Floaters(gltf.scene, ocean);
      }
      batchInstances(gltf.scene);
      gltf.scene.traverse((o) => {
        if (o.isMesh) {
          o.castShadow = !o.material.transparent;
          o.receiveShadow = true;
        }
      });
      scene.add(gltf.scene);
      current = { slug, root: gltf.scene, meta };
      applyMeta(meta);
      $('w-title').textContent = meta.title;
      $('w-desc').textContent = meta.description;
      $('w-stats').textContent =
        `${meta.stats.objects} objects · ${meta.stats.triangles_drawn.toLocaleString()} tris · ` +
        `${(meta.stats.glb_bytes / 1e6).toFixed(1)} MB · Blender ${meta.built_with}`;
      document.title = `${meta.title} · Worlds`;
      $('loading').hidden = true;
    } catch (err) {
      console.error(err);
      $('loading').textContent = `Could not load "${slug}": ${err.message}`;
    }
  }

  function close() {
    running = false;
    document.title = 'Worlds';
  }

  // Repeated objects (harness instance() copies) arrive as separate meshes sharing geometry and
  // material. Merge each such set into one InstancedMesh: one draw call instead of hundreds.
  function batchInstances(root) {
    root.updateMatrixWorld(true);
    const groups = new Map();
    root.traverse((o) => {
      if (!o.isMesh || o.isInstancedMesh) return;
      for (let p = o; p; p = p.parent) if (p.userData?.bob) return;  // floaters move on their own
      const key = `${o.geometry.uuid}|${o.material.uuid}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(o);
    });
    let merged = 0;
    for (const meshes of groups.values()) {
      if (meshes.length < 4) continue;
      const inst = new THREE.InstancedMesh(meshes[0].geometry, meshes[0].material, meshes.length);
      inst.name = `${meshes[0].name}×${meshes.length}`;
      meshes.forEach((m, i) => {
        inst.setMatrixAt(i, m.matrixWorld);  // root sits at the origin, so world == root space
        m.removeFromParent();
      });
      inst.computeBoundingSphere();
      root.add(inst);
      merged += meshes.length;
    }
    return merged;
  }

  function dispose(root) {
    root.traverse((o) => {
      o.geometry?.dispose();
      for (const m of [].concat(o.material || [])) {
        for (const v of Object.values(m)) if (v?.isTexture) v.dispose();
        m.dispose();
      }
    });
  }

  function step(delta) {
    if (!worlds.length || !current) return;
    const i = worlds.findIndex((w) => w.slug === current.slug);
    location.hash = `#/w/${worlds[(i + delta + worlds.length) % worlds.length].slug}`;
  }

  function toggleSpin() {
    controls.autoRotate = !controls.autoRotate;
    $('b-spin').classList.toggle('on', controls.autoRotate);
  }

  $('b-prev').onclick = () => step(-1);
  $('b-next').onclick = () => step(1);
  $('b-reset').onclick = resetView;
  $('b-spin').onclick = toggleSpin;
  window.addEventListener('keydown', (e) => {
    if ($('viewer').hidden) return;
    if (e.key === 'Escape') location.hash = '#/';
    if (e.key === '[') step(-1);
    if (e.key === ']') step(1);
    if (e.key === '0') resetView();
    if (e.key === 'r') toggleSpin();
  });

  // Handle for debugging and automated checks from the browser console.
  window.viewer = { scene, camera, controls, renderer, get ocean() { return ocean; } };

  return { open, close };
})();

main();
