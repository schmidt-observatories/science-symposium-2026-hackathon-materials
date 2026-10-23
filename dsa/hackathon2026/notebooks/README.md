# notebooks_jupyterhub/

Copies of `../notebooks/` for the **Schmidt JupyterHub**, where the DSA release sits on the
`schmidt-observatory-system` S3 bucket, NFS-mounted read-only at
`~/s3/schmidt-observatory-system/dsa/v1-convening/` (10 DPR-DSA-07
cubes; no `MANIFEST.csv`, `fold.par`, `volume.json`, README or DSA-03/11/12 files). The
notebooks read straight from the mount and write everything (rewritten archives, `fold.par`,
templates, ToAs) to `~/convening2026_work/`. Same science edits as `../notebooks_fixed/`.

| Notebook | Needs | Changes vs original |
|---|---|---|
| `dsa3_load_plot.ipynb` | astropy, numpy, matplotlib (hub image) + `dsahackathon2026` | data root = mount; loads a DPR-DSA-07 cube (no DSA-03 in `v1-convening`) and averages it over frequency |
| `dsa13_inspect_archives.ipynb` | + PSRCHIVE (CLI + Python), tempo2 | data root = mount; inventory built from the files; `fold.par` recovered from the PSRPARAM HDU into the work dir; beam term dropped; README / `volume.json` cells skipped |
| `dsa13_timing.ipynb` | + PINT | same, plus outputs to `~/convening2026_work/templates/`; phase-connection limited to the visits present (visit 0) |

`dsa11_dsa12_frb.ipynb` is not copied: the DSA-11/12 HDF5 files are not on the bucket.

**CHR notebooks (`dsa13_*`)** read the 150 DPR-DSA-13 archives (P1-P3, visits 0-6) from the sibling
`~/s3/schmidt-observatory-system/dsa/v2-convening/` and only rewrite the pulsar in use (P3, 42 files). Work files go
to `/tmp/convening2026_work/` (set `DSA_WORK` to change it): the home directory has a quota that the `pam` rewrites
exceed. The notebooks set `PSRCHIVE` and `TEMPO2` themselves, because a kernel started from a kernelspec does not run
conda's activate scripts. `dsa13_timing` takes ~3 min and reproduces the expected chi2_red sequence for P3.

## Setup on the hub (once)

```bash
cd ~ && tar xzf ~/s3/schmidt-observatory-system/dsa/v1-convening/convening2026-release-2026.9.28.tar.gz
pip install -e ~/convening2026-release-2026.9.28          # the dsahackathon2026 helper package
```

CHR notebooks only: PSRCHIVE, tempo2 and PINT are not in the hub image, so create the env and register it as a kernel
(the hub's default Python 3 kernel does not have `pam`):

```bash
mamba env create -f ~/convening2026-release-2026.9.28/environment.yml
/srv/conda/envs/dsahackathon2026/bin/python -m ipykernel install --user --name dsahackathon2026 --display-name "Python (dsahackathon2026)"
```

Then open `dsa13_*.ipynb` with **Python (dsahackathon2026)** (Kernel -> Change Kernel). `dsa3_load_plot` runs on the default
Python 3 kernel. If the mount lives elsewhere,
set `DSA_DATA=/path/to/v1-convening` before starting the kernel.

## Notes

- Verified on a laptop against a read-only copy of the same 16 files (`chmod -w`), not on the
  hub itself: all three run end to end with no errors.
- The `pam` rewrite step (PSRCHIVE crash workaround, see `report/changes.md` item 5) is kept;
  it is harmless if the hub's Linux PSRCHIVE does not have the crash (~100 MB, a few seconds).
- `dsa/v2-convening/` on the bucket does hold a DSA-03 mosaic
  (`mockfm_DPR-DSA-03_mp37_701.235_20260922.fits`); the original `dsa3_load_plot` works on it
  if you point `DS` there and have the RAM for the full image (the parent repo's
  `01_opening_fits_from_s3.ipynb` shows cutouts via `hdu.section` instead).
- Regenerate from `report/build_hub.py` (run from the release root) if the originals change.
