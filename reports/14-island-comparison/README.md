# 14 — Island comparison: whose program is this anyway?

**Run**: `python reports/14-island-comparison/run.py` · No network · **Last run**: 2026-08-12
**Sources**: `kopdes_stats_village.csv` (economics, complete) +
`data/web/kopdes_points.parquet` (spatial, the committed analysis mart)

F3 of `analytics-plan.md`. The 38 provinces are mapped to seven island groups
and both halves of the evidence are compared: the **complete economic picture**
from the village file, and the **per-cooperative spatial picture** assembled in
the mart. Every cooperative is placed on exactly one island (83,323 of 83,342;
the 19 unplaced are 08's impossible coordinates, excluded from medians).

## Finding 1 — economics: the program is a Java phenomenon

[`islands_economy.csv`](islands_economy.csv)

| Island        | Coops  | % reporting tx | Rp tx per coop | % any savings |
| ------------- | ------ | -------------- | -------------- | ------------- |
| **JAVA**      | 25,248 | **7.85%**      | **4,819,782**  | 20.6%         |
| KALIMANTAN    | 7,160  | 1.82%          | 2,137,211      | 9.9%          |
| NUSA TENGGARA | 5,342  | 0.90%          | 1,575,089      | 17.5%         |
| SUMATRA       | 25,589 | 1.18%          | 1,243,838      | 9.2%          |
| SULAWESI      | 10,555 | 0.48%          | 161,012        | 10.2%         |
| MALUKU        | 2,427  | 0.08%          | 93,436         | 2.6%          |
| **PAPUA**     | 7,060  | **0.09%**      | **56,390**     | **1.1%**      |

Java has 30% of the cooperatives and **~68% of the reported transaction value**;
Papua has 8.5% of the cooperatives and **0.2%** of the value. The gap is ~85×
in per-cooperative output.

## Finding 2 — spatial: the placement story is a Papua/Maluku story

[`islands_spatial.csv`](islands_spatial.csv) · excluding 08's 19 impossible coordinates

| Island        | % zero-pop cell | median pop within 1.4 km | median km to minimarket | median m to nearest coop | % land verified |
| ------------- | --------------- | ------------------------ | ----------------------- | ------------------------ | --------------- |
| JAVA          | 2.6%            | 29,015                   | 6.7                     | 1,293                    | 62.7%           |
| NUSA TENGGARA | 16.0%           | 5,012                    | 12.8                    | 1,967                    | 42.2%           |
| SUMATRA       | 19.7%           | 6,406                    | 25.0                    | 1,782                    | 41.0%           |
| SULAWESI      | 20.7%           | 4,792                    | 27.1                    | 1,935                    | 32.9%           |
| KALIMANTAN    | 38.4%           | 1,565                    | 35.6                    | 3,605                    | 30.9%           |
| MALUKU        | 54.7%           | 1,014                    | 128.7                   | 2,652                    | 22.0%           |
| **PAPUA**     | **70.7%**       | 1,337                    | **74.6**                | 2,422                    | **3.2%**        |

Every "tail" finding in the investigation is disproportionately a
Papua/Maluku/Kalimantan phenomenon: 70.7% of Papua cooperatives sit in a
zero-population 400 m cell (national 21.4%, 03), 75 km to the nearest
minimarket, and only 3.2% have their land verified. Java is the opposite:
2.6% in zero-pop cells, 62.7% land verified.

## What this does to the three claims

- **Remoteness** — the real tail (03/04/05) is an eastern-Indonesia tail.
  Java's cooperatives are not remote; Papua's are.
- **Cannibalisation** — retail proximity (06) is a Java/urban phenomenon,
  where minimarkets exist at all.
- **Budget-vs-output** — the money is in Java, the empty registries are in
  Papua, and the construction gap (15) follows the same line.

## Caveats

- Island groups are province-name mappings (static and explicit in `run.py`).
- Economics come from the complete village file; spatial figures come from the
  committed analysis mart (per-cooperative), which is downstream of reports
  03/05/06/08/10. If a number here disagrees with one of those reports, the
  report is right.
- Per-coop medians exclude 08's 19 impossible coordinates; `cooperatives`
  counts include all points placed on an island.
