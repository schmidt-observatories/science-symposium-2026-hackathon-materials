---
name: esc-etc
description: Lazuli ExtraSolar Camera (ESC) coronagraph exposure time calculator. Load for questions about direct imaging of exoplanets or reflected-light planet detectability, S/N or time to S/N for a planet at a given contrast and separation, raw dark-hole contrast, post-processing gain, inner working angle, reference-star subtraction (RDI), frame time and saturation on bright hosts, zodi and exozodi backgrounds, or the twelve ESC filters. Package is esc_etc. Transit spectroscopy is not ESC, use lazuli-exo.
---

# Lazuli ESC Coronagraph ETC (`esc_etc`)

The ESC is the coronagraph on Lazuli: 3 m telescope, charge-6 vortex mask, deformable mirror digging
a dark hole of raw contrast ~1e-8, twelve filters from 400 to 730 nm. `esc_etc` is an analytic ETC
for one planet at one separation: five count rates in a resolution-element aperture (planet, speckle,
zodi, exozodi, host) plus a speckle noise floor that post-processing only partly removes.
Web version: <https://simulators.schmidtobservatorysystem.org/esc/>.

This is direct imaging. For **transit spectroscopy** (K2-18 b, TRAPPIST-1 e, ...) use the `lazuli-exo`
skill, which is the IFS, not the ESC.

## Quick start

```python
import astropy.units as u
from esc_etc import Simulation, use_lazuli_style

# Sun twin at 10 pc (V = 4.83), Jupiter-like planet at contrast 1e-8 (delta mag 20) at 0.4"
sim = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v",
                              planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)

r = sim.get_snr(total_time=3600, frame_time=100)        # seconds or astropy Quantities
r["snr"], r["signal_e"], r["noise_e"], r["M"]           # also reference_noise_e, science_time, charged_time

t = sim.get_int_time_for_snr(5, frame_time=100)
t["int_time_continuous"][0].to(u.hr)                    # exact time to S/N 5; NaN if above the plateau
t["int_time"][0]                                        # rounded up to whole frames
```

`from_default` arguments:

| argument | meaning |
|---|---|
| `filter` | ESC filter name, e.g. `"R3"` (F659W) or `"B4"` (F450W); `esc_etc.FILTERS` maps names and designations |
| `hoststarmag`, `hoststar_band` | host magnitude, in `"johnson_v"` or `None` (= the ESC filter itself) |
| `mag_system` | `"vega"` (default) or `"AB"` |
| `planetdeltamag` | planet faintness vs host in the ESC band; contrast C = 10**(-0.4 Δm), so 20 mag = 1e-8 |
| `contrast` | raw dark-hole contrast |
| `ppgain` | post-processing gain (speckle suppression factor) |
| `separation` | arcsec; must be inside the tabulated 20 λ/D (~0.9" in R3) |
| `bg_flux` | zodi, V mag/arcsec² (default 22.5) |
| `exobg_flux` | exozodi as Δmag/arcsec² relative to the host, in the ESC band (default 21) |
| `lifetime` | `"eol"` (default) or `"bol"` throughput |

## The plateau

S/N(t) = S t / sqrt(S t + B t + n_pix n_reads σ_read² + (M t)²) → S/M = ppgain × C_planet / C_raw as t → ∞.
The speckle floor term grows as t, so the S/N **saturates**; `get_int_time_for_snr` returns NaN for a
target S/N above the plateau. S/N 5 needs C_planet > 5 C_raw / ppgain. Check this first when an answer
comes back NaN.

## Changing parameters: `update()` / `reset()`

Any parameter is `component__parameter` (double underscore; nested elements add a level):

```python
sim.update(scene__star__mag=6.0, scene__planet__deltamag=22.5,
           coronagraph__ppgain=100, coronagraph__separation=0.15, coronagraph__raw_dh_contrast=1e-9)
sim.update(coronagraph__subtraction="rdi", coronagraph__ref_time_ratio=1.0, coronagraph__ref_brightness_ratio=1.0)
sim.update(scene__exozodi__mag=22.5, scene__exozodi__band="johnson_v")   # absolute exozodi surface brightness
sim.reset()                                                              # back to the constructed state
```

Invalid values raise `ValueError`. Inside loops, `update` then `reset` each iteration. Note the sign:
`scene__planet__deltamag = -2.5 * np.log10(contrast)` (positive; the planet is fainter).

## Frame time and saturation

Read noise is paid once per frame, so short frames hurt faint planets (1 s frames are read-noise
dominated, 1000 s frames are not). Bright hosts limit the frame:

```python
sim.saturation_time()            # frame time at which the brightest aperture pixel hits 80% of the well (Quantity)
sim.is_saturated(100)            # check a given frame time

def frame_for(sim, max_frame=1000 * u.s):     # helper used throughout the tutorials
    return min(u.Quantity(max_frame, u.s), 0.5 * sim.saturation_time())
```

`saturation_time()` returns a Quantity, so compare it with Quantities, not bare floats. It models only the
planet location at dark-hole contrast; for a very bright host the safe frame can be shorter.

## Diagnostics and plots

```python
rates = sim.count_rate_components()         # .source, .speckle, .zodi, .exozodi, .host (electron / s)
sim.coronagraph.off_axis_throughput(0.2)    # vortex mask throughput at 0.2"; ~0.65 peak, IWA (50%) ≈ 3.6 λ/D ≈ 0.165" in R3
sim.sensor.describe(); sim.coronagraph.describe()
sim.plot()                                  # six-panel overview
sim.plot_snr_vs_time(sweep={"coronagraph__ppgain": [1, 10, 100]})   # any update() key; also frame_time=, ax=, label=
sim.plot_count_rates(); sim.plot_bandpass(); sim.plot_aperture(); sim.plot_offaxis_throughput()
```

Components can be built separately and combined:
`Telescope.from_default`, `Sensor.from_default`, `get_scene`, `Coronagraph.from_default`, then
`Simulation.from_components(tel, sen, scene, cor)`.

## Model limits (say these when they matter)

- Star and planet spectra are **flat**: no colour terms. A red host quoted in V is treated as equally bright in R3; apply a V − filter colour by hand.
- Raw contrast is one number across the dark hole; in reality it degrades towards the IWA.
- Zodi and exozodi are pure shot noise. 1 zodi ≈ 22 − 2.5 log10(n) + 5 log10(r/AU) V mag/arcsec² (face-on, solar-luminosity host).
- No orbit, phase function or albedo model: the user supplies the contrast and separation.

## Tutorials and exercises

`lazuli/esc/tutorial/` (start with the README):
- `01_etc_in_one_line` — `from_default`, `get_snr`, `get_int_time_for_snr`, rates, the plateau
- `02_components_and_filters` — components, `update`/`reset`, magnitudes, the twelve filters, the aperture
- `03_contrast_gain_separation` — raw contrast, ppgain, mask throughput and IWA, contrast floor, RDI
- `04_frame_time_saturation` — read noise per frame, `saturation_time`, bright hosts, noise budget
- `05_zodi_and_exozodi` — background parameterization, zodis, exozodi sweep
- `exercises/ex1`–`ex6` (Jupiter twin, detectability map, bright hosts, RV giants, exozodi tolerance, bring your own target), solutions in `exercises/solutions/`. Exercises 3 and 4 contain a deliberately broken cell; let the user find it rather than fixing it unprompted.
- `backup/12_reflected_light_giants.ipynb`, `backup/13_exozodi_tolerance.ipynb` — the original ESC science cases.

Suggest starting from one of these rather than from scratch.
