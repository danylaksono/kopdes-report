#!/usr/bin/env python3
"""Harvest coordinate-correction reports into the corrections registry.

The /periksa/ page hands a reader a prefilled GitHub issue whose body is
machine-parseable:

    **ID SIMKOPDES**: 1301
    **Koordinat SIMKOPDES**: -6.956898, 112.500000
    **Koordinat yang saya laporkan**: -6.956900, 112.500100

This script pulls issues with the correction label (or one issue by number),
parses the id and the reported coordinate, validates the point, and appends
`pending` rows to data/corrections/user_coordinates.csv. It never marks
anything `applied`; reviewing the issues and flipping the status is the human
step. Only `status = applied` rows override the SIMKOPDES coordinate when the
mart is rebuilt (scripts/build_analysis_mart.py).

Usage:
  python scripts/import_coordinate_corrections.py                  # all labelled issues
  python scripts/import_coordinate_corrections.py --issue 123      # one issue by number
  python scripts/import_coordinate_corrections.py --dry-run        # parse + validate only

Requires `gh` (GitHub CLI) authenticated against the repo. Idempotent: rows
whose source_issue already exists are skipped, so re-running is safe.
"""

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "corrections" / "user_coordinates.csv"
# The repo the /periksa/ page links to (app/periksa/ui.js REPO_ISSUES).
REPO = "danylaksono/kopdes-vis"
DEFAULT_LABEL = "koreksi koordinat"
# Matches the story map's Indonesia bounds (app/story-map.js INDONESIA_BOUNDS).
INDONESIA = {"min_lat": -11.8, "max_lat": 7.2, "min_lon": 94.0, "max_lon": 141.8}
DEFAULT_CAP_KM = 100.0

COLUMNS = [
    "cooperative_id", "user_latitude", "user_longitude", "source_issue",
    "submitted_at", "basis", "status", "note",
]


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points, in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_official_coords():
    """cooperative_id -> (lat, lon) from the SIMKOPDES baseline the mart uses."""
    raw = Path(os.environ["KOPDES_RAW"]) if os.environ.get("KOPDES_RAW") else ROOT / "data" / "raw"
    path = raw / "kopdes_locations.csv"
    if not path.exists():
        sys.exit(f"FATAL: no {path.relative_to(ROOT)} to validate against")
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                out[int(row["id"])] = (float(row["latitude"]), float(row["longitude"]))
            except (KeyError, ValueError):
                continue
    return out


def parse_body(body):
    """Pull (cooperative_id, user_lat, user_lon) out of the prefilled issue body."""
    mid = re.search(r"\*\*ID SIMKOPDES\*\*\s*:\s*(\d+)", body or "")
    mpt = re.search(
        r"\*\*Koordinat yang saya laporkan\*\*\s*:\s*"
        r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)",
        body or "",
    )
    if not mid or not mpt:
        return None
    return int(mid.group(1)), float(mpt.group(1)), float(mpt.group(2))


def gh_json(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit("gh (GitHub CLI) not found on PATH; install it, or copy the issue "
                 "body into the registry by hand")
    except subprocess.CalledProcessError as e:
        sys.exit(f"gh failed: {e.stderr.strip() or e}")
    return json.loads(out.stdout)


def fetch_issue(repo, number):
    return gh_json(["gh", "issue", "view", str(number), "--repo", repo,
                    "--json", "number,title,body,createdAt,url"])


def fetch_issues(repo, label):
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "200",
           "--json", "number,title,body,createdAt,url"]
    if label:
        cmd += ["--label", label]
    return gh_json(cmd)


def load_registry():
    if not REGISTRY.exists():
        return []
    with open(REGISTRY, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--label", default=DEFAULT_LABEL,
                    help=f"issue label to pull (default: {DEFAULT_LABEL})")
    ap.add_argument("--issue", type=int, help="only this issue number")
    ap.add_argument("--cap-km", type=float, default=DEFAULT_CAP_KM,
                    help="reject reports further than this from the official point")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and validate, write nothing")
    args = ap.parse_args()

    issues = fetch_issue(args.repo, args.issue) if args.issue else fetch_issues(args.repo, args.label)
    if not issues:
        print("no issues to import")
        return

    official = load_official_coords()
    existing = {r["source_issue"] for r in load_registry()}
    rows, rejected = [], []

    for i in issues:
        parsed = parse_body(i.get("body", ""))
        if not parsed:
            rejected.append((i["number"], "unparseable body (missing ID SIMKOPDES or koordinat yang saya laporkan)"))
            continue
        coop_id, lat, lon = parsed
        if coop_id not in official:
            rejected.append((i["number"], f"unknown cooperative_id {coop_id}"))
            continue
        olat, olon = official[coop_id]
        if not (INDONESIA["min_lat"] <= lat <= INDONESIA["max_lat"]
                and INDONESIA["min_lon"] <= lon <= INDONESIA["max_lon"]):
            rejected.append((i["number"], f"reported point outside Indonesia ({lat:.6f}, {lon:.6f})"))
            continue
        d = haversine_km(olat, olon, lat, lon)
        if d > args.cap_km:
            rejected.append((i["number"], f"{d:.1f} km from the official point (cap {args.cap_km:.0f} km)"))
            continue
        url = i["url"]
        if url in existing:
            continue
        rows.append({
            "cooperative_id": coop_id,
            "user_latitude": f"{lat:.6f}",
            "user_longitude": f"{lon:.6f}",
            "source_issue": url,
            "submitted_at": (i.get("createdAt") or date.today().isoformat())[:10],
            "basis": "",
            "status": "pending",
            "note": "",
        })
        existing.add(url)

    for num, why in rejected:
        print(f"  #{num}  SKIP  {why}")
    print(f"{len(rows)} new pending row(s), {len(rejected)} rejected, "
          f"{len(issues) - len(rows) - len(rejected)} already imported")

    if args.dry_run or not rows:
        return

    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    newfile = not REGISTRY.exists()
    with open(REGISTRY, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if newfile:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"appended to {REGISTRY.relative_to(ROOT)} (review, then flip status to 'applied')")


if __name__ == "__main__":
    main()
