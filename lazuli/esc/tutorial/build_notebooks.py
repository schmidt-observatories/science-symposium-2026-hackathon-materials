#!/usr/bin/env python
"""Build the ESC tutorial notebooks, exercises and solutions.

    cd lazuli/esc/tutorial
    python build_notebooks.py          # writes the .ipynb files (no outputs)
    jupyter nbconvert --to notebook --execute --inplace 0*.ipynb exercises/solutions/*.ipynb

Exercises and solutions share one definition: a `sol()` cell becomes `# your code here` in the
exercise notebook, and a `bug(broken, fixed)` pair gives the exercise the broken cell and the
solution the fixed one. Same pattern as lazuli/wcc/tutorial/build_notebooks.py.
"""
from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = Path(__file__).parent
META = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}}

SETUP = """
import warnings
import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
import esc_etc
from esc_etc import Simulation, use_lazuli_style

use_lazuli_style()
warnings.filterwarnings("ignore", module="synphot")
"""

SUN_TWIN = """
sim = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v",
                              planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
"""

FRAME_FOR = '''
def frame_for(sim, max_frame=1000 * u.s):
    """Frame time to use: max_frame, or half the saturation time if that is shorter."""
    return min(u.Quantity(max_frame, u.s), 0.5 * sim.saturation_time())


def hours_to_snr(sim, snr=5, max_frame=1000 * u.s):
    """Integration time (hours) to reach snr with the current configuration; NaN above the speckle plateau."""
    return sim.get_int_time_for_snr(snr, frame_for(sim, max_frame))["int_time_continuous"][0].to_value(u.hr)
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
# 01 — esc_etc as an exposure time calculator

`esc_etc` is the exposure time calculator (ETC) for the **ExtraSolar Camera (ESC)**, the
coronagraphic instrument on the Lazuli Space Observatory: a 3 m telescope, a charge-6 vortex
focal-plane mask, a deformable mirror that digs a dark hole of raw contrast ~$10^{-8}$, and twelve
filters between 400 and 730 nm. The question it answers is *"how long until this planet, at this
contrast and separation, reaches S/N = 5?"*

A **web version** of the same calculator is at <https://simulators.schmidtobservatorysystem.org/esc/>:
use it for a quick number, and these notebooks when you want sweeps, plots and the full model.

The model is analytic: five count rates in a resolution-element-sized aperture (planet, residual
starlight "speckles", zodiacal light, exozodiacal light, and the host star for saturation), with a
speckle noise floor that post-processing can only partly remove.

In this notebook:
1. a simulation: `Simulation.from_default()`,
2. S/N for a total time, and time for a target S/N,
3. the count-rate budget,
4. S/N versus time and the **plateau**.

**Jupyter AI.** These notebooks are written to be run with the Jupyter AI chat open in the side
panel. Boxes marked 🤖 suggest things to ask it; boxes marked ✏️ ask you to guess a number before
computing it.
"""),
    code(SETUP),
    md(r"""
***
## 1. A simulation

`from_default` builds everything from the bundled Lazuli and ESC configuration: give it the host
star magnitude (and the band it is quoted in), the planet's delta magnitude relative to the host
(20 mag = contrast $10^{-8}$), the raw dark-hole contrast, the post-processing gain, the separation
in arcseconds and the filter. The scene here is a Sun twin at 10 pc with a Jupiter-like planet at
4 AU, i.e. 0.4".
"""),
    code(SUN_TWIN + """
for part in (sim.sensor, sim.coronagraph):
    print(f"--- {type(part).__name__}")
    part.describe()
st, pl = sim.scene.star, sim.scene.planet
print(f"--- Scene: star {st.mag} ({st.mag_system}, {st.band}), planet {pl.deltamag} mag fainter in the ESC band, "
      f"zodi {sim.scene.zodi.mag} mag/arcsec², exozodi {sim.scene.exozodi.mag:.2f} mag/arcsec²")
"""),
    md(r"""
***
## 2. S/N for a time, time for an S/N

`get_snr(total_time, frame_time)` takes plain seconds or astropy quantities. The total time is
split into frames of `frame_time`, and the read noise is paid once per frame (notebook 04).
"""),
    code("""
r = sim.get_snr(total_time=3600, frame_time=100)
for k, v in r.items():
    print(f"{k:18s} {v}")
"""),
    md(r"""
- `signal_e`, `noise_e`: planet electrons in the aperture and the total noise.
- `M`: the speckle noise floor rate, the residual starlight that post-processing leaves behind.
- `science_time` and `charged_time` differ only with reference-star subtraction (notebook 03).

The inverse: `get_int_time_for_snr` returns the exact (`int_time_continuous`) and whole-frame
(`int_time`) integration time, and **NaN when the S/N is unreachable** because of the floor.
"""),
    code("""
for snr in (3, 5, 9, 20):
    t = sim.get_int_time_for_snr(snr, frame_time=100)
    print(f"S/N = {snr:2d}: {t['int_time_continuous'][0].to(u.hr):.2f}  ({t['int_time'][0]:.0f} in whole frames)")
"""),
    md(r"""
***
## 3. The count-rate budget

`count_rate_components()` gives the five rates in the photometric aperture. The host star's rate
is what lands on the detector *without* the coronagraph; the speckle rate is the host times the raw
contrast times the mask throughput.
"""),
    code("""
rates = sim.count_rate_components()
for name in ("source", "speckle", "zodi", "exozodi", "host"):
    print(f"{name:8s}: {getattr(rates, name):.3e}")
fig, ax = sim.plot_count_rates()
plt.show()
"""),
    md(r"""
***
## 4. S/N versus time, and the plateau

With $S$ the planet rate, $B$ the background rates, and $M$ the speckle floor rate,

$$\mathrm{S/N}(t) = \frac{S\,t}{\sqrt{S\,t + B\,t + n_\mathrm{pix}\,n_\mathrm{reads}\,\sigma_\mathrm{read}^2 + (M\,t)^2}}
\;\xrightarrow{t\to\infty}\; \frac{S}{M} = \frac{C_\mathrm{planet}}{C_\mathrm{raw}}\,\mathrm{ppgain}.$$

The floor term grows as $t$, not $\sqrt{t}$, so the S/N saturates at a **plateau** set by the
planet-to-raw contrast ratio and the post-processing gain. No amount of time gets past it.
"""),
    guess("this planet reaches S/N 4.6 in one hour. What S/N does it reach in ten hours? In a hundred?"),
    code("""
for hours in (1, 10, 100):
    print(f"{hours:4d} h: S/N = {sim.get_snr(hours * u.hr, 100)['snr']:.2f}")
print(f"plateau S/N = S / M = {rates.source / r['M']:.2f}  (= ppgain x C_planet / C_raw = 10 x 1e-8 / 1e-8)")
fig, ax = sim.plot_snr_vs_time()
ax.axhline(10, color="0.5", ls=":")
plt.show()
"""),
    ai("Turn the S/N-at-one-hour computation into a loop over the twelve ESC filters (esc_etc.FILTERS) and print a table of filter, central wavelength (sim.telescope.primary_filter) and S/N in one hour, sorted by S/N.",
       "Notebook 02 does the same; compare. Ask it why the wide filters win so clearly."),
    md(r"""
`plot()` draws the six-panel overview: spectra, bandpass, aperture, mask throughput, rates and
S/N versus time.
"""),
    code("""
fig, axes = sim.plot()
plt.show()
"""),
    md(r"""
***
## Summary

```python
sim = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v",
                              planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
sim.get_snr(3600, 100)["snr"]                                   # S/N in 1 h of 100 s frames
sim.get_int_time_for_snr(5, 100)["int_time_continuous"][0]      # time to S/N 5 (NaN above the plateau)
sim.count_rate_components()                                     # planet, speckle, zodi, exozodi, host
sim.plot_snr_vs_time(); sim.plot()
```

Next: [02 — components, parameters and filters](02_components_and_filters.ipynb).
"""),
]

T02 = [
    md(r"""
# 02 — Components, parameters and filters

A simulation is four components: a `Telescope`, a `Sensor`, a `Scene` (star, planet, zodi,
exozodi) and a `Coronagraph`. `from_default` assembles them from the bundled configuration;
you can also build them yourself, and change any parameter afterwards with `update()`.

In this notebook:
1. the four components and `from_components`,
2. `update()` and `reset()`,
3. magnitudes: which band, which system,
4. the twelve filters, end of life and beginning of life,
5. the photometric aperture.
"""),
    code(SETUP + "\nfrom esc_etc import Telescope, Sensor, Coronagraph, get_scene, FILTERS\n"),
    md(r"""
***
## 1. The four components
"""),
    code("""
tel = Telescope.from_default(filter="R3")
sen = Sensor.from_default(tel, filter="R3", lifetime="eol")
scene = get_scene(tel, hoststarmag=4.83, hoststar_band="johnson_v", planetdeltamag=20, bg_flux=22.5, exobg_flux=21)
cor = Coronagraph.from_default(tel, raw_dh_contrast=1e-8, ppgain=10, separation=0.4)

print(f"telescope: D = {tel.diameter_primary}, secondary {tel.diameter_secondary}, collecting area {tel.surface:.2f}, "
      f"f/{tel.f_num:.1f}, jitter {tel.jitter_rms.to(u.mas):.0f}, central wavelength {tel.primary_filter.to(u.nm):.0f}")
print(f"sensor:    {sen.pixel_size} pixels at {sen.plate_scale * 1e3:.2f} mas/px, read noise {sen.read_noise:.2f}, "
      f"dark {sen.dark_current:.4f}, well {sen.well_depth:.0f}")
print(f"scene:     star V = {scene.star.mag} ({scene.star.mag_system}), planet {scene.planet.deltamag} mag fainter, "
      f"zodi {scene.zodi.mag} mag/arcsec² in V, exozodi {scene.exozodi.mag:.2f} mag/arcsec² in the ESC band")
print(f"coronagraph: raw contrast {cor.raw_dh_contrast}, ppgain {cor.ppgain}, separation {cor.separation} arcsec")

sim = Simulation.from_components(tel, sen, scene, cor)
same = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
print(f"\\nS/N in 1 h: {sim.get_snr(3600, 100)['snr']:.3f} from components, {same.get_snr(3600, 100)['snr']:.3f} from_default")
"""),
    md(r"""
***
## 2. `update()` and `reset()`

Any parameter is reachable as `component__parameter` (two underscores; a nested element adds a
level, `scene__star__mag`). `update` recomputes what depends on it; `reset` restores the state the
simulation was built with. Invalid values are refused.
"""),
    code("""
base = sim.get_snr(3600, 100)["snr"]
sim.update(scene__star__mag=6.0)
print(f"host 1.2 mag fainter:      S/N = {sim.get_snr(3600, 100)['snr']:.3f}")
sim.update(coronagraph__ppgain=100)
print(f"... and ppgain 100:        S/N = {sim.get_snr(3600, 100)['snr']:.3f}")
sim.update(coronagraph__separation=0.15)
print(f"... and 0.15 arcsec:       S/N = {sim.get_snr(3600, 100)['snr']:.3f}")
try:
    sim.update(sensor__encircled_energy=1.7)
except ValueError as err:
    print("refused:", err)
sim.reset()
print(f"after reset:               S/N = {sim.get_snr(3600, 100)['snr']:.3f} (was {base:.3f})")
"""),
    md(r"""
***
## 3. Magnitudes

`hoststarmag` is quoted in `hoststar_band`: `"johnson_v"` for a catalogue V magnitude, or `None`
for the ESC filter itself. `planetdeltamag` is the planet's faintness relative to the host in the
ESC band (contrast $C = 10^{-0.4\,\Delta m}$). `mag_system` is `"vega"` (default) or `"AB"`.
The spectra behind these are **flat**: the ETC has no colour terms, so a red M dwarf quoted in V is
treated as if it were as bright in R3 as in V.
"""),
    code("""
for band, label in ((None, "ESC band (R3)"), ("johnson_v", "Johnson V")):
    s = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band=band, planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
    print(f"host 4.83 in {label:14s}: S/N in 1 h = {s.get_snr(3600, 100)['snr']:.3f}")
s = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v", mag_system="AB", planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
print(f"host 4.83 in Johnson V, AB   : S/N in 1 h = {s.get_snr(3600, 100)['snr']:.3f}")
for dm in (17.5, 20, 22.5):
    sim.update(scene__planet__deltamag=dm)
    print(f"planet delta mag {dm:4.1f} (contrast {10 ** (-0.4 * dm):.1e}): S/N in 1 h = {sim.get_snr(3600, 100)['snr']:.3f}")
sim.reset()
"""),
    ai("Read esc_etc/scene.py and tell me how the star and planet spectra are modelled. What does that imply for an M4 dwarf host whose V magnitude I pass with hoststar_band='johnson_v'? How would I correct for it by hand?",
       "The honest answer is a colour term you apply yourself; ask it for the V minus R3 colour of an M4 dwarf."),
    md(r"""
***
## 4. The filters

`FILTERS` lists the twelve ESC filters by name and by designation; `filter=` picks one, `lifetime`
picks the end-of-life (default) or beginning-of-life throughput curve.
"""),
    guess("which filter gives the highest S/N in one hour on a Jupiter twin, and by what factor over the narrow ones?"),
    code("""
names = ["B1", "B2", "B3", "B4", "B5", "B6", "R1", "R2", "R3", "R4", "R5", "R6"]
rows = []
print(f"{'filter':7s} {'designation':12s} {'lambda [nm]':>11s} {'S/N in 1 h':>10s}")
for name in names:
    s = Simulation.from_default(filter=name, hoststarmag=4.83, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
    desig = [k for k, v in FILTERS.items() if v == FILTERS[name] and k != name][0]
    rows.append((name, desig, s.telescope.primary_filter.to_value(u.nm), s.get_snr(3600, 100)["snr"]))
    print(f"{name:7s} {desig:12s} {rows[-1][2]:11.0f} {rows[-1][3]:10.2f}")

fig, ax = plt.subplots(figsize=(9, 4))
for name in ("B4", "R1", "R3"):
    Simulation.from_default(filter=name).plot_bandpass(ax=ax, label=f"{name} end of life")
Simulation.from_default(filter="R3", lifetime="bol").plot_bandpass(ax=ax, label="R3 beginning of life")
ax.legend()
plt.show()
"""),
    md(r"""
The wide filters (B4 = F450W, R3 = F659W) collect several times the planet photons of the narrow
ones (N = narrow, W = wide), so for a detection they win outright; the narrow filters are for
colours and for the methane band at 725 nm (R5).

***
## 5. The photometric aperture

The planet is measured in one resolution element (`aperture="resel"`): a circle of area
$\pi(\lambda/2D)^2$ that holds about 46 % of the encircled energy at 20 pixels of the 8.7 mas
pixel scale. The same resel also collects the zodi and exozodi.
"""),
    code("""
s = sim.sensor
print(f"aperture: {s.aperture}, {s.num_psf_pixels:.1f}, solid angle {s.aperture_solid_angle:.5f}, encircled energy {s.ee_fraction:.3f}, peak-pixel fraction {s.peak_pixel_fraction:.3f}")
fig, ax = sim.plot_aperture()
plt.show()
"""),
    md(r"""
***
## Summary

```python
Telescope.from_default(filter="R3"); Sensor.from_default(tel, ...); get_scene(tel, ...); Coronagraph.from_default(tel, ...)
Simulation.from_components(tel, sen, scene, cor)
sim.update(scene__star__mag=6, coronagraph__ppgain=100, coronagraph__separation=0.15); sim.reset()
Simulation.from_default(filter="B4", lifetime="bol")      # FILTERS has the twelve names
```

Next: [03 — contrast, post-processing gain and separation](03_contrast_gain_separation.ipynb).
"""),
]

T03 = [
    md(r"""
# 03 — Contrast, post-processing gain and separation

Three coronagraph numbers decide whether a planet is detectable at all: the **raw dark-hole
contrast** (how much starlight leaks through), the **post-processing gain** (how much of that
leak a reference subtraction removes), and the **separation** relative to the mask's inner
working angle.

In this notebook:
1. the raw contrast sweep and the plateau,
2. the post-processing gain,
3. the separation and the mask's off-axis throughput,
4. time to S/N 5 versus planet contrast: the floor,
5. reference-star subtraction (RDI).
"""),
    code(SETUP + SUN_TWIN + FRAME_FOR),
    md(r"""
***
## 1. Raw contrast

`plot_snr_vs_time(sweep={...})` draws one curve per value of any `update()` key.
"""),
    code("""
fig, ax = sim.plot_snr_vs_time(sweep={"coronagraph__raw_dh_contrast": [1e-7, 1e-8, 1e-9]})
ax.set_title("planet contrast 1e-8: raw contrast sets the plateau")
plt.show()
for c in (1e-7, 1e-8, 1e-9):
    sim.update(coronagraph__raw_dh_contrast=c)
    print(f"raw contrast {c:.0e}: S/N in 1 h = {sim.get_snr(3600, 100)['snr']:.2f}, plateau = {10 * 1e-8 / c:.0f}")
sim.reset()
"""),
    md(r"""
At raw contrast $10^{-7}$ the plateau is $10 \times 10^{-8}/10^{-7} = 1$: the planet is ten times
fainter than the speckles and post-processing by 10 only brings them level. Nothing is detected,
ever.

***
## 2. Post-processing gain
"""),
    guess("going from ppgain 10 to 100, does the one-hour S/N on this planet go up by 10 %, by a factor 2, or by a factor 10?"),
    code("""
fig, ax = sim.plot_snr_vs_time(sweep={"coronagraph__ppgain": [1, 10, 100]})
plt.show()
for g in (1, 10, 100):
    sim.update(coronagraph__ppgain=g)
    print(f"ppgain {g:3d}: S/N in 1 h = {sim.get_snr(3600, 100)['snr']:5.2f}, in 10 h = {sim.get_snr(10 * u.hr, 100)['snr']:5.2f}, plateau {g * 1e-8 / 1e-8:.0f}")
sim.reset()
"""),
    md(r"""
The gain lifts the plateau but hardly changes the first hour: there the photon noise of the speckles
(not their systematic residual) dominates, and `ppgain` does nothing about photon noise.

***
## 3. Separation and the mask throughput

The vortex mask transmits the planet with a throughput that rises from zero on axis to about 65 %
beyond 10 $\lambda/D$. The configuration tabulates it out to 20 $\lambda/D$; the ETC refuses
separations beyond that. A common definition of the inner working angle (IWA) is 50 % of the peak
throughput.
"""),
    code("""
cg = sim.coronagraph
lamD = (cg.primary_filter / cg.diameter_primary).to_value(u.arcsec, equivalencies=u.dimensionless_angles())
seps = cg._lamD * lamD
thr = cg._throughput
IWA = seps[np.argmax(thr >= 0.5 * thr.max())]
print(f"lambda/D = {lamD * 1e3:.1f} mas at {cg.primary_filter.to(u.nm):.0f}; table edge {seps.max():.3f}\\" (20 lambda/D)")
print(f"peak throughput {thr.max():.2f}; IWA (50 % of peak) = {IWA:.3f}\\" = {IWA / lamD:.1f} lambda/D")
for sep in (0.1, 0.2, 0.4, 0.8):
    print(f"  {sep:.1f}\\": throughput {cg.off_axis_throughput(sep):.3f}")
fig, ax = sim.plot_offaxis_throughput()
ax.axvline(IWA, color="0.5", ls=":")
plt.show()
fig, ax = sim.plot_snr_vs_time(sweep={"coronagraph__separation": [0.1, 0.2, 0.4]})
plt.show()
"""),
    md(r"""
The throughput scales planet *and* speckle rates alike, so the plateau does not move with
separation; only the time to get there does. (The raw contrast is a single number across the dark
hole in this model: in reality it degrades towards the IWA.)

***
## 4. Time to S/N 5 versus planet contrast

The floor in contrast: S/N 5 needs a plateau above 5, i.e. $C_\mathrm{planet} > 5\,C_\mathrm{raw}/\mathrm{ppgain}$.
`hours_to_snr` (defined in the setup cell) wraps `get_int_time_for_snr` with a frame time capped
at half the saturation time, and returns NaN above the plateau.
"""),
    code("""
contrasts = np.logspace(-9.5, -7, 26)
fig, ax = plt.subplots(figsize=(7, 4.5))
for g in (10, 30, 100):
    hours = []
    for c in contrasts:
        sim.update(scene__planet__deltamag=-2.5 * np.log10(c), coronagraph__ppgain=g)
        hours.append(hours_to_snr(sim))
    sim.reset()
    ax.loglog(contrasts, hours, "o-", label=f"ppgain {g}")
    ax.axvline(5e-8 / g, color="0.6", ls=":")
    print(f"ppgain {g:3d}: floor at C = 5 x 1e-8 / {g} = {5e-8 / g:.1e}; a 1e-8 planet takes {hours[np.argmin(np.abs(contrasts - 1e-8))]:.2f} h")
ax.axhline(24, color="0.5", ls="--"); ax.text(contrasts[0], 27, "one day", color="0.5")
ax.set(xlabel="planet contrast", ylabel="time to S/N = 5 [h]", title="Sun twin at 10 pc, 0.4\\", R3, raw contrast 1e-8")
ax.legend()
plt.show()
"""),
    md(r"""
***
## 5. Reference-star subtraction

`coronagraph__subtraction="rdi"` models a reference star observed for `ref_time_ratio` times the
science time at `ref_brightness_ratio` times the brightness: its noise is added, and the charged
time grows.
"""),
    code("""
sim.update(coronagraph__subtraction="rdi", coronagraph__ref_time_ratio=1.0, coronagraph__ref_brightness_ratio=1.0)
r = sim.get_snr(3600, 100)
print(f"RDI: S/N {r['snr']:.2f} in {r['science_time']:.0f} of science time, {r['charged_time']:.0f} charged, reference noise {r['reference_noise_e']:.1f} e-")
sim.update(coronagraph__ref_brightness_ratio=4.0)
print(f"with a 4x brighter reference: S/N {sim.get_snr(3600, 100)['snr']:.2f}")
sim.reset()
print(f"no subtraction: S/N {sim.get_snr(3600, 100)['snr']:.2f}")
"""),
    ai("Starting from the S/N formula in notebook 01 (or esc_etc/noise.py), derive the plateau S/N = ppgain x C_planet / C_raw, and then the contrast floor for S/N = 5. Check it against the vertical lines in the plot above.",
       "Then ask what happens to the floor if the raw contrast were a function of separation, say 1e-8 at 10 lambda/D rising to 1e-7 at the IWA."),
    md(r"""
***
## Summary

```python
sim.plot_snr_vs_time(sweep={"coronagraph__raw_dh_contrast": [1e-7, 1e-8, 1e-9]})   # any update() key
sim.coronagraph.off_axis_throughput(0.2); sim.plot_offaxis_throughput()
plateau = ppgain * C_planet / C_raw;  floor: C_planet > 5 * C_raw / ppgain
sim.update(coronagraph__subtraction="rdi", coronagraph__ref_time_ratio=1, coronagraph__ref_brightness_ratio=1)
```

Next: [04 — frame time, read noise and saturation](04_frame_time_saturation.ipynb).
"""),
]

T04 = [
    md(r"""
# 04 — Frame time, read noise and saturation

The total integration is taken as a series of frames. Short frames pay the read noise many times;
long frames saturate on the residual starlight of a bright host. The ETC exposes both ends.

In this notebook:
1. the frame time and the read noise,
2. the inverse: whole frames versus the continuous solution,
3. `saturation_time()` and bright hosts,
4. the noise budget.
"""),
    code(SETUP + SUN_TWIN + FRAME_FOR),
    md(r"""
***
## 1. Frame time
"""),
    code("""
fig, ax = plt.subplots()
for ft in (1, 10, 100, 1000):
    sim.plot_snr_vs_time(frame_time=ft * u.s, ax=ax, label=f"frame time {ft} s")
    print(f"frame {ft:5d} s: S/N in 1 h = {sim.get_snr(3600, ft)['snr']:.2f}")
ax.legend()
plt.show()
"""),
    md(r"""
With 1.8 e- read noise over 21 pixels, a 1 s frame adds 70 e$^2$ of variance against a planet
rate of 0.08 e-/s: the read noise is everything. At 1000 s it is nothing. For faint planets use
the longest frames the host allows.

***
## 2. Whole frames versus the continuous solution
"""),
    code("""
t = sim.get_int_time_for_snr(5, frame_time=1000)
print(f"S/N 5 with 1000 s frames: {t['int_time_continuous'][0]:.0f} exactly, {t['int_time'][0]:.0f} in whole frames")
t = sim.get_int_time_for_snr(20, frame_time=1000)
print(f"S/N 20 (above the plateau of 10): {t['int_time_continuous'][0]}")
"""),
    md(r"""
***
## 3. Saturation and bright hosts

`saturation_time()` is the frame time at which the brightest pixel in the planet aperture fills
80 % of the well; `is_saturated(frame_time)` checks a given frame. Caveat from the esc-etc docs:
only the planet location at dark-hole contrast is modelled, so for a bright host the detector-safe
frame time can be much shorter than this.
"""),
    guess("Sirius is V = -1.4. How long a frame can the ESC take on it before the planet aperture saturates: 1 s, 100 s or an hour?"),
    code("""
print(f"{'V':>5} {'sat. time':>12} {'frame used':>11} {'S/N in 1 h':>10} {'host rate':>14}")
for V in (-1.4, 1.1, 3.0, 5.0, 7.0):
    sim.update(scene__star__mag=V)
    ft = frame_for(sim, 1000 * u.s)
    print(f"{V:5.1f} {sim.saturation_time().to(u.s):12.0f} {ft:11.0f} {sim.get_snr(3600, ft)['snr']:10.2f} {sim.count_rate_components().host:14.3e}")
sim.reset()
print("is_saturated(100 s) for V = 4.83:", bool(sim.is_saturated(100)), "; for a 2 x saturation-time frame:", bool(sim.is_saturated(2 * sim.saturation_time())))
"""),
    md(r"""
Brighter hosts give higher S/N for the same planet contrast: the planet is brighter too, and the
plateau is the same. The price is the frame time.

***
## 4. The noise budget

Reconstruct `noise_e` from the pieces: planet and background shot noise, read noise per frame,
and the squared speckle floor term. Notice which term grows as $t^2$.
"""),
    code("""
rates = sim.count_rate_components()
s = sim.sensor
for hours in (1, 10):
    t = hours * u.hr
    ft = 100 * u.s
    r = sim.get_snr(t, ft)
    terms = {
        "planet": (rates.source * t).to_value(u.electron),
        "speckle photons": (rates.speckle * t).to_value(u.electron),
        "zodi + exozodi": ((rates.zodi + rates.exozodi) * t).to_value(u.electron),
        "dark": (s.dark_current * s.num_psf_pixels * t).to_value(u.electron),
        "read": (s.read_noise ** 2 * s.num_psf_pixels * (t / ft)).to_value(u.electron),
        "speckle floor (M t)^2": ((r["M"] * t).to_value(u.electron)) ** 2,
    }
    total = sum(terms.values())
    assert abs(total / r["noise_e"] ** 2 - 1) < 0.02, "budget does not add up"
    print(f"--- {hours} h: noise_e^2 = {r['noise_e'] ** 2:.0f}, sum of terms {total:.0f}")
    for k, v in terms.items():
        print(f"    {k:24s} {v:12.0f}  ({v / total:5.1%})")
"""),
    ai("Write a function best_frame(sim, max_frame=1000) that returns the longest frame time that keeps sim.is_saturated(frame) False, searching a geometric grid from 1 s to max_frame, and use it to redo the bright-host table above.",
       "Compare with frame_for: half the saturation time is a simpler rule, but is it the right one when the limitation is the host's own halo rather than the dark hole?"),
    md(r"""
***
## Summary

```python
sim.get_snr(3600, frame_time=1000)                  # read noise once per frame
sim.get_int_time_for_snr(5, 1000)["int_time"]       # whole frames; "int_time_continuous" exact; NaN above the plateau
sim.saturation_time(); sim.is_saturated(100)
frame_for(sim) = min(1000 s, 0.5 * saturation_time)
```

Next: [05 — zodi and exozodi](05_zodi_and_exozodi.ipynb).
"""),
]

T05 = [
    md(r"""
# 05 — Zodi and exozodi

Two diffuse backgrounds share the planet's aperture: our own zodiacal light, and the target's
exozodiacal dust. Both are pure shot noise in this model (no residual structure), and both are
counted over the resel and multiplied by the mask throughput.

In this notebook:
1. how the two backgrounds are parameterized,
2. "zodis" and surface brightness,
3. an exozodi sweep: when does the dust matter?
"""),
    code(SETUP + SUN_TWIN + FRAME_FOR),
    md(r"""
***
## 1. Parameterization

- `bg_flux` (default 22.5): local zodi surface brightness in **V mag/arcsec²**.
- `exobg_flux` (default 21): exozodi as a **delta magnitude per arcsec² relative to the host**, in
  the ESC band. So `scene.exozodi.mag` is `hoststarmag + 21`.

Both elements take an absolute surface brightness through `update`, in any band.
"""),
    code("""
ex = sim.scene.exozodi
print(f"exozodi: mag = {ex.mag:.2f} mag/arcsec² (= host 4.83 + 21), band = {ex.band} (None = ESC band)")
print(f"zodi:    mag = {sim.scene.zodi.mag} mag/arcsec² in {sim.scene.zodi.band}")
r = sim.count_rate_components()
print(f"rates at 0.4\\" [e-/s]: planet {r.source:.3g}, speckle {r.speckle:.3g}, zodi {r.zodi:.3g}, exozodi {r.exozodi:.3g}")
print(f"aperture {sim.sensor.aperture_solid_angle:.5f}, mask throughput {sim.coronagraph.off_axis_throughput():.2f}")
"""),
    md(r"""
***
## 2. Zodis

A common convention (EXOSIMS, Stark et al. 2014): **1 zodi = 22 V mag/arcsec² at 1 AU from a
solar-luminosity star**, falling as $r^{-2}$, face on. At projected separation $r = \theta d$:

$$\mu_V(n) = 22 - 2.5\log_{10} n + 5\log_{10}(r / \mathrm{AU}).$$
"""),
    code("""
D_PC, SEP = 10.0, 0.4
r_AU = SEP * D_PC

def sb_zodis(n, r_au=r_AU):
    return 22.0 - 2.5 * np.log10(n) + 5 * np.log10(r_au)

print(f"r = {r_AU:.0f} AU: 1 zodi = {sb_zodis(1):.2f} V mag/arcsec², 10 zodi = {sb_zodis(10):.2f}, 100 zodi = {sb_zodis(100):.2f}")
print(f"the default exobg_flux = 21 corresponds to {10 ** (-0.4 * (4.83 + 21 - sb_zodis(1))):.2f} zodi here (ignoring the V vs R3 colour)")
"""),
    md(r"""
***
## 3. When does the dust matter?
"""),
    guess("at how many zodis does the time to S/N 5 double for this planet: 10, 100 or 1000?"),
    code("""
zodis = np.geomspace(0.1, 1e4, 30)

def hours_at(n_zodi):
    sim.update(scene__exozodi__mag=99.0 if n_zodi == 0 else sb_zodis(n_zodi), scene__exozodi__band="johnson_v")
    h = hours_to_snr(sim)
    sim.reset()
    return h

t0 = hours_at(0)
ratio = np.array([hours_at(n) for n in zodis]) / t0
n_double = np.interp(2.0, ratio, zodis)
print(f"no exozodi: {t0:.2f} h; 10 zodi: x{np.interp(10, zodis, ratio):.2f}; 100 zodi: x{np.interp(100, zodis, ratio):.2f}; doubles at {n_double:.0f} zodi")

fig, ax = plt.subplots(figsize=(7, 4.2))
ax.loglog(zodis, ratio, "o-")
ax.axhline(2, color="0.5", ls="--"); ax.axvspan(10, 100, color="C0", alpha=0.1)
ax.text(30, 1.1, "HOSTS high-dust tail", ha="center", color="C0")
ax.set(xlabel="exozodi [zodis]", ylabel="time to S/N 5 / time with no exozodi", title="Sun twin at 10 pc, planet 1e-8 at 0.4\\"")
plt.show()
"""),
    md(r"""
The doubling happens where the exozodi rate equals the planet plus all other background rates. At
0.4" from a Sun twin the resel is tiny and the dust has to be very bright to compete with the
speckle photons. That changes in the habitable zone of a nearby star, where $r$ is small and the
$r^{-2}$ law makes each zodi much brighter (exercise 5).
"""),
    ai("Repeat the sweep for the habitable zone of tau Ceti (3.65 pc, 0.7 AU, V = 3.5) with a 1e-10 Earth-like contrast and ppgain 100. Does the planet clear the floor at all, and if so, at how many zodis does its time double?",
       "If the answer is NaN everywhere, ask it what raw contrast would be needed."),
    md(r"""
***
## Summary

```python
Simulation.from_default(bg_flux=22.5, exobg_flux=21)                         # zodi (V mag/arcsec²), exozodi (delta mag vs host)
sim.update(scene__exozodi__mag=mu_V, scene__exozodi__band="johnson_v")      # absolute surface brightness
mu_V(n zodi) = 22 - 2.5 log10(n) + 5 log10(r / AU)
```

Now pick an exercise: [README](README.md).
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


def exercise(stem, title, covers, stars, intro, cells, setup=SETUP + FRAME_FOR):
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

> 🤖 **Ask Jupyter AI:** *Draft a GitHub issue for schmidt-observatories/esc-etc describing one thing I
> found missing, confusing or wrong in this exercise, with a minimal code example.*
""")
    write(HERE / "exercises" / f"{stem}.ipynb", ex + [feedback])
    write(HERE / "exercises" / "solutions" / f"{stem}_solution.ipynb", so + [feedback])


EX1 = [
    md(r"""
### 1.1 — Jupiter at 10 pc

A Sun twin (V = 4.83) at 10 pc with a Jupiter twin at 5.2 AU: separation 0.52", contrast
$1.4 \times 10^{-9}$ (geometric albedo 0.5, Lambert phase at quadrature, $C = A_g (R_p/a)^2/\pi$).
With the R3 filter, raw contrast $10^{-8}$ and ppgain 10: what is the S/N after one hour of 1000 s
frames, and the time to S/N 5?
"""),
    sol("""
from astropy.constants import R_jup, au
C = 0.5 / np.pi * float((R_jup / (5.2 * au)) ** 2)
dm = -2.5 * np.log10(C)
sim = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v", planetdeltamag=dm, contrast=1e-8, ppgain=10, separation=0.52)
print(f"contrast {C:.2e} (delta mag {dm:.2f}): S/N in 1 h = {sim.get_snr(3600, 1000)['snr']:.2f}, time to S/N 5 = {hours_to_snr(sim):.1f} h")
"""),
    guess("the plateau for this planet with ppgain 10 is 1.4. What ppgain is needed for S/N 5 to be reachable at all?"),
    md(r"""
### 1.2 — Post-processing gain

What is the plateau S/N for this planet at ppgain 10, 30 and 100, and the time to S/N 5 at each?
"""),
    sol("""
for g in (10, 30, 100):
    sim.update(coronagraph__ppgain=g)
    print(f"ppgain {g:3d}: plateau {g * C / 1e-8:5.1f}, time to S/N 5 = {hours_to_snr(sim):.1f} h")
sim.reset()
"""),
    md(r"""
### 1.3 — Which filter?

With ppgain 100, compute the time to S/N 5 in every filter (`esc_etc.FILTERS` has the names B1 to
B6 and R1 to R6). Which three are fastest, and why?
"""),
    sol("""
rows = []
for name in ["B1", "B2", "B3", "B4", "B5", "B6", "R1", "R2", "R3", "R4", "R5", "R6"]:
    s = Simulation.from_default(filter=name, hoststarmag=4.83, hoststar_band="johnson_v", planetdeltamag=dm, contrast=1e-8, ppgain=100, separation=0.52)
    rows.append((name, s.telescope.primary_filter.to_value(u.nm), hours_to_snr(s)))
for name, lam, h in sorted(rows, key=lambda r: r[2]):
    print(f"{name}: {lam:4.0f} nm, {h:7.1f} h")
# The wide filters (R3 = F659W, B4 = F450W) collect the most planet photons; the model has no colour, so only the bandwidth matters.
"""),
    md(r"""
### 1.4 — Twice as far

Move the system to 20 pc: the contrast is unchanged, the separation halves, and the host is 1.5 mag
fainter. Time to S/N 5 in R3 at ppgain 100? Which of the three changes hurts most? (Test them one at
a time.)
"""),
    sol("""
sim = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v", planetdeltamag=dm, contrast=1e-8, ppgain=100, separation=0.52)
print(f"10 pc:                 {hours_to_snr(sim):.1f} h")
sim.update(coronagraph__separation=0.26); print(f"separation halved:     {hours_to_snr(sim):.1f} h"); sim.reset()
sim.update(scene__star__mag=4.83 + 1.5); print(f"host 1.5 mag fainter:  {hours_to_snr(sim):.1f} h"); sim.reset()
sim.update(coronagraph__separation=0.26, scene__star__mag=4.83 + 1.5); print(f"both (20 pc):          {hours_to_snr(sim):.1f} h"); sim.reset()
"""),
    ai("Add a loop over distance from 3 to 20 pc for the Jupiter twin, with the separation and host magnitude following, and plot the time to S/N 5 against distance for ppgain 30 and 100. Mark where the separation drops below the IWA from notebook 03.",
       "Then ask it where Saturn (9.5 AU, albedo 0.5) would sit on the same plot."),
]

EX2 = [
    md(r"""
### 2.1 — The grid

For a V = 5 host in R3 (raw contrast $10^{-8}$, ppgain 30), compute the time to S/N 5 on a grid of
planet contrast ($10^{-10}$ to $10^{-7}$, 25 steps) and separation (0.05" to 0.9", 25 steps).
Show it as an image with log colour scale (hours), and overlay the contrast floor and the 50 %
throughput IWA.
"""),
    sol("""
sim = Simulation.from_default(filter="R3", hoststarmag=5.0, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=30, separation=0.4)
contrasts = np.logspace(-10, -7, 25); seps = np.linspace(0.05, 0.9, 25)
hours = np.full((contrasts.size, seps.size), np.nan)
for i, c in enumerate(contrasts):
    for j, sp in enumerate(seps):
        sim.update(scene__planet__deltamag=-2.5 * np.log10(c), coronagraph__separation=sp)
        hours[i, j] = hours_to_snr(sim)
sim.reset()
cg = sim.coronagraph
lamD = (cg.primary_filter / cg.diameter_primary).to_value(u.arcsec, equivalencies=u.dimensionless_angles())
IWA = (cg._lamD * lamD)[np.argmax(cg._throughput >= 0.5 * cg._throughput.max())]
from matplotlib.colors import LogNorm
fig, ax = plt.subplots(figsize=(8, 5.5))
im = ax.pcolormesh(seps, contrasts, hours, norm=LogNorm(1e-2, 1e3), cmap="viridis_r", shading="nearest")
ax.contour(seps, contrasts, np.nan_to_num(hours, nan=1e9), levels=[24], colors="w", linestyles="--")
ax.axhline(5e-8 / 30, color="C3", ls=":", label="contrast floor 5 C_raw / ppgain")
ax.axvline(IWA, color="C1", ls=":", label=f"IWA {IWA:.2f}\\"")
ax.set(yscale="log", xlabel="separation [arcsec]", ylabel="planet contrast", title="time to S/N 5 [h]; white dashed = one day")
fig.colorbar(im, ax=ax, label="hours"); ax.legend(loc="lower right")
plt.show()
"""),
    guess("where on the grid is an Earth twin (contrast 1e-10 at 0.1\" for a Sun at 10 pc)? Reachable, or NaN?"),
    md(r"""
### 2.2 — Reading the map

Which separation gives the shortest time at contrast $10^{-8}$, and why does the time go *up* again
beyond a few tenths of an arcsecond, if at all? Is an Earth twin ($10^{-10}$ at 0.1") anywhere on
the map?
"""),
    sol("""
i = np.argmin(np.abs(contrasts - 1e-8))
print(f"contrast 1e-8: fastest at {seps[np.nanargmin(hours[i])]:.2f}\\" ({np.nanmin(hours[i]):.2f} h); at 0.9\\": {hours[i, -1]:.2f} h")
# The mask throughput saturates beyond ~0.5", so the time flattens rather than rises: zodi/exozodi are negligible here.
print(f"Earth twin, 1e-10 at 0.1\\": {hours[0, np.argmin(np.abs(seps - 0.1))]} (NaN = below the floor of {5e-8 / 30:.1e})")
"""),
    md(r"""
### 2.3 — What would it take?

Does any combination of raw contrast ($10^{-8}$, $10^{-9}$, $10^{-10}$) and ppgain (30, 100, 300)
put a $10^{-10}$ planet at 0.1" within one day for this host? If not, what is the limit once the
speckle floor is out of the way?
"""),
    sol("""
sim.update(scene__planet__deltamag=25.0, coronagraph__separation=0.1)
print(f"{'raw':>7} " + "".join(f"{f'ppgain {g}':>12}" for g in (30, 100, 300)))
for raw in (1e-8, 1e-9, 1e-10):
    row = []
    for g in (30, 100, 300):
        sim.update(coronagraph__raw_dh_contrast=raw, coronagraph__ppgain=g)
        row.append(hours_to_snr(sim))
    print(f"{raw:7.0e} " + "".join(f"{h:12.1f}" for h in row) + "   hours")
sim.reset()
# None: once the floor is cleared the time hardly moves with ppgain or raw contrast. At 0.1" the mask
# transmits 17 % and a 1e-10 planet gives ~1e-3 e-/s: photon noise from zodi, dark and read noise set
# a limit of thousands of hours. Earths need a brighter (closer) host, a larger separation, or a bigger telescope.
"""),
    ai("Re-draw the map for raw contrast 1e-9 and overlay the known RV giants from lazuli/esc/tutorial/data/12_nearby_rv_giants.csv (exercise 4 computes their contrast and separation).",
       "Ask it to colour the points by host V magnitude, since the grid is for V = 5 only."),
]

EX3 = [
    md(r"""
### 3.0 — A broken cell

The cell below is broken on purpose. Run it, paste the traceback into Jupyter AI (or read it
yourself), fix it, and keep the fixed version: it defines the helper the rest of the exercise uses.
"""),
    bug("""
def safe_frame(sim, max_frame=1000):
    \"\"\"Frame time: max_frame, or half the saturation time if that is shorter.\"\"\"
    return min(max_frame, 0.5 * sim.saturation_time())

sim = Simulation.from_default(filter="R3", hoststarmag=-1.4, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
print(safe_frame(sim))
""", """
def safe_frame(sim, max_frame=1000 * u.s):
    \"\"\"Frame time: max_frame, or half the saturation time if that is shorter.\"\"\"
    # fixed: saturation_time() is an astropy Quantity in seconds, so max_frame must be one too
    return min(u.Quantity(max_frame, u.s), 0.5 * sim.saturation_time())

sim = Simulation.from_default(filter="R3", hoststarmag=-1.4, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
print(safe_frame(sim))
"""),
    md(r"""
### 3.1 — Sirius, Pollux and a V = 5 star

For hosts of V = -1.4, 1.1 and 5.0 with a $10^{-8}$ planet at 0.4", tabulate the saturation time,
the frame time from `safe_frame`, the S/N after one hour and the time to S/N 5.
"""),
    sol("""
print(f"{'V':>5} {'sat. time':>12} {'frame':>9} {'S/N 1 h':>8} {'t(S/N 5)':>9}")
for V in (-1.4, 1.1, 5.0):
    sim.update(scene__star__mag=V)
    ft = safe_frame(sim)
    print(f"{V:5.1f} {sim.saturation_time():12.0f} {ft:9.1f} {sim.get_snr(3600, ft)['snr']:8.2f} {sim.get_int_time_for_snr(5, ft)['int_time_continuous'][0].to_value(u.hr):9.2f} h")
sim.reset()
"""),
    guess("for the V = 5 host, how much S/N is lost in one hour by using 10 s frames instead of 1000 s: 5 %, 30 % or a factor 3?"),
    md(r"""
### 3.2 — The cost of short frames

For the V = 5 host, S/N in one hour with 1, 10, 100 and 1000 s frames. At which frame time does the
read noise fall below 10 % of the total variance? (Reconstruct the read term as in notebook 04:
$n_\mathrm{pix}\,\sigma_\mathrm{read}^2\,t/t_\mathrm{frame}$.)
"""),
    sol("""
sim.update(scene__star__mag=5.0)
s = sim.sensor
for ft in (1, 10, 100, 1000):
    r = sim.get_snr(3600, ft)
    read = (s.read_noise ** 2 * s.num_psf_pixels * (3600 * u.s / (ft * u.s))).to_value(u.electron)
    print(f"frame {ft:5d} s: S/N {r['snr']:.2f}; read noise {read / r['noise_e'] ** 2:6.1%} of the variance")
sim.reset()
"""),
    md(r"""
### 3.3 — Sirius for real

For Sirius the ETC's saturation time is the planet-aperture estimate. Suppose the host halo limits
frames to 1 s. S/N after one hour, and time to S/N 5, for a $10^{-8}$ planet at 0.4"?
"""),
    sol("""
sim.update(scene__star__mag=-1.4)
print(f"1 s frames: S/N in 1 h = {sim.get_snr(3600, 1)['snr']:.2f}, time to S/N 5 = {sim.get_int_time_for_snr(5, 1)['int_time_continuous'][0].to(u.min):.1f}")
sim.reset()
"""),
    ai("The ETC's saturation_time() only models the planet location at the dark-hole contrast (esc-etc issue #33). Using sim.count_rate_components().host, sim.sensor.peak_pixel_fraction and the mask throughput at the separation, estimate the frame time at which the host's own residual halo saturates a pixel, and compare with saturation_time().",
       "Ask it to state what it assumes about the halo profile outside the dark hole."),
]

EX4 = [
    md(r"""
### 4.1 — The sample

Load `12_nearby_rv_giants.csv` (RV planets with $0.3 < M \sin i < 15\,M_J$, $a > 1$ AU, $d < 20$ pc,
host $V < 7$, from the NASA Exoplanet Archive). For each planet compute the maximum separation
$a/d$ in arcsec and the reflected-light contrast at quadrature, $C = A_g (R_p/a)^2 / \pi$ with
$A_g = 0.5$ and the archive radius (1 $R_J$ where missing).
"""),
    code("""
import pandas as pd
from pathlib import Path
csv = next(d / "data" / "12_nearby_rv_giants.csv" for d in Path.cwd().parents if (d / "data" / "12_nearby_rv_giants.csv").exists())
df = pd.read_csv(csv)
print(len(df), "planets")
df[["pl_name", "pl_orbsmax", "pl_bmassj", "pl_radj", "sy_dist", "sy_vmag", "st_spectype"]].head()
"""),
    sol("""
from astropy.constants import R_jup, au
R_p = df.pl_radj.fillna(1.0).values * R_jup
a = df.pl_orbsmax.values * au
df["sep_arcsec"] = df.pl_orbsmax / df.sy_dist                     # AU / pc = arcsec
df["contrast"] = (0.5 / np.pi * (R_p / a) ** 2).decompose().value
print(f"contrast {df.contrast.min():.1e} to {df.contrast.max():.1e}; separation {df.sep_arcsec.min():.2f} to {df.sep_arcsec.max():.2f} arcsec")
"""),
    md(r"""
### 4.2 — A cell with a bug

The cell below computes the time to S/N 5 for every planet. It runs, but the numbers are absurd:
every planet is detected in seconds. Find the bug, fix it, and keep going.
"""),
    bug("""
sim = Simulation.from_default(filter="R3", hoststarmag=5.0, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
edge = sim.coronagraph._lamD.max() * (sim.coronagraph.primary_filter / sim.coronagraph.diameter_primary).to_value(u.arcsec, equivalencies=u.dimensionless_angles())

def time_to_snr5(V, contrast, sep, ppgain=10):
    if sep > edge:
        return np.nan                                             # beyond the tabulated dark hole
    sim.update(scene__star__mag=V, scene__planet__deltamag=2.5 * np.log10(contrast),
               coronagraph__separation=sep, coronagraph__ppgain=ppgain)
    h = hours_to_snr(sim)
    sim.reset()
    return h

df["t_hr"] = [time_to_snr5(r.sy_vmag, r.contrast, r.sep_arcsec) for r in df.itertuples()]
print(df[["pl_name", "sy_vmag", "sep_arcsec", "contrast", "t_hr"]].sort_values("t_hr").head(8).to_string(index=False))
""", """
sim = Simulation.from_default(filter="R3", hoststarmag=5.0, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=10, separation=0.4)
edge = sim.coronagraph._lamD.max() * (sim.coronagraph.primary_filter / sim.coronagraph.diameter_primary).to_value(u.arcsec, equivalencies=u.dimensionless_angles())

def time_to_snr5(V, contrast, sep, ppgain=10):
    if sep > edge:
        return np.nan                                             # beyond the tabulated dark hole
    sim.update(scene__star__mag=V, scene__planet__deltamag=-2.5 * np.log10(contrast),   # fixed: the sign; delta mag is positive (planet fainter)
               coronagraph__separation=sep, coronagraph__ppgain=ppgain)
    h = hours_to_snr(sim)
    sim.reset()
    return h

df["t_hr"] = [time_to_snr5(r.sy_vmag, r.contrast, r.sep_arcsec) for r in df.itertuples()]
print(df[["pl_name", "sy_vmag", "sep_arcsec", "contrast", "t_hr"]].sort_values("t_hr").head(8).to_string(index=False))
"""),
    md(r"""
### 4.3 — Inside the working angle

Add a column `in_wa` for planets between the 50 %-throughput IWA and the table edge. How many
planets reach S/N 5 within a day *and* sit in the working angle at ppgain 10? And at ppgain 30?
"""),
    sol("""
cg = sim.coronagraph
lamD = (cg.primary_filter / cg.diameter_primary).to_value(u.arcsec, equivalencies=u.dimensionless_angles())
IWA = (cg._lamD * lamD)[np.argmax(cg._throughput >= 0.5 * cg._throughput.max())]
df["in_wa"] = (df.sep_arcsec >= IWA) & (df.sep_arcsec <= edge)
df["t_hr_pp30"] = [time_to_snr5(r.sy_vmag, r.contrast, r.sep_arcsec, 30) for r in df.itertuples()]
for col in ("t_hr", "t_hr_pp30"):
    ok = df.in_wa & (df[col] <= 24)
    print(f"{col}: {ok.sum()} planets in a day inside the working angle -> {', '.join(df[ok].sort_values(col).pl_name)}")
print(f"beyond the table edge ({edge:.2f}\\"): {', '.join(df[df.sep_arcsec > edge].pl_name)}")
"""),
    md(r"""
### 4.4 — The picture

Plot contrast against separation for all planets, coloured by the time to S/N 5 (log scale), with
the IWA, the table edge and the contrast floor marked, and the names on the points.
"""),
    sol("""
from matplotlib.colors import LogNorm
fig, ax = plt.subplots(figsize=(10, 6.5))
ax.axvspan(0.03, IWA, color="0.92", lw=0); ax.axvspan(edge, 6, color="0.95", hatch="//", edgecolor="0.8", lw=0)
ax.axhline(5e-8 / 10, color="0.4", ls="--"); ax.text(5, 5.5e-9, "floor, ppgain 10", ha="right", color="0.4")
good = df.t_hr.notna()
sc = ax.scatter(df.sep_arcsec[good], df.contrast[good], c=df.t_hr[good], norm=LogNorm(0.003, 300), cmap="viridis_r", s=120, edgecolor="k")
ax.scatter(df.sep_arcsec[~good], df.contrast[~good], facecolor="white", edgecolor="0.5", s=80)
for r in df.itertuples():
    ax.annotate(r.pl_name, (r.sep_arcsec, r.contrast), xytext=(4, 4), textcoords="offset points", fontsize=8)
fig.colorbar(sc, ax=ax, label="time to S/N 5 [h]")
ax.set(xscale="log", yscale="log", xlim=(0.03, 6), ylim=(8e-11, 7e-8), xlabel="maximum separation a/d [arcsec]", ylabel="reflected-light contrast at quadrature",
       title="RV giants within 20 pc through the ESC (R3, raw 1e-8, ppgain 10)")
plt.show()
"""),
    ai("The separations above are maximum elongations for circular orbits. For the three planets with eccentricity above 0.3 in the table, compute the range of projected separations over the orbit (ignoring inclination) and say whether they ever leave the working angle.",
       "Then ask it to draft the observing-calendar extension: separation and phase angle on real dates, from an astrometric orbit."),
]

EX5 = [
    md(r"""
### 5.1 — The sweep

For a Sun twin at 10 pc with a planet at 0.4" (4 AU), R3, raw contrast $10^{-8}$, ppgain 30: sweep
the exozodi level from 0.1 to $10^4$ zodis (1 zodi = 22 V mag/arcsec² at 1 AU, $r^{-2}$) for
planet contrasts $3\times10^{-9}$, $10^{-8}$ and $3\times10^{-8}$. Plot the time to S/N 5 relative
to the no-exozodi time, and find where each curve doubles.
"""),
    sol("""
from scipy.optimize import brentq
sim = Simulation.from_default(filter="R3", hoststarmag=4.83, hoststar_band="johnson_v", planetdeltamag=20, contrast=1e-8, ppgain=30, separation=0.4)
r_AU = 0.4 * 10.0
sb = lambda n: 22.0 - 2.5 * np.log10(n) + 5 * np.log10(r_AU)

def hours_at(n_zodi, contrast, raw=1e-8, ppgain=30):
    sim.update(scene__exozodi__mag=99.0 if n_zodi == 0 else sb(n_zodi), scene__exozodi__band="johnson_v",
               scene__planet__deltamag=-2.5 * np.log10(contrast), coronagraph__raw_dh_contrast=raw, coronagraph__ppgain=ppgain)
    h = hours_to_snr(sim); sim.reset(); return h

zodis = np.geomspace(0.1, 1e4, 30)
fig, ax = plt.subplots(figsize=(7, 4.5))
n2 = {}
for c in (3e-9, 1e-8, 3e-8):
    t0 = hours_at(0, c)
    ratio = np.array([hours_at(n, c) for n in zodis]) / t0
    n2[c] = 10 ** brentq(lambda lg: hours_at(10 ** lg, c) / t0 - 2, -1, 5)
    ax.loglog(zodis, ratio, "o-", label=f"planet {c:.0e}: t0 = {t0:.2f} h, doubles at {n2[c]:.0f} zodi")
    print(f"planet {c:.0e}: no exozodi {t0:.2f} h; doubles at {n2[c]:.0f} zodi")
ax.axhline(2, color="0.5", ls="--"); ax.set(xlabel="exozodi [zodis]", ylabel="time to S/N 5 / no-exozodi time"); ax.legend()
plt.show()
"""),
    guess("does the post-processing gain change the zodi level at which the time doubles? Yes, no, or only for faint planets?"),
    md(r"""
### 5.2 — Post-processing gain

Repeat the $10^{-8}$ curve with ppgain 10 and 100. Does the ratio change? Explain from the
integration-time formula (notebook 04 or `esc_etc/noise.py`).
"""),
    sol("""
c = 1e-8
ref = np.array([hours_at(n, c, ppgain=30) for n in zodis]) / hours_at(0, c, ppgain=30)
for g in (10, 100):
    ratio = np.array([hours_at(n, c, ppgain=g) for n in zodis]) / hours_at(0, c, ppgain=g)
    print(f"ppgain {g:3d}: t0 = {hours_at(0, c, ppgain=g):.2f} h, max |ratio - ratio(ppgain 30)| = {np.max(np.abs(ratio - ref)):.1e}")
# t = (S + B) / [(S/SNR)^2 - M^2]: exozodi only adds to B in the numerator, ppgain only changes M in the denominator, so the ratio is independent of ppgain.
"""),
    md(r"""
### 5.3 — The habitable zone of a nearby star

Repeat 5.1 for tau Ceti (V = 3.5, 3.65 pc) with a planet at 0.7 AU (0.19"), contrast
$10^{-9}$ (a large, bright super-Earth), ppgain 100. Where does the time double now, and why is the
number so different?
"""),
    sol("""
sim = Simulation.from_default(filter="R3", hoststarmag=3.5, hoststar_band="johnson_v", planetdeltamag=22.5, contrast=1e-8, ppgain=100, separation=0.7 / 3.65)
r_AU = 0.7
t0 = hours_at(0, 1e-9, ppgain=100)
ratio = np.array([hours_at(n, 1e-9, ppgain=100) for n in zodis]) / t0
print(f"tau Ceti HZ: no exozodi {t0:.1f} h; 1 zodi = {sb(1):.2f} V mag/arcsec²; doubles at {np.interp(2, ratio, zodis):.0f} zodi")
# At 0.7 AU each zodi is (4/0.7)^2 = 33 times brighter than at 4 AU, and the planet is far fainter, so the dust competes much sooner.
"""),
    ai("Add a systematic exozodi residual to the noise model: a fraction f of the exozodi rate that does not average down, entering like the speckle floor M. For f = 0.01 and 0.1, how does the tolerance in 5.3 change?",
       "Ask it to subclass AnalyticCoronagraphNoiseModel rather than patch the package."),
]

EX6 = [
    md(r"""
This exercise has no solution key beyond a worked example. Work with Jupyter AI as a pair
programmer: you supply the astronomy, it supplies the code, you check the numbers.

### 6.1 — Pick a target

A known planet (the RV giants of exercise 4, a directly imaged companion, a hypothetical Earth
around alpha Cen A), or a disk. Write down: host V magnitude and distance, planet separation or
semi-major axis, and how you get a contrast (albedo and radius, or a measured one).

### 6.2 — Describe it to the agent

A prompt that works: *"I want to image `<planet>` around `<host>` (V = `<mag>`, `<d>` pc) with the
Lazuli ESC. Using esc_etc, build Simulation.from_default with filter R3, hoststar_band 'johnson_v',
the planet's delta magnitude from a contrast of `<C>`, raw contrast 1e-8 and ppgain 30, at a
separation of `<sep>` arcsec. Report the time to S/N 5 with 1000 s frames capped at half the
saturation time, and whether the separation is inside the mask's tabulated range."*

Check what it does against notebooks 03 and 04: does it handle NaN (below the floor)? Does it check
the separation against the table edge before calling `update`?
"""),
    sol("""
# Worked example: eps Eri b (V = 3.73, 3.2 pc, a = 3.5 AU -> 1.1", contrast ~4e-9 for 0.5 albedo and 1 R_J).
sim = Simulation.from_default(filter="R3", hoststarmag=3.73, hoststar_band="johnson_v", planetdeltamag=21, contrast=1e-8, ppgain=30, separation=0.4)
cg = sim.coronagraph
edge = cg._lamD.max() * (cg.primary_filter / cg.diameter_primary).to_value(u.arcsec, equivalencies=u.dimensionless_angles())
sep = 3.5 / 3.2
print(f"eps Eri b at {sep:.2f}\\" is {'inside' if sep <= edge else 'beyond'} the tabulated dark hole (edge {edge:.2f}\\")")
# The ETC cannot model it there. What the planet would need: bring it to the edge and ask.
sim.update(coronagraph__separation=edge * 0.99, scene__planet__deltamag=-2.5 * np.log10(4e-9))
print(f"at the table edge: time to S/N 5 = {hours_to_snr(sim):.1f} h (ppgain 30); plateau {30 * 4e-9 / 1e-8:.1f}")
sim.reset()
"""),
    md(r"""
### 6.3 — One plot, one number

Produce the one plot that answers your question (S/N versus time, time versus contrast, a map, a
sweep over ppgain) and the one number you would put in a proposal.
"""),
    sol("""
fig, ax = sim.plot_snr_vs_time(sweep={"coronagraph__ppgain": [10, 30, 100]})
ax.set_title("eps Eri b at the edge of the modelled dark hole")
plt.show()
"""),
    md(r"""
### 6.4 — What was wrong

Ask the agent to list every assumption it made that you did not state (albedo, phase, radius,
flat spectra, EOL throughput, no jitter, the raw contrast being flat across the dark hole). Which
would change the answer by more than a factor of two?
"""),
    ai("List every assumption you made in 6.2 that I did not state, and for each one estimate how much the time to S/N 5 would change if it were wrong."),
]

# =====================================================================================
# README
# =====================================================================================

README = r"""
# ESC hands-on: the coronagraph exposure time calculator

Requirements: `esc_etc` (plus `matplotlib`, `pandas`, `scipy` and `jupyter`), installed on the
symposium JupyterHub. Nothing needs the network. A web version of the ETC is at
<https://simulators.schmidtobservatorysystem.org/esc/>.

**Jupyter AI.** The notebooks assume the Jupyter AI chat is open in the side panel. Boxes marked 🤖
suggest prompts; boxes marked ✏️ ask you to guess a number before computing it. Two exercises contain
a deliberately broken cell.

## Tutorials

| notebook | content |
|---|---|
| [01 — The ETC in one line](01_etc_in_one_line.ipynb) | `Simulation.from_default()`, `get_snr()`, `get_int_time_for_snr()`, the count-rate budget, S/N versus time and the plateau |
| [02 — Components and filters](02_components_and_filters.ipynb) | `Telescope`, `Sensor`, `Scene`, `Coronagraph`, `update()` / `reset()`, magnitude bands and systems, the twelve filters, the aperture |
| [03 — Contrast, gain and separation](03_contrast_gain_separation.ipynb) | raw contrast, post-processing gain, the mask throughput and IWA, time to S/N 5 versus contrast, RDI |
| [04 — Frame time and saturation](04_frame_time_saturation.ipynb) | read noise per frame, whole-frame inversion, `saturation_time()`, bright hosts, the noise budget |
| [05 — Zodi and exozodi](05_zodi_and_exozodi.ipynb) | how the backgrounds are parameterized, zodis to surface brightness, the exozodi sweep |

## Exercises

| exercise | science | covers | difficulty |
|---|---|---|---|
| [1 — A Jupiter twin](exercises/ex1_jupiter_twin.ipynb) | reflected light | 01–02 | ★☆☆☆☆ |
| [2 — The detectability map](exercises/ex2_detectability_map.ipynb) | contrast and working angle | 03 | ★★☆☆☆ |
| [3 — Bright hosts and frame times](exercises/ex3_bright_hosts_frames.ipynb) | Sirius, Pollux | 04 | ★★☆☆☆ |
| [4 — The known RV giants](exercises/ex4_rv_giants.ipynb) | target list | 01–04 | ★★★☆☆ |
| [5 — Exozodi tolerance](exercises/ex5_exozodi_tolerance.ipynb) | dust | 05 | ★★★☆☆ |
| [6 — Bring your own target](exercises/ex6_bring_your_own_target.ipynb) | yours | all | open |

Solutions are in [`exercises/solutions/`](exercises/solutions/). The two science-case notebooks
these grew out of are in [`backup/`](backup/); the other Lazuli science cases (IFS and WCC) are in
[`../../science_gallery/`](../../science_gallery/).

To regenerate the notebooks: `python build_notebooks.py`, then execute them with `jupyter nbconvert`.
"""


if __name__ == "__main__":
    write(HERE / "01_etc_in_one_line.ipynb", T01)
    write(HERE / "02_components_and_filters.ipynb", T02)
    write(HERE / "03_contrast_gain_separation.ipynb", T03)
    write(HERE / "04_frame_time_saturation.ipynb", T04)
    write(HERE / "05_zodi_and_exozodi.ipynb", T05)

    exercise("ex1_jupiter_twin", "Exercise 1 — A Jupiter twin", "01–02", "★☆☆☆☆",
             "The simplest reflected-light target: a Jupiter twin around a Sun twin. How long does the ESC need, and "
             "what decides it?", EX1)
    exercise("ex2_detectability_map", "Exercise 2 — The detectability map", "03", "★★☆☆☆",
             "Every planet is a point in the contrast-separation plane. Map the time to S/N 5 over that plane and read "
             "off where the coronagraph's limits lie.", EX2)
    exercise("ex3_bright_hosts_frames", "Exercise 3 — Bright hosts and frame times", "04", "★★☆☆☆",
             "The best coronagraph targets are the brightest stars in the sky, and those saturate. How short must the "
             "frames be, and what does that cost?", EX3)
    exercise("ex4_rv_giants", "Exercise 4 — The known RV giants", "01–04", "★★★☆☆",
             "Radial-velocity surveys have found dozens of cold giants around bright stars within 20 pc. Which of them "
             "could the ESC image in reflected light within a day?", EX4)
    exercise("ex5_exozodi_tolerance", "Exercise 5 — Exozodi tolerance", "05", "★★★☆☆",
             "Warm dust in the target system adds background right where the planet is. How much can Lazuli tolerate "
             "before detection time doubles?", EX5)
    exercise("ex6_bring_your_own_target", "Exercise 6 — Bring your own target", "all", "open",
             "Your science, the ESC, and Jupyter AI as a pair programmer.", EX6)

    (HERE / "README.md").write_text(README.strip() + "\n")
    print("wrote README.md")
