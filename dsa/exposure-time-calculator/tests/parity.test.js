// Node parity test: JS engine vs Python reference outputs.  Run: node tests/parity.test.js
const fs = require('fs'), path = require('path');
const DATA_DIR = path.join(__dirname, '..', 'python', 'dsa_etc', 'data');
const E = require(path.join(__dirname, '..', 'web', 'js', 'dsa-engine.js'));
const rd = (f) => JSON.parse(fs.readFileSync(path.join(DATA_DIR, f)));
E.init({ rfi: rd('rfi_spring_valley_extrapolated.json'), rfi_measured: rd('rfi_spring_valley.json'), ucc: rd('ucc_confusion.json'), tsky: rd('tsky_gsm2008.json'),
  weighting: rd('weighting_factors.json'), mosaic_z: rd('mosaic_z.json'), antennas: rd('antennas_enu.json'), allocation: rd('allocation.json'),
  tsys_bandpass: rd('tsys_bandpass.json'), tsys_za: rd('tsys_za.json'), psf_uniform: rd('psf_uniform.json'), chr_taper: rd('chr_taper.json'), ne2025: rd('ne2025_grid.json') });
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'cases.json')));
const ref = JSON.parse(fs.readFileSync(path.join(__dirname, 'reference_outputs.json')));
const RTOL = 2e-5, ATOL = 1e-9;
let nfail = 0, ncmp = 0;
function cmp(a, b, where) {
  if (b === 'inf' || b === '-inf') { if (!(a === Infinity || a === -Infinity)) { fail(where, a, b); } ncmp++; return; }
  if (typeof b === 'number') {
    ncmp++;
    if (typeof a !== 'number' || !(Math.abs(a - b) <= ATOL + RTOL * Math.abs(b))) {
      // position angles are defined mod 180 and are ill-defined for near-circular beams
      if (/\.pa$/.test(where) && typeof a === 'number') { const d = Math.abs(((a - b + 90) % 180 + 180) % 180 - 90); if (d < 0.05) return; }
      fail(where, a, b);
    }
    return;
  }
  if (Array.isArray(b)) { if (!Array.isArray(a) || a.length !== b.length) return fail(where + ' (length)', a && a.length, b.length); b.forEach((v, i) => cmp(a[i], v, where + '[' + i + ']')); return; }
  if (b && typeof b === 'object') {
    // PA of a (near-)circular beam is undefined
    if ('bmaj' in b && 'bmin' in b && Math.abs(b.bmaj - b.bmin) <= 1e-3 * b.bmaj) { cmp(a && a.bmaj, b.bmaj, where + '.bmaj'); cmp(a && a.bmin, b.bmin, where + '.bmin'); return; }
    for (const k of Object.keys(b)) { if (k === 'params' || k === 'rfi_profile') continue; cmp(a ? a[k] : undefined, b[k], where + '.' + k); } return; }
  ncmp++; if (a !== b && !(a === undefined && b === null) && !(a === null && b === undefined)) fail(where, a, b);
}
function fail(where, a, b) { nfail++; if (nfail < 40) console.log('MISMATCH', where, 'js=', a, 'py=', b); }
const t0 = Date.now();
cases.forEach((c, i) => {
  const calc = new E.Calculator({ params: c.params || {}, rfi: c.rfi === 'none' ? E.rfiNone() : c.rfi === 'measured' ? E.rfiMeasured() : undefined });
  const t = Date.now();
  const r = calc.calculate(c.inp);
  cmp(r, ref[i].result, c.name);
  console.log(c.name.padEnd(34), (Date.now() - t) + ' ms');
});
console.log(`compared ${ncmp} values, ${nfail} mismatches, total ${Date.now() - t0} ms`);
process.exit(nfail ? 1 : 0);
