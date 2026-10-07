"""Resolve the single sample-data directory used by all notebooks.

Users download convening products into ``data/`` at the repository root
(local / S3 — not committed). Notebooks look there for files.
"""

from __future__ import annotations

from pathlib import Path

# src/convening2026/paths.py -> parents[2] is the repository root
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def data_dir() -> Path:
    """Return the repository ``data/`` directory (download location)."""
    return DATA_DIR


def require_data_dir() -> Path:
    """Return ``data/``, raising a clear error if it is missing."""
    path = data_dir()
    if not path.is_dir():
        raise FileNotFoundError(
            f"Sample data directory not found: {path}\n"
            "Download the convening sample into data/ (see data/README.md)."
        )
    return path


def find_product(
    product: str,
    *,
    pattern: str | None = None,
    data: Path | None = None,
) -> Path:
    """Find a file under ``data/`` whose name contains ``product``.

    Parameters
    ----------
    product
        Product id substring, e.g. ``\"DPR-DSA-03\"``.
    pattern
        Optional glob relative to ``data/`` (default ``**/*{product}*``).
    data
        Override data root (defaults to :func:`data_dir`).
    """
    root = Path(data) if data is not None else require_data_dir()
    glob_pat = pattern or f"**/*{product}*"
    matches = sorted(p for p in root.glob(glob_pat) if p.is_file())
    if not matches:
        raise FileNotFoundError(
            f"No file matching {glob_pat!r} under {root}\n"
            "Download the convening sample into data/ (see data/README.md)."
        )
    if len(matches) > 1:
        print(f"Multiple matches for {product!r}; using the first:")
        for path in matches:
            print(f"  - {path.relative_to(root)}")
    return matches[0]
