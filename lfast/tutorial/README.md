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
