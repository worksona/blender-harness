// Data twin for the viewer: records from meta.json (viewer.twin) linked to objects in the .glb
// through node extras (userData.twin). Click an object to open its record; browse every record in
// the side panel; replay time series (e.g. a pressure test) with a chart, live gauges floating at
// instruments, and objects glowing with the value.
import * as THREE from 'three';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const hhmm = (h) => `${String(Math.floor(h)).padStart(2, '0')}:${String(Math.round((h % 1) * 60) % 60).padStart(2, '0')}`;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** Sim timelines run in days from an epoch date; test replays in hours of the day. */
function timeFormatter(series) {
  const epoch = series?.clock?.epoch;
  if (!epoch) return hhmm;
  const base = Date.UTC(...epoch.split('-').map((x, i) => +x - (i === 1 ? 1 : 0)));
  return (t) => {
    const d = new Date(base + t * 86400e3);
    return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()} ${hhmm((t % 1) * 24)}`;
  };
}
// Record states on the sim timeline (harness.sim.twin_state) and how they tint their objects.
const STATES = {
  pending: { label: 'Not started', color: null, level: 0 },
  active: { label: 'In progress', color: '#ffb14a', level: 0.22 },
  ok: { label: 'Released', color: '#3ddc84', level: 0.2 },
  at_risk: { label: 'At risk', color: '#ffd23f', level: 0.3 },
  hold: { label: 'On hold', color: '#ff3b2f', level: 0.5 },
  done: { label: 'Turned over', color: '#4aa8ff', level: 0.18 },
};
const TASK = { weld: 'welding', inspect: 'inspecting', carry: 'carrying', talk: 'talking', idle: 'standing by', survey: 'surveying' };

/** Small text pill as a sprite, for document packets travelling between buildings. */
function labelSprite(text, color) {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  ctx.font = '600 40px system-ui, sans-serif';
  const w = Math.ceil(ctx.measureText(text).width) + 56;
  c.width = w; c.height = 72;
  ctx.font = '600 40px system-ui, sans-serif';
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.roundRect(2, 2, w - 4, 68, 34); ctx.fill();
  ctx.fillStyle = '#111';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 28, 37);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  sp.renderOrder = 10;
  sp.userData.aspect = w / 72;
  return sp;
}

/** Twin record id for an object: its own or its nearest ancestor's userData.twin. */
export function twinIdOf(o) {
  for (let p = o; p; p = p.parent) if (p.userData?.twin) return p.userData.twin;
  return null;
}

/** Every record id from the object up to the root, nearest first (a pipe piece, then its spool). */
export function twinChainOf(o) {
  const ids = [];
  for (let p = o; p; p = p.parent) if (p.userData?.twin && !ids.includes(p.userData.twin)) ids.push(p.userData.twin);
  return ids;
}

export class Twin {
  constructor({ scene, camera, controls, canvas, overlay }) {
    Object.assign(this, { scene, camera, controls, canvas, overlay });
    this.data = null;
    this.root = null;
    this.meshes = new Map();       // record id -> [Mesh]
    this.selected = null;
    this.series = null;            // active series
    this.time = 0;
    this.playing = false;
    this.speed = 0.06;             // hours of data per second of replay
    this.fly = null;
    this.gauges = [];
    this.sim = null;               // motions, actors, flows, states of the sim timeline
    this.wall = 0;                 // real seconds, for walking and work animations
    this.fmt = hhmm;
    this.ray = new THREE.Raycaster();
    this._v = new THREE.Vector3();
    this._down = null;
    canvas.addEventListener('pointerdown', (e) => { this._down = [e.clientX, e.clientY]; });
    canvas.addEventListener('pointerup', (e) => {
      if (!this.data || !this._down) return;
      const moved = Math.hypot(e.clientX - this._down[0], e.clientY - this._down[1]);
      this._down = null;
      if (moved < 5) this.pick(e);
    });
    $('tw-back').onclick = () => this.select(null);
    $('tw-close').onclick = () => this.toggle(false);
    $('tw-locate').onclick = () => this.selected && this.flyTo(this.selected);
    $('tw-filter').addEventListener('input', () => this.renderList());
    $('tr-play').onclick = () => { this.playing = !this.playing; this.renderReplayState(); };
    $('tr-series').addEventListener('change', (e) => this.setSeries(+e.target.value));
    const chart = $('tr-chart');
    const scrub = (e) => {
      const r = chart.getBoundingClientRect();
      const s = this.series;
      if (!s) return;
      const f = THREE.MathUtils.clamp((e.clientX - r.left) / r.width, 0, 1);
      this.setTime(s.t[0] + f * (s.t[s.t.length - 1] - s.t[0]));
    };
    chart.addEventListener('pointerdown', (e) => { chart.setPointerCapture(e.pointerId); scrub(e); chart.onpointermove = scrub; });
    chart.addEventListener('pointerup', () => { chart.onpointermove = null; });
  }

  /** New world: index meshes by record and build the UI (hidden if the world has no twin). */
  load(meta, root) {
    this.clear();
    const data = meta.viewer.twin;
    if (!data || !Object.keys(data.records || {}).length) {
      $('b-twin').hidden = true;
      $('twin-panel').hidden = true;
      $('twin-replay').hidden = true;
      return;
    }
    this.data = data;
    this.root = root;
    this.slug = meta.slug;
    // A mesh belongs to every record up its parent chain, so a spool owns all its pieces.
    root.traverse((o) => {
      if (!o.isMesh || o.isInstancedMesh) return;
      for (const id of twinChainOf(o)) {
        if (!this.meshes.has(id)) this.meshes.set(id, []);
        this.meshes.get(id).push(o);
      }
    });
    $('b-twin').hidden = false;
    $('tw-filter').value = '';
    this.renderList();
    this.select(null);
    // Replay bar and gauges
    const sel = $('tr-series');
    sel.innerHTML = (data.series || []).map((s, i) => `<option value="${i}">${esc(s.title)}</option>`).join('');
    sel.hidden = (data.series || []).length < 2;
    for (const g of data.gauges || []) {
      const el = document.createElement('div');
      el.className = 'twin-gauge';
      el.innerHTML = `<span class="lbl">${esc(g.label)}</span><span class="val"></span>`;
      if (g.record) el.onclick = () => { this.toggle(true); this.select(g.record); };
      this.overlay.append(el);
      this.gauges.push({ ...g, el, pos: new THREE.Vector3(...g.position) });
    }
    this.loadSim(data, root);
    if (data.series?.length) this.setSeries(0);
    this.playing = !!(this.sim && this.series?.clock);     // a sim world starts running
    this.renderReplayState();
    $('twin-replay').hidden = !data.series?.length;
    $('twin-panel').hidden = false;
    $('b-twin').classList.add('on');
  }

  /** Moving material, people and document flows (harness.sim), keyed to the replay time. */
  loadSim(data, root) {
    if (!data.motions?.length && !data.actors?.length && !data.flows?.length) return;
    const V = (p) => new THREE.Vector3(...p);
    const sim = { motions: [], actors: [], flows: [], states: data.states || {} };
    for (const m of data.motions || []) {
      const node = root.getObjectByName(m.node);
      if (node) sim.motions.push({ ...m, node, keys: m.keys.map(([t, p, yaw]) => ({ t, p: V(p), yaw: THREE.MathUtils.degToRad(yaw) })) });
    }
    for (const a of data.actors || []) {
      const node = root.getObjectByName(a.node);
      if (!node) continue;
      const limb = (s) => node.getObjectByName(`${a.node}_${s}`);
      sim.actors.push({ ...a, node, shift: null, seg: 0, d: 0, dwell: 0, task: null, phase: 0,
        parts: { armL: limb('arm_l'), armR: limb('arm_r'), legL: limb('leg_l'), legR: limb('leg_r') },
        shifts: a.shifts.map((s) => ({ ...s, path: s.path.map(V) })) });
    }
    for (const f of data.flows || []) {
      const sprite = labelSprite(f.label, f.color || '#6cb6ff');
      sprite.visible = false;
      root.add(sprite);
      sim.flows.push({ ...f, sprite, a: V(f.a), b: V(f.b) });
    }
    this.sim = sim;
  }

  clear() {
    this.select(null, false);
    this.setTint(0, false);
    for (const g of this.gauges) g.el.remove();
    this.gauges = [];
    this.sim = null;
    $('twin-banner').hidden = true;
    this.meshes.clear();
    this.data = null;
    this.series = null;
    this.playing = false;
  }

  toggle(force) {
    if (!this.data) return;
    const show = force ?? $('twin-panel').hidden;
    $('twin-panel').hidden = !show;
    $('b-twin').classList.toggle('on', show);
  }

  // ---------------------------------------------------------------- picking and selection

  pick(e) {
    const r = this.canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(ndc, this.camera);
    const hits = this.ray.intersectObject(this.root, true);
    for (const h of hits) {
      if (!h.object.visible) continue;
      const chain = (h.object.isInstancedMesh ? [h.object.userData.instanceTwin?.[h.instanceId]]
        : twinChainOf(h.object)).filter((id) => id && this.data.records[id]);
      if (chain.length) { this.toggle(true); this.select(this.drill(chain)); return; }
      if (!h.object.material?.transparent) break;   // first solid thing without a record: stop
    }
    this.select(null);
  }

  /** First click picks the outermost record (the spool); clicking inside the current selection
   * goes one level deeper (the piece under the cursor). */
  drill(chain) {
    const i = chain.indexOf(this.selected);
    if (i > 0) return chain[i - 1];
    const sel = this.selected && this.data.records[this.selected];
    if (sel?.parent && chain.includes(sel.parent)) return chain[0];   // another piece of the same spool
    return chain[chain.length - 1];
  }

  select(id, render = true) {
    if (this.selected) this.highlight(this.selected, false);
    this.selected = id && this.data?.records[id] ? id : null;
    if (this.selected) this.highlight(this.selected, true);
    if (render && this.data) this.renderCard();
  }

  /** Emissive overrides are per-mesh material clones, so shared materials stay untouched. */
  emissive(mesh, color, intensity) {
    if (!mesh.userData.origMat) {
      if (!intensity) return;
      mesh.userData.origMat = mesh.material;
      mesh.material = mesh.material.clone();
    }
    if (!intensity) {
      mesh.material.dispose();
      mesh.material = mesh.userData.origMat;
      delete mesh.userData.origMat;
      return;
    }
    mesh.material.emissive?.copy(color);
    mesh.material.emissiveIntensity = intensity;
  }

  highlight(id, on) {
    for (const m of this.meshes.get(id) || []) {
      m.userData.selected = on;
      this.paint(m);
    }
  }

  paint(m) {
    if (m.userData.selected) this.emissive(m, new THREE.Color('#4aa8ff'), 0.55);
    else if (m.userData.tint) this.emissive(m, m.userData.tint, m.userData.tintLevel);
    else this.emissive(m, null, 0);
  }

  flyTo(id) {
    const meshes = this.meshes.get(id);
    if (!meshes?.length) return;
    this.root.updateMatrixWorld(true);        // moving objects may have just been placed
    const box = new THREE.Box3();
    for (const m of meshes) box.expandByObject(m);
    const center = box.getCenter(new THREE.Vector3());
    const size = Math.max(box.getSize(new THREE.Vector3()).length(), 1.5);
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    // Small things near the ground (a spool in a trench): look down more steeply, from further.
    const minUp = size < 6 ? 0.6 : 0.35;
    if (dir.y < minUp) { dir.y = minUp; dir.normalize(); }
    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    const dist = Math.max(size / 2 / Math.tan(fov / 2) * 1.15, 9);
    this.fly = { t: 0, from: [this.camera.position.clone(), this.controls.target.clone()],
      to: [center.clone().addScaledVector(dir, dist), center] };
  }

  // ---------------------------------------------------------------- side panel

  renderList() {
    const q = $('tw-filter').value.trim().toLowerCase();
    const groups = new Map();
    for (const id of this.data.order) {
      const r = this.data.records[id];
      if (id === this.data.overview) continue;
      if (r.listed === false && !q) continue;          // parts and welds: found by filtering or clicking
      const hay = `${r.title} ${r.subtitle ?? ''} ${r.fields.map((f) => f[1]).join(' ')}`.toLowerCase();
      if (q && !hay.includes(q)) continue;
      const g = r.group || 'Other';
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(r);
    }
    let html = '';
    for (const [g, rs] of groups) {
      html += `<h4>${esc(g)} <span>${rs.length}</span></h4><ul>`;
      for (const r of rs) {
        html += `<li data-id="${esc(r.id)}"><i style="background:${esc(r.color || '#6cb6ff')}"></i>` +
          `<b>${esc(r.title)}</b>${r.subtitle ? `<small>${esc(r.subtitle)}</small>` : ''}</li>`;
      }
      html += '</ul>';
    }
    $('tw-list').innerHTML = html || '<p class="note">No matching records.</p>';
    for (const li of $('tw-list').querySelectorAll('li')) {
      li.onclick = () => { this.select(li.dataset.id); this.flyTo(li.dataset.id); };
    }
  }

  renderCard() {
    const id = this.selected || this.data.overview;
    const r = id ? this.data.records[id] : null;
    $('tw-browse').hidden = !!this.selected;
    $('tw-back').hidden = !this.selected;
    $('tw-locate').hidden = !this.selected || !this.meshes.has(this.selected);
    if (!r) { $('tw-card').innerHTML = ''; return; }
    let html = `<h3>${esc(r.title)}</h3>${r.subtitle ? `<p class="sub">${esc(r.subtitle)}</p>` : ''}`;
    const parent = r.parent && this.data.records[r.parent];
    if (parent) html += `<p class="parent">Part of <a href="#" data-go="${esc(r.parent)}">${esc(parent.title)}</a></p>`;
    html += this.statusHtml(id, r);
    if (r.fields.length) {
      html += '<dl>' + r.fields.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('') + '</dl>';
    }
    for (const t of r.tables) {
      html += `<h4>${esc(t.title)}</h4><div class="tbl"><table><thead><tr>` +
        t.columns.map((c) => `<th>${esc(c)}</th>`).join('') + '</tr></thead><tbody>' +
        t.rows.map((row, i) => {
          const go = t.row_ids?.[i];
          return (go ? `<tr class="go" data-go="${esc(go)}" title="Show in 3D">` : '<tr>') +
            row.map((c) => `<td>${esc(c)}</td>`).join('') + '</tr>';
        }).join('') +
        '</tbody></table></div>';
    }
    for (const im of r.images || []) {
      const src = `worlds/${this.slug}/${im.src}`;
      html += `<h4>${esc(im.title)}</h4><a class="twin-img" href="${esc(src)}" target="_blank" rel="noopener">` +
        `<img src="${esc(src)}" alt="${esc(im.title)}" loading="lazy"></a>`;
    }
    if (r.links?.length) html += '<p class="links">' + r.links.map((l) => `<a href="${esc(l.href.startsWith('http') ? l.href : `worlds/${this.slug}/${l.href}`)}" target="_blank" rel="noopener">${esc(l.title)}</a>`).join(' · ') + '</p>';
    if (r.notes.length) html += '<ul class="notes">' + r.notes.map((n) => `<li>${esc(n)}</li>`).join('') + '</ul>';
    $('tw-card').innerHTML = html;
    $('tw-card').scrollTop = 0;
    for (const el of $('tw-card').querySelectorAll('[data-go]')) {
      el.onclick = (e) => { e.preventDefault(); this.select(el.dataset.go); this.flyTo(el.dataset.go); };
    }
  }

  /** State and document checklist of a record at the playhead (sim worlds). */
  statusHtml(id, r) {
    const state = this.stateAt(id);
    if (!state && !r.docs?.length) return '';
    let html = '';
    if (state) {
      const s = STATES[state] || { label: state, color: '#999' };
      html += `<span class="state" style="background:${s.color || '#8a8f96'}">${esc(s.label)}</span>`;
    }
    if (r.docs?.length) {
      const t = this.time;
      const got = r.docs.filter(([, dt]) => dt !== null && dt <= t + 1e-6).length;
      html += `<h4>Documents <span>${got} / ${r.docs.length}</span></h4><ul class="docs">`;
      for (const [name, dt] of r.docs) {
        const cls = dt !== null && dt <= t + 1e-6 ? 'in' : dt === null ? 'missing' : 'pending';
        const when = cls === 'in' ? this.fmt(dt) : cls === 'missing' ? 'not received' : `due ${this.fmt(dt)}`;
        html += `<li class="${cls}"><i>${cls === 'in' ? '✓' : cls === 'missing' ? '✗' : '·'}</i><span>${esc(name)}</span><small>${esc(when)}</small></li>`;
      }
      html += '</ul>';
    }
    return html;
  }

  stateAt(id, t = this.time) {
    const keys = this.sim?.states?.[id];
    if (!keys) return null;
    let s = keys[0][1];
    for (const [kt, ks] of keys) { if (kt <= t + 1e-6) s = ks; else break; }
    return s;
  }

  /** Re-render the card only when what it shows at the playhead changes (keeps its scroll). */
  refreshCard() {
    const id = this.selected || this.data.overview;
    const r = id && this.data.records[id];
    if (!r || (!r.docs?.length && !this.sim?.states?.[id])) return;
    const sig = `${this.stateAt(id)}|${(r.docs || []).filter(([, dt]) => dt !== null && dt <= this.time + 1e-6).length}`;
    if (sig === this._cardSig) return;
    this._cardSig = sig;
    const top = $('tw-card').scrollTop;
    this.renderCard();
    $('tw-card').scrollTop = top;
  }

  // ---------------------------------------------------------------- replay

  setSeries(i) {
    const s = this.data.series[i];
    this.series = s;
    const t0 = s.t[0], t1 = s.t[s.t.length - 1];
    const vmin = Math.min(0, ...s.v), vmax = Math.max(...s.v) * 1.08 || 1;
    this.vRange = s.range || [vmin, vmax];
    this.fmt = timeFormatter(s);
    this.speed = s.speed ?? 0.06;
    const X = (t) => ((t - t0) / (t1 - t0)) * 1000;
    const Y = (v) => 100 - ((v - vmin) / (vmax - vmin)) * 92 - 4;
    const pts = s.t.map((t, k) => `${X(t).toFixed(1)},${Y(s.v[k]).toFixed(1)}`).join(' ');
    let grid = '';
    const [step, major] = s.clock ? [1, 7] : [0.25, 1];      // days and weeks, or quarter hours
    for (let h = Math.ceil(t0 / step) * step; h <= t1; h += step) {
      grid += `<line x1="${X(h)}" x2="${X(h)}" y1="0" y2="100" class="${Math.abs(h / major - Math.round(h / major)) > 1e-6 ? 'g' : 'g major'}"/>`;
    }
    let ev = '';
    for (const e of s.events) {
      ev += `<line x1="${X(e.t)}" x2="${X(e.t)}" y1="0" y2="100" class="ev${e.kind === 'hold' ? ' hold' : ''}"><title>${esc(this.fmt(e.t))} ${esc(e.label)}</title></line>`;
    }
    $('tr-chart').innerHTML = `<svg viewBox="0 0 1000 100" preserveAspectRatio="none">${grid}${ev}` +
      `<polyline points="0,100 ${pts} 1000,100" class="area"/><polyline points="${pts}" class="line"/>` +
      `<line id="tr-head" x1="0" x2="0" y1="0" y2="100" class="head"/></svg>` +
      `<span class="ax lo">${hhmm(t0)}</span><span class="ax hi">${hhmm(t1)}</span>` +
      `<span class="ax top">${Math.round(vmax)} ${esc(s.unit)}</span>`;
    this.X = X;
    this.setTime(t0);
  }

  valueAt(s, t) {
    const { t: ts, v } = s;
    if (t <= ts[0]) return v[0];
    for (let k = 1; k < ts.length; k++) {
      if (t <= ts[k]) return v[k - 1] + (v[k] - v[k - 1]) * (t - ts[k - 1]) / (ts[k] - ts[k - 1]);
    }
    return v[v.length - 1];
  }

  setTime(t) {
    const s = this.series;
    if (!s) return;
    this.time = t;
    const v = this.valueAt(s, t);
    $('tr-head')?.setAttribute('x1', this.X(t));
    $('tr-head')?.setAttribute('x2', this.X(t));
    const last = s.events.filter((e) => e.t <= t + 1e-6).pop();
    const hold = s.events.find((e) => e.kind === 'hold' && e.t <= t + 1e-6 && t < (e.until ?? Infinity));
    $('tr-readout').innerHTML = `<b>${this.fmt(t)}</b> ${Math.round(v).toLocaleString()} ${esc(s.unit)}` +
      (last ? ` <small>${esc(last.label)}</small>` : '') + (hold ? ` <span class="hold">HOLD</span>` : '');
    $('twin-banner').hidden = !hold;
    if (hold) $('twin-banner').innerHTML = `⚠ ${esc(hold.label)}${hold.detail ? `<small>${esc(hold.detail)}</small>` : ''}`;
    const [lo, hi] = this.vRange;
    this.setTint((v - lo) / (hi - lo), true);
    for (const g of this.gauges) {
      const gs = this.data.series.find((x) => x.id === g.series);
      if (gs) g.el.querySelector('.val').textContent = `${this.valueAt(gs, t).toFixed(g.digits)} ${gs.unit}`;
    }
    if (this.sim) { this.applySim(t); this.refreshCard(); }
  }

  /** Place moving material, pick each person's shift, and tint records by state at time t. */
  applySim(t) {
    const sim = this.sim;
    for (const m of sim.motions) {
      const k = m.keys;
      m.node.visible = !(m.hide && t < k[0].t - 1e-6) && !(m.until !== null && m.until !== undefined && t > m.until);
      let p = k[k.length - 1].p, yaw = k[k.length - 1].yaw;
      if (t <= k[0].t) { p = k[0].p; yaw = k[0].yaw; }
      else {
        for (let i = 1; i < k.length; i++) {
          if (t <= k[i].t) {
            const f = (t - k[i - 1].t) / Math.max(k[i].t - k[i - 1].t, 1e-9);
            p = k[i - 1].p.clone().lerp(k[i].p, f);
            yaw = k[i - 1].yaw + (k[i].yaw - k[i - 1].yaw) * f;
            break;
          }
        }
      }
      m.node.position.copy(p);
      m.node.rotation.set(0, yaw, 0);
    }
    for (const a of sim.actors) {
      const shift = a.shifts.find((s) => s.start <= t && t < s.end) || null;
      a.node.visible = !!shift;
      if (shift !== a.shift) {
        a.shift = shift;
        a.seg = 0; a.d = 0; a.dwell = 0; a.task = null;
        if (shift) {
          a.node.position.copy(shift.path[0]);
          const task = shift.tasks?.['0'];
          if (task) { a.dwell = task[0]; a.task = task[1]; }
        }
      }
    }
    for (const [id, keys] of Object.entries(sim.states)) {
      let state = keys[0][1];
      for (const [kt, ks] of keys) { if (kt <= t + 1e-6) state = ks; else break; }
      const st = STATES[state] || STATES.pending;
      for (const m of this.meshes.get(id) || []) {
        m.userData.tint = st.color ? new THREE.Color(st.color) : null;
        m.userData.tintLevel = st.level;
        this.paint(m);
      }
    }
    for (const f of sim.flows) f.sprite.visible = t >= f.t0 && t <= f.t1;
  }

  /** Walk each person along their shift's path in real time; animate limbs; fly the packets. */
  updateSim(dt) {
    const sim = this.sim;
    this.wall += dt;
    const w = this.wall;
    const dir = new THREE.Vector3();
    for (const a of sim.actors) {
      const s = a.shift;
      if (!s) continue;
      const P = s.path, n = P.length, parts = a.parts;
      let moving = false;
      if (a.dwell > 0) {
        a.dwell -= dt;
        if (a.dwell <= 0) a.task = null;
      } else if (n > 1 && (s.loop || a.seg < n - 1)) {
        const from = P[a.seg], to = P[(a.seg + 1) % n];
        const len = from.distanceTo(to);
        a.d += a.speed * dt;
        a.phase += a.speed * dt * 4.2;
        moving = true;
        if (a.d >= len) {
          a.d = 0;
          a.seg = (a.seg + 1) % n;
          const task = s.tasks?.[String(a.seg)];
          if (task) { a.dwell = task[0]; a.task = task[1]; }
          if (!s.loop && a.seg === n - 1 && !task) { a.task = 'idle'; a.dwell = 1e9; }
        } else {
          a.node.position.lerpVectors(from, to, a.d / len);
          dir.subVectors(to, from);
          a.node.rotation.y = Math.atan2(-dir.z, dir.x);
        }
      }
      // Limbs: legs and arms swing while walking; tasks pose the arms with a little life in them.
      const swing = moving ? Math.sin(a.phase) : 0;
      const k = a.task;
      let aL = swing * 0.45, aR = -swing * 0.45;
      if (k === 'weld') { aL = 1.15 + Math.sin(w * 7 + a.phase) * 0.06; aR = 1.25 + Math.sin(w * 5.3) * 0.05; }
      else if (k === 'inspect') { aL = 0.35 + Math.sin(w * 1.5) * 0.08; aR = 1.5 + Math.sin(w * 2.1) * 0.05; }
      else if (k === 'carry') { aL = aR = 0.95 + Math.sin(w * 3) * 0.04; }
      else if (k === 'survey') { aL = 0.9; aR = 0.2 + Math.sin(w * 1.2) * 0.15; }
      else if (k === 'talk') { aL = Math.sin(w * 2.3 + a.phase) * 0.3; aR = 0.6 + Math.sin(w * 3.1) * 0.25; }
      else if (k === 'idle') { aL = Math.sin(w * 0.9 + a.phase) * 0.06; aR = -aL; }
      if (parts.armL) parts.armL.rotation.z = aL;
      if (parts.armR) parts.armR.rotation.z = aR;
      if (parts.legL) parts.legL.rotation.z = swing * 0.6;
      if (parts.legR) parts.legR.rotation.z = -swing * 0.6;
    }
    const t = this.time;
    for (const f of sim.flows) {
      if (!f.sprite.visible) continue;
      const u = THREE.MathUtils.clamp((t - f.t0) / Math.max(f.t1 - f.t0, 1e-9), 0, 1);
      const lift = Math.max(8, f.a.distanceTo(f.b) * 0.12);
      f.sprite.position.lerpVectors(f.a, f.b, u);
      f.sprite.position.y += Math.sin(u * Math.PI) * lift + 2.5;
      const h = f.sprite.position.distanceTo(this.camera.position) * 0.028;   // constant on screen
      f.sprite.scale.set(h * f.sprite.userData.aspect, h, 1);
    }
  }

  /** Glow the series' tint group with the value (blue at rest to orange at full). */
  setTint(f, on) {
    const s = this.series;
    if (!s?.tint_group || !this.data) return;
    f = THREE.MathUtils.clamp(f, 0, 1);
    const color = new THREE.Color('#1d6fd6').lerp(new THREE.Color('#ff7a1a'), f);
    for (const id of this.data.order) {
      if (this.data.records[id].group !== s.tint_group) continue;
      for (const m of this.meshes.get(id) || []) {
        m.userData.tint = on && f > 0.02 ? color : null;
        m.userData.tintLevel = 0.05 + 0.22 * f;   // a glow, not a repaint: textures stay readable
        this.paint(m);
      }
    }
  }

  renderReplayState() {
    $('tr-play').textContent = this.playing ? '❚❚' : '▶';
  }

  // ---------------------------------------------------------------- per frame

  update(dt) {
    if (this.fly) {
      this.fly.t = Math.min(1, this.fly.t + dt / 0.9);
      const k = this.fly.t * this.fly.t * (3 - 2 * this.fly.t);
      this.camera.position.lerpVectors(this.fly.from[0], this.fly.to[0], k);
      this.controls.target.lerpVectors(this.fly.from[1], this.fly.to[1], k);
      if (this.fly.t >= 1) this.fly = null;
    }
    if (!this.data) return;
    if (this.playing && this.series) {
      const s = this.series;
      let t = this.time + dt * this.speed;
      if (t > s.t[s.t.length - 1]) t = s.t[0];
      this.setTime(t);
    }
    if (this.sim) this.updateSim(dt);
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    for (const g of this.gauges) {
      this._v.copy(g.pos).project(this.camera);
      const visible = this._v.z < 1 && Math.abs(this._v.x) < 1.1 && Math.abs(this._v.y) < 1.1;
      g.el.hidden = !visible;
      if (visible) g.el.style.transform = `translate(${(this._v.x * 0.5 + 0.5) * w}px, ${(-this._v.y * 0.5 + 0.5) * h}px)`;
    }
  }
}
