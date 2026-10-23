/*
 * DSA sensitivity / exposure-time calculator: JavaScript engine.
 * A line-by-line port of python/dsa_etc/engine.py (the reference implementation);
 * tests/parity.test.js checks that both give the same numbers.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.DSAETC = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var C_LIGHT = 299792458.0, K_B = 1.380649e-23, JY = 1e-26, HI_REST_MHZ = 1420.405752;
  var FOUR_LN2 = 4 * Math.log(2), ARCSEC = Math.PI / 180 / 3600, D2R = Math.PI / 180, R2D = 180 / Math.PI;

  var DEFAULTS = {
    n_ant: 1650, dish_diameter_m: 6.155, aperture_efficiency: 0.67, tsys_zenith_K: null,
    correlator_efficiency: 0.988, n_pol: 2, galactic_noise: true, extra_loss_percent: 0.0,   // imaging: 4-bit correlation
    pointing_s: 1260.0, el_min_deg: 20.0, ha_max_h: 2.0, confusion_beta: 16, smooth_subtract_sources: true, subtract_snr: 5.0,
    // time domain (Chronoscope pulsar and FRB products; independent of the survey/targeted mode)
    td_track_s: 1260.0, td_subband_MHz: 10.0,
    td_eta_v4: 0.988, td_eta_i2: 0.939, td_eta_i4: 0.994, td_scattering: 'ne2025', td_self_noise: true,
    td_confusion_uJy: 230.0, td_confusion_nu_MHz: 1410.0, td_confusion_index: -0.7, td_confusion_tau_s: 10.0,
    psr_period_ms: 500.0, psr_width_ms: 15.0, psr_dm: null, psr_flux_mJy: 0.02, psr_nu_ref_MHz: 1400.0, psr_alpha: -1.6,
    psr_snr: 10.0, psr_untargeted_pmin_ms: 10.0, psr_untargeted_pmax_ms: 10000.0, psr_targeted_pmin_ms: 1.0,
    psr_targeted_pmax_ms: 10000.0, psr_untargeted_beam_arcsec: null, psr_untargeted_n_beams: 200000,
    psr_targeted_center_MHz: 953.35, pt_tsamp_us: 1.0, pt_eta: 1.0,
    pta_period_ms: 4.0, pta_width_ms: 0.2, pta_dm: 20.0, pta_flux_mJy: 1.0, pta_nu_ref_MHz: 1400.0, pta_alpha: -1.6, pta_snr: 10.0,
    frb_snr: 10.0, frb_dm: 500.0, frb_width_ms: 1.0, frb_max_dm: 5000.0, frb_dm_tolerance: 1.25, frb_alpha_c: 1.5,
    frb_gamma: 0.0, frb_dm_halo: 20.0, frb_f_d: 0.84, frb_host_mu: 5.49, frb_host_sigma: 0.62, frb_n_beams: 6000000,
    hi_widths_kms: [50.0, 200.0, 500.0], hi_distances_Mpc: [10.0, 50.0, 100.0],
    hi_redshifts: [0.1, 0.25, 0.5, 0.75, 1.0], nhi_width_kms: 20.0
  };

  var THETA_HEX = 1.667, THETA_ROW = 1.45, A_HEX = THETA_HEX * THETA_ROW, PB_FWHM_1GHZ = 3.36;
  var SURVEY_DEC_EDGE = -30.45;
  var TIERS = [['S04', -30.45, -26.1, 19], ['S03', -26.1, -17.4, 40], ['S02', -17.4, -8.7, 42], ['S01', -8.7, 0.0, 43],
    ['N01', 0.0, 8.7, 43], ['N02', 8.7, 17.4, 42], ['N03', 17.4, 26.1, 40], ['N04', 26.1, 34.8, 37],
    ['N05', 34.8, 43.5, 33], ['N06', 43.5, 52.2, 29], ['N07', 52.2, 60.9, 24], ['N08', 60.9, 69.6, 18],
    ['N09', 69.6, 78.3, 12], ['N10', 78.3, 87.0, 6], ['N11', 87.0, 90.0, 1]];
  var PSF0_1350 = { bmaj: 3.03, bmin: 2.31, pa: 90.6 };
  var BAND_MHZ = [700.0, 2002.0], WC_WIDTH = 130.2;
  var WC_EDGES = []; for (var _i = 0; _i < 11; _i++) WC_EDGES.push(700.0 + WC_WIDTH * _i);
  var SNAP_EDGES = []; for (_i = 0; _i < 5; _i++) SNAP_EDGES.push(700.0 + 325.5 * _i);
  var MP_WIDTH = 2.604, MP_N = 500;
  var LINE_BANDS = {
    ZB: { label: 'Galactic HI (Zoom B)', f_lo: 1419.93, f_hi: 1420.91, nchan: 960, chan_kHz: 1.017 },
    ZA: { label: 'HI to ~100 Mpc (Zoom A)', f_lo: 1388.0, f_hi: 1422.1, nchan: 4192, chan_kHz: 8.138 },
    NL: { label: 'HI to z~1 (Narrow Line)', f_lo: 700.0, f_hi: 1429.12, nchan: 5600, chan_kHz: 130.2 }
  };
  // Chronoscope (Connor et al. 2026, Table 1): band, f_lo, f_hi, channel summing (untargeted)
  var CHR_BANDS = [['B1', 880.0, 980.0, 1], ['B2', 1310.0, 1510.0, 2], ['B3', 1650.0, 1950.0, 3]];
  var CHR_CHAN_MHZ = 0.12268, CHR_TARGETED_BW = 2500 * CHR_CHAN_MHZ, CHR_TARGETED_PRESETS = [953.35, 1800.0];
  var CHR_UNTARGETED_TSAMP_S = 1e-3, CHR_TARGETED_TSAMP_S = 1e-4, CHR_UNTARGETED_BEAM_1 = 13.5, CHR_UNIQUE_AREA_DEG2 = A_HEX, HEX_CELL = Math.sqrt(3) / 2;
  var FRB_TSAMP_S = 1e-3, PT_BAND = [700.0, 2000.0], PT_NSUB = 13, TD_LIMITS = [700.0, 2002.0];
  var KDM_S = 4.148808e-3, YEAR_S = 365.25 * 86400.0;
  // FRB rate reference surveys (Connor et al. 2026 Sec. 3.1): name, rate /yr, SEFD Jy, solid angle deg^2, bandwidth MHz
  var FRB_RATE_REF = { B1: ['CHIME/FRB', 1.0e3, 100.0, 200.0, 300.0], B2: ['Parkes HTRU', 31.0, 40.0, 0.55, 340.0],
    B3: ['Parkes HTRU', 31.0, 40.0, 0.55, 340.0] };
  var H0_KMS_MPC = 67.66, OMEGA_M = 0.3097, OMEGA_B = 0.02242 / (0.6766 * 0.6766);
  var MPC_CM = 3.0856775814913673e24, PC_CM = 3.0856775814913673e18, G_CGS = 6.6743e-8, M_P_G = 1.67262192e-24, CHI_E = 0.875;
  var GAL_ROT = [[-0.0548755604162154, -0.8734370902348850, -0.4838350155487132],
    [0.4941094278755837, -0.4448296299600112, 0.7469822444972189],
    [-0.8676661490190047, -0.1980763734312015, 0.4559837761750669]];
  var SCHEMES = [['natural', 'optimal'], ['natural', 'equal'], ['robust_freq', 'optimal'], ['robust_freq', 'equal'],
    ['robust_0p4', 'optimal'], ['robust_0p4', 'equal']];

  // ---------------------------------------------------------------- numeric helpers
  function interp(x, xs, ys, left, right) {
    var n = xs.length;
    if (x <= xs[0]) return (left === undefined) ? ys[0] : (x < xs[0] ? left : ys[0]);
    if (x >= xs[n - 1]) return (right === undefined) ? ys[n - 1] : (x > xs[n - 1] ? right : ys[n - 1]);
    var lo = 0, hi = n - 1;
    while (hi - lo > 1) { var m = (lo + hi) >> 1; if (xs[m] <= x) lo = m; else hi = m; }
    var t = (x - xs[lo]) / (xs[hi] - xs[lo]);
    return ys[lo] + t * (ys[hi] - ys[lo]);
  }
  function extrap(x, xs, ys) {
    var n = xs.length;
    if (x < xs[0]) return ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0]);
    return ys[n - 1] + (x - xs[n - 1]) * (ys[n - 1] - ys[n - 2]) / (xs[n - 1] - xs[n - 2]);
  }
  function linspace(a, b, n) { var o = new Array(n); if (n === 1) { o[0] = a; return o; } for (var i = 0; i < n; i++) o[i] = a + (b - a) * i / (n - 1); return o; }
  function erf(x) { return 1 - erfc(x); }
  function erfc(x) { // Numerical Recipes erfcc, |rel err| < 1.2e-7
    var z = Math.abs(x), t = 1 / (1 + 0.5 * z);
    var r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 +
      t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
    return x >= 0 ? r : 2 - r;
  }
  function hypot(a, b) { return Math.sqrt(a * a + b * b); }
  // 2x2 symmetric matrices as [a, b, c] = [[a,b],[b,c]]
  function covFromBeam(bmaj, bmin, pa) {
    var a = pa * D2R, vx = Math.sin(a), vy = Math.cos(a), ux = Math.cos(a), uy = -Math.sin(a);
    return [bmaj * bmaj * vx * vx + bmin * bmin * ux * ux, bmaj * bmaj * vx * vy + bmin * bmin * ux * uy,
      bmaj * bmaj * vy * vy + bmin * bmin * uy * uy];
  }
  function inv2(m) { var d = m[0] * m[2] - m[1] * m[1]; return [m[2] / d, -m[1] / d, m[0] / d]; }
  function beamFromCov(P) {
    var a = P[0], b = P[1], c = P[2], tr = a + c, det = a * c - b * b;
    var disc = Math.sqrt(Math.max(tr * tr / 4 - det, 0)), l1 = tr / 2 + disc, l2 = tr / 2 - disc;
    var vx, vy;
    if (Math.abs(b) > 1e-14 * (Math.abs(a) + Math.abs(c))) { vx = l1 - c; vy = b; } else if (a >= c) { vx = 1; vy = 0; } else { vx = 0; vy = 1; }
    var pa = Math.atan2(vx, vy) * R2D; pa = ((pa % 180) + 180) % 180;
    return { bmaj: Math.sqrt(Math.max(l1, 0)), bmin: Math.sqrt(Math.max(l2, 0)), pa: pa };
  }

  // ---------------------------------------------------------------- data
  var DATA = null, TSKY = null, UCC = null, BASE = null, COUNTS = {}, TSYSBP = null, TSYSZA = null, TAPER = null, NE = null, MACQ = {};

  function decodeB64Int16(s) {
    var bin = (typeof atob === 'function') ? atob(s) : Buffer.from(s, 'base64').toString('binary');
    var n = bin.length >> 1, out = new Int16Array(n);
    for (var i = 0; i < n; i++) { var v = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8); out[i] = v > 32767 ? v - 65536 : v; }
    return out;
  }

  function init(data) {
    DATA = data;
    // sky temperature planes
    var t = data.tsky, planes = [];
    for (var p = 0; p < t.log10T_milli_b64delta.length; p++) {
      var a = decodeB64Int16(t.log10T_milli_b64delta[p]), T = new Float64Array(a.length);
      for (var i = 0; i < t.ndec; i++) {
        var acc = 0;
        for (var j = 0; j < t.nra; j++) { acc += a[i * t.nra + j]; T[i * t.nra + j] = Math.pow(10, acc / 1000); }
      }
      planes.push(T);
    }
    TSKY = { f: t.planes_MHz, lf: t.planes_MHz.map(Math.log10), T: planes, lTref: t.Tref_K.map(Math.log10),
      dec0: t.dec_start, ddec: t.dec_step, ra0: t.ra_start, dra: t.ra_step, ndec: t.ndec, nra: t.nra };
    UCC = { lt: data.ucc.log10_theta_arcsec, f16: data.ucc.log10_f_beta16, f25: data.ucc.log10_f_beta25 };
    COUNTS = {};
    BASE = null;
    // time domain: T_sys table, taper table, NE2025 grid
    var c = data.tsys_bandpass, f = [];
    for (i = 0; i < c.tsys_zenith_K.length; i++) f.push(c.freq_start_MHz + c.freq_step_MHz * i);
    TSYSBP = { f: f, T: c.tsys_zenith_K, meta: c };
    TSYSZA = data.tsys_za;
    TAPER = data.chr_taper;
    NE = null;
    if (data.ne2025) {
      var ng = data.ne2025, nd = ng.dm_grid.length, grids = {};
      Object.keys(ng.grids).forEach(function (name) {
        var g = ng.grids[name], o = {}, k;
        for (k in g) o[k] = g[k];
        o.dmmax = cumLast(decodeB64Int16(g.log_dmmax_b64), g.nl);
        o.taux = cumLast(decodeB64Int16(g.log_taux_b64), g.nl);
        o.dist = cumLast(decodeB64Int16(g.log_dist_b64), nd);
        o.tau = cumLast(decodeB64Int16(g.log_tau_b64), nd);
        grids[name] = o;
      });
      NE = { ldm: ng.dm_grid.map(Math.log10), nd: nd, grids: grids, meta: ng };
    }
    MACQ = {};
    return true;
  }
  // cumulative sum along the last axis (length m) of a flattened int16 array, divided by 1000 (log10 values)
  function cumLast(a, m) {
    var out = new Float64Array(a.length);
    for (var s = 0; s < a.length; s += m) { var acc = 0; for (var j = 0; j < m; j++) { acc += a[s + j]; out[s + j] = acc / 1000; } }
    return out;
  }

  function rfiFromData(d) {
    var n = d.occupancy_percent.length, f = new Array(n), o = new Array(n);
    for (var i = 0; i < n; i++) { f[i] = d.freq_start_MHz + d.freq_step_MHz * i; o[i] = d.occupancy_percent[i] / 100; }
    return { name: d.name, freq: f, occ: o };
  }
  // default: 'Spring Valley model extrapolated' (measured shape, 15% band-averaged loss)
  function rfiDefault() { return rfiFromData(DATA.rfi); }
  // Spring Valley occupancy as measured by the site RFI survey
  function rfiMeasured() { return rfiFromData(DATA.rfi_measured || DATA.rfi); }
  function makeRfiProfile(freq, occ, name) {
    var idx = freq.map(function (_, i) { return i; }).sort(function (a, b) { return freq[a] - freq[b]; });
    var mx = Math.max.apply(null, occ.filter(function (v) { return isFinite(v); }));
    var sc = mx > 1 ? 0.01 : 1;
    return { name: name || 'user profile', freq: idx.map(function (i) { return +freq[i]; }),
      occ: idx.map(function (i) { return Math.min(Math.max(occ[i] * sc, 0), 1); }) };
  }
  function rfiNone() { return { name: 'none (ideal)', freq: [600.0, 2100.0], occ: [0, 0] }; }
  function occAt(rfi, f) { return interp(f, rfi.freq, rfi.occ, 0, 0); }
  function usableBwHz(rfi, fLo, fHi, extraLoss) {
    var width = fHi - fLo; if (width <= 0) return 0;
    var n = Math.max(3, Math.ceil(width / 0.1) + 1), x = linspace(fLo, fHi, n), s = 0;
    var prev = occAt(rfi, x[0]);
    for (var i = 1; i < n; i++) { var cur = occAt(rfi, x[i]); s += 0.5 * (prev + cur) * (x[i] - x[i - 1]); prev = cur; }
    var frac = 1 - s / width;
    return Math.max(frac, 0) * width * 1e6 * (1 - (extraLoss || 0));
  }
  function confusionUJy(theta, freqMHz, beta) {
    var lf = beta === 25 ? UCC.f25 : UCC.f16;
    var f = Math.pow(10, interp(Math.log10(Math.max(theta, 1.0)), UCC.lt, lf));
    return f * theta * theta * Math.pow(freqMHz / 1400.0, -0.7);
  }
  // 1.4-GHz source counts behind the confusion curve (inverting N(>5 sigma_c) = 1/(beta Omega_beam)) and their second
  // moment M2(S) = int_0^S S'^2 n(S') dS', exact for power-law segments between table points.
  function segM2(Nk, Sk, a, s) {
    if (Math.abs(2.0 - a) < 1e-9) return a * Nk * Sk * Sk * Math.log(s / Sk);
    return a * Nk * Sk * Sk * (Math.pow(s / Sk, 2.0 - a) - 1.0) / (2.0 - a);
  }
  function counts(beta) {
    var key = beta === 25 ? 25 : 16;
    if (COUNTS[key]) return COUNTS[key];
    var lf = key === 25 ? UCC.f25 : UCC.f16, n = UCC.lt.length, S = [], N = [], alpha = [], M2 = new Array(n);
    for (var i = 0; i < n; i++) {
      var th = Math.pow(10, UCC.lt[i]);
      S.push(5.0 * Math.pow(10, lf[i]) * th * th);
      N.push(FOUR_LN2 / (key * Math.PI * (th * ARCSEC) * (th * ARCSEC)));
    }
    for (i = 0; i < n - 1; i++) alpha.push(-(Math.log(N[i + 1]) - Math.log(N[i])) / (Math.log(S[i + 1]) - Math.log(S[i])));
    M2[0] = alpha[0] * N[0] * S[0] * S[0] / (2.0 - alpha[0]);
    for (i = 0; i < n - 1; i++) M2[i + 1] = M2[i] + segM2(N[i], S[i], alpha[i], S[i + 1]);
    COUNTS[key] = { S: S, N: N, alpha: alpha, M2: M2 };
    return COUNTS[key];
  }
  function countsM2(s, beta) {
    var c = counts(beta), S = c.S, n = S.length;
    if (s <= S[0]) return c.alpha[0] * c.N[0] * S[0] * S[0] * Math.pow(s / S[0], 2.0 - c.alpha[0]) / (2.0 - c.alpha[0]);
    var k = 0; while (k < n - 1 && S[k + 1] <= s) k++;
    k = Math.min(k, n - 2);
    return c.M2[k] + segM2(c.N[k], S[k], c.alpha[k], s);
  }
  // confusion (uJy/beam) left after subtracting every source brighter than limitUJy at limitNuMHz (Poisson remainder)
  function residualConfusionUJy(limitUJy, limitNuMHz, beam, freqMHz, beta) {
    var s1400 = limitUJy * Math.pow(limitNuMHz / 1400.0, 0.7);
    var omegaE = Math.PI * beam.bmaj * beam.bmin * ARCSEC * ARCSEC / (2.0 * FOUR_LN2);
    return Math.sqrt(omegaE * countsM2(s1400, beta)) * Math.pow(freqMHz / 1400.0, -0.7);
  }
  function tskyK(freqMHz, ra, dec) {
    var t = TSKY, y = (dec - t.dec0) / t.ddec;
    y = Math.min(Math.max(y, 0), t.ndec - 1.000001);
    var x = ((ra - t.ra0) / t.dra) % t.nra; if (x < 0) x += t.nra;
    var i0 = Math.floor(y), j0 = Math.floor(x), fy = y - i0, fx = x - j0, j1 = (j0 + 1) % t.nra, nra = t.nra;
    var lv = t.T.map(function (P) {
      return Math.log10(P[i0 * nra + j0] * (1 - fx) * (1 - fy) + P[i0 * nra + j1] * fx * (1 - fy) +
        P[(i0 + 1) * nra + j0] * (1 - fx) * fy + P[(i0 + 1) * nra + j1] * fx * fy);
    });
    var xf = Math.log10(freqMHz), inside = xf >= t.lf[0] && xf <= t.lf[t.lf.length - 1];
    var T = Math.pow(10, inside ? interp(xf, t.lf, lv) : extrap(xf, t.lf, lv));
    var Tref = Math.pow(10, inside ? interp(xf, t.lf, t.lTref) : extrap(xf, t.lf, t.lTref));
    return [T, Tref];
  }
  function robustFactors(scheme, freqMHz, dec) {
    if (scheme === 'natural') return [1.0, 1.0];
    var w = DATA.weighting, kb = scheme === 'robust_freq' ? 'beam_robust_freq' : 'beam_robust_0p4';
    var kr = scheme === 'robust_freq' ? 'rms_robust_freq' : 'rms_robust_0p4';
    var fr = w.freqs_MHz, fq = Math.min(Math.max(freqMHz, fr[0]), fr[fr.length - 1]);
    function at(d) { var f = w.factors[String(d)]; return [interp(fq, fr, f[kb]), interp(fq, fr, f[kr])]; }
    var d = Math.min(Math.max(dec, -40), 30), pairs = [[30, -20], [-20, -30], [-30, -40]];
    for (var i = 0; i < pairs.length; i++) {
      var hi = pairs[i][0], lo = pairs[i][1];
      if (d >= lo && d <= hi) {
        var t = (hi - d) / (hi - lo), H = at(hi), L = at(lo);
        return [H[0] + t * (L[0] - H[0]), H[1] + t * (L[1] - H[1])];
      }
    }
    return at(30);
  }
  function mosaicZ(freqMHz, dec) {
    var d = DATA.mosaic_z, fg = freqMHz / 1000, tp = PB_FWHM_1GHZ / fg;
    var zmean = 0.5665 * tp * tp * (1 - Math.exp(-8 * Math.log(2) * 0.911 * 0.911)) / A_HEX;
    var zmin = interp(fg, d.freq_GHz, d.zmin), zmax = interp(fg, d.freq_GHz, d.zmax), edge = 1;
    if (dec !== undefined && dec !== null) {
      var sig = tp / (4 * Math.sqrt(Math.log(2)));
      edge = 0.5 * erfc(-(dec - SURVEY_DEC_EDGE) / (sig * Math.SQRT2));
    }
    return { zmean: zmean * edge, zmin: zmin * edge, zmax: zmax * edge, edge_factor: edge };
  }
  // Baselines for the smoothing (uv-taper) noise: every baseline shorter than 1 km (weight 1), which makes large
  // smoothing scales exact, plus every 13th longer pair in i<j order (weight 13). Matches all 1,360,425 to 0.3%.
  var BASELINE_EXACT_M = 1000.0;
  function baselineSample(step) {
    if (BASE) return BASE;
    step = step || 13;
    var a = DATA.antennas, E = a.E, N = a.N, U = a.U, n = E.length, phi = a.site_lat_deg * D2R;
    var sp = Math.sin(phi), cp = Math.cos(phi), p = 0, Lx = [], Ly = [], Lz = [], c = [], lim2 = BASELINE_EXACT_M * BASELINE_EXACT_M, tot = 0;
    for (var i = 0; i < n; i++) for (var j = i + 1; j < n; j++) {
      var BE = E[j] - E[i], BN = N[j] - N[i], BU = U[j] - U[i];
      var short = BE * BE + BN * BN + BU * BU < lim2;
      if (short || p % step === 0) {
        Lx.push(-sp * BN + cp * BU); Ly.push(BE); Lz.push(cp * BN + sp * BU);
        var w = short ? 1.0 : step; c.push(w); tot += w;
      }
      p++;
    }
    BASE = { Lx: Float64Array.from(Lx), Ly: Float64Array.from(Ly), Lz: Float64Array.from(Lz), c: Float64Array.from(c), ctot: tot };
    return BASE;
  }
  function siteLat() { return DATA.antennas.site_lat_deg; }

  // ---------------------------------------------------------------- geometry
  function zenithAngle(haDeg, dec, lat) {
    var h = haDeg * D2R, d = dec * D2R, p = lat * D2R;
    var c = Math.sin(p) * Math.sin(d) + Math.cos(p) * Math.cos(d) * Math.cos(h);
    return Math.acos(Math.max(-1, Math.min(1, c))) * R2D;
  }
  function trackPlan(dec, hours, lat, elMin, haMaxH) {
    var p = lat * D2R, d = dec * D2R, sEl = Math.sin(elMin * D2R), denom = Math.cos(p) * Math.cos(d), hVis;
    if (denom <= 1e-9) hVis = (Math.sin(p) * Math.sin(d) >= sEl) ? 12 : 0;
    else {
      var c = (sEl - Math.sin(p) * Math.sin(d)) / denom;
      hVis = c > 1 ? 0 : (c < -1 ? 12 : Math.acos(c) * R2D / 15);
    }
    if (hVis <= 0) return { observable: false, h_lim: 0, n_transits: 0, ha_half_h: 0, ha_samples: [] };
    var hLim = Math.min(haMaxH, hVis);
    var nTr = Math.max(1, Math.ceil(hours / (2 * hLim) - 1e-9));
    var half = hours / (2 * nTr);
    var ns = half < 1e-6 ? 1 : Math.max(3, Math.min(17, 2 * Math.ceil(half / 0.25) + 1));
    var has = ns === 1 ? [0.0] : linspace(-half * 15, half * 15, ns);
    return { observable: true, h_lim: hLim, h_visible: hVis, n_transits: nTr, ha_half_h: half, ha_samples: has };
  }
  function Mmat(haDeg, dec, lat) {
    var h = haDeg * D2R, d = dec * D2R, p = lat * D2R;
    return [[Math.cos(h), -Math.sin(p) * Math.sin(h)],
      [Math.sin(d) * Math.sin(h), Math.sin(p) * Math.sin(d) * Math.cos(h) + Math.cos(p) * Math.cos(d)]];
  }
  function psfNatural1350(dec, has, weights, lat, psf0) {
    var b0 = psf0 || PSF0_1350, K0 = inv2(covFromBeam(b0.bmaj, b0.bmin, b0.pa));
    var K = [0, 0, 0], sw = 0;
    for (var k = 0; k < has.length; k++) {
      var M = Mmat(has[k], dec, lat), w = weights[k];
      // M K0 M^T
      var a = M[0][0], b = M[0][1], c = M[1][0], d = M[1][1];
      var k00 = K0[0], k01 = K0[1], k11 = K0[2];
      var r00 = a * (a * k00 + b * k01) + b * (a * k01 + b * k11);
      var r01 = a * (c * k00 + d * k01) + b * (c * k01 + d * k11);
      var r11 = c * (c * k00 + d * k01) + d * (c * k01 + d * k11);
      K[0] += w * r00; K[1] += w * r01; K[2] += w * r11; sw += w;
    }
    K = [K[0] / sw, K[1] / sw, K[2] / sw];
    return beamFromCov(inv2(K));
  }
  function scaleBeam(b, f) { return { bmaj: b.bmaj * f, bmin: b.bmin * f, pa: b.pa }; }
  function beamSolidAngleSr(b) { return Math.PI * (b.bmaj * ARCSEC) * (b.bmin * ARCSEC) / FOUR_LN2; }
  function tbK(sigmaJy, freqMHz, b) { var lam = C_LIGHT / (freqMHz * 1e6); return sigmaJy * JY * lam * lam / (2 * K_B * beamSolidAngleSr(b)); }
  function smoothPlan(b, target) {
    if (!target || target <= b.bmin) return null;
    var kMaj = Math.sqrt(Math.max(target * target - b.bmaj * b.bmaj, 0)), kMin = Math.sqrt(target * target - b.bmin * b.bmin);
    var o = { bmaj: Math.max(target, b.bmaj), bmin: target, pa: b.pa, k_maj: kMaj, k_min: kMin };
    if (o.bmaj < o.bmin) { var t = o.bmaj; o.bmaj = o.bmin; o.bmin = t; }
    return o;
  }
  function taperNoiseFactor(kernel, freqMHz, dec, has, weights) {
    if (!kernel) return 1.0;
    if (has.length > 5) { // the taper factor varies slowly along a track: 5 samples suffice
      var idx = [0, 1, 2, 3, 4].map(function (i) { return Math.round(i * (has.length - 1) / 4); });
      has = idx.map(function (i) { return has[i]; }); weights = idx.map(function (i) { return weights[i]; });
    }
    var B = baselineSample(), lam = C_LIGHT / (freqMHz * 1e6), a = kernel.pa * D2R;
    var e0 = Math.sin(a), e1 = Math.cos(a), f0 = Math.cos(a), f1 = -Math.sin(a);
    var cmaj = (Math.PI * Math.PI / FOUR_LN2) * Math.pow(kernel.k_maj * ARCSEC, 2);
    var cmin = (Math.PI * Math.PI / FOUR_LN2) * Math.pow(kernel.k_min * ARCSEC, 2);
    var d = dec * D2R, sd = Math.sin(d), cd = Math.cos(d), sT = 0, sT2 = 0, sW = 0, n = B.Lx.length;
    for (var k = 0; k < has.length; k++) {
      var hr = has[k] * D2R, sh = Math.sin(hr), ch = Math.cos(hr), w = weights[k], t1 = 0, t2 = 0;
      for (var i = 0; i < n; i++) {
        var u = (sh * B.Lx[i] + ch * B.Ly[i]) / lam;
        var v = (-sd * ch * B.Lx[i] + sd * sh * B.Ly[i] + cd * B.Lz[i]) / lam;
        var pm = u * e0 + v * e1, pn = u * f0 + v * f1;
        var T = Math.exp(-(cmaj * pm * pm + cmin * pn * pn)), cT = B.c[i] * T;
        t1 += cT; t2 += cT * T;
      }
      sT += w * t1; sT2 += w * t2; sW += w * B.ctot;
    }
    return Math.sqrt(sT2 * sW) / sT;
  }
  function lumDistMpc(z, h0, om) {
    h0 = h0 || 67.66; om = om || 0.3097;
    if (z <= 0) return 0;
    var n = 400, s = 0, prev = 1 / Math.sqrt(om + (1 - om));
    for (var i = 1; i <= n; i++) {
      var zi = z * i / n, cur = 1 / Math.sqrt(om * Math.pow(1 + zi, 3) + (1 - om));
      s += 0.5 * (prev + cur) * (z / n); prev = cur;
    }
    return (1 + z) * (C_LIGHT / 1e3 / h0) * s;
  }

  // ---------------------------------------------------------------- time domain: data and helpers
  // zenith T_sys (K) of the measured bandpass (RFI removed)
  function tsysBandpassK(f) { return interp(f, TSYSBP.f, TSYSBP.T); }
  // [spillover, atmosphere]: increase of T_sys over zenith (K); bilinear, frequency clamped, linear in ZA beyond 80 deg
  function zaIncreaseK(f, za) {
    var d = TSYSZA, fs = d.freq_MHz, zs = d.za_deg, x = Math.min(Math.max(f, fs[0]), fs[fs.length - 1]), j = 0, i = 0;
    while (j < fs.length - 2 && fs[j + 1] <= x) j++;
    var u = (x - fs[j]) / (fs[j + 1] - fs[j]);
    while (i < zs.length - 2 && zs[i + 1] <= za) i++;
    var v = (za - zs[i]) / (zs[i + 1] - zs[i]);
    function bil(t) {
      var a = t[i][j] + (t[i][j + 1] - t[i][j]) * u, b = t[i + 1][j] + (t[i + 1][j + 1] - t[i + 1][j]) * u;
      return a + (b - a) * v;
    }
    return [bil(d.spill_K), bil(d.atm_K)];
  }
  function tdSubbandEdges(fLo, fHi, width) {
    var n = Math.max(1, Math.ceil((fHi - fLo) / width - 1e-9)), w = (fHi - fLo) / n, out = [];
    for (var i = 0; i < n; i++) out.push([fLo + w * i, fLo + w * (i + 1)]);
    return out;
  }
  // untargeted beam: noise factor, sidelobe-rms ratio and FWHM, linear in Dec then in beam FWHM
  function chrTaper(band, dec, beam) {
    var t = TAPER, b = t.bands[band], decs = t.dec_deg;
    var d = Math.min(Math.max(dec, decs[0]), decs[decs.length - 1]);
    var j = Math.min(Math.floor((d - decs[0]) / (decs[1] - decs[0])), decs.length - 2), u = (d - decs[j]) / (decs[j + 1] - decs[j]);
    function row(key) { return b[key][j].map(function (a, i) { return (1 - u) * a + u * b[key][j + 1][i]; }); }
    var fw = row('fwhm_arcsec'), ft = row('f_taper'), sl = row('sidelobe_rms'), note = null, x = beam;
    if (x <= fw[0]) { x = fw[0]; note = 'narrower than the natural beam: untapered'; }
    else if (x > fw[fw.length - 1]) { x = fw[fw.length - 1]; note = 'wider than the taper table: clamped'; }
    return { f_taper: interp(x, fw, ft), sidelobe_ratio: interp(x, fw, sl) / sl[0], fwhm_arcsec: x, natural_fwhm_arcsec: fw[0],
      sidelobe_rms0: sl[0], note: note };
  }
  function radecToLb(ra, dec) {
    var a = ra * D2R, d = dec * D2R, v = [Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)], g = [0, 0, 0];
    for (var i = 0; i < 3; i++) for (var k = 0; k < 3; k++) g[i] += GAL_ROT[i][k] * v[k];
    var l = Math.atan2(g[1], g[0]) * R2D;
    return [((l % 360) + 360) % 360, Math.asin(Math.max(-1, Math.min(1, g[2]))) * R2D];
  }
  function lbToRadec(l, b) {
    var a = l * D2R, d = b * D2R, g = [Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)], v = [0, 0, 0];
    for (var i = 0; i < 3; i++) for (var k = 0; k < 3; k++) v[i] += GAL_ROT[k][i] * g[k];
    var ra = Math.atan2(v[1], v[0]) * R2D;
    return [((ra % 360) + 360) % 360, Math.asin(Math.max(-1, Math.min(1, v[2]))) * R2D];
  }
  // NE2025 grid: trilinear in (l, b, log DM) on log D and log tau; tau_X bilinear on log; DM_max from the nearest sightline
  function ne2025At(l, b, dm) {
    var inner = NE.grids.inner, g;
    g = (inner && b >= inner.b0 && b <= inner.b0 + inner.db * (inner.nb - 1)) ? inner : NE.grids.outer;
    var nl = g.nl, nb = g.nb, nd = NE.nd, ldm = NE.ldm;
    var x = ((l - g.l0) / g.dl) % nl; if (x < 0) x += nl;
    var y = Math.min(Math.max((b - g.b0) / g.db, 0), nb - 1);
    var z = Math.min(Math.max(Math.log10(Math.max(dm, 1e-3)), ldm[0]), ldm[nd - 1]);
    var k = 0; while (k < nd - 1 && ldm[k + 1] <= z) k++;
    k = Math.min(k, nd - 2);
    var fz = (z - ldm[k]) / (ldm[k + 1] - ldm[k]);
    var i0 = Math.min(Math.floor(y), nb - 2), fy = y - i0, j0 = Math.floor(x), fx = x - j0, j1 = (j0 + 1) % nl;
    function tri(A) {
      var s = 0, cells = [[i0, 1 - fy], [i0 + 1, fy]], cols = [[j0, 1 - fx], [j1, fx]];
      for (var a = 0; a < 2; a++) for (var c = 0; c < 2; c++) {
        var base = (cells[a][0] * nl + cols[c][0]) * nd;
        s += cells[a][1] * cols[c][1] * ((1 - fz) * A[base + k] + fz * A[base + k + 1]);
      }
      return s;
    }
    var ni = Math.floor(y + 0.5), nj = Math.floor(x + 0.5) % nl, dmMax = Math.pow(10, g.dmmax[ni * nl + nj]), T = g.taux;
    var ltx = (1 - fy) * ((1 - fx) * T[i0 * nl + j0] + fx * T[i0 * nl + j1]) + fy * ((1 - fx) * T[(i0 + 1) * nl + j0] + fx * T[(i0 + 1) * nl + j1]);
    return { dist_kpc: Math.pow(10, tri(g.dist)), tau_1GHz_ms: Math.pow(10, tri(g.tau)), dm_max: dmMax,
      tau_x_1GHz_ms: Math.pow(10, ltx), saturated: dm > dmMax };
  }
  // Cordes et al. (2022) tau-DM relation (ms), nu^-4 scaling
  function tauCordes22Ms(dm, f) { return 1.90e-7 * Math.pow(dm, 1.5) * (1 + 3.55e-5 * dm * dm * dm) * Math.pow(f / 1000, -4.0); }
  function tDmS(dm, chan, f) { return 8.3e-6 * dm * chan / Math.pow(f / 1000, 3); }
  // rate of change of parallactic angle with hour angle (rad / rad)
  function dqDh(haDeg, dec, lat) {
    var h = haDeg * D2R, d = dec * D2R, p = lat * D2R;
    var cz = Math.sin(p) * Math.sin(d) + Math.cos(p) * Math.cos(d) * Math.cos(h), s2 = Math.max(1 - cz * cz, 1e-12);
    return Math.cos(p) * (Math.sin(p) * Math.cos(d) * Math.cos(h) - Math.cos(p) * Math.sin(d)) / s2;
  }
  function confusionTauS(tauRef, dec, halfH, lat) {
    var ref = Math.abs(dqDh(15.0, lat, lat)), n = 32, mean = 0;
    if (halfH <= 0) mean = Math.abs(dqDh(0, dec, lat));
    else { for (var i = 0; i < n; i++) mean += Math.abs(dqDh(-halfH * 15 + (i + 0.5) * 2 * halfH * 15 / n, dec, lat)); mean /= n; }
    return Math.min(Math.max(tauRef * ref / Math.max(mean, 1e-12), 1.0), 1000.0);
  }
  function lorentzPsd(f, sigma, tau) { return 4 * sigma * sigma * tau / (1 + Math.pow(2 * Math.PI * f * tau, 2)); }
  // S/N factor from red sidelobe confusion for matched folding of a Gaussian profile (FWHM weff)
  function psrConfusionFactor(period, weff, tsamp, sigma1, sigmaC, tauC) {
    if (sigmaC <= 0 || !isFinite(sigma1) || weff >= period) return 1.0;
    var pth = 2 * sigma1 * sigma1, c = Math.PI * Math.PI * weff * weff / (FOUR_LN2 * period * period), num = 0, den = 0;
    for (var k = 1; k < 1000000; k++) {
      var a = Math.exp(-c * k * k);
      if (a < 1e-3 || k / period > 0.5 / tsamp) break;
      num += a * a / (pth + lorentzPsd(k / period, sigmaC, tauC));
      den += a * a / pth;
    }
    return den > 0 ? Math.sqrt(num / den) : 1.0;
  }
  function sinc(x) { return x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x); }
  // S/N factor sqrt(V_th / (V_th + V_c)) for a boxcar of width W minus a running-mean baseline of max(1 s, 10 W)
  function frbConfusionFactor(weff, sigma1, sigmaC, tauC, n) {
    if (sigmaC <= 0 || !isFinite(sigma1)) return 1.0;
    n = n || 4000;
    var tb = Math.max(1.0, 10 * weff), vth = sigma1 * sigma1 * (1 / weff - 1 / tb);
    var lo = Math.log(1e-3 / Math.max(tb, tauC)), hi = Math.log(100 / weff), vc = 0, prev = 0;
    for (var i = 0; i < n; i++) {
      var f = Math.exp(lo + (hi - lo) * i / (n - 1)), hh = sinc(f * weff) - sinc(f * tb);
      var g = 4 * sigmaC * sigmaC * tauC / (1 + Math.pow(2 * Math.PI * f * tauC, 2)) * hh * hh * f;
      if (i > 0) vc += 0.5 * (g + prev);
      prev = g;
    }
    vc *= (hi - lo) / (n - 1);
    return Math.sqrt(vth / (vth + vc));
  }
  // mean response of an elliptical Gaussian beam over a hexagonal cell whose spacing is its geometric-mean FWHM
  // S/N factor from self-noise: on-pulse noise rises from SEFD to SEFD + S_on (x = S_on / SEFD) for a data fraction delta
  function selfNoiseFactor(x, delta) { return Math.pow((1 + x) * (1 + x) * (1 - delta) + delta, -0.5); }
  // flux at which snrOf(flux)[0] = thr, from flux0 (no self-noise, a lower bound): bracket, then Illinois regula falsi in log
  function solveThreshold(snrOf, flux0, thr, tol, nMax) {
    tol = tol || 1e-10; nMax = nMax || 60;
    if (!(flux0 > 0 && isFinite(flux0))) return Infinity;
    var lo = flux0, sLo = snrOf(flux0)[0];
    if (!(sLo > 0)) return Infinity;
    if (sLo >= thr * (1 - tol)) return flux0 * thr / sLo;
    var hi = lo * thr / sLo, sHi = snrOf(hi)[0], k = 0;
    while (sHi < thr * (1 - tol)) {
      k++;
      if (k > nMax || sHi <= sLo) return Infinity;   // the S/N saturates below the threshold
      lo = hi; sLo = sHi; hi = hi * 2 * thr / sHi; sHi = snrOf(hi)[0];
    }
    if (sHi <= thr * (1 + tol)) return hi * thr / sHi;
    var a = Math.log(lo), fa = Math.log(sLo / thr), b = Math.log(hi), fb = Math.log(sHi / thr), side = 0, c = b;
    for (var it = 0; it < nMax; it++) {
      c = (a * fb - b * fa) / (fb - fa);
      var fc = Math.log(snrOf(Math.exp(c))[0] / thr);
      if (Math.abs(fc) < tol) break;
      if (fc * fb > 0) { b = c; fb = fc; if (side === -1) fa *= 0.5; side = -1; }
      else { a = c; fa = fc; if (side === 1) fb *= 0.5; side = 1; }
    }
    return Math.exp(c);
  }
  // mean response <r^power>^(1/power) of an elliptical Gaussian over a hexagonal cell spaced at its geometric-mean FWHM
  function hexStraddle(beam, power) {
    power = power || 1;
    var a = Math.sqrt(beam.bmaj * beam.bmin), R = a / Math.sqrt(3), K = inv2(covFromBeam(beam.bmaj, beam.bmin, beam.pa));
    var m = 20, s = 0, cnt = 0;
    for (var t = 0; t < 6; t++) {
      var a0 = (90 + 60 * t) * D2R, a1 = (150 + 60 * t) * D2R;
      var P1x = R * Math.cos(a0), P1y = R * Math.sin(a0), P2x = R * Math.cos(a1), P2y = R * Math.sin(a1);
      for (var i = 0; i < m; i++) for (var j = 0; j < m - i; j++) for (var up = 0; up < 2; up++) {
        if (up && j === m - i - 1) continue;
        var u = up ? (i + 2 / 3) / m : (i + 1 / 3) / m, v = up ? (j + 2 / 3) / m : (j + 1 / 3) / m;
        var x = u * P1x + v * P2x, y = u * P1y + v * P2y;
        s += Math.exp(-FOUR_LN2 * (K[0] * x * x + 2 * K[1] * x * y + K[2] * y * y) * power); cnt++;
      }
    }
    return Math.pow(s / cnt, 1 / power);
  }
  // mean of sqrt(W / W(dDM)) over a uniform DM offset within +-half a trial step (Simpson)
  function dmTrialLoss(tol, n) {
    n = n || 200;
    var c = tol * tol - 1, h = 1 / n, s = 0;
    for (var i = 0; i <= n; i++) { var x = i * h, w = (i === 0 || i === n) ? 1 : (i % 2 ? 4 : 2); s += w * Math.pow(1 + c * x * x, -0.25); }
    return s * h / 3;
  }
  // <DM_cosmic>(z), z = 0..10 (step 0.005), trapezoid cumulative integral of (1+z)/E(z) (Planck 2018)
  function macquartTable(fd) {
    if (MACQ[fd]) return MACQ[fd];
    var h0 = H0_KMS_MPC * 1e5 / MPC_CM, kk = 3 * 2.99792458e10 * h0 * OMEGA_B * fd * CHI_E / (8 * Math.PI * G_CGS * M_P_G) / PC_CM;
    var n = 2000, zs = [], g = [], dm = [0];
    for (var i = 0; i <= n; i++) { var z = 10 * i / n; zs.push(z); g.push((1 + z) / Math.sqrt(OMEGA_M * Math.pow(1 + z, 3) + 1 - OMEGA_M)); }
    for (i = 1; i <= n; i++) dm.push(dm[i - 1] + 0.5 * (g[i] + g[i - 1]) * (zs[i] - zs[i - 1]) * kk);
    MACQ[fd] = [zs, dm];
    return MACQ[fd];
  }
  function dmCosmic(z, fd) { var t = macquartTable(fd === undefined ? 0.84 : fd); return interp(z, t[0], t[1]); }
  // number of DM trials from 0 to dmMax (smearing at half a step raises the width by tol)
  function frbDmTrials(wint, tsamp, chan, fc, fLo, fHi, dmMax, tol) {
    var k = KDM_S * (Math.pow(fLo / 1000, -2) - Math.pow(fHi / 1000, -2)), c = 2 * Math.sqrt(tol * tol - 1) / k, dm = 0, n = 0;
    while (dm < dmMax && n < 1000000) { var td = tDmS(dm, chan, fc); dm += c * Math.sqrt(wint * wint + tsamp * tsamp + td * td); n++; }
    return n;
  }
  // effective solid angle for rates: beams cover N (sqrt3/2) theta^2 (a centered disk), weighted by r_PB^alpha and
  // normalized so that exactly the FWHM disk gives the FWHM area
  function frbRateSolidAngle(nBeams, beamArcsec, pbFwhm, alpha) {
    var aCov = nBeams * HEX_CELL * Math.pow(beamArcsec / 3600, 2), rho2 = aCov / Math.PI;
    var w = (1 - Math.exp(-FOUR_LN2 * alpha * rho2 / (pbFwhm * pbFwhm))) / (1 - Math.pow(2, -alpha));
    return [Math.PI / 4 * pbFwhm * pbFwhm * w, aCov];
  }
  // Connor et al. (2026) eq. 2
  function frbRate(rRef, omRef, sefdRef, bwRef, om, sefd, bw, expo) { return rRef * (om / omRef) * Math.pow((sefdRef / sefd) * Math.sqrt(bw / bwRef), expo); }

  // ---------------------------------------------------------------- calculator
  function Calculator(opts) {
    opts = opts || {};
    this.p = JSON.parse(JSON.stringify(DEFAULTS));
    var params = opts.params || {};
    for (var k in params) if (Object.prototype.hasOwnProperty.call(params, k)) this.p[k] = params[k];
    this.rfi = opts.rfi || rfiDefault();
    this.lat = siteLat();
    this.variant = opts.variant || null;
    this._g = {}; this._pc = {}; this._tz = {};
  }
  var CP = Calculator.prototype;
  CP.extraLoss = function () { return this.p.extra_loss_percent / 100; };
  CP.galExcessK = function (f, ra, dec) {
    if (!this.p.galactic_noise) return 0;
    var key = f.toFixed(4) + '|' + ra.toFixed(6) + '|' + dec.toFixed(6), v = this._g[key];
    if (v === undefined) { var t = tskyK(f, ra, dec); v = this._g[key] = t[0] - t[1]; }
    return v;
  };
  // zenith T_sys (K) at fLo, or the effective value over [fLo, fHi]: <(1 - occupancy) T^-2>^-1/2
  CP.tzK = function (fLo, fHi) {
    var flat = this.p.tsys_zenith_K;
    if (flat !== null && flat !== undefined) return +flat;
    if (fHi === undefined || fHi === null || fHi <= fLo) return tsysBandpassK(fLo);
    var key = fLo.toFixed(6) + '|' + fHi.toFixed(6), v = this._tz[key];
    if (v === undefined) {
      var n = Math.max(3, Math.ceil((fHi - fLo) / 0.5) + 1), x = linspace(fLo, fHi, n), sw = 0, s = 0;
      for (var i = 0; i < n; i++) { var w = 1 - occAt(this.rfi, x[i]), T = tsysBandpassK(x[i]); sw += w; s += w * Math.pow(T, -2); }
      v = sw > 0 ? Math.pow(s / sw, -0.5) : tsysBandpassK(0.5 * (fLo + fHi));
      this._tz[key] = v;
    }
    return v;
  };
  // per-antenna SEFD (Jy); band = [lo, hi] averages T_sys over that band
  CP.sefdJy = function (f, za, ra, dec, band) {
    var p = this.p, area = Math.PI * Math.pow(p.dish_diameter_m / 2, 2);
    var tz = band ? this.tzK(band[0], band[1]) : this.tzK(f), gal = this.galExcessK(f, ra, dec), za2 = zaIncreaseK(f, za);
    return 2 * K_B * (tz + za2[0] + za2[1] + gal) / p.aperture_efficiency / area / JY;
  };
  CP.tsysBreakdown = function (f, za, ra, dec) {
    var t = tskyK(f, ra, dec), tz = this.tzK(f), za2 = zaIncreaseK(f, za);
    var gal = this.p.galactic_noise ? (t[0] - t[1]) : 0;
    return { tsys_K: tz + za2[0] + za2[1] + gal, tsys_zenith_K: tz, spill_K: za2[0], atm_K: za2[1], galactic_excess_K: gal,
      tsky_gal_K: t[0], tsky_ref_K: t[1] };
  };
  // full-band (0.70-2.00 GHz) T_sys and SEFD as used by the full-band products
  CP.tsysBand = function (za, ra, dec) {
    var lo = BAND_MHZ[0], hi = BAND_MHZ[1], fc = 0.5 * (lo + hi), tz = this.tzK(lo, hi), za2 = zaIncreaseK(fc, za), gal = this.galExcessK(fc, ra, dec);
    return { tsys_band_K: tz + za2[0] + za2[1] + gal, tsys_band_zenith_K: tz, spill_band_K: za2[0], atm_band_K: za2[1], galactic_band_K: gal,
      sefd_band_Jy: this.sefdJy(fc, za, ra, dec, [lo, hi]) };
  };
  CP.radiometerJy = function (sefd, bwHz, tS, beam) {
    var p = this.p, n = p.n_ant;
    if (bwHz <= 0 || tS <= 0) return Infinity;
    var nb = (beam === 'phased') ? n * n : n * (n - 1);
    return sefd / (p.correlator_efficiency * Math.sqrt(nb * p.n_pol * bwHz * tS));
  };
  CP.allocation = function () { return DATA.allocation; };
  CP.tileOf = function (ra, dec) {
    if (dec < SURVEY_DEC_EDGE) return null;
    for (var k = 0; k < TIERS.length; k++) {
      var t = TIERS[k];
      if ((dec >= t[1] && dec < t[2]) || (t[0] === 'N11' && dec >= t[1])) {
        var r = ((ra % 360) + 360) % 360, i = Math.floor(r / (360 / t[3])) % t[3];
        return [t[0], i, t[1], t[2], t[3]];
      }
    }
    return null;
  };
  CP.epochsAt = function (ra, dec, variant) {
    var t = this.tileOf(ra, dec); if (!t) return [0, null];
    var al = this.allocation(), v = variant || this.variant || al.default_variant, key = t[0] + '_' + t[1], tile = al.tiles[key];
    return [tile.epochs[v], { tile: key, tier: t[0], index: t[1], dec_lo: t[2], dec_hi: t[3], ra_lo: 360 / t[4] * t[1],
      ra_hi: 360 / t[4] * (t[1] + 1), 'class': tile['class'], n_pointings: tile.n_ptg, variant: v }];
  };
  CP.setup = function (mode, ra, dec, depth, nEpochs, hours, variant) {
    var lat = this.lat, obs = { mode: mode, ra: ra, dec: dec, lat: lat };
    obs.za_transit = Math.abs(lat - dec); obs.el_transit = 90 - obs.za_transit;
    if (mode === 'survey') {
      var e = this.epochsAt(ra, dec, variant), n;
      obs.epochs_full = e[0]; obs.tile = e[1]; obs.in_survey = e[1] !== null;
      if (depth === 'single') n = 1; else if (depth === 'custom') n = Math.max(1, Math.round(nEpochs || 1)); else n = e[0];
      obs.n_epochs = n; obs.depth = depth; obs.ha_samples = [0.0];
      obs.time_per_pointing_s = this.p.pointing_s; obs.total_time_s = n * this.p.pointing_s;
      obs.observable = obs.in_survey && n > 0;
    } else {
      var hrs = +(hours || 1), tp = trackPlan(dec, hrs, lat, this.p.el_min_deg, this.p.ha_max_h);
      for (var k in tp) obs[k] = tp[k];
      obs.hours = hrs; obs.total_time_s = hrs * 3600;
    }
    return obs;
  };
  CP.haWeights = function (obs, f, band) {
    var self = this;
    return obs.ha_samples.map(function (h) { return Math.pow(self.sefdJy(f, zenithAngle(h, obs.dec, self.lat), obs.ra, obs.dec, band), -2); });
  };
  CP.sefdEff = function (obs, f, band) {
    if (obs.mode === 'survey') return this.sefdJy(f, obs.za_transit, obs.ra, obs.dec, band);
    var ws = this.haWeights(obs, f, band), s = 0; for (var i = 0; i < ws.length; i++) s += ws[i];
    return Math.pow(s / ws.length, -0.5);
  };
  var NEFF_FREQS = [700.0, 800.0, 950.0, 1100.0, 1300.0, 1500.0, 1750.0, 2002.0];
  CP.neffTable = function (obs, nOverride) {
    var key = '_neff_' + (nOverride === undefined || nOverride === null ? 'None' : nOverride);
    if (obs[key]) return obs[key];
    var al = this.allocation(), v = obs.tile ? obs.tile.variant : al.default_variant;
    var a0 = obs.ra * D2R, d0 = obs.dec * D2R, sd0 = Math.sin(d0), cd0 = Math.cos(d0), out = [];
    for (var fi = 0; fi < NEFF_FREQS.length; fi++) {
      var sig = (PB_FWHM_1GHZ / (NEFF_FREQS[fi] / 1000)) / (4 * Math.sqrt(Math.log(2))), sw = 0, swn = 0;
      for (var ix = -10; ix <= 10; ix++) for (var iy = -10; iy <= 10; iy++) {
        var x = ix * sig / 3, y = iy * sig / 3, w = Math.exp(-(x * x + y * y) / (2 * sig * sig));
        var xi = x * D2R, eta = y * D2R, den = cd0 - eta * sd0;
        var ra = (((a0 + Math.atan2(xi, den)) * R2D) % 360 + 360) % 360;
        var dec = Math.atan2(sd0 + eta * cd0, Math.sqrt(xi * xi + den * den)) * R2D;
        var t = this.tileOf(ra, dec), n;
        if (!t) n = 0; else if (nOverride !== undefined && nOverride !== null) n = nOverride; else n = al.tiles[t[0] + '_' + t[1]].epochs[v];
        sw += w; swn += w * n;
      }
      out.push(swn / sw);
    }
    obs[key] = out;
    return out;
  };
  CP.surveyWeight = function (obs, f, nOverride) {
    var tab = this.neffTable(obs, nOverride);
    var neff = interp(Math.log10(f), NEFF_FREQS.map(Math.log10), tab);
    return mosaicZ(f).zmean * neff;
  };
  CP.effTimeS = function (obs, f) {
    if (obs.mode === 'survey') return this.p.pointing_s * this.surveyWeight(obs, f, obs.depth === 'full' ? null : obs.n_epochs);
    return obs.total_time_s;
  };
  CP.psfNat = function (obs, f) {
    var key = obs.mode + '|' + obs.dec + '|' + obs.ha_samples.join(','), b = this._pc[key];
    if (!b) {
      var ws = obs.mode !== 'survey' ? this.haWeights(obs, 1350.0) : [1.0];
      b = this._pc[key] = psfNatural1350(obs.dec, obs.ha_samples, ws, this.lat);
    }
    return scaleBeam(b, 1350.0 / f);
  };

  // continuum
  CP.continuumWindows = function (obs, scheme) {
    var rows = [];
    for (var i = 0; i < 10; i++) {
      var fLo = WC_EDGES[i], fHi = WC_EDGES[i + 1], fc = 0.5 * (fLo + fHi);
      var bw = usableBwHz(this.rfi, fLo, fHi, this.extraLoss()), sefd = this.sefdEff(obs, fc, [fLo, fHi]), teff = this.effTimeS(obs, fc);
      var fac = robustFactors(scheme[0], fc, obs.dec), sig = fac[1] * this.radiometerJy(sefd, bw, teff);
      var psf = scaleBeam(this.psfNat(obs, fc), fac[0]);
      rows.push({ window: i + 1, f_lo: fLo, f_hi: fHi, f_center: fc, bw_usable_MHz: bw / 1e6, sefd_jy: sefd, t_eff_s: teff,
        sigma_jy: sig, psf: psf, rms_factor: fac[1], beam_factor: fac[0] });
    }
    return rows;
  };
  CP.combineFc = function (rows, summation, beta) {
    var ok = rows.filter(function (r) { return isFinite(r.sigma_jy) && r.sigma_jy > 0; });
    var w = ok.map(function (r) { return summation === 'optimal' ? 1 / (r.sigma_jy * r.sigma_jy) : 1; });
    var sw = 0, s2 = 0, nu = 0, K = [0, 0, 0];
    for (var i = 0; i < ok.length; i++) {
      sw += w[i]; s2 += w[i] * w[i] * ok[i].sigma_jy * ok[i].sigma_jy; nu += w[i] * ok[i].f_center;
      var Ki = inv2(covFromBeam(ok[i].psf.bmaj, ok[i].psf.bmin, ok[i].psf.pa));
      K[0] += w[i] * Ki[0]; K[1] += w[i] * Ki[1]; K[2] += w[i] * Ki[2];
    }
    var sig = Math.sqrt(s2) / sw; nu /= sw;
    var psf = beamFromCov(inv2([K[0] / sw, K[1] / sw, K[2] / sw]));
    var conf = confusionUJy(Math.sqrt(psf.bmaj * psf.bmin), nu, beta) * 1e-6;
    return { sigma_jy: sig, nu_eff: nu, psf: psf, confusion_jy: conf, total_jy: hypot(sig, conf), weights: w.map(function (x) { return x / sw; }) };
  };
  CP.chooseScheme = function (obsFull, beta) {
    var best = null, table = [];
    for (var s = 0; s < SCHEMES.length; s++) {
      var sc = SCHEMES[s], rows = this.continuumWindows(obsFull, sc), fc = this.combineFc(rows, sc[1], beta);
      table.push({ imaging: sc[0], summation: sc[1], thermal_uJy: fc.sigma_jy * 1e6, confusion_uJy: fc.confusion_jy * 1e6,
        total_uJy: fc.total_jy * 1e6, nu_eff_MHz: fc.nu_eff, psf: fc.psf });
      if (!best || fc.total_jy < best[1]) best = [sc, fc.total_jy];
    }
    return [best[0], table];
  };
  CP.continuum = function (obs, scheme, smooth) {
    var beta = this.p.confusion_beta, rows = this.continuumWindows(obs, scheme), fc = this.combineFc(rows, scheme[1], beta), self = this;
    var outRows = rows.map(function (r) {
      var th = Math.sqrt(r.psf.bmaj * r.psf.bmin), conf = confusionUJy(th, r.f_center, beta) * 1e-6;
      return { window: r.window, f_lo_MHz: r.f_lo, f_hi_MHz: r.f_hi, f_center_MHz: r.f_center, bw_usable_MHz: r.bw_usable_MHz,
        sefd_Jy: r.sefd_jy, t_eff_s: r.t_eff_s, thermal_uJy: r.sigma_jy * 1e6, confusion_uJy: conf * 1e6,
        total_uJy: hypot(r.sigma_jy, conf) * 1e6, psf: r.psf, tb_thermal_mK: tbK(r.sigma_jy, r.f_center, r.psf) * 1e3,
        z_mosaic: obs.mode === 'survey' ? mosaicZ(r.f_center, obs.dec) : null };
    });
    var fcd = { thermal_uJy: fc.sigma_jy * 1e6, confusion_uJy: fc.confusion_jy * 1e6, total_uJy: fc.total_jy * 1e6,
      nu_eff_MHz: fc.nu_eff, psf: fc.psf, tb_thermal_mK: tbK(fc.sigma_jy, fc.nu_eff, fc.psf) * 1e3,
      tb_total_mK: tbK(fc.total_jy, fc.nu_eff, fc.psf) * 1e3, window_weights: fc.weights, imaging: scheme[0], summation: scheme[1] };
    var res = { windows: outRows, fc: fcd };
    if (smooth && smooth > 0) res.smoothed = self.continuumSmoothed(obs, smooth, fcd);
    return res;
  };
  CP.continuumSmoothed = function (obs, target, detect) {
    var beta = this.p.confusion_beta, rows = this.continuumWindows(obs, ['natural', 'optimal']), self = this;
    var srows = rows.map(function (r) {
      var k = smoothPlan(r.psf, target), nf = 1, psf = r.psf;
      if (k) {
        var ws = obs.mode !== 'survey' ? self.haWeights(obs, r.f_center) : [1.0];
        nf = taperNoiseFactor(k, r.f_center, obs.dec, obs.ha_samples, ws);
        psf = { bmaj: k.bmaj, bmin: k.bmin, pa: k.pa };
      }
      var o = {}; for (var key in r) o[key] = r[key];
      o.sigma_jy = r.sigma_jy * nf; o.psf = psf; o.noise_factor = nf; return o;
    });
    var fc = this.combineFc(srows, 'optimal', beta), sig = fc.sigma_jy, nu = fc.nu_eff, psf = fc.psf;
    // sources above subtract_snr x the full-resolution total noise can be subtracted before smoothing
    var limit = this.p.subtract_snr * detect.total_uJy;
    var resid = residualConfusionUJy(limit, detect.nu_eff_MHz, psf, nu, beta) * 1e-6, ucc = fc.confusion_jy;
    var applied = !!this.p.smooth_subtract_sources, conf = applied ? resid : ucc;
    return { target_arcsec: target, thermal_uJy: sig * 1e6, confusion_uJy: conf * 1e6, total_uJy: hypot(sig, conf) * 1e6,
      nu_eff_MHz: nu, psf: psf, tb_thermal_mK: tbK(sig, nu, psf) * 1e3,
      tb_total_mK: tbK(hypot(sig, conf), nu, psf) * 1e3, noise_factors: srows.map(function (r) { return r.noise_factor; }),
      subtraction: { applied: applied, limit_uJy: limit, limit_nu_MHz: detect.nu_eff_MHz, residual_confusion_uJy: resid * 1e6,
        tb_total_subtracted_mK: tbK(hypot(sig, resid), nu, psf) * 1e3, unsubtracted_confusion_uJy: ucc * 1e6,
        tb_total_unsubtracted_mK: tbK(hypot(sig, ucc), nu, psf) * 1e3 } };
  };
  CP.snapshots = function (obs, scheme) {
    var beta = this.p.confusion_beta, t = 6.0, sub = [], out = [], self = this;
    for (var k = 0; k < 4; k++) {
      var lo = SNAP_EDGES[k], hi = SNAP_EDGES[k + 1], fc = 0.5 * (lo + hi);
      var sefd = this.sefdJy(fc, obs.za_transit, obs.ra, obs.dec, [lo, hi]), bw = usableBwHz(this.rfi, lo, hi, this.extraLoss());
      var fac = robustFactors(scheme[0], fc, obs.dec);
      var os = {}; for (var key in obs) os[key] = obs[key]; os.ha_samples = [0.0]; os.mode = 'survey';
      var psf = scaleBeam(this.psfNat(os, fc), fac[0]), sig = fac[1] * this.radiometerJy(sefd, bw, t);
      var conf = confusionUJy(Math.sqrt(psf.bmaj * psf.bmin), fc, beta) * 1e-6;
      sub.push({ label: 'Subband ' + (k + 1), f_lo_MHz: lo, f_hi_MHz: hi, thermal_uJy: sig * 1e6, confusion_uJy: conf * 1e6,
        total_uJy: hypot(sig, conf) * 1e6, psf: psf, f_center: fc, sigma_jy: sig });
    }
    var sw = 0, nu = 0, K = [0, 0, 0];
    sub.forEach(function (r) {
      var w = 1 / (r.sigma_jy * r.sigma_jy); sw += w; nu += w * r.f_center;
      var Ki = inv2(covFromBeam(r.psf.bmaj, r.psf.bmin, r.psf.pa)); K[0] += w * Ki[0]; K[1] += w * Ki[1]; K[2] += w * Ki[2];
    });
    var sig = 1 / Math.sqrt(sw); nu /= sw;
    var psf = beamFromCov(inv2([K[0] / sw, K[1] / sw, K[2] / sw]));
    var conf = confusionUJy(Math.sqrt(psf.bmaj * psf.bmin), nu, beta) * 1e-6;
    sub.forEach(function (r) { out.push({ label: r.label, f_lo_MHz: r.f_lo_MHz, f_hi_MHz: r.f_hi_MHz, thermal_uJy: r.thermal_uJy,
      confusion_uJy: r.confusion_uJy, total_uJy: r.total_uJy, psf: r.psf }); });
    out.push({ label: 'Full band', f_lo_MHz: BAND_MHZ[0], f_hi_MHz: BAND_MHZ[1], thermal_uJy: sig * 1e6, confusion_uJy: conf * 1e6,
      total_uJy: hypot(sig, conf) * 1e6, psf: psf });
    return out;
  };

  // spectral line
  CP.lineChannel = function (obs, f, chanHz, smooth) {
    var bw = chanHz * (1 - occAt(this.rfi, f)) * (1 - this.extraLoss());
    var sefd = this.sefdEff(obs, f), teff = this.effTimeS(obs, f), sig = this.radiometerJy(sefd, bw, teff), psf = this.psfNat(obs, f);
    var res = { freq_MHz: f, sigma_mJy: sig * 1e3, psf: psf, tb_K: tbK(sig, f, psf), occupancy: occAt(this.rfi, f), sefd_Jy: sefd, t_eff_s: teff };
    if (smooth && smooth > 0) {
      var k = smoothPlan(psf, smooth);
      if (k) {
        var ws = obs.mode !== 'survey' ? this.haWeights(obs, f) : [1.0];
        var nf = taperNoiseFactor(k, f, obs.dec, obs.ha_samples, ws), sp = { bmaj: k.bmaj, bmin: k.bmin, pa: k.pa };
        res.smoothed = { target_arcsec: smooth, sigma_mJy: sig * nf * 1e3, psf: sp, tb_K: tbK(sig * nf, f, sp), noise_factor: nf };
      }
    }
    return res;
  };
  CP.spectralLine = function (obs, smooth) {
    var p = this.p, out = {}, self = this;
    ['ZB', 'ZA', 'NL'].forEach(function (key) {
      var bd = LINE_BANDS[key], chan = bd.chan_kHz * 1e3, freqs;
      if (key === 'NL') freqs = [0.0].concat(p.hi_redshifts).map(function (z) { return HI_REST_MHZ / (1 + z); })
        .filter(function (f) { return f >= bd.f_lo && f <= bd.f_hi; });
      else freqs = [HI_REST_MHZ];
      var chans = freqs.map(function (f) {
        var c = self.lineChannel(obs, f, chan, smooth), z = HI_REST_MHZ / f - 1, dv = C_LIGHT / 1e3 * chan / (f * 1e6);
        c.z = z; c.dv_kms = dv;
        var nch = Math.max(1, p.nhi_width_kms / dv);   // rest-frame Tb is (1+z) x observed
        c.nhi_5sigma_cm2 = 1.8224e18 * 5 * c.tb_K * (1 + z) * Math.sqrt(nch) * dv;
        if (c.smoothed) c.smoothed.nhi_5sigma_cm2 = 1.8224e18 * 5 * c.smoothed.tb_K * (1 + z) * Math.sqrt(nch) * dv;
        var ml = [], mlS = [], dists = [];
        if (key === 'ZA') dists = p.hi_distances_Mpc.slice(); else if (key === 'NL' && z > 0.01) dists = [lumDistMpc(z)];
        dists.forEach(function (D) {
          p.hi_widths_kms.forEach(function (W) {
            var dnu = f * 1e6 * W / (C_LIGHT / 1e3), n = Math.max(1, dnu / chan), sint = 5 * c.sigma_mJy * 1e-3 * Math.sqrt(n) * chan;
            ml.push({ D_Mpc: D, width_kms: W, mhi_5sigma_Msun: 49.7 * D * D * sint });
            if (c.smoothed) {   // unresolved at the smoothed beam
              var sintS = 5 * c.smoothed.sigma_mJy * 1e-3 * Math.sqrt(n) * chan;
              mlS.push({ D_Mpc: D, width_kms: W, mhi_5sigma_Msun: 49.7 * D * D * sintS });
            }
          });
        });
        c.mhi_limits = ml;
        if (c.smoothed) c.smoothed.mhi_limits = mlS;
        return c;
      });
      var dv0 = C_LIGHT / 1e3 * chan / (HI_REST_MHZ * 1e6);
      out[key] = { label: bd.label, f_lo_MHz: bd.f_lo, f_hi_MHz: bd.f_hi, nchan: bd.nchan, chan_kHz: bd.chan_kHz, dv_kms_at_1420: dv0,
        v_range_kms: [C_LIGHT / 1e3 * (1 - bd.f_hi / HI_REST_MHZ), C_LIGHT / 1e3 * (1 - bd.f_lo / HI_REST_MHZ)],
        z_range: [Math.max(HI_REST_MHZ / bd.f_hi - 1, -1), HI_REST_MHZ / bd.f_lo - 1], channels: chans };
    });
    return out;
  };

  // polarization
  CP.polarization = function (obs, scheme, smooth) {
    var imaging = scheme[0], chans = [], invVar = 0, self = this;
    for (var k = 0; k < MP_N; k++) {
      var lo = BAND_MHZ[0] + MP_WIDTH * k, fc = lo + 0.5 * MP_WIDTH;
      var bw = usableBwHz(this.rfi, lo, lo + MP_WIDTH, this.extraLoss()), sefd = this.sefdEff(obs, fc, [lo, lo + MP_WIDTH]), teff = this.effTimeS(obs, fc);
      var rf = robustFactors(imaging, fc, obs.dec)[1], sig = rf * this.radiometerJy(sefd, bw, teff);
      chans.push([fc, sig]); if (isFinite(sig)) invVar += 1 / (sig * sig);
    }
    var sigBand = Math.pow(invVar, -0.5);
    var l2min = Math.pow(C_LIGHT / (BAND_MHZ[1] * 1e6), 2), l2max = Math.pow(C_LIGHT / (BAND_MHZ[0] * 1e6), 2), dl2 = l2max - l2min;
    var dl2ch = 2 * C_LIGHT * C_LIGHT * MP_WIDTH * 1e6 / Math.pow(BAND_MHZ[0] * 1e6, 3);
    var reps = [750.0, 1000.0, 1400.0, 1950.0].map(function (f) {
      var kk = Math.floor((f - BAND_MHZ[0]) / MP_WIDTH), fc = chans[kk][0], sig = chans[kk][1];
      var fac = robustFactors(imaging, fc, obs.dec), psf = scaleBeam(self.psfNat(obs, fc), fac[0]);
      var row = { freq_MHz: fc, sigma_uJy: sig * 1e6, psf: psf, confusion_I_uJy: confusionUJy(Math.sqrt(psf.bmaj * psf.bmin), fc, self.p.confusion_beta),
        tb_mK: tbK(sig, fc, psf) * 1e3 };
      if (smooth && smooth > 0) {
        var kp = smoothPlan(self.psfNat(obs, fc), smooth);
        if (kp) {
          var ws = obs.mode !== 'survey' ? self.haWeights(obs, fc) : [1.0], base = sig / fac[1];
          var nf = taperNoiseFactor(kp, fc, obs.dec, obs.ha_samples, ws), sp = { bmaj: kp.bmaj, bmin: kp.bmin, pa: kp.pa };
          row.smoothed = { target_arcsec: smooth, sigma_uJy: base * nf * 1e6, psf: sp, tb_mK: tbK(base * nf, fc, sp) * 1e3, noise_factor: nf };
        }
      }
      return row;
    });
    return { n_channels: MP_N, chan_MHz: MP_WIDTH, channels: reps, band_qu_sigma_uJy: sigBand * 1e6,
      rmsf_fwhm_rad_m2: 2 * Math.sqrt(3) / dl2, max_scale_rad_m2: Math.PI / l2min, max_rm_rad_m2: Math.sqrt(3) / dl2ch,
      lambda2_range_m2: [l2min, l2max], spectrum: chans.map(function (c) { return [Math.round(c[0] * 1000) / 1000, c[1] * 1e6]; }) };
  };

  // ---------------------------------------------------------------- time domain (Chronoscope pulsars and FRBs)
  CP.tdSetup = function (ra, dec, trackS) {
    var p = this.p, t = (trackS === undefined || trackS === null) ? p.td_track_s : trackS, td = { ra: ra, dec: dec, track_s: t };
    var tp = trackPlan(dec, t / 3600, this.lat, p.el_min_deg, p.ha_max_h);
    for (var k in tp) td[k] = tp[k];
    var lb = radecToLb(ra, dec); td.l_deg = lb[0]; td.b_deg = lb[1];
    td.za_transit = Math.abs(this.lat - dec);
    td.tau_c_s = td.observable ? confusionTauS(p.td_confusion_tau_s, dec, td.ha_half_h, this.lat) : null;
    var e = this.epochsAt(ra, dec, null), ti = e[1];
    td.survey = { tile: ti ? ti.tile : null, 'class': ti ? ti['class'] : null, epochs: e[0], in_7_epoch_tile: e[0] === 7 };
    td._sub = {};
    return td;
  };
  // per-antenna SEFD (Jy) over [fLo, fHi], combined along the track as <SEFD^-2>^-1/2 (same T_sys model as every product)
  // aperture efficiency of the time-domain products (the system value unless set)
  CP.tdSefd = function (td, fLo, fHi) {
    var fc = 0.5 * (fLo + fHi), s = 0;
    for (var i = 0; i < td.ha_samples.length; i++) {
      var za = zenithAngle(td.ha_samples[i], td.dec, this.lat);
      s += Math.pow(this.sefdJy(fc, za, td.ra, td.dec, [fLo, fHi]), -2);
    }
    return Math.pow(s / td.ha_samples.length, -0.5);
  };
  CP.tdSubbands = function (td, fLo, fHi) {
    var key = fLo.toFixed(6) + '-' + fHi.toFixed(6);
    if (td._sub[key]) return td._sub[key];
    var self = this, rows = tdSubbandEdges(fLo, fHi, this.p.td_subband_MHz).map(function (e) {
      var bw = usableBwHz(self.rfi, e[0], e[1], self.extraLoss()), fc = 0.5 * (e[0] + e[1]);
      return { fc: fc, bw_hz: bw, tsys_K: self.tzK(e[0], e[1]), sefd: bw > 0 ? self.tdSefd(td, e[0], e[1]) : Infinity };
    });
    td._sub[key] = rows;
    return rows;
  };
  CP.tdSigmaC = function (fc, ratio) {
    var p = this.p;
    return p.td_confusion_uJy * 1e-6 * Math.pow(fc / p.td_confusion_nu_MHz, p.td_confusion_index) * (ratio === undefined ? 1 : ratio);
  };
  CP.psrPropagation = function (td, dmIn) {
    var p = this.p, dm = (dmIn === undefined || dmIn === null) ? td.psr_dm : dmIn, ne = ne2025At(td.l_deg, td.b_deg, dm), tau1, idx, dist;
    if (p.td_scattering === 'cordes22') { tau1 = tauCordes22Ms(dm, 1000.0); idx = -4.0; dist = null; }
    else { tau1 = ne.tau_1GHz_ms; idx = -4.4; dist = ne.dist_kpc; }
    var tb = {};
    CHR_BANDS.forEach(function (b) { tb[b[0]] = tau1 * Math.pow(0.5 * (b[1] + b[2]) / 1000, idx); });
    return [tau1, idx, { model: p.td_scattering, dm: dm, dist_kpc: dist, tau_1GHz_ms: tau1, tau_index: idx, tau_bands_ms: tb,
      dm_max: ne.dm_max, tau_x_1GHz_ms: ne.tau_x_1GHz_ms, dm_above_max: dm > ne.dm_max,
      scatter_dex: p.td_scattering === 'cordes22' ? 0.76 : null }];
  };
  CP.psrWeff = function (f, tsamp, chan, tau1, idx, dm, wintIn) {
    var p = this.p, wint = (wintIn === undefined || wintIn === null) ? p.psr_width_ms * 1e-3 : wintIn, tdm = chan ? tDmS(dm, chan, f) : 0, tau = tau1 * 1e-3 * Math.pow(f / 1000, idx);
    return [Math.sqrt(wint * wint + tsamp * tsamp + tdm * tdm + tau * tau), wint, tdm, tau];
  };
  // S/N and sigma_TOA of the input pulsar in one band, summed over sub-bands, with the confusion factor
  CP.psrBand = function (td, fLo, fHi, beamDiv, eta, tsamp, chan, confRatio, tau1, idx, period, wint, src) {
    var p = this.p;
    if (!src) src = { flux_mJy: p.psr_flux_mJy, nu_ref_MHz: p.psr_nu_ref_MHz, alpha: p.psr_alpha, dm: td.psr_dm, width_ms: p.psr_width_ms };
    if (wint === undefined || wint === null) wint = src.width_ms * 1e-3;
    var npol = p.n_pol, t = td.track_s, dm = src.dm, sref = src.flux_mJy * 1e-3, nref = src.nu_ref_MHz, alpha = src.alpha;
    var snr2 = 0, snr2ns = 0, toa2 = 0, iv = 0, bw = 0, subs = this.tdSubbands(td, fLo, fHi);
    for (var i = 0; i < subs.length; i++) {
      var s = subs[i];
      if (s.bw_hz <= 0 || !isFinite(s.sefd)) continue;
      var sig = s.sefd / beamDiv / Math.sqrt(npol * s.bw_hz);
      iv += Math.pow(sig, -2); bw += s.bw_hz;
      var w = this.psrWeff(s.fc, tsamp, chan, tau1, idx, dm, wint)[0];
      if (w >= period) continue;
      var si = sref * Math.pow(s.fc / nref, alpha), snrNs = eta * si / sig * Math.sqrt(t) * Math.sqrt((period - w) / w);
      // self-noise: on-pulse flux density S P / W adds to the beam SEFD for a fraction W / P of the data
      var fs = p.td_self_noise ? selfNoiseFactor(si * period / w / (s.sefd / beamDiv), w / period) : 1.0, snr = snrNs * fs;
      snr2 += snr * snr; snr2ns += snrNs * snrNs; toa2 += Math.pow(snr / w, 2);
    }
    var fc = 0.5 * (fLo + fHi), wc = this.psrWeff(fc, tsamp, chan, tau1, idx, dm, wint), sigBand = iv > 0 ? Math.pow(iv, -0.5) : Infinity;
    var conf = psrConfusionFactor(period, wc[0], tsamp, sigBand, this.tdSigmaC(fc, confRatio), td.tau_c_s);
    return { snr: conf * Math.sqrt(snr2), snr_thermal: Math.sqrt(snr2), snr_noself: conf * Math.sqrt(snr2ns),
      self_noise: snr2ns > 0 ? Math.sqrt(snr2 / snr2ns) : 1.0, toa_s: toa2 > 0 ? 1 / (conf * Math.sqrt(toa2)) : Infinity,
      f_center: fc, bw_hz: bw, sigma_1s: sigBand, confusion: conf,
      weff: { weff_ms: wc[0] * 1e3, w_int_ms: wc[1] * 1e3, t_samp_ms: tsamp * 1e3, t_dm_ms: wc[2] * 1e3, tau_ms: wc[3] * 1e3 } };
  };
  CP.psrSrc = function (td, flux) {
    var p = this.p;
    return { flux_mJy: (flux === undefined || flux === null) ? p.psr_flux_mJy : flux, nu_ref_MHz: p.psr_nu_ref_MHz, alpha: p.psr_alpha,
      dm: td.psr_dm, width_ms: p.psr_width_ms };
  };
  // flux density at nu_ref (mJy) at which the pulsar of src reaches S/N thr in one band (self-noise included)
  CP.psrSminMJy = function (args, period, wint, src, thr, r0) {
    var self = this;
    if (!r0) r0 = this.psrBand.apply(this, args.concat([period, wint, src]));
    if (!(r0.snr_noself > 0)) return Infinity;
    var f0 = thr * src.flux_mJy / r0.snr_noself;
    return solveThreshold(function (f) {
      var s2 = {}; for (var k in src) s2[k] = src[k]; s2.flux_mJy = f;
      var r = self.psrBand.apply(self, args.concat([period, wint, s2]));
      return [r.snr, r.snr_noself];
    }, f0, thr);
  };
  CP.psrRow = function (r, fLo, fHi, eta, searched, sminMJy) {
    var p = this.p, nref = p.psr_nu_ref_MHz, alpha = p.psr_alpha, snr = searched ? r.snr : 0;
    var sminRef = searched ? sminMJy * 1e3 : Infinity;
    return { f_lo_MHz: fLo, f_hi_MHz: fHi, f_center_MHz: r.f_center, bw_usable_MHz: r.bw_hz / 1e6, searched: searched, snr: snr,
      smin_uJy: sminRef * Math.pow(r.f_center / nref, alpha), s1400_min_uJy: sminRef * Math.pow(1400 / nref, alpha),
      sefd_beam_Jy: r.bw_hz > 0 ? r.sigma_1s * Math.sqrt(p.n_pol * r.bw_hz) : Infinity,
      weff: r.weff, losses: { quantization: eta, confusion: r.confusion, self_noise: r.self_noise } };
  };
  CP.psrCurve = function (args, pmin, pmax, periods) {
    var p = this.p, self = this, duty = p.psr_width_ms / p.psr_period_ms;   // curves keep the input pulsar's duty cycle
    return periods.map(function (P) {
      if (P < pmin || P > pmax) return null;
      var s = self.psrSminMJy(args, P, duty * P, self.psrSrc(args[0]), p.psr_snr) * 1e3;
      return s * Math.pow(0.5 * (args[1] + args[2]) / p.psr_nu_ref_MHz, p.psr_alpha);
    });
  };
  CP.pulsar = function (td, warnings) {
    var p = this.p, n = p.n_ant, P = p.psr_period_ms * 1e-3, self = this;
    var dmDefault = p.psr_dm === null || p.psr_dm === undefined;
    td.psr_dm = dmDefault ? 0.5 * ne2025At(td.l_deg, td.b_deg, 1.0).dm_max : p.psr_dm;
    var pr = this.psrPropagation(td), tau1 = pr[0], idx = pr[1], prop = pr[2];
    if (prop.dm_above_max && p.td_scattering !== 'cordes22')
      warnings.push('Pulsar DM ' + td.psr_dm.toFixed(0) + ' exceeds the NE2025 Galactic maximum (' + prop.dm_max.toFixed(0) +
        ') at this position: distance and scattering are saturated.');
    var etaS = p.td_eta_v4 * p.td_eta_i2, nbImg = Math.sqrt(n * (n - 1)), periods = [];
    for (var i = 0; i < 200; i++) periods.push(Math.pow(10, Math.log10(3e-4) + i * (Math.log10(10.0) - Math.log10(3e-4)) / 199));
    var curves = { period_s: periods, duty_cycle: p.psr_width_ms / p.psr_period_ms }, beams = p.psr_untargeted_beam_arcsec, untargeted = [];
    var pmin = p.psr_untargeted_pmin_ms * 1e-3, pmax = p.psr_untargeted_pmax_ms * 1e-3;
    CHR_BANDS.forEach(function (b, k) {
      var name = b[0], lo = b[1], hi = b[2], nsum = b[3], fc = 0.5 * (lo + hi);
      var theta = beams ? beams[k] : CHR_UNTARGETED_BEAM_1 * 930.0 / fc, tp = chrTaper(name, td.dec, theta), div = nbImg / tp.f_taper;
      var args = [td, lo, hi, div, etaS, CHR_UNTARGETED_TSAMP_S, CHR_CHAN_MHZ * nsum, tp.sidelobe_ratio, tau1, idx];
      var r = self.psrBand.apply(self, args.concat([P])), row = self.psrRow(r, lo, hi, etaS, pmin <= P && P <= pmax,
        self.psrSminMJy(args, P, null, self.psrSrc(td), p.psr_snr, r));
      row.losses.taper = tp.f_taper;
      var area = p.psr_untargeted_n_beams * HEX_CELL * Math.pow(tp.fwhm_arcsec / 3600, 2);   // hexagonal grid
      var fov = Math.PI / 4 * Math.pow(PB_FWHM_1GHZ / (fc / 1000), 2);
      row.band = name; row.chan_kHz = CHR_CHAN_MHZ * nsum * 1e3; row.tsamp_ms = CHR_UNTARGETED_TSAMP_S * 1e3;
      row.beam_requested_arcsec = theta; row.beam_arcsec = tp.fwhm_arcsec; row.beam_natural_arcsec = tp.natural_fwhm_arcsec;
      row.beam_note = tp.note; row.sidelobe_ratio = tp.sidelobe_ratio; row.n_beams = p.psr_untargeted_n_beams;
      row.area_deg2 = area; row.frac_unique_area = area / CHR_UNIQUE_AREA_DEG2; row.frac_pb_fwhm = area / fov;
      row.period_range_ms = [p.psr_untargeted_pmin_ms, p.psr_untargeted_pmax_ms];
      untargeted.push(row);
      curves['untargeted_' + name] = { f_center_MHz: fc, smin_uJy: self.psrCurve(args, pmin, pmax, periods) };
    });
    var centers = CHR_TARGETED_PRESETS.slice(), sel = p.psr_targeted_center_MHz;
    if (centers.every(function (c) { return Math.abs(sel - c) > 1e-6; })) centers.push(sel);
    var targeted = [], tmin = p.psr_targeted_pmin_ms * 1e-3, tmax = p.psr_targeted_pmax_ms * 1e-3, half = 0.5 * CHR_TARGETED_BW;
    centers.forEach(function (c) {
      var lo = Math.max(c - half, TD_LIMITS[0]), hi = Math.min(c + half, TD_LIMITS[1]);
      if (lo > c - half || hi < c + half)
        warnings.push('Targeted band centered on ' + c.toFixed(2) + ' MHz extends outside 700-2002 MHz; clipped to ' + lo.toFixed(1) + '-' + hi.toFixed(1) + ' MHz.');
      var args = [td, lo, hi, n, etaS, CHR_TARGETED_TSAMP_S, CHR_CHAN_MHZ, 1.0, tau1, idx];
      var r = self.psrBand.apply(self, args.concat([P])), row = self.psrRow(r, lo, hi, etaS, tmin <= P && P <= tmax,
        self.psrSminMJy(args, P, null, self.psrSrc(td), p.psr_snr, r));
      row.center_MHz = c; row.selected = Math.abs(c - sel) <= 1e-6; row.preset = CHR_TARGETED_PRESETS.indexOf(c) >= 0;
      row.toa_us = r.toa_s * 1e6; row.chan_kHz = CHR_CHAN_MHZ * 1e3; row.tsamp_ms = CHR_TARGETED_TSAMP_S * 1e3;
      row.period_range_ms = [p.psr_targeted_pmin_ms, p.psr_targeted_pmax_ms];
      targeted.push(row);
      if (Math.abs(c - sel) <= 1e-6) curves.targeted = { f_center_MHz: r.f_center, smin_uJy: self.psrCurve(args, tmin, tmax, periods) };
    });
    return { inputs: { period_ms: p.psr_period_ms, width_ms: p.psr_width_ms, dm: td.psr_dm, dm_default: dmDefault, flux_mJy: p.psr_flux_mJy,
      nu_ref_MHz: p.psr_nu_ref_MHz, alpha: p.psr_alpha, snr: p.psr_snr },
      propagation: prop, untargeted: untargeted, targeted: targeted, curves: curves };
  };
  // Pulsar Timing subsystem (PTA): four coherently dedispersed voltage beams over 700-2000 MHz, for the PTA pulsar
  CP.pta = function (td, warnings) {
    var p = this.p, n = p.n_ant, P = p.pta_period_ms * 1e-3, i;
    var src = { flux_mJy: p.pta_flux_mJy, nu_ref_MHz: p.pta_nu_ref_MHz, alpha: p.pta_alpha, dm: p.pta_dm, width_ms: p.pta_width_ms };
    var pr = this.psrPropagation(td, src.dm), tau1 = pr[0], idx = pr[1], prop = pr[2];
    if (prop.dm_above_max && p.td_scattering !== 'cordes22')
      warnings.push('PTA pulsar DM ' + src.dm.toFixed(0) + ' exceeds the NE2025 Galactic maximum (' + prop.dm_max.toFixed(0) +
        ') at this position: distance and scattering are saturated.');
    var tsPt = p.pt_tsamp_us * 1e-6, subs = [], snr2 = 0, snr2th = 0, snr2ns = 0, toaIv = 0, self = this;
    var edge = function (k) { return PT_BAND[0] + (PT_BAND[1] - PT_BAND[0]) * k / PT_NSUB; };
    var snrAll = function (f) {
      var s2 = 0, s2n = 0, sf = {}; for (var k in src) sf[k] = src[k]; sf.flux_mJy = f;
      for (var j = 0; j < PT_NSUB; j++) {
        var rr = self.psrBand(td, edge(j), edge(j + 1), n, p.pt_eta, tsPt, null, 1.0, tau1, idx, P, null, sf);
        s2 += rr.snr * rr.snr; s2n += rr.snr_noself * rr.snr_noself;
      }
      return [Math.sqrt(s2), Math.sqrt(s2n)];
    };
    for (i = 0; i < PT_NSUB; i++) {
      var lo = edge(i), hi = edge(i + 1);
      var r = this.psrBand(td, lo, hi, n, p.pt_eta, tsPt, null, 1.0, tau1, idx, P, null, src);
      snr2 += r.snr * r.snr; snr2th += r.snr_thermal * r.snr_thermal; snr2ns += r.snr_noself * r.snr_noself;
      if (isFinite(r.toa_s)) toaIv += Math.pow(r.toa_s, -2);
      subs.push({ f_center_MHz: r.f_center, bw_usable_MHz: r.bw_hz / 1e6, snr: r.snr, toa_us: r.toa_s * 1e6, confusion: r.confusion,
        weff_ms: r.weff.weff_ms, tau_ms: r.weff.tau_ms });
    }
    var snrPt = Math.sqrt(snr2), sminRef = snr2ns > 0 ? solveThreshold(snrAll, p.pta_snr * src.flux_mJy / Math.sqrt(snr2ns), p.pta_snr) * 1e3 : Infinity;
    var wc = this.psrWeff(1350.0, tsPt, null, tau1, idx, src.dm, src.width_ms * 1e-3);
    return { inputs: { period_ms: p.pta_period_ms, width_ms: p.pta_width_ms, dm: src.dm, flux_mJy: src.flux_mJy, nu_ref_MHz: src.nu_ref_MHz,
      alpha: src.alpha, snr: p.pta_snr },
      propagation: prop, f_lo_MHz: PT_BAND[0], f_hi_MHz: PT_BAND[1], n_beams: 4, tsamp_us: p.pt_tsamp_us, track_s: td.track_s,
      snr: snrPt, toa_us: toaIv > 0 ? Math.pow(toaIv, -0.5) * 1e6 : Infinity,
      smin_uJy: sminRef * Math.pow(1350.0 / src.nu_ref_MHz, src.alpha), s1400_min_uJy: sminRef * Math.pow(1400.0 / src.nu_ref_MHz, src.alpha),
      bw_usable_MHz: subs.reduce(function (a, s) { return a + s.bw_usable_MHz; }, 0),
      weff: { weff_ms: wc[0] * 1e3, w_int_ms: wc[1] * 1e3, t_samp_ms: tsPt * 1e3, t_dm_ms: 0.0, tau_ms: wc[3] * 1e3 },
      losses: { quantization: p.pt_eta, confusion: snr2th > 0 ? snrPt / Math.sqrt(snr2th) : 1.0,
        self_noise: snr2ns > 0 ? snrPt / Math.sqrt(snr2ns) : 1.0 }, subbands: subs };
  };

  // FRB
  CP.frbDmBudget = function (td, dmObs) {
    var p = this.p, ne = ne2025At(td.l_deg, td.b_deg, 1.0), dmMw = ne.dm_max, halo = p.frb_dm_halo, hostMed = Math.exp(p.frb_host_mu);
    var ex = dmObs - dmMw - halo, z, host;
    if (ex < hostMed) { z = 0; host = Math.max(ex, 0); }
    else {
      var lo = 0, hi = 10;
      for (var i = 0; i < 60; i++) { var mid = 0.5 * (lo + hi); if (dmCosmic(mid, p.frb_f_d) + hostMed / (1 + mid) < ex) lo = mid; else hi = mid; }
      z = 0.5 * (lo + hi); host = hostMed;
    }
    var tauMw = p.td_scattering !== 'cordes22' ? ne.tau_x_1GHz_ms : 0.0;
    return { dm_obs: dmObs, dm_mw: dmMw, dm_halo: halo, z: z, dm_cosmic: dmCosmic(z, p.frb_f_d), dm_host: host, dm_host_median: hostMed,
      below_galactic: dmObs < dmMw + halo, tau_mw_1GHz_ms: tauMw, tau_host_1GHz_ms: 3 * tauCordes22Ms(host, 1000.0) * Math.pow(1 + z, -3),
      host_scatter_dex: 0.76 };
  };
  CP.frbWeff = function (f, bud) {
    var wint = this.p.frb_width_ms * 1e-3, tdm = tDmS(bud.dm_obs, CHR_CHAN_MHZ, f);
    var tmw = bud.tau_mw_1GHz_ms * 1e-3 * Math.pow(f / 1000, -4.4), th = 3 * tauCordes22Ms(bud.dm_host, f) * Math.pow(1 + bud.z, -3) * 1e-3;
    return [Math.sqrt(wint * wint + FRB_TSAMP_S * FRB_TSAMP_S + tdm * tdm + tmw * tmw + th * th), wint, tdm, tmw, th];
  };
  // fluence (Jy s) at the S/N threshold at the peak of a beam at the beam center (quantization and confusion included)
  CP.frbFluence = function (td, lo, hi, bud) {
    var p = this.p, n = p.n_ant, s2 = 0, iv = 0, bw = 0, subs = this.tdSubbands(td, lo, hi), sub = [];
    for (var i = 0; i < subs.length; i++) {
      var s = subs[i];
      if (s.bw_hz <= 0 || !isFinite(s.sefd)) continue;
      var sefdB = s.sefd / Math.sqrt(n * (n - 1)), sig = sefdB / Math.sqrt(p.n_pol * s.bw_hz), w = this.frbWeff(s.fc, bud)[0];
      s2 += 1 / (sig * sig * w); iv += Math.pow(sig, -2); bw += s.bw_hz; sub.push([sig, w, sefdB]);
    }
    var fc = 0.5 * (lo + hi), wc = this.frbWeff(fc, bud), sigBand = iv > 0 ? Math.pow(iv, -0.5) : Infinity;
    var conf = frbConfusionFactor(wc[0], sigBand, this.tdSigmaC(fc), td.tau_c_s), eta = p.td_eta_v4 * p.td_eta_i4, thr = p.frb_snr;
    if (!(s2 > 0)) return [Infinity, Infinity, wc, conf, sigBand, bw];
    var fl0 = thr / (eta * conf * Math.sqrt(s2));
    // self-noise: the burst's peak flux density f / W adds to the beam SEFD during the burst; the baseline is off-burst
    var fl = solveThreshold(function (f) {
      var a = 0;
      for (var j = 0; j < sub.length; j++) {
        var sg = sub[j][0], ww = sub[j][1], sb = sub[j][2];
        var fs = p.td_self_noise ? selfNoiseFactor(f / ww / sb, ww / (ww + Math.max(1.0, 10 * ww))) : 1.0;
        a += Math.pow(f / (sg * Math.sqrt(ww)) * fs, 2);
      }
      return [eta * conf * Math.sqrt(a), f * eta * conf * Math.sqrt(s2)];
    }, fl0, thr);
    return [fl, fl0, wc, conf, sigBand, bw];
  };
  CP.frb = function (td, warnings) {
    var p = this.p, self = this, bud = this.frbDmBudget(td, p.frb_dm);
    if (bud.below_galactic)
      warnings.push('FRB DM ' + p.frb_dm.toFixed(0) + ' is below the Galactic contribution (DM_MW ' + bud.dm_mw.toFixed(0) + ' + halo ' + bud.dm_halo.toFixed(0) + ') at this position.');
    var eta = p.td_eta_v4 * p.td_eta_i4, pb = 0.5 / Math.log(2), dmt = dmTrialLoss(p.frb_dm_tolerance);
    var psfObs = { mode: 'survey', dec: td.dec, ha_samples: [0.0] }, bands = [];
    var dmLo = Math.max(1.0, bud.dm_mw + bud.dm_halo), dms = [];
    for (var i = 0; i < 60; i++) dms.push(Math.pow(10, Math.log10(dmLo) + i * (Math.log10(Math.max(p.frb_max_dm, dmLo * 1.0001)) - Math.log10(dmLo)) / 59));
    var curves = { dm: dms };
    CHR_BANDS.forEach(function (b) {
      var name = b[0], lo = b[1], hi = b[2], fc = 0.5 * (lo + hi), F = self.frbFluence(td, lo, hi, bud);
      var fl = F[0], fl0 = F[1], wc = F[2], conf = F[3], sigBand = F[4], bw = F[5], selfn = (fl > 0 && isFinite(fl)) ? fl0 / fl : 1.0;
      var psf = self.psfNat(psfObs, fc), strad = hexStraddle(psf), strad_r = hexStraddle(psf, p.frb_alpha_c), loss = strad * pb * dmt, flAll = fl / loss;
      var psfU = scaleBeam(psfNatural1350(td.dec, [0.0], [1.0], self.lat, DATA.psf_uniform.uniform), 1350.0 / fc), covU = covFromBeam(psfU.bmaj, psfU.bmin, psfU.pa);
      var sefdArr = bw > 0 ? sigBand * Math.sqrt(p.n_pol * bw) : Infinity, sefdDsa = sefdArr / (eta * strad_r * dmt * conf * selfn);
      var ref = FRB_RATE_REF[name], fov = Math.PI / 4 * Math.pow(PB_FWHM_1GHZ / (fc / 1000), 2);
      var expo = p.frb_alpha_c * (name === 'B3' ? (1 + p.frb_gamma) : 1.0);
      var omr = frbRateSolidAngle(p.frb_n_beams, Math.sqrt(psf.bmaj * psf.bmin), PB_FWHM_1GHZ / (fc / 1000), p.frb_alpha_c);
      var rate = frbRate(ref[1], ref[3], ref[2], ref[4], omr[0], sefdDsa, bw / 1e6, expo);
      bands.push({ band: name, f_lo_MHz: lo, f_hi_MHz: hi, f_center_MHz: fc, bw_usable_MHz: bw / 1e6, chan_kHz: CHR_CHAN_MHZ * 1e3,
        tsamp_ms: FRB_TSAMP_S * 1e3, sefd_beam_Jy: sefdArr, fluence_peak_Jyms: fl * 1e3, fluence_min_Jyms: flAll * 1e3,
        speak_peak_mJy: fl / wc[0] * 1e3, speak_min_mJy: flAll / wc[0] * 1e3,
        weff: { weff_ms: wc[0] * 1e3, w_int_ms: wc[1] * 1e3, t_samp_ms: FRB_TSAMP_S * 1e3, t_dm_ms: wc[2] * 1e3, tau_mw_ms: wc[3] * 1e3, tau_host_ms: wc[4] * 1e3 },
        losses: { quantization: eta, straddle: strad, pb_average: pb, dm_trial: dmt, confusion: conf, self_noise: selfn, total: eta * conf * selfn * loss },
        fov_deg2: fov, n_beams: p.frb_n_beams, psf: psf, beam_area_deg2: omr[1], beam_coverage: omr[1] / fov, omega_rate_deg2: omr[0],
        straddle_rate: strad_r,
        dm_trials: frbDmTrials(p.frb_width_ms * 1e-3, FRB_TSAMP_S, CHR_CHAN_MHZ, fc, lo, hi, p.frb_max_dm, p.frb_dm_tolerance),
        psf_uniform: psfU, loc_1sigma_arcsec: Math.sqrt(psfU.bmaj * psfU.bmin) / (2 * p.frb_snr),
        loc_ra_1sigma_arcsec: Math.sqrt(covU[0]) / (2 * p.frb_snr), loc_dec_1sigma_arcsec: Math.sqrt(covU[2]) / (2 * p.frb_snr), rate_ref: ref[0], sefd_dsa_Jy: sefdDsa,
        rate_per_yr: rate, rate_in_track: rate * td.track_s / YEAR_S });
      curves[name] = dms.map(function (d) { return self.frbFluence(td, lo, hi, self.frbDmBudget(td, d))[0] / loss * 1e3; });
    });
    return { inputs: { dm: p.frb_dm, width_ms: p.frb_width_ms, snr: p.frb_snr, max_dm: p.frb_max_dm, dm_tolerance: p.frb_dm_tolerance,
      alpha_c: p.frb_alpha_c, gamma: p.frb_gamma }, dm_budget: bud, bands: bands, curves: curves };
  };
  CP.timeDomain = function (ra, dec, products, out, trackS) {
    var p = this.p, td = this.tdSetup(ra, dec, trackS), meta = TSYSBP.meta, self = this, uf = {};
    CHR_BANDS.forEach(function (b) { uf[b[0]] = usableBwHz(self.rfi, b[1], b[2], self.extraLoss()) / ((b[2] - b[1]) * 1e6); });
    out.time_domain = { ra: ra, dec: dec, l_deg: td.l_deg, b_deg: td.b_deg, track_s: td.track_s, observable: td.observable,
      n_transits: td.n_transits, ha_half_h: td.ha_half_h, tau_c_s: td.tau_c_s, survey: td.survey,
      aperture_efficiency: p.aperture_efficiency, tsys_source: meta.source_file, usable_fraction: uf,
      scattering: p.td_scattering };
    if (!td.observable) { out.warnings.push('Time-domain track not observable: the position never rises above the elevation limit.'); return; }
    if (td.n_transits > 1) out.warnings.push('Time-domain track exceeds one transit window; split over ' + td.n_transits + ' transits of ' + (2 * td.ha_half_h).toFixed(2) + ' h.');
    if (products.indexOf('pulsar') >= 0) out.pulsar = this.pulsar(td, out.warnings);
    if (products.indexOf('frb') >= 0) out.frb = this.frb(td, out.warnings);
    if (products.indexOf('pta') >= 0) out.pta = this.pta(td, out.warnings);
  };

  CP.singlePointing = function (obs, scheme) {
    var beta = this.p.confusion_beta, o = {}; for (var k in obs) o[k] = obs[k];
    o.mode = 'targeted'; o.total_time_s = this.p.pointing_s; o.ha_samples = [0.0];
    var rows = this.continuumWindows(o, scheme), fc = this.combineFc(rows, scheme[1], beta);
    return { thermal_uJy: fc.sigma_jy * 1e6, confusion_uJy: fc.confusion_jy * 1e6, total_uJy: fc.total_jy * 1e6, nu_eff_MHz: fc.nu_eff, psf: fc.psf };
  };

  CP.calculate = function (inp) {
    inp = inp || {};
    // default position RA 170, Dec +39.57 (transits at the zenith); an explicit 0 must stay 0
    var has = function (v) { return v !== undefined && v !== null; };
    var mode = inp.mode || 'survey', ra = has(inp.ra) ? +inp.ra : 170.0, dec = has(inp.dec) ? +inp.dec : 39.57, depth = inp.depth || 'full';
    var products = inp.products || ['continuum', 'line', 'polarization', 'frb', 'pulsar', 'pta'];
    var weighting = inp.weighting || 'auto', smooth = +(inp.smooth_arcsec || 0);
    var obs = this.setup(mode, ra, dec, depth, inp.n_epochs, inp.hours, inp.variant);
    var obsOut = {}; for (var k in obs) if (k !== 'ha_samples' && k.charAt(0) !== '_') obsOut[k] = obs[k];
    var out = { inputs: { mode: mode, ra: ra, dec: dec, depth: depth, n_epochs: inp.n_epochs === undefined ? null : inp.n_epochs, hours: inp.hours === undefined ? 1.0 : inp.hours, weighting: weighting,
      smooth_arcsec: smooth, rfi_profile: this.rfi.name, params: JSON.parse(JSON.stringify(this.p)) }, observation: obsOut, warnings: [] };
    var tdProducts = ['pulsar', 'frb', 'pta'].filter(function (k) { return products.indexOf(k) >= 0; });
    var tdTrack = mode !== 'survey' ? obs.total_time_s : null;   // targeted: the on-source time
    if (obs.observable === false) {
      out.warnings.push('Position is not observable with these settings (outside the survey footprint or below the elevation limit).');
      if (tdProducts.length) this.timeDomain(ra, dec, tdProducts, out, tdTrack);
      return out;
    }
    if (mode === 'survey') {
      obsOut.effective_epochs_1350 = this.surveyWeight(obs, 1350.0, obs.depth === 'full' ? null : obs.n_epochs) / mosaicZ(1350.0).zmean;
      obsOut.t_eff_1350_s = this.effTimeS(obs, 1350.0);
    }
    var tb = this.tsysBreakdown(1350.0, obs.za_transit, ra, dec);
    var tbb = this.tsysBand(obs.za_transit, ra, dec);
    Object.keys(tbb).forEach(function (k) { tb[k] = tbb[k]; });
    tb.sefd_1350_Jy = this.sefdJy(1350.0, obs.za_transit, ra, dec);
    tb.sefd_700_Jy = this.sefdJy(700.0, obs.za_transit, ra, dec);
    tb.sefd_2000_Jy = this.sefdJy(2000.0, obs.za_transit, ra, dec);
    tb.tsys_700_K = this.tsysBreakdown(700.0, obs.za_transit, ra, dec).tsys_K;
    tb.usable_band_fraction = usableBwHz(this.rfi, BAND_MHZ[0], BAND_MHZ[1], this.extraLoss()) / ((BAND_MHZ[1] - BAND_MHZ[0]) * 1e6);
    out.system = tb;
    var beta = this.p.confusion_beta, scheme;
    if (weighting === 'auto') {
      var obsRef = obs;
      if (mode === 'survey') { obsRef = {}; for (k in obs) obsRef[k] = obs[k]; obsRef.n_epochs = Math.max(obs.epochs_full, 1); obsRef.depth = 'full'; }
      var cs = this.chooseScheme(obsRef, beta), basis = 'this observation';
      scheme = cs[0];
      if (mode === 'survey') {
        var tile = this.allocation().tiles[obs.tile.tile], sch = tile.scheme && tile.scheme[obs.tile.variant];
        if (sch) scheme = sch.split(':');
        basis = 'tile ' + obs.tile.tile + ' final coadd (' + obs.epochs_full + ' epochs)';
      }
      out.weighting = { imaging: scheme[0], summation: scheme[1], auto: true, comparison: cs[1], basis: basis };
    } else {
      scheme = weighting.split(':');
      out.weighting = { imaging: scheme[0], summation: scheme[1], auto: false };
    }
    if (products.indexOf('continuum') >= 0) {
      var c = this.continuum(obs, scheme, smooth);
      c.snapshots_6s = this.snapshots(obs, scheme);
      if (mode === 'survey') { var one = {}; for (k in obs) one[k] = obs[k]; one.n_epochs = 1; c.single_pointing = this.singlePointing(one, scheme); }
      out.continuum = c;
    }
    if (products.indexOf('line') >= 0) out.line = this.spectralLine(obs, smooth);
    if (products.indexOf('polarization') >= 0) out.polarization = this.polarization(obs, scheme, smooth);
    if (tdProducts.length) this.timeDomain(ra, dec, tdProducts, out, tdTrack);
    if (mode === 'survey' && obs.dec < -27.0) out.warnings.push('Near the southern survey edge (Dec -30.45): fewer overlapping pointings reduce the mosaic depth.');
    if (smooth && smooth > 900.0) out.warnings.push("Smoothing beyond 15′ is set by a few dozen short baselines (72 are shorter than 50 m): at 1.35 GHz the smoothed beam comes out 10–20% narrower than requested, with 10–40% sidelobes, so treat these T_b values as indicative. The limit scales with wavelength (about 30′ at 0.7 GHz).");
    if (mode !== 'survey' && (obs.n_transits || 1) > 1) out.warnings.push('Requested time exceeds one transit window; split over ' + obs.n_transits + ' transits of ' + (2 * obs.ha_half_h).toFixed(2) + ' h.');
    return out;
  };

  return {
    init: init, Calculator: Calculator, DEFAULTS: DEFAULTS, SCHEMES: SCHEMES, WC_EDGES: WC_EDGES, LINE_BANDS: LINE_BANDS,
    CHR_BANDS: CHR_BANDS, BAND_MHZ: BAND_MHZ, TIERS: TIERS, SURVEY_DEC_EDGE: SURVEY_DEC_EDGE,
    rfiDefault: rfiDefault, rfiMeasured: rfiMeasured, rfiNone: rfiNone, residualConfusionUJy: residualConfusionUJy, makeRfiProfile: makeRfiProfile, occAt: occAt, usableBwHz: usableBwHz,
    confusionUJy: confusionUJy, tskyK: tskyK, mosaicZ: mosaicZ, lumDistMpc: lumDistMpc, zenithAngle: zenithAngle,
    radecToLb: radecToLb, lbToRadec: lbToRadec, CHR_TARGETED_PRESETS: CHR_TARGETED_PRESETS,
    data: function () { return DATA; }
  };
});
