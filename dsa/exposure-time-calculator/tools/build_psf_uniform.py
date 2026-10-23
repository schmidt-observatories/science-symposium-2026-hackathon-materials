"""Build python/dsa_etc/data/psf_uniform.json: the uniformly weighted snapshot PSF at zenith and 1.35 GHz.

All 1,360,425 baselines of the configuration at transit for a source at the zenith. Uniform weighting divides each
visibility's weight by the number of visibilities in its uv cell, with cells of 1/FOV for a 2-arcmin localization image
around a detection. The result is converged for fields below a few arcmin (2.03" x 1.57" at 2', 1.96" x 1.52" at 0.5';
2.98" x 2.28" for the whole primary beam, where nearly every visibility has its own cell). The PSF is scaled as 1/nu.
The half-power contour is found along 36 directions (direct Fourier sum) and fitted with an ellipse. The natural-weighted
PSF is computed the same way as a check against the tabulated 3.03" x 2.31", PA 90.6.

Run:  python3 tools/build_psf_uniform.py
"""
import json
import math
import os

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "python", "dsa_etc", "data", "psf_uniform.json")
ANT = os.path.join(ROOT, "python", "dsa_etc", "data", "antennas_enu.json")
C = 299792458.0
ARCSEC = math.pi / 180 / 3600
FREQ = 1350.0
FOV_DEG = 2.0 / 60.0


def uv_zenith():
    a = json.load(open(ANT))
    E, N, U = (np.asarray(a[k], float) for k in ("E", "N", "U"))
    phi = math.radians(a["site_lat_deg"])
    i, j = np.triu_indices(len(E), 1)
    BE, BN, BU = E[j] - E[i], N[j] - N[i], U[j] - U[i]
    Lx = -math.sin(phi) * BN + math.cos(phi) * BU
    Ly = BE
    Lz = math.cos(phi) * BN + math.sin(phi) * BU
    lam = C / (FREQ * 1e6)
    d = phi                                            # source at the zenith, HA = 0
    return Ly / lam, (-math.sin(d) * Lx + math.cos(d) * Lz) / lam


def psf_at(u, v, w, x, y, chunk=24):
    out = np.empty(len(x))
    W = w.sum()
    for s in range(0, len(x), chunk):
        ph = 2 * math.pi * (np.outer(x[s:s + chunk], u) + np.outer(y[s:s + chunk], v))
        out[s:s + chunk] = (np.cos(ph) @ w) / W
    return out


def half_power_ellipse(u, v, w, guess):
    ang = np.arange(36) * math.pi / 36                  # PSF is centrally symmetric
    rr = guess * np.linspace(0.15, 1.3, 28)
    x = (np.outer(np.sin(ang), rr) * ARCSEC).ravel()   # x east, y north
    y = (np.outer(np.cos(ang), rr) * ARCSEC).ravel()
    P = psf_at(u, v, w, x, y).reshape(len(ang), len(rr))
    pts = []
    for k in range(len(ang)):
        p = P[k]
        m = int(np.nonzero(p < 0.5)[0][0])
        r = rr[m - 1] + (0.5 - p[m - 1]) * (rr[m] - rr[m - 1]) / (p[m] - p[m - 1])
        pts.append((r * math.sin(ang[k]), r * math.cos(ang[k])))
    pts = np.asarray(pts)
    # x^T Q x = 1 on the half-power contour; the FWHM covariance is 4 Q^-1 (a radius is half a FWHM)
    A = np.c_[pts[:, 0] ** 2, 2 * pts[:, 0] * pts[:, 1], pts[:, 1] ** 2]
    q = np.linalg.lstsq(A, np.ones(len(pts)), rcond=None)[0]
    S = 4.0 * np.linalg.inv(np.array([[q[0], q[1]], [q[1], q[2]]]))
    ev, evec = np.linalg.eigh(S)
    vmaj = evec[:, 1]
    return {"bmaj": float(math.sqrt(ev[1])), "bmin": float(math.sqrt(ev[0])),
            "pa": float(math.degrees(math.atan2(vmaj[0], vmaj[1])) % 180.0)}


def main():
    u, v = uv_zenith()
    cell = 1.0 / math.radians(FOV_DEG)                 # uv cell (wavelengths)
    iu, iv = np.floor(u / cell).astype(np.int64), np.floor(v / cell).astype(np.int64)
    # each baseline also samples (-u, -v); count both so the weights are Hermitian-symmetric
    keys = np.concatenate([iu * 1000003 + iv, (-iu - 1) * 1000003 + (-iv - 1)])
    uniq, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
    w_uni = 1.0 / cnt[inv[:len(u)]]
    nat = half_power_ellipse(u, v, np.ones(len(u)), 3.5)
    uni = half_power_ellipse(u, v, w_uni, 2.5)
    out = {"config": "dsa1650_P305_v2.5.6.8", "freq_MHz": FREQ, "hour_angle_deg": 0.0, "zenith": True,
           "weighting": "uniform, uv cells of 1/FOV for a %.1f-arcmin localization image" % (FOV_DEG * 60),
           "uniform": uni, "natural_check": nat, "n_cells": int(len(uniq))}
    json.dump(out, open(OUT, "w"), indent=1)
    print("natural (check vs 3.03 x 2.31, PA 90.6):", {k: round(x, 3) for k, x in nat.items()})
    print("uniform:", {k: round(x, 3) for k, x in uni.items()}, "cells", len(uniq))


if __name__ == "__main__":
    main()
