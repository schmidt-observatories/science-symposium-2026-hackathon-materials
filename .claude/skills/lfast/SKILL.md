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

Tutorials: `lfast/tutorial/01` to `04`; six science exercises with solutions in `lfast/tutorial/exercises/`.
Web ETC: <https://simulators.schmidtobservatorysystem.org/lfast/>. Package and docs:
<https://github.com/schmidt-observatories/lfast-etc>.

## Quick pattern

```python
from lfast_etc import LFASTETC, Source, Telescope, Instrument, Sky, list_instruments
from lfast_etc.plotting import plot_snr_map, plot_limiting_magnitude, plot_vs_n_telescopes, equivalent_diameter_axis

# Build the ETC — n_telescopes shorthand or explicit Telescope + Sky
etc = LFASTETC("bench_r1800", n_telescopes=20)              # preset + array size; list_instruments() for names
etc = LFASTETC("bench_r1800", telescope=Telescope(n_telescopes=20, fiber="18um"), sky=Sky())
etc = LFASTETC(ins, wavelength_min_nm=lo, wavelength_max_nm=hi, n_telescopes=20)  # Instrument object or CSHELL window

# Source
src = Source.blackbody(5800, mag=15, band="V")              # shape + one magnitude in one band (Vega default)
print(src.describe())                                        # one-line description
src.plot(wavelength_nm=np.linspace(380, 1000, 2000))        # plot spectrum with normalising band shaded

# Core ETC calls
res = etc.exptime(src, snr=50)                              # ETCResult — exposure time per resel
res = etc.snr(src, exptime=600, n_exp=1)                    # the inverse; n_exp = number of reads
res.summary()["exptime"][50]                                # percentile keys are ints: 10, 50, 90
res.at(550.0)                                               # dict for one wavelength bin
res.to_table()                                              # astropy Table of all columns (wavelength, snr, exptime, …)
res.exptime                                                 # array of per-resel exposure times (pass back to etc.snr for round trip)
res.snr                                                     # array of per-resel SNRs

# Plots
res.plot()                                                  # SNR or exptime vs wavelength
res.plot_spectrum(seed=1)                                   # noisy realisation overlaid on noiseless signal
res.plot_rates(ax=ax)                                       # star, sky, dark electron rates per pixel per second
res.plot_noise_budget(ax=ax)                                # fraction of variance by term (star, sky, read, dark)

# Sensitivity sweeps
etc.limiting_magnitude(src, exptime=900, snr=10, wavelength=(500, 650))  # median over a wavelength window
etc.exptime_vs_mag(src, mags, snr=30, wavelength=(500, 650))             # array of times vs magnitude array
snr = etc.snr_grid(src, mags, exptimes, wavelength=(500, 650))           # 2-D grid (mags × exptimes)
plot_snr_map(mags, exptimes, snr, band="V", title="...")                 # filled-contour sensitivity map
plot_limiting_magnitude(etc, src, exptimes=[60, 600, 3600], snr=10, ax=ax)
plot_vs_n_telescopes(lambda n: LFASTETC("bench_r1800", n_telescopes=n), src,
                     ns=[1, 2, 5, 10, 20, 50, 100, 200], exptimes=[60, 600, 3600], snr=10, wavelength=(500, 650))
equivalent_diameter_axis(ax)                                # top axis: equivalent single-dish diameter

# Saturation / reads
etc.reads_needed(src, exptime=300)                          # minimum reads to keep peak pixel < 80% full well
res.saturated; res.peak_e_per_pixel                         # per-resel saturation flag and fill level
```

## Sources

| constructor | notes |
|---|---|
| `Source.blackbody(teff, mag, band, system="Vega")` | stars, thermal transients |
| `Source.powerlaw(alpha, mag, band, system="AB")` | $F_\nu \propto \nu^\alpha$; afterglows, AGN |
| `Source.flat(mag, band, system="AB")` | flat $F_\nu$ |
| `Source.from_arrays(wl_nm, flux, flux_unit="flam", mag=m, band="I")` | `flux_unit` = `"flam"` (proportional to $F_\lambda$), `"fnu"`, or `"W/m2/nm"` (absolute; `mag` then derived) |

**Source methods:** `.add_line(center_nm, depth, sigma_nm)` (negative depth = emission line, positive = absorption),
`.with_mag(m)` (copy at new magnitude), `.magnitude(band, system)` (synthetic magnitude in another band),
`.flux(wl)` (W/m²/nm), `.describe()` (one-line string), `.plot(wavelength_nm=...)` (spectrum + normalising band).

Re-feeding `.flux()` through `from_arrays(flux_unit="flam", mag=...)` renormalises the spectrum, which erases
any brightening you added.

## Instruments and the array

```python
list_instruments()                                      # names of all bundled presets
ins = Instrument.from_preset("bench_r1800")             # load a preset
ins = Instrument.from_preset("bench_r1800", read_noise=5.0, qe=0.9)  # preset with overrides
ins2 = ins.replace(read_noise=5.0)                      # copy with changes
ins.setting_window(center_nm)                           # (lo, hi) nm for one CSHELL echelle setting
ins.description; ins.resolving_power; ins.wavelength_min_nm; ins.wavelength_max_nm
ins.efficiency; ins.qe; ins.pixels_per_resel; ins.n_pix; ins.read_noise; ins.dark_current
ins.min_exptime; ins.full_well

etc.plot_throughput()                                   # end-to-end throughput curve vs wavelength
etc.describe()                                          # text summary of ETC, instrument, telescope, sky
```

**CSHELL workflow:** one setting = one narrow echelle order (~3-4 nm wide). Always restrict the wavelength
grid to one setting; the full-range CSHELL ETC gives "what each setting would give" rather than one exposure.
CSHELL minimum exposure is 8 s (Fowler read).

```python
cs = Instrument.from_preset("cshell_r18000")
lo, hi = cs.setting_window(1555.0)
etc = LFASTETC(cs, wavelength_min_nm=lo, wavelength_max_nm=hi, n_telescopes=20)
```

**Telescope / array:**
```python
Telescope(n_telescopes=20, fiber="18um"|"50um", combine="fiber"|"independent", telescopes_per_input=20)
```
- `18um` fiber through the combiner: signal and sky grow with N, detector noise paid once per input.
- `50um` fiber bypasses the combiner: SNR grows as sqrt(N). Couples more sky.
- Beyond 20 telescopes the default is one combiner input per 20-telescope array; `telescopes_per_input=None` is an idealised single combiner.
- `etc.telescope.n_inputs`, `.total_area_m2`, `.equivalent_diameter_m`.

**Sky:** `Sky()` is the bundled grey-time table (moon up, ~V 20.5/sq.arcsec at 550 nm).
`Sky(scale=0.4)` is a crude dark-time estimate (scales airglow lines too). `etc.plot_sky()` shows the
surface brightness and sky electron rate per pixel.

## Noise budget

`res.plot_rates(ax=ax)` — star, sky, dark e⁻/pix/s vs wavelength.
`res.plot_noise_budget(ax=ax)` — fractional variance contributions (star, sky, read noise, dark) vs wavelength.
Use to diagnose whether read noise, sky, or the source dominates for your target.

Classification-style SNR targets at R = 300 convert to per-resel targets as `SNR / sqrt(R / 300)`.

## Gotchas

- Bins where the throughput is zero (687 nm O₂ band, 1.36-1.42 um water band) return NaN; use `np.nanmedian`.
- `res.saturated` / `res.peak_e_per_pixel` flag the bright limit; use `n_exp` or `reads_needed` to split reads.
- Bench spectrograph efficiencies are scaled from the WIYN table and the QE is a flat placeholder; the CSHELL
  slit throughput at R = 21,500 and 43,000 are placeholders (0.5).
- `exptime_vs_mag` and `snr_grid` accept a `mags=` array of floats and `wavelength=(lo, hi)` to get the
  median over a band; omit `wavelength` to get a per-resel result.

## Science exercises

Six exercises in `lfast/tutorial/exercises/` (solutions in `exercises/solutions/`):

| exercise | science case | tutorials used |
|---|---|---|
| ex1_stellar_metallicity | Galactic archaeology — stellar metallicities | 01–04 |
| ex2_transient_classification | TDAMM / kilonovae — transient classification | 01, 03, 04 |
| ex3_stellar_flares | M-dwarf flares at high cadence | 01, 03 |
| ex4_he10830_cshell | He 10830 with CSHELL / exoplanet atmospheres | 02–04 |
| ex5_array_scaling | Array design — 20 / 100 / 200 telescopes | 04 |
| ex6_bring_your_own_target | Open / user science case | all |
