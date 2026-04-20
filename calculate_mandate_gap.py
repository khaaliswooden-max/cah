#!/usr/bin/env python3
"""
Mandate gap analysis against the CAH 2-part mandate.

The dual mandate requires every Critical Access Hospital to clear BOTH:
    FI (Financial Index) >= 0.50        — operating margin floor
    QI (Clinical Quality Index) >= 0.50 — MBQIP quality floor

This script reads the per-facility scores produced by
`calculate_cahsp_baseline.py` (reports/cahsp_national_baseline.csv) and
classifies every CAH into one of four cohorts based purely on which gate(s)
it misses. No intervention sizing — just gap + cohort + quick-wins.

Outputs (under `reports/`):

  - mandate_gap_analysis.csv       per-facility gap and cohort
  - mandate_cohort_summary.json    cohort counts + state breakdown + quick-wins
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(REPO_ROOT / "src"))

from cahsp_score import FI_FLOOR, QI_FLOOR  # noqa: E402

BASELINE_CSV = REPO_ROOT / "reports" / "cahsp_national_baseline.csv"
GAP_CSV = REPO_ROOT / "reports" / "mandate_gap_analysis.csv"
COHORT_JSON = REPO_ROOT / "reports" / "mandate_cohort_summary.json"

# A facility within this distance of BOTH floors is a "quick win" — the
# 60-day push cohort. Chosen to align with the 0.05 headroom we use to flag
# near-threshold scores elsewhere.
QUICK_WIN_HEADROOM = 0.05

COHORTS = {
    "dual_solved":      "FI >= 0.50 AND QI >= 0.50 — mandate cleared, maintain",
    "qi_only_blocker":  "FI >= 0.50 but QI < 0.50 — quality push to unlock mandate",
    "fi_only_blocker":  "QI >= 0.50 but FI < 0.50 — margin push to unlock mandate",
    "both_blockers":    "FI < 0.50 AND QI < 0.50 — dual push required",
}


@dataclass
class MandateRow:
    ccn: str
    name: str
    state: str
    ownership: str
    fi: float
    qi: float
    cahsp: float
    band: str
    fi_gap: float   # max(0, FI_FLOOR - fi) — how far below the floor
    qi_gap: float   # max(0, QI_FLOOR - qi)
    max_gap: float  # the binding gap (larger of the two)
    cohort: str
    is_quick_win: bool


def classify(fi: float, qi: float) -> str:
    fi_ok = fi >= FI_FLOOR
    qi_ok = qi >= QI_FLOOR
    if fi_ok and qi_ok:
        return "dual_solved"
    if fi_ok and not qi_ok:
        return "qi_only_blocker"
    if not fi_ok and qi_ok:
        return "fi_only_blocker"
    return "both_blockers"


def analyse_row(row: dict) -> MandateRow:
    fi = float(row["fi"])
    qi = float(row["qi"])
    fi_gap = max(0.0, FI_FLOOR - fi)
    qi_gap = max(0.0, QI_FLOOR - qi)
    cohort = classify(fi, qi)
    quick_win = (
        cohort != "dual_solved"
        and fi_gap <= QUICK_WIN_HEADROOM
        and qi_gap <= QUICK_WIN_HEADROOM
    )
    return MandateRow(
        ccn=row["ccn"],
        name=row["facility_name"],
        state=row["state"],
        ownership=row["ownership"],
        fi=fi,
        qi=qi,
        cahsp=float(row["cahsp"]),
        band=row["band"],
        fi_gap=round(fi_gap, 4),
        qi_gap=round(qi_gap, 4),
        max_gap=round(max(fi_gap, qi_gap), 4),
        cohort=cohort,
        is_quick_win=quick_win,
    )


def write_gap_csv(rows: list[MandateRow], out: Path) -> None:
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "ccn", "facility_name", "state", "ownership",
            "fi", "qi", "fi_gap", "qi_gap", "max_gap",
            "cahsp", "band", "cohort", "is_quick_win",
        ])
        for r in rows:
            w.writerow([
                r.ccn, r.name, r.state, r.ownership,
                round(r.fi, 4), round(r.qi, 4),
                r.fi_gap, r.qi_gap, r.max_gap,
                round(r.cahsp, 2), r.band,
                r.cohort, r.is_quick_win,
            ])


def summarise(rows: list[MandateRow]) -> dict:
    cohort_counts: dict[str, int] = {k: 0 for k in COHORTS}
    by_state_cohort: dict[str, dict[str, int]] = {}
    for r in rows:
        cohort_counts[r.cohort] = cohort_counts.get(r.cohort, 0) + 1
        by_state = by_state_cohort.setdefault(r.state, {k: 0 for k in COHORTS})
        by_state[r.cohort] += 1

    quick_wins = sorted(
        (r for r in rows if r.is_quick_win),
        key=lambda r: (r.max_gap, -r.cahsp),
    )

    near_mandate = sorted(
        (r for r in rows if r.cohort != "dual_solved"),
        key=lambda r: (r.max_gap, -r.cahsp),
    )[:50]

    return {
        "generated": datetime.now().isoformat(),
        "mandate": {
            "fi_floor": FI_FLOOR,
            "qi_floor": QI_FLOOR,
            "quick_win_headroom": QUICK_WIN_HEADROOM,
            "description": (
                "CAH 2-part mandate: a facility is 'solved' only when both "
                f"FI >= {FI_FLOOR} (margin) AND QI >= {QI_FLOOR} (quality)."
            ),
        },
        "total_facilities": len(rows),
        "cohorts": {
            k: {
                "count": cohort_counts[k],
                "description": COHORTS[k],
            }
            for k in COHORTS
        },
        "quick_wins": {
            "headroom": QUICK_WIN_HEADROOM,
            "count": len(quick_wins),
            "facilities": [
                {
                    "ccn": r.ccn,
                    "name": r.name,
                    "state": r.state,
                    "fi": round(r.fi, 4),
                    "qi": round(r.qi, 4),
                    "fi_gap": r.fi_gap,
                    "qi_gap": r.qi_gap,
                    "cohort": r.cohort,
                }
                for r in quick_wins
            ],
        },
        "top_50_nearest_to_mandate": [
            {
                "ccn": r.ccn,
                "name": r.name,
                "state": r.state,
                "cohort": r.cohort,
                "max_gap": r.max_gap,
                "cahsp": round(r.cahsp, 2),
            }
            for r in near_mandate
        ],
        "by_state": by_state_cohort,
    }


def main() -> int:
    if not BASELINE_CSV.exists():
        print(f"Missing {BASELINE_CSV}. Run calculate_cahsp_baseline.py first.",
              file=sys.stderr)
        return 1

    with open(BASELINE_CSV, newline="", encoding="utf-8") as f:
        rows = [analyse_row(r) for r in csv.DictReader(f)]

    rows.sort(key=lambda r: (r.cohort != "dual_solved", r.max_gap, -r.cahsp))

    write_gap_csv(rows, GAP_CSV)
    print(f"Wrote {GAP_CSV.relative_to(REPO_ROOT)} ({len(rows)} rows)")

    summary = summarise(rows)
    COHORT_JSON.write_text(json.dumps(summary, indent=2, default=str))
    print(f"Wrote {COHORT_JSON.relative_to(REPO_ROOT)}")

    print("\nCohort breakdown:")
    for key, meta in summary["cohorts"].items():
        n = meta["count"]
        pct = (n / len(rows) * 100.0) if rows else 0.0
        print(f"  {key:>18}: {n:>4}  ({pct:5.1f}%)")

    qw = summary["quick_wins"]["count"]
    print(f"\nQuick wins within {QUICK_WIN_HEADROOM:.02f} of both floors: {qw}")
    if qw:
        print("  (first 5 by smallest gap)")
        for f in summary["quick_wins"]["facilities"][:5]:
            print(
                f"  - {f['ccn']} {f['name']} [{f['state']}]  "
                f"FI={f['fi']:.2f} (gap {f['fi_gap']:.2f}) "
                f"QI={f['qi']:.2f} (gap {f['qi_gap']:.2f}) "
                f"-> {f['cohort']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
