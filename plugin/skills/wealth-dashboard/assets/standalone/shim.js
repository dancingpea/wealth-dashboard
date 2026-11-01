/* Standalone stand-in for the Dashboard type's `dash` API: datasets come from the JSON embedded in the page,
   calculations run in the browser, filters live in the address bar's hash-free memory (and localStorage). */
(function () {
  var store = JSON.parse(document.getElementById('wd-data').textContent || '{}');
  var raw = store.datasets || {};
  var defaults = store.params || {};
  var KEY = 'wealth-dashboard:params:' + (store.key || 'default');
  var params = Object.assign({}, defaults);
  try { Object.assign(params, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) { /* storage unavailable */ }
  var calcs = {}, cache = {}, listeners = [], pending = false;
  function save() { try { localStorage.setItem(KEY, JSON.stringify(params)); } catch (e) { /* storage unavailable */ } }
  function cols(rows) { return Array.isArray(rows) && rows.length ? Object.keys(rows[0]) : []; }
  function data(id) {
    if (Object.prototype.hasOwnProperty.call(raw, id)) return { status: 'ok', data: raw[id], columns: cols(raw[id]), rows: raw[id], refreshing: false, meta: [] };
    if (calcs[id]) {
      if (!Object.prototype.hasOwnProperty.call(cache, id)) {
        try {
          var ins = calcs[id].inputs.map(function (i) { var d = data(i); if (d.status !== 'ok') throw new Error('input ' + i + ' is ' + d.status); return d.data; });
          cache[id] = { ok: true, v: calcs[id].fn.apply(null, ins) };
        } catch (e) { console.error('[wealth-dashboard] calc ' + id + ' failed:', e); cache[id] = { ok: false, e: e }; }
      }
      var c = cache[id];
      return c.ok ? { status: 'ok', data: c.v, columns: cols(c.v), rows: c.v, refreshing: false, meta: [] } : { status: 'error', data: [], message: String(c.e && c.e.message), refreshing: false, meta: [] };
    }
    return { status: 'missing', data: [], columns: [], rows: [], refreshing: false, meta: [] };
  }
  function run() { pending = false; listeners.forEach(function (fn) { try { fn(); } catch (e) { console.error('[wealth-dashboard] draw failed:', e); } }); }
  function queue() { if (pending) return; pending = true; (window.requestAnimationFrame || setTimeout)(run); }
  var css = getComputedStyle(document.documentElement);
  window.dash = {
    data: data,
    calc: function (id, def) { calcs[id] = def; },
    loader: function () {},
    onData: function (fn) { listeners.push(fn); queue(); },
    params: function () { return params; },
    setParams: function (o) { Object.keys(o || {}).forEach(function (k) { if (o[k] === null || o[k] === undefined) delete params[k]; else params[k] = o[k]; }); save(); queue(); },
    resetParams: function () { params = Object.assign({}, defaults); save(); queue(); },
    setLink: function (name) { try { history.replaceState(null, '', name && name !== 'overview' ? '#' + name : location.pathname + location.search); } catch (e) { /* sandboxed */ } },
    refresh: function () { queue(); },
    colors: ['var(--wd-c1)', 'var(--wd-c2)', 'var(--wd-c3)', 'var(--wd-c4)', 'var(--wd-c5)', 'var(--wd-c6)', 'var(--wd-c7)', 'var(--wd-c8)']
  };
  var lastW = 0;
  function onResize() { var w = document.documentElement.clientWidth; if (Math.abs(w - lastW) > 2) { lastW = w; queue(); } }
  window.addEventListener('resize', onResize);
  lastW = document.documentElement.clientWidth;
  void css;
})();
