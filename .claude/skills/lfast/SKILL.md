---
name: lfast
description: LFAST (Large Fiber Array Spectroscopic Telescope) exposure time calculator. Load for questions about SNR, exposure time, limiting magnitude, instrument modes (WIYN Bench, CSHELL), fiber choice or array size for LFAST. Package is lfast_etc.
---

# LFAST Exposure Time Calculator (`lfast_etc`)

LFAST is an array of 0.726 m telescopes at Kitt Peak (nominally 20) whose 18 um fibers are merged into
one spectrograph input by a fiber combiner. Two spectrographs are modelled: the **WIYN Bench** (visible,
15 grating/order presets) and **CSHELL** (1.08-1.75 um, R = 18,000 to 43,000, one narrow echelle setting
per exposure). Everything is **per resolution element** (resel); SNR per pixel is lower by about
`sqrt(pixels per resel)` (2.2 on the Bench). The bundled sky is grey time (moon up), so faint-end
numbers are a few tenths of a magnitude pessimistic for dark time.

Tutorials: `lfast/tutorial/01` to `04`; science exercises with solutions in `lfast/tutorial/exercises/`.
Web ETC: <https://simulators.schmidtobservatorysystem.org/lfast/>. Package and docs:
<https://github.com/schmidt-observatories/lfast-etc>.

## Quick pattern

```python
from lfast_etc import LFASTETC, Source, Telescope, Instrument, Sky, list_instruments

etc = LFASTETC("bench_r1800", n_telescopes=20)           # preset + array; list_instruments() for names
src = Source.blackbody(5800, mag=15, band="V")            # shape + one magnitude in one band (Vega default)
res = etc.exptime(src, snr=50)                            # ETCResult, one value per resel
res = etc.snr(src, exptime=600, n_exp=1)                  # the inverse; n_exp = number of reads
res.summary()["exptime"][50]                              # percentile keys are ints: 10, 50, 90
res.at(550.0); res.to_table(); res.plot(); res.plot_noise_budget(); res.plot_spectrum()
etc.limiting_magnitude(src, exptime=900, snr=10, wavelength=(500, 650))   # median over a window
etc.exptime_vs_mag(src, mags, snr=30, wavelength=(500, 650))
etc.snr_grid(src, mags, exptimes, wavelength=(500, 650))  # sensitivity map; plot with lfast_etc.plotting.plot_snr_map
etc.reads_needed(src, 300)                                # reads to keep the peak pixel below 80% of full well
```

## Sources

| constructor | notes |
|---|---|
| `Source.blackbody(teff, mag, band, system="Vega")` | stars, thermal transients |
| `Source.powerlaw(alpha, mag, band, system="AB")` | $F_\nu \propto \nu^\alpha$; afterglows, AGN |
| `Source.flat(mag, band, system="AB")` | flat $F_\nu$ |
| `Source.from_arrays(wl_nm, flux, flux_unit, mag, band)` | `flux_unit` = `"flam"`, `"fnu"` (scaled to `mag`) or `"W/m2/nm"` (absolute; `mag` is then derived) |

`.add_line(center_nm, depth, sigma_nm)` (negative depth = emission), `.with_mag(m)`, `.magnitude(band, system)`,
`.flux(wl)` returns W/m2/nm. Re-feeding `.flux()` through `from_arrays(flux_unit="flam", mag=...)` renormalises
the spectrum, which erases any brightening you added.

## Instruments and the array

- `Instrument.from_preset(name, **overrides)` and `ins.replace(**changes)` to test design choices
  (`read_noise`, `qe`, `slit_throughput`, ...). `LFASTETC(ins, ...)` accepts an `Instrument` or a name.
- CSHELL: restrict to one setting with `lo, hi = ins.setting_window(center_nm)` and
  `LFASTETC(ins, wavelength_min_nm=lo, wavelength_max_nm=hi)`; the full-range ETC gives "what each
  setting would give", not one exposure. Its minimum exposure is 8 s (Fowler read).
- `Telescope(n_telescopes, fiber="18um"|"50um", combine="fiber"|"independent", telescopes_per_input=20)`:
  18 um fibers go through the combiner (signal and sky grow with N, detector noise paid once per input);
  beyond 20 the default is one input per 20-telescope array, co-added; `telescopes_per_input=None` is an
  idealised single combiner. The 50 um fiber bypasses the combiner (SNR grows as sqrt(N)).
  `etc.telescope.n_inputs`, `.total_area_m2`, `.equivalent_diameter_m`.
- `Sky(scale=0.4)` is a crude dark-time estimate (it scales airglow lines too).
- Plot helpers in `lfast_etc.plotting`: `plot_snr_map`, `plot_limiting_magnitude`, `plot_vs_n_telescopes`,
  `equivalent_diameter_axis`.

## Gotchas

- Bins where the throughput is zero (687 nm O2 band, 1.36-1.42 um water band) return NaN; use `np.nanmedian`.
- `res.saturated` / `res.peak_e_per_pixel` flag the bright limit; `n_exp` or `reads_needed` to split reads.
- Bench spectrograph efficiencies are scaled from the WIYN table and the QE is a flat placeholder; the CSHELL
  slit throughput at R = 43k is a placeholder (0.5).
- Classification-style SNR targets at R = 300 convert to per-resel targets by `SNR / sqrt(R / 300)`.
