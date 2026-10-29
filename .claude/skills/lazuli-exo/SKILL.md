---
name: lazuli-exo
description: Lazuli ESC/IFS exoplanet transmission spectroscopy ETC. Load for questions about exoplanet atmosphere detectability, transit spectroscopy SNR, stellar contamination, or comparing planet scenarios with the Lazuli coronagraph or IFS. Package is lazuli_exo.
---

# Lazuli Exoplanet ETC (`lazuli_exo`)

Lookup-table ETC for exoplanet transmission spectroscopy with the Lazuli IFS. Planets are parameterized by archive values; atmospheres are pre-computed model grids.

## List available planets and scenarios

```python
import lazuli_exo

planets   = lazuli_exo.list_planets()     # DataFrame of supported showcase planets
scenarios = lazuli_exo.list_scenarios()   # available atmosphere scenarios per planet
print(planets[["name", "host", "R_p_Re", "T_eq_K", "J_mag"]])
```

## Simulate an observation

`observe()` returns a `SimulatedSpectrum` from the precomputed noise table:

```python
result = lazuli_exo.observe(
    planet="K2-18b",
    scenario="clear",      # atmosphere model label
    n_transits=10,
    R=100,                 # spectral resolution for binning
    f_spot=0.0,            # unocculted spot fraction (stellar contamination)
    T_spot_K=None,         # spot temperature; None → default from registry
)
print(result.wavelength_um)   # μm bin centers
print(result.depth_ppm)       # transit depth in ppm
print(result.sigma_ppm)       # 1-sigma per bin
result.plot()
```

## Run the forward model (no noise)

`simulate()` returns the model transmission spectrum only:

```python
spec = lazuli_exo.simulate(planet="TRAPPIST-1e", scenario="earth_like", R=50)
```

## Stellar contamination

Add unocculted star spots/faculae to any `observe()` call:

```python
result = lazuli_exo.observe(
    "K2-18b", "clear", n_transits=20,
    f_spot=0.02, T_spot_K=3200,     # 2% spot coverage, 3200 K
    f_fac=0.01,                      # 1% faculae
)
```

## Key output attributes (`SimulatedSpectrum`)

| attribute | meaning |
|---|---|
| `.wavelength_um` | bin-center wavelengths in μm |
| `.depth_ppm` | transit depth (model + noise realization) |
| `.sigma_ppm` | 1-sigma per bin |
| `.model_ppm` | noiseless model depth |
| `.flat_depth` | geometric (R_p/R_s)² |

## Tutorials

`lazuli/science_gallery/01_k2-18b_trappist-1e_atmospheres.ipynb` — primary tutorial showing the full workflow from `list_planets` through `observe` and comparative plots.

`lazuli/science_gallery/02_atmosphere_survey_ranking.ipynb` — ranks all supported planets by atmospheric signal per transit.

`lazuli/science_gallery/03_stellar_contamination.ipynb` — stellar contamination deep dive.

If a user asks about exoplanet atmosphere detectability or transit spectroscopy, suggest starting from one of these notebooks rather than from scratch.
