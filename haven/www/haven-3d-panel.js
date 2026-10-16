/**
 * Haven Realtime — Home Assistant custom panel adapter.
 * Keeps authentication inside Home Assistant and relays only states and
 * authorized service calls to the same-origin architectural frontend.
 */
class Haven3DPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._ready = false;
    this._areas = [];
    this._entities = [];
    this._devices = [];
    this._timer = null;
    this._onMessage = this._onMessage.bind(this);
  }
  connectedCallback() {
    if (this._frame) return;
    this.style.cssText = 'display:block;width:100%;height:100%;min-height:100vh;overflow:hidden;background:#080d15';
    const frame = document.createElement('iframe');
    frame.title = 'Haven Realtime — 3D Home Assistant';
    frame.setAttribute('allow', 'fullscreen');
    frame.style.cssText = 'width:100%;height:100%;min-height:100vh;display:block;border:0;background:#080d15';
    frame.src = '/local/haven/Haven_3D_Realtime_Ultra.html?haven_panel=1';
    this.append(frame);
    this._frame = frame;
    window.addEventListener('message', this._onMessage);
  }
  disconnectedCallback() {
    window.removeEventListener('message', this._onMessage);
    clearTimeout(this._timer);
    this._frame?.remove();
    this._frame = null;
    this._ready = false;
  }
  set hass(next) {
    this._hass = next;
    if (this._ready && !this._timer) {
      this._timer = setTimeout(() => { this._timer = null; this._sync(); }, 220);
    }
  }
  get hass() { return this._hass; }
  _post(data) {
    if (this._ready && this._frame?.contentWindow) {
      this._frame.contentWindow.postMessage(data, location.origin);
    }
  }
  _sync() {
    if (!this._hass || !this._ready) return;
    this._post({
      type: 'haven:sync',
      states: Object.values(this._hass.states || {}),
      areas: this._areas,
      entities: this._entities,
      devices: this._devices
    });
  }
  async _loadRegistries() {
    if (!this._hass?.connection?.sendMessagePromise) { this._sync(); return; }
    const types = [
      'config/area_registry/list',
      'config/entity_registry/list',
      'config/device_registry/list'
    ];
    const results = await Promise.allSettled(types.map(type => this._hass.connection.sendMessagePromise({type})));
    this._areas = results[0].status === 'fulfilled' ? results[0].value : [];
    this._entities = results[1].status === 'fulfilled' ? results[1].value : [];
    this._devices = results[2].status === 'fulfilled' ? results[2].value : [];
    this._sync();
  }
  async _onMessage(event) {
    if (event.origin !== location.origin || event.source !== this._frame?.contentWindow) return;
    const m = event.data || {};
    if (m.type === 'haven:ready') {
      this._ready = true;
      this._sync();
      await this._loadRegistries();
      return;
    }
    if (m.type === 'haven:refresh') {
      await this._loadRegistries();
      return;
    }
    if (m.type !== 'haven:call') return;
    const domains = new Set(['light','switch','fan','cover','lock','climate','media_player','input_boolean','number','scene','script']);
    const entity = String(m.entity_id || '');
    const domain = String(m.domain || '');
    if (!domains.has(domain) || !entity.startsWith(domain + '.') || !/^[a-z0-9_]+\.[a-z0-9_]+$/.test(entity)) {
      this._post({type:'haven:call_result',id:m.id,ok:false,error:'Invalid entity or domain'});
      return;
    }
    try {
      if (!this._hass?.callService) throw new Error('Home Assistant is not connected');
      await this._hass.callService(domain, String(m.service), m.data || {}, {entity_id:entity});
      this._post({type:'haven:call_result',id:m.id,ok:true});
      this._sync();
    } catch (e) {
      this._post({type:'haven:call_result',id:m.id,ok:false,error:e.message || String(e)});
    }
  }
}
customElements.define('haven-3d-panel', Haven3DPanel);
