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
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Reports default to the committed 08-05 baseline (data/raw). Set KOPDES_RAW
# to a snapshot dir to re-run a report against a newer pull, e.g.
#   KOPDES_RAW=data/snapshots/2026-08-13 python reports/05-road-access/run.py
# Resolved, because KOPDES_RAW is normally given relative to the repo root and
# the provenance stamp below has to name it relative to ROOT.
RAW = (
    Path(os.environ["KOPDES_RAW"]).resolve()
    if os.environ.get("KOPDES_RAW")
    else ROOT / "data" / "raw"
)


# One conversion rate for the whole project. The published pages quote USD
# alongside every rupiah headline (Rp 202,6 miliar as "about USD 12 juta"), and
# those were rendered at ~16.800 while report 11's stdout divided by 16.000, so
# the same total came out as USD 12,1M in one place and USD 12,7M in another.
# The rate is a rounded convenience, not a measurement, which is exactly why it
# needs to be stated once and imported rather than typed at each call site.
IDR_PER_USD = 16_800


def _rel(p: Path) -> str:
    """Path relative to the repo root, or absolute if it lives outside it."""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def raw_id() -> dict:
    """Identify the input pull, for stamping into every report's outputs.

    Reports read whichever directory `RAW` points at, and several of the
    committed CSVs were produced from `data/snapshots/2026-08-13` rather than
    from the default `data/raw` (the 08-05 export). Nothing in the report
    directory said so, so a re-run silently replaced 08-13 findings with 08-05
    ones and every published percentage moved: 3,3% of villages reporting
    becomes 3,0%, Rp 202,6 miliar becomes Rp 179,6 miliar.

    The snapshot CSVs themselves stay out of git at 28 MB a pull (see
    `.gitignore`), so the fix is not to commit them. It is to record which pull
    a table came from, using the SHA-256 hashes the snapshot manifest already
    carries. `_manifest.json` is committed even though its CSVs are not,
    precisely so this identification is possible after the fact.
    """
    manifest = RAW / "_manifest.json"
    if manifest.exists():
        m = json.loads(manifest.read_text(encoding="utf-8"))
        return {
            "snapshot": m.get("snapshot_date", RAW.name),
            "path": _rel(RAW),
            "manifest": _rel(manifest),
            "sha256": {k: v.get("sha256") for k, v in (m.get("files") or {}).items()},
        }
    # data/raw ships without a manifest; it is the 08-05 export by definition.
    return {
        "snapshot": "2026-08-05",
        "path": _rel(RAW),
        "manifest": None,
        "sha256": {},
    }


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
    # Stamp the input pull next to the outputs. This lives in write_csv rather
    # than in each run.py so no report can forget it, and so adding a report
    # later cannot reintroduce the untraceable-vintage problem.
    stamp_provenance(path.parent)


def stamp_provenance(out: Path) -> None:
    """Write `_source.json` naming the snapshot these CSVs were built from."""
    (out / "_source.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
                "input": raw_id(),
                "note": (
                    "Which SIMKOPDES pull produced the CSVs in this directory. "
                    "Reports default to data/raw (2026-08-05); set KOPDES_RAW to "
                    "a snapshot directory to reproduce a later vintage. The "
                    "snapshot CSVs are not committed, so the sha256 hashes above "
                    "are the provenance record."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
