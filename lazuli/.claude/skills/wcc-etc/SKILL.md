---
name: wcc-etc
description: Quick reference for the wcc_etc exposure time calculator API used in Lazuli WCC/ESC/IFS notebooks. Load this before writing any code that calls get_scene, Simulation, or ImageSimulator, or when asked about SED options, host galaxy parameters, sensor/filter names, or bundled data files.
---

# wcc_etc API reference

## Core imports

```python
import wcc_etc
from wcc_etc import Simulation, ImageSimulator, get_scene
wcc_etc.set_wcc_style()   # plot styling; call once per notebook
```

Package location: `/srv/conda/envs/notebook/lib/python3.13/site-packages/wcc_etc/`

---

## `get_scene` — build a scene (source + optional host + background)

```python
scene = get_scene(
    name,               # spectrum key (see table)
    mag,                # float or None — AB mag for normalisation
    bandpass="sdss_r",  # passband for mag normalisation
    magsys="abmag",     # "abmag" or "vegamag"
    host=None,          # spectrum key for host; same options as name
    host_prop=None,     # dict — host Sersic profile (see below)
    background=None,    # "zodi" for zodiacal sky
    **spectrum_kwargs,  # SED-specific kwargs (teff, alpha, source_file, lines…)
)
```

### Spectrum name keys

| `name` | required extra kwargs | description |
|---|---|---|
| `"G5V"` (any Pickles type) | — | Pickles library; ~80 types O5V–M2I |
| `"blackbody"` | `teff=<K>` | Planck blackbody |
| `"flat"` | — | flat F_nu (AB-flat); `flat_unit="flam"` for flat F_lambda |
| `"powerlaw"` | `alpha=<float>` | F_λ ∝ (λ/5500 Å)^α; optional `lambda_ref=` |
| `"emission"` | `lines=[{"wave":Å,"flux":erg/s/cm²,"fwhm":Å},…]` | `mag` **must** be `None` |
| `"file"` | `source_file="<abs-path>"` | 2-col text (Å, F_lambda); also `wave_unit=`, `flux_unit=`, `names=True` |

Galaxy templates: pass any Brown+ library basename, e.g. `"ngc_4486_spec"`.

### `host_prop` dict keys

```python
host_prop = {
    "mag":      16.0,      # total host magnitude
    "profile":  "sersic",
    "r_eff":    0.5,       # half-light radius, arcsec
    "n":        4,         # Sersic index (4 = elliptical, 1 = disk)
    "dx":       0.0,       # transient–nucleus separation, arcsec
    "bandpass": "sdss_r",
    "magsys":   "abmag",
}
```

---

## Bundled data files

```python
import os, wcc_etc
_d = os.path.join(os.path.dirname(wcc_etc.__file__), "data", "astrophysics")
HSIAO07 = os.path.join(_d, "hsiao07.dat")   # SN Ia Hsiao+2007, phase 0 d (B-max)
```

Load: `get_scene("file", source_file=HSIAO07, mag=21, bandpass="sdss_r", magsys="abmag", ...)`

---

## `Simulation` API

```python
sim = Simulation.from_sensorfilter("zwo:r", scene)  # sensor:filter string

# Mutate scene parameters in place (double-underscore for nested):
sim.update(host__dx=0.5)      # transient offset from nucleus, arcsec
sim.update(host__n=1)         # Sersic index
sim.update(host__mag=18.0)
sim.update(source__mag=22.0)

# SNR calculation:
result = sim.get_image_snr(
    t,              # total seconds
    n_reads=2,      # split into n frames of t/n s each
    mags=mags,      # optional array — sweep source magnitude
    warn=False,
)
# result: dict with "snr", "signal_e", "noise_e", "saturated" (scalar or arrays)

# Saturation check:
sim.get_peak_pixel(t, units="e-")   # peak pixel electrons in a single t-second frame
```

Sensor:filter options include `"zwo:r"`, `"zwo:g"`, `"zwo:i"`, `"zwo:z"`.

---

## Notebook helper idioms

These helpers are defined in the standard tutorial notebooks and are available in the kernel once cells are run:

```python
READS = (1, 2, 3, 5, 10, 30)   # read-split candidates

def choose_reads(sim, t, reads=READS, **kw):
    """Smallest n_reads with no saturated pixel; returns (n, result_dict)."""
    for n in reads:
        r = sim.get_image_snr(t, n_reads=n, warn=False, **kw)
        if not np.any(r["saturated"]):
            return n, r
    return None, r

def snr_crossing(mags, snr, target=5):
    """Interpolated magnitude where SNR crosses target (5σ depth). Returns NaN if not bracketed."""
    ...
```

Difference-image SNR (template subtraction adds noise):
```python
snr_diff = r_sci["signal_e"] / np.hypot(r_sci["noise_e"], ref["noise_e"] / template_factor)
# ref = choose_reads(sim, t * template_factor, mags=40.0)[1]
# mags=40.0 → template has no transient, only host+sky noise
```

---

## Common patterns

**Kilonova blackbody proxy (two phases):**
```python
get_scene("blackbody", teff=5000, mag=21, bandpass="sdss_r", magsys="abmag")  # day ~1
get_scene("blackbody", teff=2500, mag=21, bandpass="sdss_r", magsys="abmag")  # day ~5
```

**SN Ia at B-maximum:**
```python
import os, wcc_etc
hsiao = os.path.join(os.path.dirname(wcc_etc.__file__), "data", "astrophysics", "hsiao07.dat")
get_scene("file", source_file=hsiao, mag=21, bandpass="sdss_r", magsys="abmag")
```

**Change host morphology only:**
```python
sim.update(host__n=1)   # disk; leave mag, r_eff, dx unchanged
```
