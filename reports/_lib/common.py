"""
Shared helpers for reports/*/run.py.

Every report is a self-contained directory:

    reports/NN-slug/
        run.py        reproducible script - writes everything else in here
        README.md     the write-up (hand-written, cites the CSVs)
        *.csv         outputs, committed so the findings survive without a re-run

Conventions:
  - run.py is runnable from the repo root: `python reports/NN-slug/run.py`
  - it never writes outside its own directory
  - it prints a short summary to stdout and writes the full result to CSV
  - anything hitting the live SIMKOPDES API says so loudly, because results
    will differ from the committed CSVs by design (see reports/01-snapshot-drift)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Reports default to the committed 08-05 baseline (data/raw). Set KOPDES_RAW
# to a snapshot dir to re-run a report against a newer pull, e.g.
#   KOPDES_RAW=data/snapshots/2026-08-13 python reports/05-road-access/run.py
RAW = Path(os.environ["KOPDES_RAW"]) if os.environ.get("KOPDES_RAW") else ROOT / "data" / "raw"


def out_dir(report_file: str) -> Path:
    """Directory of the calling run.py - where all its outputs go."""
    return Path(report_file).resolve().parent


def load_extractor():
    """
    Import scripts/extract_kopdes.py as a module without running main().

    It's a script, not a package, and it takes its output dir from argv - so
    neutralise argv before executing it.
    """
    spec = importlib.util.spec_from_file_location(
        "extract_kopdes", ROOT / "scripts" / "extract_kopdes.py"
    )
    module = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["extract_kopdes"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = saved
    return module


def live_client():
    """
    Authenticated SIMKOPDES API client.

    The API is AES-encrypted with a key published in the site's own JS bundle;
    `discover_cipher()` re-reads it at runtime so this keeps working across
    key rotations. Requires network access.
    """
    ek = load_extractor()
    return ek.Client(*ek.discover_cipher())


def write_csv(df, path: Path, note: str = "") -> None:
    df.to_csv(path, index=False)
    print(f"  wrote {path.relative_to(ROOT)}  ({len(df):,} rows){'  - ' + note if note else ''}")
