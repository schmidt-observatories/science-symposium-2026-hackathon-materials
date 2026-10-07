# notebooks_fixed/

Copies of `../notebooks/` with the smallest edits needed to run on **this machine with the data
currently in `data/`** (6 visit-0 CHR archives, 10 DPR-DSA-07 cubes; no DSA-03/11/12 files, no
`MANIFEST.csv`, `fold.par`, `volume.json`). The originals in `notebooks/` are untouched. Each
notebook's first markdown cell says what was changed; `report/changes.md` has the full log.

| Notebook | Kernel | Changes vs original |
|---|---|---|
| `dsa3_load_plot.ipynb` | `python3` (py313) | loads a DPR-DSA-07 cube instead of DSA-03; averages the cube over frequency to get a 2D image |
| `dsa13_inspect_archives.ipynb` | `Python 3 (convening2026)` | inventory built from files (no manifest); `fold.par` recovered from the archive's PSRPARAM HDU; beam term dropped (needs `theta_deg`); `volume.json` cell skipped if absent; archives rewritten once by `pam` into `data/rewritten/` (PSRCHIVE crash workaround) |
| `dsa13_timing.ipynb` | `Python 3 (convening2026)` | same inventory / `fold.par` / rewrite as above; phase-connection steps limited to visits present (visit 0) |

`dsa11_dsa12_frb.ipynb` is not copied: it needs the DSA-11/12 HDF5 files and has nothing to fix.

Outputs written by the CHR notebooks go to `data/rewritten/` and `data/templates/` (gitignored).
Regenerate from the builder script if the originals change (session scratch:
`build_fixed.py`, see `report/changes.md`).
