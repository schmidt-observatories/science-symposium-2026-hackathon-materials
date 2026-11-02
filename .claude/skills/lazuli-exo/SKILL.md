---
name: lazuli-exo
description: Lazuli IFS exoplanet transmission spectroscopy ETC. Load for questions about transiting exoplanet atmosphere detectability, transit spectroscopy SNR, number of transits needed, stellar contamination (spots, faculae), or comparing planet and atmosphere scenarios with the Lazuli IFS. Package is lazuli_exo. Not the coronagraph, for ESC direct imaging use esc-etc.
---

# Lazuli Exoplanet Transit Spectroscopy ETC (`lazuli_exo`)

Transmission-spectroscopy ETC for the **Lazuli IFS** (0.4–1.7 µm). Showcase planets come with archive
parameters and precomputed slicersim noise tables; atmospheres are a 1D isothermal,
equilibrium-chemistry surrogate of POSEIDON.

This is **not** the coronagraph. For direct imaging / reflected light with the ESC, use the `esc-etc`
skill (`esc_etc` package, `lazuli/esc/tutorial/`).

## Planets and targets

```python
import lazuli_exo
from lazuli_exo.targets import get_target

lazuli_exo.list_planets()        # list of 14 showcase planet names, e.g. "K2-18 b", "TRAPPIST-1 e", "WASP-39 b"
t = get_target("K2-18 b")        # dict: T_eq_K, period_d, T_eff_K, J_mag, R_p_RJ, t14_s, ...
```

Planet names have a **space before the letter** (`"K2-18 b"`, not `"K2-18b"`).

Scenarios: `"clear"`, `"hazy"`, `"high_metallicity"`, `"cloudy"`, `"flat"` (featureless, zero signal by
construction; useful as a null for contamination tests).

## Observe a showcase planet

```python
o = lazuli_exo.observe("K2-18 b", "clear", n_transits=1, R=100)

o.wavelength        # bin centres, µm
o.depth             # model transit depth, FRACTION (multiply by 1e6 for ppm)
o.depth_err         # 1-sigma per bin, fraction
o.meta["atmosphere"]["feature_amplitude_ppm"]   # peak-to-peak feature amplitude
o.meta["atmosphere"].get("T_clamped")           # set if T_eq was clamped to the 300 K chemistry floor
o.simulate_points(seed=0)                       # one noisy realization of the depths
o.plot(units="ppm", seed=1)                     # returns a matplotlib Axes

d = o.detect()
d["template_snr_diagonal"]      # matched-template S/N against a flat line
d["band_snr"]["H2O"]            # per-molecule band S/N (dict keyed by molecule)
```

Errors scale as 1/sqrt(n_transits), so transits to reach S/N 5 are `ceil((5 / snr_1)**2)`; calendar
time is that times `get_target(p)["period_d"]`. `observe()` raises a `UserWarning` mentioning saturation
for bright hosts whose noise table is not validated; catch and report it.

## Custom atmospheres: `simulate()`

`simulate()` takes a planet/star dict (start from a preset) and runs live slicersim noise (the first call
for a new star takes about a minute, then it is cached):

```python
from lazuli_exo import presets
o = lazuli_exo.simulate({**presets.showcase("TRAPPIST-1 e", "clear"), "mu": 10.0}, R=100, n_transits=1)
o.detect()["band_snr"]["H2O"]
```

The validated mean molecular weight range stops at mu = 15, so N₂/CO₂ atmospheres (mu ≈ 28–44) are
outside the model. A user-supplied spectrum can be passed as `simulate(star, spectrum=(wl, depth))`.

## Stellar contamination (transit light source effect)

`observe()` multiplies the depth by the Rackham et al. (2018) contamination factor ε(λ) when given
unocculted spot / facula covering fractions:

```python
from lazuli_exo.star import TLSE_PRESETS     # e.g. "M_late_solar", "M_mid_solar", and "<key>_fac" variants
o = lazuli_exo.observe("TRAPPIST-1 e", "flat", n_transits=1, R=100, f_spot=0.2)
o = lazuli_exo.observe("TRAPPIST-1 e", "flat", n_transits=4, R=100, **TLSE_PRESETS["M_late_solar_fac"])
o.meta["atmosphere"]["tlse"]                 # T_spot_K, T_fac_K, eps_min, eps_max actually used
```

Defaults: T_spot = 0.86 T_eff for M dwarfs, T_fac = T_eff + 100 K.

## Caveats to state

- Template / band S/N is a ranking statistic, not a detection significance; the H₂O mask overlaps CH₄ near 1.15 µm.
- No systematics floor: errors fall as 1/sqrt(N) forever.
- M-dwarf PHOENIX SEDs are too bright in the blue, so blue-end noise is ~10–25% optimistic.
- Temperate planets are clamped to the 300 K chemistry floor.

## Tutorials

The worked examples are in `lazuli/science_gallery/`:
- `01_k2-18b_trappist-1e_atmospheres.ipynb` — S/N vs number of transits, scenarios, mean molecular weight sweep with `simulate`.
- `02_atmosphere_survey_ranking.ipynb` — ranks all showcase planets by S/N per transit.
- `03_stellar_contamination.ipynb` — spots and faculae faking or hiding an atmosphere.

If a user asks about transiting-exoplanet atmosphere detectability, suggest starting from one of these
notebooks rather than from scratch.
