---
name: dsa-sensitivity
description: Deep Synoptic Array (DSA) sensitivity and exposure-time calculator. Use for any question about what the DSA can detect or how long it needs - continuum, HI or polarization image noise, confusion, PSF size, brightness temperature, FRB fluence limits and rates, pulsar-search flux limits (targeted and untargeted Chronoscope beams), pulsar-timing precision, scattering and DM budgets, or survey depth at a sky position.
---

# DSA sensitivity calculator

This skill runs the engine behind the DSA Sensitivity Calculator web page and gives the same numbers. It covers every DSA data product, either at a position in the Cadenced All-Sky Survey (CASS) or for a targeted observation:

- continuum images (ten spectral windows, the full band, and 6-s snapshots)
- HI cubes (Zoom B, Zoom A, Narrow Line)
- polarization cubes (IQUV, 500 × 2.6 MHz) and RM synthesis
- Chronoscope time-domain products, each a track centered on transit (default 21 min): FRB search (fluence limits, losses, DM budget, rates), pulsar search (untargeted and targeted beams) and pulsar timing (targeted beams and the Pulsar Timing subsystem)

## Run it

Needs Python 3.9 or later and numpy (`pip install numpy` if the import fails). From this skill's folder:

```bash
python3 scripts/run.py --ra 150.12 --dec 2.21                         # survey position, full depth
python3 scripts/run.py --ra 10:00:28.6 --dec +02:12:21 --depth single  # one epoch
python3 scripts/run.py --mode targeted --ra 150.12 --dec 2.21 --hours 10 --smooth 30
python3 scripts/run.py --ra 266.4 --dec -28.94 --json > result.json    # every number, as JSON
```

`--ra` takes degrees or sexagesimal hours. `--dec` takes degrees or sexagesimal degrees.

| Option | Meaning | Default |
|---|---|---|
| `--mode survey` or `targeted` | Survey mosaic at the position, or one pointing centered on it | survey |
| `--depth full`, `single` or `custom` with `--epochs N` | Survey depth: all epochs planned for the position, one epoch, or N | full |
| `--hours H` | Targeted time on source. Tracks stay within ±2 h of transit, so longer requests are split over several transits (100 h = 25 transits of 4 h). | 1 |
| `--weighting IMAGING:SUMMATION` | Imaging `natural` (Natural), `robust_freq` (Robust, R = 0.46–1.94, rising with frequency) or `robust_0p4` (Robust, R = 0.4); spectral-window summation `optimal` (inverse-variance) or `equal`. `auto` picks the lowest total noise. | auto |
| `--smooth ARCSEC` | Also give image products convolved to this resolution, for brightness-temperature sensitivity on larger scales | off |
| `--no-subtract` | Smoothed continuum: do not subtract the sources detected at full resolution before smoothing | subtract |
| `--products` | Any of `continuum,line,polarization,frb,pulsar,pta` (`pulsar` includes targeted timing; `pta` is the Pulsar Timing subsystem) | all |
| `--rfi` | `default` (Spring Valley model extrapolated: the measured pattern scaled to DSA sensitivity, 15% loss), `measured` (2.8% loss), `none`, or a CSV of MHz, occupancy | default |
| `--variant` | Survey plan: `A` (Plan A: DSA-00264 corrected fill), `B` (uniform Euclid/HSC depth), `C` (maximum detections) or `fig1` (reference plan: depth by declination) | A |
| `--track-s S` | Time-domain track length in survey mode, centered on transit; in targeted mode the pulsar and FRB products use `--hours` | 1260 |
| `--psr-period-ms`, `--psr-width-ms`, `--psr-dm`, `--psr-flux-mJy`, `--psr-nu-ref`, `--psr-alpha` | The one pulsar that drives every pulsar product (width is the intrinsic FWHM, not scaled with period; flux density at `--psr-nu-ref` MHz) | 500, 15, ½ Galactic DM, 0.02, 1400, −1.6 |
| `--targeted-center-MHz F` | Targeted-beam band center; presets 953.35 (800.0–1106.7 MHz) and 1800 are always reported, a custom center is added | 953.35 |
| `--untargeted-beam-arcsec B1,B2,B3` | Untargeted beam FWHM per band | 13.5, 8.90, 6.98 |
| `--pta-period-ms`, `--pta-width-ms`, `--pta-dm`, `--pta-flux-mJy`, `--pta-nu-ref`, `--pta-alpha` | Pulsar timed by the Pulsar Timing subsystem | 4, 0.2, 20, 1, 1400, −1.6 |
| `--hi-widths W1,W2,…` | HI line widths (km/s) for the mass limits | 50,200,500 |
| `--scattering` | `ne2025` (grid) or `cordes22` (τ–DM relation, no distance) | ne2025 |
| `--frb-dm`, `--frb-width-ms`, `--frb-max-dm` | FRB DM, intrinsic width, maximum searched DM | 500, 1, 5000 |
| `--set KEY=VALUE` | Override any engine parameter, e.g. `tsys_zenith_K=25`, `extra_loss_percent=10`, `galactic_noise=false`, `frb_dm_halo=40`, `td_eta_i2=0.9`, `td_confusion_uJy=0`, `hi_distances_Mpc=[20,40]` | |

For loops, plots or inverse questions, use the Python API:

```python
import sys; sys.path.insert(0, "scripts")            # this skill's scripts folder
from dsa_etc import DSACalculator, DEFAULTS, rfi_measured
calc = DSACalculator()                                # or DSACalculator(tsys_zenith_K=25, rfi=rfi_measured())
r = calc.calculate(mode="survey", ra=150.12, dec=2.21)                    # depth="single" / depth="custom", n_epochs=3
r = calc.calculate(mode="targeted", ra=150.12, dec=2.21, hours=10, smooth_arcsec=30,
                   products=("continuum", "line"), weighting="natural:optimal")
print(r["continuum"]["fc"]["total_uJy"])
```

## Where the answers are

All noise values are 1σ; flux densities are per beam; PSF sizes are FWHM in arcsec, PA in degrees.

| Question | Field |
|---|---|
| Continuum, full band | `continuum.fc`: `thermal_uJy`, `confusion_uJy`, `total_uJy`, `nu_eff_MHz`, `psf` {bmaj, bmin, pa}, `tb_thermal_mK`, `tb_total_mK` |
| Continuum per 130-MHz window | `continuum.windows[]`: same fields plus `t_eff_s` |
| One 21-min pointing (survey) | `continuum.single_pointing` |
| 6-s snapshots (transients) | `continuum.snapshots_6s[]`: four sub-bands and the full band |
| Smoothed images | `continuum.smoothed` (and `smoothed` inside HI and polarization channels); `continuum.smoothed.subtraction` has both cases: `applied`, `limit_uJy` (5σ of the full-resolution image), `residual_confusion_uJy`, `tb_total_subtracted_mK`, `unsubtracted_confusion_uJy`, `tb_total_unsubtracted_mK` |
| HI | `line.ZB`, `line.ZA`, `line.NL`, each with `channels[]`: `sigma_mJy` per channel, `dv_kms`, `tb_K`, `nhi_5sigma_cm2` (over 20 km/s), `mhi_limits[]` (5σ HI mass) |
| Polarization | `polarization`: `channels[]` (four representative channels, 750–1950 MHz), `band_qu_sigma_uJy`, `rmsf_fwhm_rad_m2`, `max_scale_rad_m2`, `max_rm_rad_m2`, `spectrum` ([MHz, σ in μJy] for each 2.6-MHz channel) |
| Time-domain set-up | `time_domain`: `track_s`, `n_transits`, `l_deg`, `b_deg`, `tau_c_s` (confusion correlation time), `survey` (tile, class, epochs, `in_7_epoch_tile`; context only), `usable_fraction` per band |
| FRB | `frb.bands[]` (B1 880–980, B2 1310–1510, B3 1650–1950 MHz): `fluence_min_Jyms` (headline, all losses), `fluence_peak_Jyms` (beam peak), `speak_min_mJy`, `weff` {`weff_ms`, `w_int_ms`, `t_samp_ms`, `t_dm_ms`, `tau_mw_ms`, `tau_host_ms`}, `losses` {`quantization`, `straddle`, `pb_average`, `dm_trial`, `confusion`, `self_noise`, `total`}, `dm_trials`, `fov_deg2`, `beam_area_deg2` and `beam_coverage` (sky covered by the search beams, and as a fraction of `fov_deg2`), `omega_rate_deg2` (solid angle used for the rates), `straddle_rate`, `loc_ra_1sigma_arcsec`, `loc_dec_1sigma_arcsec` (uniformly weighted localization beam), `rate_per_yr`, `rate_in_track`; `frb.dm_budget` (`dm_mw`, `dm_halo`, `z`, `dm_cosmic`, `dm_host`, `tau_mw_1GHz_ms`, `tau_host_1GHz_ms`, `below_galactic`); `frb.curves` (`dm` and fluence per band) |
| Pulsar search and timing | `pulsar.untargeted[]` (per band) and `pulsar.targeted[]` (953.35, 1800 and any custom center; `selected`): `snr`, `smin_uJy` (at the band center), `s1400_min_uJy`, `searched` (false outside the period range), `weff` {`weff_ms`, `w_int_ms`, `t_samp_ms`, `t_dm_ms`, `tau_ms`}, `losses` {`quantization`, `confusion`, `self_noise`, untargeted also `taper`}, `bw_usable_MHz`, `sefd_beam_Jy`; targeted `toa_us`; untargeted `beam_arcsec`, `n_beams`, `area_deg2`, `frac_unique_area`, `frac_pb_fwhm`. `pta` (Pulsar Timing subsystem, its own pulsar in `pta.inputs`): `snr`, `toa_us`, `s1400_min_uJy`, `losses` {`quantization` (1: no digitization loss), `confusion`, `self_noise`}, `subbands[]`. `pulsar.propagation`: `model`, `dist_kpc`, `tau_1GHz_ms`, `tau_bands_ms`, `dm_max`, `dm_above_max`. `pulsar.curves`: `period_s` and `smin_uJy` for `targeted`, `untargeted_B1`… (null = not searched) |
| Why the noise is what it is | `system` (full band: `tsys_band_K` and its parts, `sefd_band_Jy`; at 1.35 GHz: `tsys_K`, `spill_K`, `atm_K`, `galactic_excess_K`, `sefd_1350_Jy`; usable band); `observation` (tile, planned epochs, `effective_epochs_1350`, transits); `weighting` (choice and `comparison` of all six schemes); `warnings` |

## How to answer

- **Always report** thermal, confusion and total noise together with the PSF, and name the weighting.
- **For survey positions**, give the tile's planned epochs and the beam-weighted effective epochs. Depth blends across tile boundaries: RA 0, Dec 0 sits between a 7-epoch and a 3-epoch tile and gets 5.3 effective epochs.
- **Pass on warnings** (southern edge, split transits, unobservable positions).
- **Say which defaults matter** when the user did not choose them: survey Plan A; the extrapolated RFI model (15% of the band lost); the 4-bit quantization efficiency 0.988 on the imaging noise; for time-domain products the 21-min track, the input pulsar (P 500 ms, W 15 ms, DM half the Galactic value, 0.02 mJy at 1.4 GHz), FRB S/N 10, DM 500, 1 ms, and NE2025 scattering.
- **For pulsar and FRB answers**, quote the losses separately (quantization, taper, confusion, self-noise; FRB straddle, primary-beam average, DM trials) and the W_eff breakdown, so the user can see what dominates. Say which targeted center you quote. FRB rates carry roughly a factor-of-two uncertainty.
- **Never add the FRB rates of B1, B2 and B3.** The bands observe overlapping sky, so one burst can be detected in more than one band and the band rates are not additive; a sum overestimates the total by up to about 3×. Quote each band's rate, or the highest one, as the calculator does, and say that the bands overlap.

**Time needed to reach a noise level (targeted).** Thermal noise falls as 1/√t but confusion does not. If the target is below the confusion noise, say it cannot be reached at that resolution and suggest robust weighting (smaller beam, less confusion) or survey stacking. Otherwise solve for the time, trying each weighting:

```python
from dsa_etc.engine import SCHEMES

def hours_for(target_uJy, ra, dec, hi=5000.0):
    """Shortest targeted time for a full-band continuum total noise. Returns (hours, weighting) or None."""
    best = None
    for im, su in SCHEMES:
        w = im + ":" + su
        total = lambda h: calc.calculate("targeted", ra, dec, hours=h, products=("continuum",),
                                         weighting=w)["continuum"]["fc"]["total_uJy"]
        if total(hi) > target_uJy:
            continue                                  # confusion floor, or more than `hi` hours
        lo, top = 0.01, hi
        for _ in range(40):                           # bisection in log(hours)
            mid = (lo * top) ** 0.5
            lo, top = (mid, top) if total(mid) > target_uJy else (lo, mid)
        if best is None or top < best[0]:
            best = (top, w)
    return best
```

At Dec +30 this gives 0.43 h for 1 μJy, 6.3 h for 0.3 μJy and 17.0 h for 0.2 μJy; 0.05 μJy is below the confusion floor. Close to the floor the answer depends on small PSF changes (long requests are split into several shorter transits), so quote it as approximate and give the thermal and confusion parts.

**HI mass limits for other distances or line widths.** Use `--set hi_distances_Mpc=[20,40] --set hi_widths_kms=[100]`, then read `line.ZA.channels[0].mhi_limits`. Limits are 5σ for an unresolved source: M_HI = 49.7 D_L² S_int, with S_int in Jy Hz.

**Brightness temperature on larger scales.** Use `--smooth θ` and read `tb_thermal_mK` of the smoothed product. Smoothing is equivalent to a uv taper; the noise per beam rises by the taper factor, computed from the real baselines (every one shorter than 1 km, down to 10 m). The smoothed beam is the requested Gaussian: tapering the dirty beam gives a main lobe within 2% of it to 1′ and within 13% to 10′ at 1.35 GHz; beyond ~15′ (~30′ at 0.7 GHz) the few shortest baselines set the beam and the output carries a warning. By default the sources detected at full resolution (above 5σ) are subtracted before smoothing, and the confusion left is that of the fainter sources, which falls with scale (T_b ∝ 1/θ) and ends up comparable to the thermal T_b. Without subtraction (`--no-subtract`) confusion dominates every smoothed scale (34–87 mK from 1′ to 15′, peaking near 7′, at full survey depth at the default position). Always say which case you quote; `subtraction` holds both.

**Survey depth across the sky.** Loop over positions with `products=("continuum",)`; each position takes about 5 ms (all products about 0.1 s).

## Model in brief

- **SEFD** = 2k T_sys/(ηA), with T_sys(ν) the measured bandpass at zenith on cold sky with RFI removed (median 21.4 K), η = 0.67 and A = π(6.155 m)²/4: 2817 Jy at zenith at 1.35 GHz, for every product. Spillover and atmosphere add with zenith angle (about +2.5 K at ZA 40°, +7.3 K at ZA 70°, band average). Galactic synchrotron (GSM2008, beam-smoothed) adds above the median high-latitude sky.
- **Thermal noise** σ = SEFD/(η_v4 √(N(N−1) · 2 · Δν · t)), with N = 1650, Δν = ∫(1 − occupancy) dν and η_v4 = 0.988, the efficiency of correlating 4-bit voltages (`correlator_efficiency`). The default occupancy keeps the frequency pattern of the Spring Valley measurement but is scaled to DSA sensitivity (each channel treated as having 24× as many transmitters above threshold), losing 15% of the band; clean channels, including the HI band, stay clean.
- **Survey:** 21-min pointings on a hexagonal grid. The effective time is 21 min × Z(ν) × N_eff(ν). The mean mosaic weight Z is 5.35 at 0.7 GHz, 1.44 at 1.35 GHz and 0.65 at 2.0 GHz; N_eff is the beam-weighted number of epochs. The survey has 64,250 pointings (5 × 12,850) over 429 tiles; Plan A is the default.
- **Targeted:** noise at the primary-beam center, |HA| ≤ 2 h, elevation ≥ 20°.
- **PSF** from configuration `dsa1650_P305_v2.5.6.8`: natural weighting gives 3.03″ × 2.31″/cos(ZA) at 1.35 GHz, scaling as 1/ν. Robust-weighting factors come from Rosero (2026).
- **Confusion:** Condon's Universal Confusion Calculator curve for β = 16 (Mauch et al. 2020 criterion; Matthews et al. 2021 counts; tabulated by Rosero 2026), σ_c ∝ θ² ν^−0.7 in form, evaluated at the full-band beam and effective frequency.
- **Time domain (Chronoscope):** the same T_sys, η and RFI profile as the imaging products (B1 99%, B2 100%, B3 98% usable). 10-MHz sub-bands, W_eff = √(W_int² + t_samp² + t_DM² + τ²), quantization 0.988 (4-bit voltages, for beams formed from the correlations and for the targeted voltage beams) × 0.939 (2-bit intensities, pulsar searches and targeted timing) or × 0.994 (4-bit intensities, FRBs); no digitization loss for the Pulsar Timing beams, which are formed before the antenna voltages are requantized; self-noise from the source's own on-pulse or on-burst flux density; sidelobe confusion as red noise; NE2025 scattering. Untargeted beams are tapered visibility beams (noise and sidelobe factors from the configuration); the Pulsar Timing subsystem (four full-band beams) times its own pulsar; targeted beams are full-array voltage beams. FRBs add host DM and scattering, beam straddle, primary-beam average and DM-trial losses, and rates from Connor et al. (2026) eq. 2 over the sky the search beams cover, weighted by the primary-beam response and the source counts.

`reference/model.md` has every equation, table and source.

## Caveats to pass on

- The default RFI model is an extrapolation, not a measurement: the true loss at DSA sensitivity is not yet known. For a more pessimistic case add `extra_loss_percent` (24 leaves 65% of the band usable).
- The T_sys bandpass is interpolated across ranges dominated by RFI (1170–1300 and 1540–1630 MHz).
- Robust-weighting factors north of Dec +30° use the +30° values.
- Pulse jitter and scintillation are not modeled; scattering is the NE2025 (or Cordes et al. 2022) mean, whose real scatter is large (0.76 dex for pulsars, ~1 dex for FRB hosts).

## Reference values (default parameters: extrapolated RFI model, Plan A)

Use these to sanity-check a run. If code cannot run, they give the scale only: say so, and scale thermal noise as 1/√t.

| Case | Continuum full band: total (thermal, confusion), μJy/beam | Beam | HI Zoom A, mJy per 1.7 km/s channel | FRB B2 10σ fluence, all losses (beam peak), Jy ms |
|---|---|---|---|---|
| Survey full depth, COSMOS (150.12, +2.21), 7 epochs | 0.449 (0.369, 0.256); Robust, R = 0.4 | 2.92″ × 2.80″ | 0.147 | 0.076 (0.037) |
| Survey full depth, (180, +60), 7 epochs | 0.402 (0.350, 0.198) | 2.95″ × 2.40″ | 0.140 | 0.073 (0.035) |
| Survey full depth, Galactic plane l = 30° (281.2, −1.1), 7 epochs, full-band T_sys 33.9 K | 0.629 (0.581, 0.241) | 2.92″ × 2.89″ | 0.204 | 0.48 (0.23) |
| Survey single epoch, (180, +60) | 0.947 (0.926, 0.198) | 2.95″ × 2.40″ | 0.371 | 0.073 (0.035) |
| Targeted 1 h, Dec +30 | 0.665 (0.646, 0.158); Natural | 2.94″ × 2.27″ | 0.245 | 0.071 (0.034) |
| Targeted 10 h, Dec +30 | 0.250 (0.233, 0.090); Robust, R = 0.4 | 2.56″ × 1.97″ | 0.078 | 0.072 (0.035) |

Time-domain values use a 21-min track in survey mode, whatever the depth, and the on-source time in targeted mode. With the default pulsar (P 500 ms, W 15 ms, DM half the Galactic value, 0.02 mJy at 1.4 GHz) at (180, +30): targeted search at 953.35 MHz S_min ≈ 3.7 μJy, untargeted B2 ≈ 12 μJy at 1.4 GHz. The default PTA pulsar (1 mJy at 1.4 GHz, P 4 ms, W 0.2 ms, DM 20) there gives σ_TOA ≈ 35 ns with the Pulsar Timing subsystem. In the Galactic plane (l = 30°) scattering and sky temperature raise the B2 FRB limit to 0.48 Jy ms.
