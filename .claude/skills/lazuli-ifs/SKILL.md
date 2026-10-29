---
name: lazuli-ifs
description: Lazuli integral field spectrograph (IFS slicer) simulator and ETC. Load for any question about IFS SNR, exposure time, spectral cubes, transient or supernova spectroscopy, kilonova followup, or the Lazuli narrow/wide field modes. Package is slicersim.
---

# Lazuli IFS Simulator (`slicersim`)

Simulate IFS observations with the Lazuli slicer spectrograph. The IFS has two co-pointing fields on one detector:

| field | spaxel scale | spaxels | use case |
|---|---|---|---|
| narrow | 40 mas | 58×58 | point sources, high spatial resolution |
| wide | 80 mas | 58×58 | extended sources, fainter background |

## Quick ETC — exposure time for a given SNR

For a Type Ia SN:
```python
import slicersim
t = slicersim.lazuli_sn_etc(
    model="salt",          # "salt", "salt3", or "twin"
    redshift=0.1,
    snr=10,                # target SNR per resolution element
    x1=0, c=0,             # SALT2 params
    phase=0,               # days from B-band max
    lbda_range=[4000, 6800],
)
print(f"Exposure time: {t:.0f} s")
```

For an arbitrary spectrum (wavelength array in Å, flux in erg/s/cm²/Å):
```python
t = slicersim.lazuli_etc(lbda, flux, snr=10)
```

## High-level target classes

All `Lazuli*` classes wire in the Lazuli instrument config automatically.

```python
sn  = slicersim.LazuliSupernova(model="salt", redshift=0.1, x1=0, c=0, phase=0)
kn  = slicersim.LazuliKilonova(...)
std = slicersim.LazuliCalSpec(name="bd_17d4708")   # HST CalSpec standard
tgt = slicersim.LazuliTarget(lbda, flux, redshift=0.1)   # arbitrary spectrum
gal = slicersim.LazuliGalaxy(...)                  # galaxy alone, no point source
bb  = slicersim.LazuliBlackBody(teff=6000, mag=18)
```

## Running a simulation

```python
sim = sn.simulation           # slicersim.Simulation object
sim.run()

# Outputs
sim.spectrum                  # 1D extracted spectrum (flux vs wavelength)
sim.snr_spectrum              # SNR per wavelength bin
sim.variance                  # noise variance budget
sim.datacube                  # 3D (wave, y, x) datacube
sim.detector_image            # 2D detector image
```

## Switching between narrow and wide fields

```python
sn.change_spectrograph("wide")    # switch to 80-mas wide field
sn.change_spectrograph("narrow")  # back to 40-mas narrow field
combined_image = sn.to_image()    # both fields on one detector array
```

## Setting exposure time to hit a target SNR

```python
sn.setup_to_snr(snr=10, per_resolution=True)
print(sn.simulation.time)    # resulting exposure time in seconds
```

## Variance / noise budget

```python
sn.simulation.variance_budget()   # dict: photon, dark, read, thermal
```

## Tutorials

`lazuli/ifs/tutorial/` — start with `01_exposure_time_calculator.ipynb`, then `02_lazuli_targets.ipynb` and `05_variance_budget.ipynb`.

Science gallery notebooks are worked examples for common IFS science cases — prefer pointing users to these as a starting point rather than building from scratch:
- `lazuli/science_gallery/04_sn_ia_redshift_reach.ipynb` — SN Ia classification spectrum, redshift reach
- `lazuli/science_gallery/05_kilonova_followup.ipynb` — kilonova spectroscopic follow-up at 40 and 200 Mpc
- `lazuli/science_gallery/06_emission_line_galaxies.ipynb` — faint H-alpha / [O III] at z=1
- `lazuli/science_gallery/07_bright_limits_and_calibration.ipynb` — bright-limit and CalSpec calibration
