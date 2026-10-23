"""Build python/dsa_etc/data/tsys_bandpass.json: the system temperature at zenith, T_sys(nu), used by every product.

Input (PI file, tools/inputs/):
  tsys_feedlnaint_aug2025_30C.txt  T_sys(nu) measured at zenith on cold sky, 700-2000 MHz in 2-MHz steps (feed + LNA +
                                   integration, Aug 2025, 30 C). It includes receiver, zenith spillover, atmosphere,
                                   CMB and cold sky, and also the RFI present when it was measured.

The measurement is a bandpass plus RFI. RFI is removed here so that it is not counted twice: data loss to RFI is
handled by the occupancy model (Spring Valley model extrapolated by default), and T_sys(nu) must be the bandpass alone.

Separation (RFI only adds power):
  1. Spring Valley channels: a 2-MHz point is an RFI channel if the Spring Valley occupancy within it exceeds 0.5%
     (measured) or 5% (extrapolated model). An RFI channel is masked unless it lies at or below the interpolation of
     the clean points around it (within max(2 sigma, 0.3 K)); a point that is not raised carries the bandpass.
  2. RFI seen only where T_sys was measured: any point more than max(5 sigma, 2 K) above an 11-point (22-MHz) running
     median of the clean bandpass is masked, with neighbors more than max(3 sigma, 0.7 K) above it.
     sigma is the robust (MAD) scatter of clean points about that median.
  3. Steps 1-2 are iterated to convergence. Masked points are replaced by linear interpolation between clean points,
     and the result is smoothed lightly (Savitzky-Golay, 5 points = 10 MHz, quadratic).
  Non-positive or > 200 K values (the drop-out near 1990 MHz) are masked. The 2002-MHz point repeats 2000 MHz.

The increase of T_sys with zenith angle (spillover and atmosphere) is added to this zenith value by the engine, from
tsys_za.json (tools/build_tsys_za.py).

Run:  python3 tools/build_tsys.py [--plot tools/tsys_bandpass.png]
"""
import argparse
import json
import os

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "python", "dsa_etc", "data")
SRC = os.path.join(ROOT, "tools", "inputs", "tsys_feedlnaint_aug2025_30C.txt")
OUT = os.path.join(DATA, "tsys_bandpass.json")

SV_MEASURED_PCT = 0.5        # Spring Valley measured occupancy marking an RFI channel
SV_MODEL_PCT = 5.0           # Spring Valley extrapolated occupancy marking an RFI channel
WIN = 11                     # running-median window (points) for the local-RFI test


def runmed(y, win=WIN):
    h = win // 2
    return np.array([np.median(y[max(0, i - h):i + h + 1]) for i in range(len(y))])


def savgol5(y):
    """Savitzky-Golay, 5 points, quadratic (coefficients -3, 12, 17, 12, -3 / 35); ends use the nearest full window."""
    c = np.array([-3.0, 12.0, 17.0, 12.0, -3.0]) / 35.0
    out = y.copy()
    for i in range(2, len(y) - 2):
        out[i] = float(np.dot(c, y[i - 2:i + 3]))
    return out


def runs(f, flag):
    out, i = [], 0
    while i < len(f):
        if flag[i]:
            j = i
            while j + 1 < len(f) and flag[j + 1]:
                j += 1
            out.append([float(f[i]), float(f[j])])
            i = j + 1
        else:
            i += 1
    return out


def occupancy_per_point(f, name):
    d = json.load(open(os.path.join(DATA, name)))
    fs = d["freq_start_MHz"] + d["freq_step_MHz"] * np.arange(len(d["occupancy_percent"]))
    o = np.asarray(d["occupancy_percent"], float)
    return np.array([o[(fs >= x - 1.4) & (fs <= x + 1.4)].max(initial=0.0) for x in f])


def separate(f, T):
    occ = occupancy_per_point(f, "rfi_spring_valley.json")
    occx = occupancy_per_point(f, "rfi_spring_valley_extrapolated.json")
    sv = (occx > SV_MODEL_PCT) | (occ > SV_MEASURED_PCT)
    bad = ~np.isfinite(T) | (T <= 0) | (T > 200)
    interp = lambda mask: np.interp(f, f[~mask], T[~mask])  # noqa: E731
    m = bad.copy()
    for _ in range(50):
        base = runmed(interp(m | sv))
        r = T - base
        s = 1.4826 * np.median(np.abs(r[~(m | sv)]))
        strong = r > max(5 * s, 2.0)
        local = strong.copy()
        for i in np.where(strong)[0]:
            for j in (i - 1, i + 1):
                if 0 <= j < len(f) and r[j] > max(3 * s, 0.7):
                    local[j] = True
        b0 = interp(bad | local | sv)
        svmask = sv & (T > b0 + max(2 * s, 0.3))
        new = bad | local | svmask
        if (new == m).all():
            break
        m = new
    clean = savgol5(interp(m))
    kind = np.where(bad, "dropout", np.where(svmask, "spring_valley", np.where(local, "local", "")))
    return clean, m, kind, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", help="also write a PNG comparing the measurement and the bandpass")
    a = ap.parse_args()
    d = np.loadtxt(SRC, skiprows=1)
    f = np.round(d[:, 0] * 1000.0, 3)
    T = d[:, 1].astype(float)
    step = float(np.median(np.diff(f)))
    assert np.allclose(np.diff(f), step), "irregular frequency grid"
    f = np.append(f, f[-1] + step)
    T = np.append(T, T[-1])
    clean, m, kind, s = separate(f, T)

    out = {
        "name": "DSA T_sys bandpass at zenith on cold sky, RFI removed (feed+LNA, Aug 2025, 30 C)",
        "source_file": os.path.basename(SRC),
        "method": "tools/build_tsys.py: RFI channels from the Spring Valley occupancy and local outliers masked, "
                  "linear interpolation, 10-MHz Savitzky-Golay smoothing",
        "freq_start_MHz": float(f[0]), "freq_step_MHz": step,
        "tsys_zenith_K": [round(float(x), 4) for x in clean],
        "tsys_measured_K": [round(float(x), 4) for x in T],
        "rfi_masked": m.astype(int).tolist(),
        "rfi_regions_MHz": {k: runs(f, kind == k) for k in ("spring_valley", "local", "dropout")},
        "scatter_K": round(float(s), 4),
        "median_K": round(float(np.median(clean)), 4), "mean_K": round(float(clean.mean()), 4),
        "measured_median_K": round(float(np.median(T[T > 0])), 4),
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("wrote", os.path.relpath(OUT, ROOT))
    print("  %d points %.0f-%.0f MHz; masked %d (%.1f%%); scatter %.2f K" % (len(f), f[0], f[-1], m.sum(),
                                                                          100 * m.mean(), s))
    print("  bandpass median %.2f K, mean %.2f K (measurement median %.2f K)" % (out["median_K"], out["mean_K"],
                                                                                out["measured_median_K"]))
    for k, v in out["rfi_regions_MHz"].items():
        print("  %-14s" % k, v)

    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        sv = json.load(open(os.path.join(DATA, "rfi_spring_valley.json")))
        sx = json.load(open(os.path.join(DATA, "rfi_spring_valley_extrapolated.json")))
        fs = sv["freq_start_MHz"] + sv["freq_step_MHz"] * np.arange(len(sv["occupancy_percent"]))
        ranges = [(700, 920), (920, 1140), (1140, 1360), (1360, 1580), (1580, 1800), (1800, 2002)]
        fig, ax = plt.subplots(len(ranges), 1, figsize=(12, 15))
        for A, (lo, hi) in zip(ax, ranges):
            k = (f >= lo) & (f <= hi)
            B = A.twinx()
            ks = (fs >= lo) & (fs <= hi)
            B.fill_between(fs[ks], np.asarray(sv["occupancy_percent"])[ks], step="mid", color="#4c8bd6", alpha=.25,
                           lw=0, label="Spring Valley occupancy, measured")
            B.plot(fs[ks], np.asarray(sx["occupancy_percent"])[ks], color="#e07b39", lw=.7, drawstyle="steps-mid",
                   label="Spring Valley model extrapolated")
            B.set_ylim(0, 100)
            B.set_ylabel("occupancy (%)")
            A.set_zorder(B.get_zorder() + 1)
            A.patch.set_visible(False)
            A.plot(f[k], T[k], ".-", color="#333", lw=.6, ms=3, label="T_sys measured")
            A.plot(f[k & m], T[k & m], "x", color="#c62828", ms=5, label="RFI (masked)")
            A.plot(f[k], clean[k], "-", color="#2e7d32", lw=1.8, label="T_sys bandpass (this file)")
            A.set_xlim(lo, hi)
            A.set_ylim(14, 40)
            A.set_ylabel("T_sys (K)")
        ax[0].legend(loc="upper left", fontsize=8, ncol=3)
        B.legend(loc="upper left", fontsize=8)
        ax[-1].set_xlabel("frequency (MHz)")
        plt.tight_layout()
        plt.savefig(a.plot, dpi=90)
        print("wrote", a.plot)


if __name__ == "__main__":
    main()
