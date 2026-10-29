---
name: wcc-etc
description: Lazuli Wide-field Context Camera (WCC) exposure time calculator. Load when estimating SNR, depth, or exposure time for point sources, extended sources, transients, or transit light curves observed with the WCC. Package is wcc_etc.
---

# WCC Exposure Time Calculator (`wcc_etc`)

Compute SNR or exposure time for observations with the Lazuli Wide-field Context Camera.

## Quick pattern

```python
import wcc_etc

telescope = wcc_etc.Telescope()         # default WCC config
sensor    = wcc_etc.Sensor()            # default sensor config
scene     = wcc_etc.get_scene("star", mag=20.0, band="r", magsys="abmag")
sim       = wcc_etc.Simulation(telescope, sensor, scene, time=90)  # time in seconds
sim.run()
print(sim.snr)           # per-aperture SNR
print(sim.mag_limit)     # 5-sigma limiting magnitude
```

## Scene construction

`get_scene(kind, ...)` is the recommended factory. Common kinds:

| kind | required kwargs | notes |
|---|---|---|
| `"star"` | `mag`, `band` | point source; PSF-aperture photometry |
| `"galaxy"` | `mag`, `band`, `re_arcsec`, `n` | Sérsic profile |
| `"uniform"` | `mag_arcsec2`, `band` | sky / extended background |
| `"blackbody"` | `teff`, `mag`, `band` | stellar SED |
| `"powerlaw"` | `index`, `mag`, `band` | AGN / transient SED |

Load from a config file: `get_scene_from_file(path)`. Default `magsys` is `"abmag"`; pass `magsys="vegamag"` for Vega.

## PSF

`Simulation` picks a default PSF. Override with the `psf=` kwarg:

```python
psf = wcc_etc.DefocusPSF()                  # mission baseline defocus
psf = wcc_etc.AiryPSF(lbda_um=0.7)         # Airy disk at given wavelength
psf = wcc_etc.PolychromaticPSF(lbda_range=[0.4, 1.0])
sim = wcc_etc.Simulation(telescope, sensor, scene, time=90, psf=psf)
```

## Key Simulation attributes after `.run()`

- `sim.snr` — scalar or array SNR
- `sim.snr_per_pixel` — per-pixel SNR map
- `sim.mag_limit` — 5-sigma point-source limiting magnitude
- `sim.noise_budget` — dict of noise terms (sky, dark, read, signal)
- `sim.image` — `SimulatedImage` with `.data`, `.header`

## Plotting helpers (matplotlib)

```python
wcc_etc.plot_image_mpl(sim)
wcc_etc.plot_radial_mpl(sim)
wcc_etc.plot_encircled_energy_mpl(sim)
wcc_etc.set_wcc_style()     # apply WCC house style to all mpl figures
```

## Transit light curve

```python
lc_sim = wcc_etc.LightCurveSimulator(telescope, sensor, scene)
lc     = lc_sim.run(transit_model)   # transit_model is a wcc_etc.TransitModel
lc.plot()
```

Download planet parameters: `wcc_etc.download_exoplanet_archive()` → `load_exoplanet_archive()`.

## Config / IO

```python
cfg = wcc_etc.read_config()                     # default instrument config dict
cfg = wcc_etc.get_sensor_config("wcc_prime")    # named sensor config
```

## Tutorials

`lazuli/wcc/tutorial/` — especially `01_tdamm_transient_on_host.ipynb` and `03_exo_transit_photometry.ipynb`.

Science gallery notebooks are worked examples — prefer pointing users to these as a starting point:
- `lazuli/science_gallery/08_fast_transient_depth.ipynb` — depth in 1/5/30 min, kilonova colour
- `lazuli/science_gallery/09_tde_in_galaxy_nuclei.ipynb` — nuclear transient on a bright bulge
- `lazuli/science_gallery/10_precision_transit_photometry.ipynb` — bright-star photometric precision, Earth-transit detectability
