#!/usr/bin/env python
"""Build the LFAST tutorial notebooks, exercises and solutions.

    cd lfast/tutorial
    python build_notebooks.py          # writes the .ipynb files (no outputs)
    jupyter nbconvert --to notebook --execute --inplace 0*.ipynb exercises/solutions/*.ipynb

Exercises and solutions share one definition: a `sol()` cell becomes `# your code here` in the
exercise notebook, and a `bug(broken, fixed)` pair gives the exercise the broken cell and the
solution the fixed one. Same pattern as lazuli/esc/tutorial/build_notebooks.py. The content is
adapted from the example notebooks of the lfast-etc package (scripts/build_notebooks.py and
scripts/build_science_notebooks.py there).
"""
from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = Path(__file__).parent
META = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}}

SETUP = """
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from lfast_etc import LFASTETC, Source, Telescope, Instrument, Sky, list_instruments
from lfast_etc.plotting import plot_snr_map, plot_limiting_magnitude, plot_vs_n_telescopes, equivalent_diameter_axis

plt.rcParams.update({"figure.figsize": (7, 4), "axes.titlesize": 10, "legend.fontsize": 8})
"""

SCALES = '''
# the array sizes compared throughout: replicated in arrays of 20, one spectrograph input per array
SCALES = {20: "nominal 20x (3.2 m eq.)", 200: "10 arrays (10.3 m eq.)", 1720: "86 arrays (30.1 m eq.)"}
NS = np.array([20, 40, 60, 100, 200, 400, 600, 1000, 1720, 2500])

def tel(n, telescopes_per_input=20):
    return Telescope(n_telescopes=int(n), fiber="18um", combine="fiber", telescopes_per_input=telescopes_per_input)

def mark_scales(ax):
    for n in (20, 200, 1720):
        ax.axvline(n, color="0.6", ls="--", lw=0.8)
    ax.set_xscale("log"); ax.set_xlabel("Number of telescopes")
    equivalent_diameter_axis(ax, ticks=(3, 5, 10, 20, 30))
'''


def md(s):
    return new_markdown_cell(s.strip())


def code(s):
    return new_code_cell(s.strip())


def ai(prompt, then=None):
    s = f"> 🤖 **Ask Jupyter AI:** *{prompt.strip()}*"
    if then:
        s += f"\n>\n> {then.strip()}"
    return md(s)


def guess(what):
    return md(f"> ✏️ **Before you run the next cell:** {what.strip()} Write your guess down (or put it in the room poll), then run.")


def write(path, cells):
    nb = new_notebook(cells=cells, metadata=META)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        nbf.write(nb, f)
    print(f"wrote {path.relative_to(HERE)}: {len(cells)} cells")


# =====================================================================================
# Tutorials
# =====================================================================================

T01 = [
    md(r"""
# 01 — lfast_etc as an exposure time calculator

`lfast_etc` is the exposure time calculator (ETC) for **LFAST**, an array of small telescopes at
Kitt Peak: nominally 20 units of 0.726 m, each feeding an 18 um fiber, with the fibers merged into
one spectrograph input by a fiber combiner. Two spectrographs are modelled: the **WIYN Bench**
(visible, 15 grating/order modes) and **CSHELL** (near-infrared, 1.08 to 1.75 um, R up to 43,000).
The throughput model follows Choi et al. (2026, SPIE 14147). The question it answers is *"how long
do I need to expose to reach a given signal-to-noise ratio (SNR) on this target, and what SNR do I
get in a given time?"*

A **web version** of the same calculator, with the same presets and sky, is at
<https://simulators.schmidtobservatorysystem.org/lfast/>: use it for a quick number, and these
notebooks when you want sweeps, plots and your own spectra.

**One idea to hold on to: everything is per resolution element.** The spectrum is cut into bins
one resolution element (resel) wide, $\delta\lambda = \lambda/R$. In each bin the source delivers
$N_*$ electrons per second (summed over the array), the sky $N_{sky}$ electrons per second per pixel,
and the resel is spread over $n_{pix}$ detector pixels. With dark current $D$, read noise $RN$ and a
total exposure $t$ split into $n_{exp}$ reads,

$$\mathrm{SNR} = \frac{N_* t}{\sqrt{N_* t + n_{pix}(N_{sky} + D)\,t + n_{pix}\, n_{exp}\, RN^2}}.$$

Survey papers often quote SNR per pixel, which is lower by about $\sqrt{2.2}$ on the Bench
(the pixels per resel along the dispersion direction): SNR 30 per resel is roughly SNR 20 per pixel.

In this notebook:
1. an ETC: `LFASTETC(preset, n_telescopes)`,
2. a source: `Source.blackbody()`,
3. exposure time for an SNR, and SNR for an exposure time: `exptime()` and `snr()`,
4. reading the result: `plot()`, `summary()`, `at()`, `to_table()`, `plot_spectrum()`.

**Jupyter AI.** These notebooks are written to be run with the Jupyter AI chat open in the side
panel (the sparkle icon). Boxes marked 🤖 suggest things to ask it. It can see the cell you have
selected, so "explain this cell" or pasting a traceback works well. Boxes marked ✏️ ask you to guess
a number before computing it.
"""),
    code(SETUP),
    md(r"""
***
## 1. An ETC

An `LFASTETC` is an instrument preset plus a telescope array plus a sky model. The presets are
TOML files inside the package (notebook 02 lists them); `bench_r1800` is the Bench sample
configuration at R ~ 1800 over 412 to 686 nm. Printing the object tells you what you built:
resolving power, bandpass, pixels per resel, detector numbers, the array, and the sky table.
"""),
    code("""
etc = LFASTETC("bench_r1800", n_telescopes=20)
etc
"""),
    md(r"""
The wavelength grid has one point per resel, about 900 bins between 412 and 686 nm. The preset
stops at 686 nm because the telescope throughput curve has a zero at the 687 nm O$_2$ band.
"""),
    md(r"""
***
## 2. A source

A `Source` is a spectral shape plus one magnitude in one band. The magnitude sets the absolute
scale; the shape comes from a blackbody, a power law, a flat spectrum or your own arrays
(notebook 03). Here: a 5800 K star at V = 15 (Vega), with a 30% deep H$\alpha$ line added.
"""),
    code("""
src = Source.blackbody(5800, mag=15, band="V").add_line(656.3, depth=0.3, sigma_nm=0.05)
print(src.describe(), "| synthetic J =", round(src.magnitude("J"), 2))
src.plot(wavelength_nm=np.linspace(380, 1000, 2000));
"""),
    md(r"""
The shaded box is the normalising band. The synthetic J magnitude comes from integrating the same
spectrum over the J band, which is how you get a magnitude in another band for a target you only
know in one.
"""),
    md(r"""
***
## 3. Exposure time for an SNR

`exptime(source, snr)` returns an `ETCResult` with one value per bin. The plot shows the total
exposure time needed for SNR 50 per resel at each wavelength. Time rises steeply to the blue because
both the throughput and this star's spectrum fall there, and the H$\alpha$ line shows up as a
spike: fewer photons in the line, more time needed.
"""),
    code("""
res = etc.exptime(src, snr=50)
res.plot()
res.summary()
"""),
    md(r"""
`summary()` gives the 10th, 50th and 90th percentiles over the band. The median is the number to
quote if you need one exposure time for the whole spectrum. Pick one wavelength with `at`, or export
every column to an astropy table (`to_table().write("spectrum.csv")` for a file).
"""),
    code("""
print(res.at(550.0))
res.to_table()[:5]
"""),
    guess("the median time for SNR 50 is in the summary above. For SNR 100, is it twice as long, four times, or ten times?"),
    code("""
for snr in (25, 50, 100):
    t = etc.exptime(src, snr=snr)
    print(f"SNR {snr:3d}: median {t.summary()['exptime'][50]:7.1f} s, at 550 nm {t.at(550.0)['exptime']:7.1f} s")
"""),
    md(r"""
Four times, not two: $\mathrm{SNR} \propto \sqrt{t}$ when the star's own photon noise dominates.
Notebook 03 shows where that stops being true.
"""),
    md(r"""
***
## 4. SNR for an exposure time

The inverse question. The dashed line marks SNR 50, so you can see where a 600 s exposure reaches
the target set above. `n_exp` splits the total time into reads, each paying its read noise
(notebook 03).
"""),
    code("""
res = etc.snr(src, exptime=600)
ax = res.plot()
ax.axhline(50, color="0.4", ls="--")
res.summary()["snr"]
"""),
    md(r"""
`simulate` draws one realisation of the extracted spectrum with the per-resel SNR of the result,
and `plot_spectrum` overlays it on the noiseless signal. The H$\alpha$ dip is clearly detected at
this SNR. This is the plot to show when someone asks whether a feature will be visible.
"""),
    code("""
res.plot_spectrum(seed=1);
"""),
    ai("Loop over V = 12 to 20 in steps of 1 for this star and print the median exposure time for SNR 30 per resel in a table, with the time in minutes.",
       "Then ask it why the step from V = 18 to 19 costs more than a factor 2.5."),
    md(r"""
***
## 5. Check yourself

The round trip must close: the SNR computed for the exposure times that `exptime` returned has to
be the target SNR in every bin. If this fails, something in your installation is off.
"""),
    code("""
t = etc.exptime(src, snr=50)
back = etc.snr(src, exptime=t.exptime)
assert np.allclose(back.snr[np.isfinite(back.snr)], 50, rtol=1e-8)
print("round trip OK")
"""),
    md(r"""
***
## Summary

```python
etc = LFASTETC("bench_r1800", n_telescopes=20)        # preset + array (+ default grey-time sky)
src = Source.blackbody(5800, mag=15, band="V")         # shape + one magnitude in one band
res = etc.exptime(src, snr=50)                        # time per resel for SNR 50
res = etc.snr(src, exptime=600, n_exp=1)              # SNR per resel in 600 s
res.plot(); res.summary(); res.at(550.0); res.to_table(); res.plot_spectrum()
```

Next: [02 — instruments, presets and the array](02_instruments_presets_array.ipynb).
"""),
]

T02 = [
    md(r"""
# 02 — Instruments, presets and the array

Every number the ETC uses is an input: the instrument preset, the telescope array, the fiber and
the sky. This notebook is about the first two.

In this notebook:
1. the presets: `list_instruments()` and the mode table,
2. where the photons go: `plot_throughput()`,
3. CSHELL and its narrow echelle settings: `Instrument.setting_window()`,
4. overriding a preset: `Instrument.from_preset(**overrides)` and `replace()`,
5. the array: `Telescope(n_telescopes, fiber, combine, telescopes_per_input)`.
"""),
    code(SETUP),
    md(r"""
***
## 1. The presets

Each instrument mode is a preset: a set of spectrograph and detector parameters loaded by name.
The `bench_*` presets are the WIYN Bench grating and order combinations that reach 400 nm
([the WIYN table](https://www.wiyn.org/Instruments/wiynbench.html)), scaled from the reference
`bench_r1800` mode; the `cshell_*` presets are CSHELL at R = 18,000 (bare fiber), 21,500 and
43,000 (100 um slit). *One setting* is the wavelength range a single exposure covers: the whole
range for the Bench, but only one free spectral range (~2.5e-3 $\lambda$) for CSHELL. `n_pix` is
the extraction aperture per resel (dispersion pixels times the fiber-image height). The CSHELL slit
throughputs at R = 21,500 and 43,000 and the flat QEs are placeholders.
"""),
    code("""
rows = {}
for name in list_instruments():
    ins = Instrument.from_preset(name)
    lo, hi = ins.setting_window(0.5 * (ins.wavelength_min_nm + ins.wavelength_max_nm))
    rows[name] = {"description": ins.description, "R": int(ins.resolving_power),
                  "range (nm)": f"{ins.wavelength_min_nm:.0f}-{ins.wavelength_max_nm:.0f}",
                  "one setting at centre (nm)": round(hi - lo, 1),
                  "efficiency": ins.efficiency, "QE": ins.qe, "pix/resel": ins.pixels_per_resel, "n_pix": ins.n_pix,
                  "read noise (e-)": ins.read_noise, "dark (e-/s/pix)": ins.dark_current,
                  "min exptime (s)": ins.min_exptime}
modes = pd.DataFrame(rows).T.rename_axis("preset")
modes
"""),
    md(r"""
`describe()` on an instrument, a telescope, a sky or the whole ETC prints the same information as
text.
"""),
    code("""
etc = LFASTETC("bench_r1800", n_telescopes=20)
etc.describe()
"""),
    md(r"""
***
## 2. Where the photons go

$K_{opt}$ is the end-to-end telescope throughput for a point source, and it already contains the
fiber injection efficiency $\eta_{fib}$ and the atmospheric extinction at the reference airmass
(that is how Choi et al. define it). The sky fills the fiber uniformly and pays no injection loss,
so it sees $K_{opt}/\eta_{fib}$. The spectrograph efficiency and the detector QE are flat
placeholders in the presets. The black curve is the product of everything, and it is low: a few
percent of the photons that hit the primary mirrors end up as detected electrons.
"""),
    code("""
etc.plot_throughput();
"""),
    ai("Plot the total throughput of every bench_* preset on one axis over its own wavelength range, using LFASTETC(name).plot_throughput or etc.throughputs(). Which mode is the most efficient at 650 nm?"),
    md(r"""
***
## 3. CSHELL: one echelle setting at a time

CSHELL is a single-order echelle: its free spectral range is only ~2.5e-3 $\lambda$, so one setting
covers a narrow window (~3 nm at 1.08 um, ~4 nm at 1.55 um). `Instrument.setting_window(center_nm)`
returns the window of one setting, which is then passed to the ETC to restrict the wavelength grid.
Building the full-range CSHELL ETC is also allowed; its results are then "what each setting would
give", not one exposure.
"""),
    code("""
cs = Instrument.from_preset("cshell_r18000")
lo, hi = cs.setting_window(1555.0)
print(f"One CSHELL setting centred on 1555 nm covers {lo:.1f}-{hi:.1f} nm ({10 * (hi - lo):.0f} A)")

cshell = LFASTETC(cs, wavelength_min_nm=lo, wavelength_max_nm=hi)
kstar = Source.blackbody(4500, mag=9, band="H")
r = cshell.snr(kstar, exptime=300)
print(f"H=9 K star, 300 s: median SNR/resel = {np.nanmedian(r.snr):.1f} | peak = {np.nanmax(r.peak_e_per_pixel):.0f} e-/pix | saturated: {bool(r.saturated.any())}")
"""),
    md(r"""
***
## 4. Overriding a preset

Every preset field can be changed, which is how to test design choices:
`Instrument.from_preset(name, **overrides)` builds a modified preset and `instrument.replace(...)`
copies an existing one with some fields changed. For example, what would a lower-noise detector
buy CSHELL? Here its read noise drops from 22 to 5 e-.
"""),
    guess("CSHELL's read noise drops from 22 to 5 e- on each of the 36 pixels of the extraction aperture. Does the SNR of the H = 9 star above go up by 10%, 50% or a factor 4?"),
    code("""
low_rn = cs.replace(read_noise=5.0)
r2 = LFASTETC(low_rn, wavelength_min_nm=lo, wavelength_max_nm=hi).snr(kstar, exptime=300)
for label, rr, ins in (("preset", r, cs), ("override", r2, low_rn)):
    print(f"{label:8s}: read noise {ins.read_noise:4.0f} e-  ->  median SNR/resel = {np.nanmedian(rr.snr):.1f}")
"""),
    md(r"""
At H = 9 the star gives ~6600 e$^-$ per resel in 300 s, but the read noise, 22 e$^-$ on each of the
36 pixels, adds a variance of ~17,000 e$^{-2}$, more than the star's own photon noise. Lowering it
to 5 e$^-$ raises the SNR by ~50%; for fainter targets the gain is larger still.
"""),
    md(r"""
***
## 5. The array

The number of telescopes is an ordinary parameter. `Telescope` holds the array:

- `n_telescopes`: how many 0.726 m units;
- `fiber`: `"18um"` (goes through the fiber combiner) or `"50um"` (does not);
- `combine`: `"fiber"` (the telescopes of one array feed one spectrograph input: signal and sky
  per pixel grow with $N$, detector noise is paid once per input) or `"independent"` (each
  telescope produces its own spectrum, co-added afterwards, SNR $\propto \sqrt{N}$);
- `telescopes_per_input`: beyond 20 telescopes the ETC assumes one combiner input per 20-telescope
  array (the default), read out separately and co-added; `None` is an idealised single combiner.

`etc.telescope` reports the derived numbers: inputs, total area, equivalent single-dish diameter.
"""),
    code("""
for n in (1, 20, 200):
    t = Telescope(n_telescopes=n)
    print(f"N={n:3d}: {t.n_inputs} input(s), {t.total_area_m2:5.1f} m2, equivalent diameter {t.equivalent_diameter_m:.1f} m")
"""),
    guess("going from 20 to 200 telescopes with the 18 um fiber: does the exposure time for a V = 19 star at SNR 10 drop by a factor 10, more, or less?"),
    code("""
faint = Source.blackbody(5800, mag=19, band="V")
rows = {}
for n in (20, 100, 200):
    row = {}
    for fiber in ("18um", "50um"):
        e = LFASTETC("bench_r1800", telescope=Telescope(n_telescopes=n, fiber=fiber))
        row[f"{fiber} inputs"] = e.telescope.n_inputs
        row[f"{fiber} time (min)"] = round(float(np.nanmedian(e.exptime(faint, snr=10).exptime)) / 60, 1)
    rows[n] = row
pd.DataFrame(rows).T.rename_axis("N telescopes").astype({"18um inputs": int, "50um inputs": int})
"""),
    md(r"""
With the 18 um fiber, 5x more telescopes cut the time by ~4x and 10x by ~6x. Co-adding the inputs
raises the SNR by $\sqrt{n_{inputs}}$ at fixed time; that is worth a factor $n_{inputs}$ in time
only when the sky dominates the noise, and less here because read noise still contributes for this
faint star. The 50 um fiber is slower at every N: it collects more sky per telescope and pays read
noise once per telescope. Notebook 04 maps this out against N.
"""),
    md(r"""
***
## Summary

```python
list_instruments()                                       # the bundled presets
ins = Instrument.from_preset("cshell_r18000", read_noise=5.0)   # a preset with overrides
ins.replace(qe=0.9); ins.setting_window(1555.0)          # a copy; one echelle setting (lo, hi)
etc = LFASTETC(ins, telescope=Telescope(n_telescopes=200, fiber="18um", combine="fiber", telescopes_per_input=20),
               wavelength_min_nm=lo, wavelength_max_nm=hi)
etc.plot_throughput(); etc.describe(); etc.telescope.equivalent_diameter_m
```

Next: [03 — sources, sky and the noise budget](03_sources_sky_noise.ipynb).
"""),
]

T03 = [
    md(r"""
# 03 — Sources, the sky and the noise budget

The SNR equation of notebook 01 has three kinds of terms: the source, the sky, and the detector.
This notebook shows how to describe each, and how to see which one limits you.

In this notebook:
1. sources: blackbody, power law, flat, your own arrays, lines, magnitudes in other bands,
2. the sky: `plot_sky()`, grey versus dark time with `Sky(scale=...)`,
3. the noise budget: `plot_rates()` and `plot_noise_budget()`,
4. reads: `n_exp`, `reads_needed()` and saturation.
"""),
    code(SETUP),
    md(r"""
***
## 1. Sources

`Source.blackbody(teff, mag, band, system)`, `Source.powerlaw(alpha, mag, band, system)` with
$F_\nu \propto \nu^{\alpha}$, `Source.flat(mag)` and `Source.from_arrays(wavelength_nm, flux, ...)`.
The band is the one the magnitude is quoted in; the default system is Vega, and `system="AB"` is
there for transients and AGN. `magnitude(band)` integrates the same spectrum over another band.
"""),
    code("""
sources = {
    "G dwarf, V=15": Source.blackbody(5800, 15, "V"),
    "M dwarf, V=15": Source.blackbody(3300, 15, "V"),
    "afterglow, R=15 (AB)": Source.powerlaw(-0.7, 15, "R", system="AB"),
    "flat F_nu, V=15 (AB)": Source.flat(15, "V"),
}
for label, s in sources.items():
    print(f"{label:22s} {s.describe():45s}  J = {s.magnitude('J'):5.2f}  V(AB) = {s.magnitude('V', 'AB'):5.2f}")
"""),
    md(r"""
Any `(wavelength_nm, flux)` pair works. `flux_unit="flam"` means the array is proportional to
$F_\lambda$ in whatever unit and the magnitude sets the scale; `"fnu"` for an $F_\nu$ array; and
`"W/m2/nm"` for an absolute spectrum, in which case the magnitude is derived rather than given.
Gaussian lines are added with `add_line` and averaged over each resel, so the equivalent width is
preserved: a 0.05 nm wide line with a 30% core on a 0.36 nm resel appears as a resel-wide dip of
about 10%.
"""),
    code("""
wl = np.linspace(380, 1800, 3000)
flux = wl**-2 * (1 + 0.5 * np.exp(-0.5 * ((wl - 850) / 20)**2))   # F_nu-flat continuum with a bump
user = Source.from_arrays(wl, flux, flux_unit="flam", mag=16, band="I").add_line(656.3, depth=0.3, sigma_nm=0.05)
print(user.describe())
r = LFASTETC("bench_r1800").snr(user, 900)
r.plot();
"""),
    md(r"""
***
## 2. The sky

Sky surface brightness per resel on the ETC grid, in AB magnitudes per square arcsecond (left
axis, brighter is up), with the sky electron rate per pixel in the 18 um fiber in grey. The spikes
are airglow lines ([O I] 557.7 nm, Na D near 589 nm, [O I] 630.0 and 636.4 nm).

The bundled SkyCalc table is **grey time**: the moon is up, 45 degrees from the target, and
scattered moonlight is about 60% of the visible sky. Around 550 nm it is V ~ 20.5 mag per square
arcsecond, about a magnitude brighter than dark Kitt Peak (V ~ 21.7 to 22.0 at zenith, Neugent &
Massey 2010). Faint-end results are therefore pessimistic by a few tenths of a magnitude for dark time.
"""),
    code("""
etc = LFASTETC("bench_r1800", n_telescopes=20)
etc.plot_sky();
"""),
    md(r"""
`Sky(scale=0.4)` is a crude dark-time estimate. It scales the airglow lines too, which is wrong in
detail; generate a proper SkyCalc table for real planning.
"""),
    guess("how much deeper (in magnitudes, for SNR 10 in 15 minutes) is dark time than the bundled grey sky for a G star?"),
    code("""
gstar = Source.blackbody(5800, 0, "V")
for label, sky in (("grey (bundled)", Sky()), ("dark (x0.4)", Sky(scale=0.4))):
    e = LFASTETC("bench_r1800", n_telescopes=20, sky=sky)
    print(f"{label:15s}: V_lim(SNR=10, 900 s) = {e.limiting_magnitude(gstar, 900, 10, wavelength=(500, 650)):.2f}")
"""),
    md(r"""
***
## 3. The noise budget

Two views of the same budget. `plot_rates` shows star, sky and dark electrons per pixel per second;
`plot_noise_budget` shows the fraction of the variance each term contributes for this exposure.
For a V = 15 star in 600 s the star dominates almost everywhere and the sky takes over only at the
bright airglow lines.
"""),
    code("""
src = Source.blackbody(5800, 15, "V")
res = etc.snr(src, exptime=600)
fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
res.plot_rates(ax=axes[0])
res.plot_noise_budget(ax=axes[1])
axes[0].set_xlabel("");
"""),
    guess("same plot for a V = 18 star. At which wavelengths does the sky take over, and does read noise matter anywhere?"),
    code("""
res18 = etc.snr(src.with_mag(18), exptime=600)
fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
res18.plot_rates(ax=axes[0])
res18.plot_noise_budget(ax=axes[1])
axes[0].set_xlabel("");
"""),
    ai("Make a plot of the fraction of the variance from the star, the sky and the detector at 550 nm as a function of V magnitude from 10 to 22, in a 600 s exposure, using res.to_table() columns. Mark the magnitude where the sky overtakes the star."),
    md(r"""
***
## 4. Reads and saturation

`n_exp` splits the exposure into reads. Each read pays the read noise again, so the cost depends on
how much read noise matters: nothing for a bright star, a lot for a faint one. `reads_needed`
returns the smallest number of reads that keeps the brightest pixel below a fraction (`margin`,
default 0.8) of the full well; `peak_e_per_pixel` and `saturated` in the result say where the limit
is.
"""),
    guess("splitting a 600 s exposure into 10 reads: how much SNR does it cost at V = 15, and at V = 19?"),
    code("""
for mag in (15, 19):
    s = src.with_mag(mag)
    one = np.nanmedian(etc.snr(s, 600, n_exp=1).snr)
    ten = np.nanmedian(etc.snr(s, 600, n_exp=10).snr)
    print(f"V = {mag}: median SNR/resel {one:6.1f} in one read, {ten:6.1f} in ten ({100 * (1 - ten / one):.0f}% lower)")
"""),
    code("""
for mag in (4, 6, 8, 10):
    s = Source.blackbody(5800, mag, "V")
    n = etc.reads_needed(s, 60)
    r = etc.snr(s, 60, n_exp=n)
    print(f"V = {mag:2d}, 60 s: {n:3d} read(s), peak {np.nanmax(r.peak_e_per_pixel):8.0f} e-/pix of {etc.instrument.full_well:.0f}, saturated: {bool(r.saturated.any())}")
"""),
    md(r"""
***
## Summary

```python
Source.blackbody(5800, 15, "V"); Source.powerlaw(-0.7, 19, "R", system="AB"); Source.flat(15)
Source.from_arrays(wl, flux, flux_unit="flam", mag=16, band="I").add_line(656.3, 0.3, 0.05)
src.magnitude("J"); src.with_mag(18)
LFASTETC("bench_r1800", sky=Sky(scale=0.4)); etc.plot_sky()
res.plot_rates(); res.plot_noise_budget()
etc.snr(src, 600, n_exp=10); etc.reads_needed(src, 60); res.peak_e_per_pixel; res.saturated
```

Next: [04 — sensitivity maps and array scaling](04_sensitivity_maps_array_scaling.ipynb).
"""),
]

T04 = [
    md(r"""
# 04 — Sensitivity maps and array scaling

The source electron rate scales exactly as $10^{-0.4 m}$ with magnitude, so the ETC can evaluate
the SNR on a (magnitude, exposure time) grid without redoing the spectrum each time, and it can
solve the limiting magnitude for a given SNR and exposure analytically, bin by bin. This notebook
builds those maps for both instruments and then asks how they move with the number of telescopes,
which is still an open design choice for LFAST.

In this notebook:
1. `snr_grid()` and `plot_snr_map()`,
2. `limiting_magnitude()` and `plot_limiting_magnitude()`,
3. `exptime_vs_mag()`,
4. scaling the array: `Telescope(...)` sweeps, `plot_vs_n_telescopes()`, `equivalent_diameter_axis()`.
"""),
    code(SETUP),
    md(r"""
***
## 1. SNR versus magnitude and exposure time

The map is the median SNR over 500 to 650 nm. Read it along a horizontal line to see how the SNR
grows with time at fixed magnitude, or along a contour to see how much fainter a longer exposure
reaches. The magnitude of the source object does not matter here; the grid supplies it.
"""),
    code("""
bench = LFASTETC("bench_r1800", n_telescopes=20)
gstar = Source.blackbody(5800, mag=0, band="V")
mags = np.linspace(8, 22, 57)
exps = np.logspace(0, 4, 49)                     # 1 s to about 3 h
snr = bench.snr_grid(gstar, mags, exps, wavelength=(500, 650))
plot_snr_map(mags, exps, snr, band="V", title="Bench R~1800, 20 telescopes, median SNR/resel 500-650 nm");
"""),
    md(r"""
Where the contours are straight lines of slope $-2.5$ mag per decade of time the measurement is
photon limited by the star. They bend at the faint end where sky and read noise enter and the gain
per unit time slows down. Following the SNR = 10 contour, a V ~ 18.9 star reaches it in 15 min; the
gain drops from 2.5 mag per decade at the bright end to 1.5 mag between 1000 and 10,000 s.

Same map for CSHELL in its R = 18,000 mode, for one echelle setting centred on 1.555 um. The grid
starts at 8 s because that is the shortest Fowler-sampled read for which the quoted read noise
applies.
"""),
    code("""
cs = Instrument.from_preset("cshell_r18000")
lo, hi = cs.setting_window(1555.0)
cshell = LFASTETC(cs, n_telescopes=20, wavelength_min_nm=lo, wavelength_max_nm=hi)
kstar = Source.blackbody(4500, mag=0, band="H")
mags_h = np.linspace(2, 16, 57)
exps_h = exps[exps >= cshell.instrument.min_exptime]
snr_h = cshell.snr_grid(kstar, mags_h, exps_h, wavelength=(lo, hi))
plot_snr_map(mags_h, exps_h, snr_h, band="H", levels=(3, 10, 30, 100, 300),
             title=f"CSHELL R=18k, 20 telescopes, one setting {lo:.1f}-{hi:.1f} nm");
"""),
    md(r"""
***
## 2. Limiting magnitude

`limiting_magnitude(source, exptime, snr, wavelength)` solves for the magnitude that reaches the
target SNR; with a `(lo, hi)` window it is the median over that window, with a single wavelength
it is that bin. `plot_limiting_magnitude` does it bin by bin across the band. For the Bench the
curve follows the throughput: deepest in the red, about a magnitude shallower at 420 nm. The spikes
are the night-sky emission lines.
"""),
    code("""
print(f"Bench, SNR 10 in 900 s, median over 500-650 nm: V < {bench.limiting_magnitude(gstar, 900, 10, wavelength=(500, 650)):.2f}")
fig, ax = plt.subplots(figsize=(9, 4))
plot_limiting_magnitude(bench, gstar, exptimes=[60, 600, 3600], snr=10, ax=ax)
ax.set_title("Bench, SNR=10 per resel, 20 telescopes");
"""),
    code("""
fig, ax = plt.subplots(figsize=(9, 4))
full = LFASTETC("cshell_r18000", n_telescopes=20)   # the whole CSHELL range, many echelle settings
plot_limiting_magnitude(full, kstar, exptimes=[60, 600, 3600], snr=10, ax=ax)
ax.set_title("CSHELL R=18k, SNR=10 per resel, 20 telescopes");
"""),
    md(r"""
Each wavelength in the CSHELL plot is what one echelle setting would give; the curve is not a
single exposure. The gaps between 1.36 and 1.42 um are bins where $K_{opt}$ is zero in the water
band, and the ETC returns NaN there rather than a number.
"""),
    md(r"""
***
## 3. Exposure time versus magnitude at fixed SNR

The most compact way to read off survey speed. The dashed line is one hour.
"""),
    code("""
mags = np.linspace(8, 21, 53)
fig, ax = plt.subplots(figsize=(7, 4.5))
for snr_t in (10, 30, 100):
    t = bench.exptime_vs_mag(gstar, mags, snr=snr_t, wavelength=(500, 650))
    ax.plot(mags, t / 60, label=f"SNR={snr_t}")
ax.set_yscale("log"); ax.set_xlabel("V magnitude"); ax.set_ylabel("Exposure time (min)")
ax.axhline(60, color="0.4", ls="--"); ax.legend(); ax.set_title("Bench R~1800, 20 telescopes, 5800 K star");
"""),
    md(r"""
***
## 4. Scaling the number of telescopes

The 18 um fibers go through a 20-to-1 combiner. Within one array both $N_*$ and $N_{sky}$ grow with
$N$ while the detector terms do not, so the gain is better than $\sqrt{N}$ whenever read noise or
dark current matter. Beyond 20 telescopes the ETC assumes one combiner input per 20 telescopes,
co-added incoherently (`telescopes_per_input=20`); the dotted curve is an idealised single
combiner for comparison. The 50 um fiber bypasses the combiner, so each telescope yields a spectrum
and the SNR grows as $\sqrt{N}$, but it couples about twice as much point-source light and admits
a 7.7 times larger patch of sky. The nominal 20-telescope prototype and the 100- and 200-telescope
upgrade options are marked; `equivalent_diameter_axis` adds the single-dish diameter with the same
collecting area on top.
"""),
    guess("at 900 s and SNR 10, how many magnitudes deeper is 200 telescopes than 20 for the Bench? (The collecting area alone would give 2.5 mag.)"),
    code("""
ns = np.array([1, 2, 4, 8, 12, 16, 20, 30, 40, 60, 80, 100, 150, 200])
configs = (("18um", "fiber", 20), ("18um", "fiber", None), ("18um", "independent", 20), ("50um", "independent", 20))
fig, ax = plt.subplots(figsize=(7, 4.5))
for fiber, combine, tpi in configs:
    lim = [LFASTETC("bench_r1800", telescope=Telescope(n_telescopes=int(n), fiber=fiber, combine=combine, telescopes_per_input=tpi))
           .limiting_magnitude(gstar, exptime=900, snr=10, wavelength=(500, 650)) for n in ns]
    ax.plot(ns, lim, marker="o", ms=3, ls=":" if tpi is None else "-",
            label=f"{fiber}, {combine}" + (" (ideal single combiner)" if tpi is None else ""))
ax.set_xscale("log"); ax.invert_yaxis()
ax.set_xlabel("Number of telescopes"); ax.set_ylabel("Limiting V (SNR=10/resel, 900 s)")
for n, txt, ha in ((20, "nominal 20", "left"), (100, "100", "left"), (200, "200", "right")):
    ax.axvline(n, color="0.4", ls="--"); ax.text(n * 1.05 if ha == "left" else n / 1.05, ax.get_ylim()[1] + 0.3, txt, fontsize=8, ha=ha)
ax.legend(); ax.set_title("Bench R~1800, median over 500-650 nm")
equivalent_diameter_axis(ax);
"""),
    md(r"""
The same comparison for CSHELL, where the 22 e$^-$ read noise and the 0.5 e$^-$/s dark current,
both over a 36-pixel extraction aperture, are large, shows the fiber combiner mattering more.
"""),
    code("""
fig, ax = plt.subplots(figsize=(7, 4.5))
for fiber, combine in (("18um", "fiber"), ("18um", "independent"), ("50um", "independent")):
    lim = [LFASTETC("cshell_r18000", telescope=Telescope(n_telescopes=int(n), fiber=fiber, combine=combine),
                    wavelength_min_nm=lo, wavelength_max_nm=hi).limiting_magnitude(kstar, 900, 10)
           for n in ns]
    ax.plot(ns, lim, marker="o", ms=3, label=f"{fiber}, {combine}")
ax.set_xscale("log"); ax.invert_yaxis()
ax.set_xlabel("Number of telescopes"); ax.set_ylabel("Limiting H (SNR=10/resel, 900 s)")
for n in (20, 100, 200):
    ax.axvline(n, color="0.4", ls="--")
ax.legend(); ax.set_title(f"CSHELL R=18k, one setting {lo:.1f}-{hi:.1f} nm")
equivalent_diameter_axis(ax);
"""),
    md(r"""
For the common case of one configuration and several exposure times there is a one-call helper,
`plot_vs_n_telescopes`. You pass a function that builds the ETC for a given $N$, so you decide the
fiber, the combiner and the bandpass.
"""),
    code("""
plot_vs_n_telescopes(lambda n: LFASTETC("bench_r1800", n_telescopes=n), gstar,
                     ns=[1, 2, 5, 10, 20, 50, 100, 200], exptimes=[60, 600, 3600], snr=10, wavelength=(500, 650));
"""),
    ai("Redo the Bench sensitivity map for a 3500 K star normalised in I instead of V. Which contour moves most, and why does the normalising band matter here?",
       "Then: add n_exp=10 to snr_grid. Where on the map does the extra read noise show?"),
    md(r"""
***
## Summary

```python
snr = etc.snr_grid(src, mags, exptimes, wavelength=(500, 650)); plot_snr_map(mags, exptimes, snr, band="V")
etc.limiting_magnitude(src, exptime=900, snr=10, wavelength=(500, 650))
plot_limiting_magnitude(etc, src, exptimes=[60, 600, 3600], snr=10)
etc.exptime_vs_mag(src, mags, snr=30, wavelength=(500, 650))
plot_vs_n_telescopes(lambda n: LFASTETC("bench_r1800", n_telescopes=n), src, ns, exptimes, snr=10)
equivalent_diameter_axis(ax)
```

Now pick an exercise from the [README](README.md).
"""),
]

# =====================================================================================
# Exercises
# =====================================================================================


class Sol(str):
    """Solution code; replaced by a placeholder in the exercise notebook."""


def sol(s):
    return Sol(s.strip())


class Bug(tuple):
    """(broken, fixed) code: the exercise gets the broken cell, the solution the fixed one."""


def bug(broken, fixed):
    return Bug((broken.strip(), fixed.strip()))


def exercise(stem, title, covers, stars, intro, cells, setup=SETUP):
    header = md(f"# {title}\n\n*Covers notebooks {covers}. Difficulty: {stars}*\n\n{intro.strip()}")
    ex, so = [header, code(setup)], [header, code(setup)]
    for c in cells:
        if isinstance(c, Sol):
            ex.append(code("# your code here")); so.append(code(c))
        elif isinstance(c, Bug):
            ex.append(code(c[0])); so.append(code(c[1]))
        else:
            ex.append(c); so.append(c)
    feedback = md("""
***
## Share-back and feedback

Bring back **one plot and one number** to the share-back board, and the observing decision you draw
from them.

> 🤖 **Ask Jupyter AI:** *Draft a GitHub issue for schmidt-observatories/lfast-etc describing one thing I
> found missing, confusing or wrong in this exercise, with a minimal code example.*
""")
    write(HERE / "exercises" / f"{stem}.ipynb", ex + [feedback])
    write(HERE / "exercises" / "solutions" / f"{stem}_solution.ipynb", so + [feedback])


EX1 = [
    md(r"""
At R ~ 1800 the Bench sample configuration is LAMOST-like, so LAMOST tells us what to expect:
[Fe/H] to about 0.1 dex for FGK stars once the SNR per pixel exceeds 20 to 30 (Wu et al. 2014;
Luo et al. 2015), and about 0.05 dex only with data-driven methods trained on high-resolution
labels, which need SNR > 50 (Ho et al. 2017; Xiang et al. 2019). The ETC works per resel
(2.2 pixels), so SNR 20 per pixel is about 30 per resel. The metallicity information sits in the
Mg b region, 500 to 560 nm.

LFAST is not a multiplexed survey instrument: all telescopes point at one star. Its niche is
depth on individually selected targets (Gaia XP metal-poor candidates, stream members, faint halo
giants). The questions are *how faint* and *how fast*.
"""),
    code("""
bench = LFASTETC("bench_r1800", n_telescopes=20)
stars = {"G dwarf 5800 K": 5800, "K dwarf 4500 K": 4500, "M dwarf 3500 K": 3500}
mags = np.linspace(9, 20, 45)
WINDOW = (500, 560)          # the Mg b region
OVERHEAD = 600.0             # s per target: slew, acquisition, read-out
"""),
    md(r"""
### 1.1 — Exposure time to reach the SNR thresholds

Plot the exposure time versus V for the three stars, in two panels: SNR 30 (about 0.1 dex) and
SNR 75 (what the 0.05 dex methods need), with the 15 minute and one hour lines marked. Why do the
three curves lie almost on top of each other?
"""),
    sol("""
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
for ax, snr_t in zip(axes, (30, 75)):
    for label, teff in stars.items():
        t = bench.exptime_vs_mag(Source.blackbody(teff, 0, "V"), mags, snr=snr_t, wavelength=WINDOW)
        ax.plot(mags, t / 60, label=label)
    ax.set_yscale("log"); ax.set_xlabel("V magnitude"); ax.set_title(f"SNR = {snr_t} per resel, 500-560 nm")
    for h, txt in ((15, "15 min"), (60, "1 h")):
        ax.axhline(h, color="0.4", ls="--"); ax.text(mags[0], h * 1.1, txt, fontsize=8, color="0.4")
axes[0].set_ylabel("Exposure time (min)"); axes[0].legend()
# The window sits inside the V band, where the magnitude pins the flux, so spectral type only enters
# through the slope of the SED across 60 nm. Normalise in I instead and the curves separate.
"""),
    md(r"""
### 1.2 — Survey depth

Make a table of the limiting V (median SNR over 500 to 560 nm) for both SNR targets and all three
stars, in 5, 15 and 60 minutes. Read it as: *with this exposure, every star brighter than this V
gets a metallicity at this precision.* How does the depth grow with time, and what does that say
about which noise term dominates?
"""),
    guess("with 20 telescopes, how faint a G dwarf reaches SNR 30 per resel in 15 minutes? V = 15, 17 or 19?"),
    sol("""
exps = (300, 900, 3600)
depth = pd.DataFrame({(label.split()[0], f"SNR {snr_t}"): [bench.limiting_magnitude(Source.blackbody(teff, 0, "V"), t, snr_t, wavelength=WINDOW) for t in exps]
                      for label, teff in stars.items() for snr_t in (30, 75)},
                     index=pd.Index([t // 60 for t in exps], name="exposure (min)"))
depth.round(1)
# 5 -> 15 min (x3) gains ~1.1 mag, 15 -> 60 min (x4) ~1.25 mag: between the source-limited
# 2.5 log10(t) (1.2, 1.5 mag) and the sky-limited 1.25 log10(t) (0.6, 0.75), closer to the former.
"""),
    md(r"""
### 1.3 — Distance reach by tracer

Turn the one-hour SNR 30 limit into a distance (ignoring extinction) for a G dwarf ($M_V$ = +4.8),
a K giant ($M_V$ = +0.5) and a star at the tip of the red giant branch ($M_V$ = -2.5). Use the
5800 K blackbody for the dwarf and 4500 K for the giants.
"""),
    sol("""
tracers = {"G dwarf (M_V=+4.8)": (5800, 4.8), "K giant (M_V=+0.5)": (4500, 0.5), "RGB tip (M_V=-2.5)": (4500, -2.5)}
for label, (teff, MV) in tracers.items():
    vlim = bench.limiting_magnitude(Source.blackbody(teff, 0, "V"), 3600, 30, wavelength=WINDOW)
    print(f"{label:22s}: V < {vlim:.1f}  ->  {10**((vlim - MV + 5) / 5) / 1000:6.1f} kpc")
# Dwarfs probe the thick disc; giants reach into the halo.
"""),
    md(r"""
### 1.4 — Survey throughput

One star at a time, so the number of stars per 8 hour night is
$N = 8\,\mathrm{h} / (t_{exp}(V) + t_{overhead})$. Plot it for G dwarfs at SNR 30 with the 10 minute
overhead. Where does the overhead stop mattering, and what does that mean for a bigger array?
"""),
    sol("""
t = bench.exptime_vs_mag(Source.blackbody(5800, 0, "V"), mags, snr=30, wavelength=WINDOW)
n_per_night = 8 * 3600 / (t + OVERHEAD)
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(mags, n_per_night)
ax.set_yscale("log"); ax.set_xlabel("V magnitude"); ax.set_ylabel("Stars per 8 h night (SNR=30)")
ax.set_title(f"G dwarfs, Bench R~1800, 20 telescopes, {OVERHEAD / 60:.0f} min overhead")
# Bright stars are overhead-limited: at most 48 per night whatever the array size. The exposure
# equals the overhead at V ~ 16.5; only fainter than that does a larger array help.
"""),
    md(r"""
### 1.5 — Gaia XP candidates

Gaia XP photometric metallicities (to G < 17.65) contain about 2 x 10$^5$ candidates with
[Fe/H] < -2 (Xylakis-Dornbusch et al. 2024). How long does the nominal array take to confirm a
K giant candidate at V = 16, 17.5, 19 and 20 at SNR 30? Which of those could a season of nights
get through?
"""),
    sol("""
giant = Source.blackbody(4500, 0, "V")
for m, ti in zip((16, 17.5, 19, 20), bench.exptime_vs_mag(giant, [16, 17.5, 19, 20], snr=30, wavelength=WINDOW)):
    print(f"V = {m:4.1f}: {ti / 60:6.1f} min  ({8 * 3600 / (ti + OVERHEAD):5.1f} per night)")
"""),
    ai("Move the metric window to the G band (425 to 435 nm), the window that matters for carbon-enhanced metal-poor stars, and redo the depth table. Then switch to the bench_1200_28p7_o2 preset (R ~ 7600 around 400 nm): does the higher resolution pay for itself in exposure time at fixed SNR per resel?"),
]

EX2 = [
    md(r"""
Time-domain and multi-messenger follow-up with a spectrograph is first about **classification**: a
low-SNR spectrum, rebinned to R ~ 100 to 300, that tells a SN Ia from a SN II or a TDE from an AGN
flare. The question for LFAST is *what is the faint limit to classify a transient in a given
exposure?* All times are on-target integration.

Assumptions:
* Classification needs SNR ~ 5 per **rebinned** element at R_bin = 300 across 450 to 650 nm
  (SEDM: Blagorodnova et al. 2018; 4MOST/TiDES: Swann et al. 2019). Co-adding $k = R/R_{bin}$
  adjacent resels of equal SNR raises the SNR by $\sqrt{k}$.
* 60 minutes is the practical upper limit for one classification spectrum.
* Transient SEDs as blackbodies: a hot 25,000 K source (young SN II / TDE), 10,000 K (SN Ia near
  peak) and 3500 K (kilonova at ~3 d, luminous red nova), with magnitudes in Cousins R (Vega); a
  GRB afterglow as a power law $F_\nu \propto \nu^{-0.7}$ in AB.
* Kilonova: AT2017gfo-like, r = 17.3 at 0.5 d at 40 Mpc, fading 0.95 mag per day, cooling from
  10,000 K at 0.5 d to 5000 K at 1.5 d and 2500 K at 5.5 d (Drout et al. 2017; Shappee et al. 2017).
* Grey-time sky, a fair average for target-of-opportunity work where the moon phase is not chosen.

**One cell in this exercise is broken on purpose.** The numbers it produces are wrong by a
constant factor; find out which one and why before you go on.
"""),
    bug("""
N_TEL = 20
WINDOW = (450, 650)          # nm, classification window
R_BIN = 300                  # rebinned resolution for classification
SNR_CLASS = 5                # SNR per R_BIN element needed to classify
EXP_MAX = 3600               # s, practical upper limit for one classification spectrum
BAND = "R"                   # magnitudes in Cousins R (~ SDSS r)

bench = LFASTETC("bench_r1800", n_telescopes=N_TEL, wavelength_min_nm=WINDOW[0], wavelength_max_nm=WINDOW[1])
snr_resel_needed = SNR_CLASS                   # SNR per native resel that gives SNR_CLASS at R_BIN
print(f"need SNR {snr_resel_needed:.2f} per resel")

seds = {"hot 25,000 K": Source.blackbody(25000, 0, BAND),
        "SN Ia 10,000 K": Source.blackbody(10000, 0, BAND),
        "red 3500 K": Source.blackbody(3500, 0, BAND),
        "afterglow (AB)": Source.powerlaw(-0.7, 0, BAND, system="AB")}
""", """
N_TEL = 20
WINDOW = (450, 650)          # nm, classification window
R_BIN = 300                  # rebinned resolution for classification
SNR_CLASS = 5                # SNR per R_BIN element needed to classify
EXP_MAX = 3600               # s, practical upper limit for one classification spectrum
BAND = "R"                   # magnitudes in Cousins R (~ SDSS r)

bench = LFASTETC("bench_r1800", n_telescopes=N_TEL, wavelength_min_nm=WINDOW[0], wavelength_max_nm=WINDOW[1])
k = bench.instrument.resolving_power / R_BIN   # resels per rebinned element (6)
snr_resel_needed = SNR_CLASS / np.sqrt(k)      # SNR per native resel that gives SNR_CLASS at R_BIN
print(f"{k:.1f} resels per R={R_BIN} bin -> need SNR {snr_resel_needed:.2f} per resel")
# The broken cell asked for SNR 5 per native resel, six times more signal than the R=300 bin needs:
# every exposure time was ~6x too long and every depth ~1 mag too shallow.

seds = {"hot 25,000 K": Source.blackbody(25000, 0, BAND),
        "SN Ia 10,000 K": Source.blackbody(10000, 0, BAND),
        "red 3500 K": Source.blackbody(3500, 0, BAND),
        "afterglow (AB)": Source.powerlaw(-0.7, 0, BAND, system="AB")}
"""),
    md(r"""
### 2.1 — Exposure time to classify versus magnitude

Plot the integration time to reach the classification SNR against R magnitude for the four SEDs,
with the 5, 30 and 60 minute lines. Mark the Argus Array detection depths, the discovery engine
LFAST would follow up: **g = 20.0** single-epoch (1 minute) and **g = 21.5** 15-minute co-add
(5 sigma, dark time; Law et al. 2022). How long does a SN Ia at each Argus depth take?
"""),
    guess("a SN Ia-like transient at the Argus single-epoch depth (R ~ 20): classified in 1 minute, 7 minutes or 40 minutes?"),
    sol("""
mags = np.linspace(14, 22, 41)
fig, ax = plt.subplots(figsize=(7.5, 4.5))
for label, src in seds.items():
    t = bench.exptime_vs_mag(src, mags, snr=snr_resel_needed, wavelength=WINDOW)
    ax.plot(mags, t / 60, label=label, ls="--" if "afterglow" in label else "-")
ax.set_yscale("log"); ax.set_xlabel(f"{BAND} magnitude"); ax.set_ylabel("Exposure time (min)")
for tmin, ls in ((60, "-"), (30, "--"), (5, ":")):
    ax.axhline(tmin, color="0.4", ls=ls, lw=0.8); ax.text(14.1, tmin * 1.1, f"{tmin} min", fontsize=8, color="0.4")
ARGUS = {"Argus 1 min": 20.0, "Argus 15 min": 21.5}
for txt, mag in ARGUS.items():
    ax.axvline(mag, color="0.5", ls="-.", lw=0.8); ax.text(mag - 0.08, 0.5, txt, fontsize=8, color="0.4", rotation=90, ha="right", va="top")
ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.52))
ax.set_title(f"Classification: SNR={SNR_CLASS} per R={R_BIN} bin, {WINDOW[0]}-{WINDOW[1]} nm, {N_TEL} telescopes")

t_ref = bench.exptime_vs_mag(seds["SN Ia 10,000 K"], list(ARGUS.values()), snr=snr_resel_needed, wavelength=WINDOW)
print("SN Ia: " + ";  ".join(f"at {txt} depth ({mag}): {t / 60:.1f} min" for (txt, mag), t in zip(ARGUS.items(), t_ref)))
# ~7 min at the single-epoch depth, ~1 h at the co-add depth: right at the classification budget.
"""),
    md(r"""
### 2.2 — Classification depth versus exposure time

Table of the faintest R magnitude that can be classified in 5, 15, 30 and 60 minutes, per SED.
Why does doubling from 30 to 60 minutes gain only ~0.4 mag?
"""),
    sol("""
exps = (300, 900, 1800, 3600)
depth = pd.DataFrame({label: [bench.limiting_magnitude(src, t, snr_resel_needed, wavelength=WINDOW) for t in exps]
                      for label, src in seds.items()},
                     index=pd.Index([t // 60 for t in exps], name="exposure (min)"))
depth.round(1)
# Background-limited scaling: 1.25 log10(2) = 0.38 mag. Sky and detector noise dominate at these
# magnitudes, so SNR grows as sqrt(t). The next half magnitude would cost another ~1.5 h.
"""),
    md(r"""
### 2.3 — How many days after merger can a kilonova still be classified?

For an AT2017gfo-like kilonova at 40, 100 and 200 Mpc, plot the exposure needed for a
classification spectrum against days after merger (0.5 to 5 d), and print the last day on which
it fits in 30 and 60 minutes. 40 Mpc is GW170817; the LIGO binary-neutron-star range is 150 to
170 Mpc in O4 and 225 to 295 Mpc planned for O5.
"""),
    sol("""
days = np.linspace(0.5, 5, 91)
def kn_mag(d, D_Mpc):
    return 17.3 + 0.95 * (d - 0.5) + 5 * np.log10(D_Mpc / 40)
def kn_teff(d):
    return np.interp(d, [0.5, 1.5, 5.5], [10000, 5000, 2500])

fig, ax = plt.subplots(figsize=(7.5, 4.5))
for D in (40, 100, 200):
    t_needed = np.array([bench.exptime_vs_mag(Source.blackbody(kn_teff(d), 0, BAND), [kn_mag(d, D)],
                                              snr=snr_resel_needed, wavelength=WINDOW)[0] for d in days]) / 60
    ax.plot(days, t_needed, label=f"{D} Mpc")
    last = {tmin: days[t_needed <= tmin].max() if (t_needed <= tmin).any() else np.nan for tmin in (30, 60)}
    print(f"{D:3d} Mpc: classifiable until {last[30]:.1f} d (30 min) / {last[60]:.1f} d (60 min)")
ax.axhline(60, color="0.4", lw=0.8); ax.text(0.6, 66, "60 min", fontsize=8, color="0.4")
ax.axhline(30, color="0.4", ls="--", lw=0.8); ax.text(0.6, 33, "30 min", fontsize=8, color="0.4")
ax.set_yscale("log"); ax.set_ylim(0.2, 1e3); ax.set_xlabel("Days after merger"); ax.set_ylabel("Exposure for classification (min)")
ax.legend(title="distance"); ax.set_title(f"AT2017gfo-like kilonova, Bench, {N_TEL} telescopes")
# The kilonova fades ~1 mag/day and cools, moving its flux redward of the 450-650 nm window.
"""),
    md(r"""
### 2.4 — The array-size trade

With 20, 100 and 200 telescopes (one combiner input per 20, the default), tabulate the 60 minute
classification depth for each SED and the gain over 20. At the faint end every noise term grows
with the number of inputs, so the expected gain is $1.25\log_{10}(N/20)$: 0.9 mag for 100 and
1.25 mag for 200. For the kilonova, what does 1.25 mag mean in distance?
"""),
    sol("""
rows = {}
for n in (20, 100, 200):
    e = LFASTETC("bench_r1800", n_telescopes=n, wavelength_min_nm=WINDOW[0], wavelength_max_nm=WINDOW[1])
    rows[n] = {"D_eq (m)": e.telescope.equivalent_diameter_m, "inputs": e.telescope.n_inputs,
               **{label: e.limiting_magnitude(src, EXP_MAX, snr_resel_needed, wavelength=WINDOW) for label, src in seds.items()}}
trade = pd.DataFrame(rows).T.rename_axis("N telescopes")
trade["inputs"] = trade["inputs"].astype(int)
trade["gain vs N=20 (mag)"] = trade["SN Ia 10,000 K"] - trade.loc[20, "SN Ia 10,000 K"]
trade.round(2)
# 1.25 mag is a factor 10**(1.25/5) = 1.8 in distance: 200 telescopes reach at 200 Mpc what 20 reach at ~110 Mpc.
"""),
    ai("Add a GRB afterglow section: for afterglows at R = 17, 19 and 21 (AB) one hour after the burst, fading as t^-1, plot the exposure needed for SNR 10 per native resel (an absorption-line redshift) against the delay from 15 minutes to 48 hours. Which one is still reachable within an hour's integration after 10 hours?",
       "Then: use Sky(scale=0.4) for dark time and redo the kilonova plot. Does the 200 Mpc curve cross the 30 minute line?"),
]

EX3 = [
    md(r"""
A fiber-combined array reads out once per exposure regardless of the number of telescopes, so
second-to-minute cadence spectroscopy of bright-ish stars is a natural niche: H$\alpha$, H$\beta$
and He I D3 during M-dwarf flares, chromospheric variability of exoplanet hosts, accretion
variability in young stars.

Assumptions: SNR 20 per resel in the continuum next to H$\alpha$ (650 to 660 nm) as the threshold
for a usable line profile per exposure; cadences of 10, 60 and 600 s; M dwarfs as 3300 K blackbodies
normalised in V, with $M_V$ = +10 (M3), +13 (M5) and +16 (M8) for the distance reach; grey sky.

**One cell in this exercise is broken on purpose.** It runs without error and makes a plausible
plot, but the physics is wrong. Find it.
"""),
    code("""
WINDOW = (650, 660); SNR_LINE = 20
mdwarf = Source.blackbody(3300, 0, "V")
bench = LFASTETC("bench_r1800", n_telescopes=20)
"""),
    md(r"""
### 3.1 — Faintest M dwarf with SNR 20 per resel at H-alpha

For cadences of 10, 60 and 600 s, what is the limiting V? Then the distance reach at 10 s cadence
for an M3, M5 and M8 dwarf.
"""),
    guess("at 10 s cadence with 20 telescopes, how faint an M dwarf still gives SNR 20 per resel next to H-alpha? V = 12, 14 or 16?"),
    sol("""
lims = {exp: bench.limiting_magnitude(mdwarf, exp, SNR_LINE, wavelength=WINDOW) for exp in (10, 60, 600)}
for exp, v in lims.items():
    print(f"{exp:4d} s cadence: V < {v:.1f}")
for label, MV in {"M3 (M_V=+10)": 10, "M5 (M_V=+13)": 13, "M8 (M_V=+16)": 16}.items():
    print(f"{label:14s} at 10 s cadence: {10**((lims[10] - MV + 5) / 5):6.1f} pc")
"""),
    md(r"""
### 3.2 — A flare spectrum at 10 s cadence

During a large flare the blue continuum brightens by magnitudes while H$\alpha$ goes into strong
emission. Model the flare as the quiescent 3300 K star (V = 12) plus a 10,000 K blackbody component
that doubles the V flux (a 0.75 mag flare), with H$\alpha$ in emission (depth -3 on a 0.1 nm
Gaussian). The cell below builds the flare source. Check `flare.mag` before you plot.
"""),
    bug("""
wl = np.linspace(380, 1000, 4000)
quiet = Source.blackbody(3300, 12, "V")
hot = Source.blackbody(10000, 12, "V")
flare_flux = quiet.flux(wl) + hot.flux(wl)
flare = Source.from_arrays(wl, flare_flux, flux_unit="flam", mag=12, band="V").add_line(656.3, -3.0, 0.1)
print(f"quiescent V = {quiet.mag:.2f}, flare V = {flare.mag:.2f}")
""", """
wl = np.linspace(380, 1000, 4000)
quiet = Source.blackbody(3300, 12, "V")
hot = Source.blackbody(10000, 12, "V")
flare_flux = quiet.flux(wl) + hot.flux(wl)
# flux() returns an absolute spectrum in W/m2/nm: pass it as such and let the magnitude follow.
# With flux_unit="flam" and mag=12 the sum was renormalised back to V = 12, erasing the flare.
flare = Source.from_arrays(wl, flare_flux, flux_unit="W/m2/nm", band="V").add_line(656.3, -3.0, 0.1)
print(f"quiescent V = {quiet.mag:.2f}, flare V = {flare.mag:.2f}")
"""),
    md(r"""
Plot the SNR per resel across the band in 10 s for the star quiet and in flare, for 20 and 200
telescopes. Which end of the spectrum gains the most, and why is that the end that matters?
"""),
    sol("""
fig, ax = plt.subplots(figsize=(9, 4))
for n, ls in ((20, "-"), (200, "--")):
    e = LFASTETC("bench_r1800", n_telescopes=n)
    ax.plot(e.wavelength, e.snr(quiet, 10).snr, ls=ls, color="C0", lw=0.8, label=f"quiescent, N={n}")
    ax.plot(e.wavelength, e.snr(flare, 10).snr, ls=ls, color="C3", lw=0.8, label=f"flare, N={n}")
ax.set_yscale("log"); ax.set_xlabel("Wavelength (nm)"); ax.set_ylabel("SNR per resel in 10 s")
ax.set_title(f"V=12 M dwarf, flare V={flare.mag:.2f}"); ax.legend(ncol=2)
# The blue end gains the most: that is where the Balmer jump and the hot continuum live.
"""),
    md(r"""
### 3.3 — Exoplanet-host monitoring and the bright limit

SNR per resel at H$\alpha$ in a 60 s exposure for a V = 8 K dwarf (4800 K), a V = 11 and a V = 14
M dwarf, with 20 telescopes. Which one saturates the STA1 full well, and how many reads does
`reads_needed` say it needs?
"""),
    sol("""
hosts = {"V=8 K dwarf": (4800, 8), "V=11 M dwarf": (3300, 11), "V=14 M dwarf": (3300, 14)}
for label, (teff, mag) in hosts.items():
    s = Source.blackbody(teff, mag, "V")
    r = bench.snr(s, 60)
    n = bench.reads_needed(s, 60)
    rn = bench.snr(s, 60, n_exp=n)
    print(f"{label:14s} 60 s at H-alpha: SNR={r.at(656.3)['snr']:6.0f}" + (f" (saturated! {n} reads -> SNR={rn.at(656.3)['snr']:.0f})" if r.saturated.any() else ""))
"""),
    ai("Plot the limiting V for SNR 20 at H-alpha against the number of telescopes (1 to 200, log axis) for the 10 s and 60 s cadences, with equivalent_diameter_axis on top. At what array size does a V = 13 M dwarf come within reach at 10 s?"),
]

EX4 = [
    md(r"""
CSHELL at R = 43,000 (100 um slit) or R = 18,000 (bare fiber) covers 1.08 to 1.75 um, but its free
spectral range is only about 2.5e-3 of the wavelength: one setting is about 27 A wide at 1.08 um.
That rules out cross-correlation over hundreds of molecular lines in one shot and points to single
strong features. The best one is the metastable He I triplet at 1083.3 nm, the standard probe of
escaping atmospheres (Spake et al. 2018; Allart et al. 2018), with transit depths of 0.5 to 5% over
a ~1 A core for hot Jupiters and warm Neptunes.

Assumptions:
* He 10830 setting 1081 to 1086 nm (vacuum), at R = 43,000 and 18,000.
* Detection metric: the excess absorption averaged over `n_core` resels centred on the planet line
  (3 resels at R = 43k, 2 at R = 18k), in transit minus out of transit with equal in and out
  exposure: $\sigma = \sqrt{2}/(\mathrm{SNR}_{resel}\sqrt{n_{core}\,N_{exp,in}})$ per transit.
* The planet line is a Gaussian of 0.7 A FWHM; the literature depth is the peak depth, so the
  measured depth is the mean of that profile over the `n_core` window (`core_fraction`).
* 300 s exposures, split into reads only if the brightest pixel would saturate (`reads_needed`);
  2 h transit (24 in-transit exposures) and the same out of transit.
* Not included, each a 20 to 40% effect: the stellar He I line core, the OH airglow doublet at
  10832 and 10834 A, the water tellurics, the array-wide line spread function. The slit throughput
  at R = 43k is a placeholder (0.5).
"""),
    code("""
from scipy.special import erf
N_TEL = 20
EXP = 300.0                  # s per exposure
T_TRANSIT = 2 * 3600         # s in transit (same out of transit)
LINE_FWHM_A = 0.7            # He 10830 planet line FWHM
HE_NM = 1083.3               # vacuum
N_CORE = {"cshell_r43000": 3, "cshell_r18000": 2}   # resels averaged over the line core
N_IN = int(T_TRANSIT / EXP)  # in-transit exposures per transit

def he_setup(name, n_tel=N_TEL):
    return LFASTETC(name, n_telescopes=n_tel, wavelength_min_nm=1081, wavelength_max_nm=1086)

def core_fraction(etc, n_core):
    \"\"\"Mean of a Gaussian line (peak 1, FWHM LINE_FWHM_A) over n_core resels centred on it.\"\"\"
    sigma = LINE_FWHM_A / 2.3548 / 10          # nm
    half = n_core * HE_NM / etc.instrument.resolving_power / 2
    return sigma * np.sqrt(2 * np.pi) / (2 * half) * erf(half / (sigma * np.sqrt(2)))

targets = {  # (Teff [K], 2MASS J, peak He 10830 depth): well-known detections
    "HD 189733 b": (5000, 6.07, 0.0104),   # Salz et al. 2018
    "WASP-69 b":   (4715, 8.03, 0.0359),   # Nortmann et al. 2018
    "HAT-P-11 b":  (4780, 7.61, 0.0108),   # Allart et al. 2018
    "GJ 3470 b":   (3600, 8.79, 0.015),    # Palle et al. 2020
    "WASP-107 b":  (4430, 9.38, 0.0554),   # Allart et al. 2019
}
"""),
    md(r"""
### 4.1 — Per-transit precision and significance

Write `precision_per_transit(etc, src)` returning the sigma on the measured depth per transit, the
continuum SNR per resel per 300 s exposure at the He line, and the reads per exposure; and
`significance(etc, src, depth)`, the detection significance of a line of peak depth `depth`
(remember `core_fraction`). Print both for the five known detections in each CSHELL mode. Does
any host need more than one read in 300 s?
"""),
    sol("""
def precision_per_transit(etc, src, exp=EXP, n_in=N_IN):
    n_exp = etc.reads_needed(src, exp)
    snr = etc.snr(src, exp, n_exp=n_exp).at(HE_NM)["snr"]
    n_core = N_CORE[etc.instrument.name]
    return np.sqrt(2) / (snr * np.sqrt(n_core * n_in)), snr, n_exp

def significance(etc, src, depth):
    sig = precision_per_transit(etc, src)[0]
    return depth * core_fraction(etc, N_CORE[etc.instrument.name]) / sig

for mode in ("cshell_r43000", "cshell_r18000"):
    etc = he_setup(mode)
    print(f"--- {etc.instrument.description} | core fraction {core_fraction(etc, N_CORE[mode]):.2f} over {N_CORE[mode]} resels ---")
    for name, (teff, jmag, depth) in targets.items():
        src = Source.blackbody(teff, jmag, "J")
        sig, snr, n_exp = precision_per_transit(etc, src)
        print(f"{name:12s} J={jmag:5.2f}: SNR/resel/300s={snr:6.1f} (reads={n_exp})  "
              f"sigma={100 * sig:.3f}% per transit  ->  {significance(etc, src, depth):5.1f} sigma on a {100 * depth:.1f}% line")
"""),
    md(r"""
### 4.2 — Significance versus host J magnitude

Plot the per-transit significance of a 0.5% and a 2% line against host J (4 to 13, 4800 K host),
solid for R = 43k and dashed for R = 18k, with the 5 sigma line. Which resolution wins, and why?
"""),
    guess("R = 43,000 resolves the 0.7 A line and R = 18,000 does not. Which mode detects a 1% line around a J = 9 host at higher significance?"),
    sol("""
jmags = np.linspace(4, 13, 37)
fig, ax = plt.subplots(figsize=(7.5, 4.5))
for mode, ls in (("cshell_r43000", "-"), ("cshell_r18000", "--")):
    etc = he_setup(mode)
    for depth, color in ((0.005, "C0"), (0.02, "C1")):
        s = np.array([significance(etc, Source.blackbody(4800, j, "J"), depth) for j in jmags])
        ax.plot(jmags, s, ls=ls, color=color, label=f"R={etc.instrument.resolving_power:.0f}, depth {100 * depth:g}%")
ax.axhline(5, color="0.4", ls="--"); ax.text(4.1, 5.5, "5 sigma", fontsize=8, color="0.4")
ax.set_yscale("log"); ax.set_xlabel("Host J magnitude"); ax.set_ylabel("He 10830 significance per transit")
ax.legend(ncol=2); ax.set_title(f"CSHELL, {N_TEL} telescopes, 2 h transit, 300 s exposures, 4800 K host")
# R = 18k wins at every magnitude: its resels collect 2.4x more light and it pays no slit loss,
# which outweighs the smaller fraction of the line depth it retains (0.59 vs 0.79).
# Much of the gap is the placeholder slit throughput of 0.5 at R = 43k.
"""),
    md(r"""
### 4.3 — Why the combiner matters here

CSHELL's 22 e$^-$ read noise and 0.5 e$^-$/s dark current are large. With all fibers combined the
detector terms are paid once per exposure; with independent spectra they are paid $N$ times. Print
the per-transit precision for a J = 9 host at R = 43k for N = 5, 10, 20, 40, 80 telescopes, for
`combine="fiber"` and `"independent"`.
"""),
    sol("""
src = Source.blackbody(4800, 9.0, "J")
for combine in ("fiber", "independent"):
    row = []
    for n in (5, 10, 20, 40, 80):
        etc = LFASTETC("cshell_r43000", telescope=Telescope(n, "18um", combine=combine), wavelength_min_nm=1081, wavelength_max_nm=1086)
        row.append(f"N={n}: {100 * precision_per_transit(etc, src)[0]:.2f}%")
    print(f"{combine:12s} " + "  ".join(row))
"""),
    md(r"""
### 4.4 — Paschen-beta accretion monitoring

T Tauri stars in Taurus (140 pc) have J ~ 8 to 12. For a 10% line-flux measurement of Pa-beta
(1282.2 nm, EW ~ 5 A) we need SNR 30 per resel at R = 18k. How long per epoch for J = 8, 10, 12
and 14 (4000 K blackbody) with the nominal array?
"""),
    sol("""
pab = LFASTETC("cshell_r18000", n_telescopes=20, wavelength_min_nm=1280, wavelength_max_nm=1284)
t = pab.exptime_vs_mag(Source.blackbody(4000, 0, "J"), [8, 10, 12, 14], snr=30, wavelength=1282.2)
print("  ".join(f"J={m}: {ti:7.0f} s" for m, ti in zip((8, 10, 12, 14), t)))
"""),
    ai("Set slit_throughput=1.0 on the R = 43k preset with Instrument.from_preset('cshell_r43000', slit_throughput=1.0) and redo the significance plot: the best case once the slit loss is measured. Then change EXP to 60 s: bright hosts no longer need several reads, but each exposure pays read noise against less signal. Which host magnitude is the break-even point?"),
]

EX5 = [
    md(r"""
LFAST is replicated in arrays of 20 unit telescopes. The nominal Kitt Peak array (20 x 0.726 m,
8.3 m$^2$) has the collecting area of a 3.2 m telescope; 10 arrays (200 telescopes) match a
10.3 m aperture and 86 arrays (1720 telescopes) a 30.1 m aperture. This exercise builds the
scaling model and produces the headline sensitivity curves against the array size.

How arrays combine in the ETC: each 20-to-1 fiber combiner feeds one spectrograph input. Within an
array, star and sky electrons both scale with the number of telescopes while detector noise is
incurred once; beyond 20, one input per array, co-added incoherently, so the SNR grows as
$\sqrt{n_{arrays}}$ on top of the single-array value. An idealised single combiner
(`telescopes_per_input=None`) is shown dotted where it matters.

This is a photon-budget scaling and nothing more: it assumes the spectrographs scale with the
arrays, that the per-array throughput stays at the Choi et al. (2026) values, and that sky
subtraction and fiber-combiner stability do not limit faint-end performance. Multiplexing is not
modelled.
"""),
    code(SCALES),
    md(r"""
### 5.1 — Equivalent apertures

A table of arrays, collecting area, equivalent diameter and number of spectrograph inputs for every
N in `NS`.
"""),
    sol("""
apertures = pd.DataFrame(
    {int(n): {"Arrays": -(-int(n) // 20), "Area (m2)": tel(int(n)).total_area_m2,
              "D_eq (m)": tel(int(n)).equivalent_diameter_m, "Spectrographs": tel(int(n)).n_inputs}
     for n in NS}).T.rename_axis("N telescopes")
apertures.astype({"Arrays": int, "Spectrographs": int}).round(1)
"""),
    md(r"""
### 5.2 — Limiting magnitude versus array size, both instruments

Three cases: the Bench in V over 500 to 650 nm, CSHELL at R = 18k in H for one setting at 1.555 um,
and CSHELL at R = 43k in J at the He 10830 line. Plot the SNR 10 limiting magnitude against N for
60, 900 and 3600 s, solid for one combiner per 20 telescopes and dotted for the idealised single
combiner. Where is the gap between them largest, and why?
"""),
    guess("which instrument gains more from a single combiner feeding all 1720 telescopes into one spectrograph: the Bench or CSHELL?"),
    sol("""
gstar = Source.blackbody(5800, 0, "V")
kstar = Source.blackbody(4500, 0, "H")
cs_lo, cs_hi = Instrument.from_preset("cshell_r18000").setting_window(1555.0)
cases = {
    "Bench R~1800, V, 500-650 nm": ("bench_r1800", gstar, dict(), (500, 650)),
    "CSHELL R=18k, H, one setting at 1.555 um": ("cshell_r18000", kstar, dict(wavelength_min_nm=cs_lo, wavelength_max_nm=cs_hi), None),
    "CSHELL R=43k, J, He 10830": ("cshell_r43000", Source.blackbody(4800, 0, "J"), dict(wavelength_min_nm=1081, wavelength_max_nm=1086), 1083.3),
}
fig, axes = plt.subplots(1, 3, figsize=(13, 4))
summary = {}
for ax, (label, (preset, src, kw, win)) in zip(axes, cases.items()):
    for exp, color in ((60, "C2"), (900, "C0"), (3600, "C1")):
        lim = [LFASTETC(preset, telescope=tel(int(n)), **kw).limiting_magnitude(src, exp, 10, wavelength=win) for n in NS]
        ideal = [LFASTETC(preset, telescope=tel(int(n), telescopes_per_input=None), **kw).limiting_magnitude(src, exp, 10, wavelength=win) for n in NS]
        ax.plot(NS, lim, marker="o", ms=3, color=color, label=f"{exp} s")
        ax.plot(NS, ideal, ls=":", color=color, lw=1)
        summary[(label, exp)] = dict(zip(NS, lim))
    ax.set_ylabel(f"Limiting {src.band} (SNR=10/resel)")
    ax.set_title(label + " (dotted: ideal single combiner)", fontsize=8); ax.legend()
    mark_scales(ax)
plt.tight_layout()
lim_table = pd.DataFrame({(label, exp): {f"N={n}": d[n] for n in SCALES} for (label, exp), d in summary.items()}).T
lim_table.index.names = ["case (SNR=10 per resel)", "exposure (s)"]
lim_table["gain 20->200"] = lim_table["N=200"] - lim_table["N=20"]
lim_table["gain 20->1720"] = lim_table["N=1720"] - lim_table["N=20"]
lim_table.astype(float).round(2)
# The gap is largest for CSHELL: a single combiner would pay its noisy detector once instead of
# once per array (~1.2 mag deeper at 200 and ~2.3 mag at 1720 in 15 min). For the Bench it is ~0.1 mag.
"""),
    md(r"""
### 5.3 — The regimes

At fixed SNR the required exposure time scales as $1/N$ in every regime once the array count grows
(incoherent co-add of inputs), and faster than $1/N$ inside a single array when detector noise
matters. Plot the exposure time relative to the 20-telescope value against N for a G star at V = 12,
18 and 21, with the $1/N$ line. Which regime is each magnitude in?
"""),
    sol("""
fig, ax = plt.subplots(figsize=(7, 4.3))
for mag, label in ((12, "V=12 (source-limited)"), (18, "V=18"), (21, "V=21 (sky-limited)")):
    t = [LFASTETC("bench_r1800", telescope=tel(int(n))).exptime_vs_mag(gstar, [mag], snr=10, wavelength=(500, 650))[0] for n in NS]
    ax.plot(NS, np.array(t) / t[0], marker="o", ms=3, label=label)
ax.plot(NS, 20 / NS, color="0.4", ls="--", label="1/N")
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("Number of telescopes"); ax.set_ylabel("Exposure time relative to 20x")
ax.legend(); ax.set_title("Bench, SNR=10 per resel, 5800 K")
# The magnitude gain at fixed time is 2.5 log10(N) when source limited and 1.25 log10(N) when
# background limited, so the faint-end gain from 20 to 1720 telescopes is between 2.4 and 4.8 mag.
"""),
    md(r"""
### 5.4 — Classification depth versus array size

Using the classification metric of exercise 2 (SNR 5 per R = 300 bin over 450 to 650 nm, a
10,000 K SED in R), plot the depth against N for 5, 30 and 60 minutes, with the Argus single-epoch
(g = 20.0), Argus 15-minute co-add (g = 21.5) and LSST single-visit (r ~ 24.5) depths as horizontal
lines. How many arrays does it take to classify everything LSST finds in a single visit?
"""),
    sol("""
WINDOW = (450, 650); R_BIN = 300; SNR_CLASS = 5
snr_resel_class = SNR_CLASS / np.sqrt(1800 / R_BIN)
sn_like = Source.blackbody(10000, 0, "R")
def bench(n):
    return LFASTETC("bench_r1800", telescope=tel(n), wavelength_min_nm=WINDOW[0], wavelength_max_nm=WINDOW[1])
REFS = {"Argus 1 min (g)": 20.0, "Argus 15 min (g)": 21.5, "LSST single visit (r)": 24.5}
fig, ax = plt.subplots(figsize=(7.5, 4.5))
depth = {}
for exp, color in ((300, "C2"), (1800, "C0"), (3600, "C1")):
    d = np.array([bench(int(n)).limiting_magnitude(sn_like, exp, snr_resel_class, wavelength=WINDOW) for n in NS])
    depth[exp] = dict(zip(NS, d))
    ax.plot(NS, d, marker="o", ms=3, color=color, label=f"{exp / 60:.0f} min")
for txt, mag in REFS.items():
    ax.axhline(mag, color="0.5", ls=":"); ax.text(NS[-1], mag + 0.05, txt, fontsize=8, color="0.4", ha="right")
ax.set_ylabel("Classification depth (R mag)")
ax.set_title("SNR=5 per R=300 bin, 450-650 nm, 10,000 K SED, grey sky"); ax.legend(loc="upper left")
mark_scales(ax)
pd.DataFrame({f"N={n}": {exp // 60: depth[exp][n] for exp in depth} for n in SCALES}).rename_axis("exposure (min)").round(1)
# 86 arrays reach R ~ 24.0 in 60 min, within ~0.5 mag of the LSST single-visit depth.
"""),
    md(r"""
### 5.5 — The bright end

With one combiner input per array, the light per detector pixel is set by a single array and does
not grow with the number of arrays, so the bright limit is the same at 20, 200 and 1720 telescopes.
Tabulate the brightest star for which a 1 s (Bench) or 8 s (CSHELL, Fowler minimum) read stays below
80% of full well, for the three scales. What would an idealised single combiner do instead?
"""),
    sol("""
bright = {}
for preset, band, teff, kw, tmin in (("bench_r1800", "V", 5800, {}, 1.0), ("cshell_r18000", "H", 4500, dict(wavelength_min_nm=cs_lo, wavelength_max_nm=cs_hi), 8.0)):
    row = {}
    for n in SCALES:
        e = LFASTETC(preset, telescope=tel(n), **kw)
        mags = np.arange(-2, 14, 0.1)
        peak = np.array([np.nanmax(e.snr(Source.blackbody(teff, m, band), tmin).peak_e_per_pixel) for m in mags])
        row[f"N={n}"] = f"{band} > {mags[peak < 0.8 * e.instrument.full_well].min():.1f}"
    bright[f"{preset} ({tmin:.0f} s read)"] = row
pd.DataFrame(bright).T.rename_axis("brightest unsaturated star")
# A single combiner would saturate N/20 times sooner. A brighter star has to be attenuated:
# fewer telescopes per array, or a neutral-density filter.
"""),
    ai("Add the kilonova horizon: for an AT2017gfo-like kilonova at 0.5, 1, 2 and 3 days after merger, plot the distance at which it can still be classified in 30 minutes against N, with the LIGO O4 (150-170 Mpc) and O5 (225-295 Mpc) binary-neutron-star ranges shaded. At what array size does the 1-day horizon pass the O5 range?"),
]

EX6 = [
    md(r"""
This exercise has no solution key beyond a worked example. Work with Jupyter AI as a pair
programmer: you supply the astronomy, it supplies the code, you check the numbers.

### 6.1 — Pick a target

A star, a transient, a planet host, a young star, an AGN. Write down: its magnitude and the band it
is quoted in, its spectral shape (temperature, power-law slope, or a spectrum file), the feature or
window you care about, the SNR you need there and why, and the instrument (Bench mode, or CSHELL
with one setting).

### 6.2 — Describe it to the agent

A prompt that works: *"I want to observe `<target>` (`<band>` = `<mag>`, `<Teff>` K) with LFAST
using lfast_etc. Build LFASTETC with the `<preset>` preset and 20 telescopes, a Source.blackbody
normalised in `<band>`, and report the median exposure time for SNR `<snr>` per resel over
`<lo>` to `<hi>` nm, the number of reads needed to avoid saturation, and which noise term dominates
there. Then show how the time changes with 100 and 200 telescopes."*

Check what it does against notebooks 02 and 03: did it restrict CSHELL to one setting? Did it
check `saturated`? Did it quote SNR per resel or per pixel?
"""),
    sol("""
# Worked example: a Ca II triplet velocity for a V = 17 K giant (RGB tip at ~80 kpc) in the red
# bench_740vph_o1 mode (772-987 nm, R ~ 3600), SNR 30 per resel over 845-870 nm.
ins = Instrument.from_preset("bench_740vph_o1")
print(ins.description, f"{ins.wavelength_min_nm:.0f}-{ins.wavelength_max_nm:.0f} nm, R={ins.resolving_power:.0f}")
giant = Source.blackbody(4500, 17, "V")
for n in (20, 100, 200):
    e = LFASTETC(ins, n_telescopes=n)
    r = e.exptime(giant, snr=30)
    win = (r.wavelength >= 845) & (r.wavelength <= 870)
    print(f"N={n:3d}: median exposure for SNR 30 over 845-870 nm = {np.nanmedian(r.exptime[win]) / 60:6.1f} min")
"""),
    md(r"""
### 6.3 — One plot, one number

Produce the one plot that answers your question (exposure time versus magnitude, the noise budget,
a sensitivity map, the array-size sweep) and the one number you would put in a proposal.
"""),
    sol("""
e = LFASTETC(ins, n_telescopes=20)
r = e.snr(giant, exptime=1800)
fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
r.plot(ax=axes[0]); axes[0].axvspan(845, 870, color="0.9", zorder=0)
r.plot_noise_budget(ax=axes[1]); axes[0].set_xlabel("")
print(f"30 min, 20 telescopes: median SNR/resel over the Ca II triplet = {np.nanmedian(r.snr[(r.wavelength >= 845) & (r.wavelength <= 870)]):.1f}")
"""),
    md(r"""
### 6.4 — What was wrong

Ask the agent to list every assumption it made that you did not state (blackbody instead of a real
spectrum, grey sky, no overheads, no slit or fiber losses beyond the model, flat QE, the placeholder
Bench efficiencies). Which would change the answer by more than a factor of two?
"""),
    ai("List every assumption you made in 6.2 that I did not state, and for each one estimate how much the exposure time would change if it were wrong."),
]

# =====================================================================================
# README
# =====================================================================================

README = r"""
# LFAST hands-on: the exposure time calculator

Requirements: `lfast_etc` (plus `matplotlib`, `pandas`, `scipy` and `jupyter`), installed on the
symposium JupyterHub. Nothing needs the network. A web version of the ETC is at
<https://simulators.schmidtobservatorysystem.org/lfast/>; the package and its docs are at
<https://github.com/schmidt-observatories/lfast-etc>.

**Jupyter AI.** The notebooks assume the Jupyter AI chat is open in the side panel. Boxes marked 🤖
suggest prompts; boxes marked ✏️ ask you to guess a number before computing it. Two exercises contain
a deliberately broken cell.

## Tutorials

| notebook | content |
|---|---|
| [01 — The ETC in one line](01_etc_in_one_line.ipynb) | `LFASTETC()`, `Source.blackbody()`, `exptime()`, `snr()`, the `ETCResult` (`plot`, `summary`, `at`, `to_table`, `plot_spectrum`), the round trip |
| [02 — Instruments, presets and the array](02_instruments_presets_array.ipynb) | `list_instruments()`, the Bench and CSHELL presets, `plot_throughput()`, `setting_window()`, overrides and `replace()`, `Telescope(n, fiber, combine, telescopes_per_input)` |
| [03 — Sources, sky and noise](03_sources_sky_noise.ipynb) | blackbody, power law, flat and array sources, lines, other bands, `plot_sky()`, `Sky(scale)`, `plot_rates()`, `plot_noise_budget()`, `n_exp`, `reads_needed()`, saturation |
| [04 — Sensitivity maps and array scaling](04_sensitivity_maps_array_scaling.ipynb) | `snr_grid()`, `plot_snr_map()`, `limiting_magnitude()`, `plot_limiting_magnitude()`, `exptime_vs_mag()`, sweeps over N, `plot_vs_n_telescopes()`, `equivalent_diameter_axis()` |

## Exercises

Each is one science case. Pick the one closest to your own science.

| exercise | science | covers | difficulty |
|---|---|---|---|
| [1 — Stellar metallicities](exercises/ex1_stellar_metallicity.ipynb) | Galactic archaeology | 01–04 | ★☆☆☆☆ |
| [2 — Classifying transients](exercises/ex2_transient_classification.ipynb) | TDAMM, kilonovae | 01, 03, 04 | ★★☆☆☆ |
| [3 — M-dwarf flares at high cadence](exercises/ex3_stellar_flares.ipynb) | stellar activity | 01, 03 | ★★★☆☆ |
| [4 — He 10830 with CSHELL](exercises/ex4_he10830_cshell.ipynb) | exoplanet atmospheres | 02–04 | ★★★☆☆ |
| [5 — 20 telescopes, 10 m, 30 m](exercises/ex5_array_scaling.ipynb) | array design | 04 | ★★★★☆ |
| [6 — Bring your own target](exercises/ex6_bring_your_own_target.ipynb) | yours | all | open |

Solutions are in [`exercises/solutions/`](exercises/solutions/). The science-case notebooks these
grew out of, from the `lfast-etc` package, are in [`backup/`](backup/).

To regenerate the notebooks: `python build_notebooks.py`, then execute them with `jupyter nbconvert`.
"""


if __name__ == "__main__":
    write(HERE / "01_etc_in_one_line.ipynb", T01)
    write(HERE / "02_instruments_presets_array.ipynb", T02)
    write(HERE / "03_sources_sky_noise.ipynb", T03)
    write(HERE / "04_sensitivity_maps_array_scaling.ipynb", T04)

    exercise("ex1_stellar_metallicity", "Exercise 1 — Stellar metallicities with the Bench", "01–04", "★☆☆☆☆",
             "How faint and how fast can LFAST deliver LAMOST-quality metallicities, one star at a time?", EX1)
    exercise("ex2_transient_classification", "Exercise 2 — Classifying transients", "01, 03, 04", "★★☆☆☆",
             "What is the faint limit to classify a transient, how long does a kilonova stay classifiable, and what does "
             "a bigger array buy?", EX2)
    exercise("ex3_stellar_flares", "Exercise 3 — M-dwarf flares at high cadence", "01, 03", "★★★☆☆",
             "One readout per exposure whatever the array size makes LFAST a natural flare spectrograph. How faint, "
             "how fast, and what does a flare look like?", EX3)
    exercise("ex4_he10830_cshell", "Exercise 4 — He 10830 with CSHELL", "02–04", "★★★☆☆",
             "One strong line per echelle setting: escaping atmospheres with the metastable helium triplet.", EX4)
    exercise("ex5_array_scaling", "Exercise 5 — 20 telescopes, 10 m equivalent, 30 m equivalent", "04", "★★★★☆",
             "The headline sensitivity curves against the array size, for both instruments.", EX5, setup=SETUP + SCALES)
    exercise("ex6_bring_your_own_target", "Exercise 6 — Bring your own target", "all", "open",
             "Your science, LFAST, and Jupyter AI as a pair programmer.", EX6)

    (HERE / "README.md").write_text(README.strip() + "\n")
    print("wrote README.md")
