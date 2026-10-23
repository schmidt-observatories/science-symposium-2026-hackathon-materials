# DSA Sensitivity Calculator (version 3.1)

Noise, resolution and detection limits for every data product of the Deep Synoptic Array (DSA): continuum, HI, polarization, FRB search, pulsar search and pulsar timing. It covers any position in the Cadenced All-Sky Survey (CASS) or a targeted observation.

The model is implemented twice, in JavaScript and Python, with identical results, and comes in three forms:

| | Where | Use |
|---|---|---|
| **Web page** | `web/` (source), `dist/site/` (built) | Interactive tool for the DSA website |
| **Python package** | `python/dsa_etc/` | Scripts, notebooks and the command line |
| **Claude skill** | `skill/dsa-sensitivity/`, packaged as `dist/dsa-sensitivity-skill.zip` | Ask Claude DSA sensitivity questions; it runs the Python engine |

`tests/parity.test.js` checks that the two agree on about 66,000 output values across 24 test cases (relative tolerance 2×10⁻⁵). CI runs it (`.github/workflows/tests.yml`), and the model checks in `tests/`, on every push.

The web page has a calculator view and four documentation views (User guide, Methods, Survey plan, DSA specifications). The user guide and the methods are written in `docs/user-guide.md` and `docs/model.md` and rendered into the page by `tools/build_web.py`.

## Quick start

**Web page.** Serve `dist/site/` from any web server; it needs no backend. To run it on your own machine, from this folder (Python 3.7 or later, standard library only):

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist/site
```

Open http://127.0.0.1:8000 and stop the server with Ctrl-C in its terminal. `--bind 127.0.0.1` keeps it private to your machine; if port 8000 is taken, use another. The page must be served over http: opening `index.html` as a file (`file://`) cannot load the model tables in `data/`. Serve `dist/site/`, not `web/`: in `web/` the User guide and Methods views show only a placeholder until `tools/build_web.py` renders them. After editing `web/`, `docs/` or the model data, run `python3 tools/build_web.py` and reload.

**Python.**

```bash
pip install ./python
dsa-etc --ra 150.12 --dec 2.21                              # survey products, full depth
dsa-etc --mode targeted --ra 10:00:28.6 --dec +02:12:21 --hours 10 --smooth 30
dsa-etc --ra 266.4 --dec -28.9 --json > gc.json             # full results as JSON
dsa-etc --ra 150.12 --dec 2.21 --rfi measured --variant B   # measured RFI instead of the extrapolated model; Plan B
```

```python
from dsa_etc import DSACalculator
calc = DSACalculator()                      # defaults: measured T_sys bandpass, eta 0.67, 4-bit imaging efficiency 0.988, 1650 x 6.155 m, Galactic noise on
r = calc.calculate(mode="targeted", ra=150.12, dec=2.21, hours=10, smooth_arcsec=30)
r["continuum"]["fc"]["total_uJy"], r["line"]["ZA"]["channels"][0]["sigma_mJy"]
```

Installation, the command-line options and the output fields are in [`python/README.md`](python/README.md); worked answers to common questions (survey depth, integration time, HI limits, transient light curves, FRBs, pulsars) in [`python/COOKBOOK.md`](python/COOKBOOK.md).

`DSACalculator(**overrides)` accepts any key in `dsa_etc.DEFAULTS`, for example `tsys_zenith_K=25`, `extra_loss_percent=10` or `galactic_noise=False`. The RFI profile is the `rfi` argument: the default is the extrapolated Spring Valley model, `rfi=rfi_measured()` gives the measured occupancy, and `rfi=make_rfi_profile(freq_MHz, occupancy)` takes your own.

## Deploying on the DSA website

1. Run `python3 tools/build_web.py`. It writes `dist/site/index.html`, with the CSS and JavaScript inlined, next to `data/` (the model tables, ~0.5 MB) and `img/`.
2. Copy the whole `dist/site/` folder to the web server, for example to `https://<dsa-site>/sensitivity/`. The page loads `data/*.json` with relative URLs, so keep the three items together. It must be served over http(s); `file://` cannot load the data.
3. To embed it in an existing page, either link to it or use `<iframe src="/sensitivity/" style="width:100%;height:2400px;border:0">`.

The only external requests are Google Fonts. Without them the page falls back to system fonts.

## Using it in Claude

`dist/dsa-sensitivity-skill.zip` is a Claude skill: the engine, its data, instructions (`SKILL.md`) and the model description. With code execution enabled, upload the zip as a custom skill ([Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)). Claude then runs the calculator to answer questions such as "What continuum depth does the survey reach at the COSMOS field?" or "How long do I need to reach 0.2 μJy at Dec +30?".

Without code execution, `SKILL.md` on its own still works as a context file: it summarizes the model and lists reference values, though Claude can then only scale from those.

`CLAUDE.md` gives Claude Code the conventions for working on this repository.

## Repository layout

```
web/            page source: index.html, css/app.css, js/dsa-engine.js (engine), js/app.js (UI), img/, data/ (synced copy)
python/         pip-installable package dsa_etc: engine.py, cli.py, data/*.json (the single source of model data); README.md, COOKBOOK.md
docs/model.md   the model: every equation, table and source
tools/          scripts that build the data tables, the survey plan, the site and the skill, plus source figures and the antenna configuration
tests/          cases.json, make_reference.py (Python reference), parity.test.js (JS vs Python), test_engine.py (pytest)
skill/          Claude skill: SKILL.md and scripts/run.py; tools/build_skill.py adds the engine and docs/model.md
dist/           built outputs: site/ (copy to the DSA website) and dsa-sensitivity-skill.zip; artifact/ and skill/ are git-ignored intermediates
CLAUDE.md       notes for Claude Code when working on this repository
```

## The model in one page

The full description, with every equation, is in [`docs/model.md`](docs/model.md).

- **System temperature.** The measured T_sys(ν) at zenith on cold sky, with RFI removed (`tools/build_tsys.py`; median 21.4 K), aperture efficiency 0.67, for every product. Spillover (simulated for the v3 feed) and atmospheric emission (ITU-R P.676) rise with zenith angle and frequency. Galactic synchrotron comes from GSM2008 (de Oliveira-Costa et al. 2008), smoothed by the primary beam at each frequency, and is added above the median |b| > 30° sky.
- **Thermal noise.** σ = SEFD / (η_v4 √(N(N−1) · 2 · Δν · t)), with the unflagged bandwidth Δν = ∫(1 − occupancy) dν and the 4-bit quantization efficiency η_v4 = 0.988 of the correlated voltages.
- **RFI.** The default, *Spring Valley model extrapolated*, keeps the frequency pattern of the site RFI survey but scales it to DSA sensitivity: each channel is treated as having 24× as many transmitters above the flagging threshold, so its clean fraction becomes (1 − p)²⁴. That loses 15% of the band, against 2.8% in the measurement, which remains selectable. Clean channels, including the HI band, stay clean.
- **Survey depth.** Pointings last 21 min on the modified hexagonal grid (θ_hex = 1.667°, θ_row = 1.45°), with mean mosaic weight Z(ν) = 5.35 / 1.44 / 0.65 at 0.7 / 1.35 / 2.0 GHz. At each frequency the epochs of the tiles under the squared primary beam are averaged. Depth therefore varies smoothly across tile boundaries and falls off at the southern edge (δ = −30.45°).
- **Resolution.** The natural-weighted PSF comes from `dsa1650_P305_v2.5.6.8`: 3.03″ E-W × 2.31″/cos ZA N-S at 1.35 GHz, scaling as 1/ν. Hour-angle tracks average the projected snapshot PSFs, which agrees with a full FFT to about 1%. Robust weighting applies per-frequency beam and noise factors from Rosero (2026). The full-band beam is the summation-weighted combination of the ten window beams.
- **Confusion.** The curve of Condon's Universal Confusion Calculator for β_min = 16 (Mauch et al. 2020), as tabulated by Rosero (2026), from the 1.4-GHz source counts of Matthews et al. (2021). Each survey tile uses the imaging and summation weighting that minimizes its final full-band coadd noise. Targeted observations do the same unless a weighting is chosen.
- **Smoothing.** Gaussian convolution is equivalent to a uv taper. The noise per smoothed beam rises by √⟨T²⟩/⟨T⟩, summed over the configuration's baselines: every one shorter than 1 km plus every 13th longer one (within 0.3% of all 1,360,425 at every scale). The smoothed beam is the requested Gaussian; tapering the dirty beam gives a main lobe within 2% of it to 1′ and within 13% to 10′ at 1.35 GHz, degrading beyond ~15′ (see `docs/model.md`). Before smoothing, sources above 5σ in the full-resolution image are subtracted by default; the confusion left is that of the fainter sources, from the same counts as the confusion curve, and it falls with scale in brightness temperature (1′: 2.0 mK total at the default position, against 34 mK without subtraction). `--no-subtract` or `smooth_subtract_sources=False` turns this off.
- **HI.** Zoom B has 960 × 1.017 kHz channels, Zoom A 4192 × 8.138 kHz, and Narrow Line 5600 × 130.2 kHz. Brightness temperature is quoted per channel. N_HI uses the rest-frame T_b over 20 km/s. HI mass limits are 5σ, M_HI = 49.7 D_L² ∫S dν, with Planck 2018 cosmology.
- **Time domain (Chronoscope).** Pulsar and FRB products (`docs/model.md`, Chronoscope sections) use a track centered on transit at the position: the on-source time in targeted mode, 1260 s by default in survey mode.
  - *System:* the same T_sys, Galactic excess, η and RFI profile as the imaging products (B1 99%, B2 100%, B3 98% usable). Sensitivities sum 10-MHz sub-bands.
  - *Losses:* quantization (4-bit voltages 0.988, for beams formed from the correlations and the targeted voltage beams; 2-bit intensities 0.939; 4-bit intensities 0.994; none for the Pulsar Timing beams, formed before requantization), self-noise from the source's on-pulse or on-burst flux density, sidelobe confusion as red noise (230 μJy at 1410 MHz, correlation time scaled by the parallactic-angle rate), scattering from an NE2025 grid (or the Cordes et al. 2022 τ–DM relation).
  - *Chronoscope: pulsars.* One input pulsar (default P 500 ms, W 15 ms, DM half the Galactic value, 0.02 mJy at 1.4 GHz) drives the untargeted search (200,000 tapered beams in B1/B2/B3, 13.5″ × 930 MHz/ν, 1 ms, channels summed ×1/×2/×3, periods 10 ms – 10 s, taper and sidelobe level from the configuration), the targeted search and timing (306.7 MHz centered on 953.35 or 1800 MHz, 0.1 ms, 1 ms – 10 s), S_min(P) curves for every search.
  - *Pulsar timing (PTA-like).* The Pulsar Timing subsystem (four full-band beams, 700–2000 MHz, coherent dedispersion) times its own pulsar (default P 4 ms, W 0.2 ms, DM 20, 1 mJy at 1.4 GHz).
  - *Chronoscope: FRBs.* B1/B2/B3, 1 ms, 122.68 kHz, 6×10⁶ beams; DM budget with NE2025 DM_max, a 20 pc cm⁻³ halo, the Macquart relation and the Verdi et al. (2026) host DM; host scattering; beam straddle, primary-beam average and DM-trial losses; event rates scaled from CHIME/FRB and Parkes (Connor et al. 2026, eq. 2) over the sky the beams cover (N_b √3/2 θ², weighted by B^1.5), not additive across bands; fluence against DM.

## Survey plan (epoch allocation)

The full budget is 5 × 12,850 = 64,250 pointings of 21 min over the 429 tiles of the tiered-tile scheme. `tools/allocation.py` scores four plans with the noise model above; the figure of merit is continuum sources above 5σ in the final full-band coadd.

| Plan | Pointings | Euclid/HSC median noise | Galactic plane | Wide area | Sources > 5σ |
|---|---|---|---|---|---|
| **Plan A: DSA-00264 corrected fill** (default) | 64,250 | 0.40 μJy | 0.45 | 0.66 | 1.69 bn |
| Plan B: uniform Euclid/HSC depth | 64,250 | 0.41 (all tiles 0.40–0.42) | 0.45 | 0.66 | 1.68 bn |
| Plan C: maximum detections | 64,250 | 0.46 | 0.45 | 0.59 | 1.71 bn |
| Reference plan: depth by declination | 63,110 | 0.40 | 0.45 | 0.67 | 1.67 bn |

Plan A keeps 7 epochs in the Euclid/HSC footprint and in the Galactic plane and bulge and uses the whole budget: the reference plan leaves 1,140 pointings unused and sets the wide area by declination alone, while Plan A places the wide-area epochs where they add the most detections, with at least 2 everywhere. Noise values are medians of the final full-band total noise per tile, with the default RFI model.

The Galactic plane and bulge keep at least 7 epochs in every plan, for pulsar confirmation. To change the rules, edit `tools/allocation.py` and re-run it; this rewrites `python/dsa_etc/data/allocation.json`.

## Rebuilding data and running tests

```bash
python3 tools/build_data.py          # RFI profiles (measured and extrapolated), UCC curve, sky-temperature planes, weighting factors
python3 tools/allocation.py          # survey plans (about 1 min; re-evaluates tools/tile_eval.json when the noise model changes)
python3 tools/build_tsys.py          # T_sys bandpass with RFI removed (from tools/inputs/)
python3 tools/build_chr_taper.py     # untargeted-beam taper table (about 15 min on 8 cores)
python3 tools/build_ne2025_grid.py   # NE2025 grid (needs mwprop, mpmath, astropy; see tools/ne2025_build_notes.md)
python3 tools/build_web.py           # dist/site and dist/artifact
python3 tools/build_skill.py         # dist/dsa-sensitivity-skill.zip
python3 tests/make_reference.py && node tests/parity.test.js    # JS vs Python
python3 -m pytest tests/test_engine.py tests/test_chr.py       # model checks
```

`tools/make_tsky.py` rebuilds the GSM2008 planes. It needs `healpy`, `h5py` and `gsm_components.h5` from https://github.com/telegraphic/PyGSM.

## Known limitations

- The default RFI model is an extrapolation of the site survey; the loss at DSA sensitivity has not been measured. `extra_loss_percent` adds further loss.
- The T_sys bandpass is interpolated across ranges dominated by RFI (1170–1300 and 1540–1630 MHz), where it is not measured.
- FRB rates follow eq. 2 of Connor et al. (2026), whose posteriors span about a factor of two. The three FRB bands observe overlapping sky, so their rates are not additive.
- Smoothed continuum subtracts the sources detected at full resolution by default; the confusion left behind is the Poisson noise of the fainter sources, without their clustering or subtraction errors.
- Pulse jitter and scintillation are not modeled; scattering uses the NE2025 (or Cordes et al. 2022) mean.

## References

See the reference list in `docs/model.md`: Hallinan et al. (2026); the SIP; DSA-00264; DSA-00207; Ravi et al. (2026b); Rosero (2026); Mauch et al. (2020); Connor et al. (2026); Cordes et al. (2022); de Oliveira-Costa et al. (2008); Macquart et al. (2020); Matthews et al. (2021); Meyer et al. (2017); Ocker & Cordes (2026); Planck Collaboration (2020); Thompson, Moran & Swenson (2017); Verdi et al. (2026).
