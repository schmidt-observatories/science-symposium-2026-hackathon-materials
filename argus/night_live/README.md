# An Argus night, live

[`argus_night_live.ipynb`](argus_night_live.ipynb) draws one night of a field observed by simulated Argus and processed
by the Argus pipeline (hdps), live in JupyterLab, with one star that you edit: its type, brightness, amplitude, period,
position and airmass. The star is drawn into the pipeline's own images and measured with its own detector and alert
detection. The notebook's first cell lists the controls and what is simplified.

## Requirements

- **Python 3.12 or newer**, and JupyterLab with ipympl (`%matplotlib widget`).
- **The demo's archive** (code and data, 308 MB). The setup cell finds it on the bucket mount at
  `~/s3/schmidt-observatory-system/argus/argus_night_live/`, checks its SHA-256 and unpacks it into
  `~/.cache/argus_night_live/` (set `ARGUS_NIGHT_LIVE_HOME` to unpack elsewhere). To use a local copy, set
  `ARGUS_NIGHT_LIVE_ARCHIVE` to its path or put it next to the notebook.
- **The Python packages the app imports**, listed in the setup cell. A missing one is installed with
  `pip install --user`, after which the kernel must be restarted.

## On a shared hub

The app measures with worker processes, 2 to 6 by default, each holding its own copy of the night. Set
`ARGUS_NIGHT_LIVE_WORKERS` low (for example 2, or 0 to measure with threads) where many people share one machine.
