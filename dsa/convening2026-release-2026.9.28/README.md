# DSA-2000 — 2026 Science Convening Release

Notebooks and sample data for the **2026 Science Convening of The Schmidt
Observatory System** (DSA-2000 contribution).

This branch (`main`) is for **notebook users**: install the environment, download
the sample into `data/`, and run the notebooks.

## Install

**Recommended (conda)** — needed for the CHR pulsar notebooks (PSRCHIVE):

```bash
mamba env create -f environment.yml
mamba activate convening2026
```

**pip only** (no PSRCHIVE — skip notebooks 02/03 or install PSRCHIVE another way):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Download the sample data

Put all convening products in the single directory **`data/`** (not in git):

```bash
# Once the convening bucket/prefix is assigned:
aws s3 sync s3://BUCKET/PREFIX/dsa-2000/ data/
```

Details and expected files: [data/README.md](data/README.md).

## Run the notebooks

```bash
cd notebooks
jupyter lab
```

| Notebook | What it does |
|----------|----------------|
| [dsa3_load_plot.ipynb](notebooks/dsa3_load_plot.ipynb) | Load and plot a **DPR-DSA-03** continuum mosaic |
| [dsa13_inspect_archives.ipynb](notebooks/dsa13_inspect_archives.ipynb) | Inspect **DPR-DSA-13** CHR folded pulsar archives |
| [dsa13_timing.ipynb](notebooks/dsa13_timing.ipynb) | Timing workflow on DPR-DSA-13 (PSRCHIVE + PINT) |
| [dsa11_dsa12_frb.ipynb](notebooks/dsa11_dsa12_frb.ipynb) | Explore **DPR-DSA-11** / **DPR-DSA-12** FRB mocks |

Shared helpers:

```python
from convening2026 import data_dir, find_product

data_dir()                  # .../data
find_product("DPR-DSA-03")  # file under data/
```

More notebook notes: [notebooks/README.md](notebooks/README.md).

## What is in the sample?

See [DATA.md](DATA.md) (science description) and [data/README.md](data/README.md)
(layout, volumes, sharing). The sample is intended for **all registered convening
participants**.

## Layout

```text
.
├── data/                   # ★ download sample here
├── notebooks/              # walkthroughs
├── src/convening2026/      # helpers imported by the notebooks
├── environment.yml
├── requirements.txt
└── pyproject.toml
```

---

## Development

Material below is for maintainers, not for Hub notebook users.

### Optional: validate products

`data-validator` (from
[dsa-2000-monorepo](https://gitlab.com/dsa-2000/dsa-2000-repos/dsa-2000-monorepo)
`packages/dat/data-validator`) is **not** required to run notebooks. Install it
only when checking staged products before S3 upload:

```bash
pip install -e ".[validate]"
# or: pip install -e ../dsa-2000-monorepo/packages/dat/data-validator
```

See [data/README.md](data/README.md) for product-specific validation notes.

### Data generation

Code that **generates** the sample (e.g. CHR `chrpreview` simulations) lives on
the **`data-generation`** branch, not on `main`:

```bash
git fetch origin
git checkout data-generation
```

Regenerate or extend products there, then publish the outputs for users to
download into `data/` on `main`.

### Convening checklist (organizers)

| Request | Where |
|---------|--------|
| Data description | [DATA.md](DATA.md), [data/README.md](data/README.md) |
| Data volume | [data/README.md](data/README.md) |
| ETC notebook | TBD |
| Workflow notebooks | [notebooks/](notebooks/) |
| Shareable with registered participants? | **Yes** — [DATA.md](DATA.md) |
