"""
CASS epoch allocation v2: distribute the full 5 x 12,850 = 64,250 pointing-epoch budget over the 429
tiered-tile survey tiles, using the DSA calculator's noise model (measured T_sys bandpass, spillover and atmosphere
vs zenith angle, Galactic synchrotron, RFI occupancy, mosaic weight, confusion with the best weighting per tile).

Figure of merit: continuum sources detected at 5 sigma in the final full-band coadd, from the 1.4-GHz source
counts implied by Condon's Universal Confusion Calculator (the same counts that set the confusion noise).

Variants (A is the default)
  A  "DSA-00264 corrected fill":   Galactic plane/bulge = 7, Euclid/HSC = 7 (as DSA-00264), wide area >= 2 with
     the rest of the budget placed where it adds the most detections.
  B  "uniform Euclid/HSC depth":  as A, but the Euclid/HSC tiles share the same total time so that each
     reaches one common final noise.
  C  "Maximum detections":         every tile >= 2, Galactic plane/bulge >= 7, all remaining budget placed by
     marginal detections per pointing-epoch.
The per-tile noise table is cached in tools/tile_eval.json and recomputed whenever the noise model changes.
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
from dsa_etc.engine import (DSACalculator, SCHEMES, _load, robust_factors, confusion_uJy, _cov_from_beam,   # noqa
                            _beam_from_cov, mosaic_z, usable_bw_hz, WC_EDGES, DATA_DIR)

BUDGET = 5 * 12850
N_MAX = 16
AS = math.pi / 180 / 3600


def counts_table():
    d = _load("ucc_confusion.json")
    lt = np.array(d["log10_theta_arcsec"]); th = 10 ** lt
    S = 5 * 10 ** np.array(d["log10_f_beta16"]) * th ** 2                         # uJy at 1.4 GHz
    om = math.pi * (th * AS) ** 2 / (4 * math.log(2))
    N = 1.0 / (16 * om) / (180 / math.pi) ** 2                                     # per deg^2
    o = np.argsort(S)
    return np.log10(S[o]), np.log10(N[o])


LS, LN = counts_table()


def n_above(s_uJy_1400):
    return 10 ** np.interp(np.log10(s_uJy_1400), LS, LN)


def tile_area_deg2(t):
    return (math.radians(t["ra1"] - t["ra0"]) * (math.sin(math.radians(t["dec1"])) - math.sin(math.radians(t["dec0"])))
            * (180 / math.pi) ** 2)


def evaluate_tiles(calc, tiles):
    """For each tile and n=1..N_MAX: RMS final total noise (best scheme), detections, chosen scheme."""
    beta = calc.p["confusion_beta"]
    out = {}
    fr = [0.5 * (WC_EDGES[i] + WC_EDGES[i + 1]) for i in range(10)]
    bws = [usable_bw_hz(calc.rfi, WC_EDGES[i], WC_EDGES[i + 1], calc.extra_loss) for i in range(10)]
    ns = np.arange(1, N_MAX + 1)
    for key, t in tiles.items():
        fr_ra = [t["ra0"] + (t["ra1"] - t["ra0"]) * f for f in (1 / 6, 0.5, 5 / 6)]
        fr_de = [t["dec0"] + (t["dec1"] - t["dec0"]) * f for f in (1 / 6, 0.5, 5 / 6)]
        if t["tier"] == "N11":
            fr_de = [88.0, 89.0, 89.5]
        pos = [(r, d) for r in fr_ra for d in fr_de]
        tot = np.zeros((len(SCHEMES), len(pos), N_MAX))
        det = np.zeros((len(SCHEMES), len(pos), N_MAX))
        for ip, (ra, dec) in enumerate(pos):
            obs = calc.setup("survey", ra, max(dec, -30.4), depth="custom", n_epochs=1)
            if obs["tile"] is None:
                obs = calc.setup("survey", ra, -30.4, depth="custom", n_epochs=1)
            sig1 = {}
            psf = {}
            for im in ("natural", "robust_freq", "robust_0p4"):
                s_list, p_list = [], []
                for i, f in enumerate(fr):
                    b, r = robust_factors(im, f, dec)
                    sefd = calc.sefd_eff(obs, f, (WC_EDGES[i], WC_EDGES[i + 1]))
                    teff = calc.p["pointing_s"] * mosaic_z(f, max(dec, -30.4))["zmean"]
                    s_list.append(r * calc.radiometer_jy(sefd, bws[i], teff))
                    pn = calc.psf_nat(obs, f)
                    p_list.append({"bmaj": pn["bmaj"] * b, "bmin": pn["bmin"] * b, "pa": pn["pa"]})
                sig1[im] = np.array(s_list)
                psf[im] = p_list
            for isc, (im, su) in enumerate(SCHEMES):
                s = sig1[im]
                for k, n in enumerate(ns):
                    sn = s / math.sqrt(n)
                    w = 1 / sn ** 2 if su == "optimal" else np.ones_like(sn)
                    sw = w.sum()
                    sig = math.sqrt((w ** 2 * sn ** 2).sum()) / sw
                    nu = (w * np.array(fr)).sum() / sw
                    if k == 0 or su == "optimal":
                        Kinv = sum(wi * np.linalg.inv(_cov_from_beam(p["bmaj"], p["bmin"], p["pa"]))
                                   for wi, p in zip(w, psf[im])) / sw
                        pb = _beam_from_cov(np.linalg.inv(Kinv))
                        conf = confusion_uJy(math.sqrt(pb["bmaj"] * pb["bmin"]), nu, beta) * 1e-6
                    tt = math.hypot(sig, conf)
                    tot[isc, ip, k] = tt
                    det[isc, ip, k] = n_above(5 * tt * 1e6 * (nu / 1400.0) ** 0.7)
        rms = np.sqrt((tot ** 2).mean(axis=1))                  # (scheme, n)
        best = rms.argmin(axis=0)                               # per n
        area = tile_area_deg2(t)
        out[key] = {"area": area, "rms_uJy": [float(rms[best[k], k] * 1e6) for k in range(N_MAX)],
                    "det": [float(area * det[best[k], :, k].mean()) for k in range(N_MAX)],
                    "scheme": [SCHEMES[best[k]][0] + ":" + SCHEMES[best[k]][1] for k in range(N_MAX)]}
    return out


def greedy(ev, tiles, n0, budget, fixed=(), n_max=N_MAX):
    """Add epochs one tile at a time by marginal detections per pointing-epoch until the budget is used."""
    n = dict(n0)
    used = sum(n[k] * tiles[k]["n_ptg"] for k in n)
    while True:
        best, gain = None, -1
        for k in n:
            if k in fixed or n[k] >= n_max:
                continue
            if used + tiles[k]["n_ptg"] > budget:
                continue
            g = (ev[k]["det"][n[k]] - ev[k]["det"][n[k] - 1]) / tiles[k]["n_ptg"]
            if g > gain:
                best, gain = k, g
        if best is None:
            break
        n[best] += 1
        used += tiles[best]["n_ptg"]
    return n, used


def greedy_exact(ev, tiles, n0, budget, fixed=(), n_max=N_MAX):
    """greedy(), then use the whole budget: if pointings are left over because no tile fits them, try each tile of a
    different size (the 10-pointing polar cap) at every allowed depth and keep the exact fill with most detections."""
    n, used = greedy(ev, tiles, n0, budget, fixed, n_max)
    if used == budget:
        return n, used
    det = lambda m: sum(ev[k]["det"][m[k] - 1] for k in m)                        # noqa: E731
    size = max(set(t["n_ptg"] for t in tiles.values()), key=[t["n_ptg"] for t in tiles.values()].count)
    best = None
    for k in [k for k in n if tiles[k]["n_ptg"] != size and k not in fixed]:
        for m in range(n0[k], n_max + 1):
            n1 = dict(n0)
            n1[k] = m
            nn, u = greedy(ev, tiles, n1, budget, set(fixed) | {k}, n_max)
            if u == budget and (best is None or det(nn) > det(best[0])):
                best = (nn, u)
    return best if best else (n, used)


def equal_depth(ev, tiles, keys, budget):
    """Epochs per tile to reach a common final noise, using at most `budget` pointing-epochs over `keys`."""
    lo, hi = 0.05, 5.0
    best = None
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        n = {}
        for k in keys:
            r = ev[k]["rms_uJy"]
            m = next((i + 1 for i, v in enumerate(r) if v <= mid), N_MAX)
            n[k] = max(m, 2)
        used = sum(n[k] * tiles[k]["n_ptg"] for k in keys)
        if used > budget:
            lo = mid
        else:
            hi = mid
            best = (n, used, mid)
    return best


def summarize(name, n, ev, tiles):
    used = sum(n[k] * tiles[k]["n_ptg"] for k in n)
    area = {k: ev[k]["area"] for k in n}
    A = sum(area.values())
    det = sum(ev[k]["det"][n[k] - 1] for k in n)
    by_cls = {}
    for c in ("euclid_hsc", "galactic", "wide"):
        ks = [k for k in n if tiles[k]["class"] == c]
        rms = [ev[k]["rms_uJy"][n[k] - 1] for k in ks]
        by_cls[c] = {"tiles": len(ks), "area_deg2": sum(area[k] for k in ks),
                     "mean_epochs": sum(n[k] * area[k] for k in ks) / sum(area[k] for k in ks),
                     "median_total_uJy": float(np.median(rms)), "p10_total_uJy": float(np.percentile(rms, 10)),
                     "p90_total_uJy": float(np.percentile(rms, 90)),
                     "detections_millions": sum(ev[k]["det"][n[k] - 1] for k in ks) / 1e6}
    hist = {}
    for k in n:
        hist[n[k]] = hist.get(n[k], 0) + area[k]
    return {"variant": name, "pointing_epochs": used, "budget": BUDGET, "mean_epochs": sum(n[k] * area[k] for k in n) / A,
            "detections_millions": det / 1e6, "area_by_epochs": {str(k): round(v) for k, v in sorted(hist.items())},
            "by_class": by_cls}


def main():
    al = _load("allocation.json")
    tiles = al["tiles"]
    calc = DSACalculator()
    cache = os.path.join(HERE, "tile_eval.json")
    # anything that changes the per-tile noise invalidates the cache
    signature = {"params": {k: v for k, v in calc.p.items() if not isinstance(v, (dict, list))},
                 "rfi": calc.rfi["name"],
                 "usable": round(usable_bw_hz(calc.rfi, 700.0, 2002.0, calc.extra_loss) / 1302e6, 6)}
    ev = None
    if os.path.exists(cache):
        c = json.load(open(cache))
        if isinstance(c, dict) and c.get("signature") == signature:
            ev = c["tiles"]
    if ev is None:
        print("evaluating tiles for", signature["rfi"], "...")
        ev = evaluate_tiles(calc, tiles)
        json.dump({"signature": signature, "tiles": ev}, open(cache, "w"))
    keys = list(tiles)
    gp = [k for k in keys if tiles[k]["class"] == "galactic"]
    eh = [k for k in keys if tiles[k]["class"] == "euclid_hsc"]
    wide = [k for k in keys if tiles[k]["class"] == "wide"]
    variants = {}
    # A
    n0 = {k: (7 if k in gp or k in eh else 2) for k in keys}
    nA, uA = greedy_exact(ev, tiles, n0, BUDGET, fixed=set(gp) | set(eh))
    variants["A"] = nA
    # B
    eh_budget = sum(7 * tiles[k]["n_ptg"] for k in eh)
    nEH, uEH, target = equal_depth(ev, tiles, eh, eh_budget)
    n0 = {k: (7 if k in gp else (nEH[k] if k in eh else 2)) for k in keys}
    nB, uB = greedy_exact(ev, tiles, n0, BUDGET, fixed=set(gp) | set(eh))
    variants["B"] = nB
    # C
    n0 = {k: (7 if k in gp else 2) for k in keys}
    nC, uC = greedy_exact(ev, tiles, n0, BUDGET)
    variants["C"] = nC
    fig1 = {k: tiles[k]["epochs"]["fig1"] for k in keys}
    summ = {"fig1": summarize("fig1", fig1, ev, tiles)}
    for v, n in variants.items():
        summ[v] = summarize(v, n, ev, tiles)
    summ["B"]["euclid_hsc_target_uJy"] = target
    print(json.dumps(summ, indent=1))
    # write back into allocation.json
    labels = {
        "A": ("Plan A: DSA-00264 corrected fill", "7 epochs in the Euclid/HSC footprint and in the Galactic plane "
              "and bulge; the remaining pointings go to the wide area where they add the most 5\u03c3 detections, with "
              "at least 2 epochs everywhere. Uses all 64,250 pointings."),
        "B": ("Plan B: uniform Euclid/HSC depth", "As Plan A, but the Euclid/HSC tiles share the same total time so "
              "that every tile there reaches the same final noise."),
        "C": ("Plan C: maximum detections", "At least 2 epochs everywhere and 7 in the Galactic plane and bulge; all "
              "remaining time goes wherever it adds the most 5\u03c3 detections."),
        "fig1": ("Reference plan: depth by declination", "7 epochs in the Euclid/HSC footprint and the Galactic plane "
                 "and bulge; 4, 3 or 2 by declination elsewhere. Uses 63,110 of the 64,250 pointings."),
    }
    for k in keys:
        for v, n in variants.items():
            tiles[k]["epochs"][v] = int(n[k])
        tiles[k]["scheme"] = {v: ev[k]["scheme"][int(tiles[k]["epochs"][v]) - 1] for v in ["fig1"] + list(variants)}
    al["variants"] = {v: {"label": labels[v][0], "description": labels[v][1], "summary": summ[v]} for v in labels}
    al["budget_pointing_epochs"] = BUDGET
    al["default_variant"] = "A"
    json.dump(al, open(os.path.join(DATA_DIR, "allocation.json"), "w"), separators=(",", ":"))
    return al, ev


if __name__ == "__main__":
    main()
