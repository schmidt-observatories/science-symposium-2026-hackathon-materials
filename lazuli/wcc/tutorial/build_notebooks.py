#!/usr/bin/env python
"""Build the WCC tutorial notebooks, exercises and solutions.

    cd lazuli/wcc/tutorial
    python build_notebooks.py          # writes the .ipynb files (no outputs)
    jupyter nbconvert --to notebook --execute --inplace *.ipynb exercises/*.ipynb exercises/solutions/*.ipynb

Exercises and solutions share one definition: a solution code cell becomes `# your code here`
in the exercise notebook.
"""
from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = Path(__file__).parent
META = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}}

SETUP = """
import numpy as np
import matplotlib.pyplot as plt
import wcc_etc
from wcc_etc import Simulation, get_scene

wcc_etc.set_wcc_style()
"""

SETUP_SIM = """
import numpy as np
import matplotlib.pyplot as plt
from astropy.visualization import simple_norm
from wcc_etc import plot_image_mpl
from wcc_sim import simulate_field
from wcc_sim.catalog import query_gaia
from wcc_phot import run_photometry
from wcc_phot.centroid import centroid_stars
"""

LIMITING_MAG = '''
def limiting_mag(sim, t, snr_target=5, mags=np.arange(16, 32.01, 0.25), **kw):
    """Magnitude at which the SNR in t seconds falls to snr_target; NaN if saturated or not bracketed."""
    r = sim.get_image_snr(t, mags=mags, warn=False, **kw)
    snr = np.where(r["saturated"], np.nan, r["snr"])
    ok = np.isfinite(snr)
    if ok.sum() < 2 or not (snr[ok].max() > snr_target > snr[ok].min()):
        return np.nan
    return float(np.interp(np.log10(snr_target), np.log10(snr[ok][::-1]), mags[ok][::-1]))
'''

CHOOSE_READS = '''
READS = (1, 2, 3, 6, 10, 30, 60, 120, 240)

def choose_reads(sim, t, reads=READS, **kw):
    """Smallest read count whose per-frame image has no saturated pixel; (None, last result) if none works."""
    for n in reads:
        r = sim.get_image_snr(t, n_reads=n, warn=False, **kw)
        if not np.any(r["saturated"]):
            return n, r
    return None, r
'''


def md(s):
    return new_markdown_cell(s.strip())


def code(s):
    return new_code_cell(s.strip())


def ai(prompt, then=None):
    """A boxed suggestion of what to ask Jupyter AI."""
    s = f"> 🤖 **Ask Jupyter AI:** *{prompt.strip()}*"
    if then:
        s += f"\n>\n> {then.strip()}"
    return md(s)


def guess(what):
    """A prediction box: guess before you run."""
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
# 01 — wcc_etc as an exposure time calculator

`wcc_etc` is the exposure time calculator (ETC) for the **Wide-field Context Camera (WCC)** on the
Lazuli Space Observatory: a 3.065 m unobscured telescope feeding a Sony IMX455 CMOS sensor at
**16.9 mas per pixel**, with u, g, r, i, z, a wide "bb" filter and three H-alpha filters.
The first thing it is used for is to answer *"what SNR do I get in t seconds, and how long do I
need for SNR = 10?"*

A **web version** of the same calculator is at <https://simulators.schmidtobservatorysystem.org/wcc/>:
use it for a quick number, and these notebooks when you want sweeps, plots, your own spectra and
simulated images.

In this notebook:
1. a scene and a simulation: `get_scene()` and `Simulation.from_sensorfilter()`,
2. SNR for an exposure time, and exposure time for an SNR,
3. sweeps over exposure time and magnitude, and the 5 sigma limiting magnitude,
4. the sensor:filter labels.

**Jupyter AI.** These notebooks are written to be run with the Jupyter AI chat open in the side
panel (the sparkle icon). Boxes marked 🤖 suggest things to ask it. It can see the cell you have
selected, so "explain this cell" or pasting a traceback works well. Boxes marked ✏️ ask you to guess
a number before computing it.
"""),
    code(SETUP),
    md(r"""
***
## 1. A scene and a simulation

A **scene** is a source (a spectrum with a magnitude), optionally a host galaxy, and a background
(zodiacal light by default). A **simulation** is a scene on a telescope + sensor + filter.
The label `"zwo:r"` means the IMX455 sensor (ZWO camera) in the r filter.

`get_scene` normalizes to Johnson V (Vega) unless told otherwise: always give `bandpass` and
`magsys` explicitly, here SDSS r in AB.
"""),
    code("""
scene = get_scene("G2V", mag=20, bandpass="sdss_r", magsys="abmag")
sim = Simulation.from_sensorfilter("zwo:r", scene)
sim.describe()
"""),
    md(r"""
`describe()` lists everything the calculation uses: the 3.065 m aperture, the 10 mas pointing
jitter, the sensor read noise, dark current and well depth at this gain setting, and the scene.
"""),
    md(r"""
***
## 2. SNR for an exposure time, exposure time for an SNR

`get_image_snr(t)` renders the PSF on the pixel grid, places an aperture on it, and returns a
dictionary. `snr` is the number you want; the others say how it was obtained.
"""),
    code("""
r = sim.get_image_snr(60)
for k, v in r.items():
    print(f"{k:18s} {v}")
"""),
    md(r"""
- `signal_e`, `noise_e`: electrons in the aperture, and the noise (photon + background + dark + read).
- `r_aper_mas`, `n_pix`, `enclosed_fraction`: the aperture (radius in milliarcseconds, pixels inside,
  fraction of the PSF it encloses). Notebook 04 shows how to change it.
- `saturated`, `n_saturated`: whether any pixel exceeds the well depth. Notebook 02 is about this.

The inverse question, the exposure time for a target SNR:
"""),
    code("""
r10 = sim.get_image_exptime_for_snr(10)
r100 = sim.get_image_exptime_for_snr(100)
print(f"SNR = 10 in {r10['time_s']:.2f} s, SNR = 100 in {r100['time_s']:.1f} s (ratio {r100['time_s'] / r10['time_s']:.0f})")
"""),
    md(r"""
A factor 10 in SNR costs a factor ~100 in time, as expected when the source dominates the noise
($\mathrm{SNR} \propto \sqrt{t}$). Notebook 02 shows when it does not.
"""),
    md(r"""
***
## 3. Sweeps: SNR versus exposure time and magnitude

The simulation has plot helpers for the common sweeps. `plot_snr` takes an array of exposure times.
"""),
    code("""
fig, ax = sim.plot_snr(np.logspace(0, 3.5, 60))
ax.set(xscale="log", yscale="log", title="G2V, r = 20 (AB), zwo:r")
plt.show()
"""),
    md(r"""
Passing `mags=` to `get_image_snr` sweeps the source magnitude at fixed exposure time: the result
dictionary then holds arrays. The 5 sigma **limiting magnitude** is where the SNR curve crosses 5.
`limiting_mag` below interpolates that crossing; it returns NaN rather than a guess when the
curve is saturated or does not bracket the target. Keep this helper, the exercises use it.
"""),
    code(LIMITING_MAG),
    guess("what is the 5 sigma point-source depth of WCC in r in a single 300 s exposure? (AB magnitude)"),
    code("""
mags = np.arange(16, 30.01, 0.5)
t = 300
r = sim.get_image_snr(t, mags=mags, warn=False)
depth = limiting_mag(sim, t)

fig, ax = plt.subplots(figsize=(6.5, 4))
ax.semilogy(mags, r["snr"], "o-")
ax.axhline(5, color="0.5", lw=1)
ax.axvline(depth, color="C3", ls=":", label=f"5 sigma at r = {depth:.2f}")
ax.set(xlabel="source r magnitude (AB)", ylabel=f"SNR in {t} s", title="G2V point source, zwo:r")
ax.legend()
plt.show()
print(f"5 sigma depth in {t} s: r = {depth:.2f} (AB)")
"""),
    md(r"""
***
## 4. The sensor:filter labels

`from_sensorfilter` accepts these labels (an unknown label raises an error that lists them):

| label | sensor | filter | PSF |
|---|---|---|---|
| `zwo:u` `zwo:g` `zwo:r` `zwo:i` `zwo:z` | IMX455 | SDSS-like broadband | in focus |
| `zwo:bb` | IMX455 | wide "bb" filter | in focus |
| `zwo:halpha2` `zwo:halpha6` `zwo:halpha20` | IMX455 | H-alpha, 20 / 60 / 200 Å wide | in focus |
| `zwo:r+1` `zwo:r-1` | IMX455 | r | defocused by 1 wave (notebook 04) |
| `zwo:bb2` | IMX455 | bb | defocused by 2 waves |
| `qcmos:u` `qcmos:g` `qcmos:i` `qcmos:z` `qcmos:bb` | Hamamatsu qCMOS | broadband | in focus |

The same scene in one other filter:
"""),
    code("""
sim_g = Simulation.from_sensorfilter("zwo:g", scene)
print(f"zwo:g: 5 sigma depth in 300 s = {limiting_mag(sim_g, 300):.2f} (AB)")
"""),
    ai("Turn the cell above into a loop over zwo:u, zwo:g, zwo:r, zwo:i, zwo:z and zwo:bb, and print a table of the 5 sigma depth in 300 s with the filter pivot wavelength.",
       "Then compare with the next cell, which also draws the filter curves."),
    code("""
filters = ["zwo:u", "zwo:g", "zwo:r", "zwo:i", "zwo:z", "zwo:bb"]
fig, ax = plt.subplots(figsize=(9, 4))
print(f"{'filter':8s} {'pivot [A]':>9s} {'5 sigma, 300 s':>14s}")
for f in filters:
    s = Simulation.from_sensorfilter(f, scene)
    wcc_etc.plot_bandpass_mpl(s.sensor, ax=ax, label=f)
    print(f"{f:8s} {s.sensor.bandpass.pivot().value:9.0f} {limiting_mag(s, 300):14.2f}")
ax.set(title="WCC total throughput (telescope + filter + QE)")
ax.legend()
plt.show()
"""),
    md(r"""
***
## Summary

```python
scene = get_scene("G2V", mag=20, bandpass="sdss_r", magsys="abmag")   # source (+ host, + background)
sim   = Simulation.from_sensorfilter("zwo:r", scene)                   # on the WCC, in a filter
sim.get_image_snr(60)["snr"]                                           # SNR in 60 s
sim.get_image_exptime_for_snr(10)["time_s"]                            # seconds for SNR = 10
sim.get_image_snr(300, mags=np.arange(16, 30))["snr"]                  # a magnitude sweep
sim.update(source__mag=22)                                             # change anything, then recompute
```

Next: [02 — the detector](02_detector_saturation_reads.ipynb), where bright stars saturate.
"""),
]

T02 = [
    md(r"""
# 02 — The CMOS detector: saturation and reads

The IMX455 has 3.76 µm pixels and, at the WCC gain setting, a **well depth of about 16 000
electrons** with 3 e- read noise and negligible dark current. With 16.9 mas pixels a star's light is
concentrated on very few pixels, so **saturation, not photon noise, is the first limit for anything
brighter than r ~ 18**. The way out is to split an exposure into several short reads and add them.

In this notebook:
1. the peak pixel versus exposure time, and `is_saturated()`,
2. splitting into reads with `n_reads`, and what it costs,
3. the noise budget: where the variance comes from,
4. the bright limit as a function of magnitude.
"""),
    code(SETUP),
    md(r"""
***
## 1. The peak pixel

`get_peak_pixel(t)` gives the electrons in the brightest pixel; the well depth is in the sensor
metadata. `plot_peak_pixel` draws both against exposure time.
"""),
    code("""
sim = Simulation.from_sensorfilter("zwo:r", get_scene("G2V", mag=14, bandpass="sdss_r", magsys="abmag"))
well = sim.sensor.meta["well_depth"]
for t in (0.25, 1, 10, 60):
    peak = sim.get_peak_pixel(t, units="e-").value
    print(f"{t:6.2f} s: peak pixel {peak:8.0f} e-  ({peak / well:5.2f} of the well)  saturated: {sim.is_saturated(t)}")

fig, ax = sim.plot_peak_pixel(np.logspace(-1, 3, 100))
ax.set(xscale="log", yscale="log", title="G2V, r = 14: peak pixel versus exposure time")
plt.show()
"""),
    md(r"""
The same information is in every `get_image_snr` result as `saturated` and `n_saturated`.
An SNR computed from a saturated image is not a valid number (the ETC still returns it, with a
warning unless `warn=False`), so always check the flag.
"""),
    md(r"""
***
## 2. Splitting into reads

`n_reads=n` splits the exposure into n equal frames that are co-added: each frame holds 1/n of the
charge, and the read noise is paid n times. The sensor's shortest frame is 0.25 s.
"""),
    code("""
t = 60
print(f"{'reads':>5} {'frame [s]':>9} {'peak e-':>8} {'saturated':>9} {'SNR':>7}")
for n in (1, 3, 10, 30, 100, 240):
    r = sim.get_image_snr(t, n_reads=n, warn=False)
    print(f"{n:5d} {t / n:9.2f} {sim.get_peak_pixel(t, n_reads=n, units='e-').value:8.0f} {str(r['saturated']):>9} {r['snr']:7.0f}")
"""),
    md(r"""
For this r = 14 star, 30 reads of 2 s keep every frame below the well, and the SNR barely moves:
the star's own photon noise dominates, and 30 extra read-noise contributions of 3 e- per pixel are
nothing next to it. The picture changes for a faint source.
"""),
    guess("for an r = 24 source in 300 s, by what factor does the SNR drop when the exposure is split into 100 reads of 3 s instead of one read?"),
    code("""
sim.update(source__mag=24.0)
t = 300
for n in (1, 10, 100):
    r = sim.get_image_snr(t, n_reads=n, warn=False)
    print(f"r = 24, {t} s as {n:3d} x {t / n:5.1f} s: SNR = {r['snr']:5.1f}")
"""),
    md(r"""
***
## 3. The noise budget

The variance in the aperture is the sum of four terms:
$\sigma^2 = S + B\,t + D\,n_\mathrm{pix}\,t + n_\mathrm{pix}\,n_\mathrm{reads}\,\sigma_\mathrm{read}^2$
with $S$ the source electrons, $B$ the background rate in the aperture, $D$ the dark current per
pixel. The result dictionary has $S$ (`signal_e`), $n_\mathrm{pix}$ and the co-added read noise
(`read_noise_e` $= \sqrt{n_\mathrm{reads}}\,\sigma_\mathrm{read}$); the dark current is in the
sensor; and the background is what is left in the variance of a source-free image (`mags=40`).
The cell checks the sum against the `noise_e` the ETC reports.
"""),
    code("""
empty = sim.get_image_snr(t, mags=40.0, n_reads=1, warn=False)                  # no source: background + dark + read
dark = sim.sensor.dark_current.value * empty["n_pix"] * t
background = empty["noise_e"] ** 2 - empty["n_pix"] * empty["read_noise_e"] ** 2 - dark
budget = {}
print(f"{'reads':>5} {'source':>8} {'background':>10} {'dark':>6} {'read':>8} {'sum':>8} {'ETC noise^2':>11}   SNR")
for n in (1, 10, 100):
    r = sim.get_image_snr(t, n_reads=n, warn=False)
    budget[n] = {"source": r["signal_e"], "background": background, "dark": dark,
                 "read": r["n_pix"] * r["read_noise_e"] ** 2}                     # read_noise_e already includes sqrt(n_reads)
    total = sum(budget[n].values())
    assert abs(total / r["noise_e"] ** 2 - 1) < 0.03, "budget does not add up"
    print(f"{n:5d} {budget[n]['source']:8.0f} {budget[n]['background']:10.0f} {budget[n]['dark']:6.0f} "
          f"{budget[n]['read']:8.0f} {total:8.0f} {r['noise_e'] ** 2:11.0f} {r['snr']:5.1f}")

fig, ax = plt.subplots(figsize=(6, 3.8))
bottom = np.zeros(3)
for term in ("source", "background", "dark", "read"):
    vals = np.array([budget[n][term] for n in budget])
    ax.bar([str(n) for n in budget], vals, bottom=bottom, label=term)
    bottom += vals
ax.set(xlabel="number of reads", ylabel="variance [e-$^2$]", title=f"r = 24, {t} s, zwo:r")
ax.legend()
plt.show()
"""),
    md(r"""
In space the background is only a few electrons per pixel per minute, so for faint sources the read
noise is the competitor as soon as the frames get short. Deep fields want the **longest frames the
brightest star in the field allows**; bright-star programs can split freely.
"""),
    md(r"""
***
## 4. The bright limit versus magnitude

Planning an observation of a bright star means finding the smallest read split that keeps every
frame unsaturated. Write that helper, or ask for it.
"""),
    ai("Write a function choose_reads(sim, t) that tries n_reads in (1, 2, 3, 6, 10, 30, 60, 120, 240) and returns the first n for which sim.get_image_snr(t, n_reads=n, warn=False)['saturated'] is False, together with the result; return (None, result) if none works.",
       "Compare with the version below, which the exercises reuse."),
    code(CHOOSE_READS),
    code("""
t = 60
mags = np.arange(10, 21, 1.0)
needed, ppm = [], []
print(f"{'r (AB)':>6} {'reads':>5} {'frame [s]':>9} {'SNR':>6} {'ppm/point':>9}")
for m in mags:
    sim.update(source__mag=float(m))
    n, r = choose_reads(sim, t)
    needed.append(n if n else np.nan)
    ppm.append(1e6 / r["snr"] if n else np.nan)
    print(f"{m:6.1f} {str(n) if n else '-':>5} {t / n if n else np.nan:9.2f} {r['snr']:6.0f} {ppm[-1]:9.0f}"
          + ("" if n else "   saturated at every split"))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
ax1.semilogy(mags, needed, "o-", color="C3")
ax1.set(xlabel="r magnitude (AB)", ylabel=f"reads needed per {t} s", title="reads to stay below the well")
ax2.semilogy(mags, ppm, "o-")
ax2.set(xlabel="r magnitude (AB)", ylabel="precision per 60 s point [ppm]", title="photometric precision")
plt.show()
"""),
    md(r"""
Below r ~ 11 even 0.25 s frames clip: those stars need the defocused modes of notebook 04.

***
## 5. What if the sensor were different?

`update_sensor` changes any sensor parameter in place; `reset()` restores the configuration the
simulation was built with (the scene included).
"""),
    code("""
sim.update(source__mag=24.0)
base = sim.get_image_snr(300, n_reads=100, warn=False)["snr"]
sim.update_sensor(read_noise=1.0)
quiet = sim.get_image_snr(300, n_reads=100, warn=False)["snr"]
sim.reset()                                   # back to the configuration the simulation was built with, scene included (r = 14 here)
sim.update(source__mag=24.0)
print(f"r = 24, 100 x 3 s: SNR {base:.1f} with 3 e- read noise, {quiet:.1f} with 1 e-; after reset: {sim.get_image_snr(300, n_reads=100, warn=False)['snr']:.1f}")
"""),
    md(r"""
***
## Summary

```python
sim.get_peak_pixel(t, units="e-")         # brightest pixel; compare with sim.sensor.meta["well_depth"]
sim.is_saturated(t)                       # True / False
sim.get_image_snr(t, n_reads=n)           # split into n frames, co-added
sim.update_sensor(read_noise=1.0); sim.reset()
```

Next: [03 — scenes](03_scenes_spectra_hosts.ipynb): spectra, hosts, backgrounds.
"""),
]

T03 = [
    md(r"""
# 03 — Scenes: spectra, hosts and backgrounds

The SNR of a source depends on what its spectrum does inside the filter, on the galaxy it sits in,
and on the sky behind it. `get_scene` builds all three.

In this notebook:
1. stellar templates and how the magnitude is normalized,
2. parametric spectra: flat, blackbody, power law, emission lines; a spectrum from a file,
3. the background,
4. a transient on a Sersic host, and on a real galaxy at a redshift.
"""),
    code(SETUP),
    md(r"""
***
## 1. Stellar templates

The source name is a Pickles spectral type (`O5V` … `M5V`, giants `K3III`, …). At the same r
magnitude the SNR in r hardly depends on the type; in u and z it does, because the template sets
the colour.
"""),
    code("""
types = ["O5V", "A0V", "F5V", "G2V", "K5V", "M5V", "K3III"]
filters = ["zwo:u", "zwo:r", "zwo:z"]
print(f"{'type':6s}" + "".join(f"{f:>9s}" for f in filters) + "   (SNR in 60 s at r = 20 AB)")
for sp in types:
    scene = get_scene(sp, mag=20, bandpass="sdss_r", magsys="abmag")
    snr = [Simulation.from_sensorfilter(f, scene).get_image_snr(60, warn=False)["snr"] for f in filters]
    print(f"{sp:6s}" + "".join(f"{s:9.1f}" for s in snr))
"""),
    md(r"""
**Normalization.** `mag` is interpreted in `bandpass` and `magsys`. Leaving them out means
Johnson V in Vega magnitudes, whatever the observing filter. A G2V star at V = 20 (Vega) is 0.2
mag brighter in r than an r = 20 (AB) one; for an M dwarf the difference is more than a magnitude.
"""),
    code("""
for sp in ("G2V", "M5V"):
    s_v = Simulation.from_sensorfilter("zwo:r", get_scene(sp, mag=20))                                   # V = 20, Vega (the default)
    s_r = Simulation.from_sensorfilter("zwo:r", get_scene(sp, mag=20, bandpass="sdss_r", magsys="abmag"))
    print(f"{sp}: SNR in r, 60 s: {s_v.get_image_snr(60, warn=False)['snr']:6.1f} at V = 20 (Vega), "
          f"{s_r.get_image_snr(60, warn=False)['snr']:6.1f} at r = 20 (AB)")
"""),
    md(r"""
***
## 2. Parametric spectra, and your own

`"flat"` ($F_\nu$ = constant, i.e. AB colours of zero), `"blackbody"` with `teff`, `"powerlaw"`
with `alpha` ($F_\lambda \propto \lambda^\alpha$), and `"emission"` with a list of lines
(`mag=None`: the line fluxes are absolute). `get_spectrum(as_array=True)` returns the normalized
spectrum for plotting.
"""),
    code("""
import astropy.units as u

scenes = {
    "G2V": get_scene("G2V", mag=21, bandpass="sdss_r", magsys="abmag"),
    "flat": get_scene("flat", mag=21, bandpass="sdss_r", magsys="abmag"),
    "blackbody 3500 K": get_scene("blackbody", teff=3500, mag=21, bandpass="sdss_r", magsys="abmag"),
    "power law alpha = -2": get_scene("powerlaw", alpha=-2, mag=21, bandpass="sdss_r", magsys="abmag"),
}
w = np.arange(3200, 10500, 5) * u.AA
fig, ax = plt.subplots(figsize=(8, 4))
for name, sc in scenes.items():
    wave, flux = sc.source.get_spectrum(as_array=True, wave=w, flux_unit="flam")
    ax.plot(wave, flux, label=name)
ax.set(xlabel="wavelength [Å]", ylabel="$F_\\lambda$ [erg/s/cm²/Å]", yscale="log", title="all normalized to r = 21 (AB)")
ax.legend()
plt.show()

for name, sc in scenes.items():
    print(f"{name:22s} SNR in 60 s: u {Simulation.from_sensorfilter('zwo:u', sc).get_image_snr(60, warn=False)['snr']:5.1f}, "
          f"z {Simulation.from_sensorfilter('zwo:z', sc).get_image_snr(60, warn=False)['snr']:5.1f}")
"""),
    md(r"""
The power law with $\alpha = -2$ gives the same numbers as `"flat"`: $F_\lambda \propto \lambda^{-2}$ is
constant in $F_\nu$, which is what "flat" means in AB magnitudes.
"""),
    md(r"""
An emission-line source: a point source with a 4 Å wide line of $10^{-15}$ erg/s/cm² at H-alpha,
with no continuum. The narrow H-alpha filter and the broad r filter collect the same line photons
but very different amounts of background and continuum (exercise 4).
"""),
    code("""
import warnings
warnings.filterwarnings("ignore", message="spectrum")      # the line spectrum does not cover the whole filter: expected

line = [{"wave": 6563.0, "flux": 1e-15, "fwhm": 4}]
scene_line = get_scene("emission", mag=None, lines=line)
for f in ("zwo:halpha2", "zwo:halpha20", "zwo:r"):
    print(f"{f:13s}: line SNR in 300 s = {Simulation.from_sensorfilter(f, scene_line).get_image_snr(300, warn=False)['snr']:5.1f}")
"""),
    ai("I have my object's spectrum in a two-column text file (wavelength in Å, flux in erg/s/cm²/Å). Show me how to load it with wcc_etc.get_scene_from_file, normalize it to r = 21 AB, and compute the SNR in 300 s in zwo:r.",
       "`get_scene_from_file(path, mag=21, bandpass='sdss_r', magsys='abmag')` is the call; the agent should find the column and unit arguments in the docstring."),
    md(r"""
***
## 3. The background

The default background is zodiacal light at V = 22.5 mag/arcsec² (Vega). `background_prop`
overrides it; the Lazuli L3 requirement value is 22.1. It matters only for faint sources.
"""),
    code("""
for m_src in (20, 24, 27):
    row = []
    for m_sky in (22.5, 22.1, 21.0):
        sc = get_scene("G2V", mag=m_src, bandpass="sdss_r", magsys="abmag", background="zodi", background_prop={"mag": m_sky})
        row.append(Simulation.from_sensorfilter("zwo:r", sc).get_image_snr(300, warn=False)["snr"])
    print(f"r = {m_src}: SNR in 300 s = {row[0]:6.1f} (sky 22.5), {row[1]:6.1f} (22.1), {row[2]:6.1f} (21.0 mag/arcsec²)")
"""),
    md(r"""
***
## 4. A transient on a host galaxy

`host` adds a second scene element. A Sersic profile is set with `host_prop`: total magnitude,
`r_eff` (arcsec), index `n`, and the offset `dx`, `dy` (arcsec) of the source from the nucleus.
The host adds photon noise under the transient and can saturate the nucleus.
"""),
    code("""
scene = get_scene("G5V", mag=22, bandpass="sdss_r", magsys="abmag",
                  host="G5V", host_prop={"mag": 16, "profile": "sersic", "r_eff": 0.5, "n": 4, "dx": 0.3,
                                         "bandpass": "sdss_r", "magsys": "abmag"})
sim = Simulation.from_sensorfilter("zwo:r", scene)
fig, axes = sim.plot_host(300)
plt.show()
r = sim.get_image_snr(300, warn=False)
print(f"transient r = 22 at 0.3\\" from an r = 16 nucleus: SNR {r['snr']:.1f} in 300 s, saturated: {r['saturated']}")
"""),
    guess("moving the transient from 0.3\" to 3\" from the nucleus: does the SNR go up by 10 %, 50 % or a factor of 3?"),
    code("""
blank = Simulation.from_sensorfilter("zwo:r", get_scene("G5V", mag=22, bandpass="sdss_r", magsys="abmag"))
print(f"{'offset':>8} {'SNR':>6}")
for dx in (0.0, 0.3, 1.0, 3.0):
    sim.update(host__dx=dx)
    r = sim.get_image_snr(300, n_reads=3, warn=False)
    print(f"{dx:7.1f}\\" {r['snr']:6.1f}" + ("  (saturated)" if r["saturated"] else ""))
print(f"{'no host':>8} {blank.get_image_snr(300, n_reads=3, warn=False)['snr']:6.1f}")
"""),
    md(r"""
**A real galaxy at a redshift.** `host="ngc0628"` takes the r-band image and spectrum of NGC 628
(76 NGC galaxies are available). One `redshift` moves source and host together: a supernova with
absolute magnitude `magabs` is placed through the distance modulus, and the galaxy keeps its physical
size, so it shrinks on the sky with distance. `"hsiao07"` is a SN Ia template.
"""),
    code("""
for z in (0.05, 0.2, 0.5):
    scene = get_scene("hsiao07", mag=None, magabs=-19.3, redshift=z, bandpass="sdss_r", magsys="abmag",
                      host="ngc0628", host_prop={"dx": 1.0})
    sim = Simulation.from_sensorfilter("zwo:r", scene)
    n = 1
    r = sim.get_image_snr(300, warn=False)
    while r["saturated"] and n < 100:
        n *= 2
        r = sim.get_image_snr(300, n_reads=n, warn=False)
    print(f"z = {z:4.2f}: SN Ia r = {sim.scene.source.mag:5.2f}, SNR {r['snr']:6.1f} in 300 s ({n} reads)")

fig, axes = sim.plot_host(300)
plt.show()
"""),
    md(r"""
***
## Summary

```python
get_scene("K5V", mag=20, bandpass="sdss_r", magsys="abmag")            # a template; always give bandpass + magsys
get_scene("blackbody", teff=3500, mag=21, ...)                          # "flat", "powerlaw" (alpha), "emission" (lines, mag=None)
get_scene_from_file("spec.txt", mag=21, ...)                            # your own spectrum
get_scene(..., background_prop={"mag": 22.1})                           # the sky
get_scene("G5V", mag=22, ..., host="G5V", host_prop={"mag": 16, "profile": "sersic", "r_eff": 0.5, "n": 4, "dx": 0.3})
get_scene("hsiao07", mag=None, magabs=-19.3, redshift=0.2, ..., host="ngc0628")
sim.update(host__dx=1.0)                                                # host__ and source__ prefixes
```

Next: [04 — PSF, apertures and images](04_psf_apertures_images.ipynb).
"""),
]

T04 = [
    md(r"""
# 04 — PSF, apertures, jitter and defocus

At 600 nm the diffraction-limited PSF of a 3.065 m telescope has a FWHM of about 41 mas, i.e.
**2.4 pixels**: the WCC is close to critically sampled, and a tenth of the light of a star lands in
one pixel. That is why bright stars saturate (notebook 02), and why the aperture, the pointing
jitter and a deliberate defocus all change the answer.

In this notebook:
1. a simulated image stamp: `ImageSimulator`, radial profile, encircled energy,
2. the photometric aperture and `optimize=True`,
3. pointing jitter,
4. the defocused modes `zwo:r+1` and `zwo:bb2`.
"""),
    code(SETUP + "\nfrom wcc_etc import ImageSimulator\n" + CHOOSE_READS),
    md(r"""
***
## 1. A simulated image

`ImageSimulator` renders a stamp (electrons, with photon, background, dark and read noise) for one
exposure. The returned object has `image_e`, `image_clean`, `saturation_mask` and plot methods.
"""),
    code("""
scene = get_scene("G2V", mag=18, bandpass="sdss_r", magsys="abmag")
img = ImageSimulator.from_sensorfilter("zwo:r", scene, npix=64).simulate(60, seed=1)
fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
img.plot_image(ax=axes[0], title="r = 18, 60 s, one read")
img.plot_radial(ax=axes[1])
img.plot_encircled_energy(ax=axes[2])
plt.show()
print(f"{img.pixel_scale_mas:.2f} mas/px; peak pixel {img.image_clean.max():.0f} e-, {img.image_clean.max() / img.image_clean.sum():.1%} of the light")
"""),
    md(r"""
***
## 2. The aperture

`get_image_snr` measures the source in a circular aperture of radius `r_aper_mas` (default: set
by the PSF, about 70 mas). A small aperture loses signal; a large one adds background and read noise.
`optimize=True` searches the radius that maximizes the SNR.
"""),
    code("""
sim = Simulation.from_sensorfilter("zwo:r", scene)
sim.update(source__mag=24.0)
radii = np.array([20, 35, 50, 70, 100, 150, 200, 300])
fig, ax = sim.plot_snr_vs_aperture(radii, time=300)
best = sim.get_image_snr(300, optimize=True, warn=False)
ax.axvline(best["r_aper_mas"], color="C3", ls=":", label=f"optimize=True: {best['r_aper_mas']:.0f} mas, SNR {best['snr']:.1f}")
ax.set(title="r = 24, 300 s, zwo:r")
ax.legend()
plt.show()
"""),
    md(r"""
***
## 3. Pointing jitter

The telescope jitters by 10 mas (1 sigma) by default. `jitter_sigma_mas` convolves the PSF with a
Gaussian of that width: more jitter spreads the light (lower peak pixel, bright stars saturate
later) and lowers the SNR of faint sources.
"""),
    code("""
print(f"{'jitter [mas]':>12} {'peak fraction':>13} {'SNR r=24, 300 s':>15}")
for j in (0, 10, 30, 100, 300):
    print(f"{j:12d} {sim.peak_pixel_fraction(jitter_sigma_mas=j):13.3f} {sim.get_image_snr(300, jitter_sigma_mas=j, warn=False)['snr']:15.1f}")
"""),
    md(r"""
***
## 4. Defocus

The labels `zwo:r+1` / `zwo:r-1` (one wave of defocus) and `zwo:bb2` (two waves) use measured
defocused PSFs instead of the Airy pattern. The light is spread over ~50 times more pixels, so a
star ~4 magnitudes brighter fits in the well, at the price of SNR for faint sources and a much
larger aperture.
"""),
    guess("an r = 12 G2V star needs 120 reads per minute in focus (notebook 02). With one wave of defocus, how many?"),
    code("""
bright = get_scene("G2V", mag=12, bandpass="sdss_r", magsys="abmag")
print(f"{'label':8s} {'peak fraction':>13} {'n_pix':>6} {'reads / 60 s':>12} {'SNR':>7}")
for label in ("zwo:r", "zwo:r+1"):
    s = Simulation.from_sensorfilter(label, bright)
    n, r = choose_reads(s, 60)
    print(f"{label:8s} {s.peak_pixel_fraction():13.4f} {r['n_pix']:6d} {str(n) if n else 'none':>12} {r['snr']:7.0f}")

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
for ax, label in zip(axes, ("zwo:r", "zwo:r+1")):
    ImageSimulator.from_sensorfilter(label, bright, npix=128).simulate(0.5, seed=1).plot_image(ax=ax, title=f"{label}, r = 12, 0.5 s")
plt.show()
"""),
    md(r"""
The faint end pays for it:
"""),
    code("""
faint = get_scene("G2V", mag=24, bandpass="sdss_r", magsys="abmag")
for label in ("zwo:r", "zwo:r+1"):
    s = Simulation.from_sensorfilter(label, faint)
    print(f"{label:8s}: r = 24, 300 s, SNR = {s.get_image_snr(300, warn=False)['snr']:5.1f} (aperture {s.get_image_snr(300, warn=False)['r_aper_mas']:.0f} mas)")
"""),
    ai("For a G2V star of r = 12 observed for 60 s, compare zwo:r with the smallest unsaturated read split against zwo:r+1 with one read: which gives the better photometric precision in ppm, and why? Write the comparison as a small table.",
       "Then change the star to r = 9 and r = 15 and see where the answer flips."),
    md(r"""
***
## Summary

```python
ImageSimulator.from_sensorfilter("zwo:r", scene, npix=64).simulate(60, seed=1)   # .plot_image(), .plot_radial(), .plot_encircled_energy()
sim.get_image_snr(t, r_aper_mas=100)      # fixed aperture
sim.get_image_snr(t, optimize=True)       # best aperture
sim.get_image_snr(t, jitter_sigma_mas=30) # pointing jitter
Simulation.from_sensorfilter("zwo:r+1", scene)   # one wave of defocus; "zwo:bb2" two waves
```

Next: [05 — light curves](05_light_curves.ipynb).
"""),
]

T05 = [
    md(r"""
# 05 — Light curves

Time-series photometry is the WCC's bread and butter: transits, flares, variable stars, transients.
`wcc_etc` combines an ETC simulation with a transit model to generate a light curve with realistic
white noise.

In this notebook:
1. `TransitModel` and `LightCurveSimulator`,
2. the per-point precision, binning, and what white noise can and cannot tell you,
3. bright hosts: reads per point.
"""),
    code(SETUP + "\nfrom wcc_etc import TransitModel, LightCurveSimulator\n" + CHOOSE_READS),
    md(r"""
***
## 1. A transit light curve

`TransitModel` takes the usual parameters (`per` in days, `rp` = $R_p/R_*$, `a` = $a/R_*$,
`inc` in degrees, quadratic limb darkening `u`). `LightCurveSimulator.simulate(time, t_exp)`
evaluates the model at the given times (days) and adds noise from the ETC SNR at `t_exp` seconds.
"""),
    code("""
sim = Simulation.from_sensorfilter("zwo:r", get_scene("K2V", mag=19, bandpass="sdss_r", magsys="abmag"))
planet = TransitModel(t0=0.0, per=1.0, rp=0.1, a=10.0, inc=88.0)
t_exp = 60
time = np.arange(-0.12, 0.12, t_exp / 86400)          # days, one point per exposure
lc = LightCurveSimulator(sim, planet).simulate(time, t_exp, seed=3)
print(lc)
fig, ax = lc.plot()
ax.set(xlabel="time from mid-transit [days]", title=f"K2V, r = 19 (AB), 1 % transit, {t_exp} s cadence")
plt.show()
"""),
    md(r"""
`lc.flux_err` is the ETC's 1 sigma per point; `flux_clean` is the noiseless model. The out-of-transit
scatter should reproduce `flux_err`, and binning should average it down as $1/\sqrt{N}$: the
simulator has only white noise. (With ~260 out-of-transit points the comparison is itself noisy at
the 10 to 20 % level; try another `seed`.) Real data have a red-noise floor (flat field, intrapixel
sensitivity × jitter, gain drift) that this ETC does not model.
"""),
    code("""
oot = np.abs(lc.time) > 0.03                            # out of transit
resid = lc.flux[oot] - lc.flux_clean[oot]
print(f"per-point: scatter {resid.std() * 1e6:.0f} ppm, ETC flux_err {lc.flux_err * 1e6:.0f} ppm")
for nbin in (3, 10, 30):
    n = resid.size // nbin
    binned = resid[:n * nbin].reshape(n, nbin).mean(axis=1)
    print(f"binned x{nbin:3d} ({nbin * t_exp / 60:4.0f} min): scatter {binned.std() * 1e6:5.0f} ppm, white-noise expectation {lc.flux_err / np.sqrt(nbin) * 1e6:5.0f} ppm")
"""),
    ai("Fit the transit depth to lc.flux with scipy.optimize.curve_fit, using a box model (constant out of transit, constant minus depth inside |t| < T14/2) with T14 fixed to 0.8 h, and report the depth with its uncertainty.",
       "Compare the uncertainty with flux_err / sqrt(N_in) : nothing more sophisticated is needed to understand exercise 2."),
    md(r"""
***
## 2. Bright hosts: reads per point

`LightCurveSimulator` uses one read per point, so a host brighter than r ~ 18 saturates it. For
those, plan with the ETC directly: `choose_reads` gives the smallest split and its per-point SNR,
and the precision is `1e6 / snr` ppm. (Notebook 02 made the plot; exercise 2 turns it into
detection significances.)
"""),
    code("""
t_exp = 60
for m in (12, 14, 16, 18):
    sim.update(source__mag=float(m))
    n, r = choose_reads(sim, t_exp)
    print(f"K2V r = {m}: {n:3d} x {t_exp / n:5.2f} s per point, {1e6 / r['snr']:5.0f} ppm per point, {1e6 / r['snr'] / np.sqrt(60):4.0f} ppm per hour (white noise)")
"""),
    md(r"""
***
## Summary

```python
planet = TransitModel(t0=0, per=1.0, rp=0.1, a=10, inc=88)
lc = LightCurveSimulator(sim, planet).simulate(time_days, t_exp_s, seed=1)   # .time .flux .flux_clean .flux_err .plot()
```

Next: [06 — fields and photometry](06_fields_and_photometry.ipynb), where whole detector frames
are rendered from Gaia.
"""),
]

T06 = [
    md(r"""
# 06 — Fields and photometry: `wcc_sim` and `wcc_phot`

The ETC works on one source. `wcc_sim` renders a **full WCC frame** of a real sky position from
Gaia DR3 (plus any extended sources you add), with the same PSF, sensor and noise model as the ETC,
and keeps the truth catalogue with it. `wcc_phot` measures those frames: differential aperture
photometry against an ensemble of comparison stars, and centroiding.

In this notebook:
1. a frame of a Gaia field: `simulate_field`,
2. the truth catalogue and the saturation mask,
3. an injected source and a light curve with `run_photometry`,
4. centroids with `centroid_stars`,
5. writing FITS.

**Memory:** a 2048 px square subarray is three float images of 17 MB each; a full 9576 x 6388 frame
is 20 times that. Use subarrays, and restart the kernel when done.
"""),
    code(SETUP_SIM),
    md(r"""
***
## 1. A frame of a Gaia field

`query_gaia` fetches (and caches in `gaia_cache/`) the Gaia DR3 sources around a position;
`simulate_field` renders them. Passing the catalogue in with `catalog=` avoids repeating the query
and lets you edit it. The field here is a random spot at (RA, Dec) = (300°, +30°), 60" across.
"""),
    code("""
RA, DEC = 300.0, 30.0
cat = query_gaia(RA, DEC, radius_arcsec=60, mag_limit=21.0, cache_dir="gaia_cache")
field = simulate_field(RA, DEC, sensorfilter="zwo:r", focus=0, exptime=60, seed=1, shape=(2048, 2048), catalog=cat)
PLATE = field.params["plate_scale_mas"]
print(f"{len(cat)} Gaia sources; image {field.image_e.shape}, {PLATE:.2f} mas/px, {field.image_e.shape[0] * PLATE / 1000:.0f}\\" on a side")
print("params:", {k: field.params[k] for k in ("exptime", "n_reads", "jitter_sigma_mas", "read_noise", "well_depth", "sky_e_s")})
"""),
    code("""
c = field.catalog
inn = np.asarray(c["in_image"], bool); sat = np.asarray(c["saturated"], bool)
fig, ax = plt.subplots(figsize=(8, 7.5))
plot_image_mpl(image_e=field.image_e, saturation_mask=field.saturation_mask, pixel_scale_mas=PLATE,
               show_saturation=True, stretch="asinh", cmap="gray_r", ax=ax)
ax.scatter(c["x"][inn & ~sat], c["y"][inn & ~sat], s=60, facecolors="none", edgecolors="C0", lw=0.8, label="unsaturated star")
ax.scatter(c["x"][inn & sat], c["y"][inn & sat], s=140, facecolors="none", edgecolors="C3", lw=1.2, label="saturated star")
ax.plot([80, 80 + 5000 / PLATE], [80, 80], "k-", lw=3); ax.text(80, 120, '5"', fontsize=11)
ax.legend(loc="upper right"); ax.set_title("zwo:r, 60 s, 2048 px subarray")
plt.show()
print(f"{inn.sum()} stars in the frame, {(inn & sat).sum()} saturated (brightest G = {c['phot_g_mean_mag'][inn].min():.1f}), {int(field.saturation_mask.sum())} saturated pixels")
"""),
    md(r"""
***
## 2. The truth catalogue

`field.catalog` is the Gaia table plus the rendered pixel positions `x`, `y`, the spectral type
used for the colour (`spt`), the electron rate, and the `in_image` and `saturated` flags. It is the
truth against which `wcc_phot` is checked.
"""),
    code("""
c[inn]["source_id", "phot_g_mean_mag", "phot_bp_mean_mag", "spt", "x", "y", "rate_e_s", "saturated"][:8]
"""),
    md(r"""
***
## 3. An injected source and differential photometry

Add a row to the catalogue (a NaN colour makes `wcc_sim` use its default G2V template), render a
few frames with the injected star at different magnitudes, and recover the light curve with
`run_photometry`: aperture photometry of the target and `n_ref` comparison stars of similar
brightness, normalized by the ensemble.
"""),
    code("""
row = {k: np.nan for k in cat.colnames}
row.update(source_id=1, ra=RA, dec=DEC, phot_g_mean_mag=18.0)
cat.add_row(row)
dmag = np.array([0.0, 0.0, -0.2, -0.3, -0.1, 0.0])                 # the injected light curve, mag
frames = []
for k, dm in enumerate(dmag):
    cat["phot_g_mean_mag"][-1] = 18.0 + dm
    frames.append(simulate_field(RA, DEC, sensorfilter="zwo:r", focus=0, exptime=60, seed=10 + k, shape=(2048, 2048), catalog=cat))
res = run_photometry(frames, target=1, method="aperture", n_ref=10, times=np.arange(len(dmag)) * 0.5)
print(f"aperture {res.params['r_ap']} px, {res.params['n_ref']} reference stars")
lc = res.lightcurve
rec = -2.5 * np.log10(lc["rel_flux_norm"])
rec_err = 2.5 / np.log(10) * lc["rel_flux_norm_err"] / lc["rel_flux_norm"]
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(lc["time"], dmag - np.median(dmag), "k--", label="injected")
ax.errorbar(lc["time"], rec, yerr=rec_err, fmt="o", label="recovered")
ax.invert_yaxis(); ax.set(xlabel="epoch [days]", ylabel="magnitude relative to median"); ax.legend()
plt.show()
print(f"residual RMS {1e3 * np.std(rec - (dmag - np.median(dmag))):.1f} mmag, propagated error {1e3 * np.median(rec_err):.1f} mmag; flagged measurements: {int((res.measurements['flags'] != 0).sum())}")
"""),
    md(r"""
`res.measurements` holds every star in every frame with `flags` (saturation, edge, centroid
failure); `res.stars` lists the target and the comparison stars with their Gaia magnitudes.
`report=path.pdf` writes a diagnostic PDF.
"""),
    md(r"""
***
## 4. Centroids

`centroid_stars(frame, x0, y0, box)` recentres each star by a background-subtracted centre of mass
in a `box` px window. Against the truth positions this gives the single-frame astrometric precision.
"""),
    code("""
f0 = frames[0]; c = f0.catalog
use = np.asarray(c["in_image"], bool) & ~np.asarray(c["saturated"], bool) & (c["x"] > 20) & (c["x"] < 2027) & (c["y"] > 20) & (c["y"] < 2027)
x, y, flags = centroid_stars(f0, c["x"][use], c["y"][use], box=15)
good = flags == 0
dx = (x - c["x"][use])[good] * PLATE; dy = (y - c["y"][use])[good] * PLATE
print(f"{good.sum()} stars: per-coordinate scatter {0.5 * (dx.std() + dy.std()):.2f} mas, mean offset ({dx.mean():+.2f}, {dy.mean():+.2f}) mas")
fig, ax = plt.subplots(figsize=(6, 4))
ax.semilogy(c["phot_g_mean_mag"][use][good], np.hypot(dx, dy), "o")
ax.set(xlabel="Gaia G", ylabel="radial residual [mas]", title="single 60 s frame, box centroids")
plt.show()
"""),
    ai("Write a loop that renders this field at exposure times 2, 5, 10, 30 and 60 s (same seed), recentroids the unsaturated stars with centroid_stars, and plots the per-coordinate scatter in mas against exposure time with a t^-1/2 reference line.",
       "That is most of exercise 6."),
    md(r"""
***
## 5. Writing FITS

`to_hdulist()` packs the frame as SCI, SATMASK, CAT and CLEAN extensions, the format the symposium
S3 bucket uses for simulated WCC data.
"""),
    code("""
hdul = frames[0].to_hdulist()
hdul.info()
# hdul.writeto("wcc_field_300_+30_r_60s.fits", overwrite=True)
"""),
    md(r"""
***
## Summary

```python
cat   = query_gaia(ra, dec, radius_arcsec=60, mag_limit=21, cache_dir="gaia_cache")
field = simulate_field(ra, dec, sensorfilter="zwo:r", focus=0, exptime=60, seed=1, shape=(2048, 2048), catalog=cat)
field.image_e, field.saturation_mask, field.catalog, field.params, field.to_hdulist()
res   = run_photometry(frames, target=source_id, n_ref=10, times=...)     # .lightcurve .measurements .stars
x, y, flags = centroid_stars(field, x0, y0, box=15)
```

Now pick an exercise: [README](README.md).
"""),
]

# =====================================================================================
# Exercises: list of cells; a `sol(...)` cell becomes "# your code here" in the exercise
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
            ex.append(code("# your code here"))
            so.append(code(c))
        elif isinstance(c, Bug):
            ex.append(code(c[0]))
            so.append(code(c[1]))
        else:
            ex.append(c); so.append(c)
    feedback = md("""
***
## Share-back and feedback

Bring back **one plot and one number** to the share-back board, and the observing decision you draw
from them.

> 🤖 **Ask Jupyter AI:** *Draft a GitHub issue for schmidt-observatories/wcc-etc describing one thing I
> found missing, confusing or wrong in this exercise, with a minimal code example.*
""")
    write(HERE / "exercises" / f"{stem}.ipynb", ex + [feedback])
    write(HERE / "exercises" / "solutions" / f"{stem}_solution.ipynb", so + [feedback])


EX1 = [
    md(r"""
### 1.1 — Blank sky

A G5V-like transient on empty sky, observed in zwo:r. What is the 5 sigma limiting magnitude in a
single 300 s exposure? (Use `limiting_mag` from notebook 01, or write your own.)
"""),
    sol(LIMITING_MAG + """
blank = Simulation.from_sensorfilter("zwo:r", get_scene("G5V", mag=22, bandpass="sdss_r", magsys="abmag"))
print(f"blank sky, 300 s: 5 sigma at r = {limiting_mag(blank, 300):.2f}")
"""),
    md(r"""
### 1.2 — On a host

Put the same transient at r = 22, 0.5" from the nucleus of an r = 16 elliptical (Sersic n = 4,
half-light radius 0.5"). What is its SNR in 300 s, and the 5 sigma depth at that position?
Check the saturation flag.
"""),
    sol("""
scene = get_scene("G5V", mag=22, bandpass="sdss_r", magsys="abmag",
                  host="G5V", host_prop={"mag": 16, "profile": "sersic", "r_eff": 0.5, "n": 4, "dx": 0.5,
                                         "bandpass": "sdss_r", "magsys": "abmag"})
sim = Simulation.from_sensorfilter("zwo:r", scene)
r = sim.get_image_snr(300, warn=False)
print(f"r = 22 at 0.5\\": SNR {r['snr']:.1f}, saturated: {r['saturated']}; 5 sigma depth r = {limiting_mag(sim, 300):.2f}")
"""),
    guess("the transient now sits on the nucleus (dx = 0). Does the 5 sigma depth drop by 0.5, 1.5 or 3 magnitudes compared with blank sky?"),
    md(r"""
### 1.3 — Nuclear

Move the transient onto the nucleus. Is a single 300 s frame still unsaturated? Find the smallest
read split that is (`choose_reads` from notebook 02), and the 5 sigma depth with that split.
"""),
    sol(CHOOSE_READS + """
sim.update(host__dx=0.0)
print("single 300 s frame saturated:", sim.get_image_snr(300, warn=False)["saturated"])
n, r = choose_reads(sim, 300)
print(f"smallest split: {n} x {300 / n:.0f} s; 5 sigma depth on the nucleus: r = {limiting_mag(sim, 300, n_reads=n):.2f}")
"""),
    md(r"""
### 1.4 — Depth versus offset

Plot the 5 sigma depth in 300 s as a function of the offset from the nucleus (0, 0.25, 0.5, 1,
1.5, 3"), each with its own smallest read split, with the blank-sky depth as a horizontal line.
"""),
    sol("""
offsets = [0, 0.25, 0.5, 1.0, 1.5, 3.0]
depths = []
for dx in offsets:
    sim.update(host__dx=dx)
    n, _ = choose_reads(sim, 300)
    depths.append(limiting_mag(sim, 300, n_reads=n))
    print(f"{dx:4.2f}\\": {n} reads, 5 sigma at r = {depths[-1]:.2f}")
fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(offsets, depths, "o-", label="on an r = 16 Sersic n = 4 host")
ax.axhline(limiting_mag(blank, 300), color="0.5", ls="--", label="blank sky")
ax.set(xlabel="offset from nucleus [arcsec]", ylabel="5 sigma depth in 300 s [r, AB]", title="transient depth versus host position")
ax.legend()
plt.show()
"""),
    md(r"""
### 1.5 — The template

The transient is really measured on a difference image, so the template's noise adds:
$\sigma_\mathrm{diff}^2 = \sigma_\mathrm{sci}^2 + \sigma_\mathrm{ref}^2 / k$ for a template
$k$ times deeper. For the nuclear case, compute the 5 sigma depth with an equal-depth template
($k = 1$) and with one five times deeper. `signal_e` and `noise_e` with `mags=` give the arrays;
the template is the same scene with the transient removed (set its magnitude to 40).
"""),
    sol("""
sim.update(host__dx=0.0)
n, sci = choose_reads(sim, 300, mags=np.arange(18, 28.01, 0.25))
mags = np.arange(18, 28.01, 0.25)
for k in (1, 5):
    _, ref = choose_reads(sim, 300 * k, mags=np.full_like(mags, 40.0))
    snr = sci["signal_e"] / np.hypot(sci["noise_e"], ref["noise_e"] / k)
    ok = np.isfinite(snr)
    depth = np.interp(np.log10(5), np.log10(snr[ok][::-1]), mags[ok][::-1])
    print(f"template {k} x deeper: 5 sigma at r = {depth:.2f}")
"""),
    ai("Explain why the host penalty is largest on the nucleus even when the nucleus is not saturated, and what the half-light radius has to do with it. Then: how would I add an AGN-like power-law host component instead of a G5V spectrum?"),
]

EX2 = [
    md(r"""
### 2.1 — A bright host

A K2V host at r = 16 (AB) observed at 60 s cadence in zwo:r. What is the smallest read split that
keeps each frame unsaturated, and the resulting precision per 60 s point in ppm?
"""),
    sol(CHOOSE_READS + """
sim = Simulation.from_sensorfilter("zwo:r", get_scene("K2V", mag=16, bandpass="sdss_r", magsys="abmag"))
n, r = choose_reads(sim, 60)
print(f"r = 16: {n} x {60 / n:.0f} s per point, {1e6 / r['snr']:.0f} ppm per point")
"""),
    md(r"""
### 2.2 — A simulated transit

Simulate a 1 % deep transit (P = 1 d, a/R* = 10, i = 88°) of a K2V host at r = 19 over ±0.12 d
at 60 s cadence, and plot it. Compare the out-of-transit scatter with the ETC's `flux_err`.
"""),
    sol("""
from wcc_etc import TransitModel, LightCurveSimulator
sim.update(source__mag=19.0)
planet = TransitModel(t0=0.0, per=1.0, rp=0.1, a=10.0, inc=88.0)
time = np.arange(-0.12, 0.12, 60 / 86400)
lc = LightCurveSimulator(sim, planet).simulate(time, 60, seed=2)
fig, ax = lc.plot(); ax.set(xlabel="time from mid-transit [days]"); plt.show()
oot = np.abs(lc.time) > 0.03
print(f"out-of-transit scatter {np.std(lc.flux[oot] - lc.flux_clean[oot]) * 1e6:.0f} ppm, flux_err {lc.flux_err * 1e6:.0f} ppm")
"""),
    md(r"""
### 2.3 — Precision versus magnitude

For K2V hosts from r = 11 to 21, tabulate the smallest read split, the precision per 60 s point
and the precision binned to one hour (white noise). Plot both against magnitude with horizontal
lines for the transit depths of Jupiter, Neptune and Earth around a Sun-like star, and of an Earth
around a 0.3 $R_\odot$ M dwarf (use `astropy.constants`).
"""),
    sol("""
from astropy.constants import R_jup, R_earth, R_sun
depths = {"Jupiter / Sun": float((R_jup / R_sun) ** 2), "Neptune / Sun": float((3.88 * R_earth / R_sun) ** 2),
          "Earth / 0.3 Rsun": float((R_earth / (0.3 * R_sun)) ** 2), "Earth / Sun": float((R_earth / R_sun) ** 2)}
mags = np.arange(11, 21.1, 1.0)
rows = []
for m in mags:
    sim.update(source__mag=float(m))
    n, r = choose_reads(sim, 60)
    ppm = 1e6 / r["snr"] if n else np.nan
    rows.append((n if n else np.nan, ppm, ppm / np.sqrt(60)))
    print(f"r = {m:4.1f}: {str(n):>4} reads, {ppm:6.0f} ppm per point, {rows[-1][2]:5.0f} ppm per hour")
n_needed, ppm_point, ppm_hour = map(np.array, zip(*rows))
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.semilogy(mags, ppm_point, "o-", label="per 60 s point")
ax.semilogy(mags, ppm_hour, "s-", label="binned to 1 h")
for name, d in depths.items():
    ax.axhline(d * 1e6, color="0.5", lw=1); ax.text(mags[0], d * 1.15e6, f"{name}: {d * 1e6:.0f} ppm", color="0.5", fontsize=8)
ax.set(xlabel="host r magnitude (AB)", ylabel="precision [ppm]", title="K2V host, zwo:r"); ax.legend(loc="lower right")
plt.show()
"""),
    md(r"""
### 2.4 — Detection significance

For one transit of duration $T_{14}$ = 0.8 h in a 5.8 h window at 60 s cadence, the depth
uncertainty with white noise is
$\sigma_\delta = \sigma_\mathrm{point}\sqrt{1/N_\mathrm{in} + 1/N_\mathrm{out}}$.
At which host magnitude does a Neptune/Sun transit reach 5 sigma in a single event? And an
Earth/Sun transit?
"""),
    sol("""
n_in = 0.8 * 3600 / 60; n_out = (5.8 - 0.8) * 3600 / 60
sigma_depth = ppm_point * np.sqrt(1 / n_in + 1 / n_out)
for name in ("Neptune / Sun", "Earth / Sun"):
    sig = depths[name] * 1e6 / sigma_depth
    ok = sig >= 5
    print(f"{name}: " + (f"5 sigma out to r = {mags[ok].max():.0f}" if ok.any() else "never 5 sigma in one transit") + "  (" + ", ".join(f"{m:.0f}: {s:.1f}" for m, s in zip(mags, sig)) + ")")
"""),
    ai("Turn the sigma_depth formula into a function of (ppm_point, T14_hours, window_hours, cadence_s) and plot the Neptune/Sun significance against T14 from 0.5 to 5 h for an r = 15 host.",
       "Then ask it what systematic noise floor (in ppm per hour) would make the Earth/Sun case hopeless at every magnitude."),
]

EX3 = [
    md(r"""
### 3.1 — Depth per filter

For a flat-spectrum (AB) point source, what 5 sigma depth does a single 300 s exposure reach in
zwo:u, g, r, i, z and bb?
"""),
    sol(LIMITING_MAG + """
filters = ["zwo:u", "zwo:g", "zwo:r", "zwo:i", "zwo:z", "zwo:bb"]
sims = {f: Simulation.from_sensorfilter(f, get_scene("flat", mag=24, magsys="abmag")) for f in filters}
for f, s in sims.items():
    print(f"{f:7s}: 5 sigma in 300 s at AB = {limiting_mag(s, 300):.2f}")
"""),
    guess("going from 300 s to 3000 s, does the g-band depth improve by 1.25 mag (sky limited), 2.5 mag (read-noise limited) or something in between?"),
    md(r"""
### 3.2 — Depth versus exposure time

Plot the 5 sigma depth against single-exposure time (30, 100, 300, 1000, 3000, 10000 s) for all six
filters. For g, compute the slope in magnitudes per decade between 30 and 300 s and between 3000
and 10000 s. The limits are 2.5 mag/decade (read-noise limited) and 1.25 (background limited):
which regime is the WCC in, and why does it change?
"""),
    sol("""
exptimes = np.array([30, 100, 300, 1000, 3000, 10000])
depth = {f: np.array([limiting_mag(s, t) for t in exptimes]) for f, s in sims.items()}
fig, ax = plt.subplots(figsize=(7, 4.5))
for f in filters:
    ax.semilogx(exptimes, depth[f], "o-", label=f)
ax.set(xlabel="exposure time [s]", ylabel="5 sigma depth [AB]", title="single exposure, flat spectrum"); ax.legend()
plt.show()
slope = lambda f, i, j: (depth[f][j] - depth[f][i]) / np.log10(exptimes[j] / exptimes[i])
print(f"g: {slope('zwo:g', 0, 2):.2f} mag/decade (30 -> 300 s), {slope('zwo:g', 4, 5):.2f} mag/decade (3000 -> 10000 s)")
# The zodiacal sky is a few e-/pixel/minute: read noise dominates short frames, the sky only after ~1000 s.
"""),
    md(r"""
### 3.3 — The cost of stacking

3000 s of r band taken as one frame, as 10 x 300 s, and as 100 x 30 s: what is the 5 sigma depth
of each stack? Why would anyone choose the shorter frames?
"""),
    sol("""
for n in (1, 10, 100):
    print(f"3000 s as {n:3d} x {3000 / n:5.0f} s: 5 sigma at AB = {limiting_mag(sims['zwo:r'], 3000, n_reads=n):.2f}")
# Saturation of the brightest stars in the field, cosmic rays, and dithering for detector defects.
"""),
    md(r"""
### 3.4 — A real field

The field you want contains a G2V star of r = 15. What is the longest unsaturated single frame in
zwo:r (try 1, 2, 3, 5, 10, 20, 30, 60 s), and what 5 sigma depth does an hour of such frames reach?
"""),
    sol("""
bright = Simulation.from_sensorfilter("zwo:r", get_scene("G2V", mag=15, bandpass="sdss_r", magsys="abmag"))
frame = max(t for t in (1, 2, 3, 5, 10, 20, 30, 60) if not bright.is_saturated(t))
n = int(round(3600 / frame))
print(f"longest unsaturated frame: {frame} s -> {n} frames per hour; 5 sigma depth AB = {limiting_mag(sims['zwo:r'], 3600, n_reads=n):.2f} "
      f"(one 3600 s frame would give {limiting_mag(sims['zwo:r'], 3600):.2f})")
"""),
    ai("The zodiacal background in wcc_etc is fixed at V = 22.5 mag/arcsec² but the Lazuli requirement value is 22.1. Rerun 3.1 with background_prop={'mag': 22.1} and report how much depth is lost in each filter.",
       "Ask it, too, what else is missing from the noise model (hint: the wcc-etc README lists the known limitations)."),
]

EX4 = [
    md(r"""
### 4.0 — A broken cell

The cell below is broken on purpose. Run it, paste the traceback into Jupyter AI (or read it
yourself), fix it, and keep the fixed version: it builds the simulations the rest of the exercise
uses.
"""),
    bug("""
filters = ["zwo:halpha2", "zwo:halpha6", "zwo:halpha20", "zwo:r"]
line = [{"wave": 6563.0, "flux": 1e-15, "fwhm": 4}]              # erg/s/cm^2, Angstrom
sims = {f: Simulation.from_sensorfilter(f, get_scene("emission", mag=18, lines=line)) for f in filters}
""", """
filters = ["zwo:halpha2", "zwo:halpha6", "zwo:halpha20", "zwo:r"]
line = [{"wave": 6563.0, "flux": 1e-15, "fwhm": 4}]              # erg/s/cm^2, Angstrom
# fixed: emission sources carry absolute line fluxes, so mag must be None (mag=18 raised a ValueError)
sims = {f: Simulation.from_sensorfilter(f, get_scene("emission", mag=None, lines=line)) for f in filters}
"""),
    md(r"""
### 4.1 — The filters

Tabulate for each filter the FWHM of the installed throughput curve (sample `sim.sensor.bandpass(w)`
on a fine grid) and the throughput at 6563 Å, and plot the four curves between 6200 and 6900 Å
with the line drawn on top.
"""),
    sol("""
w = np.arange(5000, 7500, 0.05)
fwhm = {}
print(f"{'filter':13s} {'FWHM [A]':>9s} {'T(6563)':>8s}")
for f, s in sims.items():
    T = s.sensor.bandpass(w).value; half = w[T >= T.max() / 2]
    fwhm[f] = half.max() - half.min()
    print(f"{f:13s} {fwhm[f]:9.1f} {s.sensor.bandpass(6563.0).value:8.3f}")
fig, ax = plt.subplots(figsize=(9, 4))
for f, s in sims.items():
    wcc_etc.plot_bandpass_mpl(s.sensor, ax=ax, label=f"{f} (FWHM {fwhm[f]:.0f} A)")
ax.plot(w, 0.37 * np.exp(-0.5 * ((w - 6563) / (4 / 2.355)) ** 2), color="0.3", lw=1, label="the line (scaled)")
ax.set(xlim=(6200, 6900)); ax.legend(fontsize=8)
plt.show()
"""),
    md(r"""
### 4.2 — A pure line

The line SNR in 300 s in each filter, no continuum. Why are the three H-alpha filters so close?
"""),
    sol("""
for f, s in sims.items():
    print(f"{f:13s}: SNR = {s.get_image_snr(300, warn=False)['snr']:5.1f}")
# Same line photons in all three; only the (small) zodiacal background grows with filter width.
"""),
    guess("with a V = 15 continuum under the line, which filter wins, and is the 200 Å filter still usable?"),
    md(r"""
### 4.3 — A line on a continuum

Now the line sits on a G5V-like continuum of V = 13 to 22 (Vega), passed as a point-source host:
`host="G5V", host_prop={"mag": V, "bandpass": "johnson_v", "magsys": "vegamag"}`. Plot the line SNR in
300 s against continuum magnitude for the four filters, omitting saturated points (split the r
exposure into 30 reads). Where does each filter win?
"""),
    sol("""
host_mags = np.arange(13, 22.5, 1.0)
fig, ax = plt.subplots(figsize=(7, 4.5))
for f in filters:
    s = Simulation.from_sensorfilter(f, get_scene("emission", mag=None, lines=line, host="G5V",
                                                   host_prop={"mag": 17, "bandpass": "johnson_v", "magsys": "vegamag"}))
    snr = []
    for m in host_mags:
        s.update(host__mag=float(m))
        r = s.get_image_snr(300, n_reads=30 if f == "zwo:r" else 1, warn=False)
        snr.append(np.nan if r["saturated"] else r["snr"])
    ax.semilogy(host_mags, snr, "o-", label=f)
ax.axhline(5, color="0.5", lw=1)
ax.set(xlabel="continuum V (Vega)", ylabel="line SNR in 300 s", title="1e-15 erg/s/cm² line on a G5V continuum"); ax.legend()
plt.show()
"""),
    md(r"""
### 4.4 — Limiting line flux

For a V = 18 continuum, find the 5 sigma limiting line flux in 300 s in each filter (sweep the line
flux with `s.update(source__lines=[...])` over $10^{-17}$ to $10^{-14}$ erg/s/cm²).
"""),
    sol("""
fluxes = np.logspace(-17, -14, 13)
for f in filters:
    s = Simulation.from_sensorfilter(f, get_scene("emission", mag=None, lines=line, host="G5V",
                                                   host_prop={"mag": 18, "bandpass": "johnson_v", "magsys": "vegamag"}))
    snr = []
    for fl in fluxes:
        s.update(source__lines=[{"wave": 6563.0, "flux": float(fl), "fwhm": 4}])
        r = s.get_image_snr(300, n_reads=30 if f == "zwo:r" else 1, warn=False)
        snr.append(np.nan if r["saturated"] else r["snr"])
    snr = np.array(snr)
    print(f"{f:13s}: 5 sigma line flux = {10 ** np.interp(np.log10(5), np.log10(snr), np.log10(fluxes)):.1e} erg/s/cm²")
"""),
    ai("My H II region has a radial velocity of +900 km/s. Shift the line wavelength accordingly, recompute 4.2, and tell me which filters still transmit it.",
       "The fix is one number; the agent should also explain the FWHM-to-km/s conversion."),
]

EX5 = [
    md(r"""
### 5.1 — The field and the injected nucleus

Load the cached Gaia field at (RA, Dec) = (300°, +30°) (60" radius), add a row at the field centre
with `source_id=1` and G = 18 (a host-free, stellar-SED stand-in for an AGN), and render eight 60 s
frames on a 2048 px subarray in which the injected source follows the flare
`dmag = [0, 0, -0.10, -0.25, -0.35, -0.30, -0.20, -0.10]`. Show the first frame with the target
marked.
"""),
    sol("""
RA, DEC = 300.0, 30.0
cat = query_gaia(RA, DEC, radius_arcsec=60, mag_limit=21.0, cache_dir="gaia_cache")
row = {k: np.nan for k in cat.colnames}
row.update(source_id=1, ra=RA, dec=DEC, phot_g_mean_mag=18.0)
cat.add_row(row)
dmag = np.array([0.0, 0.0, -0.10, -0.25, -0.35, -0.30, -0.20, -0.10])
frames = []
for k, dm in enumerate(dmag):
    cat["phot_g_mean_mag"][-1] = 18.0 + dm
    frames.append(simulate_field(RA, DEC, sensorfilter="zwo:r", focus=0, exptime=60, seed=k, shape=(2048, 2048), catalog=cat))
c = frames[0].catalog
x0, y0 = [float(c[c["source_id"] == 1][k][0]) for k in ("x", "y")]
fig, ax = plt.subplots(figsize=(7, 7))
ax.imshow(frames[0].image_e, origin="lower", cmap="gray_r", norm=simple_norm(frames[0].image_e, "asinh", percent=99.7))
ax.plot(x0, y0, "o", ms=16, mfc="none", mec="r"); ax.set_title("frame 0 with the injected G = 18 nucleus")
plt.show()
"""),
    md(r"""
### 5.2 — Recover the flare

Run `run_photometry` on the eight frames (target 1, ten comparison stars, epochs 0.5 d apart) and
plot the recovered magnitude change with error bars over the injected one. Report the residual RMS
and the median propagated error in mmag, and list any flagged epochs.
"""),
    sol("""
res = run_photometry(frames, target=1, method="aperture", n_ref=10, times=np.arange(len(dmag)) * 0.5)
lc = res.lightcurve
rec = -2.5 * np.log10(lc["rel_flux_norm"]); rec_err = 2.5 / np.log(10) * lc["rel_flux_norm_err"] / lc["rel_flux_norm"]
inj = dmag - np.median(dmag)
flagged = np.unique(res.measurements["frame"][res.measurements["flags"] != 0])
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(lc["time"], inj, "k--", label="injected"); ax.errorbar(lc["time"], rec, yerr=rec_err, fmt="o", label="recovered")
ax.invert_yaxis(); ax.set(xlabel="epoch [days]", ylabel="mag relative to median"); ax.legend()
plt.show()
print(f"residual RMS {1e3 * np.std(np.asarray(rec - inj)):.1f} mmag, median error {1e3 * np.median(rec_err):.1f} mmag; flagged epochs: {flagged.tolist()}")
"""),
    guess("by how much does the per-frame precision degrade from G = 18 to G = 20: a factor 1.5, 2.5 or 6?"),
    md(r"""
### 5.3 — Precision versus nucleus magnitude

For G = 17, 18, 19, 20, render three constant-brightness frames each and take the median
propagated error per frame as the precision. Plot it against magnitude. (This takes a minute or
two: ~10 s per frame.)
"""),
    sol("""
mags = [17, 18, 19, 20]
prec = []
for m in mags:
    cat["phot_g_mean_mag"][-1] = m
    fr = [simulate_field(RA, DEC, sensorfilter="zwo:r", focus=0, exptime=60, seed=100 + k, shape=(2048, 2048), catalog=cat) for k in range(3)]
    r = run_photometry(fr, target=1, n_ref=10)
    good = r.lightcurve["flags"] == 0
    err = r.lightcurve["rel_flux_norm_err"] / r.lightcurve["rel_flux_norm"]
    prec.append(1e3 * 2.5 / np.log(10) * np.median(err[good]) if good.any() else np.nan)
    print(f"G = {m}: {prec[-1]:.1f} mmag per 60 s frame" + ("" if good.all() else f" ({int((~good).sum())} frames flagged)"))
fig, ax = plt.subplots(figsize=(6, 4))
ax.semilogy(mags, prec, "o-"); ax.set(xlabel="nucleus G", ylabel="precision per 60 s frame [mmag]")
plt.show()
"""),
    ai("Replace the hand-written dmag array by a tidal disruption event: a rise over 2 epochs to a peak 0.5 mag brighter, then a t^(-5/3) decay over 10 epochs spaced 2 days apart. Regenerate the frames and rerun 5.2.",
       "Then ask it how to add the host galaxy as a SersicComponent under the nucleus, and what that does to the aperture photometry."),
]

EX6 = [
    md(r"""
### 6.1 — Baade's Window

Render a 10 s zwo:r frame of Baade's Window, (RA, Dec) = (270.9°, -30.03°), on a 2048 px subarray
(the Gaia query is cached; use `cache_dir="gaia_cache"` and `seed=7`). How many stars are in the
frame, how many are saturated, and how bright is the brightest? Show the frame with the saturated
stars marked.
"""),
    sol("""
RA, DEC = 270.9, -30.03
field = simulate_field(RA, DEC, sensorfilter="zwo:r", focus=0, exptime=10, seed=7, shape=(2048, 2048), cache_dir="gaia_cache")
PLATE = field.params["plate_scale_mas"]
c = field.catalog
inn = np.asarray(c["in_image"], bool); sat = np.asarray(c["saturated"], bool)
print(f"{inn.sum()} stars in frame, {(inn & sat).sum()} saturated, brightest G = {c['phot_g_mean_mag'][inn].min():.1f}")
fig, ax = plt.subplots(figsize=(8, 7.5))
plot_image_mpl(image_e=field.image_e, saturation_mask=field.saturation_mask, pixel_scale_mas=PLATE, show_saturation=True, stretch="asinh", cmap="gray_r", ax=ax)
ax.scatter(c["x"][inn & sat], c["y"][inn & sat], s=120, facecolors="none", edgecolors="C3", label="saturated")
ax.legend(); ax.set_title("Baade's Window, zwo:r, 10 s")
plt.show()
"""),
    md(r"""
### 6.2 — A cell with a bug

The cell below recentroids every unsaturated star and prints the scatter against the truth
catalogue. It runs without error, but the numbers it prints are wrong by a constant factor.
Find the bug (with or without Jupyter AI), fix it, and keep going. Is 0.03 "mas" plausible for a
2.4 px FWHM PSF?
"""),
    code("""
use = inn & ~sat & (c["x"] > 20) & (c["x"] < 2027) & (c["y"] > 20) & (c["y"] < 2027)
x, y, flags = centroid_stars(field, c["x"][use], c["y"][use], box=15)
good = flags == 0
dx = (x - c["x"][use])[good]; dy = (y - c["y"][use])[good]            # BUG: these are pixels, not mas
print(f"{good.sum()} stars: scatter sigma_x = {dx.std():.3f}, sigma_y = {dy.std():.3f} mas")
"""),
    sol("""
dx = (x - c["x"][use])[good] * PLATE; dy = (y - c["y"][use])[good] * PLATE     # fixed: pixels -> mas
print(f"{good.sum()} stars: scatter sigma_x = {dx.std():.2f}, sigma_y = {dy.std():.2f} mas; mean offset ({dx.mean():+.2f}, {dy.mean():+.2f}) mas")
"""),
    md(r"""
### 6.3 — Precision versus magnitude

Plot the radial residual of each star against its Gaia G, and the per-coordinate scatter in 1 mag
bins. Add a line at 0.1 px.
"""),
    sol("""
g = np.asarray(c["phot_g_mean_mag"][use])[good]; res = np.hypot(dx, dy)
edges = np.arange(13, 21.5, 1); mid = 0.5 * (edges[1:] + edges[:-1])
sig = [0.5 * (dx[m].std() + dy[m].std()) if m.sum() > 2 else np.nan for m in [(g >= a) & (g < b) for a, b in zip(edges[:-1], edges[1:])]]
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.semilogy(g, res, ".", alpha=0.5, label="radial residual per star")
ax.plot(mid, sig, "s-", color="C3", label="per-coordinate sigma per 1 mag bin")
ax.axhline(PLATE / 10, color="0.5", ls=":", label="0.1 px")
ax.set(xlabel="Gaia G", ylabel="residual [mas]", title="single 10 s frame, box centroids"); ax.legend(fontsize=8)
plt.show()
"""),
    guess("from 2 s to 20 s exposures, does the centroid scatter of 17 < G < 19 stars fall as t^-1/2 all the way?"),
    md(r"""
### 6.4 — Precision versus exposure time

For exposures of 2, 5, 10 and 20 s (same seed), compute the pooled per-coordinate scatter of stars
with 17 < G < 19 and plot it against exposure time with a $t^{-1/2}$ reference. What limits the
precision at the long end?
"""),
    sol("""
times = [2, 5, 10, 20]
sig_t = []
for t in times:
    f = simulate_field(RA, DEC, sensorfilter="zwo:r", focus=0, exptime=t, seed=7, shape=(2048, 2048), cache_dir="gaia_cache")
    ct = f.catalog
    sel = (np.asarray(ct["in_image"], bool) & ~np.asarray(ct["saturated"], bool) & (ct["phot_g_mean_mag"] > 17) & (ct["phot_g_mean_mag"] < 19)
           & (ct["x"] > 20) & (ct["x"] < 2027) & (ct["y"] > 20) & (ct["y"] < 2027))
    xt, yt, ft = centroid_stars(f, ct["x"][sel], ct["y"][sel], box=15)
    gd = ft == 0
    d = np.concatenate([(xt - ct["x"][sel])[gd], (yt - ct["y"][sel])[gd]]) * PLATE
    sig_t.append(d.std())
    print(f"{t:3d} s: {sel.sum()} stars, per-coordinate sigma {sig_t[-1]:.2f} mas")
fig, ax = plt.subplots(figsize=(6, 4))
ax.loglog(times, sig_t, "o-", label="17 < G < 19")
ax.loglog(times, sig_t[0] * np.sqrt(times[0] / np.array(times)), "k:", label="$t^{-1/2}$")
ax.set(xlabel="exposure time [s]", ylabel="centroid scatter [mas]"); ax.legend()
plt.show()
# Crowding and the fixed centroid box (neighbours bias the centre of mass) flatten the curve; PSF fitting would do better.
"""),
    ai("The dithered-stack version of this: render five frames shifted by 40 pixels in RA and Dec, register them on the CAT positions with integer shifts (no np.roll: it wraps the edges), co-add, and check that the SNR of a faint star grows as sqrt(N).",
       "Ask it to inject point sources at G = 21 to 27 first so there is something faint to measure."),
]

EX7 = [
    md(r"""
This exercise has no solution key beyond a worked example. Work with Jupyter AI as a pair
programmer: you supply the astronomy, it supplies the code, you check the numbers.

### 7.1 — Pick a target

Your own, or one from the reflected-light sample of the ESC notebooks (they are
bright: V = 4 to 6; the file is `lazuli/data/12_nearby_rv_giants.csv`). Write down: the spectral type or SED, the magnitude and the system it is in, and
the measurement you want (a detection? a precision per hour? a depth?).
"""),
    code("""
import pandas as pd
from pathlib import Path
csv = next(d / "data" / "12_nearby_rv_giants.csv" for d in Path.cwd().parents if (d / "data" / "12_nearby_rv_giants.csv").exists())
targets = pd.read_csv(csv)
targets
"""),
    md(r"""
### 7.2 — Describe it to the agent

A prompt that works: *"I want to observe `<target>` (`<spectral type>`, V = `<mag>` Vega) with the
WCC in the r band. Using wcc_etc, build the scene with get_scene with an explicit bandpass and
magsys, find the smallest read split that avoids saturation at 60 s with Simulation.from_sensorfilter
for 'zwo:r' and 'zwo:r+1', and report the precision per point in ppm."*

Check what it does against notebooks 02 and 04: does it pass `warn=False` and look at `saturated`?
Does it respect the 0.25 s minimum frame time?
"""),
    sol(CHOOSE_READS + """
# Worked example: HD 27442 (K1/2 III, V = 4.44). Nearest Pickles template: K3III.
scene = get_scene("K3III", mag=4.44, bandpass="johnson_v", magsys="vegamag")
for label in ("zwo:r", "zwo:r+1", "zwo:bb2"):
    sim = Simulation.from_sensorfilter(label, scene)
    peak = sim.get_peak_pixel(0.25, units="e-").value
    print(f"{label:8s}: peak pixel in a 0.25 s frame {peak:9.0f} e- = {peak / sim.sensor.meta['well_depth']:5.0f} x the well depth")
# WCC cannot observe a V = 4.4 star unsaturated in any mode: the ESC or the IFS are the instruments for this sample.
# How faint would it have to be? Sweep the magnitude in the most forgiving mode:
sim = Simulation.from_sensorfilter("zwo:bb2", scene)
for m in (6, 7, 8, 9, 10):
    sim.update(source__mag=float(m))
    n, r = choose_reads(sim, 60)
    print(f"V = {m}: " + (f"{n} x {60 / n:.2f} s, {1e6 / r['snr']:.0f} ppm per 60 s" if n else "saturated at every split"))
"""),
    md(r"""
### 7.3 — One plot, one number

Whatever your target: produce the one plot that answers your question (SNR versus time, precision
versus magnitude, depth versus filter, a simulated light curve or image) and the one number you would
put in a proposal.
"""),
    sol("""
sim = Simulation.from_sensorfilter("zwo:bb2", get_scene("K3III", mag=9, bandpass="johnson_v", magsys="vegamag"))
fig, ax = sim.plot_peak_pixel(np.logspace(-0.7, 1, 50))
ax.set(xscale="log", yscale="log", title="K3III, V = 9, zwo:bb2: the longest unsaturated frame")
plt.show()
"""),
    md(r"""
### 7.4 — What was wrong

Ask the agent to list every assumption it made that you did not state (template, magnitude system,
background, aperture, jitter, no overheads). Which ones would change the answer by more than a factor
of two?
"""),
    ai("List every assumption you made in 7.2 that I did not state, and for each one estimate how much the precision would change if it were wrong."),
]

# =====================================================================================
# README
# =====================================================================================

README = r"""
# WCC hands-on: simulating Wide-field Context Camera observations

Requirements: `wcc_etc`, `wcc_sim` and `wcc_phot` (plus `matplotlib` and `jupyter`), installed on
the symposium JupyterHub. The Gaia fields used by notebook 06 and exercises 5 and 6 are cached in
`gaia_cache/`, so no network access is needed. A web version of the ETC is at
<https://simulators.schmidtobservatorysystem.org/wcc/>.

**Jupyter AI.** The notebooks assume the Jupyter AI chat is open in the side panel. Boxes marked 🤖
suggest prompts; boxes marked ✏️ ask you to guess a number before computing it. Two exercises contain
a deliberately broken cell.

## Tutorials

| notebook | content |
|---|---|
| [01 — The ETC in one line](01_etc_in_one_line.ipynb) | `get_scene()`, `Simulation.from_sensorfilter()`, `get_image_snr()`, `get_image_exptime_for_snr()`, sweeps, the 5 sigma depth, the sensor:filter labels |
| [02 — The detector](02_detector_saturation_reads.ipynb) | the 16 ke- well, peak pixel, `is_saturated()`, `n_reads`, the noise budget, the bright limit, `update_sensor()` |
| [03 — Scenes](03_scenes_spectra_hosts.ipynb) | stellar templates and magnitude systems, parametric spectra, your own spectrum, the background, Sersic and NGC hosts, redshift |
| [04 — PSF, apertures, images](04_psf_apertures_images.ipynb) | `ImageSimulator`, the aperture and `optimize=True`, pointing jitter, the defocused modes `zwo:r+1` and `zwo:bb2` |
| [05 — Light curves](05_light_curves.ipynb) | `TransitModel`, `LightCurveSimulator`, binning, reads per point for bright hosts |
| [06 — Fields and photometry](06_fields_and_photometry.ipynb) | `simulate_field()` on a Gaia field, the truth catalogue, `run_photometry()`, `centroid_stars()`, FITS output |

## Exercises

Each is one science case. Pick the one closest to your own science; ex1 to ex4 need the ETC only,
ex5 and ex6 render full frames (a few minutes, ~1 GB of memory), ex7 is open-ended.

| exercise | science | covers | difficulty |
|---|---|---|---|
| [1 — A transient on a host galaxy](exercises/ex1_transient_on_host.ipynb) | TDAMM | 01–03 | ★☆☆☆☆ |
| [2 — Transit photometry of a bright star](exercises/ex2_transit_precision.ipynb) | exoplanets | 02, 05 | ★★☆☆☆ |
| [3 — Deep-field depth and stacking](exercises/ex3_deep_field_depth.ipynb) | cosmology / galaxies | 01, 02 | ★★☆☆☆ |
| [4 — Which H-alpha filter?](exercises/ex4_halpha_filter_choice.ipynb) | ISM / nearby galaxies | 03 | ★★★☆☆ |
| [5 — Recovering an AGN flare](exercises/ex5_agn_flare_recovery.ipynb) | TDAMM | 06 | ★★★★☆ |
| [6 — Astrometry in a crowded field](exercises/ex6_crowded_field_astrometry.ipynb) | stellar | 06 | ★★★★☆ |
| [7 — Bring your own target](exercises/ex7_bring_your_own_target.ipynb) | yours | all | open |

Solutions are in [`exercises/solutions/`](exercises/solutions/). The original science-case gallery
notebooks these exercises grew out of are in [`backup/`](backup/).

To regenerate the notebooks: `python build_notebooks.py`, then execute them with `jupyter nbconvert`.
"""


if __name__ == "__main__":
    write(HERE / "01_etc_in_one_line.ipynb", T01)
    write(HERE / "02_detector_saturation_reads.ipynb", T02)
    write(HERE / "03_scenes_spectra_hosts.ipynb", T03)
    write(HERE / "04_psf_apertures_images.ipynb", T04)
    write(HERE / "05_light_curves.ipynb", T05)
    write(HERE / "06_fields_and_photometry.ipynb", T06)

    exercise("ex1_transient_on_host", "Exercise 1 — A transient on a host galaxy", "01–03", "★☆☆☆☆",
             "A supernova or kilonova sits on a host galaxy whose light adds photon noise and can saturate the "
             "nucleus. How faint a transient can the WCC detect, and how much does it depend on where in the galaxy it lands?",
             EX1)
    exercise("ex2_transit_precision", "Exercise 2 — Transit photometry of a bright star", "02, 05", "★★☆☆☆",
             "Transit follow-up needs millimagnitude precision on stars that are bright by survey standards. On the WCC "
             "the limit is photon noise on one side and the shallow CMOS well on the other.",
             EX2)
    exercise("ex3_deep_field_depth", "Exercise 3 — Deep-field depth and stacking", "01, 02", "★★☆☆☆",
             "Galaxy-evolution programs are planned in limiting magnitude: how deep does a field get per band for a given "
             "time, and what does it cost to build that time out of short frames?",
             EX3)
    exercise("ex4_halpha_filter_choice", "Exercise 4 — Which H-alpha filter?", "03", "★★★☆☆",
             "H II regions and star-forming knots are emission lines on a continuum. The WCC has three H-alpha filters "
             "of different width: which gives the best line SNR, and how does the answer depend on the continuum?",
             EX4)
    exercise("ex5_agn_flare_recovery", "Exercise 5 — Recovering an AGN flare", "06", "★★★★☆",
             "A nucleus brightens by a few tenths of a magnitude over days. Inject it into a real Gaia field, render "
             "WCC frames, and see how well differential photometry against field stars recovers it.\n\n"
             "*Renders 2048 px frames: ~10 s each, ~1 GB. Restart the kernel when done.*",
             EX5, setup=SETUP_SIM)
    exercise("ex6_crowded_field_astrometry", "Exercise 6 — Astrometry in a crowded field", "06", "★★★★☆",
             "At 16.9 mas per pixel the WCC resolves fields that seeing blends. How precisely are star positions "
             "recovered from a single frame of Baade's Window, as a function of magnitude and exposure time?\n\n"
             "*Renders 2048 px frames: ~10 s each, ~1 GB. Restart the kernel when done.*",
             EX6, setup=SETUP_SIM)
    exercise("ex7_bring_your_own_target", "Exercise 7 — Bring your own target", "all", "open",
             "Your science, the WCC, and Jupyter AI as a pair programmer.",
             EX7)

    (HERE / "README.md").write_text(README.strip() + "\n")
    print("wrote README.md")
