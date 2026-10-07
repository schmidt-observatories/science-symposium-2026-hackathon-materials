# Notebooks (main branch)

Download the sample into **`data/`** first ([data/README.md](../data/README.md)).
Every notebook resolves products from that single directory.

```bash
mamba activate convening2026   # or: pip install -e .
cd notebooks && jupyter lab
```

| Notebook | Purpose |
|----------|---------|
| [dsa3_load_plot.ipynb](dsa3_load_plot.ipynb) | **DPR-DSA-03** continuum mosaic: find by name under `data/`, load, plot |
| [dsa13_inspect_archives.ipynb](dsa13_inspect_archives.ipynb) | **DPR-DSA-13** CHR archives from `data/` (`MANIFEST.csv`) |
| [dsa13_timing.ipynb](dsa13_timing.ipynb) | **DPR-DSA-13** timing with PSRCHIVE + PINT |
| [dsa11_dsa12_frb.ipynb](dsa11_dsa12_frb.ipynb) | **DPR-DSA-11** / **DPR-DSA-12** FRB mocks under `data/` |

Helpers: `from convening2026 import data_dir, find_product` (and
`convening2026.chr_helpers` for the CHR notebooks).

For CHR timing, a folding ephemeris (`data/fold.par` or `data/ephemerides/P3/fold.par`)
is required. An `answer_key/` tree is **optional** (simulation truth for self-checks).
