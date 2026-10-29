---
name: cross-observatory
description: Multi-facility science with the Schmidt Observatory System. Load when a question involves more than one observatory, asks how facilities compare, or requires combining outputs (depth, SNR, spectra, radio) across Lazuli, DSA, Argus, or LFAST.
---

# Cross-Observatory Science — Schmidt Observatory System

## Facility quick-reference

| facility | wavelength / band | angular resolution | field of view | strengths |
|---|---|---|---|---|
| **Lazuli WCC** | optical (g–z, ~0.4–1.0 µm) | ~100 mas (space, defocused PSF) | ~0.1 deg² | wide-field optical imaging; transient discovery; transit photometry |
| **Lazuli IFS** | optical (0.4–0.68 µm) | 40–80 mas spaxels | 58×58 spaxels (narrow/wide field) | classification spectra; SN typing; kilonova spectral evolution |
| **Lazuli ESC** | optical + near-IR | coronagraphic | ~few arcsec contrast | exoplanet atmosphere transmission spectra; direct imaging context |
| **DSA** | radio 0.70–2.00 GHz | ~3.5″ (full-band imaging) | 3.4° primary beam (1.35 GHz) | continuum, HI, polarization; FRB detection & localization; pulsar timing |
| **Argus Array** | optical g + ρ bands | ~3″ (ground, seeing-limited) | all-sky cadenced survey | variability; cadence / light-curve history; depth map at any position |
| **LFAST** | optical + near-IR | seeing-limited | fiber-fed (fixed zenith) | rapid spectroscopic follow-up; fiber throughput limited |

## Common multi-facility patterns

### Transient multi-messenger follow-up

1. **Argus** flags the transient (SurveyRun visit history, depth map sets context magnitude limit)
2. **WCC** provides precise optical position and multi-epoch photometry
3. **Lazuli IFS** classifies the transient (SN type, kilonova phase, AGN vs. stellar) via `LazuliSupernova` / `LazuliKilonova`
4. **DSA** checks for radio counterpart (continuum / FRB search depending on transient class)

Handoff: WCC FITS WCS → DSA targeted pointing; Argus `run.visits(ra,dec)` → pre-trigger baseline light curve.

### FRB host galaxy identification

1. **DSA** detects FRB and gives arcsecond localization
2. **WCC** images the error box (optical counterpart / host candidate)
3. **Lazuli IFS** takes a spectrum of the host candidate for redshift confirmation

ETC chain: run `dsa_etc` for FRB fluence limit → `wcc_etc.Simulation` for host imaging depth → `slicersim.lazuli_etc` for host redshift exposure time.

### Exoplanet atmosphere survey

1. **Lazuli ESC / `lazuli_exo`** simulates transmission spectrum SNR (`observe(planet, scenario, n_transits)`)
2. **WCC + `TransitModel`** estimates photometric transit precision for the same system (ingress timing, stellar variability)
3. **Argus** provides the long-baseline variability record of the host star (`run.inject(vis, stellar_model)`)

### SN Ia cosmology

1. **Argus** discovers SN candidates in survey (depth_map + inject with `sncosmo` template)
2. **WCC** provides multi-band light curve (g, r: use `wcc_etc.FluxModel` / `LightCurveSimulator`)
3. **Lazuli IFS** types the SN and measures redshift (`LazuliSupernova(model="salt", redshift=z)`)
4. **DSA** constrains host galaxy HI properties (targeted HI cube)

## Comparing depth / SNR across facilities

Each tool returns SNR or limiting magnitude independently; combine them by position:

```python
# Argus depth at a position
from argus_sim.lightcurve import SurveyRun
run = SurveyRun("s3://…/argsim_5yr_…/")
dm = run.depth_map("g")        # limmag column = 5-sigma stacked depth per tile

# WCC depth for the same position, one pointing
import wcc_etc
sim = wcc_etc.Simulation(wcc_etc.Telescope(), wcc_etc.Sensor(),
                         wcc_etc.get_scene("star", mag=25, band="r"), time=300)
sim.run()
print(sim.mag_limit)           # 5-sigma point-source AB mag

# DSA continuum noise at the same sky position
import subprocess, json
result = json.loads(subprocess.check_output(
    ["python3", "-m", "dsa_etc.cli", "--ra", "150.12", "--dec", "2.21", "--json"],
    cwd="dsa/exposure-time-calculator/python"
))
print(result["full_band"]["sigma_uJy"])  # 1-sigma µJy/beam, full survey depth

# IFS exposure time for a given target SNR
import slicersim
t = slicersim.lazuli_sn_etc("salt", redshift=0.1, snr=10, x1=0, c=0)
```

## Data format handoffs

| from | to | what to pass |
|---|---|---|
| Argus `run.visits(ra,dec)` | WCC targeting | (ra, dec) in decimal degrees |
| WCC FITS image | DSA targeted obs | WCS centroid → `--ra` / `--dec` in dsa_etc CLI |
| DSA localization (arcsec) | IFS slit/spaxel | position error box; check it fits in 58×58 spaxels at 40–80 mas |
| `slicersim.LazuliSupernova` spectrum | Argus light-curve model | redshift + SALT2 params → `sncosmo` source → `run.inject` model |

## Tips

- **Argus is a ground-based, night-only survey of the sky visible from its site. It is not full-sky and not continuous.** It observes only between the end of evening and the start of morning astronomical twilight. Its instantaneous field of view is about 8,000 deg², it covers up to about 21,000 deg² per night and up to two-thirds of the celestial sphere per year, and it reaches south only to about −20° declination. The minimum altitude is 38°.
- **Argus does not stare at one field.** It tracks the sky in 9–15 minute pointings and then moves on, so per-field light curves come in segments within a night and have daytime gaps between nights. Base cadence is minute-scale exposures on dark and gray nights. A second-scale high-speed cadence runs on the brightest nights (about 12% of nights). Each band is planned to be imaged at least once per hour of observation.
- Before planning follow-up, check that the target is north of about −20° declination and is observable at night from the Argus site on the dates you need.
- DSA continues to provide all-sky continuum imaging at radio wavelengths.
