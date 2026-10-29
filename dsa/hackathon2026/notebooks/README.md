# notebooks_jupyterhub/

Copies of `../notebooks/` for the **Schmidt JupyterHub**, where the DSA release sits on the
`schmidt-observatory-system` S3 bucket, NFS-mounted read-only at
`~/s3/schmidt-observatory-system/dsa/v1-convening/` (10 DPR-DSA-07
cubes; no `MANIFEST.csv`, `fold.par`, `volume.json`, README or DSA-03/11/12 files). The
notebooks read straight from the mount and write everything (rewritten archives, `fold.par`,
templates, ToAs) to `~/convening2026_work/`. Same science edits as `../notebooks_fixed/`.
## Setup on the hub 

**Attendees of the Florence Symposium (2i2c jupyterhub) require no special setup beyond the jupyterhub environment.**

Outside of the symposium, you may set this up as:

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

Then open `dsa13_*.ipynb` with **Python (dsahackathon2026)** (Kernel -> Change Kernel). `dsa03_load_plot` runs on the default
Python 3 kernel. If the mount lives elsewhere,
set `DSA_DATA=/path/to/v1-convening` before starting the kernel.