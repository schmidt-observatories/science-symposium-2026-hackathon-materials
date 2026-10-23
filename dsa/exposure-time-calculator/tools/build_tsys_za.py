"""Build python/dsa_etc/data/tsys_za.json: the increase of T_sys with zenith angle, dT(nu, ZA), added to the zenith
bandpass (tsys_bandpass.json, which already contains the zenith spillover and zenith atmosphere).

Two terms, each relative to its zenith value:

  Spillover   tools/inputs/dsa_feedv3_gendish6p15m_tsp_freqghz_v_za.txt: simulated spillover temperature of the
              6.15-m dish with the v3 feed (J. Jonas), 0.7-2.0 GHz in 25-MHz steps, ZA 0-80 deg in 5-deg steps.
              The simulation alternates point to point in frequency (an undersampled standing wave), so each ZA row is
              smoothed with a 1-2-1 kernel (zero response at the 25-MHz alternation; ends reflected).
  Atmosphere  ITU-R P.676-12 line-by-line oxygen and water-vapour absorption through the ITU-R P.835 mid-latitude
              reference atmospheres (summer and winter averaged), with the water vapor scaled to the ITU-R P.836
              median at the site (8.4 mm), from the site height (1746 m) upward; spherical path, no refraction.
              Radiative transfer: T_atm = integral T(h) dtau exp(-tau).

The spillover table of version 1 (tools/inputs/tsysovereta_6p15m_cylshield.txt, total T_sys/eta) is reproduced by
these two terms to ~0.1 K rms (band average, ZA 0-75 deg, eta = 0.67); tests/test_engine.py checks it.

Needs the itur package (pip install itur); the engine reads only the JSON.
Run:  python3 tools/build_tsys_za.py [--plot tools/tsys_za_components.png]
"""
import argparse
import json
import os
import warnings

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "tools", "inputs", "dsa_feedv3_gendish6p15m_tsp_freqghz_v_za.txt")
OUT = os.path.join(ROOT, "python", "dsa_etc", "data", "tsys_za.json")
LAT, LON, H0 = 39.55393, -114.42415, 1.7463     # site (antennas_enu.json); km
RE = 6371.0


def read_spill():
    rows = [ln.rstrip("\n").split("\t") for ln in open(SRC) if ln.strip()]
    f = np.array([float(x) for x in rows[0][1:] if x])
    za = np.array([float(r[0]) for r in rows[1:]])
    T = np.array([[float(x) for x in r[1:] if x] for r in rows[1:]])
    return f, za, T


def smooth121(y):
    p = np.concatenate([[y[1]], y, [y[-2]]])
    return 0.25 * p[:-2] + 0.5 * p[1:-1] + 0.25 * p[2:]


def atmosphere(f_ghz, za_deg):
    warnings.filterwarnings("ignore")
    import itur.models.itu676 as m
    import itur.models.itu835 as s
    import itur.models.itu836 as w

    def val(q):
        return float(getattr(q, "value", q))

    pwv = val(w.total_water_vapour_content(LAT, LON, 50, H0))
    h = np.concatenate([np.arange(H0, 10, 0.05), np.arange(10, 30, 0.25), np.arange(30, 80, 1.0)])
    out = np.zeros((len(za_deg), len(f_ghz)))
    for season in ("summer", "winter"):
        P = np.array([val(s.pressure(LAT, x, season)) for x in h])
        T = np.array([val(s.temperature(LAT, x, season)) for x in h])
        rho = np.array([val(s.water_vapour_density(LAT, x, season)) for x in h])
        rho *= pwv / (np.trapezoid(rho, h * 1000) / 1000.0)
        for j, fg in enumerate(f_ghz):
            g = np.array([val(m.gamma0_exact(fg, p, r, t)) + val(m.gammaw_exact(fg, p, r, t))
                          for p, r, t in zip(P, rho, T)])
            k = g / (10 * np.log10(np.e))                       # nepers / km
            for i, z in enumerate(za_deg):
                e = np.radians(90 - z)
                dtau = k / np.sqrt(1 - ((RE + H0) * np.cos(e) / (RE + h)) ** 2)
                tau = np.concatenate([[0], np.cumsum(0.5 * (dtau[1:] + dtau[:-1]) * np.diff(h))])
                out[i, j] += 0.5 * np.trapezoid(T * dtau * np.exp(-tau), h)
    return out, pwv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", help="also write a PNG of the two terms")
    a = ap.parse_args()
    f, za, Tsp = read_spill()
    sp = np.array([smooth121(r) for r in Tsp])
    atm, pwv = atmosphere(f, za)
    dsp, datm = sp - sp[0], atm - atm[0]
    out = {
        "name": "Increase of T_sys with zenith angle relative to zenith: spillover + atmosphere (K)",
        "spill_source": os.path.basename(SRC) + " (J. Jonas, feed v3 on the 6.15-m dish), 1-2-1 smoothed in frequency",
        "atm_source": "ITU-R P.676-12 (O2 + H2O, line by line), P.835 mid-latitude summer/winter averaged, P.836 "
                      "median water vapor %.1f mm, site height %.0f m" % (pwv, H0 * 1000),
        "method": "tools/build_tsys_za.py",
        "freq_MHz": [round(float(x) * 1000, 3) for x in f], "za_deg": [float(x) for x in za],
        "spill_K": [[round(float(v), 4) for v in r] for r in dsp],
        "atm_K": [[round(float(v), 4) for v in r] for r in datm],
        "spill_zenith_K": [round(float(v), 4) for v in sp[0]],
        "atm_zenith_K": [round(float(v), 4) for v in atm[0]],
        "pwv_mm": round(pwv, 2),
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("wrote", os.path.relpath(OUT, ROOT), "(PWV %.1f mm)" % pwv)
    for z in (20, 40, 60, 70, 80):
        i = list(za).index(z)
        print("  ZA %2d: spillover %.2f K, atmosphere %.2f K (band mean); at 0.7/1.35/2.0 GHz total %s" % (
            z, dsp[i].mean(), datm[i].mean(),
            np.round([np.interp(x, f, dsp[i] + datm[i]) for x in (0.7, 1.35, 2.0)], 2)))
    print("  zenith atmosphere %.2f-%.2f K, zenith spillover mean %.2f K (both already in the bandpass)" % (
        atm[0].min(), atm[0].max(), sp[0].mean()))

    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
        for z, c in zip((20, 40, 60, 70, 80), ("#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b")):
            i = list(za).index(z)
            ax[0].plot(f * 1000, Tsp[i] - Tsp[0], color=c, lw=.6, alpha=.5)
            ax[0].plot(f * 1000, dsp[i], color=c, lw=1.8, label="ZA %d" % z)
            ax[0].plot(f * 1000, datm[i], color=c, lw=1.2, ls="--")
            ax[1].plot(f * 1000, dsp[i] + datm[i], color=c, lw=1.8, label="ZA %d" % z)
        ax[0].set_title("spillover (solid; thin = unsmoothed) and atmosphere (dashed)")
        ax[1].set_title("total increase of T_sys over zenith")
        for A in ax:
            A.set_xlabel("frequency (MHz)")
            A.set_ylabel("K")
            A.legend(fontsize=8)
        plt.tight_layout()
        plt.savefig(a.plot, dpi=90)
        print("wrote", a.plot)


if __name__ == "__main__":
    main()
