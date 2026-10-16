/* HAVEN REALTIME · production model renderer.
 *
 * Loads haven-home.glb (built headless in Blender from blender-harness worlds/haven-home) and drives
 * it from the same Home Assistant `devices` state as the dashboard panels. Nothing is fetched from a
 * CDN: three.js is vendored under ./vendor/three.
 *
 * The model marks what the dashboard controls with glTF extras (three.js userData):
 *   haven_room      room floors              haven_light + haven_power   light anchors
 *   haven_glow      emissive parts per room  haven_role  tv_screen | blind | fan_rotor | monitor
 *   haven_cutaway   north | west tall walls, hidden while the camera is behind them
 *
 * createGlbModel(ctx) resolves to {select, sync, dispose}, the same interface as the procedural
 * renderer, so the rest of the app is unchanged.
 */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {GTAOPass} from 'three/addons/postprocessing/GTAOPass.js';
import {UnrealBloomPass} from 'three/addons/postprocessing/UnrealBloomPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';

const LAMP = new THREE.Color(0xffc690);
const FOV = 35;
const HOME = {target: [0, 0.3, 0.1], dist: 23, yaw: 0.71, elev: 0.62};
const LAMP_CANDELA = 3.6;      // per unit of haven_power at full brightness

const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

export async function createGlbModel(ctx) {
  const {host, shell, rooms, getDevices, getSelected, $, url = 'haven-home.glb', onProgress} = ctx;
  const gltf = await new GLTFLoader().loadAsync(url, e => onProgress?.(e.total ? e.loaded / e.total : 0));
  const model = gltf.scene;

  // ---------------------------------------------------------------- renderer and scene
  const renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'high-performance'});
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const canvas = renderer.domElement;
  canvas.className = 'haven-realtime-canvas';
  canvas.setAttribute('aria-label', 'Interactive 3D home. Drag to orbit; scroll to zoom; click a room to inspect devices.');
  canvas.style.cssText = 'display:block;width:100%;height:100%;touch-action:none';
  host.append(canvas);
  host.style.pointerEvents = 'auto';

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = envTex;
  scene.add(model);

  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 220);

  // Background: the stage's dark radial gradient, warmed at golden hour.
  const bgCanvas = document.createElement('canvas');
  bgCanvas.width = bgCanvas.height = 256;
  const bgTex = new THREE.CanvasTexture(bgCanvas);
  bgTex.colorSpace = THREE.SRGBColorSpace;
  scene.background = bgTex;
  function paintBackground(up, warm) {
    const g = bgCanvas.getContext('2d');
    const grad = g.createRadialGradient(118, 128, 8, 128, 128, 190);
    grad.addColorStop(0, `rgb(${Math.round(40 + warm * 30 + up * 22)},${Math.round(48 + warm * 14 + up * 26)},${Math.round(66 + up * 26)})`);
    grad.addColorStop(0.72, `rgb(${Math.round(15 + up * 8)},${Math.round(22 + up * 10)},${Math.round(37 + up * 12)})`);
    grad.addColorStop(1, '#0b121e');
    g.fillStyle = grad;
    g.fillRect(0, 0, 256, 256);
    bgTex.needsUpdate = true;
  }

  // Lights: sun (or moon), sky fill, and one point light per lamp in the model.
  const hemi = new THREE.HemisphereLight(0xcfe0ff, 0x5b4a3c, 0.8);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xffffff, 2.5);
  sun.castShadow = true;
  sun.shadow.camera.left = -15; sun.shadow.camera.right = 15;
  sun.shadow.camera.top = 15; sun.shadow.camera.bottom = -15;
  sun.shadow.camera.near = 1; sun.shadow.camera.far = 80;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.025;
  scene.add(sun, sun.target);

  // ---------------------------------------------------------------- what the dashboard drives
  model.updateMatrixWorld(true);
  const anchors = [], glows = [], cutaways = [], blinds = [], rotors = [], screens = [], pickables = [];
  let studio = null;
  model.traverse(o => {
    const u = o.userData || {};
    if (o.name === 'Studio') studio = o;
    if (u.haven_light) anchors.push({room: u.haven_light, power: +u.haven_power || 1, pos: o.getWorldPosition(new THREE.Vector3())});
    if (u.haven_cutaway) cutaways.push({obj: o, side: u.haven_cutaway});
    if (u.haven_role === 'blind') blinds.push({obj: o, room: u.haven_room || 'bedroom', open: 0});
    if (u.haven_role === 'fan_rotor') rotors.push({obj: o, axis: new THREE.Vector3(...(u.haven_axis || [0, 0, 1])).normalize()});
    if (u.haven_glow || u.haven_role === 'tv_screen') {
      o.traverse(m => {
        if (!m.isMesh) return;
        m.material = m.material.clone();   // per-object intensity
        const entry = {mesh: m, room: u.haven_glow, base: m.material.emissiveIntensity || 1, role: u.haven_role};
        if (u.haven_role === 'tv_screen') screens.push(entry); else glows.push(entry);
      });
    }
    if (o.isMesh) {
      const transparent = o.material.transparent;
      o.castShadow = !transparent && !u.haven_light;
      o.receiveShadow = true;
      if (o.material.map) o.material.map.anisotropy = renderer.capabilities.getMaxAnisotropy();
    }
  });
  if (studio) studio.visible = false;
  const catcher = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.ShadowMaterial({opacity: 0.5}));
  catcher.rotation.x = -Math.PI / 2;
  catcher.position.y = -0.9;
  catcher.receiveShadow = true;
  scene.add(catcher);
  model.traverse(o => { if (o.isMesh && o !== studio) pickables.push(o); });

  // Point lights: one per lamp ("ultra"), or one per room ("lite", much cheaper on phones).
  const lightGroup = new THREE.Group();
  scene.add(lightGroup);
  let lamps = [];
  function buildLamps(perFixture) {
    lightGroup.clear();
    lamps = [];
    const groups = perFixture ? anchors.map(a => [a]) :
      Object.values(anchors.reduce((acc, a) => ((acc[a.room] ||= []).push(a), acc), {}));
    for (const list of groups) {
      const pos = list.reduce((s, a) => s.add(a.pos), new THREE.Vector3()).divideScalar(list.length);
      const power = list.reduce((s, a) => s + a.power, 0);
      const light = new THREE.PointLight(LAMP, 0, perFixture ? 6.5 : 8, 2);
      light.position.copy(pos);
      lightGroup.add(light);
      lamps.push({light, room: list[0].room, power, level: 0});
    }
  }

  // Selected-room frame on the floor.
  const frameMat = new THREE.MeshBasicMaterial({color: 0xd3b994, transparent: true, opacity: 0, depthWrite: false});
  const frame = new THREE.Group();
  for (let i = 0; i < 4; i++) frame.add(new THREE.Mesh(new THREE.BoxGeometry(1, 0.012, 1), frameMat));
  frame.position.y = 0.042;
  scene.add(frame);
  function placeFrame(r) {
    const t = 0.05, [n, s, e, w] = frame.children;
    n.scale.set(r.w, 1, t); n.position.set(0, 0, -r.d / 2);
    s.scale.set(r.w, 1, t); s.position.set(0, 0, r.d / 2);
    e.scale.set(t, 1, r.d); e.position.set(r.w / 2, 0, 0);
    w.scale.set(t, 1, r.d); w.position.set(-r.w / 2, 0, 0);
    frame.position.x = r.x; frame.position.z = r.z;
  }

  // ---------------------------------------------------------------- post processing
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const gtao = new GTAOPass(scene, camera, 2, 2);
  gtao.updateGtaoMaterial({radius: 0.35, distanceExponent: 1.5, thickness: 1.0, scale: 1.0, samples: 12});
  gtao.blendIntensity = 0.85;
  composer.addPass(gtao);
  const bloom = new UnrealBloomPass(new THREE.Vector2(2, 2), 0.32, 0.55, 0.92);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  // ---------------------------------------------------------------- quality
  const forced = new URLSearchParams(location.search).get('quality');   // ultra | lite
  let quality = forced !== 'lite', cinema = true, W = 0, H = 0;
  function applyQuality() {
    const size = quality ? 4096 : 1536;
    if (sun.shadow.mapSize.x !== size) {
      sun.shadow.mapSize.set(size, size);
      sun.shadow.map?.dispose();
      sun.shadow.map = null;
    }
    gtao.enabled = quality;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, quality ? 2 : 1));
    buildLamps(quality);
    W = 0;
    resize();
    sync();
  }
  function resize() {
    const r = host.getBoundingClientRect();
    const w = Math.max(2, Math.floor(r.width)), h = Math.max(2, Math.floor(r.height));
    if (w === W && h === H) return;
    W = w; H = h;
    renderer.setSize(w, h, false);
    composer.setPixelRatio(renderer.getPixelRatio());
    composer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (lastSelect !== null) tDist = distanceFor(lastSelect);
  }

  // ---------------------------------------------------------------- room labels
  const overlay = document.createElement('div');
  overlay.className = 'haven-room-overlay';
  shell.append(overlay);
  const labels = new Map();
  for (const r of rooms) {
    const b = document.createElement('button');
    b.className = 'haven-room-chip';
    b.textContent = r.name;
    b.title = 'Explore ' + r.full;
    b.onclick = () => ctx.selectRoom(r.id, true);
    overlay.append(b);
    labels.set(r.id, b);
  }
  const tmp = new THREE.Vector3();
  function updateLabels() {
    for (const r of rooms) {
      tmp.set(r.x, 1.84, r.z).project(camera);
      const el = labels.get(r.id);
      const x = (tmp.x * 0.5 + 0.5) * W, y = (-tmp.y * 0.5 + 0.5) * H;
      el.style.left = `${Math.round(x)}px`;
      el.style.top = `${Math.round(y)}px`;
      el.style.opacity = tmp.z > 1 || x < -0.04 * W || x > 1.04 * W || y < -0.1 * H || y > 1.1 * H ? 0 : 1;
    }
  }

  // ---------------------------------------------------------------- camera rig
  let yaw = HOME.yaw, elev = HOME.elev, dist = HOME.dist, tYaw = yaw, tElev = elev, tDist = dist;
  const target = new THREE.Vector3(...HOME.target), desired = target.clone();
  let auto = false, top = false;
  const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Distance at which a view `rh` meters wide and `rv` meters tall (as seen from the orbit
  // elevation) fits the viewport.
  const fit = (rh, rv) => {
    const v = Math.tan(FOV * Math.PI / 360);
    return Math.max(rh / (v * camera.aspect), rv / v);
  };
  let lastSelect = null;
  function distanceFor(id) {
    const r = rooms.find(x => x.id === id);
    if (r) {
      const span = Math.max(r.w, r.d);
      return Math.min(26, Math.max(10.5, fit(span * 0.62 + 0.9, span * 0.42 + 1.0)));
    }
    return Math.max(top ? 18 : 17, fit(8.6, 5.4));
  }
  function select(id, animated = true) {
    lastSelect = id;
    const r = rooms.find(x => x.id === id);
    tDist = distanceFor(id);
    if (r) {
      desired.set(r.x, 0.35, r.z);
      tElev = top ? 1.5 : 0.78;
      placeFrame(r);
    } else {
      desired.set(...HOME.target);
      tElev = top ? 1.5 : HOME.elev;
      if (!top) tYaw = nearestTurn(HOME.yaw);
    }
    frameMat.userData.on = !!r;
    if (!animated) { target.copy(desired); dist = tDist; yaw = tYaw; elev = tElev; }
    labels.forEach((el, key) => el.classList.toggle('chosen', key === id));
  }
  const nearestTurn = a => a + Math.round((yaw - a) / (2 * Math.PI)) * 2 * Math.PI;

  let press = null, pinch = null;
  const onDown = e => {
    press = {x: e.clientX, y: e.clientY, px: e.clientX, py: e.clientY, t: performance.now(), drag: false};
    canvas.setPointerCapture(e.pointerId);
  };
  const onMove = e => {
    if (!press || pinch) return;
    const dx = e.clientX - press.px, dy = e.clientY - press.py;
    press.px = e.clientX; press.py = e.clientY;
    if (Math.hypot(e.clientX - press.x, e.clientY - press.y) > 5) press.drag = true;
    if (press.drag) {
      tYaw += dx * 0.007;
      tElev = Math.min(1.52, Math.max(0.18, tElev + dy * 0.006));
      setAuto(false);
    }
  };
  const ray = new THREE.Raycaster();
  const onUp = e => {
    if (!press) return;
    const p = press; press = null;
    if (p.drag || performance.now() - p.t > 520) return;
    const rect = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(pickables, false).find(h => visibleChain(h.object));
    let chosen = null;
    if (hit) {
      const q = hit.point;
      chosen = rooms.find(r => Math.abs(q.x - r.x) <= r.w / 2 + 0.25 && Math.abs(q.z - r.z) <= r.d / 2 + 0.25)?.id;
      if (!chosen) {
        let best = 3;
        for (const r of rooms) { const d = Math.hypot(q.x - r.x, q.z - r.z); if (d < best) { best = d; chosen = r.id; } }
      }
    }
    if (chosen) ctx.selectRoom(chosen, true);
  };
  const visibleChain = o => { for (; o; o = o.parent) if (!o.visible) return false; return true; };
  const onWheel = e => { e.preventDefault(); tDist = Math.max(6, Math.min(40, tDist * Math.exp(e.deltaY * 0.0011))); };
  const onTouchMove = e => {
    if (e.touches.length !== 2) { pinch = null; return; }
    const [a, b] = e.touches, d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    if (pinch) tDist = Math.max(6, Math.min(40, tDist * pinch / d));
    pinch = d;
  };
  const onTouchEnd = () => { pinch = null; };
  canvas.addEventListener('pointerdown', onDown);
  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('pointercancel', () => { press = null; });
  canvas.addEventListener('wheel', onWheel, {passive: false});
  canvas.addEventListener('touchmove', onTouchMove, {passive: true});
  canvas.addEventListener('touchend', onTouchEnd);

  function setAuto(on) { auto = on; $('#rotateView')?.classList.toggle('active', on); }
  const resetView = () => { top = false; $('#topView')?.classList.remove('active'); ctx.selectRoom('all', true); };
  $('#resetView').onclick = resetView;
  if ($('#resetCameraFooter')) $('#resetCameraFooter').onclick = resetView;
  $('#topView').onclick = () => {
    top = !top;
    $('#topView').classList.toggle('active', top);
    select(getSelected?.() || 'all', true);
  };
  $('#rotateView').onclick = () => setAuto(!auto);
  $('#qualityToggle').onclick = () => { downgraded = true; quality = !quality; $('#qualityToggle').classList.toggle('active', quality); applyQuality(); };
  $('#cinemaToggle').onclick = () => { cinema = !cinema; $('#cinemaToggle').classList.toggle('active', cinema); bloom.enabled = cinema; };
  $('#qualityToggle').classList.toggle('active', quality);
  $('#cinemaToggle').classList.add('active');

  // ---------------------------------------------------------------- time of day
  let dayTime = +($('#timeSlider')?.value || 17), dayCycle = false, lastBg = -1;
  $('#timeSlider').oninput = e => {
    dayTime = +e.target.value;
    dayCycle = false;
    $('#animateDay').classList.remove('active');
    $('#animateDay').textContent = '▶ DAY CYCLE';
  };
  $('#animateDay').onclick = () => {
    dayCycle = !dayCycle;
    $('#animateDay').classList.toggle('active', dayCycle);
    $('#animateDay').textContent = dayCycle ? 'Ⅱ PAUSE CYCLE' : '▶ DAY CYCLE';
  };
  const sunColorLow = new THREE.Color(0xffa565), sunColorHigh = new THREE.Color(0xfff3e4);
  const moon = new THREE.Color(0x8fa6d6), skyDay = new THREE.Color(0xd6e4ff), skyNight = new THREE.Color(0x1c2638);
  function atmosphere() {
    // Sun rises in the east (+x) at 06:00, crosses the south (+z) and sets in the west at 18:00.
    const a = (dayTime - 6) / 12 * Math.PI;
    const up = Math.sin(a);                       // < 0 at night
    const day = smooth(-0.06, 0.35, up);
    const warm = Math.max(0, 1 - Math.abs(up - 0.12) / 0.32) * smooth(-0.05, 0.05, up);
    if (up > -0.02) {
      sun.position.set(Math.cos(a) * 30, Math.max(0.05, up) * 26 + 1.5, Math.max(0.15, Math.sin(a)) * 16 + 4);
      sun.color.copy(sunColorLow).lerp(sunColorHigh, smooth(0.08, 0.6, up));
      sun.intensity = 3.6 * smooth(-0.02, 0.12, up);
    } else {   // moonlight
      sun.position.set(-12, 24, 10);
      sun.color.copy(moon);
      sun.intensity = 0.18;
    }
    sun.position.add(target);
    sun.target.position.copy(target);
    hemi.color.copy(skyNight).lerp(skyDay, day);
    hemi.intensity = lerp(0.16, 0.5, day);
    scene.environmentIntensity = lerp(0.09, 0.32, day);
    renderer.toneMappingExposure = lerp(1.35, 0.95, day) + warm * 0.05;
    if (Math.abs(dayTime - lastBg) > 0.1) { paintBackground(day, warm); lastBg = dayTime; }
    const label = dayTime >= 5 && dayTime < 10 ? 'Morning' : dayTime >= 10 && dayTime < 16 ? 'Daylight'
      : dayTime >= 16 && dayTime < 20 ? 'Golden hour' : 'Night';
    const hh = Math.floor(dayTime), mm = Math.floor((dayTime - hh) * 60);
    const tv = $('#timeValue');
    if (tv) tv.textContent = `${label} · ${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
  }

  // ---------------------------------------------------------------- Home Assistant state
  const roomLevel = {};
  let tvOn = false, coverOpen = {}, fanSpin = 0;
  function sync() {
    const devices = getDevices();
    for (const r of rooms) {
      const on = devices.filter(d => d.room === r.id && d.domain === 'light' && d.on);
      roomLevel[r.id] = on.length ? on.reduce((t, d) => t + (d.brightness ?? 80) / 100, 0) / on.length : 0;
    }
    tvOn = devices.some(d => d.domain === 'media_player' && d.room === 'living' && d.on);
    for (const b of blinds) coverOpen[b.room] = devices.some(d => d.domain === 'cover' && d.room === b.room && d.on);
    const fans = devices.filter(d => d.domain === 'fan' && d.room === 'hall');
    fanSpin = fans.length ? (fans.some(f => f.on) ? 9 : 0) : 1.2;   // no fan entity: slow ambient spin
  }

  // ---------------------------------------------------------------- frame loop
  let raf = 0, last = performance.now(), frameNo = 0, tvPhase = 0, downgraded = !!forced;
  const slow = [];
  function draw() {
    raf = requestAnimationFrame(draw);
    if (document.hidden) return;
    const now = performance.now(), dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    frameNo++;
    resize();
    if (auto && !prefersReduced) tYaw += dt * 0.12;
    if (dayCycle) { dayTime = (dayTime + dt * 0.32) % 24; $('#timeSlider').value = dayTime; }
    const k = Math.min(1, dt * 5);
    yaw += (tYaw - yaw) * k; elev += (tElev - elev) * k; dist += (tDist - dist) * k;
    target.lerp(desired, Math.min(1, dt * 4.2));
    const c = Math.cos(elev);
    camera.position.set(target.x + Math.sin(yaw) * c * dist, target.y + Math.sin(elev) * dist, target.z + Math.cos(yaw) * c * dist);
    camera.lookAt(target);
    atmosphere();

    // Lamps ease toward the confirmed Home Assistant state.
    for (const l of lamps) {
      l.level += ((roomLevel[l.room] || 0) - l.level) * Math.min(1, dt * 4);
      l.light.intensity = LAMP_CANDELA * l.power * l.level;
      l.light.visible = l.level > 0.003;
    }
    const levelOf = room => lamps.filter(l => l.room === room).reduce((m, l) => Math.max(m, l.level), 0);
    for (const g of glows) {
      const lv = levelOf(g.room);
      g.mesh.material.emissiveIntensity = g.role === 'monitor' ? g.base * (0.35 + 0.65 * lv) : g.base * (0.015 + lv);
    }
    tvPhase += dt;
    for (const s of screens) {
      const m = s.mesh.material;
      if (tvOn) {
        m.emissive.setHSL(0.58 + 0.04 * Math.sin(tvPhase * 0.7), 0.45, 0.42 + 0.04 * Math.sin(tvPhase * 2.3));
        m.emissiveIntensity = 1.3;
      } else {
        m.emissiveIntensity = 0;
      }
    }
    for (const b of blinds) {
      b.open += ((coverOpen[b.room] ? 1 : 0) - b.open) * Math.min(1, dt * 2.5);
      b.obj.scale.y = 1 - 0.93 * b.open;
    }
    for (const r of rotors) r.obj.rotateOnAxis(r.axis, fanSpin * dt);
    // Hide tall walls that stand between the camera and the rooms.
    const p = camera.position;
    for (const cw of cutaways) cw.obj.visible = !(cw.side === 'north' ? p.z < -4.5 : cw.side === 'west' ? p.x < -6 : false);
    frameMat.opacity += ((frameMat.userData.on ? 0.85 : 0) - frameMat.opacity) * Math.min(1, dt * 6);
    frame.visible = frameMat.opacity > 0.01;

    if (cinema || quality) composer.render(dt);
    else renderer.render(scene, camera);
    // Slow device: drop to lite once (no AO, per-room lights, smaller shadows).
    if (quality && !downgraded && frameNo > 20) {
      slow.push(dt);
      if (slow.length === 60) {
        downgraded = true;
        if (slow.reduce((a, b) => a + b, 0) / slow.length > 0.04) {
          quality = false; $('#qualityToggle').classList.remove('active'); applyQuality();
        }
      }
    }
    if (frameNo % 3 === 0) updateLabels();
  }

  const observer = new ResizeObserver(resize);
  observer.observe(host);
  applyQuality();
  select(getSelected?.() || 'living', false);
  atmosphere();
  draw();
  const snap = () => { target.copy(desired); dist = tDist; yaw = tYaw; elev = tElev; };
  window.havenViewer = {scene, camera, renderer, model, anchors, get lamps() { return lamps; }, snap};

  return {
    select,
    sync,
    dispose() {
      cancelAnimationFrame(raf);
      observer.disconnect();
      canvas.remove();
      overlay.remove();
      composer.dispose?.();
      envTex.dispose();
      pmrem.dispose();
      renderer.dispose();
    },
  };
}
