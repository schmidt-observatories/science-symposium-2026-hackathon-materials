---
name: dsa
description: DSA hackathon materials. Load for questions about the DSA notebooks, data products (HI/continuum, FRB mocks, pulsar timing archives), the dsahackathon2026 helper package, or how the dsa/ directory is organized. For sensitivity/ETC questions, read dsa/exposure-time-calculator/skill/dsa-sensitivity/SKILL.md and dsa/exposure-time-calculator/CLAUDE.md.
---

# DSA Hackathon Materials

The `dsa/` directory has two subdirectories:

| Subdirectory | Contents |
|---|---|
| `dsa/hackathon2026/` | Notebooks and sample data products for the convening |
| `dsa/exposure-time-calculator/` | DSA sensitivity calculator: Python package (`dsa_etc`) + web page |

## Subdirectory 1 — `dsa/hackathon2026/`

### Installed helper package

```python
from dsahackathon2026 import data_dir, find_product

data_dir()                  # path to the downloaded data/ directory
find_product("DPR-DSA-11")  # resolves to a file under data/
```

### Notebooks

| Notebook | Data product | What it does |
|---|---|---|
| `dsa07_load_plot.ipynb` | DPR-DSA-03 | Load and plot a DSA continuum mosaic (FITS) |
| `dsa11_dsa12_frb.ipynb` | DPR-DSA-11/12 | Explore FRB mock data: voltage cutout (HDF5, 4+4-bit complex) and total-intensity dynamic spectrum; DM, Stokes I, polarisation |
| `dsa13_inspect_archives.ipynb` | DPR-DSA-13 | Inspect CHR folded pulsar archives (PSRFITS, PSRCHIVE-readable) |
| `dsa13_timing.ipynb` | DPR-DSA-13 | Pulsar timing workflow with PSRCHIVE + PINT |

### Data download

```bash
aws s3 sync s3://BUCKET/PREFIX/dsa/ dsa/hackathon2026/data/
```

See `dsa/hackathon2026/DATA.md` for science descriptions and volumes. Key data products:

- **DPR-DSA-11** — FRB voltage cutout. HDF5, 813 ch × 2 pol × 2460 samples, 4+4-bit complex, coherently dedispersed at DM 200. 4.1 MB.
- **DPR-DSA-12** — FRB total-intensity dynamic spectrum. HDF5, 813 ch × 64 samples at 1 ms. 4.1 MB combined with DPR-DSA-11.
- **DPR-DSA-13** — Synthetic folded pulsar archives. PSRFITS, 42 files (1 MSP in a WD binary, P = 6.1 ms, DM 60, 7 visits over 2 yr). 733 MB.

### Environment

Notebooks requiring PSRCHIVE (the pulsar timing ones) need the conda env:

```bash
mamba activate dsahackathon2026
```

The FRB and continuum notebooks run in the standard symposium `notebook` env.

### Answer key

```python
from dsahackathon2026 import answer_key_dir
# True timing model for DPR-DSA-13 is under answer_key_dir()
```

## Subdirectory 2 — `dsa/exposure-time-calculator/`

This is the DSA sensitivity and exposure-time calculator. It has its own `CLAUDE.md` with full model documentation and change instructions.

**For DSA sensitivity/ETC questions:** read `dsa/exposure-time-calculator/CLAUDE.md` and/or `dsa/exposure-time-calculator/skill/dsa-sensitivity/SKILL.md`.

Quick reference:

```bash
cd dsa/exposure-time-calculator/python
python3 -m dsa_etc.cli --ra 150.12 --dec 2.21               # survey sensitivity at a position
python3 -m dsa_etc.cli --mode targeted --ra 150.12 --dec 2.21 --hours 10 --json
```

The Python package (`dsa_etc`) and the web page (`web/`) implement the same noise model; change both together.
