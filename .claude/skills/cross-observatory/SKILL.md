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
| **Argus Array** | optical β + ρ bands | ~3″ (ground, seeing-limited) | all-sky cadenced survey | variability; cadence / light-curve history; depth map at any position |
| **LFAST** | optical 412–686 nm (Bench, R~300–3600) + near-IR 1.08–1.75 µm (CSHELL, R 18k–43k) | seeing-limited | single-fiber (one target per pointing) | cadenced / rapid spectroscopic follow-up at moderate R; He 10830 / near-IR stellar lines (CSHELL); stellar activity monitoring (Ca II, Hα); the *only* TSOS facility with NIR spectroscopy |

## Common multi-facility patterns

### Transient multi-messenger follow-up

1. **Argus** flags the transient (SurveyRun visit history, depth map sets context magnitude limit)
2. **WCC** provides precise optical position and multi-epoch photometry
3. **Classification spectrum** — two options depending on brightness and scheduling:
   - **Lazuli IFS** (`LazuliSupernova` / `LazuliKilonova`): preferred for faint transients (V ≳ 18) or when IFU spatial context matters (host separation, offset)
   - **LFAST Bench** (R~1800, 412–686 nm): sufficient for bright transients (V ≲ 18) and rapid cadenced monitoring; lower scheduling overhead than space time; use `LFASTETC("bench_r1800", n_telescopes=20)` to check exptime first
4. **DSA** checks for radio counterpart (continuum / FRB search depending on transient class)

**LFAST + Argus as a self-contained rapid-response chain** (no Lazuli needed for bright events):
Argus discovery → LFAST classification spectrum within the same night; use `LFASTETC.exptime(src, snr=30)` to confirm feasibility before requesting time.

**LFAST for spectral time series:** Lazuli IFS takes key-epoch classification spectra; LFAST monitors spectral evolution at high cadence across many epochs (e.g., SN phase coverage, kilonova NIR via CSHELL).

Handoff: WCC FITS WCS → DSA targeted pointing; Argus `run.visits(ra,dec)` → pre-trigger baseline light curve.

### FRB host galaxy identification

1. **DSA** detects FRB and gives arcsecond localization
2. **WCC** images the error box (optical counterpart / host candidate)
3. **Redshift spectrum** — two options:
   - **Lazuli IFS**: preferred for faint (r ≳ 19) or compact/high-z hosts where spatial resolution or depth matters
   - **LFAST Bench**: sufficient for bright nearby hosts (r ≲ 18–19) when rapid scheduling is needed

ETC chain: run `dsa_etc` for FRB fluence limit → `wcc_etc.Simulation` for host imaging depth → `slicersim.lazuli_etc` or `LFASTETC` for host redshift exposure time.

### Exoplanet atmosphere survey

1. **Lazuli ESC / `lazuli_exo`** simulates transmission spectrum SNR (`observe(planet, scenario, n_transits)`)
2. **WCC + `TransitModel`** estimates photometric transit precision for the same system (ingress timing, stellar variability)
3. **Argus** provides the long-baseline variability record of the host star (`run.inject(vis, stellar_model)`)
4. **LFAST** adds two independent ground-based diagnostics:
   - **CSHELL at R~18k** (1083 nm setting): He 10830 metastable helium transit absorption — a sensitive atmospheric escape tracer not covered by Lazuli IFS (which stops at 0.68 µm); see `ex4_he10830_cshell` for the ETC pattern. Use `Instrument.from_preset("cshell_r18000")` + `setting_window(1083.0)`.
   - **Bench (Ca II H&K ~397 nm, Hα 656 nm)**: stellar chromospheric activity monitoring in-transit to separate planetary signal from stellar contamination in ESC transmission spectra.

### SN Ia cosmology

1. **Argus** discovers SN candidates in survey (depth_map + inject with `sncosmo` template)
2. **WCC** provides multi-band light curve (g, r: use `wcc_etc.FluxModel` / `LightCurveSimulator`)
3. **Classification spectrum** — two options:
   - **Lazuli IFS** (`LazuliSupernova(model="salt", redshift=z)`): for SNe at z ≳ 0.05 or when high-fidelity spectral matching is needed; add `host="ngc0628"` or `host="sersic:bb-5000"` to include host galaxy noise (matters most when SN is near the nucleus)
   - **LFAST Bench**: sufficient for nearby SNe (z ≲ 0.05, V ≲ 18) and for dense phase coverage (many epochs) across the light-curve evolution; SNR classification targets at R~300 convert to Bench targets as `SNR_per_resel = SNR_300 / sqrt(R_bench / 300)`
4. **DSA** constrains host galaxy HI properties (targeted HI cube)

## Comparing depth / SNR across facilities

Each tool returns SNR or limiting magnitude independently; combine them by position:

```python
# Argus depth at a position
from argus_sim.lightcurve import SurveyRun
run = SurveyRun("~/s3/schmidt-observatory-system/argus/sim/argsim_5yr_beta_rho_uniform_v5.4/store")
dm = run.depth_map("beta")     # limmag column = 5-sigma stacked depth per tile

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

# LFAST Bench: limiting magnitude and exposure time for a target
from lfast_etc import LFASTETC, Source
import numpy as np
etc = LFASTETC("bench_r1800", n_telescopes=20)
src = Source.blackbody(5800, mag=0, band="V")               # template; magnitude set by grid
print(etc.limiting_magnitude(src, exptime=900, snr=10, wavelength=(500, 650)))  # V_lim, 20 tel, 15 min
# or: check if a specific transient is feasible
transient = Source.powerlaw(-1.0, mag=17, band="r", system="AB")
res = etc.exptime(transient, snr=30)
print(f"median exptime for SNR 30: {np.nanmedian(res.exptime):.0f} s")

# LFAST CSHELL: SNR for He 10830 in one echelle setting
from lfast_etc import Instrument
cs = Instrument.from_preset("cshell_r18000")
lo, hi = cs.setting_window(1083.0)
cshell = LFASTETC(cs, wavelength_min_nm=lo, wavelength_max_nm=hi, n_telescopes=20)
star = Source.blackbody(3500, mag=8, band="J")
r = cshell.snr(star, exptime=600)
print(f"He 10830, J=8 M star, 600 s: median SNR/resel = {np.nanmedian(r.snr):.1f}")
```

## Data format handoffs

| from | to | what to pass |
|---|---|---|
| Argus `run.visits(ra,dec)` | WCC targeting | (ra, dec) in decimal degrees |
| WCC FITS image | DSA targeted obs | WCS centroid → `--ra` / `--dec` in dsa_etc CLI |
| DSA localization (arcsec) | IFS slit/spaxel | position error box; check it fits in 58×58 spaxels at 40–80 mas |
| DSA localization (arcsec) | LFAST fiber | position precision; LFAST uses a single fiber — target must be point-like or unresolved |
| `slicersim.LazuliSupernova` spectrum | Argus light-curve model | redshift + SALT2 params → `sncosmo` source → `run.inject` model |
| WCC magnitude (r-band) | LFAST feasibility check | `Source.powerlaw` or `.blackbody` normalised to the WCC r-band mag; run `LFASTETC.exptime` to confirm exptime before scheduling |
| LFAST Bench spectrum (SN redshift) | IFS targeting | confirmed redshift → `LazuliSupernova(redshift=z)` for deeper / higher-resolution follow-up |

## Tips

- **Argus is a ground-based, night-only survey of the sky visible from its site. It is not full-sky and not continuous.** It observes only between the end of evening and the start of morning astronomical twilight. Its instantaneous field of view is about 8,000 deg², it covers up to about 21,000 deg² per night and up to two-thirds of the celestial sphere per year, and it reaches south only to about −20° declination. The minimum altitude is 38°.
- **Argus does not stare at one field.** It tracks the sky in 9–15 minute pointings and then moves on, so per-field light curves come in segments within a night and have daytime gaps between nights. Base cadence is minute-scale exposures on dark and gray nights. A second-scale high-speed cadence runs on the brightest nights (about 12% of nights). Each band is planned to be imaged at least once per hour of observation.
- Before planning follow-up, check that the target is north of about −20° declination and is observable at night from the Argus site on the dates you need.
- DSA continues to provide all-sky continuum imaging at radio wavelengths.
