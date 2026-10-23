/* DSA Sensitivity Calculator: page logic (inputs, sky map, charts, results). Engine: dsa-engine.js */
(function () {
  'use strict';
  var E = window.DSAETC;
  var $ = function (id) { return document.getElementById(id); };
  var state = { mode: 'survey', rfiMode: 'default', rfi: null, userRfi: null, variant: null, last: null, stale: false };
  var DATA_FILES = { rfi: 'rfi_spring_valley_extrapolated.json', rfi_measured: 'rfi_spring_valley.json', ucc: 'ucc_confusion.json', tsky: 'tsky_gsm2008.json',
    weighting: 'weighting_factors.json', mosaic_z: 'mosaic_z.json', antennas: 'antennas_enu.json', allocation: 'allocation.json',
    tsys_bandpass: 'tsys_bandpass.json', tsys_za: 'tsys_za.json', psf_uniform: 'psf_uniform.json', chr_taper: 'chr_taper.json', ne2025: 'ne2025_grid.json' };
  var DATA_BASE = (window.DSA_DATA_BASE || 'data/');
  var SCHEME_NAME = { natural: 'Natural', robust_freq: 'Robust, R = 0.46–1.94', robust_0p4: 'Robust, R = 0.4' };
  var SUM_NAME = { optimal: 'optimal summation', equal: 'equal summation' };
  var CLASS_NAME = { euclid_hsc: 'Euclid/HSC footprint', galactic: 'Galactic plane & bulge', wide: 'Wide area' };
  var IMG = window.DSA_IMG_BASE || 'img/';

  // ------------------------------------------------------------------ formatting
  function sig(x, n) {
    if (x === null || x === undefined || !isFinite(x)) return '—';
    if (x === 0) return '0';
    n = n || 3;
    var a = Math.abs(x), d = Math.max(0, n - 1 - Math.floor(Math.log10(a)));
    if (d > 6) d = 6;
    var s = x.toFixed(d);
    if (a >= 1e4) s = Math.round(x).toLocaleString('en-US');
    return s;
  }
  function sci(x, n) {
    if (!isFinite(x)) return '—';
    var e = Math.floor(Math.log10(Math.abs(x))), m = x / Math.pow(10, e);
    return m.toFixed(n === undefined ? 1 : n) + '×10<sup>' + e + '</sup>';
  }
  function noise(uJy) { // pick μJy or mJy or nJy
    if (!isFinite(uJy)) return '—';
    if (uJy >= 1000) return sig(uJy / 1000) + ' <small>mJy</small>';
    if (uJy < 0.1) return sig(uJy * 1000) + ' <small>nJy</small>';
    return sig(uJy) + ' <small>μJy</small>';
  }
  function noiseTxt(uJy) { return noise(uJy).replace(/<small>|<\/small>/g, ''); }
  function beam(b) { return sig(b.bmaj, 3) + '″ × ' + sig(b.bmin, 3) + '″'; }
  function beamC(b) { return sig(b.bmaj, 3) + '×' + sig(b.bmin, 3) + '″'; }
  function beamPA(b) { return beam(b) + (Math.abs(b.bmaj - b.bmin) > 0.01 * b.bmaj ? ', PA ' + Math.round(b.pa) + '°' : ''); }
  function tb(mK) { if (!isFinite(mK)) return '—'; return mK >= 1000 ? sig(mK / 1000) + ' K' : sig(mK) + ' mK'; }
  function hours(s) { var h = s / 3600; return h >= 10 ? sig(h, 3) + ' h' : (h >= 1 ? h.toFixed(2) + ' h' : Math.round(s / 60) + ' min'); }
  function pad(n, w) { var s = String(n); while (s.length < w) s = '0' + s; return s; }
  function raSexa(ra) {
    var h = ((ra % 360) + 360) % 360 / 15, hh = Math.floor(h), mm = Math.floor((h - hh) * 60), ss = ((h - hh) * 60 - mm) * 60;
    if (ss >= 59.95) { ss = 0; mm += 1; } if (mm >= 60) { mm = 0; hh = (hh + 1) % 24; }
    return pad(hh, 2) + 'h' + pad(mm, 2) + 'm' + (ss < 10 ? '0' : '') + ss.toFixed(1) + 's';
  }
  function decSexa(dec) {
    var s = dec < 0 ? '−' : '+', a = Math.abs(dec), d = Math.floor(a), m = Math.floor((a - d) * 60), x = ((a - d) * 60 - m) * 60;
    if (x >= 59.5) { x = 0; m += 1; } if (m >= 60) { m = 0; d += 1; }
    return s + pad(d, 2) + '°' + pad(m, 2) + '′' + pad(Math.round(x), 2) + '″';
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  // ------------------------------------------------------------------ coordinates
  function parseAngle(str, isRA) {
    var s = String(str || '').trim().replace(/[−–]/g, '-');
    if (!s) return NaN;
    var sexa = /[:hmsd°'"′″]/i.test(s) || /\d\s+\d/.test(s);
    if (!sexa) { var v = Number(s); if (!isFinite(v)) return NaN; return v; }
    var sign = /^\s*-/.test(s) ? -1 : 1;
    var parts = s.replace(/^\s*[+-]/, '').split(/[^0-9.]+/).filter(Boolean).map(Number);
    if (!parts.length || parts.some(function (p) { return !isFinite(p); })) return NaN;
    var val = parts[0] + (parts[1] || 0) / 60 + (parts[2] || 0) / 3600;
    return sign * (isRA ? val * 15 : val);
  }
  var RG = [[-0.0548755604, -0.8734370902, -0.4838350155], [0.4941094279, -0.4448296300, 0.7469822445], [-0.8676661490, -0.1980763734, 0.4559837762]];
  function toGal(ra, dec) {
    var a = ra * Math.PI / 180, d = dec * Math.PI / 180, x = [Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)];
    var g = RG.map(function (r) { return r[0] * x[0] + r[1] * x[1] + r[2] * x[2]; });
    var l = Math.atan2(g[1], g[0]) * 180 / Math.PI; if (l < 0) l += 360;
    return [l, Math.asin(Math.max(-1, Math.min(1, g[2]))) * 180 / Math.PI];
  }
  function fromGal(l, b) {
    var L = l * Math.PI / 180, B = b * Math.PI / 180, g = [Math.cos(B) * Math.cos(L), Math.cos(B) * Math.sin(L), Math.sin(B)];
    var x = [0, 1, 2].map(function (i) { return RG[0][i] * g[0] + RG[1][i] * g[1] + RG[2][i] * g[2]; });
    var ra = Math.atan2(x[1], x[0]) * 180 / Math.PI; if (ra < 0) ra += 360;
    return [ra, Math.asin(Math.max(-1, Math.min(1, x[2]))) * 180 / Math.PI];
  }
  function readPosition() {
    var ra = parseAngle($('ra').value, true), dec = parseAngle($('dec').value, false);
    var okRa = isFinite(ra), okDec = isFinite(dec) && dec >= -90 && dec <= 90;
    $('ra').setAttribute('aria-invalid', okRa ? 'false' : 'true');
    $('dec').setAttribute('aria-invalid', okDec ? 'false' : 'true');
    if (!okRa || !okDec) { $('pos-parsed').textContent = !okRa ? 'Cannot read the RA: use degrees (150.12) or hours (10:00:28.6).' : 'Dec must be between −90 and +90 degrees.'; return null; }
    ra = ((ra % 360) + 360) % 360;
    var g = toGal(ra, dec);
    $('pos-parsed').textContent = raSexa(ra) + ' ' + decSexa(dec) + ' · l ' + g[0].toFixed(2) + '°, b ' + (g[1] >= 0 ? '+' : '−') + Math.abs(g[1]).toFixed(2) + '°';
    return { ra: ra, dec: dec, l: g[0], b: g[1] };
  }

  // ------------------------------------------------------------------ theme helpers
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function isDark() {
    var bg = cssVar('--bg'), m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i.exec(bg);
    if (!m) return false;
    var r = parseInt(m[1], 16), g = parseInt(m[2], 16), b = parseInt(m[3], 16);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 110;
  }
  // ordinal blue ramp (validated sequential ramp; flips anchor in dark mode)
  var RAMP_LIGHT = ['#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b'];
  var RAMP_DARK = ['#184f95', '#1c5cab', '#256abf', '#2a78d6', '#3987e5', '#5598e7', '#6da7ec', '#86b6ef', '#9ec5f4', '#b7d3f6'];
  function epochColor(n) {
    var ramp = isDark() ? RAMP_DARK : RAMP_LIGHT;
    return ramp[Math.max(0, Math.min(ramp.length - 1, n - 2))];
  }

  // ------------------------------------------------------------------ sky map
  var MAP = { W: 720, H: 380, R: 0, cx: 0, cy: 0, dpr: 1 };
  function mollTheta(lat) {
    if (Math.abs(lat) >= Math.PI / 2 - 1e-9) return lat;
    var t = lat, k = Math.PI * Math.sin(lat);
    for (var i = 0; i < 30; i++) { var f = 2 * t + Math.sin(2 * t) - k, df = 2 + 2 * Math.cos(2 * t); var dt = f / df; t -= dt; if (Math.abs(dt) < 1e-9) break; }
    return t;
  }
  function project(ra, dec) { // RA increases to the left, 0h at center
    var lon = -(((ra + 180) % 360 + 360) % 360 - 180) * Math.PI / 180, lat = dec * Math.PI / 180, th = mollTheta(lat);
    return [MAP.cx + MAP.R * 2 * Math.SQRT2 / Math.PI * lon * Math.cos(th), MAP.cy - MAP.R * Math.SQRT2 * Math.sin(th)];
  }
  function unproject(px, py) {
    var x = (px - MAP.cx) / MAP.R, y = (MAP.cy - py) / MAP.R;
    if (Math.abs(y) > Math.SQRT2) return null;
    var th = Math.asin(y / Math.SQRT2), c = Math.cos(th);
    var lon = Math.PI * x / (2 * Math.SQRT2 * (c || 1e-9));
    if (Math.abs(lon) > Math.PI) return null;
    var lat = Math.asin(Math.max(-1, Math.min(1, (2 * th + Math.sin(2 * th)) / Math.PI)));
    var ra = -lon * 180 / Math.PI; ra = ((ra % 360) + 360) % 360;
    return [ra, lat * 180 / Math.PI];
  }
  // the map is drawn on the panel canvas and, when enlarged, on the dialog canvas (with zoom and pan)
  var MAPVIEW = { z: 1, ox: 0, oy: 0 };
  function drawMap() {
    drawMapOn($('skymap'), null, 'map-legend');
    if ($('map-dialog') && $('map-dialog').open) drawMapOn($('skymap-lg'), MAPVIEW, 'map-legend-lg');
  }
  function drawMapOn(cv, view, legendId) {
    var cssW = cv.clientWidth || 340, dpr = window.devicePixelRatio || 1;
    var cssH = view ? Math.round(Math.min(cssW * 0.53, window.innerHeight * 0.72)) : Math.round(cssW * 0.53);
    cv.style.height = cssH + 'px';
    cv.width = Math.round(cssW * dpr); cv.height = Math.round(cssH * dpr);
    var ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var baseR = Math.min((cssW - 8) / (4 * Math.SQRT2), (cssH - 8) / (2 * Math.SQRT2)), z = view ? view.z : 1;
    MAP.W = cssW; MAP.H = cssH; MAP.R = baseR * z; MAP.cx = cssW / 2 + (view ? view.ox : 0); MAP.cy = cssH / 2 + (view ? view.oy : 0);
    cv._map = { W: MAP.W, H: MAP.H, R: MAP.R, cx: MAP.cx, cy: MAP.cy, baseR: baseR };
    ctx.clearRect(0, 0, cssW, cssH);
    // sky ellipse
    ctx.beginPath(); ctx.ellipse(MAP.cx, MAP.cy, 2 * Math.SQRT2 * MAP.R, Math.SQRT2 * MAP.R, 0, 0, 2 * Math.PI);
    ctx.fillStyle = cssVar('--surface'); ctx.fill();
    var al = E.data().allocation, v = state.variant || al.default_variant, surf = cssVar('--surface');
    Object.keys(al.tiles).forEach(function (k) {
      var t = al.tiles[k], n = t.epochs[v];
      // RA 180 deg is the map edge: split tiles that cross it, and keep a tile that ends (or starts) exactly there on
      // its own side; otherwise RA 180 projects to the opposite edge and the tile is drawn across the whole row
      var e0 = t.ra0 === 180 ? 180.001 : t.ra0, e1 = t.ra1 === 180 ? 179.999 : t.ra1;
      var spans = (e0 < 180 && e1 > 180) ? [[e0, 179.999], [180.001, e1]] : [[e0, e1]];
      spans.forEach(function (sp) {
        ctx.beginPath();
        var d1 = Math.min(t.dec1, 89.99), steps = 10, i, p;
        for (i = 0; i <= steps; i++) { p = project(sp[0] + (sp[1] - sp[0]) * i / steps, t.dec0); if (i === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]); }
        for (i = steps; i >= 0; i--) { p = project(sp[0] + (sp[1] - sp[0]) * i / steps, d1); ctx.lineTo(p[0], p[1]); }
        ctx.closePath(); ctx.fillStyle = epochColor(n); ctx.fill();
        ctx.lineWidth = 0.6; ctx.strokeStyle = surf; ctx.stroke();
      });
    });
    // graticule
    ctx.lineWidth = 0.5; ctx.strokeStyle = cssVar('--line-strong'); ctx.setLineDash([]);
    [-60, -30, 0, 30, 60].forEach(function (d) {
      ctx.beginPath(); for (var r = 0; r <= 360; r += 3) { var p = project(r === 360 ? 180.0001 : (r + 180.0001) % 360, d); if (r === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]); } ctx.globalAlpha = .6; ctx.stroke(); ctx.globalAlpha = 1;
    });
    // Galactic plane and |b| = 10 deg
    [[0, [], 1.3], [10, [2, 3], 0.9], [-10, [2, 3], 0.9]].forEach(function (g) {
      ctx.beginPath(); ctx.setLineDash(g[1]); ctx.lineWidth = g[2]; ctx.strokeStyle = cssVar('--s2');
      var prev = null;
      for (var l = 0; l <= 360; l += 1) {
        var eq = fromGal(l, g[0]), p = project(eq[0], eq[1]);
        if (prev && Math.abs(p[0] - prev[0]) > MAP.R) ctx.moveTo(p[0], p[1]); else if (!prev) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
        prev = p;
      }
      ctx.stroke();
    });
    ctx.setLineDash([]);
    // outline
    ctx.beginPath(); ctx.ellipse(MAP.cx, MAP.cy, 2 * Math.SQRT2 * MAP.R, Math.SQRT2 * MAP.R, 0, 0, 2 * Math.PI);
    ctx.lineWidth = 1; ctx.strokeStyle = cssVar('--line-strong'); ctx.stroke();
    // RA labels
    ctx.font = '500 10px ' + (cssVar('--font-mono') || 'monospace'); ctx.textAlign = 'center'; ctx.lineJoin = 'round';
    var label = function (txt, x, y) {   // text with a halo in the surface color, legible over tiles
      ctx.lineWidth = 3; ctx.strokeStyle = cssVar('--surface'); ctx.strokeText(txt, x, y); ctx.fillStyle = cssVar('--ink-2'); ctx.fillText(txt, x, y);
    };
    [0, 60, 120, 240, 300].forEach(function (ra) { var p = project(ra, 0); label((ra / 15) + 'h', p[0], p[1] - 4); });
    ctx.textAlign = 'left';
    [60, 30, -30].forEach(function (d) { var p = project(179.99, d); label((d > 0 ? '+' : '−') + Math.abs(d) + '°', p[0] + 3, p[1] + 3); });
    // marker
    var pos = readPosition();
    if (pos) {
      var p = project(pos.ra, pos.dec);
      ctx.beginPath(); ctx.arc(p[0], p[1], 6, 0, 2 * Math.PI); ctx.lineWidth = 3; ctx.strokeStyle = cssVar('--surface'); ctx.stroke();
      ctx.beginPath(); ctx.arc(p[0], p[1], 6, 0, 2 * Math.PI); ctx.lineWidth = 1.8; ctx.strokeStyle = cssVar('--ink'); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(p[0] - 11, p[1]); ctx.lineTo(p[0] - 7, p[1]); ctx.moveTo(p[0] + 7, p[1]); ctx.lineTo(p[0] + 11, p[1]);
      ctx.moveTo(p[0], p[1] - 11); ctx.lineTo(p[0], p[1] - 7); ctx.moveTo(p[0], p[1] + 7); ctx.lineTo(p[0], p[1] + 11); ctx.stroke();
    }
    drawLegend(legendId);
  }
  function drawLegend(id) {
    var al = E.data().allocation, v = state.variant || al.default_variant, counts = {};
    Object.keys(al.tiles).forEach(function (k) { var n = al.tiles[k].epochs[v]; counts[n] = (counts[n] || 0) + 1; });
    var ns = Object.keys(counts).map(Number).sort(function (a, b) { return a - b; });
    $(id || 'map-legend').innerHTML = '<span style="margin-right:4px">Epochs</span>' + ns.map(function (n) {
      return '<span class="lg-item"><span class="sw" style="background:' + epochColor(n) + '"></span>' + n + '</span>';
    }).join('') + '<span class="lg-item"><span class="sw" style="background:none;border-top:2px solid ' + cssVar('--s2') + ';height:0;width:14px"></span>Galactic plane</span>';
  }
  function tileInfo(ra, dec) {
    var calc = new E.Calculator({ variant: state.variant }), e = calc.epochsAt(ra, dec, state.variant);
    return e;
  }
  // hover tooltip and click-to-select on a map canvas; on the enlarged map also wheel zoom and drag to pan
  function mapEvents(cv, tip, view) {
    function locate(ev) {
      var r = cv.getBoundingClientRect(), x = (ev.clientX - r.left), y = (ev.clientY - r.top);
      if (cv._map) { MAP.W = cv._map.W; MAP.H = cv._map.H; MAP.R = cv._map.R; MAP.cx = cv._map.cx; MAP.cy = cv._map.cy; }
      return { x: x, y: y, sky: unproject(x, y) };
    }
    var drag = null;
    cv.addEventListener('mousemove', function (ev) {
      if (drag && view) {
        var dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
        if (drag.moved) { view.ox = drag.ox + dx; view.oy = drag.oy + dy; tip.hidden = true; drawMapOn(cv, view, 'map-legend-lg'); return; }
      }
      var L = locate(ev);
      if (!L.sky) { tip.hidden = true; return; }
      var e = tileInfo(L.sky[0], L.sky[1]);
      tip.innerHTML = raSexa(L.sky[0]).slice(0, 6) + ' ' + (L.sky[1] >= 0 ? '+' : '−') + Math.abs(L.sky[1]).toFixed(1) + '° · ' +
        (e[1] ? e[0] + ' epochs · ' + CLASS_NAME[e[1]['class']] : 'outside survey');
      tip.style.left = (L.x + cv.offsetLeft) + 'px'; tip.style.top = (L.y + cv.offsetTop) + 'px'; tip.hidden = false;
    });
    cv.addEventListener('mouseleave', function () { tip.hidden = true; drag = null; });
    if (view) {
      cv.addEventListener('mousedown', function (ev) { drag = { x: ev.clientX, y: ev.clientY, ox: view.ox, oy: view.oy, moved: false }; });
      window.addEventListener('mouseup', function () { setTimeout(function () { drag = null; }, 0); });
      cv.addEventListener('wheel', function (ev) {
        ev.preventDefault();
        var r = cv.getBoundingClientRect();
        zoomMap(ev.deltaY < 0 ? 1.25 : 0.8, ev.clientX - r.left, ev.clientY - r.top);
      }, { passive: false });
    }
    cv.addEventListener('click', function (ev) {
      if (drag && drag.moved) return;
      var L = locate(ev); if (!L.sky) return;
      $('ra').value = L.sky[0].toFixed(2); $('dec').value = (L.sky[1] >= 0 ? '+' : '') + L.sky[1].toFixed(2);
      tip.hidden = true; readPosition(); drawMap(); calculate();
    });
  }
  // zoom the enlarged map by factor f about the canvas point (mx, my), keeping the sky point there fixed
  function zoomMap(f, mx, my) {
    var cv = $('skymap-lg'), g = cv._map; if (!g) return;
    var z = Math.min(Math.max(MAPVIEW.z * f, 1), 8); f = z / MAPVIEW.z;
    if (mx === undefined) { mx = g.W / 2; my = g.H / 2; }
    var cx = mx - (mx - g.cx) * f, cy = my - (my - g.cy) * f;
    MAPVIEW.z = z; MAPVIEW.ox = z === 1 ? 0 : cx - g.W / 2; MAPVIEW.oy = z === 1 ? 0 : cy - g.H / 2;
    drawMapOn(cv, MAPVIEW, 'map-legend-lg');
  }
  function setupMap() {
    mapEvents($('skymap'), $('map-tip'), null);
    mapEvents($('skymap-lg'), $('map-tip-lg'), MAPVIEW);
    var dlg = $('map-dialog');
    $('map-expand').addEventListener('click', function () {
      $('map-dialog-plan').textContent = E.data().allocation.variants[state.variant || E.data().allocation.default_variant].label;
      MAPVIEW.z = 1; MAPVIEW.ox = 0; MAPVIEW.oy = 0;
      if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
      drawMap();
    });
    $('map-close').addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (ev) { if (ev.target === dlg) dlg.close(); });   // click on the backdrop
    $('map-zoom-in').addEventListener('click', function () { zoomMap(1.5); });
    $('map-zoom-out').addEventListener('click', function () { zoomMap(1 / 1.5); });
    $('map-zoom-reset').addEventListener('click', function () { MAPVIEW.z = 1; MAPVIEW.ox = 0; MAPVIEW.oy = 0; drawMap(); });
    window.addEventListener('resize', function () { if (dlg.open) drawMap(); });
  }

  // ------------------------------------------------------------------ SVG charts
  var NS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs, parent) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  // SVG text with <sub>…</sub> subscripts (dy shifts, since baseline-shift is not supported everywhere)
  function svgText(t, s) {
    var dy = 0;
    String(s).split(/(<sub>.*?<\/sub>)/).forEach(function (p) {
      if (!p) return;
      var m = /^<sub>(.*)<\/sub>$/.exec(p), a = m ? { dy: 3 - dy, 'font-size': '78%' } : (dy ? { dy: -dy } : {});
      el('tspan', a, t).textContent = m ? m[1] : p;
      dy = m ? 3 : 0;
    });
  }
  function logTicks(lo, hi) {
    var t = [], e0 = Math.floor(Math.log10(lo)), e1 = Math.ceil(Math.log10(hi));
    for (var e = e0; e <= e1; e++) [1, 2, 5].forEach(function (m) { var v = m * Math.pow(10, e); if (v >= lo * 0.999 && v <= hi * 1.001) t.push(v); });
    if (t.length > 7) t = t.filter(function (v) { return Math.abs(Math.log10(v) - Math.round(Math.log10(v))) < 1e-9 || v / Math.pow(10, Math.floor(Math.log10(v))) === 3; });
    return t;
  }
  /* opts: {width,height,xmin,xmax,xticks,xlabel,ylog,ymin,ymax,ylabel,yfmt,series:[{name,color,pts:[[x,y]],markers,label}],hover:fn(i)->html, xs:[..]} */
  function lineChart(opts) {
    var wrap = document.createElement('div'); wrap.className = 'chart';
    if (opts.series.length > 1) {
      var lg = document.createElement('div'); lg.className = 'legend';
      lg.innerHTML = opts.series.map(function (s) { return '<span><i style="background:' + s.color + '"></i>' + esc(s.name) + '</span>'; }).join('') + (opts.legendExtra || '');
      wrap.appendChild(lg);
    }
    var W = opts.width || 640, H = opts.height || 240, m = { l: opts.leftPad || 62, r: opts.rightPad || 70, t: 10, b: 38 };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': opts.aria || 'chart' }, wrap);
    var X = opts.xlog ? function (x) { return m.l + (Math.log10(x) - Math.log10(opts.xmin)) / (Math.log10(opts.xmax) - Math.log10(opts.xmin)) * (W - m.l - m.r); }
      : function (x) { return m.l + (x - opts.xmin) / (opts.xmax - opts.xmin) * (W - m.l - m.r); };
    var Y = opts.ylog ? function (y) { return m.t + (Math.log10(opts.ymax) - Math.log10(y)) / (Math.log10(opts.ymax) - Math.log10(opts.ymin)) * (H - m.t - m.b); }
      : function (y) { return m.t + (opts.ymax - y) / (opts.ymax - opts.ymin) * (H - m.t - m.b); };
    var yt = opts.yticks || (opts.ylog ? logTicks(opts.ymin, opts.ymax) : [opts.ymin, (opts.ymin + opts.ymax) / 2, opts.ymax]);
    yt.forEach(function (v) {
      el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: cssVar('--grid'), 'stroke-width': 1 }, svg);
      var t = el('text', { x: m.l - 6, y: Y(v) + 3.5, 'text-anchor': 'end', 'class': 'ax-label' }, svg); t.textContent = (opts.yfmt || sig)(v);
    });
    (opts.xticks || []).forEach(function (v) {
      el('line', { x1: X(v), x2: X(v), y1: H - m.b, y2: H - m.b + 4, stroke: cssVar('--axis') }, svg);
      var t = el('text', { x: X(v), y: H - m.b + 16, 'text-anchor': 'middle', 'class': 'ax-label' }, svg); t.textContent = opts.xfmt ? opts.xfmt(v) : v;
    });
    el('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: cssVar('--axis') }, svg);
    var xt = el('text', { x: (m.l + W - m.r) / 2, y: H - 4, 'text-anchor': 'middle', 'class': 'ax-title' }, svg); svgText(xt, opts.xlabel || '');
    var ytl = el('text', { x: 11, y: (m.t + H - m.b) / 2, 'text-anchor': 'middle', 'class': 'ax-title', transform: 'rotate(-90 11 ' + ((m.t + H - m.b) / 2) + ')' }, svg); svgText(ytl, opts.ylabel || '');
    (opts.bands || []).forEach(function (b) {
      el('rect', { x: X(b[0]), y: m.t, width: Math.max(1, X(b[1]) - X(b[0])), height: H - m.t - m.b, fill: cssVar('--accent-soft'), opacity: 0.7 }, svg);
    });
    (opts.refLines || []).forEach(function (r) {
      el('line', { x1: m.l, x2: W - m.r, y1: Y(r.y), y2: Y(r.y), stroke: r.color, 'stroke-width': 1.2, 'stroke-dasharray': '5 4' }, svg);
      var t = el('text', { x: W - m.r + 6, y: Y(r.y) + 4, 'class': 'direct-label' }, svg); t.textContent = r.label;
    });
    (opts.vLines || []).forEach(function (r) {
      if (r.x < opts.xmin || r.x > opts.xmax) return;
      el('line', { x1: X(r.x), x2: X(r.x), y1: m.t, y2: H - m.b, stroke: cssVar('--muted'), 'stroke-width': 1, 'stroke-dasharray': '4 3' }, svg);
      var t = el('text', { x: X(r.x) + 4, y: m.t + 11, 'class': 'direct-label' }, svg); t.textContent = r.label;
    });
    var labels = [];
    opts.series.forEach(function (s) {
      // zeros are real values on a linear axis; non-finite values (e.g. fully flagged channels) break the line
      var valid = function (p) { return isFinite(p[1]) && (opts.ylog ? (p[1] > 0 && p[1] >= opts.ymin * 0.5) : true); };
      var pts = s.pts.filter(valid);
      if (!pts.length) return;
      var d = '', pen = false;
      s.pts.forEach(function (p) {
        if (!valid(p)) { pen = false; return; }
        d += (pen ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(Math.min(Math.max(p[1], opts.ymin), opts.ymax)).toFixed(1) + ' ';
        pen = true;
      });
      if (s.area) {
        el('path', { d: d + ' L' + X(pts[pts.length - 1][0]).toFixed(1) + ' ' + (H - m.b) + ' L' + X(pts[0][0]).toFixed(1) + ' ' + (H - m.b) + ' Z', fill: s.color, opacity: 0.18, stroke: 'none' }, svg);
      }
      el('path', { d: d, fill: 'none', stroke: s.color, 'stroke-width': s.width || 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
      if (s.markers) pts.forEach(function (p) {
        el('circle', { cx: X(p[0]), cy: Y(p[1]), r: 4, fill: s.color, stroke: cssVar('--surface'), 'stroke-width': 2 }, svg);
      });
      if (s.label) { var lp = pts[pts.length - 1]; labels.push({ x: X(lp[0]) + 8, y: Y(lp[1]) + 4, text: s.label }); }
    });
    (opts.marks || []).forEach(function (mk) {
      if (!(isFinite(mk.y) && mk.y > 0) || mk.x < opts.xmin || mk.x > opts.xmax) return;
      var cy = Y(Math.min(Math.max(mk.y, opts.ymin), opts.ymax));
      el('circle', { cx: X(mk.x), cy: cy, r: 5, fill: mk.color, stroke: cssVar('--surface'), 'stroke-width': 2 }, svg);
    });
    labels.sort(function (a, b) { return a.y - b.y; });
    for (var li = 1; li < labels.length; li++) if (labels[li].y - labels[li - 1].y < 13) labels[li].y = labels[li - 1].y + 13;
    labels.forEach(function (lb) { var t = el('text', { x: lb.x, y: lb.y, 'class': 'direct-label' }, svg); t.textContent = lb.text; });
    if (opts.hover) {
      var cross = el('line', { y1: m.t, y2: H - m.b, stroke: cssVar('--muted'), 'stroke-width': 1, 'stroke-dasharray': '3 3', visibility: 'hidden' }, svg);
      var hit = el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: 'transparent' }, svg);
      var tip = document.createElement('div'); tip.className = 'chart-tip'; tip.hidden = true; wrap.appendChild(tip);
      var xs = opts.xs;
      var move = function (ev) {
        var r = svg.getBoundingClientRect(), sx = (ev.clientX - r.left) * W / r.width, fr = (sx - m.l) / (W - m.l - m.r);
        var xv = opts.xlog ? Math.log10(opts.xmin) + fr * (Math.log10(opts.xmax) - Math.log10(opts.xmin)) : opts.xmin + fr * (opts.xmax - opts.xmin);
        var best = 0, bd = Infinity; xs.forEach(function (x, i) { var d = Math.abs((opts.xlog ? Math.log10(x) : x) - xv); if (d < bd) { bd = d; best = i; } });
        cross.setAttribute('x1', X(xs[best])); cross.setAttribute('x2', X(xs[best])); cross.setAttribute('visibility', 'visible');
        tip.innerHTML = opts.hover(best); tip.hidden = false;
        var px = X(xs[best]) * r.width / W, left = px + 14;
        if (left + tip.offsetWidth > r.width) left = px - tip.offsetWidth - 14;
        tip.style.left = Math.max(0, left) + 'px'; tip.style.top = '28px';
      };
      hit.addEventListener('mousemove', move);
      hit.addEventListener('mouseleave', function () { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); });
    }
    return wrap;
  }

  // ------------------------------------------------------------------ RFI
  function currentRfi() {
    if (state.rfiMode === 'none') return E.rfiNone();
    if (state.rfiMode === 'measured') return E.rfiMeasured();
    if (state.rfiMode === 'upload' && state.userRfi) return state.userRfi;
    return E.rfiDefault();
  }
  function drawRfi() {
    var rfi = currentRfi(), box = $('rfi-plot'); box.innerHTML = '';
    // with the extrapolated default, show the measured profile it is scaled from
    var ref = state.rfiMode === 'default' ? E.rfiMeasured() : null;
    var pts = [], rpts = [], xs = [];
    for (var f = 700; f <= 2000; f += 1) {
      pts.push([f, E.occAt(rfi, f) * 100]); xs.push(f);
      if (ref) rpts.push([f, E.occAt(ref, f) * 100]);
    }
    var series = [{ name: ref ? 'Extrapolated' : 'Occupancy', color: cssVar('--s1'), pts: pts, area: true, width: 1.4 }];
    if (ref) series.push({ name: 'Measured', color: cssVar('--s2'), pts: rpts, width: 1.1 });
    var ch = lineChart({ width: 360, height: 150, xmin: 700, xmax: 2000, xticks: [800, 1200, 1600, 2000], xlabel: 'Frequency (MHz)',
      ymin: 0, ymax: 100, yticks: [0, 50, 100], ylabel: 'Occupancy %', yfmt: function (v) { return v; }, rightPad: 10,
      bands: [[1388, 1422]], series: series, xs: xs,
      hover: function (i) {
        var h = '<div class="tt-h">' + xs[i] + ' MHz</div><div class="tt-r"><span>' + series[0].name + '</span><span>' + pts[i][1].toFixed(1) + '%</span></div>';
        if (ref) h += '<div class="tt-r"><span>Measured</span><span>' + rpts[i][1].toFixed(1) + '%</span></div>';
        return h;
      },
      aria: 'RFI occupancy versus frequency' });
    ch.querySelector('svg').classList.add('rfi-plot');
    box.appendChild(ch);
    var loss = function (p) { return 100 * (1 - E.usableBwHz(p, 700, 2002, 0) / 1302e6); };
    $('rfi-summary').textContent = loss(rfi).toFixed(1) + '% of 0.70–2.00 GHz flagged' + (ref ? ' (measured: ' + loss(ref).toFixed(1) + '%)' : '') + '.';
  }
  function parseCsv(text) {
    var f = [], o = [];
    text.split(/\r?\n/).forEach(function (line) {
      if (!line.trim() || /^\s*#/.test(line)) return;
      var p = line.split(/[,;\t ]+/).filter(Boolean).map(Number);
      if (p.length >= 2 && isFinite(p[0]) && isFinite(p[1])) { f.push(p[0]); o.push(p[1]); }
    });
    if (f.length < 2) throw new Error('Found fewer than two numeric rows. Use two columns: frequency in MHz, occupancy (0–1 or %).');
    var fmin = Math.min.apply(null, f), fmax = Math.max.apply(null, f);
    if (fmax < 600 || fmin > 2100) throw new Error('Frequencies should be in MHz and overlap 700–2000 MHz.');
    return E.makeRfiProfile(f, o, 'Uploaded profile');
  }

  // ------------------------------------------------------------------ inputs -> calculation
  function num(id, def) { var v = parseFloat($(id).value); return isFinite(v) ? v : def; }
  function readParams() {
    return {
      tsys_zenith_K: $('p-tsys').value.trim() === '' ? null : num('p-tsys', null), n_ant: Math.round(num('p-nant', 1650)),
      dish_diameter_m: num('p-dish', 6.155), extra_loss_percent: num('p-loss', 0), confusion_beta: parseInt($('p-beta').value, 10), smooth_subtract_sources: $('smooth-subtract').checked,
      galactic_noise: $('p-gal').checked, el_min_deg: num('p-elmin', 20), ha_max_h: num('p-hamax', 2),
      td_track_s: num('td-track', 1260), td_scattering: $('td-scat').value,
      psr_period_ms: num('psr-p', 500), psr_width_ms: num('psr-w', 15), psr_dm: $('psr-dm').value.trim() === '' ? null : num('psr-dm', null),
      psr_flux_mJy: num('psr-s', 0.02), psr_nu_ref_MHz: num('psr-nu', 1400), psr_alpha: num('psr-alpha', -1.6), psr_snr: num('psr-snr', 10),
      psr_targeted_center_MHz: $('psr-center').value === 'custom' ? num('psr-center-custom', 1400) : parseFloat($('psr-center').value),
      psr_untargeted_beam_arcsec: readBeams(),
      frb_dm: num('frb-dm', 500), frb_width_ms: num('frb-w', 1), frb_snr: num('frb-snr', 10), frb_max_dm: num('frb-maxdm', 5000),
      hi_widths_kms: readWidths(),
      pta_period_ms: num('pta-p', 4), pta_width_ms: num('pta-w', 0.2), pta_dm: num('pta-dm', 20), pta_flux_mJy: num('pta-s', 1),
      pta_nu_ref_MHz: num('pta-nu', 1400), pta_alpha: num('pta-alpha', -1.6), pta_snr: num('pta-snr', 10)
    };
  }
  // untargeted beam FWHM per band: empty = frequency-scaled default; one value applies to all bands
  function readBeams() {
    var v = $('psr-beams').value.split(/[,;\s]+/).filter(Boolean).map(Number);
    if (!v.length || v.some(function (x) { return !(x > 0); })) return null;
    while (v.length < 3) v.push(v[v.length - 1]);
    return v.slice(0, 3);
  }
  // HI line widths (km/s) for the mass limits: up to five positive values, sorted
  function readWidths() {
    var v = $('hi-widths').value.split(/[,;\s]+/).filter(Boolean).map(Number).filter(function (x) { return x > 0 && isFinite(x); });
    v = v.filter(function (x, i) { return v.indexOf(x) === i; }).sort(function (a, b) { return a - b; }).slice(0, 5);
    return v.length ? v : [50, 200, 500];
  }
  function readInputs() {
    var pos = readPosition(); if (!pos) return null;
    var depth = document.querySelector('input[name="depth"]:checked').value;
    var prods = Array.prototype.map.call(document.querySelectorAll('input[name="prod"]:checked'), function (c) { return c.value; });
    return { mode: state.mode, ra: pos.ra, dec: pos.dec, l: pos.l, b: pos.b, depth: depth, n_epochs: Math.max(1, Math.round(num('n-epochs', 3))),
      hours: Math.max(0.05, num('hours', 4)), weighting: state.mode === 'survey' ? $('survey-weighting').value : $('weighting').value,
      smooth_arcsec: Math.max(0, num('smooth', 0)), products: prods, variant: state.variant };
  }
  function setStale(on) {
    state.stale = on;
    var s = $('status'); if (!s) return;
    s.className = 'status' + (on ? ' stale' : '');
    s.textContent = on ? 'Inputs changed: press Calculate' : 'Up to date';
  }
  function calculate() {
    var inp = readInputs();
    if (!inp) { setStale(true); return; }
    var btn = $('calc-btn'); btn.disabled = true; btn.textContent = 'Calculating…';
    setTimeout(function () {
      try {
        var params = readParams(), rfi = currentRfi();
        var calc = new E.Calculator({ params: params, rfi: rfi, variant: state.variant });
        var res = calc.calculate(inp);
        if (inp.mode === 'survey' && inp.depth !== 'single' && res.continuum) {
          var one = calc.calculate({ mode: 'survey', ra: inp.ra, dec: inp.dec, depth: 'single', products: ['continuum'], variant: state.variant });
          res._single_epoch = one.continuum ? one.continuum.fc : null;
        }
        state.last = { inp: inp, res: res };
        var open = openPanels();
        render(inp, res);
        restorePanels(open);
        setStale(false);
      } catch (err) {
        $('results').innerHTML = '<div class="panel warn">Calculation failed: ' + esc(err.message) + '</div>';
        if (window.console) console.error(err);
      }
      btn.disabled = false; btn.textContent = 'Calculate';
    }, 20);
  }

  // ------------------------------------------------------------------ rendering
  function tile(label, value, sub, hero, tip) {
    return '<div class="tile' + (hero ? ' hero' : '') + '"><span class="t-label">' + lc(label) + (tip ? qm(tip) : '') + '</span><span class="t-val">' + value + '</span>' + (sub ? '<span class="t-sub">' + sub + '</span>' : '') + '</div>';
  }
  // a tile with two equally weighted values (e.g. S/N and the detection limit)
  function tile2(label, v1, c1, v2, c2, hero, tip) {
    return '<div class="tile tile2' + (hero ? ' hero' : '') + '"><span class="t-label">' + lc(label) + (tip ? qm(tip) : '') + '</span><div class="t-pair"><div><span class="t-val">' + v1 + '</span><span class="t-sub">' + c1 + '</span></div><div><span class="t-val">' + v2 + '</span><span class="t-sub">' + c2 + '</span></div></div></div>';
  }
  function subH(text, tip) { return '<p class="sub-h">' + lc(text) + (tip ? qm(tip) : '') + '</p>'; }
  function productCard(id, title, guide, thumb, bodyHtml) {
    var th = thumb.indexOf('<svg') === 0 ? thumb.replace('<svg', '<svg class="thumb"') : '<img class="thumb" src="' + IMG + thumb + '" alt="" loading="lazy">';
    // collapsed at first; panels the reader opened stay open when the results are recalculated
    return '<details class="panel product" id="' + id + '"><summary class="product-head">' + th + '<div class="product-title"><h3>' + title + qm(guide.tip) + '</h3><a class="guide-link" href="#' + guide.anchor + '">Info</a></div><span class="chev" aria-hidden="true"></span></summary><div class="product-body">' + bodyHtml + '</div></details>';
  }
  var ICON_PSR = '<svg viewBox="0 0 64 64" role="img" aria-label="Pulse train" style="background:#0a1522"><path d="M4 44h9l3-24 3 24h9l3-24 3 24h9l3-24 3 24h9" fill="none" stroke="#f0a24a" stroke-width="2.2" stroke-linejoin="round"/><path d="M4 52h56" stroke="#3a5a78" stroke-width="1"/></svg>';

  function render(inp, r) {
    var out = [], o = r.observation, sys = r.system;
    // ---- summary
    var head = inp.mode === 'survey' ? 'Survey products at ' : 'Targeted observation of ';
    var s = '<div class="panel summary"><div class="summary-head"><h2>' + head + '<span class="mono">' + raSexa(inp.ra) + ' ' + decSexa(inp.dec) + '</span></h2><span class="status" id="status">Up to date</span></div>';
    if (o.observable === false) {
      s += '<div class="warn">' + esc(r.warnings.join(' ')) + '</div></div>';
      var tdOnly = [s];
      if (r.pulsar) tdOnly.push(renderPsr(inp, r));
      if (r.frb) tdOnly.push(renderFrb(inp, r));
      if (r.pta) tdOnly.push(renderPta(inp, r));
      $('results').innerHTML = tdOnly.join('');
      if (r.pulsar) mountPsrChart(r);
      if (r.frb) mountFrbChart(r);
      return;
    }
    s += '<dl class="kv">';
    s += '<div><dt>Position</dt><dd>RA ' + inp.ra.toFixed(3) + '°, Dec ' + (inp.dec >= 0 ? '+' : '−') + Math.abs(inp.dec).toFixed(3) + '°<span class="sub">l ' + inp.l.toFixed(2) + '°, b ' + inp.b.toFixed(2) + '° · transit elevation ' + o.el_transit.toFixed(1) + '°</span></dd></div>';
    if (inp.mode === 'survey') {
      var t = o.tile, vlab = E.data().allocation.variants[t.variant].label.split(':')[0];
      s += '<div><dt>Survey tile</dt><dd>' + t.tile + ' · ' + CLASS_NAME[t['class']] + '<span class="plan-chip">' + esc(vlab) + '</span><span class="sub">' + o.epochs_full + ' epochs in the full survey</span></dd></div>';
      s += '<div><dt>Integration</dt><dd>' + o.n_epochs + ' × 21 min per pointing<span class="sub">' + 'beam-weighted ' + o.effective_epochs_1350.toFixed(2) + ' epochs' + (inp.depth === 'full' ? ' from overlapping tiles' : '') + '; ' + hours(o.t_eff_1350_s) + ' effective at 1.35 GHz</span></dd></div>';
    } else {
      s += '<div><dt>Integration</dt><dd>' + hours(o.total_time_s) + ' on source<span class="sub">' + o.n_transits + ' transit' + (o.n_transits > 1 ? 's' : '') + ' of ±' + o.ha_half_h.toFixed(2) + ' h HA; lowest elevation ' +
        (90 - E.zenithAngle(o.ha_half_h * 15, inp.dec, o.lat)).toFixed(1) + '°</span></dd></div>';
    }
    s += '<div><dt>Performance (full band)' + qm('System temperature, and the system equivalent flux density (SEFD) of one antenna, over 0.70–2.00 GHz (unflagged channels) at this position at transit. Lower is more sensitive.') + '</dt><dd>T<sub>sys</sub> ' + sys.tsys_band_K.toFixed(1) + ' K · SEFD ' + Math.round(sys.sefd_band_Jy).toLocaleString('en-US') + ' Jy per antenna</dd></div>';
    s += '<div><dt>Usable band' + qm('Fraction of 0.70–2.00 GHz not lost to RFI (the RFI profile below, plus any extra data loss set in Advanced settings). Every product, imaging and time-domain, uses the same unflagged channels; each panel lists the usable bandwidth of its own windows or bands.') + '</dt><dd>' + (100 * sys.usable_band_fraction).toFixed(1) + '% of 0.70–2.00 GHz<span class="sub">' + esc(r.inputs.rfi_profile) + '</span></dd></div>';
    var w = r.weighting;
    if (w) s += '<div><dt>Image weighting' + qm(w.auto ? (inp.mode === 'survey' ? 'Each survey tile uses the weighting that gives the lowest total noise in its final image. The Continuum panel compares all six schemes.' : 'The weighting with the lowest total noise for this observation. The Continuum panel compares all six schemes.') : 'The weighting you selected. The Continuum panel compares all six schemes.') + '</dt><dd>' + SCHEME_NAME[w.imaging] + '<span class="sub">' + SUM_NAME[w.summation] + (w.auto ? ' · chosen automatically' : '') + '</span></dd></div>';
    s += '</dl>';
    r.warnings.forEach(function (m) { s += '<div class="warn">' + esc(m) + '</div>'; });
    s += '</div>';
    out.push(s);
    var depthLabel = inp.mode === 'survey' ? (o.n_epochs === o.epochs_full && inp.depth === 'full' ? 'full survey, ' + o.n_epochs + ' epochs' : o.n_epochs + ' epoch' + (o.n_epochs > 1 ? 's' : '')) : hours(o.total_time_s);

    if (r.continuum) out.push(renderContinuum(inp, r, depthLabel));
    if (r.line) out.push(renderLine(inp, r, depthLabel));
    if (r.polarization) out.push(renderPol(inp, r, depthLabel));
    if (r.frb) out.push(renderFrb(inp, r));
    if (r.pulsar) out.push(renderPsr(inp, r));
    if (r.pta) out.push(renderPta(inp, r));
    out.push('<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><button class="btn btn-ghost" type="button" id="copy-json">Copy all results as JSON</button><span class="hint" id="copy-msg"></span></div>');
    $('results').innerHTML = out.join('');
    // charts
    if (r.continuum) mountContinuumChart(r);
    if (r.polarization) mountPolChart(r);
    if (r.pulsar) mountPsrChart(r);
    if (r.frb) mountFrbChart(r);
    $('copy-json').addEventListener('click', function () {
      var txt = JSON.stringify(state.last.res, function (k, v) { return (typeof v === 'number' && !isFinite(v)) ? String(v) : v; }, 1);
      var done = function (ok) { $('copy-msg').textContent = ok ? 'Copied ' + Math.round(txt.length / 1024) + ' kB of JSON.' : 'Copy was blocked here; select the text below instead.'; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(function () { done(true); }, function () { fallbackCopy(txt); done(false); });
      else { fallbackCopy(txt); done(false); }
    });
  }
  // open product panels (and their open inner sections), so a recalculation keeps the reader's place
  function openPanels() {
    return Array.prototype.map.call(document.querySelectorAll('#results details[open]'), function (d) {
      var p = d.closest('details.product');
      return { id: d.id || (p ? p.id + '|' + Array.prototype.indexOf.call(p.querySelectorAll('details'), d) : '') };
    }).filter(function (x) { return x.id; });
  }
  function restorePanels(list) {
    list.forEach(function (x) {
      var k = x.id.split('|'), d = $(k[0]);
      if (d && k.length > 1) d = d.querySelectorAll('details')[+k[1]];
      if (d) d.open = true;
    });
  }
  function fallbackCopy(txt) {
    var ta = document.createElement('textarea'); ta.value = txt; ta.style.width = '100%'; ta.style.height = '160px'; ta.className = 'mono';
    $('results').appendChild(ta); ta.focus(); ta.select();
  }

  function weightingCompare(w) {
    if (!w || !w.comparison) return '';
    return '<details><summary style="cursor:pointer;font-size:.8rem;color:var(--accent)">Compare all six weighting schemes at this position</summary><div class="table-wrap" style="margin-top:8px"><table class="data cmp-table"><thead><tr><th>Weighting</th><th>Thermal</th><th>Confusion</th><th>Total</th><th>ν<sub>eff</sub></th><th>Beam</th></tr></thead><tbody>' +
          w.comparison.map(function (c) {
            var isSel = c.imaging === w.imaging && c.summation === w.summation;
            return '<tr' + (isSel ? ' class="em"' : '') + '><td class="txt">' + SCHEME_NAME[c.imaging] + ' · ' + SUM_NAME[c.summation] + '</td><td>' + noiseTxt(c.thermal_uJy) + '</td><td>' + noiseTxt(c.confusion_uJy) + '</td><td>' + noiseTxt(c.total_uJy) + '</td><td>' + Math.round(c.nu_eff_MHz) + ' MHz</td><td>' + beam(c.psf) + '</td></tr>';
          }).join('') + '</tbody></table></div></details>';
  }
  function renderContinuum(inp, r, depthLabel) {
    var c = r.continuum, fc = c.fc, b = '';
    b += '<div class="tiles">' +
      tile('Full-band noise', noise(fc.total_uJy) + '<small>/beam</small>', depthLabel + ' · thermal ⊕ confusion', true, 'The 1σ noise of the full-band (0.7–2.0 GHz) image: receiver noise and confusion from faint sources, added in quadrature.') +
      tile('Thermal', noise(fc.thermal_uJy), 'Stokes I and V') +
      tile('Confusion', noise(fc.confusion_uJy), 'Stokes I (V negligible)', false, 'Noise from many faint sources overlapping within the beam. It does not decrease with integration time.') +
      tile('Resolution', beam(fc.psf), 'PA ' + Math.round(fc.psf.pa) + '°') +
      tile('Effective freq.', Math.round(fc.nu_eff_MHz) + '<small>MHz</small>', 'weighted over 10 windows') +
      tile('Brightness temp.', tb(fc.tb_thermal_mK), '1σ thermal, native beam', false, 'The thermal noise expressed as a surface brightness.') + '</div>';
    var extra = [];
    if (r._single_epoch) extra.push('One epoch: <b class="mono">' + noiseTxt(r._single_epoch.total_uJy) + '</b> total (' + noiseTxt(r._single_epoch.thermal_uJy) + ' thermal)');
    if (c.single_pointing) extra.push('one 21-min pointing at the beam center, no mosaicking: <b class="mono">' + noiseTxt(c.single_pointing.thermal_uJy) + '</b> thermal');
    if (extra.length) b += '<p class="note">' + extra.join('; ') + '.</p>';
    if (c.smoothed) {
      var sm = c.smoothed, sx = sm.subtraction;
      b += '<div class="subpanel"><h4>Smoothed to ' + sm.target_arcsec + '″ (natural weighting, optimal summation)</h4><div class="tiles">' +
        tile('Thermal', noise(sm.thermal_uJy) + '<small>/beam</small>', 'noise ×' + sig(Math.min.apply(null, sm.noise_factors), 2) + '–' + sig(Math.max.apply(null, sm.noise_factors), 2) + ' vs native') +
        tile('Confusion', noise(sm.confusion_uJy), sx.applied ? 'after subtracting sources &gt; ' + noiseTxt(sx.limit_uJy) : 'no source subtraction') +
        tile('T<sub>b</sub> thermal', tb(sm.tb_thermal_mK), '1σ at ' + Math.round(sm.nu_eff_MHz) + ' MHz') +
        tile('T<sub>b</sub> incl. confusion', tb(sm.tb_total_mK), sx.applied ? 'without subtraction: ' + tb(sx.tb_total_unsubtracted_mK) : 'with subtraction: ' + tb(sx.tb_total_subtracted_mK)) +
        '</div></div>';
    }
    b += '<div>' + subH('Noise across the band') + '<div id="cont-chart"></div></div>';
    b += '<div class="table-wrap"><table class="data"><thead><tr><th>Window (MHz)</th><th>Unflagged</th><th>t<sub>eff</sub></th><th>Thermal</th><th>Confusion</th><th>Total</th><th>Beam</th><th>T<sub>b</sub> (1σ)</th></tr></thead><tbody>' +
      c.windows.map(function (w) {
        return '<tr><td>' + w.f_lo_MHz.toFixed(0) + '–' + w.f_hi_MHz.toFixed(0) + '</td><td>' + w.bw_usable_MHz.toFixed(1) + ' MHz</td><td>' + hours(w.t_eff_s) + '</td>' +
          '<td>' + noiseTxt(w.thermal_uJy) + '</td><td>' + noiseTxt(w.confusion_uJy) + '</td><td>' + noiseTxt(w.total_uJy) + '</td><td>' + beamC(w.psf) + '</td><td>' + tb(w.tb_thermal_mK) + '</td></tr>';
      }).join('') +
      '<tr class="em"><td class="txt">Full band (FC)</td><td>' + (1302 * r.system.usable_band_fraction).toFixed(0) + ' MHz</td><td></td><td>' + noiseTxt(fc.thermal_uJy) + '</td><td>' + noiseTxt(fc.confusion_uJy) + '</td><td>' + noiseTxt(fc.total_uJy) + '</td><td>' + beamC(fc.psf) + '</td><td>' + tb(fc.tb_thermal_mK) + '</td></tr>' +
      '</tbody></table></div>';
    b += weightingCompare(r.weighting);
    b += '<div>' + subH('6-second snapshot images (Stokes I/V, primary-beam center)', 'Images made every 6 s within each pointing, for transient searches.') + '<div class="table-wrap"><table class="data"><thead><tr><th>Band</th><th>Range (MHz)</th><th>Thermal</th><th>Confusion (I)</th><th>Beam</th></tr></thead><tbody>' +
      c.snapshots_6s.map(function (sn) { return '<tr' + (sn.label === 'Full band' ? ' class="em"' : '') + '><td class="txt">' + sn.label + '</td><td>' + sn.f_lo_MHz.toFixed(0) + '–' + sn.f_hi_MHz.toFixed(0) + '</td><td>' + noiseTxt(sn.thermal_uJy) + '</td><td>' + noiseTxt(sn.confusion_uJy) + '</td><td>' + beam(sn.psf) + '</td></tr>'; }).join('') +
      '</tbody></table></div></div>';
    return productCard('p-continuum', 'Continuum', { anchor: 'guide-continuum', tip: 'Noise and resolution of the continuum images: ten 130-MHz windows, the full-band image and 6-s snapshots.' }, 'thumb-continuum.jpg', b);
  }
  function mountContinuumChart(r) {
    var c = r.continuum, xs = c.windows.map(function (w) { return w.f_center_MHz; });
    var all = [];
    c.windows.forEach(function (w) { all.push(w.thermal_uJy, w.confusion_uJy, w.total_uJy); });
    all.push(c.fc.total_uJy);
    var lo = Math.min.apply(null, all.filter(function (v) { return v > 0; })), hi = Math.max.apply(null, all);
    var ymin = Math.pow(10, Math.floor(Math.log10(lo * 0.8) * 2) / 2), ymax = Math.pow(10, Math.ceil(Math.log10(hi * 1.25) * 2) / 2);
    var ch = lineChart({ width: 720, height: 260, xmin: 700, xmax: 2002, xticks: [800, 1000, 1200, 1400, 1600, 1800, 2000], xlabel: 'Frequency (MHz)',
      ylog: true, ymin: ymin, ymax: ymax, ylabel: 'μJy / beam', rightPad: 92, xs: xs,
      series: [
        { name: 'Thermal', color: cssVar('--s1'), pts: c.windows.map(function (w) { return [w.f_center_MHz, w.thermal_uJy]; }), markers: true, label: 'Thermal' },
        { name: 'Confusion', color: cssVar('--s2'), pts: c.windows.map(function (w) { return [w.f_center_MHz, w.confusion_uJy]; }), markers: true, label: 'Confusion' },
        { name: 'Total', color: cssVar('--s3'), pts: c.windows.map(function (w) { return [w.f_center_MHz, w.total_uJy]; }), markers: true, label: 'Total', labelDy: -8 }],
      refLines: [{ y: c.fc.total_uJy, color: cssVar('--ink-2'), label: 'Full band' }],
      hover: function (i) {
        var w = c.windows[i];
        return '<div class="tt-h">' + w.f_lo_MHz.toFixed(0) + '–' + w.f_hi_MHz.toFixed(0) + ' MHz</div>' +
          '<div class="tt-r"><span><i style="background:' + cssVar('--s1') + '"></i>Thermal</span><span>' + noiseTxt(w.thermal_uJy) + '</span></div>' +
          '<div class="tt-r"><span><i style="background:' + cssVar('--s2') + '"></i>Confusion</span><span>' + noiseTxt(w.confusion_uJy) + '</span></div>' +
          '<div class="tt-r"><span><i style="background:' + cssVar('--s3') + '"></i>Total</span><span>' + noiseTxt(w.total_uJy) + '</span></div>' +
          '<div class="tt-r"><span>Beam</span><span>' + beam(w.psf) + '</span></div>';
      }, aria: 'Continuum noise per frequency window: thermal, confusion and total' });
    $('cont-chart').appendChild(ch);
  }

  function renderLine(inp, r, depthLabel) {
    var L = r.line, b = '', za = L.ZA.channels[0], zb = L.ZB.channels[0];
    var ws = inpWidths(r), w0 = ws.indexOf(200) >= 0 ? 200 : ws[Math.floor((ws.length - 1) / 2)];
    // with smoothing, the headline tiles quote the smoothed cubes (a source unresolved at the smoothed beam)
    var zaS = za.smoothed, zbS = zb.smoothed, sm = zaS ? ' at ' + zaS.target_arcsec + '″' : '';
    var zaV = zaS || za, zbV = zbS || zb;
    var m50 = (zaS ? zaS.mhi_limits : za.mhi_limits).filter(function (m) { return m.D_Mpc === 50 && m.width_kms === w0; })[0];
    b += '<div class="tiles">' +
      tile('Zoom A per channel' + sm, sig(zaV.sigma_mJy) + '<small>mJy/beam</small>', sig(za.dv_kms, 3) + ' km s⁻¹ at 1420 MHz' + (zaS ? '; native ' + sig(za.sigma_mJy) + ' mJy' : ''), true) +
      tile('Zoom B per channel' + sm, sig(zbV.sigma_mJy) + '<small>mJy/beam</small>', sig(zb.dv_kms, 2) + ' km s⁻¹' + (zbS ? '; native ' + sig(zb.sigma_mJy) + ' mJy' : '')) +
      tile('5σ M<sub>HI</sub> at 50 Mpc' + sm, sci(m50.mhi_5sigma_Msun, 1) + '<small>M☉</small>', w0 + ' km s⁻¹ line, ' + (zaS ? 'unresolved at ' + zaS.target_arcsec + '″' : 'unresolved'), false,
        'The smallest HI mass detectable at 5σ at 50 Mpc with a ' + w0 + ' km/s line, for a galaxy unresolved at ' + (zaS ? 'the smoothed resolution' : 'the native resolution') + ' (line widths are set in Advanced settings).') +
      tile('5σ N<sub>HI</sub>' + (zaS ? sm : ', native'), sci(zaV.nhi_5sigma_cm2, 1) + '<small>cm⁻²</small>', 'over 20 km s⁻¹ at ' + beam(zaS ? zaS.psf : za.psf), false, 'The faintest HI column density detectable at 5σ over 20 km/s, for emission filling the beam.') + '</div>';
    b += '<div class="two-col">';
    ['ZB', 'ZA'].forEach(function (key) {
      var bd = L[key], ch = bd.channels[0];
      b += '<div class="subpanel"><div><h4>' + bd.label + '</h4><span class="meta">' + bd.nchan.toLocaleString('en-US') + ' × ' + bd.chan_kHz + ' kHz · ' + bd.f_lo_MHz + '–' + bd.f_hi_MHz + ' MHz · v ' + Math.round(bd.v_range_kms[0]) + ' to +' + Math.round(bd.v_range_kms[1]) + ' km s⁻¹</span></div><dl class="mini-kv">' +
        '<dt>Velocity resolution</dt><dd>' + sig(ch.dv_kms, 3) + ' km s⁻¹</dd>' +
        '<dt>σ per channel</dt><dd>' + sig(ch.sigma_mJy) + ' mJy/beam</dd>' +
        '<dt>T<sub>b</sub> per channel (1σ)</dt><dd>' + sig(ch.tb_K) + ' K</dd>' +
        '<dt>5σ N<sub>HI</sub> (20 km s⁻¹)</dt><dd>' + sci(ch.nhi_5sigma_cm2, 1) + ' cm⁻²</dd>' +
        '<dt>Beam</dt><dd>' + beamPA(ch.psf) + '</dd>' +
        (ch.smoothed ? '<dt>Smoothed to ' + ch.smoothed.target_arcsec + '″: σ</dt><dd>' + sig(ch.smoothed.sigma_mJy) + ' mJy/beam</dd>' +
          '<dt>T<sub>b</sub> per channel at ' + ch.smoothed.target_arcsec + '″ (1σ)</dt><dd>' + sig(ch.smoothed.tb_K) + ' K</dd>' +
          '<dt>5σ N<sub>HI</sub> at ' + ch.smoothed.target_arcsec + '″ (20 km s⁻¹)</dt><dd>' + sci(ch.smoothed.nhi_5sigma_cm2, 1) + ' cm⁻²</dd>' : '') +
        '</dl>';
      if (key === 'ZA') {
        b += '<div class="table-wrap"><table class="data"><thead><tr><th>5σ M<sub>HI</sub> (M☉)' + (ch.smoothed ? ', native beam' : '') + '</th>' + inpWidths(r).map(function (W) { return '<th>' + W + ' km s⁻¹</th>'; }).join('') + '</tr></thead><tbody>' +
          r.inputs.params.hi_distances_Mpc.map(function (D) {
            return '<tr><td>' + D + ' Mpc</td>' + inpWidths(r).map(function (W) { var m = ch.mhi_limits.filter(function (x) { return x.D_Mpc === D && x.width_kms === W; })[0]; return '<td>' + sci(m.mhi_5sigma_Msun, 1) + '</td>'; }).join('') + '</tr>';
          }).join('') + '</tbody></table></div>';
      }
      b += '</div>';
    });
    b += '</div>';
    var NL = L.NL;
    b += '<div class="subpanel"><div><h4>' + NL.label + '</h4><span class="meta">' + NL.nchan.toLocaleString('en-US') + ' × ' + NL.chan_kHz + ' kHz · 700–1429 MHz · z ≤ ' + NL.z_range[1].toFixed(2) + '</span></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>z</th><th>ν (MHz)</th><th>Δv (km s⁻¹)</th><th>σ / chan.</th><th>T<sub>b</sub> (1σ)</th><th>Beam</th>' +
      inpWidths(r).map(function (W) { return '<th>M<sub>HI</sub> · ' + W + '</th>'; }).join('') + (NL.channels[0].smoothed ? '<th>σ at ' + NL.channels[0].smoothed.target_arcsec + '″</th>' : '') + '</tr></thead><tbody>' +
      NL.channels.map(function (ch) {
        return '<tr><td>' + ch.z.toFixed(2) + '</td><td>' + ch.freq_MHz.toFixed(1) + '</td><td>' + sig(ch.dv_kms, 3) + '</td><td>' + sig(ch.sigma_mJy * 1000) + ' μJy</td><td>' + sig(ch.tb_K) + ' K</td><td>' + beam(ch.psf) + '</td>' +
          inpWidths(r).map(function (W) { var m = ch.mhi_limits.filter(function (x) { return x.width_kms === W; })[0]; return '<td>' + (m ? sci(m.mhi_5sigma_Msun, 1) : '—') + '</td>'; }).join('') +
          (ch.smoothed ? '<td>' + sig(ch.smoothed.sigma_mJy * 1000) + ' μJy</td>' : '') + '</tr>';
      }).join('') + '</tbody></table></div></div>';
    return productCard('p-line', 'Spectral line (HI)', { anchor: 'guide-spectral-line-hi', tip: 'Noise per channel in the three HI cubes, with HI column-density and mass limits.' }, 'thumb-line.jpg', b);
  }
  function inpWidths(r) { return r.inputs.params.hi_widths_kms; }

  function renderPol(inp, r, depthLabel) {
    var P = r.polarization, b = '', ch14 = P.channels[2];
    b += '<div class="tiles">' +
      tile('Band-averaged Q, U', noise(P.band_qu_sigma_uJy) + '<small>/beam</small>', depthLabel, true, 'Noise in a Stokes Q or U image averaged over the whole band (each channel weighted by 1/σ²). Rotation-measure synthesis with the same weights has the same noise in its Faraday-depth spectrum.') +
      tile('Per 2.6-MHz channel', noise(ch14.sigma_uJy), 'at ' + Math.round(ch14.freq_MHz) + ' MHz') +
      tile('RMSF width', sig(P.rmsf_fwhm_rad_m2, 3) + '<small>rad m⁻²</small>', 'FWHM in Faraday depth', false, 'Resolution in Faraday depth: two sources whose rotation measures differ by less than this blend together. Set by the range of λ² across the band.') +
      tile('Largest Faraday-depth scale', sig(P.max_scale_rad_m2, 3) + '<small>rad m⁻²</small>', 'extent of a recoverable structure', false, 'The widest structure in Faraday depth (emission spread over a range of rotation measures, as in a magneto-ionic screen) that the band can recover. It is not the largest rotation measure; see the next box.') +
      tile('Largest detectable |RM|', Math.round(P.max_rm_rad_m2) + '<small>rad m⁻²</small>', 'set by the 700-MHz channels', false, 'The largest rotation measure, of either sign, that can be measured before Faraday rotation within one 2.6-MHz channel depolarizes the signal (50% sensitivity), set by the lowest-frequency channels. Higher-frequency channels allow larger values.') + '</div>';
    b += '<div>' + subH('Noise per 2.6-MHz channel (Q, U, V)') + '<div id="pol-chart"></div></div>';
    b += '<div class="table-wrap"><table class="data"><thead><tr><th>Channel (MHz)</th><th>σ Q, U, V</th><th>Confusion (I)</th><th>Beam</th><th>T<sub>b</sub> (1σ)</th>' + (P.channels[0].smoothed ? '<th>σ at ' + P.channels[0].smoothed.target_arcsec + '″</th><th>T<sub>b</sub> at ' + P.channels[0].smoothed.target_arcsec + '″</th>' : '') + '</tr></thead><tbody>' +
      P.channels.map(function (c) {
        return '<tr><td>' + c.freq_MHz.toFixed(1) + '</td><td>' + noiseTxt(c.sigma_uJy) + '</td><td>' + noiseTxt(c.confusion_I_uJy) + '</td><td>' + beam(c.psf) + '</td><td>' + tb(c.tb_mK) + '</td>' +
          (c.smoothed ? '<td>' + noiseTxt(c.smoothed.sigma_uJy) + '</td><td>' + tb(c.smoothed.tb_mK) + '</td>' : '') + '</tr>';
      }).join('') + '</tbody></table></div>';
    return productCard('p-pol', 'Polarization', { anchor: 'guide-polarization', tip: 'Noise in the full-Stokes cubes and the rotation-measure synthesis parameters.' }, 'thumb-pol.jpg', b);
  }
  function mountPolChart(r) {
    var P = r.polarization, pts = P.spectrum.filter(function (s) { return isFinite(s[1]); }), xs = pts.map(function (p) { return p[0]; });
    var vals = pts.map(function (p) { return p[1]; }).sort(function (a, b) { return a - b; });
    var ymin = Math.pow(10, Math.floor(Math.log10(vals[0] * 0.8) * 2) / 2), ymax = Math.pow(10, Math.ceil(Math.log10(vals[Math.floor(vals.length * 0.98)] * 2.5) * 2) / 2);
    var ch = lineChart({ width: 720, height: 200, xmin: 700, xmax: 2002, xticks: [800, 1000, 1200, 1400, 1600, 1800, 2000], xlabel: 'Frequency (MHz)',
      ylog: true, ymin: ymin, ymax: ymax, ylabel: 'μJy / beam', rightPad: 16, xs: xs,
      series: [{ name: 'σ per channel', color: cssVar('--s1'), pts: pts, width: 1.4 }],
      hover: function (i) { return '<div class="tt-h">' + pts[i][0].toFixed(1) + ' MHz</div><div class="tt-r"><span>σ Q, U, V</span><span>' + noiseTxt(pts[i][1]) + '</span></div>'; },
      aria: 'Polarization noise per channel versus frequency' });
    $('pol-chart').appendChild(ch);
  }

  // ------------------------------------------------------------------ time domain (Chronoscope)
  function ms(x) { if (!isFinite(x)) return '—'; return x >= 1 ? sig(x, 3) + ' ms' : (x >= 1e-3 ? sig(x * 1e3, 3) + ' μs' : '<1 μs'); }
  function us(x) { if (!isFinite(x)) return '—'; return x >= 1000 ? sig(x / 1000, 3) + ' ms' : (x >= 1 ? sig(x, 3) + ' μs' : sig(x * 1000, 3) + ' ns'); }
  function smin(row) { return row.searched === false ? 'not searched' : noiseTxt(row.smin_uJy); }
  function s14(row) { return row.searched === false ? '—' : noiseTxt(row.s1400_min_uJy); }
  function mhz(v) { return String(Number(v.toFixed(2))); }
  function x3(v) { return '×' + (isFinite(v) ? v.toFixed(3) : '—'); }
  function tdContext(r, prop) {
    var t = r.time_domain;
    return '<dl class="kv">' +
      '<div><dt>Track' + qm('The pulsar and FRB products assume a track of this length centered on transit: the on-source time in targeted mode, the track length input in survey mode.') + '</dt><dd>' + hours(t.track_s) + ' centered on transit<span class="sub">' + (t.n_transits > 1 ? t.n_transits + ' transits of ±' + t.ha_half_h.toFixed(2) + ' h' : '±' + (t.ha_half_h >= 1 ? t.ha_half_h.toFixed(2) + ' h' : (t.ha_half_h * 60).toFixed(1) + ' min') + ' of hour angle') + ' · confusion correlation time ' + (t.tau_c_s ? sig(t.tau_c_s, 3) + ' s' : '—') + '</span></dd></div>' +
      '<div><dt>System' + qm('The same system model as the imaging products: the measured system-temperature bandpass, its zenith-angle dependence and Galactic emission, with data loss from the RFI profile. Usable fraction of each Chronoscope band.') + '</dt><dd>η ' + t.aperture_efficiency + ' · usable B1 ' + (100 * t.usable_fraction.B1).toFixed(0) + '%, B2 ' + (100 * t.usable_fraction.B2).toFixed(0) + '%, B3 ' + (100 * t.usable_fraction.B3).toFixed(0) + '%<span class="sub">' + esc(r.inputs.rfi_profile) + ' · T<sub>sys</sub>(ν) bandpass, spillover and atmosphere with zenith angle, Galactic emission</span></dd></div>' +
      (prop || '') + '</dl>';
  }
  function renderPsr(inp, r) {
    var S = r.pulsar, I = S.inputs, pr = S.propagation, b = '';
    var sel = S.targeted.filter(function (x) { return x.selected; })[0] || S.targeted[0];
    var unt = S.untargeted.filter(function (x) { return x.searched; }).sort(function (a, c) { return c.snr - a.snr; })[0];
    b += '<div class="tiles">' +
      tile2('Targeted search · ' + mhz(sel.center_MHz) + ' MHz', sel.searched ? sig(sel.snr, 3) : '—', 'S/N of this pulsar', noise(sel.smin_uJy), I.snr + 'σ S<sub>min</sub> at the band', true,
        'Signal-to-noise ratio of the input pulsar, and the faintest pulsar like it detectable at the threshold, in a full-array beam pointed at a known source.') +
      tile2('Untargeted search' + (unt ? ' · ' + unt.band : ''), unt ? sig(unt.snr, 3) : '—', unt ? 'S/N of this pulsar' : 'period not searched', unt ? noise(unt.s1400_min_uJy) : '—', I.snr + 'σ S<sub>min</sub> at 1.4 GHz', false,
        'The same for the search of 200,000 tapered beams tiling each pointing, in the band where this pulsar has the highest S/N.') +
      tile2('Targeted timing · ' + mhz(sel.center_MHz) + ' MHz', sig(sel.snr, 3), 'S/N of this pulsar', us(sel.toa_us), 'σ<sub>TOA</sub> for the track', false,
        'Pulse arrival-time precision from one track with the targeted beam.') + '</div>';
    var propKv = '<div><dt>Pulsar' + qm('The input pulsar (period, intrinsic width, DM), and its distance and scattering time from the scattering model along this line of sight.') + '</dt><dd>P ' + mhz(I.period_ms) + ' ms · W ' + mhz(I.width_ms) + ' ms · DM ' + sig(I.dm, 4) + (I.dm_default ? ' (½ Galactic)' : '') + '<span class="sub">' + (pr.dist_kpc === null ? 'no distance' : sig(pr.dist_kpc, 3) + ' kpc') + ' · scattering ' + ms(pr.tau_1GHz_ms) + ' at 1 GHz (' + (pr.model === 'cordes22' ? 'τ–DM relation' : 'NE2025') + ')</span></dd></div>';
    b += tdContext(r, propKv);
    b += '<div class="table-wrap"><table class="data"><thead><tr><th>Product</th><th>Δν · t<sub>samp</sub></th><th>Usable</th><th>Beam</th><th>S/N</th><th>S<sub>min</sub></th><th>at 1.4 GHz</th><th>W<sub>eff</sub></th><th>σ<sub>TOA</sub></th><th>Quant. · taper · conf. · self-noise</th></tr></thead><tbody>' +
      S.untargeted.map(function (x) {
        return '<tr><td class="txt" title="' + x.f_lo_MHz + '–' + x.f_hi_MHz + ' MHz">Untargeted ' + x.band + '</td><td>' + sig(x.chan_kHz, 4) + ' kHz · ' + x.tsamp_ms + ' ms</td><td>' + x.bw_usable_MHz.toFixed(0) + ' MHz</td><td>' + sig(x.beam_arcsec, 3) + '″</td><td class="strong">' + (x.searched ? sig(x.snr, 3) : '—') + '</td><td class="strong">' + smin(x) + '</td><td>' + s14(x) + '</td><td>' + ms(x.weff.weff_ms) + '</td><td>—</td><td>' + x3(x.losses.quantization) + ' · ' + x3(1 / x.losses.taper) + ' · ' + x3(x.losses.confusion) + ' · ' + x3(x.losses.self_noise) + '</td></tr>';
      }).join('') +
      S.targeted.map(function (x) {
        return '<tr' + (x.selected ? ' class="em"' : '') + '><td class="txt" title="' + mhz(x.f_lo_MHz) + '–' + mhz(x.f_hi_MHz) + ' MHz">Targeted ' + mhz(x.center_MHz) + (x.preset ? '' : ' (custom)') + '</td><td>' + sig(x.chan_kHz, 4) + ' kHz · ' + x.tsamp_ms + ' ms</td><td>' + x.bw_usable_MHz.toFixed(0) + ' MHz</td><td>voltage</td><td class="strong">' + (x.searched ? sig(x.snr, 3) : '—') + '</td><td class="strong">' + smin(x) + '</td><td>' + s14(x) + '</td><td>' + ms(x.weff.weff_ms) + '</td><td class="strong">' + us(x.toa_us) + '</td><td>' + x3(x.losses.quantization) + ' · — · ' + x3(x.losses.confusion) + ' · ' + x3(x.losses.self_noise) + '</td></tr>';
      }).join('') +
      '</tbody></table></div>';
    b += '<div>' + subH('S<sub>min</sub> against period (' + I.snr + 'σ, duty cycle ' + sig(100 * S.curves.duty_cycle, 2) + '%, DM ' + sig(I.dm, 4) + ')', 'The faintest detectable pulsar as a function of period for each search, at the DM of the input pulsar and with its duty cycle (intrinsic width / period) held fixed. The dots mark the input pulsar.') + '<div id="psr-chart"></div></div>';
    b += '<details><summary style="cursor:pointer;font-size:.8rem;color:var(--accent)">Pulse width, untargeted beams and scattering</summary>' +
      '<div class="table-wrap" style="margin-top:8px"><table class="data"><thead><tr><th>At band center</th><th>W<sub>int</sub></th><th>t<sub>samp</sub></th><th>t<sub>DM</sub></th><th>τ<sub>sc</sub></th><th>W<sub>eff</sub></th></tr></thead><tbody>' +
      S.untargeted.concat(S.targeted).map(function (x) {
        var w = x.weff, lab = x.band ? 'Untargeted ' + x.band + ', ' + x.f_center_MHz : 'Targeted ' + mhz(x.f_center_MHz);
        return '<tr><td class="txt">' + lab + ' MHz</td><td>' + ms(w.w_int_ms) + '</td><td>' + ms(w.t_samp_ms) + '</td><td>' + ms(w.t_dm_ms) + '</td><td>' + ms(w.tau_ms) + '</td><td>' + ms(w.weff_ms) + '</td></tr>';
      }).join('') + '</tbody></table></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Untargeted beams</th><th>FWHM</th><th>Natural beam</th><th>Noise ×</th><th>Sidelobes ×</th><th>N<sub>b</sub></th><th>Sky covered</th><th>of 2.42 deg²</th><th>of PB FWHM</th></tr></thead><tbody>' +
      S.untargeted.map(function (x) {
        return '<tr><td class="txt">' + x.band + (x.beam_note ? ' (' + esc(x.beam_note) + ')' : '') + '</td><td>' + sig(x.beam_arcsec, 3) + '″</td><td>' + sig(x.beam_natural_arcsec, 3) + '″</td><td>' + sig(x.losses.taper, 3) + '</td><td>' + sig(x.sidelobe_ratio, 3) + '</td><td>' + x.n_beams.toLocaleString('en-US') + '</td><td>' + sig(x.area_deg2, 3) + ' deg²</td><td>' + (100 * x.frac_unique_area).toFixed(0) + '%</td><td>' + (100 * x.frac_pb_fwhm).toFixed(0) + '%</td></tr>';
      }).join('') + '</tbody></table></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Scattering at band center</th><th>B1 (930 MHz)</th><th>B2 (1410 MHz)</th><th>B3 (1800 MHz)</th></tr></thead><tbody><tr><td class="txt">τ<sub>sc</sub> (' + (pr.model === 'cordes22' ? 'τ–DM relation' : 'NE2025') + ')</td><td>' + ms(pr.tau_bands_ms.B1) + '</td><td>' + ms(pr.tau_bands_ms.B2) + '</td><td>' + ms(pr.tau_bands_ms.B3) + '</td></tr></tbody></table></div>' +
      '</details>';
    return productCard('p-psr', 'Chronoscope: pulsars', { anchor: 'guide-chronoscope-pulsars-and-pulsar-timing', tip: 'Detection S/N and limits for the untargeted and targeted pulsar searches, and targeted timing, for the pulsar described in Advanced settings.' }, ICON_PSR, b);
  }
  var ICON_PTA = '<svg viewBox="0 0 64 64" role="img" aria-label="Folded pulse profile" style="background:#0a1522"><path d="M6 46h16c3 0 4-3 6-12s3-18 4-18 2 9 4 18 3 12 6 12h16" fill="none" stroke="#6fb6ff" stroke-width="2.2" stroke-linejoin="round"/><path d="M6 52h52" stroke="#3a5a78" stroke-width="1"/><path d="M32 12v6" stroke="#f0a24a" stroke-width="2"/></svg>';
  function renderPta(inp, r) {
    var T = r.pta, I = T.inputs, pr = T.propagation, b = '';
    b += '<div class="tiles">' +
      tile('Arrival-time precision', us(T.toa_us), 'σ<sub>TOA</sub> in ' + hours(T.track_s) + ', 0.70–2.00 GHz', true,
        'Timing precision for the PTA pulsar from one track with one of the four coherently dedispersed beams of the Pulsar Timing subsystem; each beam covers the full band and can be pointed in a different direction.') +
      tile('S/N', sig(T.snr, 3), 'of the PTA pulsar in the track') +
      tile(I.snr + 'σ S<sub>min</sub> at 1.4 GHz', noise(T.s1400_min_uJy), 'a pulsar like this one, same period and width', false,
        'The faintest pulsar with the same period, width and DM detectable at the threshold.') +
      tile('Effective width', ms(T.weff.weff_ms), 'at 1350 MHz, coherent dedispersion') + '</div>';
    b += '<dl class="kv"><div><dt>PTA pulsar' + qm('The pulsar timed by the Pulsar Timing subsystem, set in Advanced settings; by default a typical timing-array millisecond pulsar.') + '</dt><dd>P ' + mhz(I.period_ms) + ' ms · W ' + mhz(I.width_ms) + ' ms · DM ' + sig(I.dm, 4) + ' · ' + I.flux_mJy + ' mJy at ' + I.nu_ref_MHz + ' MHz, α ' + I.alpha +
      '<span class="sub">' + (pr.dist_kpc === null ? 'no distance' : sig(pr.dist_kpc, 3) + ' kpc') + ' · scattering ' + ms(pr.tau_1GHz_ms) + ' at 1 GHz (' + (pr.model === 'cordes22' ? 'τ–DM relation' : 'NE2025') + ')</span></dd></div>' +
      '<div><dt>Beams' + qm('The beams are formed before the antenna voltages are requantized, so they carry no digitization loss. Self-noise is the loss of S/N from the pulsar\'s own on-pulse flux density, which adds to the system noise of the beam.') + '</dt><dd>' + T.n_beams + ' full-band voltage beams (one on this pulsar), coherent dedispersion, ' + sig(T.tsamp_us, 3) + ' μs<span class="sub">' + T.bw_usable_MHz.toFixed(0) + ' MHz usable of 0.70–2.00 GHz · quantization ' + x3(T.losses.quantization) + ' · confusion ' + x3(T.losses.confusion) + ' · self-noise ' + x3(T.losses.self_noise) + '</span></dd></div></dl>';
    b += '<div class="table-wrap"><table class="data"><thead><tr><th>Sub-band (MHz)</th><th>Usable</th><th>S/N</th><th>σ<sub>TOA</sub></th><th>W<sub>eff</sub></th><th>τ<sub>sc</sub></th></tr></thead><tbody>' +
      T.subbands.map(function (x) {
        return '<tr><td>' + Math.round(x.f_center_MHz - 50) + '–' + Math.round(x.f_center_MHz + 50) + '</td><td>' + x.bw_usable_MHz.toFixed(0) + ' MHz</td><td>' + sig(x.snr, 3) + '</td><td>' + us(x.toa_us) + '</td><td>' + ms(x.weff_ms) + '</td><td>' + ms(x.tau_ms) + '</td></tr>';
      }).join('') + '<tr class="em"><td class="txt">Full band</td><td>' + T.bw_usable_MHz.toFixed(0) + ' MHz</td><td>' + sig(T.snr, 3) + '</td><td>' + us(T.toa_us) + '</td><td>' + ms(T.weff.weff_ms) + '</td><td>' + ms(T.weff.tau_ms) + '</td></tr></tbody></table></div>';
    return productCard('p-pta', 'Pulsar timing (PTA-like)', { anchor: 'guide-pulsar-timing-pta-like', tip: 'Arrival-time precision with a coherently dedispersed full-band beam of the Pulsar Timing subsystem (four beams, which can be pointed in different directions), for the PTA pulsar.' }, ICON_PTA, b);
  }
  function mountPsrChart(r) {
    var S = r.pulsar, C = S.curves, I = S.inputs, P = C.period_s;
    var defs = [['targeted', 'Targeted ' + mhz(C.targeted.f_center_MHz), '--s4'], ['untargeted_B1', 'Untargeted B1', '--s1'], ['untargeted_B2', 'Untargeted B2', '--s2'], ['untargeted_B3', 'Untargeted B3', '--s3']];
    var all = [];
    var series = defs.map(function (d) {
      var c = C[d[0]], pts = P.map(function (p, i) { var v = c.smin_uJy[i]; if (v !== null && isFinite(v)) all.push(v); return [p, v === null ? NaN : v]; });
      return { name: d[1], color: cssVar(d[2]), pts: pts, label: d[1].split(' ').pop(), key: d[0], fc: c.f_center_MHz };
    });
    if (!all.length) { $('psr-chart').textContent = 'The period is outside every searched range.'; return; }
    all.sort(function (a, b) { return a - b; });
    var ymin = Math.pow(10, Math.floor(Math.log10(all[0] * 0.8))), ymax = Math.pow(10, Math.ceil(Math.log10(all[Math.floor(all.length * 0.97)] * 1.5)));
    var marks = series.map(function (s) { return { x: I.period_ms * 1e-3, y: I.flux_mJy * 1e3 * Math.pow(s.fc / I.nu_ref_MHz, I.alpha), color: s.color }; });
    var ch = lineChart({ width: 720, height: 260, xlog: true, xmin: 3e-4, xmax: 10, xticks: [1e-3, 1e-2, 0.1, 1, 10], xfmt: function (v) { return v >= 1 ? v + ' s' : v * 1e3 + ' ms'; },
      xlabel: 'Period', ylog: true, ymin: ymin, ymax: ymax, ylabel: 'S<sub>min</sub> (μJy)', rightPad: 70, xs: P, series: series, marks: marks,
      legendExtra: '<span><i class="dot" style="background:' + cssVar('--muted') + '"></i>Input pulsar (P = ' + I.period_ms + ' ms): its flux density at each band center, in the band color; detectable where the dot lies above its curve</span>',
      hover: function (i) {
        return '<div class="tt-h">P = ' + (P[i] >= 1 ? sig(P[i], 3) + ' s' : sig(P[i] * 1e3, 3) + ' ms') + ' · S<sub>min</sub></div>' + series.map(function (s) {
          return '<div class="tt-r"><span><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + s.color + ';margin-right:5px"></i>' + esc(s.name) + '</span><span>' + (isFinite(s.pts[i][1]) ? noiseTxt(s.pts[i][1]) : 'not searched') + '</span></div>';
        }).join('');
      },
      aria: 'Minimum detectable flux density against period for the targeted and untargeted pulsar searches' });
    $('psr-chart').appendChild(ch);
  }
  function renderFrb(inp, r) {
    var F = r.frb, bd = F.dm_budget, I = F.inputs, b = '';
    var best = F.bands.slice().sort(function (a, c) { return a.fluence_min_Jyms - c.fluence_min_Jyms; })[0];
    var top = F.bands.slice().sort(function (a, c) { return c.rate_in_track - a.rate_in_track; })[0];
    var bestLoc = F.bands.slice().sort(function (a, c) { return a.loc_1sigma_arcsec - c.loc_1sigma_arcsec; })[0];
    b += '<div class="tiles">' +
      tile(I.snr + 'σ fluence limit · ' + best.band, sig(best.fluence_min_Jyms, 3) + '<small>Jy ms</small>', I.width_ms + ' ms burst, DM ' + I.dm + ', all losses', true,
        'The faintest burst detectable at the threshold, averaged over burst positions within the primary beam and the search grid.') +
      tile('At a beam peak · ' + best.band, sig(best.fluence_peak_Jyms, 3) + '<small>Jy ms</small>', 'beam at the primary-beam center', false,
        'The same for a burst centered on a search beam at the center of the primary beam.') +
      tile('Expected in the track · ' + top.band, sig(top.rate_in_track, 2), sci(top.rate_per_yr, 1) + ' per year', false,
        'FRB rate scaled from existing surveys, for the band with the highest rate, over the sky the search beams cover. The three bands see overlapping sky, so many bursts are detected in more than one band and the band rates are not additive.') +
      tile('Localization · ' + bestLoc.band, sig(bestLoc.loc_ra_1sigma_arcsec, 2) + '″ × ' + sig(bestLoc.loc_dec_1sigma_arcsec, 2) + '″', '1σ, RA × Dec, at the threshold', false,
        'Position uncertainty of a burst at the detection threshold, from a uniformly weighted image made from the voltages: beam width / (2 S/N) along RA and Dec. Higher bands have smaller beams and localize better.') + '</div>';
    b += tdContext(r);
    b += '<div class="table-wrap"><table class="data"><thead><tr><th>Band (MHz)</th><th>Usable</th><th>W<sub>eff</sub></th><th>Fluence, beam peak</th><th>Fluence, all losses</th><th>S<sub>peak</sub> min</th><th>DM trials</th><th>Localization (1σ)</th><th>Rate (yr⁻¹)</th><th>In track</th></tr></thead><tbody>' +
      F.bands.map(function (x) {
        return '<tr' + (x === best ? ' class="em"' : '') + '><td class="txt">' + x.band + ' · ' + x.f_lo_MHz + '–' + x.f_hi_MHz + '</td><td>' + x.bw_usable_MHz.toFixed(0) + ' MHz</td><td>' + ms(x.weff.weff_ms) + '</td><td>' + sig(x.fluence_peak_Jyms, 3) + ' Jy ms</td><td class="strong">' + sig(x.fluence_min_Jyms, 3) + ' Jy ms</td><td>' + sig(x.speak_min_mJy, 3) + ' mJy</td><td>' + x.dm_trials.toLocaleString('en-US') + '</td><td>' + sig(x.loc_ra_1sigma_arcsec, 2) + '″ × ' + sig(x.loc_dec_1sigma_arcsec, 2) + '″</td><td>' + sci(x.rate_per_yr, 1) + '</td><td>' + sig(x.rate_in_track, 2) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
    b += '<div class="table-wrap"><table class="data"><thead><tr><th>Band</th><th>SEFD<sub>beam</sub></th><th>FoV</th><th>Quantization</th><th>Beam straddle</th><th>PB average</th><th>DM trials</th><th>Confusion</th><th>Self-noise</th><th>Total</th></tr></thead><tbody>' +
      F.bands.map(function (x) {
        var L = x.losses;
        return '<tr><td class="txt">' + x.band + '</td><td>' + sig(x.sefd_beam_Jy, 3) + ' Jy</td><td>' + sig(x.fov_deg2, 3) + ' deg²</td><td>' + x3(L.quantization) + '</td><td>' + x3(L.straddle) + '</td><td>' + x3(L.pb_average) + '</td><td>' + x3(L.dm_trial) + '</td><td>' + x3(L.confusion) + '</td><td>' + x3(L.self_noise) + '</td><td>' + x3(L.total) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
    b += '<div class="table-wrap"><table class="data"><thead><tr><th>Width at band center</th><th>W<sub>int</sub></th><th>t<sub>samp</sub></th><th>t<sub>DM</sub></th><th>τ<sub>MW</sub></th><th>τ<sub>host</sub></th><th>W<sub>eff</sub></th></tr></thead><tbody>' +
      F.bands.map(function (x) {
        var w = x.weff;
        return '<tr><td class="txt">' + x.band + ' · ' + x.f_center_MHz + ' MHz</td><td>' + ms(w.w_int_ms) + '</td><td>' + ms(w.t_samp_ms) + '</td><td>' + ms(w.t_dm_ms) + '</td><td>' + ms(w.tau_mw_ms) + '</td><td>' + ms(w.tau_host_ms) + '</td><td>' + ms(w.weff_ms) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
    b += '<dl class="kv"><div><dt>Sky searched' + qm('The search beams of each band lie on a hexagonal grid spaced by the beam width and cover this area, which can be smaller or larger than the half-power area of the primary beam. The rates use it, weighted by the primary-beam response and the FRB source counts.') + '</dt><dd>' +
      F.bands.map(function (x) { return x.band + ' ' + sig(x.beam_area_deg2, 3) + ' deg²'; }).join(' · ') + '<span class="sub">' + (100 * F.bands[0].beam_coverage).toFixed(0) + '% of the primary-beam FWHM area · rate solid angle ' +
      F.bands.map(function (x) { return sig(x.omega_rate_deg2, 3); }).join(', ') + ' deg²</span></dd></div>' +
      '<div><dt>DM budget (DM ' + I.dm + ')' + qm('How the observed DM splits into the Milky Way, its halo, the intergalactic medium (which sets the redshift) and the host galaxy.') + '</dt><dd>' + Math.round(bd.dm_mw) + ' Milky Way + ' + Math.round(bd.dm_halo) + ' halo + ' + Math.round(bd.dm_cosmic) + ' cosmic + ' + Math.round(bd.dm_host) + '/(1+z) host<span class="sub">z = ' + bd.z.toFixed(3) + (bd.below_galactic ? ' · DM below the Galactic contribution' : '') + '</span></dd></div>' +
      '<div><dt>Scattering at 1 GHz' + qm('Pulse broadening in the Milky Way and in the host galaxy, which widens the burst and raises the fluence limit.') + '</dt><dd>Milky Way ' + ms(bd.tau_mw_1GHz_ms) + ' · host ' + ms(bd.tau_host_1GHz_ms) + '<span class="sub">' + (r.time_domain.scattering === 'cordes22' ? 'no Milky Way term with the τ–DM relation' : 'NE2025 (Milky Way)') + '</span></dd></div></dl>';
    b += '<div>' + subH('Fluence limit against DM (' + I.snr + 'σ, ' + I.width_ms + ' ms, all losses)', 'How the fluence limit grows with DM, as dispersion smearing and scattering widen the burst.') + '<div id="frb-chart"></div></div>';
    return productCard('p-frb', 'Chronoscope: FRBs', { anchor: 'guide-chronoscope-frbs', tip: 'Fluence limits, losses and expected rates for fast radio bursts in the three Chronoscope bands.' }, 'thumb-frb.jpg', b);
  }
  function mountFrbChart(r) {
    var F = r.frb, C = F.curves, D = C.dm;
    var cols = ['--s1', '--s2', '--s3'], all = [];
    var series = ['B1', 'B2', 'B3'].map(function (k, i) {
      C[k].forEach(function (v) { if (isFinite(v)) all.push(v); });
      return { name: k + ' ' + F.bands[i].f_lo_MHz + '–' + F.bands[i].f_hi_MHz + ' MHz', color: cssVar(cols[i]), pts: D.map(function (d, j) { return [d, C[k][j]]; }), label: k };
    });
    all.sort(function (a, b) { return a - b; });
    var ymin = Math.pow(10, Math.floor(Math.log10(all[0] * 0.8))), ymax = Math.pow(10, Math.ceil(Math.log10(all[all.length - 1] * 1.2)));
    var xt = [1, 10, 100, 1000, 10000].filter(function (v) { return v >= D[0] && v <= D[D.length - 1]; });
    var ch = lineChart({ width: 720, height: 240, xlog: true, xmin: D[0], xmax: D[D.length - 1], xticks: xt, xlabel: 'Observed DM (pc cm⁻³)',
      ylog: true, ymin: ymin, ymax: ymax, ylabel: 'Jy ms', rightPad: 40, xs: D, series: series,
      vLines: [{ x: F.inputs.dm, label: 'DM ' + F.inputs.dm }],
      hover: function (i) {
        return '<div class="tt-h">DM ' + Math.round(D[i]) + '</div>' + series.map(function (s) {
          return '<div class="tt-r"><span><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + s.color + ';margin-right:5px"></i>' + s.label + '</span><span>' + sig(s.pts[i][1], 3) + ' Jy ms</span></div>';
        }).join('');
      },
      aria: 'FRB fluence limit against DM in three bands' });
    $('frb-chart').appendChild(ch);
  }

  // ------------------------------------------------------------------ survey plan table
  // the default plan first, then the others in the order the allocation file lists them
  function planOrder(al) {
    return [al.default_variant].concat(Object.keys(al.variants).filter(function (k) { return k !== al.default_variant; }));
  }
  function renderPlanTable() {
    var al = E.data().allocation, order = planOrder(al);
    var rows = order.map(function (k) {
      var v = al.variants[k], s = v.summary, bc = s.by_class;
      return '<tr' + (k === al.default_variant ? ' class="em"' : '') + '><td class="txt"><b>' + esc(v.label) + '</b><br><span class="hint">' + esc(v.description) + '</span></td><td>' + s.pointing_epochs.toLocaleString('en-US') + '</td><td>' +
        bc.euclid_hsc.mean_epochs.toFixed(1) + ' · ' + sig(bc.euclid_hsc.median_total_uJy) + ' μJy</td><td>' + bc.galactic.mean_epochs.toFixed(1) + ' · ' + sig(bc.galactic.median_total_uJy) + ' μJy</td><td>' +
        bc.wide.mean_epochs.toFixed(1) + ' · ' + sig(bc.wide.median_total_uJy) + ' μJy</td><td>' + (s.detections_millions / 1000).toFixed(2) + ' bn</td></tr>';
    });
    $('plan-table').innerHTML = '<thead><tr><th>Plan</th><th>Pointings used</th><th>Euclid/HSC: epochs · median noise</th><th>Galactic plane</th><th>Wide area</th><th>Sources &gt; 5σ</th></tr></thead><tbody>' + rows.join('') + '</tbody>';
    $('plan-table').querySelectorAll('td.txt').forEach(function (td) { td.style.whiteSpace = 'normal'; td.style.minWidth = '260px'; });
  }

  // ------------------------------------------------------------------ wiring
  // ------------------------------------------------------------------ views (calculator and documentation)
  var VIEWS = ['calculator', 'guide', 'methods', 'survey-plan', 'specs'];
  function route() {
    var h = (location.hash || '#calculator').slice(1), view = 'calculator';
    VIEWS.forEach(function (v) { if (h === v || h.indexOf(v + '-') === 0) view = v; });
    VIEWS.forEach(function (v) { var el = $('view-' + v); if (el) el.hidden = v !== view; });
    document.querySelectorAll('[data-nav]').forEach(function (a) {
      var on = a.getAttribute('data-nav') === (view === 'calculator' ? 'calculator' : 'docs');
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    $('docs-menu').classList.remove('open'); $('docs-menu').querySelector('button').setAttribute('aria-expanded', 'false');
    var target = h !== view ? document.getElementById(h) : null;
    if (target) target.scrollIntoView(); else if (view !== 'calculator') window.scrollTo(0, 0);
  }
  function setupNav() {
    var dd = $('docs-menu'), btn = dd.querySelector('button');
    btn.addEventListener('click', function () { var o = !dd.classList.contains('open'); dd.classList.toggle('open', o); btn.setAttribute('aria-expanded', o ? 'true' : 'false'); });
    document.addEventListener('click', function (ev) { if (!dd.contains(ev.target)) { dd.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); } });
    document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') { dd.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); hideTip(); } });
    window.addEventListener('hashchange', route);
    route();
  }
  // "?" help marks: one floating tooltip, placed next to the mark and kept inside the window
  function showTip(el) {
    var t = $('qtip'); t.textContent = el.getAttribute('data-tip'); t.hidden = false;
    var r = el.getBoundingClientRect(), w = t.offsetWidth, hgt = t.offsetHeight;
    var left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8), top = r.bottom + 8;
    if (top + hgt > window.innerHeight - 8) top = r.top - hgt - 8;
    t.style.left = left + 'px'; t.style.top = top + 'px';
  }
  function hideTip() { $('qtip').hidden = true; }
  function setupHelp() {
    ['mouseover', 'focusin'].forEach(function (evn) { document.addEventListener(evn, function (ev) { var q = ev.target.closest && ev.target.closest('.qm'); if (q) showTip(q); }); });
    ['mouseout', 'focusout'].forEach(function (evn) { document.addEventListener(evn, function (ev) { if (ev.target.closest && ev.target.closest('.qm')) hideTip(); }); });
    document.addEventListener('click', function (ev) { var q = ev.target.closest && ev.target.closest('.qm'); if (q) { ev.preventDefault(); showTip(q); } });
    window.addEventListener('scroll', hideTip, { passive: true });
  }
  function qm(text) { return ' <button type="button" class="qm" data-tip="' + esc(text) + '">?</button>'; }
  function lc(s) { return String(s).replace(/σ|[kMG]Hz|\bms\b|μs/g, function (m) { return '<span class="lc">' + m + '</span>'; }); }

  function setMode(m) {
    state.mode = m;
    $('mode-survey').setAttribute('aria-pressed', m === 'survey' ? 'true' : 'false');
    $('mode-targeted').setAttribute('aria-pressed', m === 'targeted' ? 'true' : 'false');
    document.querySelectorAll('.survey-only').forEach(function (el) { el.hidden = m !== 'survey'; });
    $('targeted-opts').hidden = m !== 'targeted';
    setStale(true);
  }
  function updateDepthHint() {
    var pos = readPosition(); if (!pos) return;
    var e = tileInfo(pos.ra, pos.dec);
    $('depth-full-n').textContent = e[1] ? '(' + e[0] + ' epochs here)' : '(outside survey)';
  }
  function boot(data) {
    E.init(data);
    state.variant = data.allocation.default_variant;
    var sel = $('variant');
    planOrder(data.allocation).forEach(function (k) { var o = document.createElement('option'); o.value = k; o.textContent = data.allocation.variants[k].label; sel.appendChild(o); });
    sel.value = state.variant;
    var showPlan = function () { var v = data.allocation.variants[state.variant]; $('plan-name').textContent = v ? '· ' + v.label.split(':')[0] + (state.variant === data.allocation.default_variant ? ' (default)' : '') : ''; };
    showPlan();
    sel.addEventListener('change', function () { state.variant = sel.value; showPlan(); drawMap(); updateDepthHint(); setStale(true); });
    $('mode-survey').addEventListener('click', function () { setMode('survey'); });
    $('mode-targeted').addEventListener('click', function () { setMode('targeted'); });
    ['ra', 'dec'].forEach(function (id) { $(id).addEventListener('input', function () { readPosition(); drawMap(); updateDepthHint(); setStale(true); }); });
    document.querySelectorAll('[data-ra]').forEach(function (b) {
      b.addEventListener('click', function () { $('ra').value = b.getAttribute('data-ra'); $('dec').value = b.getAttribute('data-dec'); readPosition(); drawMap(); updateDepthHint(); calculate(); });
    });
    document.querySelectorAll('[data-smooth]').forEach(function (b) { b.addEventListener('click', function () { $('smooth').value = b.getAttribute('data-smooth'); setStale(true); }); });
    $('form').addEventListener('input', function (ev) { if (ev.target.id !== 'ra' && ev.target.id !== 'dec') setStale(true); });
    $('form').addEventListener('change', function () { setStale(true); });
    $('psr-center').addEventListener('change', function () { $('psr-center-custom-wrap').hidden = $('psr-center').value !== 'custom'; });
    $('form').addEventListener('submit', function (ev) { ev.preventDefault(); if (location.hash && location.hash !== '#calculator') location.hash = '#calculator'; calculate(); });
    setupHelp(); setupNav();
    $('rfi-select').addEventListener('change', function () {
      state.rfiMode = $('rfi-select').value;
      $('rfi-upload').hidden = state.rfiMode !== 'upload';
      if (state.rfiMode !== 'upload' || state.userRfi) drawRfi();
      setStale(true);
    });
    $('rfi-file').addEventListener('change', function () {
      var f = $('rfi-file').files[0]; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        try { state.userRfi = parseCsv(String(rd.result)); state.userRfi.name = 'Uploaded: ' + f.name; drawRfi(); setStale(true); }
        catch (e) { $('rfi-summary').textContent = e.message; }
      };
      rd.readAsText(f);
    });
    setupMap();
    readPosition(); drawMap(); updateDepthHint(); drawRfi(); renderPlanTable();
    var redraw = function () {   // theme change: re-render, keeping open panels open
      drawMap(); drawRfi();
      if (state.last) {
        var open = openPanels();
        render(state.last.inp, state.last.res);
        restorePanels(open);
      }
      if (state.stale) setStale(true);
    };
    if (window.matchMedia) { var mq = window.matchMedia('(prefers-color-scheme: dark)'); if (mq.addEventListener) mq.addEventListener('change', redraw); }
    new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    var rt = null; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(drawMap, 120); });
    calculate();
  }
  function load() {
    var keys = Object.keys(DATA_FILES);
    if (window.DSA_DATA) { boot(window.DSA_DATA); return; }
    Promise.all(keys.map(function (k) { return fetch(DATA_BASE + DATA_FILES[k]).then(function (r) { if (!r.ok) throw new Error(DATA_FILES[k] + ' (' + r.status + ')'); return r.json(); }); }))
      .then(function (arr) { var d = {}; keys.forEach(function (k, i) { d[k] = arr[i]; }); boot(d); })
      .catch(function (err) { $('results').innerHTML = '<div class="panel warn">Could not load the model data: ' + esc(err.message) + '. Serve the page from a web server (not file://) so the data folder can be read.</div>'; });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load); else load();
})();
