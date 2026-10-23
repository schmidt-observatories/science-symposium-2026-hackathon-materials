# Changes

## Version 3.1 (October 2026, `etc-chr`)

### Model

- **Pulsar Timing beams carry no digitization loss.** They are formed before the antenna voltages are requantized, so the 4-bit voltage factor 0.988 is removed (`pt_eta` = 1). The targeted beams, formed from the 4-bit voltages, keep it.
- **Self-noise** (`td_self_noise`, on by default). The source's own flux density adds to the beam noise while it is on: S/N × [(1 + x)²(1 − δ) + δ]^−½ per sub-band, with x = S_on/SEFD_beam and δ the on-source fraction (W_eff/P for pulsars; W_eff/(W_eff + T_b) for FRBs). S_min and the fluence limits are now solved numerically. With the defaults this costs < 0.1% for the search pulsar, 1.4–2% for the PTA pulsar and 1–2% at the FRB fluence limit; the FRB loss tables report it.
- **FRB rates use the sky the beams cover.** The 6 × 10⁶ beams per band cover N_b (√3/2) θ², 58–63% of the primary-beam FWHM area at declinations +15° to +50° and 165% at −30°; version 3.0 assumed the full FWHM area. The rate solid angle weights the covered disk by B^α_c, normalized to the FWHM area, and the rate straddle factor is the count-weighted ⟨b^α_c⟩^(1/α_c). At (180°, +30°) the B1 rate falls from 5.5 × 10³ to 3.9 × 10³ yr⁻¹. The headline fluence limit still averages the primary beam over the FWHM disk.
- **4-bit quantization of the imaging products.** Visibilities are correlations of 4-bit voltages, so every imaging product (continuum windows and full band, single pointings, 6-s snapshots, HI and polarization cubes, smoothed images) carries the correlator efficiency η_v4 = 0.988 (`correlator_efficiency`, previously 1). At fixed epochs and weighting, thermal noise rises by 1/0.988 (+1.2%) and confusion, beams and the time-domain products are unchanged; in the tiles whose plan changed, depth, beam and confusion change accordingly (e.g. N02_36 drops from 4 to 3 epochs: 0.526 → 0.591 μJy). The survey plans were rebuilt (22 tile epoch counts and 26 tile weighting choices of 1,716 change; rules and epoch ranges unchanged): Plan A medians 0.40 (Euclid/HSC), 0.45 (Galactic plane), 0.66 μJy (wide), 1.69 × 10⁹ sources above 5σ (was 1.70). At COSMOS the full-depth continuum noise is 0.449 μJy (was 0.445).

### Page

- Spectral line (HI): with smoothing, the four headline tiles quote the smoothed cubes; T_b and 5σ N_HI are separate rows.
- Survey epochs map: Enlarge opens a zoomable, pannable map (hover readout, click to choose a position).
- Product names are the same in the toggles, panels, Advanced settings and guide: Chronoscope: FRBs, Chronoscope: pulsars, Pulsar timing (PTA-like).
- Weighting names are the same everywhere: Natural; Robust, R = 0.46–1.94; Robust, R = 0.4; with optimal or equal summation.
- The FRB panel shows the sky searched and the rate solid angle; self-noise appears in the pulsar, PTA and FRB loss columns.
- The S_min axis label has a proper subscript; the FRB chart's Galactic line, which could never be drawn (the curve starts above that DM), is removed. The usable-band tooltip covers every product.
- Survey plan page: the Euclid/HSC depth is given per plan (7 epochs in Plan A and the reference plan, 6–11 in Plan B, 4–6 in Plan C).

### Documentation

- Methods: §8 reorganized (the system and bandwidth restatements merged; new §8.3 Self-noise; §8.4 Quantization explains why voltage beams lose the same 0.988 as correlations, applies it only to the targeted beams among the voltage beams, and states the ≥ 8-bit beam assumption); §7.2 states ideal Doppler tracking; §4.2 explains the 0.990 (primary beam truncated at 10%); §7.4 sentence fixed; §13.5 defines the DM step; §13.7 describes the rate solid angle.
- User guide: HI smoothing, the enlarged map, self-noise and the FRB beam coverage; the fluence-against-DM chart no longer claims a Galactic line.
- SKILL.md: never add the FRB band rates; quantization and self-noise summary; new output keys; reference values updated.
- Plans A, B and C use exactly 64,250 pointing-epochs; the reference plan uses 63,110 (the note under 3.0 said "each plan").
- Standalone Python documentation: `python/README.md` (installation, command line, API, output fields, parameters, limitations) and `python/COOKBOOK.md` (worked questions, including a transient light curve observed at a given cadence); docstrings for `DSACalculator` and `calculate()`.
- SKILL.md: reference values and integration times (6.3 h for 0.3 μJy, 17.0 h for 0.2 μJy) with the imaging quantization, `--track-s` in targeted mode, `pta` in `--products`, time per position, `polarization.channels[]`, Z(2.0 GHz) = 0.65 (also in the README).
- Methods: §4.1 radiometer equation with η_v4 (the SIP example gives 2.00 μJy without it, 2.02 μJy with it); §8 and §8.4 apply η_v4 to the imaging products; §14 plan table rebuilt. README, user guide, SKILL.md, the cookbook and the DSA specifications page state the imaging quantization. Corrections independent of the model change: the README smoothing example reads 34 mK without subtraction (was 36), SKILL.md 34–87 mK from 1′ to 15′ (was 35–85), and the FRB beam coverage at the pole is about 90% (was 89%).
- Methods reference: Verdi, F. (was M.).
- Package version 3.1.0.

## Version 3.0 (October 2026)

Built on the `etc-chr` branch (version 2.0, which added the Chronoscope pulsar and FRB model).

### Model

- **One system temperature for every product.** The measured T_sys bandpass (Aug 2025, 30 °C) is separated from the RFI it contains, using the Spring Valley occupancy to identify RFI channels (`tools/build_tsys.py`, plot in `tools/tsys_bandpass.png`). The cleaned bandpass (median 21.4 K) now drives the imaging products as well as the pulsar and FRB products; the flat 21.4 K remains available (`tsys_zenith_K=21.4`).
- **One RFI model for every product.** Data loss comes from the RFI profile (Spring Valley model extrapolated by default) for the pulsar and FRB products too. The version 2 rule (2-MHz channels above 1.3 × the median T_sys) is removed: it counted RFI twice and flagged whole 2-MHz channels around narrow lines.
- **Zenith-angle dependence.** Two terms, each a function of frequency and zenith angle, are added to the zenith bandpass (`tools/build_tsys_za.py`, `tsys_za.json`): the simulated spillover of the v3 feed (J. Jonas), smoothed in frequency, and the atmospheric emission at the site from ITU-R P.676/P.835/P.836 (1.2–1.4 K at zenith). Band-averaged, they reproduce the version 1 spillover table, which was total T_sys including the atmosphere, to 0.2 K up to ZA 75°. The version 2 measured curve (`za_model`) is removed. The system breakdown reports `spill_K` and `atm_K`.
- **Pulsar timing (PTA)** is its own product again, after the other products, with its own default pulsar (P 4 ms, W 0.2 ms, DM 20, 1 mJy at 1.4 GHz, α −1.6) and the version 2 calculation. Each of its four beams covers the full band.
- **Aperture efficiency** 0.67 everywhere (the stray 0.66 in the T_sys table is gone with the table, and the separate `td_aperture_efficiency` setting for the pulsar and FRB products is removed).
- **Digitization of intensities.** 2-bit and 4-bit intensities are single quantized streams: S/N factors √0.8825 = 0.939 and √0.988 = 0.994 (Kassam 1977; Manchester et al. 2001). Version 2 applied the correlator efficiencies 0.8825 and 0.988. 4-bit voltages keep 0.988.
- **Untargeted pulsar beams** follow Ravi et al. (2026b): 13.5″ × 930 MHz/ν (13.5″, 8.90″, 6.98″), so that 2 × 10⁵ beams on a hexagonal grid tile the 2.42 deg² unique area of a pointing at 930 MHz. Version 2 used 11.9″, a circular-beam area formula and a 1.65 deg² reference area; its beams covered 78% of the unique area while reporting 104%. The wider beams cost 12% in untargeted S_min.
- **Survey plans rebuilt** with the version 3 T_sys (`tools/allocation.py`): epochs, per-tile weighting choices and the plan summaries. Each plan now uses exactly 64,250 pointing-epochs (the 10-pointing polar-cap tile is sized to fill the budget).
- **HI mass limits** for user-set line widths (default 50, 200 and 500 km/s).

### Page

- Calculate is at the top of the input panel and stays in view while the panel scrolls.
- Clickable **Data products** toggles are back.
- The survey plan selector, the pulsar and FRB inputs, the HI line widths and the T_sys option are under **Advanced settings**. Plan A (DSA-00264 corrected fill) stays the default.
- Product panels stay open when the results are recalculated.
- The summary shows the full-band T_sys and SEFD (unflagged channels of 0.70–2.00 GHz) instead of the values at 1.35 GHz; the command line does the same.
- Clicking a product header opens its panel; only the word Info links to the user guide (the link had stretched across the header).
- Survey image weighting can be set under Advanced settings, overriding each tile's planned choice.
- "How to read this" is now "Info".
- The Observation help no longer describes the time-domain track.
- Sky map: tiles that end at RA 12h were drawn across the whole row, hiding half of each declination tier (the stripes and gaps). Fixed; map labels are legible over the tiles.

### Documentation

- Authors, in the page footer: Gregg Hallinan with Claude Opus 5.5, with input from Vikram Ravi. Package version 3.0.0 (it still read 2.0.0).
- Methods, user guide, README and SKILL.md: version 2 text kept, with only the corrections needed for the changes above; credits restored (Rosero 2026 for the robust-weighting factors and confusion tables; Mauch et al. 2020 for the β_min criterion; the SIP, DSA-00264 and DSA-00207); the FDR baseline is cited as Hallinan et al. (2026), DSA Overview at FDR.
- User guide: the targeted case for the imaging products, the new input locations, Data products and Info.

### Tests and CI

- New checks: bandpass separation, one T_sys across products, the zenith-angle terms against the version 1 table, the PTA pulsar. Two parity cases added (24 cases, ~66,000 values).
- The test workflow runs both test files.
- Removed: `chr_tsys.json`, `tools/build_chr_data.py`, and the stray screenshots `map_default.png` and `smoothed_panel.png`.

### Not changed

- The survey plan rules (Plans A, B, C and the reference plan) are as in version 2.
- The pulsar and FRB calculations are as in version 2, apart from the shared T_sys and RFI model, the separate PTA product, the intensity digitization and the untargeted beams: sidelobe confusion (230 μJy at 1410 MHz) and the FRB model are unchanged.
