# DSA-2000 sample data description

> Structure stub — fill in TBD items before the convening handoff.

## What the sample contains

- **Telescope / survey:** DSA-2000 (Deep Synoptic Array), contribution to the
  2026 Schmidt Observatory System Science Convening.
- **Sky / fields:** TBD
- **Science intent:** TBD

## How it was produced

- **Pipeline / simulation:** TBD
- **Calibration / imaging assumptions:** TBD
- **Selection cuts:** TBD

## Data products and formats

| Product | Format | Description |
|---------|--------|-------------|
| Continuum images / cutouts | FITS | Primary imaging products |
| Source catalog | FITS table / TBD | Positions, fluxes, etc. |
| Manifest | TBD | Inventory of products |

Validate staged products with optional `data-validator` from `dsa-2000-monorepo`
before S3 upload (maintainers — see root README Development).

## FRB sample: DPR-DSA-11 and DPR-DSA-12 (mock)

- **What:** one simulated dispersed burst (event `240918aaaa`) as two products:
  - **DPR-DSA-11:** a channelised *voltage* cutout. It has 813 channels × 2 linear polarisations ×
    2460 samples at 8.13 µs, packed 4+4-bit complex, and is coherently dedispersed at DM 200. Each
    channel has its own start time, following the sweep. There are validity masks and RFI/band-edge
    flags.
  - **DPR-DSA-12:** a *total-intensity* dynamic spectrum from a formed beam: 813 channels × 64 samples
    at 1 ms, incoherently dedispersed.
- **Format:** HDF5, self-describing through a root `README` attribute and attribute-only metadata
  groups (`/instrument`, `/clock`, `/pointing`, `/burst`, `/processing`, `/calibration`). Both pass
  `data-validator` against their schemas.
- **Notebook:** `notebooks/dsa11_dsa12_frb.ipynb` (metadata, voltage unpacking, Stokes I at the
  best-fit DM, polarisation, dynamic spectrum).
- **Volume:** 4.1 MB.

## Pulsar timing sample: DPR-DSA-13 (CHR folded pulsar profiles)

The full description is in `data/` after you download the sample (e.g.
`data/README.md` from the CHR bundle, written when the data were generated on
the `data-generation` branch).

- **What:** synthetic folded pulsar archives standing in for CHR targeted-beam timing data. The
  pulsar is one millisecond pulsar in a 4.4-day white-dwarf binary (type "P3": P = 6.1 ms, DM 60).
  There are 42 archives, one per in-beam 1260 s pointing, over 7 visits spanning 2 years (cadence
  cell `W12d_T2yr_log`). The sky position is a survey tile at Galactic (l, b) = (40°, 0°).
- **How produced:** the observation model and ToA truth come from the `chrtiming` cadence
  simulation. `chrpreview` then emulates folding of incoherently dedispersed 0.1 ms filterbank data
  exactly, without generating the filterbank. The simulation includes:
  - dispersion smearing, sampling and scattering kernels;
  - a small DM error;
  - spectral index and beam chromaticity;
  - fold-count noise structure;
  - a single visit-0 folding ephemeris.

  The signal is calibrated to the survey model's discovery S/N of 20. It is fully simulated and
  includes an answer key (true timing model). It excludes RFI, scintillation, polarisation,
  calibration, profile evolution and DM variations.
- **Format:** PSRFITS fold mode (Stokes I, 500 channels × 128 bins × 126 × 10 s sub-integrations,
  16-bit). The files are PSRCHIVE-readable and are **DPR-DSA-13** products: `DDSCHEMA`,
  `observationID` and `PRODUCTVER` are in the header, and files are named
  `dsa13_{observationID}_{SRC_NAME}_v{PRODUCTVER}.psrfits`. All 42 pass `data-validator` against
  DPR-DSA-13.
- **Stand-ins:** the site is the GBT (`TELESCOP = GBT`) and the epochs are 2030–2032, both
  consistent with the survey simulation.
- **Volume:** 733 MB. The same product for all nine simulated pulsar types over the full cadence
  would be 14.9 GB at 16-bit, or 29.2 GB at 4 bytes (the real CHR format).
- **Notebooks:** `notebooks/dsa13_inspect_archives.ipynb` and `notebooks/dsa13_timing.ipynb`.

## Relation to the eventual community release

This convening sample is a **small, curated subset** for interactive Hub use.
Document known differences from the eventual community products here: TBD.

## Sharing

Confirmed for distribution to **all registered convening participants**.
