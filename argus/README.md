# Argus Array

The Argus Array images the entire visible sky every 60 seconds in two bands,
β (blue, about 365–520 nm) and ρ (red, about 565–825 nm), with 1,212 small
telescopes. There are two sets of materials here: the simulated 5-year
survey, and real data from the Array's prototype.

| directory | content |
|---|---|
| [`argus_survey_model/`](argus_survey_model/) | ArgusSim: the simulated 5-year survey, with depth maps, the window function, every exposure of any position, and simulated light curves of any model. Start with its two tutorials in `notebooks/`; `SED_demonstration.ipynb` turns any spectrum into Argus magnitudes and count rates. |
| [`prototype_data/`](prototype_data/) | Real images, per-star cutouts with data-quality and calibration records, and light curves from the prototype (two co-pointed cameras, one per band), with four tutorials and four exercises |

The two meet in the prototype data's exercises 3 and 4: the prototype's
measured noise against the simulation's prediction, and a prototype light
curve injected into five simulated years.

ArgusSim names the bands `beta` and `rho`, the same names the prototype data use.
