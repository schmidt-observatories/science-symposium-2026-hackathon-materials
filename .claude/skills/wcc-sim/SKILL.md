---
name: wcc-sim
description: "Lazuli WCC end-to-end pixel-level image simulator. Load when building simulated WCC images of any sky scene: star fields, globular clusters, galaxies, nearby spirals (PHANGS), any sky FITS image (e.g. M31 cutout), crowded fields, multi-epoch stacks, or dithered mosaics. Package is wcc_sim; it wraps wcc_etc. Do NOT write scipy/numpy image simulation from scratch — use wcc_sim."
---

# WCC Image Simulator (`wcc_sim`)

Pixel-level photorealistic image simulation for the Lazuli Wide-field Context Camera. Builds on `wcc_etc` for the noise model and adds: source catalogs (Gaia DR3), PSF rendering, detector effects, and FITS output. **All extended-scene simulation — clusters, galaxies, real sky images — goes through wcc_sim, not custom scipy code.**

## Star fields and globular clusters — `simulate_field`

Point at any RA/Dec and `wcc_sim` queries Gaia DR3 and renders a full detector image:

```python
from wcc_sim import simulate_field

# Any Gaia field: globular cluster core, open cluster, crowded field, ...
field = simulate_field(
    ra=245.8968, dec=-26.5258,   # M4 globular cluster core
    sensorfilter="zwo:r",
    focus=1,                     # 1-wave defocus for precision photometry
    exptime=30,
    shape=(2048, 2048),          # subarray; omit for full 9576×6388 frame
    seed=42,
    cache_dir="gaia_cache",      # cache Gaia query on disk
)
field.plot(catalog=True)         # quick-look image with Gaia overlay
field.to_hdulist().writeto("m4_core.fits", overwrite=True)
```

Produces `SimulatedField` with `.image_e` (electrons), `.saturation_mask`, `.catalog` (truth), `.params`.

## PHANGS nearby galaxies — `phangs_component`

38 HST-surveyed nearby spirals (e.g. NGC 1300, NGC 628, NGC 3351) as `ImageComponent`, downloaded from the PHANGS-HST archive on first use (~400–580 MB per band):

```python
from wcc_sim import simulate_field
from wcc_sim.phangs import phangs_component, list_phangs_galaxies

print(list_phangs_galaxies())    # list available galaxy keys, e.g. 'ngc1300'

comp = phangs_component("ngc1300", "r")   # F555W HST mosaic as ImageComponent

field = simulate_field(
    ra=49.92, dec=-19.41,        # NGC 1300 centre
    sensorfilter="zwo:r",
    exptime=90,
    extended_sources=[comp],     # inject the galaxy image
    shape=(4096, 4096),
    seed=1,
)
```

## Draping any FITS sky image — `simulate_image` / `SkyImageComponent`

For any WCS-calibrated sky image (e.g. an M31 HST cutout, PanSTARRS tile, or custom mosaic):

```python
from wcc_sim import simulate_image
from wcc_sim.imagesource import SkyImageComponent

# Option A: one-call wrapper — centres on image WCS, adds noise, returns SimulatedField
field = simulate_image(
    "m31_cutout_r.fits",         # any FITS with celestial WCS and BUNIT
    sensorfilter="zwo:r",
    exptime=90,
    seed=1,
    output="m31_wcc.fits",       # optional FITS output
)

# Option B: inject as extended_sources alongside Gaia stars
comp = SkyImageComponent.from_fits("m31_cutout_r.fits")
field = simulate_field(ra=10.68, dec=41.27, sensorfilter="zwo:r", exptime=90,
                       extended_sources=[comp], seed=1)
```

`BUNIT` in the FITS header tells wcc_sim the flux units; if absent, pass `flux_unit="MJy/sr"` (or the appropriate unit) explicitly.

## Analytic galaxy models — `SersicComponent`

For a smooth Sérsic profile without a real image:

```python
gal = wcc_sim.SersicComponent(
    ra=150.12, dec=2.21,
    mag=19.5, band="r",
    re_arcsec=0.5, n=1.0,        # half-light radius, Sérsic index
)
field = simulate_field(ra=150.12, dec=2.21, sensorfilter="zwo:r", exptime=90,
                       extended_sources=[gal], seed=1)
```

## Key classes

| class | purpose |
|---|---|
| `SimulatedField` | Output of `simulate_field`; holds `.image_e`, `.saturation_mask`, `.catalog`, `.params` |
| `SersicComponent` / `GalSimComponent` | Analytic Sérsic galaxy rendered via GalSim |
| `SkyImageComponent` | Any WCS+BUNIT FITS sky image draped onto the WCC focal plane |
| `ImageComponent` | AB-calibrated image (e.g. PHANGS-HST mosaic); used by `phangs_component` |

## Multi-epoch stacking / dithering

```python
import numpy as np
rng = np.random.default_rng(0)
PIX_DEG = 16.87e-3 / 3600
fields = [
    simulate_field(RA + rng.uniform(-0.5, 0.5) * PIX_DEG,
                   DEC + rng.uniform(-0.5, 0.5) * PIX_DEG,
                   sensorfilter="zwo:r", exptime=90, seed=k, cache_dir="gaia_cache")
    for k in range(5)
]
# stack with your preferred drizzle / mean-combine logic
```

## CLI

```bash
python -m wcc_sim.cli --help
```

## Tutorials

`lazuli/wcc/tutorial/06_fields_and_photometry.ipynb` — `simulate_field`, truth catalogue, photometry with `wcc_phot`.

`lazuli/science_gallery/11_crowded_field_photometry.ipynb` — **globular cluster (M4 core)** time series with `simulate_field` + `wcc_phot`; the canonical starting point for crowded-field / cluster science cases.

`lazuli/wcc/tutorial/` — also `04_psf_apertures_images.ipynb` (deep field depth) and `05_light_curves.ipynb` (dithered stacks).
