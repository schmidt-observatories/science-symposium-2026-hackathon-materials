# Science Symposium 2026 — Hackathon Materials

Notebooks, simulators, and sample data for the Schmidt Observatory System (TSOS) Science Symposium 2026 hackathon. The four observatories are **Lazuli** (space telescope: WCC wide-field camera + IFS slicer spectrograph + ESC coronagraph), **DSA** (radio array), **Argus Array** (wide-field photometric survey), and **LFAST** (Large Fiber Array Spectroscopic Telescope: an array of 0.726 m telescopes feeding one fiber spectrograph).

## Directory layout

| directory | observatory | content |
|---|---|---|
| `lazuli/wcc/` | Lazuli WCC | Tutorial notebooks for the wide-field context camera ETC and image simulator |
| `lazuli/ifs/` | Lazuli IFS | Tutorial notebooks for the slicer integral-field spectrograph |
| `lazuli/esc/` | Lazuli ESC | Coronagraph science case notebooks |
| `lazuli/science_gallery/` | Lazuli (all) | Eleven one-question science-case notebooks spanning WCC, IFS, and ESC (exoplanet atmospheres, SN Ia, kilonovae, TDEs, transit photometry, crowded fields) |
| `dsa/hackathon2026/` | DSA | HI cube, FRB mocks, pulsar timing notebooks |
| `dsa/exposure-time-calculator/` | DSA | Sensitivity calculator: web page + Python package (`dsa_etc`) |
| `argus/argus_survey_model/` | Argus Array | Survey simulator (`argus_sim`): sky coverage, depth, light curves |
| `argus/prototype_data/` | Argus Array | Prototype data notebooks and exercises: images, minipix cutouts with DQ and calibration records, light curves |
| `lfast/tutorial/` | LFAST | Tutorial notebooks and exercises for the `lfast_etc` exposure time calculator |

## Key installed packages

### Lazuli WCC
- **`wcc_etc`** — exposure time calculator; entry point `Simulation(telescope, sensor, scene, time)`. Skills: `wcc-etc`.
- **`wcc_sim`** — end-to-end pixel-level image simulator; entry point `WCCObservation` / `simulate_field`. Skills: `wcc-sim`.

### Lazuli IFS (slicer)
- **`slicersim`** — IFS observation simulator; high-level entry points `LazuliSupernova`, `LazuliKilonova`, `LazuliTarget`, `lazuli_etc`, `lazuli_sn_etc`. Skills: `lazuli-ifs`.

### Lazuli ESC (coronagraph)
- **`lazuli_exo`** — exoplanet transmission spectroscopy ETC; high-level entry points `lazuli_exo.observe()`, `lazuli_exo.simulate()`, `list_planets()`, `list_scenarios()`. Skills: `lazuli-exo`.

### DSA
- **`dsa_etc`** — sensitivity calculator CLI and Python API. Has its own `CLAUDE.md` at `dsa/exposure-time-calculator/CLAUDE.md` and a skill at `dsa/exposure-time-calculator/skill/dsa-sensitivity/SKILL.md`.

### LFAST
- **`lfast_etc`** — exposure time calculator for the telescope array (WIYN Bench + CSHELL); entry point `LFASTETC(preset, n_telescopes)` with `Source`, `Telescope`, `Instrument`, `Sky`. Package: <https://github.com/schmidt-observatories/lfast-etc>. Skills: `lfast`.

### Argus Array
- **`argus_sim`** — survey simulator. Source in `argus/argus_survey_model/src/argus_sim/`. Skills: `argus`.
- **`argex`** — client of the Argus archive; the prototype notebooks use `argex.read()` to open the staged sample's FITS files. Skills: `argus`.

### Shared data
- **`lazuli_astrosim_data`** — bundled throughput curves, PSF files, and reference spectra used by `wcc_etc`, `wcc_sim`, and `slicersim`.
- S3 bucket `schmidt-observatory-system` is pre-mounted at `~/s3` on the symposium JupyterHub.
- Lazuli notebooks set `os.environ['SNCOSMO_DATA_DIR']` at the beginning to point to the read-only S3 bucket containing pre-downloaded data needed by `sncosmo`. If you need to download more filters, bandpasses, spectra, etc. to answer a user query, you should `cp -r ~/s3/schmidt-observatory-system/nov26-symposium/sncosmo_data_dir/ ~/` and write new files to that local user-level directory, and then update `$SNCOSMO_DATA_DIR` for your notebook.

## Notebooks and tutorials

Each instrument's tutorial notebooks are the best first reference:
- WCC: `lazuli/wcc/tutorial/01_tdamm_transient_on_host.ipynb` through `07_ism_halpha_emission_line.ipynb`
- IFS: `lazuli/ifs/tutorial/01_exposure_time_calculator.ipynb` through `06_cubes_and_fields.ipynb`
- ESC: `lazuli/esc/tutorial/` — coronagraph exercises
- Lazuli science gallery: `lazuli/science_gallery/01` through `11` — eleven one-question worked examples spanning all three Lazuli instruments (exoplanet atmospheres, SN Ia, kilonovae, emission lines, TDEs, transit photometry, crowded fields); prefer these as starting points over building from scratch
- LFAST: `lfast/tutorial/01_etc_in_one_line.ipynb` through `04_sensitivity_maps_array_scaling.ipynb` — the `lfast_etc` ETC (WIYN Bench and CSHELL, per resolution element, array size as a parameter), plus six science exercises in `lfast/tutorial/exercises/`. Skills: `lfast`.
- DSA: `dsa/hackathon2026/notebooks/dsa07_load_plot.ipynb` — load and plot the DPR-DSA-07 HI/continuum data product; `dsa11_dsa12_frb.ipynb` — browse FRB mock data products (DPR-DSA-11/12); `dsa13_inspect_archives.ipynb` and `dsa13_timing.ipynb` — inspect CHR pulsar timing archives and derive a timing solution
- Argus: `argus/argus_survey_model/notebooks/tutorial_depth_calculation.ipynb` — compute the 5-sigma depth of an Argus exposure; `tutorial_survey_data.ipynb` — open and query a simulated Argus visit store

## Environment

- Python 3.13, conda env `notebook`
- All packages installed in `/srv/conda/envs/notebook/lib/python3.13/site-packages/`
- Web-based calculators also available at `https://simulators.schmidtobservatorysystem.org/`

## Jupyter MCP tool paths

`mcp__Jupyter_MCP_Server__*` tools (`read_notebook`, `read_notebook_cells`, etc.) take paths relative to the Jupyter server root, not the repo root or shell working directory. The repo is likely in a subdirectory of the server root, so prefix paths accordingly (e.g. `science-symposium-2026-hackathon-materials/lazuli/...`) and verify you are passing the correct path relative to the server root.
