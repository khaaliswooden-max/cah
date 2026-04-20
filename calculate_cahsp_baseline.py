#!/usr/bin/env python3
"""
Compute the national CAHSP baseline for every CAH in the step6 roster.

For each of the 1,376 Critical Access Hospitals in
`data/cms_rural_health/cah_hospitals.csv`, this script derives a direct-from-
data CAHSP proxy using the signals actually present on disk:

  FI (Financial, 0.30) — state-level operating-margin benchmarks (WA/MT when
      available) combined with an ownership-based adjustment; falls back to the
      national CAH median (KFF 2024: 1.5–3.0%) otherwise. Confidence is lower
      when only a fallback is available.
  QI (Quality, 0.30)   — group-measure better/worse ratio plus overall rating,
      both from the step6 roster. If neither signal is present, defaults to
      neutral 0.50.
  OI (Operational, 0.20) — overall rating used as a coarse proxy (normalized
      to [0, 1]). Placeholder until per-facility OP-density / bed data lands.
  WI (Workforce, 0.10) — neutral default (0.50) pending HRSA FTE merge.
  CI (Confidence, 0.10) — share of FI/QI/OI signals that came from real data
      rather than a fallback. This functions like AlphaFold's pLDDT: knowing
      where the score is uncertain is part of the score.

Outputs (under `reports/`):

  - cahsp_national_baseline.csv              one row per CAH
  - cahsp_band_summary.json                  cohort band histogram
  - cahsp_binding_constraint_triage.json     binding-constraint × band matrix
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Make `src/` importable without installing the package
REPO_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(REPO_ROOT / "src"))

from cah_engine.integration.data_loader import (  # noqa: E402
    CAHDataLoader,
    CAHFacility,
    IntegratedDataset,
)
from cahsp_score import (  # noqa: E402
    BENCHMARK_THRESHOLD,
    CAHSP_WEIGHTS,
    FI_FLOOR,
    QI_FLOOR,
    score_band,
)

DATA_DIR = REPO_ROOT / "data"
REPORTS_DIR = REPO_ROOT / "reports"
STATE_BENCHMARKS_FILE = DATA_DIR / "state_benchmarks" / "wa_mt_cah_benchmarks.json"

# National CAH median operating margin (KFF 2024, midpoint of 1.5–3.0%)
NATIONAL_CAH_MEDIAN_MARGIN = 0.0225


def load_state_margins() -> dict[str, float]:
    """State-level CAH operating margins (as decimal fractions) where known."""
    out: dict[str, float] = {}
    if not STATE_BENCHMARKS_FILE.exists():
        return out
    data = json.loads(STATE_BENCHMARKS_FILE.read_text())
    for state_key, state_code in (("washington", "WA"), ("montana", "MT")):
        block = data.get(state_key) or {}
        fin = block.get("financial_context") or {}
        margin_pct = fin.get("statewide_acute_care_margin_2023")
        if margin_pct is not None:
            out[state_code] = float(margin_pct) / 100.0
    return out


def ownership_margin_bias(ownership: str) -> float:
    """
    Crude operating-margin bias by ownership class (decimal, additive).

    Rationale: government-hospital-district CAHs typically run thinner margins
    than voluntary non-profit CAHs (Holmes 2022, NRHA 2024). This is only used
    when no facility-level financial data is available.
    """
    own = (ownership or "").lower()
    if "government" in own:
        return -0.010
    if "voluntary" in own or "non-profit" in own or "nonprofit" in own:
        return +0.005
    if "proprietary" in own:
        return +0.010
    return 0.0


def compute_fi_proxy(
    facility: CAHFacility, state_margins: dict[str, float]
) -> tuple[float, bool]:
    """
    Financial Index (FI) proxy in [0, 1]; second value is True when based on
    real data signals rather than pure defaults.

    Scoring is consistent with `cahsp_score.compute_fi`: normalizes operating
    margin from [−5%, +10%] onto [0, 1].
    """
    state_margin = state_margins.get(facility.state)
    have_signal = state_margin is not None
    base = state_margin if have_signal else NATIONAL_CAH_MEDIAN_MARGIN
    margin = base + ownership_margin_bias(facility.ownership)
    fi = max(0.0, min(1.0, (margin + 0.05) / 0.15))
    return fi, have_signal


def compute_qi_proxy(facility: CAHFacility) -> tuple[float, bool]:
    """
    Clinical Quality Index (QI) proxy from group-measure counts + rating.

    Sub-components (equal weights, only the available ones are averaged):
      1. better / (better + worse) across MORT/Safety/READM groups
      2. overall star rating in [1, 5] normalized to [0, 1]

    Neutral 0.50 when no data; `have_signal` flags when at least one component
    used real data.
    """
    parts: list[float] = []
    have_signal = False

    better = (
        facility.mort_measures_better
        + facility.safety_measures_better
        + facility.readm_measures_better
    )
    worse = (
        facility.mort_measures_worse
        + facility.safety_measures_worse
        + facility.readm_measures_worse
    )
    if better + worse > 0:
        parts.append(better / (better + worse))
        have_signal = True

    if facility.overall_rating is not None:
        parts.append(max(0.0, min(1.0, (facility.overall_rating - 1) / 4.0)))
        have_signal = True

    qi = sum(parts) / len(parts) if parts else 0.50
    return qi, have_signal


def compute_oi_proxy(facility: CAHFacility) -> tuple[float, bool]:
    """
    Operational Efficiency proxy; uses overall rating as a weak signal when
    facility-level bed/ED/OP throughput data is absent.
    """
    if facility.overall_rating is not None:
        oi = max(0.0, min(1.0, (facility.overall_rating - 1) / 4.0))
        return oi, True
    return 0.50, False


def binding_constraint(fi: float, qi: float, oi: float, wi: float) -> str:
    """Return the sub-index name with the lowest score (its binding diagnosis)."""
    scores = {"fi": fi, "qi": qi, "oi": oi, "wi": wi}
    return min(scores, key=scores.get)


def recommended_action(binding: str) -> str:
    """Prioritized next action gated on binding constraint (plain English)."""
    return {
        "fi": "Drive operating margin: revenue-cycle + payer-mix diagnostic, labor-ratio review",
        "qi": "MBQIP quality push: prioritize readmission and safety measures",
        "oi": "Operational efficiency: ED throughput, occupancy, outpatient density",
        "wi": "Workforce: nurse/provider ratio and coverage-model review",
    }[binding]


@dataclass
class FacilityScore:
    ccn: str
    name: str
    state: str
    ownership: str
    overall_rating: int | None
    fi: float
    qi: float
    oi: float
    wi: float
    ci: float
    cahsp: float
    band: str
    dual_mandate_met: bool
    binding: str
    action: str
    fi_has_signal: bool
    qi_has_signal: bool
    oi_has_signal: bool


def score_facility(
    facility: CAHFacility, state_margins: dict[str, float]
) -> FacilityScore:
    fi, fi_signal = compute_fi_proxy(facility, state_margins)
    qi, qi_signal = compute_qi_proxy(facility)
    oi, oi_signal = compute_oi_proxy(facility)
    wi = 0.50  # neutral until HRSA FTE is merged per-facility

    # CI = share of FI/QI/OI signals backed by real data (WI always a fallback
    # at this stage, so excluded from the confidence ratio).
    signal_bits = [fi_signal, qi_signal, oi_signal]
    ci = sum(signal_bits) / len(signal_bits)

    total = 100.0 * (
        CAHSP_WEIGHTS["fi"] * fi
        + CAHSP_WEIGHTS["qi"] * qi
        + CAHSP_WEIGHTS["oi"] * oi
        + CAHSP_WEIGHTS["wi"] * wi
        + CAHSP_WEIGHTS["ci"] * ci
    )
    band = score_band(total)
    dual_mandate = fi >= FI_FLOOR and qi >= QI_FLOOR
    binding = binding_constraint(fi, qi, oi, wi)

    return FacilityScore(
        ccn=facility.facility_id,
        name=facility.facility_name,
        state=facility.state,
        ownership=facility.ownership,
        overall_rating=facility.overall_rating,
        fi=fi,
        qi=qi,
        oi=oi,
        wi=wi,
        ci=ci,
        cahsp=total,
        band=band,
        dual_mandate_met=dual_mandate,
        binding=binding,
        action=recommended_action(binding),
        fi_has_signal=fi_signal,
        qi_has_signal=qi_signal,
        oi_has_signal=oi_signal,
    )


def write_baseline_csv(scores: list[FacilityScore], out: Path) -> None:
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "ccn", "facility_name", "state", "ownership", "overall_rating",
            "cahsp", "band", "fi", "qi", "oi", "wi", "ci",
            "dual_mandate_met", "binding_constraint", "recommended_action",
            "fi_has_signal", "qi_has_signal", "oi_has_signal",
        ])
        for s in scores:
            w.writerow([
                s.ccn, s.name, s.state, s.ownership,
                s.overall_rating if s.overall_rating is not None else "",
                round(s.cahsp, 2), s.band,
                round(s.fi, 4), round(s.qi, 4), round(s.oi, 4),
                round(s.wi, 4), round(s.ci, 4),
                s.dual_mandate_met, s.binding, s.action,
                s.fi_has_signal, s.qi_has_signal, s.oi_has_signal,
            ])


def summarize_bands(scores: list[FacilityScore]) -> dict:
    bands: dict[str, int] = {}
    for s in scores:
        bands[s.band] = bands.get(s.band, 0) + 1
    solved = sum(
        1 for s in scores if s.cahsp >= BENCHMARK_THRESHOLD and s.dual_mandate_met
    )
    by_state: dict[str, dict[str, int]] = {}
    for s in scores:
        by_state.setdefault(s.state, {}).update(
            {s.band: by_state.setdefault(s.state, {}).get(s.band, 0) + 1}
        )
    return {
        "total_facilities": len(scores),
        "benchmark_threshold": BENCHMARK_THRESHOLD,
        "fi_floor": FI_FLOOR,
        "qi_floor": QI_FLOOR,
        "bands": bands,
        "benchmark_solved_count": solved,
        "cahsp_distribution": {
            "mean": round(statistics.mean(s.cahsp for s in scores), 2),
            "median": round(statistics.median(s.cahsp for s in scores), 2),
            "min": round(min(s.cahsp for s in scores), 2),
            "max": round(max(s.cahsp for s in scores), 2),
        },
        "by_state": by_state,
        "generated": datetime.now().isoformat(),
    }


def summarize_binding(scores: list[FacilityScore]) -> dict:
    matrix: dict[str, dict[str, int]] = {}
    for s in scores:
        row = matrix.setdefault(s.binding, {})
        row[s.band] = row.get(s.band, 0) + 1
    binding_counts = {b: sum(v.values()) for b, v in matrix.items()}
    return {
        "generated": datetime.now().isoformat(),
        "binding_by_band": matrix,
        "binding_totals": binding_counts,
        "cohort_level_intervention_priorities": {
            b: recommended_action(b) for b in sorted(binding_counts)
        },
    }


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading integrated CAH dataset...")
    loader = CAHDataLoader(DATA_DIR)
    dataset: IntegratedDataset = loader.load_all()
    facilities = sorted(dataset.facilities.values(), key=lambda f: (f.state, f.facility_name))
    print(f"  Loaded {len(facilities)} CAH facilities "
          f"across {len({f.state for f in facilities})} states")

    state_margins = load_state_margins()
    if state_margins:
        print(f"  State-level margins available for: {sorted(state_margins)}")

    print("Scoring CAHSP for every facility...")
    scores = [score_facility(f, state_margins) for f in facilities]

    baseline_csv = REPORTS_DIR / "cahsp_national_baseline.csv"
    write_baseline_csv(scores, baseline_csv)
    print(f"  Wrote {baseline_csv.relative_to(REPO_ROOT)} ({len(scores)} rows)")

    band_summary = summarize_bands(scores)
    band_file = REPORTS_DIR / "cahsp_band_summary.json"
    band_file.write_text(json.dumps(band_summary, indent=2, default=str))
    print(f"  Wrote {band_file.relative_to(REPO_ROOT)}")

    triage = summarize_binding(scores)
    triage_file = REPORTS_DIR / "cahsp_binding_constraint_triage.json"
    triage_file.write_text(json.dumps(triage, indent=2, default=str))
    print(f"  Wrote {triage_file.relative_to(REPO_ROOT)}")

    print("\nBand distribution:")
    for band in ("Elite", "Solved", "High", "Moderate", "Developing"):
        n = band_summary["bands"].get(band, 0)
        pct = (n / len(scores) * 100.0) if scores else 0.0
        print(f"  {band:>10}: {n:>4}  ({pct:5.1f}%)")
    print(f"\nBenchmark solved (CAHSP ≥ {BENCHMARK_THRESHOLD} with dual mandate): "
          f"{band_summary['benchmark_solved_count']} / {len(scores)}")
    print("\nBinding-constraint triage:")
    for b, n in sorted(triage["binding_totals"].items(), key=lambda x: -x[1]):
        print(f"  {b.upper():>3}: {n:>4}  — {recommended_action(b)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
