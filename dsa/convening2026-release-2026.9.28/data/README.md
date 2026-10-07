# Sample data (download here — not in git)

**Download the convening sample into this directory** (`data/` at the repo root).
All notebooks look here for products — there is no separate per-product data root.

```bash
# Once the convening bucket/prefix is assigned:
aws s3 sync s3://BUCKET/PREFIX/dsa-2000/ data/
```

Or unpack a release tarball into `data/`.

## Layout after download

Files may sit directly under `data/` or in subfolders that came with the download;
notebooks search under this tree by product name (and via `MANIFEST.csv` for CHR).

```text
data/
├── README.md
├── mock_DPR-DSA-03.fits          # continuum mosaic (DPR-DSA-03)
├── mock_DPR-DSA-11.h5            # FRB voltage cutout (DPR-DSA-11)
├── mock_DPR-DSA-12.h5            # FRB total-intensity beam (DPR-DSA-12)
├── MANIFEST.csv                 # CHR inventory (DPR-DSA-13)
├── archives/ ...                # CHR folded archives (paths in MANIFEST)
├── fold.par                     # or ephemerides/P3/fold.par — folding model for timing
└── answer_key/ ...              # optional — truth / self-check for the simulated sample
```

**Required for notebooks:** product files under `data/` (and for CHR: `MANIFEST.csv` +
archives it lists, plus a folding ephemeris for `dsa13_timing`).

**Optional:** `answer_key/` is only for comparing results to the simulation truth
(generation / self-check). Skip those notebook cells if it is absent.

```python
from convening2026 import data_dir, find_product
find_product("DPR-DSA-03")
```

### Products

| Product | Typical filename / layout | Notebook |
|---------|---------------------------|----------|
| DPR-DSA-03 continuum mosaic | `*DPR-DSA-03*.fits` | `dsa3_load_plot.ipynb` |
| DPR-DSA-11 FRB voltage cutout | `*DPR-DSA-11*.h5` | `dsa11_dsa12_frb.ipynb` |
| DPR-DSA-12 FRB total-intensity | `*DPR-DSA-12*.h5` | `dsa11_dsa12_frb.ipynb` |
| DPR-DSA-13 CHR archives | `MANIFEST.csv` + archives under `data/` | `dsa13_inspect_archives.ipynb`, `dsa13_timing.ipynb` |

## Sharing confirmation

**Status: YES — intended for all registered Science Convening participants.**

## Approximate volume

| Product | Format | Approx. size |
|---------|--------|--------------|
| Continuum mosaic (DPR-DSA-03) | FITS | TBD (mock ~0.3 MB) |
| FRB voltage cutout (DPR-DSA-11) | HDF5 | 3.8 MB |
| FRB total-intensity beam (DPR-DSA-12) | HDF5 | 0.3 MB |
| CHR folded archives (DPR-DSA-13) | PSRFITS | 733 MB |
| **Total sample** | | **well under 100s of GB** |

## Maintainers

Regenerating or extending the sample (e.g. CHR `chrpreview`) is done on the
**`data-generation`** branch — see the Development section of the root README.
Validating with `data-validator` is optional (`pip install -e ".[validate]"`).
