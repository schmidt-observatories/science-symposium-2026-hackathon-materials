"""Build python/dsa_etc/data/ne2025_grid.json: a precomputed NE2025 grid of
Galactic DM_max, extragalactic scattering tau_X, and distance / Galactic-source
scattering time on a log-DM grid, for the exposure-time calculator.

Physics: NE2025 (Ocker & Cordes 2026) via mwprop, unchanged. Each sightline is
integrated once to the model edge with tools/ne2025_fast.py (mwprop's own
density components and line-of-sight arithmetic; see that module's docstring).

Usage (from the package root, conda env with mwprop):
    python tools/build_ne2025_grid.py check      # fast path vs unmodified mwprop, 100 random points
    python tools/build_ne2025_grid.py build      # compute both grids (resumable), write JSON
    python tools/build_ne2025_grid.py reference  # 50 direct-mwprop points + interp_grid -> tests/data
Options: --procs N (default 12), --scratch DIR (checkpoints).
"""

import argparse
import base64
import datetime
import json
import os
import sys
import time

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_JSON = os.path.join(ROOT, "python", "dsa_etc", "data", "ne2025_grid.json")
REF_JSON = os.path.join(ROOT, "tests", "data", "ne2025_reference.json")

DM_GRID = np.geomspace(10, 5000, 16)
TAU_FLOOR_MS = 1e-12
DEC_MIN = -35.0

GRIDS = {
    "inner": dict(l0=0.0, dl=1.0, nl=360, b0=-15.0, db=1.0, nb=31),
    "outer": dict(l0=0.0, dl=5.0, nl=72, b0=-90.0, db=5.0, nb=37),
}


# ---------------------------------------------------------------------------
# Engine-side interpolation (the ETC engine reproduces exactly this)
# ---------------------------------------------------------------------------
def _decode(b64, shape):
    a = np.frombuffer(base64.b64decode(b64), dtype="<i2").astype(np.int64)
    return np.cumsum(a.reshape(shape), axis=-1) / 1000.0     # log10 values


_DECODED = {}


def interp_grid(grid_json, l, b, dm):
    """Interpolate the NE2025 grid at Galactic (l, b) deg and DM (pc cm^-3).

    Returns dict(dist_kpc, tau_1GHz_ms, dm_max, tau_x_1GHz_ms, saturated).
    - grid: "inner" if b lies inside the inner grid's b range, else "outer"
    - x = ((l - l0)/dl) mod nl (wraps), y = (b - b0)/db clamped to [0, nb-1]
    - z = fractional index of log10(dm) in log10(dm_grid), clamped to the ends
    - trilinear interpolation of log10 D and log10 tau
    - DM_max and tau_X from the nearest sightline (floor(x+0.5), floor(y+0.5))
    - saturated = dm > dm_max
    """
    gi = grid_json["grids"]["inner"]
    bmin_i = gi["b0"]
    bmax_i = gi["b0"] + (gi["nb"] - 1) * gi["db"]
    g = gi if bmin_i <= b <= bmax_i else grid_json["grids"]["outer"]
    nl, nb = g["nl"], g["nb"]
    dmg = np.asarray(grid_json["dm_grid"], float)
    ndm = dmg.size

    key = (id(grid_json), id(g))
    if key not in _DECODED:
        _DECODED[key] = dict(
            dmmax=_decode(g["log_dmmax_b64"], (nb, nl)),
            taux=_decode(g["log_taux_b64"], (nb, nl)),
            dist=_decode(g["log_dist_b64"], (nb, nl, ndm)),
            tau=_decode(g["log_tau_b64"], (nb, nl, ndm)),
        )
    A = _DECODED[key]

    x = ((l - g["l0"]) / g["dl"]) % nl
    y = min(max((b - g["b0"]) / g["db"], 0.0), nb - 1.0)
    lg = np.log10(dmg)
    z = float(np.interp(np.log10(dm), lg, np.arange(ndm)))   # clamps at the ends

    x0 = int(np.floor(x)); fx = x - x0; x1 = (x0 + 1) % nl; x0 %= nl
    y0 = int(np.floor(y)); fy = y - y0; y1 = min(y0 + 1, nb - 1)
    z0 = int(np.floor(z)); fz = z - z0; z1 = min(z0 + 1, ndm - 1)

    def tri(V):
        c00 = V[y0, x0, z0] * (1 - fz) + V[y0, x0, z1] * fz
        c01 = V[y0, x1, z0] * (1 - fz) + V[y0, x1, z1] * fz
        c10 = V[y1, x0, z0] * (1 - fz) + V[y1, x0, z1] * fz
        c11 = V[y1, x1, z0] * (1 - fz) + V[y1, x1, z1] * fz
        return ((c00 * (1 - fx) + c01 * fx) * (1 - fy)
                + (c10 * (1 - fx) + c11 * fx) * fy)

    ix = int(np.floor(x + 0.5)) % nl
    iy = int(np.floor(y + 0.5))
    dm_max = 10 ** A["dmmax"][iy, ix]
    return dict(dist_kpc=float(10 ** tri(A["dist"])),
                tau_1GHz_ms=float(10 ** tri(A["tau"])),
                dm_max=float(dm_max),
                tau_x_1GHz_ms=float(10 ** A["taux"][iy, ix]),
                saturated=bool(dm > dm_max))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def gal_to_dec(l, b):
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    c = SkyCoord(l=np.atleast_1d(l) * u.deg, b=np.atleast_1d(b) * u.deg, frame="galactic")
    return c.icrs.dec.deg


def mwprop_direct(args):
    """Unmodified mwprop: ne2025(l, b, dm, 1, dmd_only=False)."""
    l, b, dm = args
    import io, contextlib, warnings
    from mwprop.nemod.NE2025 import ne2025
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Dv = ne2025(l, b, dm, 1, classic=False, dmd_only=False)[1]
    return dict(l=l, b=b, dm=dm, dist=float(Dv["DIST"]), tau=float(Dv["TAU"]),
                limit=Dv["limdist"], dm_mod=float(Dv["DM"]), tau_x=float(Dv["TAU_X"]))


def fast_point(args):
    l, b, dms = args
    sys.path.insert(0, HERE)
    import ne2025_fast as F
    I = F.integrate_sightline(l, b)
    dm_max, d_edge = F.edge(I)
    res = [F.query(I, dm) for dm in dms]
    return dict(l=l, b=b, dm_max=dm_max, d_edge=d_edge, tau_x=F.tau_x(I),
                q=[(d, t, s) for d, t, s in res])


def fast_row(args):
    """One grid sightline -> (dm_max, tau_x, dist[16], tau[16])."""
    l, b = args
    sys.path.insert(0, HERE)
    import ne2025_fast as F
    r = F.sightline_table(l, b, DM_GRID)
    return r["dm_max"], r["tau_x"], r["dist"], r["tau"]


def random_points(n, seed, frac_inner=0.5):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        l = float(rng.uniform(0, 360))
        if rng.uniform() < frac_inner:
            b = float(rng.uniform(-15, 15))
        else:
            b = float(np.rad2deg(np.arcsin(rng.uniform(-1, 1))))
        if gal_to_dec(l, b)[0] < DEC_MIN:
            continue
        out.append((round(l, 3), round(b, 3)))
    return out


def pool(procs):
    import multiprocessing as mp
    # import mwprop in the parent: NE2025.py rewrites params/which_model.inp on
    # import, which must not race between workers
    sys.path.insert(0, HERE)
    import ne2025_fast  # noqa: F401
    from mwprop.nemod.NE2025 import ne2025  # noqa: F401
    return mp.get_context("fork").Pool(procs)


# ---------------------------------------------------------------------------
# check: fast path vs unmodified mwprop at 100 random (l, b, DM)
# ---------------------------------------------------------------------------
def cmd_check(a):
    pts = random_points(100, seed=2025)
    rng = np.random.default_rng(7)
    t0 = time.time()
    with pool(a.procs) as p:
        # choose DMs below each sightline's DM_max for 90 points (10 above, DM >= 2000)
        edges = p.map(fast_point, [(l, b, []) for l, b in pts], chunksize=1)
        dms = []
        for i, e in enumerate(edges):
            if i % 10 == 9:
                dms.append(float(max(2000.0, 1.5 * e["dm_max"])))
            else:
                dms.append(float(10 ** rng.uniform(1, np.log10(min(3000.0, 0.95 * e["dm_max"])))))
        t0 = time.time()
        ref = p.map(mwprop_direct, [(l, b, dm) for (l, b), dm in zip(pts, dms)], chunksize=1)
        t_ref = time.time() - t0
        t1 = time.time()
        fast = p.map(fast_point, [(l, b, [dm]) for (l, b), dm in zip(pts, dms)], chunksize=1)
        t_fast = time.time() - t1
    rows = []
    for r, f in zip(ref, fast):
        d, t, sat = f["q"][0]
        rows.append(dict(l=r["l"], b=r["b"], dm=r["dm"], sat_mwprop=r["limit"] == ">", sat_fast=sat,
                         dm_max_fast=f["dm_max"], dist_ref=r["dist"], dist_fast=d,
                         tau_ref=r["tau"], tau_fast=t,
                         err_dist=d / r["dist"] - 1, err_tau=t / r["tau"] - 1))
    uns = [x for x in rows if not x["sat_mwprop"] and not x["sat_fast"]]
    summ = dict(n=len(rows), n_unsaturated=len(uns),
                max_abs_err_dist_pct=100 * max(abs(x["err_dist"]) for x in uns),
                max_abs_err_tau_pct=100 * max(abs(x["err_tau"]) for x in uns),
                median_abs_err_tau_pct=100 * float(np.median([abs(x["err_tau"]) for x in uns])),
                wall_mwprop_s=t_ref, wall_fast_s=t_fast, procs=a.procs)
    os.makedirs(a.scratch, exist_ok=True)
    with open(os.path.join(a.scratch, "check_100.json"), "w") as fh:
        json.dump(dict(summary=summ, rows=rows), fh, indent=1)
    print(json.dumps(summ, indent=1))
    for x in rows:
        if x["sat_mwprop"] or x["sat_fast"] or abs(x["err_tau"]) > 0.01 or abs(x["err_dist"]) > 0.01:
            print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in x.items()})


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def compute_grid(name, g, a):
    path = os.path.join(a.scratch, f"grid_{name}.npz")
    if os.path.exists(path):
        print(f"[{name}] using checkpoint {path}")
        return dict(np.load(path))
    ls = g["l0"] + g["dl"] * np.arange(g["nl"])
    bs = g["b0"] + g["db"] * np.arange(g["nb"])
    jobs = [(float(l), float(b)) for b in bs for l in ls]
    t0 = time.time()
    res = [None] * len(jobs)
    with pool(a.procs) as p:
        for k, r in enumerate(p.imap(fast_row, jobs, chunksize=4)):
            res[k] = r
            if (k + 1) % 500 == 0:
                el = time.time() - t0
                print(f"[{name}] {k+1}/{len(jobs)}  {el:.0f}s  eta {el/(k+1)*(len(jobs)-k-1):.0f}s", flush=True)
    nb, nl, nd = g["nb"], g["nl"], DM_GRID.size
    out = dict(dm_max=np.array([r[0] for r in res]).reshape(nb, nl),
               tau_x=np.array([r[1] for r in res]).reshape(nb, nl),
               dist=np.array([r[2] for r in res]).reshape(nb, nl, nd),
               tau=np.array([r[3] for r in res]).reshape(nb, nl, nd),
               wall_s=np.array(time.time() - t0))
    np.savez(path, **out)
    print(f"[{name}] done in {time.time()-t0:.0f}s", flush=True)
    return out


def encode(x, floor):
    L = np.round(1000 * np.log10(np.maximum(x, floor))).astype(np.int64)
    D = np.concatenate([L[..., :1], np.diff(L, axis=-1)], axis=-1)
    if np.abs(D).max() > 32767:
        raise ValueError(f"delta overflow: max |delta| {np.abs(D).max()}")
    return base64.b64encode(np.ascontiguousarray(D.astype("<i2")).tobytes()).decode("ascii"), int(np.abs(D).max())


def cmd_build(a):
    import importlib.metadata as md
    os.makedirs(a.scratch, exist_ok=True)
    data = {n: compute_grid(n, g, a) for n, g in GRIDS.items()}
    grids = {}
    maxdelta = {}
    for n, g in GRIDS.items():
        d = data[n]
        e = dict(g)
        for k in ("l0", "dl", "b0", "db"):
            e[k] = float(e[k]) if e[k] != int(e[k]) else int(e[k])
        e["log_dmmax_b64"], m1 = encode(d["dm_max"], 1e-3)
        e["log_taux_b64"], m2 = encode(d["tau_x"], TAU_FLOOR_MS)
        e["log_dist_b64"], m3 = encode(d["dist"], 1e-3)
        e["log_tau_b64"], m4 = encode(d["tau"], TAU_FLOOR_MS)
        maxdelta[n] = dict(dmmax=m1, taux=m2, dist=m3, tau=m4)
        grids[n] = e
    notes = (
        "NE2025 (Ocker & Cordes 2026) via mwprop %s, physics unchanged. Each sightline integrated once "
        "to mwprop's 50 kpc limit on mwprop's own grids (0.1 kpc smooth / 0.0025 kpc small-scale), "
        "tools/ne2025_fast.py; agrees with direct ne2025() calls to <%s. dm_max = DM to the model edge; "
        "tau_x = mwprop TAU_X (extragalactic plane-wave broadening of the full column). dist/tau = DM->D "
        "distance and Galactic-source pulse broadening (mwprop TAU) at each dm_grid value; for DM > dm_max "
        "they are clamped to the model-edge values (mwprop's lower-limit distance). tau at 1 GHz in ms, "
        "floored at 1e-12 ms; scale as nu^-4.4. All sightlines computed (no declination skip). "
        "Interpolate with tools/build_ne2025_grid.py:interp_grid." % (md.version("mwprop"), a.agree))
    out = {
        "model": "NE2025", "mwprop_version": md.version("mwprop"),
        "built": datetime.date.today().isoformat(), "build_notes": notes,
        "freq_GHz": 1.0, "tau_index": -4.4, "tau_unit": "ms", "dist_unit": "kpc",
        "dm_unit": "pc cm^-3",
        "dm_grid": [float(x) for x in DM_GRID],
        "encoding": "base64 little-endian int16 of round(1000*log10(x)), delta-encoded along the last "
                    "axis (cumsum along last axis to decode), C order",
        "shapes": {"log_dmmax_b64": "(nb, nl)", "log_taux_b64": "(nb, nl)",
                   "log_dist_b64": "(nb, nl, ndm)", "log_tau_b64": "(nb, nl, ndm)"},
        "grids": grids,
    }
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    # round-trip check
    for n, g in GRIDS.items():
        e = grids[n]
        for key, arr, fl in (("log_dmmax_b64", data[n]["dm_max"], 1e-3), ("log_taux_b64", data[n]["tau_x"], TAU_FLOOR_MS),
                             ("log_dist_b64", data[n]["dist"], 1e-3), ("log_tau_b64", data[n]["tau"], TAU_FLOOR_MS)):
            dec = 10 ** _decode(e[key], arr.shape)
            err = np.max(np.abs(np.log10(dec) - np.log10(np.maximum(arr, fl))))
            assert err <= 0.0005 + 1e-9, (n, key, err)
    print("wrote", OUT_JSON, os.path.getsize(OUT_JSON), "bytes; max |delta|:", maxdelta)
    print("wall:", {n: float(data[n]["wall_s"]) for n in data})


# ---------------------------------------------------------------------------
# reference: 50 direct-mwprop points + interp_grid
# ---------------------------------------------------------------------------
def cmd_reference(a):
    with open(OUT_JSON) as fh:
        G = json.load(fh)
    pts = random_points(50, seed=4242, frac_inner=0.6)
    rng = np.random.default_rng(11)
    # DM_max per point (direct mwprop saturating call) so DMs can be chosen below it
    with pool(a.procs) as p:
        sat = p.map(mwprop_direct, [(l, b, 1e5) for l, b in pts], chunksize=1)
        jobs = []
        for i, ((l, b), s) in enumerate(zip(pts, sat)):
            dmmax = s["dm_mod"]
            if i % 12 == 5:          # >= 4 points above DM_max (DM >= 2000 -> mwprop integrates to 50 kpc)
                dm = float(min(3000.0, max(2000.0, 1.5 * dmmax)))
                if dm <= dmmax:
                    dm = float(rng.uniform(20, min(3000.0, 0.9 * dmmax)))
            else:
                dm = float(10 ** rng.uniform(np.log10(20), np.log10(min(3000.0, 0.9 * dmmax))))
            jobs.append((l, b, round(dm, 3)))
        ref = p.map(mwprop_direct, jobs, chunksize=1)
    rows = []
    for r, s in zip(ref, sat):
        it = interp_grid(G, r["l"], r["b"], r["dm"])
        rows.append(dict(l=r["l"], b=r["b"], dm=r["dm"],
                         dist_kpc=r["dist"], tau_1GHz_ms=r["tau"],
                         dm_max=s["dm_mod"], tau_x_1GHz_ms=s["tau_x"],
                         saturated=bool(r["dm"] > s["dm_mod"]),
                         interp=dict(dist_kpc=it["dist_kpc"], tau_1GHz_ms=it["tau_1GHz_ms"],
                                     dm_max=it["dm_max"], tau_x_1GHz_ms=it["tau_x_1GHz_ms"],
                                     saturated=it["saturated"]),
                         ratio=dict(dist=it["dist_kpc"] / r["dist"], tau=it["tau_1GHz_ms"] / r["tau"],
                                    dm_max=it["dm_max"] / s["dm_mod"], tau_x=it["tau_x_1GHz_ms"] / s["tau_x"])))
    os.makedirs(os.path.dirname(REF_JSON), exist_ok=True)
    doc = {"description": "50 random off-grid sightlines (Dec > -35 deg), direct unmodified mwprop NE2025 "
                          "(ne2025(l,b,dm,1,dmd_only=False); dm_max and tau_x from a DM=1e5 call), "
                          "plus interp_grid() on ne2025_grid.json and interp/direct ratios. tau at 1 GHz in ms, "
                          "distances in kpc.",
           "mwprop_version": G["mwprop_version"], "built": G["built"], "points": rows}
    with open(REF_JSON, "w") as fh:
        json.dump(doc, fh, indent=1)
    def stats(key):
        e = np.array([abs(x["ratio"][key] - 1) for x in rows]) * 100
        return dict(median_pct=round(float(np.median(e)), 2), max_pct=round(float(e.max()), 1),
                    n_gt20=int((e > 20).sum()))
    summ = {k: stats(k) for k in ("dist", "tau", "dm_max", "tau_x")}
    summ["n_saturated"] = sum(x["saturated"] for x in rows)
    summ["n_inner"] = sum(abs(x["b"]) <= 15 for x in rows)
    print(json.dumps(summ, indent=1))
    for x in rows:
        if abs(x["ratio"]["tau"] - 1) > 0.2 or abs(x["ratio"]["dist"] - 1) > 0.2:
            print(round(x["l"], 2), round(x["b"], 2), round(x["dm"], 1), "dm_max", round(x["dm_max"], 1),
                  {k: round(v, 3) for k, v in x["ratio"].items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "build", "reference"])
    ap.add_argument("--procs", type=int, default=12)
    ap.add_argument("--scratch", default="/home/ubuntu/.claude-vikram/jobs/7a69462d/tmp/ne2025")
    ap.add_argument("--agree", default="0.1%", help="validated agreement quoted in build_notes")
    a = ap.parse_args()
    {"check": cmd_check, "build": cmd_build, "reference": cmd_reference}[a.cmd](a)


if __name__ == "__main__":
    main()
