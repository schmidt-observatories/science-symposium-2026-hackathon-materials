# Change log — getting `notebooks/` to run locally

Date: 2026-10-07. Machine: Apple Silicon Mac (arm64), conda at `~/anaconda3`.
Goal: run the four notebooks with as few changes as possible.

## Code changes

None. No file under `notebooks/` or `src/` was modified.

## Environment changes

1. **Reinstalled the helper package editable** into the existing `py313` conda env
   (`~/anaconda3/envs/py313/bin/python -m pip install -e . --no-deps`).
   - Root cause: `convening2026` had been installed *non-editable* into site-packages, so
     `paths.py` computed `REPO_ROOT = Path(__file__).resolve().parents[2]` as
     `.../py313/lib/python3.13` and `data_dir()` pointed at a non-existent
     `.../python3.13/data`. Every notebook failed in its first `data_dir()` / `find_product()` /
     `H.inventory()` call.
   - After the reinstall `data_dir()` resolves to this repo's `data/` (verified).
   - The default Jupyter `python3` kernel on this machine is the `py313` env, so the notebooks
     pick it up with no kernel change.

2. **Created a conda env `convening2026`** (from `environment.yml` contents) for the two CHR
   notebooks, which need PSRCHIVE command-line tools (`vap`, `pam`, `psradd`, `pat`, `paas`,
   `psrsmooth`) and the `psrchive` Python module.
   - conda-forge has no `osx-arm64` build of `psrchive`, only `osx-64`. The env was created
     with `CONDA_SUBDIR=osx-64` so it runs under Rosetta 2 (verified present).
   - Command: `CONDA_SUBDIR=osx-64 conda create -n convening2026 --override-channels
     -c conda-forge python=3.12 psrchive pint-pulsar numpy scipy astropy matplotlib pandas
     jupyter ipywidgets pyyaml h5py pip`, then `pip install -e .` into it.
   - Result: see "Status" below.

3. Left the pre-existing `.venv/` untouched. It is a bare Python 3.14 venv with no `pip` and
   no packages, so it cannot run anything; `pint-pulsar` also has no 3.14 build. Use the conda
   envs instead (or delete `.venv/`).

## Blockers that are not code problems: missing input data

`data/` currently holds 6 CHR archives (visit 0 only) and 10 `mock_DPR-DSA-07_zb_*.fits`
spectral-line cubes. No notebook reads DPR-DSA-07. The files each notebook actually needs:

| Notebook | Needs under `data/` | Present? |
|---|---|---|
| `dsa3_load_plot.ipynb` | `*DPR-DSA-03*.fits` continuum mosaic | **no** |
| `dsa11_dsa12_frb.ipynb` | `*DPR-DSA-11*.h5`, `*DPR-DSA-12*.h5` | **no** |
| `dsa13_inspect_archives.ipynb` | `MANIFEST.csv`, `fold.par` (or `ephemerides/P3/fold.par`), CHR bundle `README.md`, `volume.json`, archives | only 6/42 archives |
| `dsa13_timing.ipynb` | `MANIFEST.csv`, `fold.par`, archives from all 7 visits | only 6/42 archives |

Notes:
- The S3 bucket (`s3://schmidt-observatory-system/dsa/v2-convening/`, see
  `../../notebooks/01_opening_fits_from_s3.ipynb`) is private; there are no AWS credentials
  on this machine, so the missing files could not be fetched here. On the hub they are
  mounted at `~/s3/schmidt-observatory-system/`.
- `fold.par` could be regenerated from the `PSRPARAM` HDU inside any archive, but
  `MANIFEST.csv` cannot: its `theta_deg`, `B_k` and `discovery` columns are simulation
  metadata, and the archive headers carry the pulsar position as the pointing centre
  (`RA/DEC == STT_CRD1/2` in all six files). Reconstructing the manifest would mean inventing
  values, so it was not done.
- With only visit-0 archives, `dsa13_timing.ipynb` would also stop at its multi-visit fits
  even with a manifest.

## Verification run (py313 kernel, after change 1)

`jupyter nbconvert --execute --allow-errors` on all four notebooks:
- `dsa3_load_plot`: fails at `find_product("DPR-DSA-03")` — file not present.
- `dsa11_dsa12_frb`: fails at `find_product("DPR-DSA-11")` — file not present.
- `dsa13_inspect_archives`: fails at `H.inventory()` — no `MANIFEST.csv`.
- `dsa13_timing`: fails at `H.inventory()` — no `MANIFEST.csv`.

All remaining errors are downstream `NameError`s from those first failures. No code error
was reached in any notebook.

## Status

- `convening2026` env created successfully (osx-64 under Rosetta). Verified in it: `import psrchive`,
  `import pint` (1.1.7), `convening2026.data_dir()` → this repo's `data/`, `H.load()` of a
  CHR archive, and `vap`, `pam`, `psradd`, `pat`, `paas`, `psrsmooth` on PATH.
- Registered a Jupyter kernel **"Python 3 (convening2026)"** (`ipykernel install --user
  --name convening2026`). Select it for the two `dsa13_*` notebooks.
- `dsa3_load_plot` and `dsa11_dsa12_frb` need no PSRCHIVE; the default `python3` kernel
  (`py313`) runs them once the files are in `data/`.

## What is still needed to run each notebook

Copy from the hub (`~/s3/schmidt-observatory-system/dsa/v2-convening/`) into `data/`:
- `dsa3_load_plot`: a `*DPR-DSA-03*.fits` mosaic (e.g. `mockfm_DPR-DSA-03_mp37_701.235_20260922.fits`, 2.2 GB).
- `dsa11_dsa12_frb`: `*DPR-DSA-11*.h5` and `*DPR-DSA-12*.h5`.
- `dsa13_inspect_archives` / `dsa13_timing`: the whole CHR bundle (`MANIFEST.csv`, `fold.par`
  or `ephemerides/P3/fold.par`, the bundle `README.md`, `volume.json`, all 42 archives,
  optional `answer_key/`).

## `notebooks_fixed/` (added on request, 2026-10-07)

Copies of three notebooks with targeted cell edits so they run on the local data. Built by a
small nbformat script (session scratch `build_fixed.py`), executed headless, and verified:
no error outputs, all code cells executed, figures produced
(`dsa3_load_plot` 4/4 cells, 1 figure; `dsa13_inspect_archives` 11/11, 5 figures;
`dsa13_timing` 13/13, 6 figures). Originals in `notebooks/` untouched.

Edits per notebook (all marked with comments in the cells):

- **dsa3_load_plot**: `PRODUCT = "DPR-DSA-07"`; if the image is a 3D cube, average over the
  frequency axis before plotting. (`data/` has DSA-07 cubes, not a DSA-03 mosaic.)
- **dsa13_inspect_archives**: kernel set to `convening2026`; inventory built from
  `data/*.psrfits` headers (no `MANIFEST.csv`; `B_k`/`theta_deg`/`discovery` are not
  recoverable); `fold.par` written from the archive's PSRPARAM HDU when absent; header cell
  reads the *original* file (see rewrite below); beam term set to `theta = 0` with the B_k
  print removed; `volume.json` cell guarded.
- **dsa13_timing**: same inventory + `fold.par`; phase-connection `steps` filtered to visits
  present in `data/` (only visit 0 here, so one fit step runs).

### Additional environment findings while making these run

4. **`pam`/`paas` failed with "fits_movnam_hdu PSRPARAM: illegal HDU number" / "Please ensure
   that PSRFITS template is current".** Cause: the kernel was launched without the env's
   activation scripts, so `PSRCHIVE=$CONDA_PREFIX` and `TEMPO2=.../share/tempo2` were unset
   and PSRCHIVE could not find `share/psrheader.fits`. Fix: the `convening2026` kernelspec
   (`~/Library/Jupyter/kernels/convening2026/kernel.json`) now launches through
   `conda run -n convening2026 --no-capture-output python -m ipykernel_launcher ...`, which
   runs the activation scripts. (`pam` returns exit 0 even on this failure, so `H.sh()` did not
   raise; the symptom was an empty stdout → `IndexError`.)

5. **Intermittent PSRCHIVE crash loading the chrpreview-written archives.** In this build
   (psrchive 2025.04.24, conda-forge osx-64, under Rosetta) `Archive_load` on the original
   `dsa13_*.psrfits` files segfaults/aborts in roughly 10–50 % of runs
   (`Reference::Able::Handle::decrement ... reference count==0`, or
   `RuntimeError: no FITSHdrExtension`), mid-call, in Python and in `psrstat` alike;
   `vap` and `pam` on the same files never crashed in 10/6 runs. Removing the HIERARCH
   `observationID`/`PRODUCTVER`/`DDSCHEMA` cards, `CAL_MODE`, or the SUBINT `TUNIT`/`TDIM`
   cards did not change the crash rate, so it is not a header-parsing issue. A copy rewritten
   once by PSRCHIVE itself (`pam -e psrfits -u data/rewritten <file>`, which adds the
   `INDEXVAL` and `PERIOD` SUBINT columns the originals lack) loaded 0/26 crashes. The rewrite
   is lossless apart from 16-bit requantisation (max |Δ| = 3e-6 vs data std 0.016, profile
   cross-correlation shift 0 bins, PSRPARAM text identical). Workaround used in both CHR
   notebooks: rewrite each archive once into `data/rewritten/` and load those; the DSA header
   keywords (dropped by the rewrite) are read from the original. Whether this crash also
   occurs on the hub's Linux build is unknown. `psrstat -c snr` still aborts on the rewritten
   files, but no notebook uses it.

6. Created `data/templates/` so `dsa13_timing` writes its products there (gitignored) instead
   of `output_02/` next to the notebook.

## notebooks_jupyterhub/ (hub versions, read-only S3 mount)

Created `notebooks_jupyterhub/` for the Schmidt JupyterHub, where the release is on the
`schmidt-observatory-system` bucket NFS-mounted read-only at
`~/s3/schmidt-observatory-system/dsa/v1-convening/` (listing supplied by the user: the same 6
CHR archives + 10 DSA-07 cubes as the local `data/`, plus the release tarball; nothing else).
Built from `notebooks/` by `report/build_hub.py` (same edits as `notebooks_fixed/`, plus):

- **Data root**: `DS = Path(os.environ.get("DSA_DATA", "~/s3/schmidt-observatory-system/dsa/v1-convening")).expanduser()`
  replaces `data_dir()`; `find_product(..., data=DS)` in dsa3. The env-var override exists so
  the notebooks could be tested here against a read-only copy.
- **Writes**: the mount is read-only, so `WORK = ~/convening2026_work/` holds `rewritten/`,
  `fold.par` and `templates/` (was `data/rewritten`, `data/fold.par`, `data/templates`). The
  `os.access`/`output_02` fallback in `dsa13_timing` is removed (it would have triggered,
  since `WORK/templates` does not exist on first run). Every remaining
  `H.fold_ephemeris(DS, ...)` call (inspect cell 24, timing cells 4 and 15) now uses `FOLD`,
  because `fold_ephemeris` only searches under the data root.
- `dsa13_inspect_archives` cell 4: the `data/README.md` read is guarded (no README on the bucket).
- Kernelspec set to the hub's default `python3` for all three (PSRCHIVE/PINT/tempo2 must be
  installed into that env; the hub image only has astropy/s3fs/matplotlib/numpy per the parent
  repo README).

Verification (this laptop, `DSA_DATA` pointed at a `chmod -R a-w` copy of the 16 files, CHR
notebooks executed on the `convening2026` kernel): dsa3 4/4 cells, dsa13_inspect 11/11
(S/N 8.7, best DM 59.9838), dsa13_timing 13/13 (6 ToAs, visit-0 chi2_red 0.53); no errors;
nothing written to the mount. One run hit the intermittent PSRCHIVE abort (item 5) in
`psradd`; the same command then succeeded 6/6 standalone and the full rerun was clean. Not
verified on the hub itself. The test work dir `~/convening2026_work` was removed afterwards.
Builder scripts for both fixed sets are now kept in `report/` (`build_fixed.py`, `build_hub.py`).
