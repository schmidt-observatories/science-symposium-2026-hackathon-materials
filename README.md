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
| [`argus/`](argus/) | Argus Array | ArgusSim survey simulator and visit store: sky coverage, depth maps, and simulated light curves from the planned 5-year survey |
| [`dsa/`](dsa/) | DSA-2000 | Hackathon release (`hackathon2026/`): HI cube, FRB mocks, and pulsar timing notebooks, plus the DSA sensitivity calculator (`exposure-time-calculator/`) as a web page and Python package |
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
