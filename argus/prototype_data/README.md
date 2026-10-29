# Argus prototype data

Notebooks on a sample of the Argus Array prototype's archive: real images,
small per-star cutouts with their data-quality and calibration records, and
light curves measured from them with photutils. The data are from ADDEM, two
co-pointed cameras imaging the same field through a blue band, **β**
(365–520 nm), and a red band, **ρ** (565–825 nm), in October 2026.

For the simulated 5-year survey (depth, cadence, simulated light curves),
see [`argus_survey_model/`](../argus_survey_model/).

## Notebooks

| notebook | content |
|---|---|
| [01 — The archive and its images](01_images.ipynb) | the footprint, the frames covering a target, a whole segment, cutouts in both bands, a time sequence |
| [02 — Minipixes and their records](02_minipixes_and_records.ipynb) | per-star cutout series, data-quality flags, the photometric-calibration model, a per-epoch DQ and zeropoint table |
| [03 — Light curves](03_light_curves.ipynb) | aperture photometry with photutils, choosing the aperture, calibrated and differential light curves of an eclipsing binary, a period search |
| [04 — Flares](04_flares.ipynb) | four M-dwarf flares measured on segment cutouts, calibrated with nearby minipixes' records |


## Requirements

```
pip install argex photutils
```

plus numpy, astropy and matplotlib, which are in the hub image.
[argex](https://github.com/argus-hdps/argex) is the Python client of the
Argus archive. Here it only reads the sample's FITS files (`argex.read()`),
returning the same objects as the archive's live service.
