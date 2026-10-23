# dsa-etc

Python package of the DSA Sensitivity Calculator, version 3.1: noise, resolution and detection limits for every Deep Synoptic Array (DSA) data product (continuum, HI, polarization, FRB search, pulsar search, pulsar timing), at a position in the Cadenced All-Sky Survey (CASS) or for a targeted observation. It is the reference implementation of the model behind the DSA Sensitivity Calculator web page; the two agree to a relative precision of 2 × 10⁻⁵.

- Worked answers to common questions: [`COOKBOOK.md`](COOKBOOK.md).
- Every equation, table and source: [`../docs/model.md`](../docs/model.md) (also the Methods page of the web calculator).
- Web calculator, same model in the browser: from the calculator's top folder, `python3 -m http.server 8000 --bind 127.0.0.1 --directory dist/site`, open http://127.0.0.1:8000, stop with Ctrl-C; details in [`../README.md`](../README.md) (Quick start).
- Instrument parameters assume the DSA project baseline at the Final Design Review.

## Install

Requires Python ≥ 3.9 and NumPy ≥ 1.22 (the only dependency). The model tables are package data; no download or network access is needed at run time. From the top folder of the calculator (the one holding `python/`, `docs/` and `web/`):

```bash
python -m pip install ./python                  # install
python -m pip install -e ./python               # editable, for development
python -m pip wheel --no-deps -w wheelhouse ./python   # wheel to share: wheelhouse/dsa_etc-3.1.0-py3-none-any.whl
```

pip leaves a `python/build/` folder; delete it before rebuilding after edits, or the wheel can carry stale files. In a conda environment, use that environment's `python -m pip`. Without installing, run from the `python/` folder (`python -m dsa_etc.cli ...`) or put the folder on `sys.path`.

Check:

```bash
dsa-etc --ra 180 --dec 60 --products continuum
# Continuum full band: total 0.402 uJy/beam (thermal 0.350, confusion 0.198) at 1134 MHz, beam 2.95" x 2.40", ...
```

## Command line

```bash
dsa-etc --ra 150.12 --dec 2.21                                  # survey position, full depth, all products
dsa-etc --ra 10:00:28.6 --dec +02:12:21 --depth single          # one survey epoch
dsa-etc --mode targeted --ra 150.12 --dec 2.21 --hours 10 --smooth 30
dsa-etc --products pulsar --psr-period-ms 3 --psr-width-ms 0.3 --psr-dm 150
dsa-etc --ra 266.4 --dec -28.94 --json > result.json            # every number, as JSON
```

The default output is a one-screen summary; `--json` prints the full result (Section [Results](#results)), with non-finite values as `null`. `dsa-etc --help` lists every option.

| Option | Meaning | Default |
|---|---|---|
| `--ra`, `--dec` | Degrees, or sexagesimal (RA in hours) | 170, +39.57 |
| `--mode` | `survey`: survey mosaic at the position; `targeted`: one pointing centered on it | survey |
| `--depth`, `--epochs N` | Survey depth: `full` (all planned epochs), `single` (one), `custom` (N) | full |
| `--hours H` | Targeted on-source time; tracks are limited to \|HA\| ≤ 2 h and elevation ≥ 20°, longer requests are split over transits | 1 |
| `--weighting` | `auto`, or `IMAGING:SUMMATION` with imaging `natural`, `robust_freq` (R = 0.46–1.94), `robust_0p4` (R = 0.4) and summation `optimal` or `equal` | auto |
| `--smooth ARCSEC` | Also give image products convolved to this circular resolution | off |
| `--no-subtract` | Smoothed continuum: keep the sources above 5σ at full resolution | subtract |
| `--products` | Any of `continuum,line,polarization,frb,pulsar,pta` | all |
| `--rfi` | `default` (Spring Valley model extrapolated, 15% loss), `measured` (2.8%), `none`, or a file of MHz, occupancy | default |
| `--variant` | Survey plan `A`, `B`, `C` or `fig1` (reference plan) | A |
| `--tsys K` | Flat zenith T_sys instead of the measured bandpass | bandpass |
| `--hi-widths` | HI line widths (km/s) for the mass limits | 50,200,500 |
| `--track-s S` | Time-domain track (s), centered on transit; survey mode only (targeted mode uses `--hours`) | 1260 |
| `--psr-*` | Input pulsar: `period-ms`, `width-ms` (intrinsic FWHM), `dm`, `flux-mJy`, `nu-ref`, `alpha` | 500, 15, ½ DM_max, 0.02, 1400, −1.6 |
| `--pta-*` | Pulsar Timing subsystem pulsar, same fields | 4, 0.2, 20, 1, 1400, −1.6 |
| `--targeted-center-MHz` | Targeted pulsar band center (953.35 and 1800 are always reported) | 953.35 |
| `--untargeted-beam-arcsec` | Untargeted search beam FWHM, B1,B2,B3 | 13.5, 8.90, 6.98 |
| `--scattering` | `ne2025` or `cordes22` | ne2025 |
| `--frb-dm`, `--frb-width-ms`, `--frb-max-dm` | FRB DM, intrinsic width, maximum searched DM | 500, 1, 5000 |
| `--set KEY=VALUE` | Override any engine parameter (Section [Parameters](#parameters)) | |

## Python API

```python
from dsa_etc import DSACalculator, DEFAULTS, rfi_measured, rfi_none, make_rfi_profile

calc = DSACalculator()                                     # default model
r = calc.calculate(mode="survey", ra=150.12, dec=2.21)     # dict; same content as --json
r["continuum"]["fc"]["total_uJy"]                          # 0.449
```

`DSACalculator(rfi=None, **params)` fixes the model: `params` are keys of `DEFAULTS`; `rfi` (pass by keyword) is an RFI profile (`None` = default extrapolated profile, `rfi_measured()`, `rfi_none()`, or `make_rfi_profile(freq_MHz, occupancy)` with occupancy as a fraction or percent). Keys not in `DEFAULTS` are accepted and ignored: check the spelling.

`calc.calculate(...)` fixes the observation:

| Argument | Values | Default |
|---|---|---|
| `mode` | `"survey"`, `"targeted"` | `"survey"` |
| `ra`, `dec` | degrees (J2000) | 170.0, 39.57 |
| `depth`, `n_epochs` | survey: `"full"`, `"single"`, `"custom"` with `n_epochs` | `"full"` |
| `hours` | targeted on-source time (h); also the time-domain track in targeted mode | 1.0 |
| `products` | tuple of `"continuum"`, `"line"`, `"polarization"`, `"frb"`, `"pulsar"`, `"pta"` | all |
| `weighting` | `"auto"` or `"imaging:summation"` | `"auto"` |
| `smooth_arcsec` | target resolution (arcsec); 0 = none | 0.0 |
| `variant` | survey plan `"A"`, `"B"`, `"C"`, `"fig1"` | A |

Reuse one calculator for loops. A position takes ~5 ms with `products=("continuum",)` and ~0.1 s with all products.

## Results

All noise values are 1σ; flux densities are per beam; PSF sizes are FWHM in arcsec, PA in degrees. Keys carry their units (`_uJy`, `_mJy`, `_mK`, `_K`, `_s`, `_MHz`, `_Jyms`, `_deg2`). Top level: `inputs`, `observation`, `warnings`, `system`, `weighting`, one entry per requested product, and `time_domain` when `frb`, `pulsar` or `pta` is requested.

| Question | Field |
|---|---|
| Continuum, full band | `continuum.fc`: `thermal_uJy`, `confusion_uJy`, `total_uJy`, `nu_eff_MHz`, `psf` {`bmaj`, `bmin`, `pa`}, `tb_thermal_mK`, `tb_total_mK`, `window_weights` |
| Continuum per 130.2-MHz window | `continuum.windows[]`: `thermal_uJy`, `confusion_uJy`, `total_uJy`, `psf`, `tb_thermal_mK`, `f_lo_MHz`, `f_center_MHz`, `f_hi_MHz`, `bw_usable_MHz`, `sefd_Jy`, `t_eff_s`, `z_mosaic` (survey) |
| One 21-min pointing at the beam center (survey) | `continuum.single_pointing` |
| 6-s snapshots (Stokes I and V) | `continuum.snapshots_6s[]`: four 325.5-MHz sub-bands and the full band |
| Smoothed images | `continuum.smoothed`; `smoothed` inside HI and polarization channels; `continuum.smoothed.subtraction` gives both the subtracted and unsubtracted cases |
| HI | `line.ZB`, `line.ZA`, `line.NL`, each with `channels[]`: `sigma_mJy` per channel, `dv_kms`, `tb_K`, `nhi_5sigma_cm2` (over 20 km/s), `mhi_limits[]` (5σ HI mass) |
| Polarization | `polarization`: `band_qu_sigma_uJy`, `rmsf_fwhm_rad_m2`, `max_scale_rad_m2`, `max_rm_rad_m2`, `channels[]` (four representative channels), `spectrum` ([MHz, σ in μJy] for each 2.6-MHz channel) |
| FRB search | `frb.bands[]` (B1 880–980, B2 1310–1510, B3 1650–1950 MHz): `fluence_min_Jyms` (all losses), `fluence_peak_Jyms` (beam peak), `speak_min_mJy`, `weff`, `losses`, `dm_trials`, `beam_area_deg2`, `beam_coverage`, `loc_ra_1sigma_arcsec`, `loc_dec_1sigma_arcsec`, `rate_per_yr`, `rate_in_track`; `frb.dm_budget`; `frb.curves` (fluence against DM) |
| Pulsar search and timing | `pulsar.untargeted[]` (per band), `pulsar.targeted[]` (953.35, 1800, custom): `snr`, `smin_uJy` (band center), `s1400_min_uJy`, `searched`, `weff`, `losses`; targeted `toa_us`; `pulsar.propagation`; `pulsar.curves` (S_min against period) |
| Pulsar Timing subsystem | `pta`: `snr`, `toa_us`, `s1400_min_uJy`, `losses`, `subbands[]`, `inputs` |
| Time-domain set-up | `time_domain`: `track_s`, `n_transits`, `l_deg`, `b_deg`, `tau_c_s`, `usable_fraction` per band |
| Why the noise is what it is | `system` (T_sys and its parts, SEFD, usable band); `observation` (tile, `epochs_full`, `effective_epochs_1350`, transits); `weighting` (choice; with `weighting="auto"` also `basis` and the `comparison` of all six schemes) |

Always read `warnings`: southern survey edge, tracks split over transits, unobservable positions, smoothing beyond 15′, DMs above the Galactic model.

## Parameters

`DEFAULTS` holds every model parameter (`--set KEY=VALUE` on the command line). The most used:

| Key | Meaning | Default |
|---|---|---|
| `tsys_zenith_K` | `None`: measured T_sys(ν) bandpass at zenith; a number: flat T_sys (K) | None |
| `aperture_efficiency` | η | 0.67 |
| `correlator_efficiency` | 4-bit quantization efficiency of the imaging products (1 = none) | 0.988 |
| `n_ant`, `dish_diameter_m` | array | 1650, 6.155 |
| `extra_loss_percent` | data loss added to the RFI profile | 0 |
| `galactic_noise` | add the GSM2008 Galactic excess to T_sys | True |
| `confusion_beta` | confusion criterion β_min, 16 or 25 | 16 |
| `smooth_subtract_sources`, `subtract_snr` | subtract sources above this S/N before smoothing | True, 5 |
| `el_min_deg`, `ha_max_h` | targeted track limits | 20, 2 |
| `pointing_s`, `td_track_s` | survey pointing; time-domain track in survey mode (s) | 1260, 1260 |
| `hi_widths_kms`, `hi_distances_Mpc`, `hi_redshifts` | HI mass-limit grid | [50, 200, 500], [10, 50, 100], [0.1, 0.25, 0.5, 0.75, 1.0] |
| `psr_*`, `pta_*`, `frb_*` | input pulsar, PTA pulsar and FRB (thresholds `psr_snr`, `pta_snr`, `frb_snr` = 10) | see `DEFAULTS` |
| `td_scattering`, `td_self_noise` | scattering model; self-noise on | `"ne2025"`, True |

## Defaults that matter

State these when quoting results: survey Plan A; the extrapolated RFI model (15% of the band lost); measured T_sys bandpass (median 21.4 K) with η = 0.67; 4-bit quantization efficiency 0.988 on the imaging noise; β_min = 16 confusion. Time-domain products use a track centered on transit: 1260 s in survey mode, the on-source time in targeted mode; default pulsar P = 500 ms, W = 15 ms, DM = ½ the NE2025 Galactic DM, 0.02 mJy at 1.4 GHz; FRB S/N 10, DM 500, 1 ms; NE2025 scattering.

## Limitations

- The default RFI model extrapolates a site survey; the loss at DSA sensitivity is not measured. `extra_loss_percent` adds loss.
- T_sys is interpolated across 1170–1300 and 1540–1630 MHz, where RFI dominates the measurement.
- Robust-weighting factors north of +30° use the +30° values.
- Smoothed continuum after source subtraction excludes source clustering and subtraction errors.
- Scattering is the mean of the chosen model (NE2025, or the Cordes et al. 2022 τ–DM relation with 0.76 dex intrinsic scatter); FRB host scattering has an intrinsic scatter of about 1 dex. Pulse jitter and scintillation are not modeled.
- FRB rates are good to about a factor of two; the three bands observe overlapping sky, so their rates are not additive.
- The survey plan sets the number of epochs per tile, not their dates: survey cadence is not part of the model.
