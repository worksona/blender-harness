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
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { createSkyDome } from './sky.js';
import { Floaters, Ocean } from './ocean.js';
import { Lamps, Plumes } from './effects.js';
import { Lighting } from './lighting.js';
import { Twin, twinIdOf } from './twin.js';

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
  const m = location.hash.match(/^#\/w\/([\w-]+)(?:\?(.*))?/);
  $('gallery').hidden = !!m;
  $('viewer').hidden = !m;
  if (m) viewer.open(m[1], new URLSearchParams(m[2] || ''));
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
    for (const t of [...(w.private ? ['private'] : []), ...(w.tags || [])]) {
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
  const lighting = new Lighting({
    renderer, scene, sun, hemi,
    onSunDir: (d) => { shadowFit.dir.set(...d).normalize(); shadowFit.radius = 0; },
  });
  const twin = new Twin({ scene, camera, controls, canvas, overlay: $('twin-gauges') });
  let ocean = null;
  let floaters = null;
  let lamps = null;
  let plumes = null;

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0, 0.35, 1.0);
  composer.addPass(bloom);
  // Photographic grade from the world's META["grade"]: per-channel gains and saturation, applied
  // in scene-linear before tone mapping, exactly like the Blender render's compositor.
  const grade = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, uGains: { value: new THREE.Vector3(1, 1, 1) },
      uSat: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform vec3 uGains; uniform float uSat;
      varying vec2 vUv;
      void main() {
        vec4 c = texture2D(tDiffuse, vUv);
        vec3 col = c.rgb * uGains;
        float lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
        gl_FragColor = vec4(max(mix(vec3(lum), col, uSat), 0.0), c.a);
      }`,
  });
  composer.addPass(grade);
  composer.addPass(new OutputPass());

  function applyGrade(g) {
    grade.uniforms.uGains.value.set(...(g?.gains ?? [1, 1, 1]));
    grade.uniforms.uSat.value = g?.saturation ?? 1;
    grade.enabled = !!g;
  }

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
    const dt = Math.min(clock.getDelta(), 0.1);
    const t = clock.elapsedTime;
    twin.update(dt);
    lightPanel.tick();
    lighting.update(camera);
    plumes?.update(t);
    lamps?.update(controls.target);
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

  function applyMeta(meta, params) {
    const v = meta.viewer;
    const min = new THREE.Vector3(...v.bounds.min), max = new THREE.Vector3(...v.bounds.max);
    shadowFit.worldRadius = Math.max(max.clone().sub(min).length() / 2, 1);
    shadowFit.radius = 0;
    lighting.setWorld({ meta, root: current.root, ocean, lamps, plumes });
    lightPanel.load(params);

    applyGrade(v.grade);
    bloom.strength = v.bloom ?? 0;
    bloom.enabled = bloom.strength > 0;
    // "agx" (default, filmic) or "neutral" (keeps saturated colors; good for photo-matched worlds).
    renderer.toneMapping = v.tone === 'neutral' ? THREE.NeutralToneMapping : THREE.AgXToneMapping;
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

  async function open(slug, params = new URLSearchParams()) {
    resize();
    if (!running) { running = true; frame(); }
    if (current?.slug === slug) { lightPanel.load(params); return; }
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
      if (lamps) { scene.remove(lamps.group); dispose(lamps.group); lamps = null; }
      if (plumes) { scene.remove(plumes.mesh); dispose(plumes.mesh); plumes = null; }
      if (meta.viewer.lamps?.length) { lamps = new Lamps(meta.viewer.lamps); scene.add(lamps.group); }
      if (meta.viewer.plumes?.length) { plumes = new Plumes(meta.viewer.plumes); scene.add(plumes.mesh); }
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
          for (let p = o; p; p = p.parent) if (p.userData?.no_cast) { o.castShadow = false; o.userData.no_cast = true; }
        }
      });
      scene.add(gltf.scene);
      current = { slug, root: gltf.scene, meta };
      applyMeta(meta, params);
      twin.load(meta, gltf.scene);
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
    twin.toggle(false);
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
      const ids = meshes.map(twinIdOf);
      if (ids.some(Boolean)) inst.userData.instanceTwin = ids;   // picking a copy finds its record
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

  // ---- light panel: time of day and atmosphere -------------------------------------------
  const lightPanel = (() => {
    const el = (id) => $(id);
    let playing = false, lastT = 0, urlTimer = 0;
    const fmt = (h) => `${String(Math.floor(h) % 24).padStart(2, '0')}:${String(Math.floor((h % 1) * 60)).padStart(2, '0')}`;
    // Visibility slider: 0..100 -> 300 m .. 80 km (log), 100 = automatic from haze.
    const visFrom = (v) => (v >= 100 ? undefined : Math.round(300 * (80000 / 300) ** (v / 99)));
    const visTo = (m) => (m === undefined ? 100 : Math.round(99 * Math.log(m / 300) / Math.log(80000 / 300)));

    function show() {
      const p = lighting.params;
      const physical = !!p;
      const q = p || lighting.fromAuthored();
      el('lp-time').value = q.time;
      el('lp-clock').textContent = fmt(q.time);
      el('lp-season').value = String([355, 80, 172, 266].reduce((a, b) => (Math.abs(b - q.day) < Math.abs(a - q.day) ? b : a)));
      el('lp-lat').value = q.latitude;
      el('lp-lat-out').textContent = `${q.latitude}°`;
      el('lp-haze').value = q.haze;
      el('lp-haze-out').textContent = (+q.haze).toFixed(2);
      el('lp-vis').value = visTo(p?.visibility);
      el('lp-vis-out').textContent = p?.visibility ? `${(p.visibility / 1000).toFixed(p.visibility < 10000 ? 1 : 0)} km` : 'auto';
      el('lp-ev').value = q.exposure ?? 0;
      el('lp-ev-out').textContent = `${(q.exposure ?? 0) >= 0 ? '+' : ''}${(+(q.exposure ?? 0)).toFixed(1)} EV`;
      el('lp-lamps').value = typeof q.lamps === 'string' ? q.lamps : 'auto';
      el('lp-status').textContent = physical ? lighting.describe()
        : 'This world has hand-set lighting. Move any control to switch to the physical sky.';
      el('lp-play').textContent = playing ? '❚❚' : '▶';
    }

    function change(partial) {
      lighting.set(partial);
      lighting.apply();
      lighting.dirty = false;
      show();
      clearTimeout(urlTimer);
      urlTimer = setTimeout(writeUrl, 300);
    }

    function writeUrl() {
      if (!current || !lighting.params) return;
      const p = lighting.params;
      const q = new URLSearchParams({ t: (+p.time).toFixed(2), haze: (+p.haze).toFixed(2), lat: p.latitude,
        day: p.day, ev: (+p.exposure).toFixed(1), lamps: p.lamps });
      if (p.visibility) q.set('vis', p.visibility);
      if (p.north) q.set('north', (+p.north).toFixed(1));
      history.replaceState(null, '', `#/w/${current.slug}?${q}`);
    }

    el('lp-time').addEventListener('input', (e) => change({ time: +e.target.value }));
    el('lp-season').addEventListener('change', (e) => change({ day: +e.target.value }));
    el('lp-lat').addEventListener('input', (e) => change({ latitude: +e.target.value }));
    el('lp-haze').addEventListener('input', (e) => change({ haze: +e.target.value }));
    el('lp-vis').addEventListener('input', (e) => change({ visibility: visFrom(+e.target.value) }));
    el('lp-ev').addEventListener('input', (e) => change({ exposure: +e.target.value }));
    el('lp-lamps').addEventListener('change', (e) => change({ lamps: e.target.value }));
    el('lp-reset').addEventListener('click', () => {
      lighting.reset(); lighting.apply(); lighting.dirty = false; playing = false; show();
      if (current) history.replaceState(null, '', `#/w/${current.slug}`);
    });
    el('lp-play').addEventListener('click', () => { playing = !playing; lastT = performance.now(); show(); });
    el('light-panel').addEventListener('submit', (e) => e.preventDefault());

    return {
      /** Apply lighting parameters from the URL (or the world's defaults when there are none). */
      load(params) {
        const n = (k) => (params.has(k) ? +params.get(k) : undefined);
        const partial = Object.fromEntries(Object.entries({
          time: n('t'), haze: n('haze'), latitude: n('lat'), day: n('day'), exposure: n('ev'),
          visibility: n('vis'), north: n('north'), lamps: params.get('lamps') ?? undefined,
        }).filter(([, v]) => v !== undefined && !Number.isNaN(v)));
        if (Object.keys(partial).length) { lighting.set(partial); lighting.apply(); lighting.dirty = false; }
        show();
      },
      toggle() { el('light-panel').hidden = !el('light-panel').hidden; $('b-light').classList.toggle('on'); show(); },
      togglePlay() { playing = !playing; lastT = performance.now(); show(); },
      tick() {
        if (!playing) return;
        const now = performance.now();
        const hours = ((now - lastT) / 1000) * 0.4;     // 1 hour every 2.5 s
        lastT = now;
        const t = ((lighting.params?.time ?? lighting.fromAuthored().time) + hours) % 24;
        lighting.set({ time: t });
        el('lp-time').value = t;
        el('lp-clock').textContent = fmt(t);
        el('lp-status').textContent = lighting.describe();
      },
    };
  })();

  function toggleSpin() {
    controls.autoRotate = !controls.autoRotate;
    $('b-spin').classList.toggle('on', controls.autoRotate);
  }

  $('b-prev').onclick = () => step(-1);
  $('b-next').onclick = () => step(1);
  $('b-reset').onclick = resetView;
  $('b-spin').onclick = toggleSpin;
  $('b-light').onclick = () => lightPanel.toggle();
  $('b-twin').onclick = () => twin.toggle();
  window.addEventListener('keydown', (e) => {
    if ($('viewer').hidden) return;
    if (e.target.matches?.('input[type=search], input[type=text]')) return;   // typing in a filter box
    if (e.key === 'Escape') location.hash = '#/';
    if (e.key === '[') step(-1);
    if (e.key === ']') step(1);
    if (e.key === '0') resetView();
    if (e.target.closest?.('#light-panel, #twin-panel, input, select')) return;
    if (e.key === 'r') toggleSpin();
    if (e.key === 'l') lightPanel.toggle();
    if (e.key === 't') twin.toggle();
    if (e.key === ' ' && !$('light-panel').hidden) { e.preventDefault(); lightPanel.togglePlay(); }
  });

  // Handle for debugging and automated checks from the browser console.
  window.viewer = { scene, camera, controls, renderer, twin, get ocean() { return ocean; } };

  return { open, close };
})();

main();
