"""Copy notebooks/ -> notebooks_fixed/ with the minimal cell edits needed to run on the local data/."""
import nbformat as nbf
from pathlib import Path

SRC, DST = Path("notebooks"), Path("notebooks_fixed")

def sub(nb, idx, old, new):
    c = nb.cells[idx]
    assert old in c.source, (idx, old)
    c.source = c.source.replace(old, new)

INVENTORY = '''from astropy.io import fits
# MANIFEST.csv is not in this download: build the inventory from the archives in data/.
# theta_deg / B_k / discovery (simulation metadata) are not recoverable from the files.
# This PSRCHIVE build (2025.04.24, conda-forge osx-64 under Rosetta) crashes intermittently when loading the
# chrpreview-written archives; copies rewritten once by pam (lossless up to 16-bit requantisation) load reliably.
# `path` points at the rewritten copy (for PSRCHIVE), `orig` at the original (keeps the DSA header keywords).
RW = DS / "rewritten"; RW.mkdir(exist_ok=True)
rows = []
for p in sorted(DS.glob("*.psrfits")):
    if not (RW / p.name).exists():
        H.sh(f"pam -e psrfits -u {RW} {p}")
    h = fits.getheader(p, 0); v, ptg = H.visit_ptg(p.name)
    rows.append(dict(file=p.name, path=str(RW / p.name), orig=str(p), pulsar=h["SRC_NAME"], visit=v, ptg=ptg, discovery=False,
                     product_type="DPR-DSA-13", obs_id=h["observationID"],
                     start_mjd=h["STT_IMJD"] + h["STT_SMJD"] / 86400.0, nbin=fits.getheader(p, "SUBINT")["NBIN"]))
man = pd.DataFrame(rows)'''

FOLDPAR = '''FOLD = DS / "fold.par"
if not FOLD.exists():   # not in this download: recover the folding ephemeris stored in the archive's PSRPARAM HDU
    FOLD.write_text("\\n".join(r[0] for r in fits.getdata(arfile, "PSRPARAM")) + "\\n")'''

# ---------------- dsa3_load_plot: use the DPR-DSA-07 cubes that are present
nb = nbf.read(SRC / "dsa3_load_plot.ipynb", as_version=4)
nb.cells[0].source += ("\n\n> **Local copy:** `data/` holds DPR-DSA-07 spectral cubes instead of a DPR-DSA-03 mosaic, "
                       "so this copy loads a DSA-07 cube and averages it over frequency to get a 2D image.")
sub(nb, 1, 'PRODUCT = "DPR-DSA-03"', 'PRODUCT = "DPR-DSA-07"')
sub(nb, 3, "    image = np.asarray(primary.data, dtype=float)\n",
    "    image = np.asarray(primary.data, dtype=float)\n"
    "if image.ndim == 3:   # DPR-DSA-07 is a (freq, dec, ra) cube: average over frequency for a 2D image\n"
    "    print(f\"cube shape: {image.shape}; averaging over {image.shape[0]} channels\")\n"
    "    image = np.nanmean(image, axis=0)\n")
nbf.write(nb, DST / "dsa3_load_plot.ipynb")

# ---------------- dsa13_inspect_archives
nb = nbf.read(SRC / "dsa13_inspect_archives.ipynb", as_version=4)
nb.metadata["kernelspec"] = {"display_name": "Python 3 (convening2026)", "language": "python", "name": "convening2026"}
nb.cells[0].source += ("\n\n> **Local copy:** `data/` has the 6 visit-0 archives only, no `MANIFEST.csv`, `fold.par` or "
                       "`volume.json`. The inventory is built from the files, the folding ephemeris is read out of "
                       "the archive, and the beam term (needs `theta_deg` from the manifest) is dropped.")
sub(nb, 2, "man = H.inventory(DS)", INVENTORY)
sub(nb, 4, 'cols = ["product_type", "obs_id", "pulsar", "visit", "ptg", "discovery", "start_mjd", "B_k", "nbin"]',
           'cols = ["product_type", "obs_id", "pulsar", "visit", "ptg", "discovery", "start_mjd", "nbin"]')
sub(nb, 8, "hdr = fits.getheader(arfile, 0)", "hdr = fits.getheader(p3.orig, 0)   # original file: the rewritten copy drops the HIERARCH keywords")
sub(nb, 10, 'FOLD = H.fold_ephemeris(DS, "P3")', FOLDPAR)
sub(nb, 18, "th = p3.theta_deg", "th = 0.0   # theta_deg lives in MANIFEST.csv (absent): assume pulsar at the pointing centre")
sub(nb, 18, 'print(f"pulsar offset from pointing centre: {th:.2f} deg; beam response at 953 MHz B_k = {p3.B_k:.3f}")\n', "")
c = nb.cells[27]; assert c.source.startswith("import json\n")
c.source = ("import json\nif not (DS / \"volume.json\").exists():\n    print(\"volume.json not in this download; skipping\")\nelse:\n"
            + "".join("    " + ln + "\n" for ln in c.source.splitlines()[1:]))
nbf.write(nb, DST / "dsa13_inspect_archives.ipynb")

# ---------------- dsa13_timing
nb = nbf.read(SRC / "dsa13_timing.ipynb", as_version=4)
nb.metadata["kernelspec"] = {"display_name": "Python 3 (convening2026)", "language": "python", "name": "convening2026"}
nb.cells[0].source += ("\n\n> **Local copy:** only the 6 visit-0 archives are in `data/`, with no `MANIFEST.csv` or "
                       "`fold.par`. The inventory is built from the files, the folding ephemeris is read out of an "
                       "archive, and the phase-connection steps are limited to the visits present (visit 0 only).")
sub(nb, 2, "man = H.inventory(DS)", INVENTORY + "\narfile = man.path.iloc[0]\n" + FOLDPAR)
sub(nb, 18, "for vis, free in steps:", "have = set(mine.visit)\nsteps = [(v, f) for v, f in steps if set(v) <= have]   # only visits present in data/\nfor vis, free in steps:")
nbf.write(nb, DST / "dsa13_timing.ipynb")
print("wrote 3 notebooks")
