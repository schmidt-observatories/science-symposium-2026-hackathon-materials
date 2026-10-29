# Argus prototype sample

## What the sample contains

- **Telescopes:** ADDEM, two co-pointed cameras of the Argus Array prototype,
  one per band: **β** (365–520 nm) and **ρ** (565–825 nm). Every frame is a
  60 s exposure; the two cameras expose together.
- **Time span:** 2026-10-08 to 2026-10-22.
- **Sky:** one 0.5° segment in full (segment 391749, around RA 47.8°,
  Dec +43.9°, in Perseus), plus 32 × 32 pixel cutouts around four flaring M
  dwarfs.
- **Volume:** 1.6 GB, 472 files.

## Files

| path | content |
|---|---|
| `manifest.json` | every file with its size and SHA-256 |
| `segments.fits` | every segment of the archive with data: id, center, frame count, epoch range |
| `bands.json` | each band's passband, camera and telescope configuration codes |
| `seg_391749/frames.fits` | every frame of the segment: epoch, frame key, telescope configuration code |
| `seg_391749/images/` | one whole frame of the segment in each band, 2048 × 2048, tile-compressed |
| `seg_391749/stacks/target_beta.fits`, `target_rho.fits` | half an hour of cutouts around the eclipsing binary, in each band |
| `seg_391749/minipix/minipix_NNNN.fits` | every active minipix of the segment: 32 × 32 cutouts from every frame, with the DQ and photocal records (433 files) |
| `flares/<Gaia DR3 id>/` | per flare: `stack_beta.fits` and `stack_rho.fits` (cutouts around the peak), `minipix/` (the five nearest minipixes over the same time window), `flare.json` (position, segment pixel, peak time) |

All FITS products open with `argex.read()`. Each is a cube or image in the
primary HDU (the tile-compressed images in the first extension), with a
`FRAMES` table holding each plane's frame identity, time and, for minipixes,
the DQ and photocal records.

## Conventions

- **Pixels** are e⁻/s per segment pixel (0.879″), north up, on the segment's
  TAN grid; `BUNIT = 'electron/s'`, `FLUXCONS = T`.
- **Times** are TT seconds since 2025-01-01T00:00:00 TT at each exposure's
  midpoint (`TIMESYS = 'TT'`); the FRAMES tables also give MJD (TT) and ISO
  UTC.
- **Zeropoints** are AB magnitudes in each camera's band for fluxes in e⁻/s
  in a 4.05″ radius aperture, at the minipix center, with a gradient across
  the minipix and a color term in g − r (pivot g − r = 0.6).
- **DQ** records give, per 16 × 16 quadrant of a minipix cutout, the OR of the
  frame's data-quality flags and the number of flagged pixels; `argex.dq`
  names the bits.

## How it was produced

The frames were calibrated, astrometrically solved and reprojected onto the
archive's sky segments by the Argus pipeline. Minipixes are kept for every
Gaia DR3 star with G ≤ 16; their zeropoints come from fitting each frame
against Gaia XP spectra integrated through the band and a model atmosphere.
The flares were found by the prototype's live difference-imaging pipeline
and confirmed by eye.

## Known limitations

- **Approximate flux conservation.** The archive's reprojection holds
  values per detector pixel (1.012″); the sample's pixels were rescaled by a
  constant (0.879/1.012)² = 0.754 (`PIXAREA`) to make them flux-conserving.
  The true ratio varies by a few percent across each detector, so
  magnitudes carry an error of that size that varies with position.
- **No zeropoint uncertainties.** The photocal records carry none.
- **Prototype calibration.** The atmosphere model and the throughput curves
  behind the zeropoints are preliminary.
