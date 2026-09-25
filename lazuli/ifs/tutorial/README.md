# slicersim hands-on: simulating Lazuli slicer observations

Requirements: `pip install slicersim` (plus `matplotlib` and `jupyter`).
The first run downloads a few model files (SALT, kilonova models, CalSpec stars).

## Tutorials

| notebook | content |
|---|---|
| [01 — Exposure time calculator](01_exposure_time_calculator.ipynb) | `lazuli_sn_etc()`, `lazuli_etc()`, `LazuliSupernova`, `setup_to_snr()`, exposure time, spectrum with and without noise |
| [02 — Lazuli targets](02_lazuli_targets.ipynb) | the pre-built science targets, and `LazuliTarget` to simulate any spectrum |
| [03 — Detector and exposure time](03_detector_and_exposure_time.ipynb) | H4RG non-destructive readout, MACC(n, m, d), `change_detector()`, what `setup_to_snr()` does |
| [04 — Changing properties](04_changing_properties.ipynb) | `change_properties()` on the target and the detector, EOL configuration, magnitude of any target |
| [05 — Variance budget](05_variance_budget.ipynb) | the variance sources, `switch_off`, `get_variance_contribution()` |
| [06 — Cubes and fields](06_cubes_and_fields.ipynb) | `get_cube()`, the narrow and wide fields, projection onto the detector with `SlicerMapper` |

## Exercises

| exercise | covers | difficulty |
|---|---|---|
| [1 — Planning with the ETC](exercises/ex1_planning_with_the_etc.ipynb) | 01–02 | ★☆☆☆☆ |
| [2 — Your own targets](exercises/ex2_your_own_targets.ipynb) | 01–02 | ★★☆☆☆ |
| [3 — Readout strategy](exercises/ex3_readout_strategy.ipynb) | 03 | ★★★☆☆ |
| [4 — What if?](exercises/ex4_what_if.ipynb) | 03–04 | ★★★☆☆ |
| [5 — Noise, cubes and the detector](exercises/ex5_noise_cubes_detector.ipynb) | 05–06 | ★★★★☆ |

Solutions are in [`exercises/solutions/`](exercises/solutions/).
