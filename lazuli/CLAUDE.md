# Lazuli WCC tutorial — development guide

## Package

`wcc_etc` is installed at:
`/srv/conda/envs/notebook/lib/python3.13/site-packages/wcc_etc/`

Standard imports used across all notebooks:
```python
import wcc_etc
from wcc_etc import Simulation, ImageSimulator, get_scene
wcc_etc.set_wcc_style()
```

## `get_scene` API

```python
get_scene(
    name,               # spectrum key — see table below
    mag,                # AB mag to normalise to (None for emission lines)
    bandpass,           # e.g. "sdss_r", "sdss_g", "johnson_v"
    magsys,             # "abmag" or "vegamag"
    host=None,          # spectrum key for host galaxy (same keys as name)
    host_prop=None,     # dict — see host_prop keys below
    background=None,    # "zodi" for zodiacal sky background
    **spectrum_kwargs,  # SED-specific — see table below
)
```

### `name` / spectrum keys and their required kwargs

| key | extra required kwargs | notes |
|---|---|---|
| `"G5V"` (or any Pickles type) | — | ~80 Pickles types: O5V … M2I |
| `"blackbody"` | `teff=<K>` | `synphot.BlackBodyNorm1D` |
| `"flat"` | — | flat in F_nu (AB-flat); `flat_unit="flam"` for flat in F_lambda |
| `"powerlaw"` | `alpha=<float>` | F_lambda ~ (lam/5500 Å)^alpha; optional `lambda_ref=` |
| `"emission"` | `lines=[{"wave":Å,"flux":erg/s/cm²,"fwhm":Å},…]` | `mag` must be `None` |
| `"file"` | `source_file="<path>"` | 2-col text (wave Å, F_lambda); optional `wave_unit=`, `flux_unit=`, `names=True` |

Galaxy templates from the Brown+ library (e.g. `"ngc_4486_spec"`) also work as `name`.

### `host_prop` keys

```python
host_prop = {
    "mag":      16.0,        # host total magnitude
    "profile":  "sersic",    # only "sersic" supported
    "r_eff":    0.5,         # half-light radius, arcsec
    "n":        4,           # Sersic index (4 = de Vaucouleurs, 1 = exponential disk)
    "dx":       0.0,         # transient offset from host centre, arcsec
    "bandpass": "sdss_r",
    "magsys":   "abmag",
}
```

## `Simulation` API

```python
sim = Simulation.from_sensorfilter("zwo:r", scene)

# Update any scene parameter with double-underscore nesting:
sim.update(host__dx=0.5)         # move host centre
sim.update(host__n=1)            # change Sersic index
sim.update(host__mag=18.0)
sim.update(source__mag=22.0)

# Compute SNR:
result = sim.get_image_snr(
    t,            # total integration seconds
    n_reads=2,    # split into n frames of t/n each
    mags=mags,    # array of source mags to sweep (optional)
    warn=False,
)
# result keys: "snr", "signal_e", "noise_e", "saturated"

# Peak pixel check (saturation):
sim.get_peak_pixel(t, units="e-")
```

## Bundled SED data files

```python
import os, wcc_etc
data_dir = os.path.join(os.path.dirname(wcc_etc.__file__), "data", "astrophysics")

hsiao07  = os.path.join(data_dir, "hsiao07.dat")   # SN Ia Hsiao+2007, phase 0d (B-max), 2-col Å/F_lambda
```

Use with: `get_scene("file", mag=21, bandpass="sdss_r", magsys="abmag", source_file=hsiao07, ...)`

## Notebook conventions (kernel state after running all cells)

Variables available in later cells once the tutorial notebook has been executed top-to-bottom:

| name | defined in | value |
|---|---|---|
| `sim` | cell 5 | `Simulation` for the n=4 host scene; `host__dx` mutated by later cells |
| `blank` | cell 9 | `Simulation` with no host, for blank-sky reference |
| `mags` | cell 9 | `np.arange(19, 27.5, 0.5)` — source magnitude sweep array |
| `t` | cell 9 | `EXPOSURE` (default 300 s) |
| `READS` | cell 5 | `(1, 2, 3, 5, 10, 30)` — read-split candidates |
| `choose_reads(sim, t, mags=, **kw)` | cell 5 | returns `(n_reads, result_dict)`; picks smallest split with no saturation |
| `snr_crossing(mags, snr, target=5)` | cell 9 | interpolates 5σ depth from a monotone SNR curve |
| `depth` | cell 9 | dict of 5σ depths for n=4 curves |

`sim` is stateful — its `host__dx` and other params are whatever the last `sim.update()` call set.
Restore with `sim.update(host__dx=0.0)` before reusing for the nuclear case.

## Gallery structure

```
lazuli/
  wcc/tutorial/   # Wide-field Context Camera ETC notebooks
  esc/            # ExtraSolar Coronagraph notebooks
  ifs/            # Integral Field Spectrograph notebooks
```

Relevant prior art in other notebooks:
- `wcc/tutorial/07_ism_halpha_emission_line.ipynb` — emission line SED
- `esc/08_fast_transient_depth.ipynb` — kilonova as flat SED, blackbody caveat
- `esc/09_tde_in_galaxy_nuclei.ipynb` — `get_scene("blackbody", teff=30000, ...)` live example
