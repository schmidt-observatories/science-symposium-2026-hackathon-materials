"""Build the data tables used by both the Python engine and the web page.

Inputs (in tools/): digitized source figures and the antenna configuration.
Outputs: python/dsa_etc/data/*.json (the web page loads the same files from web/data/).
"""
import json, os, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'python', 'dsa_etc', 'data')
os.makedirs(OUT, exist_ok=True)

def dump(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'))
    print('wrote', name, os.path.getsize(os.path.join(OUT, name)) // 1024, 'KB')

# ---------------------------------------------------------------- RFI occupancy
def build_rfi():
    im = np.array(Image.open(os.path.join(HERE, 'rfi_occupancy_spring_valley.png')).convert('RGB')).astype(float)
    alpha = np.clip((im[..., 2] - im[..., 0]) / 105.0, 0, 1)      # line color (68,116,173) vs white/gray
    x0, f0, x1, f1 = 232.5, 800.0, 1750.5, 2000.0                     # tick calibration (px -> MHz)
    # The plotted curve sits half a pixel above the tick centers (64.5, 348.5) because matplotlib snaps ticks to
    # the pixel grid; its quiet baseline (0%) is at row 348.0, so calibrate on the curve itself.
    y100, y0 = 64.0, 348.0                                            # 100% and 0% rows of the curve
    cols = np.arange(106, 1751)
    freq = f0 + (cols - x0) * (f1 - f0) / (x1 - x0)
    occ = []
    for c in cols:
        rows = np.where(alpha[55:362, c] > 0.35)[0] + 55
        if len(rows) == 0:
            occ.append(np.nan); continue
        w = alpha[rows, c]
        if rows.max() - rows.min() <= 4:            # smooth part of the curve: line center
            y = (rows * w).sum() / w.sum()
        else:                                       # steep edge / narrow spike: conservative (upper edge)
            y = rows.min() + 1.25
        occ.append((y0 - y) / (y0 - y100) * 100.0)
    occ = np.array(occ); ok = np.isfinite(occ)
    freq, occ = freq[ok], np.clip(occ[ok], 0, 100)
    occ[occ < 0.15] = 0.0
    # resample on a uniform grid from 700 to 2000 MHz
    grid = np.round(np.arange(700.0, 2000.0 + 1e-6, 0.8), 3)
    occ_g = np.interp(grid, freq, occ)
    dump('rfi_spring_valley.json', {
        'name': 'Spring Valley measured occupancy (DSA site RFI survey; digitized)',
        'freq_start_MHz': 700.0, 'freq_step_MHz': 0.8, 'occupancy_percent': [round(float(v), 2) for v in occ_g]})
    print('  mean occupancy %.2f%%' % occ_g.mean())

# ---------------------------------------------------------------- RFI: extrapolated to DSA sensitivity
EXTRAP_TARGET_LOSS = 0.15          # band-averaged data loss over 0.70-2.00 GHz


def build_rfi_extrapolated():
    """'Spring Valley model extrapolated': the measured occupancy shape, scaled to the loss expected at DSA sensitivity.

    A more sensitive receiver sees weaker and more distant transmitters, so each channel is modeled as having k times
    as many independent RFI emitters above the flagging threshold as the survey saw: its clean fraction becomes
    (1 - p)^k. This is k*p for quiet channels and saturates smoothly at 100% for busy ones. k is set so that the
    band-averaged loss is 15%. Channels that read zero in the measurement stay at zero.
    """
    import sys
    from scipy.optimize import brentq
    sys.path.insert(0, os.path.join(HERE, '..', 'python'))
    from dsa_etc.engine import make_rfi_profile, usable_bw_hz, BAND_MHZ
    with open(os.path.join(OUT, 'rfi_spring_valley.json')) as f:
        d = json.load(f)
    p = np.asarray(d['occupancy_percent'], float) / 100.0
    freq = d['freq_start_MHz'] + d['freq_step_MHz'] * np.arange(len(p))

    def model(k):
        return 100.0 * (1.0 - (1.0 - p) ** k)

    def loss(k, rounded=False):
        o = np.round(model(k), 3) if rounded else model(k)
        prof = make_rfi_profile(freq, o / 100.0)
        return 1.0 - usable_bw_hz(prof, BAND_MHZ[0], BAND_MHZ[1]) / ((BAND_MHZ[1] - BAND_MHZ[0]) * 1e6)

    k = brentq(lambda x: loss(x) - EXTRAP_TARGET_LOSS, 1.0, 200.0, xtol=1e-10)
    occ = np.round(model(k), 3)
    dump('rfi_spring_valley_extrapolated.json', {
        'name': 'Spring Valley model extrapolated',
        'description': 'Measured Spring Valley occupancy extrapolated to DSA sensitivity: each channel has k = %.2f times '
                       'as many independent RFI emitters above threshold, occupancy 1 - (1 - p)^k, scaled to a %.0f%% '
                       'band-averaged loss over 0.70-2.00 GHz.' % (k, 100 * EXTRAP_TARGET_LOSS),
        'derived_from': 'rfi_spring_valley.json', 'scale_k': round(float(k), 4),
        'band_loss_percent': round(100 * loss(k, rounded=True), 3),
        'freq_start_MHz': d['freq_start_MHz'], 'freq_step_MHz': d['freq_step_MHz'],
        'occupancy_percent': [float(v) for v in occ]})
    print('  k = %.3f, band-averaged loss %.3f%% (measured %.3f%%)' % (k, 100 * loss(k, rounded=True), 100 * loss(1.0)))


# ---------------------------------------------------------------- UCC confusion curves
def build_ucc():
    from scipy.interpolate import UnivariateSpline
    im = np.array(Image.open(os.path.join(HERE, 'ucc_figure_rosero2026.png')).convert('RGB')).astype(float)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    x0, x1, y0, y1 = 139.0, 1019.0, 562.0, 37.0          # frame: log10(theta) 0..3, log10(f) -3..-1
    th = lambda c: 10 ** ((c - x0) / (x1 - x0) * 3)
    fv = lambda rw: 10 ** (-3 + (y0 - rw) / (y0 - y1) * 2)
    gray = (abs(r - g) < 12) & (abs(g - b) < 12) & (r > 90) & (r < 170)
    blue = (b - r > 45) & (b > 170)
    gray[470:560, 860:1015] = False; blue[470:560, 860:1015] = False   # legend
    curves = {16: [], 25: []}
    for c in range(141, 1018):
        for beta, m in ((16, gray), (25, blue)):
            rows = np.where(m[40:560, c])[0] + 40
            if len(rows) >= 3:
                curves[beta].append((np.log10(th(c)), np.log10(fv(rows.mean()))))
    # precise anchors for beta=16 from Rosero memo Tables 3/4 (sigma_c, theta, nu) -> f = sigma_c (nu/1.4)^0.7 / theta^2
    anchors = [(2.23, .087, 1.35), (2.51, .140, 1.35), (2.57, .154, 1.35), (3.02, .272, 1.35), (3.49, .429, 1.35),
               (3.58, .463, 1.35), (3.60, .469, 1.35), (4.20, .713, 1.35), (4.31, .764, 1.35), (4.91, 1.055, 1.35),
               (5.84, 1.55, 1.35), (6.00, 1.65, 1.35), (3.07, .329, 1.12), (4.28, .858, 1.12), (5.16, 1.35, 1.12),
               (7.21, 2.704, 1.12), (2.62, .188, 1.12), (3.56, .520, 1.12), (4.26, .845, 1.12), (5.85, 1.781, 1.12),
               (2.86, .253, 1.15), (3.97, .691, 1.15), (4.78, 1.105, 1.15), (6.65, 2.273, 1.15)]
    grid = np.linspace(0.0, 3.0, 121)                  # log10 theta from 1" to 1000"
    out = {'log10_theta_arcsec': [round(float(v), 4) for v in grid]}
    for beta in (16, 25):
        p = np.array(curves[beta]); x, y = p[:, 0], p[:, 1]
        w = np.ones_like(x)
        if beta == 16:
            ax = np.log10([a[0] for a in anchors]); ay = np.log10([a[1] * (a[2] / 1.4) ** 0.7 / a[0] ** 2 for a in anchors])
            x = np.r_[x, ax]; y = np.r_[y, ay]; w = np.r_[w, np.full(len(ax), 25.0)]
        o = np.argsort(x); x, y, w = x[o], y[o], w[o]
        # merge duplicate x
        xu, idx = np.unique(np.round(x, 4), return_index=True)
        spl = UnivariateSpline(x[idx], y[idx], w=w[idx], s=len(idx) * 0.0004, k=3)
        out['log10_f_beta%d' % beta] = [round(float(v), 5) for v in spl(grid)]
        if beta == 16:
            dev = [10 ** spl(np.log10(a[0])) / (a[1] * (a[2] / 1.4) ** 0.7 / a[0] ** 2) - 1 for a in anchors]
            print('  beta16 spline vs memo anchors: max |dev| %.1f%%' % (100 * np.max(np.abs(dev))))
    out['definition'] = 'sigma_c [uJy/beam] = f(theta) * theta^2 * (nu/1.4 GHz)^-0.7 ; theta = sqrt(bmaj*bmin) [arcsec]'
    out['source'] = 'Condon Universal Confusion Calculator as plotted in Rosero (2026) DSA memo Fig. 1; beta=16 anchored to memo Tables 3-4'
    dump('ucc_confusion.json', out)

# ---------------------------------------------------------------- Galactic sky temperature (GSM2008)
def build_tsky():
    d = np.load(os.path.join(HERE, 'tsky_planes.npz'))
    T = d['T']                                  # (nplane, ndec, nra), K, beam-smoothed, no CMB
    import base64
    lg = np.round(np.log10(np.clip(T, 1e-3, None)) * 1000).astype(np.int16)
    # delta-encode along RA within each Dec row (first column absolute), little-endian int16, base64
    dl = lg.copy(); dl[:, :, 1:] = np.diff(lg, axis=2)
    enc = [base64.b64encode(p.astype('<i2').tobytes()).decode('ascii') for p in dl]
    dump('tsky_gsm2008.json', {
        'source': 'GSM2008 (de Oliveira-Costa et al. 2008), 408-MHz-locked basemap via pygdsm/PyGSM components; '
                  'each plane smoothed with the DSA primary beam (FWHM 3.36 deg / nu[GHz]); CMB excluded',
        'planes_MHz': [float(v) for v in d['planes']], 'dec_start': float(d['dec'][0]), 'dec_step': 1.0,
        'ndec': int(T.shape[1]), 'ra_start': 0.0, 'ra_step': 1.0, 'nra': int(T.shape[2]),
        'Tref_K': [round(float(v), 4) for v in d['Tref']],
        'Tref_definition': 'median over |b|>30 deg, Dec>=-30 (cold sky on which Tsys=21.4 K is quoted)',
        'encoding': 'per plane: base64 little-endian int16, row-major [dec][ra], delta-encoded along RA; value = round(1000*log10(T/K))',
        'log10T_milli_b64delta': enc})

# ---------------------------------------------------------------- robust weighting factors (Rosero memo Fig. 19)
def build_weighting():
    W = json.load(open(os.path.join(HERE, 'weighting_factors_raw.json')))
    fac = {}
    for dec, f in W['factors'].items():
        brv = np.array(f['beam_rv']); brv = np.minimum(brv - (brv[-1] - 1.0), 1.0)      # remove +0.002 read-out offset
        rrv = np.maximum(np.array(f['rms_rv']) / f['rms_rv'][-1], 1.0)
        fac[dec] = {'beam_robust_freq': [round(float(v), 4) for v in brv], 'rms_robust_freq': [round(float(v), 4) for v in rrv],
                    'beam_robust_0p4': f['beam_r04'], 'rms_robust_0p4': f['rms_r04']}
    dump('weighting_factors.json', {'freqs_MHz': W['freqs_MHz'], 'decs': [30, -20, -30, -40], 'factors': fac,
                                    'robust_freq_R': [0.46, 0.71, 0.95, 1.20, 1.45, 1.69, 1.94],
                                    'source': W['source']})

if __name__ == '__main__':
    build_rfi(); build_rfi_extrapolated(); build_ucc(); build_tsky(); build_weighting()
