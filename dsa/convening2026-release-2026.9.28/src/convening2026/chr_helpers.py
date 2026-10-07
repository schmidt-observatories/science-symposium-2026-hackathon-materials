"""Small helpers for the CHR data-preview notebooks.

Everything here uses only PSRCHIVE's Python interface, PINT, numpy, pandas and
matplotlib (the Hub environment); nothing needs the generation code.
"""
from __future__ import annotations

import copy
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

NU_REF = 953.35          # MHz, band centre and dedispersion reference
K_DM = 4.148808e-3       # s: dispersion delay = K_DM * DM * nu_GHz^-2


def _quiet_pint() -> None:
    """Reduce PINT's default DEBUG/INFO noise (imported lazily)."""
    import pint.logging

    pint.logging.setup(level="WARNING")


# --------------------------------------------------------------------------- dataset
def inventory(dataset=None) -> pd.DataFrame:
    """Load ``MANIFEST.csv`` under the sample ``data/`` tree (absolute archive paths).

    ``dataset`` defaults to :func:`convening2026.paths.data_dir`. If ``MANIFEST.csv``
    is not at the root of that directory, a single nested copy under it is used.

    Paths in the manifest are resolved relative to the dataset root. If a listed
    file is missing at that relative path, a same-basename match anywhere under
    the dataset is used when unique.
    """
    from convening2026.paths import require_data_dir

    ds = Path(dataset).expanduser() if dataset is not None else require_data_dir()
    if not ds.is_dir():
        raise FileNotFoundError(
            f"Sample data directory not found: {ds}\n"
            "Download the convening sample into data/ (see data/README.md)."
        )

    man = ds / "MANIFEST.csv"
    if not man.exists():
        nested = sorted(ds.glob("**/MANIFEST.csv"))
        if len(nested) == 1:
            man = nested[0]
            ds = man.parent
        elif len(nested) > 1:
            raise FileNotFoundError(
                f"Multiple MANIFEST.csv files under {ds}; put one at data/MANIFEST.csv "
                f"or pass an explicit dataset folder. Found: {[str(p) for p in nested]}"
            )
        else:
            raise FileNotFoundError(
                f"No MANIFEST.csv under {ds}\n"
                "Download the CHR (DPR-DSA-13) sample into data/ (see data/README.md)."
            )

    m = pd.read_csv(man)
    by_base: dict[str, list[Path]] = {}
    for p in ds.rglob("*"):
        if p.is_file() or p.is_symlink():
            by_base.setdefault(p.name, []).append(p)

    paths: list[str] = []
    missing: list[str] = []
    for rel in m["file"]:
        candidate = ds / rel
        if candidate.exists():
            paths.append(str(candidate))
            continue
        matches = by_base.get(Path(rel).name, [])
        if len(matches) == 1:
            paths.append(str(matches[0]))
        else:
            paths.append(str(candidate))
            missing.append(str(candidate))

    m = m.copy()
    m["path"] = paths
    if missing:
        if len(missing) == len(m):
            raise FileNotFoundError(
                f"All {len(missing)} archives listed in MANIFEST.csv are missing under {ds}, "
                f"e.g. {missing[0]}"
            )
        print(
            f"Warning: {len(missing)}/{len(m)} archives from MANIFEST.csv are missing "
            f"(e.g. {missing[0]}); continuing with {len(m) - len(missing)} present file(s)."
        )
        m = m[[Path(p).exists() for p in m["path"]]].reset_index(drop=True)
    return m


def fold_ephemeris(dataset=None, pulsar: str = "P3") -> Path:
    """Locate the folding ephemeris ``fold.par`` under ``data/``.

    Accepts ``ephemerides/{pulsar}/fold.par`` or a top-level ``fold.par``.
    """
    from convening2026.paths import require_data_dir

    ds = Path(dataset).expanduser() if dataset is not None else require_data_dir()
    candidates = [
        ds / "ephemerides" / pulsar / "fold.par",
        ds / "fold.par",
        *sorted(ds.glob(f"**/ephemerides/{pulsar}/fold.par")),
        *sorted(ds.glob("**/fold.par")),
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"No fold.par for {pulsar} under {ds}\n"
        "Expected data/fold.par or data/ephemerides/{pulsar}/fold.par."
    )


def answer_key_dir(dataset=None, pulsar: str = "P3") -> Path | None:
    """Return ``answer_key/{pulsar}/`` if present; else ``None`` (optional self-check)."""
    from convening2026.paths import require_data_dir

    ds = Path(dataset).expanduser() if dataset is not None else require_data_dir()
    for path in (
        ds / "answer_key" / pulsar,
        *sorted(ds.glob(f"**/answer_key/{pulsar}")),
    ):
        if path.is_dir():
            return path
    return None


# PSRCHIVE >= 2026-09 re-reads files that PSRCHIVE itself wrote (pam/psradd output) and reports
# "FITSArchive::load_Pointing correcting RA_SUB/DEC_SUB ..." on stderr: its writer stores RA_SUB
# wrapped to (-180, 180] deg while its reader expects [0, 360). Harmless; filtered from the display.
_HARMLESS_STDERR = ("FITSArchive::load_Pointing correcting",)


def sh(cmd: str) -> str:
    """Run a shell command and return its standard output; fail loudly on error.

    Only stdout is returned (so e.g. pat's ToAs can be written straight to a .tim file).
    Anything on stderr is printed, except known-harmless PSRCHIVE notices."""
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {cmd}\n{p.stdout}\n{p.stderr}")
    err = [ln for ln in p.stderr.splitlines() if ln.strip() and not ln.startswith(_HARMLESS_STDERR)]
    if err:
        print("\n".join(err))
    return p.stdout.strip()


# --------------------------------------------------------------------------- archives
class _FilteredStderr:
    """Capture C-level stderr (file descriptor 2) and re-print it without the known-harmless
    PSRCHIVE notices (see _HARMLESS_STDERR); used around psrchive calls from Python."""

    def __enter__(self):
        import os
        import sys
        import tempfile

        sys.stderr.flush()
        self._tmp = tempfile.TemporaryFile(mode="w+b")
        self._saved = os.dup(2)
        os.dup2(self._tmp.fileno(), 2)
        return self

    def __exit__(self, *exc):
        import os
        import sys

        sys.stderr.flush()
        os.dup2(self._saved, 2)
        os.close(self._saved)
        self._tmp.seek(0)
        text = self._tmp.read().decode(errors="replace")
        self._tmp.close()
        keep = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith(_HARMLESS_STDERR)]
        if keep:
            print("\n".join(keep), file=sys.stderr)
        return False


def load(path, fscrunch=False, tscrunch=False, dedisperse_dm=None):
    """Load an archive with PSRCHIVE; optionally scrunch; baseline removed."""
    import psrchive

    # integrations (and hence the pointing check) load lazily, so filter the whole sequence
    with _FilteredStderr():
        ar = psrchive.Archive_load(str(path))
        if dedisperse_dm is not None:
            ar.set_dispersion_measure(float(dedisperse_dm))
            ar.dedisperse()
        if tscrunch:
            ar.tscrunch()
        if fscrunch:
            ar.fscrunch()
        ar.remove_baseline()
    return ar


def data(ar) -> np.ndarray:
    """(nsub, nchan, nbin) Stokes I."""
    return ar.get_data()[:, 0]


def freqs(ar) -> np.ndarray:
    return np.array([ar.get_Profile(0, 0, c).get_centre_frequency() for c in range(ar.get_nchan())])


def on_window(profile: np.ndarray, max_frac: float = 0.25) -> tuple[int, int]:
    """Boxcar search: (start bin, width) of the circular window maximising
    sum(window) / sqrt(width) -- the standard way to find the on-pulse region."""
    p = np.asarray(profile, dtype=float) - np.median(profile)
    n = p.size
    best, arg = -np.inf, (0, 1)
    pp = np.r_[p, p]
    c = np.r_[0.0, np.cumsum(pp)]
    for w in range(1, int(n * max_frac) + 1):
        s = (c[w:w + n] - c[:n]) / np.sqrt(w)
        i = int(np.argmax(s))
        if s[i] > best:
            best, arg = s[i], (i, w)
    return arg


def snr(profile: np.ndarray, window: tuple[int, int] | None = None) -> float:
    """Boxcar S/N: on-pulse sum over the off-pulse rms x sqrt(width). With `window`
    = (start, width) from on_window() of a brighter profile, the same on-pulse region
    is used (no search, so no upward bias for faint sub-profiles)."""
    p = np.asarray(profile, dtype=float)
    n = p.size
    i0, w = window or on_window(p)
    idx = (i0 + np.arange(w)) % n
    off = np.delete(p, idx)
    return float((p[idx] - off.mean()).sum() / (off.std(ddof=1) * np.sqrt(w)))


def dm_scan(path, half_width=None, n=81):
    """S/N proxy vs trial DM for a tscrunched archive: channels are shifted relative to
    953.35 MHz by the extra dispersion delay and summed; the proxy is the power in the
    non-zero harmonics of the summed profile (maximal when channels are aligned)."""
    ar = load(path, tscrunch=True)
    d = data(ar)[0]
    f = freqs(ar)
    F = 1.0 / ar.get_Integration(0).get_folding_period()
    hdr = ar.get_dispersion_measure()
    nbin = d.shape[1]
    D = np.fft.rfft(d, axis=1)
    k = np.arange(D.shape[1])
    band = K_DM * ((f.min() / 1e3) ** -2 - (f.max() / 1e3) ** -2)
    res = 1.0 / F / nbin / band
    hw = half_width or 4 * res
    trials = hdr + np.linspace(-hw, hw, n)
    power = []
    for dm in trials:
        dt = K_DM * (dm - hdr) * ((f / 1e3) ** -2 - (NU_REF / 1e3) ** -2)
        S = (D * np.exp(2j * np.pi * k[None, :] * F * dt[:, None])).sum(axis=0)
        power.append(np.sum(np.abs(S[1:]) ** 2))
    power = np.array(power)
    i = int(np.argmax(power))
    j = slice(max(i - 3, 0), min(i + 4, n))
    c = np.polyfit(trials[j] - trials[i], power[j], 2)
    best = trials[i] - c[1] / (2 * c[0]) if c[0] < 0 else trials[i]
    return dict(trials=trials, power=power / power.max(), best=float(best), header=float(hdr),
                resolution=float(res))


def read_par(path) -> dict:
    """Minimal par reader: {KEY: value string}."""
    out = {}
    for ln in Path(path).read_text().splitlines():
        w = ln.split()
        if len(w) >= 2 and not ln.startswith("#"):
            out[w[0]] = w[1]
    return out


# --------------------------------------------------------------------------- timing
def visit_ptg(name: str) -> tuple[int, int]:
    """(visit, pointing) from a DPR-DSA-13 file name, whose observationID field is
    chrsim-v{visit}-p{pointing}-{MJD}: dsa13_chrsim-v03-p12-62608.5348_P3_v1.psrfits -> (3, 12).
    Works for derived files too (.FT, .tF). (-1, -1) if the name does not match."""
    m = re.search(r"chrsim-v(\d\d)-p(\d\d)-", name)
    return (int(m.group(1)), int(m.group(2))) if m else (-1, -1)


def visit_of(name: str) -> int:
    return visit_ptg(name)[0]


def load_toas(tim, planets=True):
    """PINT TOAs from a pat (tempo2-format) .tim file, with a 'visit' flag taken from the
    archive file name (dsa13_chrsim-v03-... -> visit 3)."""
    import pint.toa

    _quiet_pint()
    ts = pint.toa.get_TOAs(str(tim), ephem="DE440", planets=planets, include_bipm=True,
                           bipm_version="BIPM2019")
    for fl in ts.table["flags"]:
        fl["visit"] = str(visit_of(fl.get("name", "")))
    return ts


def visits(ts) -> np.ndarray:
    return np.array([int(f["visit"]) for f in ts.table["flags"]])


class TimingSession:
    """Incremental phase-connection helper around PINT.

    fit(visits, free, jumps) fits the selected visits with the chosen free parameters.
    Pulse numbers: a ToA gets its pulse number the first time it enters a fit, from the
    current best model (nearest pulse); after that it keeps it. This is how a coherent
    solution is extended to new data -- an already-connected ToA must not be renumbered
    just because an intermediate model (e.g. one still missing the position) is poor.
    undo() returns to the previous model and pulse numbers. Every fit is kept in `history`.
    """

    def __init__(self, toas, model):
        self.toas_all = copy.deepcopy(toas)
        self.model = copy.deepcopy(model)
        for p in self.model.free_params:
            getattr(self.model, p).frozen = True
        self.pn = np.full(len(toas), np.nan)          # assigned pulse numbers (NaN = not yet)
        self.history = []
        self.last = None

    def _mask(self, vis):
        return np.isin(visits(self.toas_all), list(vis))

    def _set_jumps(self, model, jumps):
        from pint.models.jump import PhaseJump
        from pint.models.parameter import maskParameter

        if "PhaseJump" in model.components:
            model.remove_component("PhaseJump")
        if not jumps:
            return model
        model.add_component(PhaseJump(), validate=False)
        pj = model.components["PhaseJump"]
        for i, v in enumerate(sorted(jumps), start=1):
            pj.add_param(maskParameter(name="JUMP", index=i, key="-visit", key_value=[str(v)],
                                       value=0.0, units="second", frozen=False))
        model.setup()
        return model

    def residuals(self, vis=None, model=None):
        import pint.residuals

        _quiet_pint()
        ts = self.toas_all if vis is None else self.toas_all[self._mask(vis)]
        return pint.residuals.Residuals(ts, model or self.model, track_mode="nearest")

    def fit(self, vis, free, jumps=()):
        import pint.fitter

        _quiet_pint()
        sel = self._mask(vis)
        new = sel & np.isnan(self.pn)
        pn = self.pn.copy()
        if new.any():
            tmp = copy.deepcopy(self.toas_all)
            tmp.compute_pulse_numbers(self.model)
            pn[new] = np.asarray(tmp.table["pulse_number"], dtype=float)[new]
        ts = copy.deepcopy(self.toas_all)
        ts.table["pulse_number"] = pn
        ts = ts[sel]
        m = self._set_jumps(copy.deepcopy(self.model), [j for j in jumps if j in vis])
        for p in m.free_params:
            getattr(m, p).frozen = True
        for p in list(free) + [q for q in m.params if q.startswith("JUMP")]:
            getattr(m, p).frozen = False
        f = pint.fitter.WLSFitter(ts, m, track_mode="use_pulse_numbers")
        f.fit_toas(maxiter=10)
        self.history.append((copy.deepcopy(self.model), self.pn.copy()))
        self.model, self.pn = f.model, pn
        self.last = dict(visits=list(vis), free=list(free), jumps=list(jumps), ntoa=int(sel.sum()),
                         n_new=int(new.sum()), chi2=float(f.resids.chi2), dof=int(f.resids.dof),
                         chi2r=float(f.resids.chi2_reduced), fitter=f)
        return self.last

    def undo(self):
        if self.history:
            self.model, self.pn = self.history.pop()
        return self.model

    def table(self, params=None):
        params = params or [p for p in ("F0", "F1", "RAJ", "DECJ", "PB", "A1", "TASC", "T0", "EPS1", "EPS2")
                            if hasattr(self.model, p) and getattr(self.model, p).value is not None]
        rows = []
        for p in params:
            q = getattr(self.model, p)
            rows.append(dict(parameter=p, value=q.str_quantity(q.quantity) if hasattr(q, "str_quantity")
                             else str(q.value), uncertainty=q.uncertainty_value, fitted=not q.frozen))
        return pd.DataFrame(rows)


def plot_residuals(ax, res, title="", unit="us"):
    """Residuals vs MJD, one colour per visit."""
    import matplotlib.pyplot as plt

    ts = res.toas
    v = visits(ts)
    t = ts.get_mjds().value
    r = res.time_resids.to_value(unit)
    e = ts.get_errors().to_value(unit)
    cm = plt.get_cmap("viridis")
    for i, vv in enumerate(sorted(set(v))):
        s = v == vv
        ax.errorbar(t[s], r[s], e[s], fmt="o", ms=4, color=cm(vv / 6.0), label=f"visit {vv}")
    ax.axhline(0, color="0.5", lw=0.8)
    ax.set_xlabel("MJD (topocentric UTC)")
    ax.set_ylabel(f"residual ({'μs' if unit == 'us' else unit})")
    ax.set_title(title)
    ax.legend(fontsize=8, ncol=2)


def pulls(model, truth_par) -> pd.DataFrame:
    """(fit - truth) / sigma for the fitted parameters, with the truth moved to the fit's
    PEPOCH and, for binaries, TASC/T0 moved by an integer number of orbits."""
    import pint.models

    _quiet_pint()
    tr = pint.models.get_model(str(truth_par))
    tr.change_pepoch(model.PEPOCH.value)
    rows = []
    for p in model.free_params + [q for q in ("F0", "F1", "RAJ", "DECJ", "PB", "A1", "TASC", "T0")
                                  if hasattr(model, q) and not getattr(model, q).frozen]:
        if any(r["parameter"] == p for r in rows) or not hasattr(tr, p) or p.startswith("JUMP"):
            continue
        q, t = getattr(model, p), getattr(tr, p)
        if q.uncertainty_value in (None, 0):
            continue
        fv, tv = float(q.value), float(t.value)
        if p in ("TASC", "T0"):
            pb = float(tr.PB.value)
            tv = tv + np.round((fv - tv) / pb) * pb
        if p in ("RAJ", "DECJ"):
            fv, tv = float(q.quantity.deg), float(t.quantity.deg)
            unc = q.uncertainty.to_value("deg")
            if p == "RAJ":
                unc = unc * 15.0 if q.uncertainty.unit.to_string() in ("hourangle",) else unc
        else:
            unc = float(q.uncertainty_value)
        rows.append(dict(parameter=p, fit=fv, truth=tv, sigma=unc, pull=(fv - tv) / unc))
    return pd.DataFrame(rows)
