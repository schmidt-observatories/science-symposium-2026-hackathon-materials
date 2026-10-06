# Notebooks

General-purpose notebooks for the symposium hackathon — data access and tooling patterns that
are not tied to one instrument. For the Lazuli instrument simulators, see [`lazuli/`](../lazuli/).

These are written for the symposium JupyterHub, where the `schmidt-observatory-system` bucket is
already readable (both through the S3 API and as an NFS mount at `~/s3`). The bucket is private,
so running them elsewhere needs AWS credentials.

Requirements: `astropy`, `s3fs`, `matplotlib`, `numpy` — all present in the hub image.

## Notebooks

| notebook | content |
|---|---|
| [01 — Opening a FITS image from S3](01_opening_fits_from_s3.ipynb) | reading a 2.2 GB DSA-2000 image without downloading it: the S3 API versus the NFS mount, header-only inspection, degenerate axes and 4-axis WCS, lazy cutouts with `hdu.section`, display with sky coordinates |
