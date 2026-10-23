"""Build python/dsa_etc/data/chr_taper.json: untargeted (visibility) beams of the Chronoscope.

For the three Chronoscope bands (930, 1410, 1800 MHz) and declinations -30..+90 deg (10-deg steps, at transit),
tabulate against a circular Gaussian uv taper T(u) = exp(-pi^2 theta_k^2 |u|^2 / (4 ln 2)) (theta_k = FWHM of the
equivalent image-plane kernel), with natural weighting and all 1,360,425 baselines of the configuration:

  fwhm_arcsec   geometric-mean FWHM of the tapered PSF: the area of its half-power contour (found along 18 directions)
                expressed as a circle, 2 sqrt(A / pi)
  f_taper       noise factor relative to the untapered natural beam, sqrt(sum T^2 * N) / sum T (as taper_noise_factor)
  sidelobe_rms  rms of the PSF (peak 1) over the annulus 10 x FWHM < r < primary-beam FWHM radius, from a direct
                Fourier sum at 4000 random points (same points for every taper; fixed seed)

The engine interpolates f_taper and sidelobe_rms at the requested beam FWHM. Heavy, offline: about 2 min on 20 cores.
Run:  python3 tools/build_chr_taper.py [--procs 20]
"""
import argparse
import json
import math
import os
import time
from multiprocessing import Pool

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ANT = os.path.join(ROOT, "python", "dsa_etc", "data", "antennas_enu.json")
OUT = os.path.join(ROOT, "python", "dsa_etc", "data", "chr_taper.json")
CONFIG = "dsa1650_P305_v2.5.6.8"

C_LIGHT = 299792458.0
ARCSEC = math.pi / 180.0 / 3600.0
FOUR_LN2 = 4.0 * math.log(2.0)
PB_FWHM_1GHZ = 3.36
BANDS = [("B1", 930.0), ("B2", 1410.0), ("B3", 1800.0)]
DECS = [float(d) for d in range(-30, 91, 10)]
KERNELS = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 14.0, 17.0, 20.0, 25.0, 30.0, 40.0, 60.0]
N_ANGLES = 18          # directions over 180 deg (the PSF is centrally symmetric)
N_SIDE = 4000          # random annulus points for the sidelobe rms
CHUNK = 32


def baselines():
    a = json.load(open(ANT))
    E, N, U = (np.asarray(a[k], float) for k in ("E", "N", "U"))
    phi = math.radians(a["site_lat_deg"])
    i, j = np.triu_indices(len(E), 1)
    BE, BN, BU = E[j] - E[i], N[j] - N[i], U[j] - U[i]
    Lx = -math.sin(phi) * BN + math.cos(phi) * BU
    Ly = BE
    Lz = math.cos(phi) * BN + math.sin(phi) * BU
    return Lx, Ly, Lz, a["site_lat_deg"]


def uv(L, freq_mhz, dec):
    """Baselines in wavelengths at transit (HA = 0)."""
    Lx, Ly, Lz = L
    lam = C_LIGHT / (freq_mhz * 1e6)
    d = math.radians(dec)
    return (Ly / lam).astype(np.float32), ((-math.sin(d) * Lx + math.cos(d) * Lz) / lam).astype(np.float32)


def psf_at(u, v, W, x, y):
    """PSF (peak 1) for each weight column of W (nbl x ntaper) at image points (x, y) in radians -> (npts, ntaper)."""
    out = np.empty((len(x), W.shape[1]))
    norm = W.sum(axis=0, dtype=np.float64)
    tp = np.float32(2.0 * math.pi)
    for s in range(0, len(x), CHUNK):
        ph = tp * (np.outer(np.asarray(x[s:s + CHUNK], np.float32), u) + np.outer(np.asarray(y[s:s + CHUNK], np.float32), v))
        out[s:s + CHUNK] = (np.cos(ph) @ W) / norm
    return out


def half_power_fwhm(u, v, w, guess):
    """Geometric-mean FWHM (arcsec) of the half-power contour of the PSF with weights w; guess = rough FWHM (arcsec)."""
    ang = np.arange(N_ANGLES) * math.pi / N_ANGLES
    rr = guess * np.linspace(0.15, 1.2, 22)                      # radii (arcsec) bracketing the half-power radius
    x = (np.outer(np.sin(ang), rr) * ARCSEC).ravel()             # x east (u), y north (v)
    y = (np.outer(np.cos(ang), rr) * ARCSEC).ravel()
    P = psf_at(u, v, w[:, None], x, y)[:, 0].reshape(N_ANGLES, len(rr))
    r_half = []
    for k in range(N_ANGLES):
        p = P[k]
        idx = np.nonzero(p < 0.5)[0]
        if len(idx) == 0:
            raise RuntimeError("half power not reached; increase the radius range")
        m = idx[0]
        r_half.append(rr[m - 1] + (0.5 - p[m - 1]) * (rr[m] - rr[m - 1]) / (p[m] - p[m - 1]))
    r_half = np.asarray(r_half)
    area = 0.5 * np.sum(r_half ** 2) * (2.0 * math.pi / (2 * N_ANGLES)) * 2.0   # both halves of the contour
    return 2.0 * math.sqrt(area / math.pi), 2.0 * r_half.max(), 2.0 * r_half.min()


def one(args):
    band, freq, dec, L = args
    t0 = time.time()
    u, v = uv(L, freq, dec)
    q2 = (u.astype(np.float64) ** 2 + v.astype(np.float64) ** 2)
    W = np.empty((len(u), len(KERNELS)), np.float32)
    for k, th in enumerate(KERNELS):
        W[:, k] = np.exp(-(math.pi ** 2 / FOUR_LN2) * (th * ARCSEC) ** 2 * q2)
    n = float(len(u))
    f_taper = [math.sqrt(float((W[:, k].astype(np.float64) ** 2).sum()) * n) / float(W[:, k].sum(dtype=np.float64))
               for k in range(len(KERNELS))]
    # natural beam scale: 3.03" x 2.31" at zenith and 1.35 GHz, scaled; generous guess
    nat_guess = 2.7 * 1350.0 / freq / max(math.cos(math.radians(abs(dec - 39.554))), 0.3) ** 0.5
    fwhm, fmaj, fmin = [], [], []
    for k, th in enumerate(KERNELS):
        g = math.sqrt(nat_guess ** 2 + th ** 2) * 1.3
        a, b, c = half_power_fwhm(u, v, W[:, k], g)
        fwhm.append(a); fmaj.append(b); fmin.append(c)
    # sidelobe rms over the annulus 10 x FWHM .. primary-beam FWHM radius
    r_out = PB_FWHM_1GHZ / (freq / 1000.0) / 2.0 * 3600.0           # arcsec
    r_in0 = 10.0 * fwhm[0]
    rng = np.random.default_rng(int(freq) * 1000 + int(dec + 100))
    r = np.sqrt(rng.uniform(r_in0 ** 2, r_out ** 2, N_SIDE))
    phi = rng.uniform(0.0, 2.0 * math.pi, N_SIDE)
    x, y = r * np.sin(phi) * ARCSEC, r * np.cos(phi) * ARCSEC
    P = psf_at(u, v, W, x, y)
    side, npts = [], []
    for k in range(len(KERNELS)):
        sel = r >= 10.0 * fwhm[k]
        side.append(float(np.sqrt(np.mean(P[sel, k] ** 2))))
        npts.append(int(sel.sum()))
    return {"band": band, "freq": freq, "dec": dec, "f_taper": f_taper, "fwhm": fwhm, "fwhm_max": fmaj, "fwhm_min": fmin,
            "sidelobe_rms": side, "n_points": npts, "secs": time.time() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=20)
    a = ap.parse_args()
    Lx, Ly, Lz, lat = baselines()
    L = (Lx, Ly, Lz)
    jobs = [(b, f, d, L) for b, f in BANDS for d in DECS]
    t0 = time.time()
    with Pool(a.procs) as pool:
        res = pool.map(one, jobs, chunksize=1)
    print("computed %d (band, dec) cases with %d baselines in %.0f s" % (len(res), len(Lx), time.time() - t0))
    tab = {}
    for b, f in BANDS:
        rows = [r for r in res if r["band"] == b]
        rows.sort(key=lambda r: r["dec"])
        tab[b] = {"freq_MHz": f,
                  "fwhm_arcsec": [[round(x, 4) for x in r["fwhm"]] for r in rows],
                  "fwhm_max_arcsec": [[round(x, 4) for x in r["fwhm_max"]] for r in rows],
                  "fwhm_min_arcsec": [[round(x, 4) for x in r["fwhm_min"]] for r in rows],
                  "f_taper": [[round(x, 6) for x in r["f_taper"]] for r in rows],
                  "sidelobe_rms": [[float("%.5g" % x) for x in r["sidelobe_rms"]] for r in rows],
                  "sidelobe_points": [r["n_points"] for r in rows]}
    out = {"config": CONFIG, "n_baselines": int(len(Lx)), "weighting": "natural, circular Gaussian uv taper",
           "hour_angle_deg": 0.0, "dec_deg": DECS, "kernel_arcsec": KERNELS,
           "annulus": "10 x FWHM to primary-beam FWHM radius (%.2f deg / nu_GHz)" % (PB_FWHM_1GHZ / 2.0),
           "n_annulus_points": N_SIDE, "bands": tab}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=0)
    print("wrote", os.path.relpath(OUT, ROOT), "(%.0f kB)" % (os.path.getsize(OUT) / 1e3))


if __name__ == "__main__":
    main()
