![The Schmidt Observatory System](docs/tsos_banner.png)

# Science Symposium 2026 — Hackathon Materials

Notebooks, simulators, and sample data for the hackathon sessions at the inaugural
**Schmidt Observatory System (TSOS) Science Symposium 2026**.

## Goals

The hackathon is a hands-on introduction to the four observatories in the system. By the end,
participants should be able to:

- **Run the tools.** Open the notebooks on the symposium JupyterHub (or locally), and execute the
  exposure time calculators, survey simulators, and data-access examples for each observatory.
- **Work with the data products.** Read the simulated and sample data in the shared
  `schmidt-observatory-system` S3 bucket, and understand the formats and conventions each
  observatory uses.
- **Plan a science case.** Take a science question from your own research, and use the
  simulators to estimate depth, cadence, signal-to-noise, or exposure time with each facility.
- **Give feedback.** Report what is missing, confusing, or broken in the tools so the
  observatory teams can improve them before first light.

## Layout

| directory | observatory | content |
|---|---|---|
| [`argus/`](argus/) | Argus Array | ArgusSim survey simulator and visit store: sky coverage, depth maps, and simulated light curves from the planned 5-year survey; real images, cutouts and light curves from the Array's prototype |
| [`dsa/`](dsa/) | DSA | Hackathon release (`hackathon2026/`): HI cube, FRB mocks, and pulsar timing notebooks, plus the DSA sensitivity calculator (`exposure-time-calculator/`) as a web page and Python package |
| [`lazuli/`](lazuli/) | Lazuli | Simulators for the three instruments: WCC (wide-field camera), ESC (coronagraph), and IFS (slicer spectrograph) with tutorials and exercises |
| [`lfast/`](lfast/) | LFAST | Exposure time calculator and fiber throughput tables |
| [`other/`](other/) | — | General-purpose notebooks not tied to one observatory, such as reading FITS files directly from S3 |

Each directory has its own README with installation and data-download instructions.

## Web-based calculators

Browser versions of the exposure time calculators and simulators, with no installation needed,
are at **<https://simulators.schmidtobservatorysystem.org/>**. The notebooks here go one level
deeper: the same calculations as Python you can modify, chain together, and run on your own targets.

## Getting started

The notebooks are written for the symposium JupyterHub, where the S3 bucket is already readable
(through the S3 API and as an NFS mount at `~/s3`). To run them elsewhere, follow the per-directory
install instructions and request AWS credentials for the bucket.

## Using Claude Code

This repository includes a `CLAUDE.md` that gives Claude Code context about the observatory system: directory layout, installed packages and their entry points, tutorial notebook locations, the shared `lazuli_astrosim_data` package, the S3 data bucket, and the Python environment.

We have also created custom skills for Claude Code that load automatically based on your prompt — you don't need to invoke them manually but you can as slash commands (e.g., /wcc-etc):

| Skill | Loads when you ask about… |
|---|---|
| `wcc-etc` | WCC SNR, depth, exposure time for point or extended sources |
| `wcc-sim` | Simulated WCC FITS images, stacks, or dithered mosaics |
| `lazuli-ifs` | IFS SNR, spectral cubes, supernova/kilonova spectroscopy |
| `lazuli-exo` | Exoplanet atmosphere detectability, transit spectroscopy with the coronagraph |
| `argus` | Argus sky coverage, per-position depth, cadence, or light curve injection; the prototype data |
| `lfast` | LFAST SNR, exposure time, spectrograph configuration (CSHELL vs WIYN Bench), fiber choice, or custom SED |
| `dsa` | DSA notebooks, data products (FRB, pulsar, continuum), and directory layout; points to the `dsa-sensitivity` skill for ETC questions |
| `cross-observatory` | Questions spanning more than one facility |
