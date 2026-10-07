"""Copy notebooks/ -> notebooks_jupyterhub/: same edits as notebooks_fixed/, but the data root is the read-only
S3 mount on the hub and everything the notebooks write goes to a writable work dir."""
import nbformat as nbf
from pathlib import Path

SRC, DST = Path("notebooks"), Path("notebooks_jupyterhub")
DST.mkdir(exist_ok=True)

def sub(nb, idx, old, new):
    c = nb.cells[idx]
    assert old in c.source, (idx, old)
    c.source = c.source.replace(old, new)

PATHS = '''import os
# JupyterHub: the DSA release is on the S3 bucket, NFS-mounted read-only under ~/s3. DSA_DATA overrides it (tests).
DS = Path(os.environ.get("DSA_DATA", "~/s3/schmidt-observatory-system/dsa/v1-convening")).expanduser()
WORK = Path("~/convening2026_work").expanduser(); WORK.mkdir(exist_ok=True)   # the mount is read-only: outputs go here
'''

INVENTORY = PATHS + '''from astropy.io import fits
# MANIFEST.csv is not on the bucket: build the inventory from the archives.
# theta_deg / B_k / discovery (simulation metadata) are not recoverable from the files.
# PSRCHIVE 2025.04.24 (conda-forge) crashes intermittently when loading the chrpreview-written archives;
# copies rewritten once by pam (lossless up to 16-bit requantisation) load reliably.
# `path` points at the rewritten copy (for PSRCHIVE), `orig` at the original (keeps the DSA header keywords).
RW = WORK / "rewritten"; RW.mkdir(exist_ok=True)
rows = []
for p in sorted(DS.glob("*.psrfits")):
    if not (RW / p.name).exists():
        H.sh(f"pam -e psrfits -u {RW} {p}")
    h = fits.getheader(p, 0); v, ptg = H.visit_ptg(p.name)
    rows.append(dict(file=p.name, path=str(RW / p.name), orig=str(p), pulsar=h["SRC_NAME"], visit=v, ptg=ptg, discovery=False,
                     product_type="DPR-DSA-13", obs_id=h["observationID"],
                     start_mjd=h["STT_IMJD"] + h["STT_SMJD"] / 86400.0, nbin=fits.getheader(p, "SUBINT")["NBIN"]))
man = pd.DataFrame(rows)'''

FOLDPAR = '''FOLD = WORK / "fold.par"
if not FOLD.exists():   # not on the bucket: recover the folding ephemeris stored in the archive's PSRPARAM HDU
    FOLD.write_text("\\n".join(r[0] for r in fits.getdata(arfile, "PSRPARAM")) + "\\n")'''

NOTE = ("\n\n> **JupyterHub copy:** reads the release straight from the S3 mount "
        "`~/s3/schmidt-observatory-system/dsa/v1-convening/` (read-only; 6 visit-0 CHR archives and 10 DPR-DSA-07 cubes, "
        "no `MANIFEST.csv`, `fold.par`, `volume.json` or DSA-03/11/12 files). ")
KS = {"display_name": "Python 3", "language": "python", "name": "python3"}

# ---------------- dsa3_load_plot: use the DPR-DSA-07 cubes that are present
nb = nbf.read(SRC / "dsa3_load_plot.ipynb", as_version=4)
nb.cells[0].source += NOTE + "It loads a DSA-07 cube and averages it over frequency to get a 2D image."
sub(nb, 1, 'PRODUCT = "DPR-DSA-03"', 'PRODUCT = "DPR-DSA-07"')
sub(nb, 1, "from convening2026 import data_dir, find_product\n", "from pathlib import Path\nfrom convening2026 import find_product\n")
sub(nb, 1, "data_dir()\n", PATHS.replace('WORK = Path("~/convening2026_work").expanduser(); WORK.mkdir(exist_ok=True)   # the mount is read-only: outputs go here\n', "") + "DS\n")
sub(nb, 2, 'pattern=f"**/*{PRODUCT}*.fits")', 'pattern=f"**/*{PRODUCT}*.fits", data=DS)')
sub(nb, 3, "    image = np.asarray(primary.data, dtype=float)\n",
    "    image = np.asarray(primary.data, dtype=float)\n"
    "if image.ndim == 3:   # DPR-DSA-07 is a (freq, dec, ra) cube: average over frequency for a 2D image\n"
    "    print(f\"cube shape: {image.shape}; averaging over {image.shape[0]} channels\")\n"
    "    image = np.nanmean(image, axis=0)\n")
nb.metadata["kernelspec"] = KS
nbf.write(nb, DST / "dsa3_load_plot.ipynb")

# ---------------- dsa13_inspect_archives
nb = nbf.read(SRC / "dsa13_inspect_archives.ipynb", as_version=4)
nb.cells[0].source += NOTE + ("The inventory is built from the files, the folding ephemeris is read out of the archive, "
                              "the beam term (needs `theta_deg`) is dropped, and outputs go to `~/convening2026_work/`.")
sub(nb, 2, "from convening2026 import data_dir\n", "")
sub(nb, 2, "DATASET = str(data_dir())\nDS = Path(DATASET)\nman = H.inventory(DS)\n", INVENTORY + "\n")
sub(nb, 4, 'readme = (DS / "README.md").read_text()\nprint(readme.split("## 2.")[0][:3000])        # section 1 of the data description\n',
           'if (DS / "README.md").exists():   # not on the bucket; see data/README.md in the release tarball\n'
           '    print((DS / "README.md").read_text().split("## 2.")[0][:3000])\n')
sub(nb, 24, 'H.read_par(H.fold_ephemeris(DS, "P3"))', 'H.read_par(FOLD)')
sub(nb, 4, 'cols = ["product_type", "obs_id", "pulsar", "visit", "ptg", "discovery", "start_mjd", "B_k", "nbin"]',
           'cols = ["product_type", "obs_id", "pulsar", "visit", "ptg", "discovery", "start_mjd", "nbin"]')
sub(nb, 8, "hdr = fits.getheader(arfile, 0)", "hdr = fits.getheader(p3.orig, 0)   # original file: the rewritten copy drops the HIERARCH keywords")
sub(nb, 10, 'FOLD = H.fold_ephemeris(DS, "P3")', FOLDPAR)
sub(nb, 18, "th = p3.theta_deg", "th = 0.0   # theta_deg lives in MANIFEST.csv (absent): assume pulsar at the pointing centre")
sub(nb, 18, 'print(f"pulsar offset from pointing centre: {th:.2f} deg; beam response at 953 MHz B_k = {p3.B_k:.3f}")\n', "")
c = nb.cells[27]; assert c.source.startswith("import json\n")
c.source = ("import json\nif not (DS / \"volume.json\").exists():\n    print(\"volume.json not on the bucket; skipping\")\nelse:\n"
            + "".join("    " + ln + "\n" for ln in c.source.splitlines()[1:]))
nb.metadata["kernelspec"] = KS
nbf.write(nb, DST / "dsa13_inspect_archives.ipynb")

# ---------------- dsa13_timing
nb = nbf.read(SRC / "dsa13_timing.ipynb", as_version=4)
nb.cells[0].source += NOTE + ("The inventory is built from the files, the folding ephemeris is read out of an archive, "
                              "the phase-connection steps are limited to the visits present (visit 0 only), and "
                              "outputs go to `~/convening2026_work/`.")
sub(nb, 2, "from convening2026 import data_dir\n", "")
sub(nb, 2, "DATASET = str(data_dir())\n", "")
sub(nb, 2, "DS = Path(DATASET)\nman = H.inventory(DS)\n", INVENTORY + "\narfile = man.path.iloc[0]\n" + FOLDPAR + "\n")
sub(nb, 2, 'OUT = DS / "templates"\nif not os.access(OUT, os.W_OK):\n    OUT = Path.cwd() / "output_02"\n'
           '    print(f"{DS / \'templates\'} is not writable; writing to {OUT} instead")\n', 'OUT = WORK / "templates"\n')
sub(nb, 4, "H.fold_ephemeris(DS, PSR)", "FOLD")
sub(nb, 15, "H.fold_ephemeris(DS, PSR)", "FOLD")
sub(nb, 18, "for vis, free in steps:", "have = set(mine.visit)\nsteps = [(v, f) for v, f in steps if set(v) <= have]   # only visits on the bucket\nfor vis, free in steps:")
nb.metadata["kernelspec"] = KS
nbf.write(nb, DST / "dsa13_timing.ipynb")
print("wrote 3 notebooks")
