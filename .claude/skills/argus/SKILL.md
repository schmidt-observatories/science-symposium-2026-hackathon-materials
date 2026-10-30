---
name: argus
description: Argus Array materials. Load for questions about the simulated 5-year survey (sky coverage, per-position depth, cadence, light curve injection, running the survey simulator; package argus_sim, source in argus/argus_survey_model/src/argus_sim/) or the real prototype data (images, per-star minipix cutouts with DQ and calibration records, light curves; argus/prototype_data/, read with argex).
---

# Argus Array

The Argus Array is a wide-field photometric survey telescope imaging the whole visible sky every 60 s in two bands, **β**
(blue, about 365–520 nm) and **ρ** (red, about 565–825 nm). The code names them `"beta"` and `"rho"`.

| Directory | Contents |
|---|---|
| `argus/argus_survey_model/` | ArgusSim (`argus_sim`): the simulated 5-year survey and its visit store |
| `argus/prototype_data/` | Real data from the Array's prototype: four tutorials and four exercises with solutions |

## Part 1 — Visit store (science users start here)

The visit store is a pre-computed survey run (current: v5.4, 5-year survey) stored as Parquet on S3 or local disk. Open
it with `SurveyRun`; no GPU needed.

```python
import numpy as np
from argus_sim.lightcurve import SurveyRun, bin_lightcurve

run = SurveyRun("~/s3/schmidt-observatory-system/argus/sim/argsim_5yr_beta_rho_uniform_v5.4/store")  # JupyterHub bucket mount
# or: SurveyRun("s3://schmidt-observatory-system/argus/sim/argsim_5yr_beta_rho_uniform_v5.4/store/", storage_options={...})
```

### Key methods

```python
vis = run.visits(ra, dec, band="beta")          # all 60-s slots covering (ra, dec); one row per slot and OTA
vis = run.visits(ra, dec, band=["beta", "rho"]) # filter to bands
vis = run.visits(ra, dec, mjd_min=…, mjd_max=…)

run.periods                          # ["2028H1", "2028H2", …, "all"]: the depth maps' half-years
run.depth_map("beta", period="all")  # per-tile 5-sigma depth for one band and period
run.night_log(ra, dec)               # why nights have no data (weather, Moon, footprint)
run.nights()                         # nightly summary: depth, area, Moon, weather

snr   = run.snr(vis, mag)            # per-visit SNR for a source of this mag
sigma = run.sigma_mag(vis, mag)      # per-visit photometric uncertainty (mag)
lim   = run.limit_mag(vis)           # per-visit 5-sigma limiting magnitude
```

Stores written before the β rename call the blue band `"g"`; `SurveyRun` reads them as `"beta"`, and `band="g"` raises.

### Light curve injection

Any function `f(mjd, band) → AB magnitude` works as a model; `band` is an array of `"beta"`/`"rho"`:

```python
def rr_lyrae(mjd, band, P=0.5672, mean=16.5, amp=0.8):
    ph = (mjd / P) % 1.0
    shape = np.where(ph < 0.15, ph / 0.15, 1 - (ph - 0.15) / 0.85)
    return mean + amp / 2 - amp * shape

lc = run.inject(vis, rr_lyrae, rng=np.random.default_rng(1))
nightly = bin_lightcurve(lc, by="night")   # or by="ratchet": one point per 16-minute pointing
```

`lc` is an astropy Table: `mjd`, `band`, `mag_true`, `mag_obs`, `mag_err`, `snr_obs`, `detected`, `limit_mag`, fluxes
(`flux_obs_e`, `flux_err_e`, and in µJy), and the pointing (`tel_id`, `ratchet`, `night`). `sncosmo` and `redback`
models plug in directly (see `tutorial_survey_data.ipynb`).

### S3 credentials / custom endpoint

`storage_options` are the keyword arguments of `pyarrow.fs.S3FileSystem`:

```python
run = SurveyRun("~/s3/schmidt-observatory-system/argus/sim/argsim_5yr_beta_rho_uniform_v5.4/store", storage_options={"access_key": …, "secret_key": …, "region": …})
```

## Part 2 — Survey simulator (instrument / cadence studies)

Runs the full schedule from scratch; needs a GPU for reasonable speed (CuPy). Most users don't need this.

```python
import argus_sim
from astropy.time import Time

survey = argus_sim.Survey(start=Time("2027-01-01"), end=Time("2027-06-01"))
survey.run()
```

`asim survey` runs one from the command line. Override the instrument or survey with an `argussim.toml` in the working
directory (`asim defaults` writes the template).

## Part 3 — Prototype data (`argus/prototype_data/`)

Real data from the prototype (ADDEM: two co-pointed cameras, one per band, October 2026), staged on the bucket at
`~/s3/schmidt-observatory-system/argus/prototype_v1` (notebooks read `ARGUS_SAMPLE` to use another copy). Files are
FITS; open any of them with `argex.read(path)` (`pip install argex`), which returns a `Cutout`, `CutoutStack` or
`MinipixSeries`. Photometry is done with photutils. `DATA.md` there describes every file and convention.

| Notebook | Content |
|---|---|
| `01_images.ipynb` | footprint, frames covering a target, a whole segment, cutouts, a time sequence |
| `02_minipixes_and_records.ipynb` | per-star cutout series, DQ flags, the photometric-calibration records |
| `03_light_curves.ipynb` | aperture photometry, calibrated and differential light curves, a period search |
| `04_flares.ipynb` | four M-dwarf flares |

Exercises 1–4 are in `exercises/`, solutions in `exercises/solutions/`; exercises 3 and 4 combine the prototype data
with ArgusSim.

Conventions: pixels are e⁻/s per 0.879″ segment pixel; times are TT; zeropoints are AB magnitudes for a 4.05″ radius
aperture with a color term in β − ρ. The sample's flux conservation is approximate (`DATA.md`, Known limitations).

## Instrument quick-reference

| parameter | value |
|---|---|
| aperture per telescope | 280 mm |
| filter bands | β (blue, about 365–520 nm), ρ (red, about 565–825 nm) |
| exposure time | 60 s (base cadence) |
| read noise | 1.2 e⁻ |
| dark current | 0.0022 e⁻/s |
| sky grid | the archive's TAN sky segments and 32-pixel minipixes |
| visit store format | Parquet (pyarrow) |

## Tutorials

`argus/argus_survey_model/notebooks/`:
- `tutorial_survey_data.ipynb` — reading the visit store, depth maps, light curve injection
- `tutorial_depth_calculation.ipynb` — single-exposure depth from throughput + noise
- `SED_demonstration.ipynb` — synthetic Argus magnitudes and count rates from any spectrum

`argus/prototype_data/`: the four notebooks and exercises above.
