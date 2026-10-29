---
name: wcc-sim
description: Lazuli WCC end-to-end pixel-level image simulator. Load when building simulated WCC FITS images, multi-epoch stacks, or dithered mosaics with a full source catalog. Package is wcc_sim; it wraps wcc_etc.
---

# WCC Image Simulator (`wcc_sim`)

Pixel-level photorealistic image simulation for the Lazuli Wide-field Context Camera. Builds on `wcc_etc` for the noise model and adds: source catalogs, PSF rendering, detector effects, and FITS output.

## Quick pattern — simulate a field

```python
import wcc_sim
import wcc_etc

# Build the source catalog (pandas DataFrame with required columns)
cat = wcc_sim.empty_catalog()          # template with correct dtypes
# add rows: cat = pd.concat([cat, rows])

# One observation = one pointing + exposure
obs = wcc_sim.WCCObservation(
    ra=150.12, dec=2.21,
    time=90,               # seconds per exposure
    n_exp=3,               # number of co-added exposures
    filter="r",
)

# Simulate — returns SimulatedField (FITS + metadata)
field = wcc_sim.simulate_field(obs, catalog=cat)
field.write("output.fits")             # write FITS image
```

## Convenience: `simulate_image`

For a single image without a full observation object:

```python
img = wcc_sim.simulate_image(telescope, sensor, scene, time=90)
# img is a wcc_etc.SimulatedImage
```

## Extended-source components

Use `GalSimComponent` / `SersicComponent` for galaxies rendered via GalSim:

```python
gal = wcc_sim.SersicComponent(
    ra=150.12, dec=2.21,
    mag=19.5, band="r",
    re_arcsec=0.5, n=1.0,
)
```

`SkyImageComponent` drapes an existing sky image (e.g. HST mosaic) onto the WCC focal plane.

## Key classes

| class | purpose |
|---|---|
| `WCCObservation` | Pointing + exposure parameters, the unit of a simulated visit |
| `SimulatedField` | Output of `simulate_field`; holds FITS WCS, image data, noise map |
| `GalSimComponent` / `SersicComponent` | Extended Sérsic galaxy sources |
| `SkyImageComponent` | Tile an existing sky image |
| `ImageComponent` | Generic rasterized source component |

## Multi-epoch stacking / dithering

Pass a list of `WCCObservation` objects to `simulate_field` to simulate a dithered stack:

```python
fields = [wcc_sim.simulate_field(obs, catalog=cat) for obs in obs_list]
# stack with your preferred drizzle / mean-combine logic
```

See `lazuli/wcc/tutorial/05_cosmo_dithered_stack.ipynb` for the full dither-and-combine pattern.

## CLI

```bash
python -m wcc_sim.cli --help
```

## Tutorials

`lazuli/wcc/tutorial/` — especially `04_cosmo_deep_field_depth.ipynb` and `05_cosmo_dithered_stack.ipynb`.

`lazuli/science_gallery/11_crowded_field_photometry.ipynb` — crowded-field (M4 core) photometric precision with `wcc_sim` + `wcc_phot`; use as a starting point for crowded-field or cluster science cases.
