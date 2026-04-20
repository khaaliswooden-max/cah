# Math, Mandate, and the National Baseline

How the CAH optimization model uses public data to solve the Critical Access
Hospital problem, how the 2‑part mandate gates a solution, and what the
current 1,376‑facility national baseline actually shows.

This document stitches together three layers already in the repo:

1. The math (`models.py`, `objectives.py`, `constraints.py`, `solver.py`,
   `pareto.py`, `robust.py`).
2. The data pipeline (`step1_download_cms_cost_reports.py` through
   `step6_scrape_cms_rural_health.py`).
3. The national population scoring added in this branch
   (`calculate_cahsp_baseline.py`, `calculate_mandate_gap.py`,
   `dashboard/national.html`, `dashboard/mandate.html`).

The goal is a single reviewable artifact that an administrator, a CNO, a state
Flex coordinator, or a board member can read end‑to‑end without needing to
trace every citation.

---

## 1. The 2‑part mandate

From `cahsp_score.py:14` and `:53-55`: a CAH solution is only "Solved" when

    CAHSP >= 85  AND  FI >= 0.50  AND  QI >= 0.50

Financial without quality does not count; quality without financial does not
count; a high composite with either floor missed does not count. The dual
mandate is a gate, not a preference.

- **FI — Financial Index** (0.30 weight in CAHSP): operating margin, cost‑based
  reimbursement realization, payer mix.
- **QI — Clinical Quality Index** (0.30 weight): MBQIP‑weighted composite over
  HCAHPS, 30‑day readmission, ED throughput, falls, CAUTI, safe opioid
  prescribing.
- **OI — Operations Index** (0.20), **WI — Workforce Index** (0.10),
  **CI — Confidence Index** (0.10): round out the composite but are not part
  of the dual gate.

**Benchmark threshold:** `BENCHMARK_THRESHOLD = 85.0` in `cahsp_score.py:51`.

---

## 2. How the data flows into the math

Each `step*` script pulls a public dataset and feeds one or more parameters
in `models.py`:

| Script | Source | Parameters fed |
|---|---|---|
| `step1_download_cms_cost_reports.py` | CMS Form 2552‑10 HCRIS | `CAHParameters.alpha_1..4` (revenue), `beta_1..4` (cost), σ's for robust analysis |
| `step2_download_mbqip_quality.py` | MBQIP (Flex Monitoring Team) | `QualityBenchmarks.benchmarks` + `.weights` (ED‑2b, OP‑18b, HCAHPS, readmit, falls, CAUTI, opioid) |
| `step3_download_cah_designation.py` | CMS Provider of Services | `DecisionVariables.bounds` (25‑bed cap), CAH roster |
| `step5_download_hrsa_workforce.py` | HRSA AHRF / HPSA / NHSC | `WorkforceParameters` (travel ratio, tele‑coverage, pipeline) |
| `step6_scrape_cms_rural_health.py` | CMS Hospital Compare / Data Catalog | `alpha_transfer`, `beta_transfer`, national CAH roster used by `calculate_cahsp_baseline.py` |

Intermediate feature modules (`calculate_payer_mix.py`, `cahsp_score.py`,
`workforce.py`, `transfer_network.py`) convert raw pulls into the scalars the
solver consumes.

---

## 3. Mathematical formulation

**Decision vector** — `DecisionVariables` (`models.py:276-316`), nine
continuous variables with regulatory bounds:

    x = [acute_beds, swing_beds, nursing_FTE, provider_FTE,
         ADC, ED_visits, OP_visits, CMI, transfer_volume]

**Objectives** — `objectives.py`:

    R(x) = alpha_1 * CMI * (ADC * 365 / ALOS)
         + alpha_2 * ED_visits
         + alpha_3 * OP_visits
         + alpha_4 * swing_beds * swing_occupancy * 365
         + alpha_transfer * transfer_volume

    C(x) = beta_1 * nursing_FTE + beta_2 * provider_FTE
         + beta_3 + beta_4 * ADC * 365
         + beta_transfer * transfer_volume

    M(x) = (R(x) - C(x)) / R(x)         # operating margin

    Q(x) = sum_i w_i * normalize(measure_i(x))

    J(x) = theta * Q(x) + (1 - theta) * M_hat(x)    # default theta = 0.6

**Constraints** — `constraints.py`:

- Hard regulatory: `acute_beds + swing_beds <= 25` (42 CFR § 485.620/645)
- Operational: `ADC <= 0.85 * acute_beds`; `nursing_FTE / ADC >= 0.5`
  (Aiken 2014); `provider_FTE >= 2.0`; `ED / provider <= 5000`;
  `transfer <= 0.15 * ADC * 365`
- MV‑CAHI workforce: `nursing_FTE + provider_FTE <= 120`
- Margin floor: `M(x) >= 0.05`

---

## 4. Solver stack

- **`solver.py` — `CAHOptimizer.optimize()`** — multi‑start SLSQP with a
  Charnes‑Cooper reformulation of the margin ratio. The reformulation
  linearizes `M(x) = (R-C)/R` so that when constraints are linear we get a
  globally optimal LP; K≈10 random seeds handle residual non‑convexity.
- **`pareto.py` — `ParetoFrontExplorer.find_front()`** — augmented
  ε‑constraint (Mavrotas 2009). Sweeps the quality↔margin frontier so
  stakeholders can choose θ explicitly.
- **`robust.py` — `RobustCAHOptimizer.optimize_robust()`** — Bertsimas‑Sim
  budget‑of‑uncertainty using the σ's in `CAHParameters.sample()`, plus
  Monte Carlo for CIs on margin and quality.

Output lands as `OptimizationResult` in `models.py:355-433`, including
shadow prices for every binding constraint.

---

## 5. What the national baseline shows (this branch)

`calculate_cahsp_baseline.py` scores every CAH on the CMS Provider of
Services roster (`data/cms_rural_health/cah_hospitals.csv`). Results in
`reports/cahsp_national_baseline.csv` (1,376 rows),
`reports/cahsp_band_summary.json`, `reports/cahsp_binding_constraint_triage.json`.

### Band distribution

| Band | Count | % |
|---|---:|---:|
| Developing | 1,159 | 84.2% |
| Moderate | 202 | 14.7% |
| High | 15 | 1.1% |
| **Benchmark Solved** (CAHSP ≥ 85 AND dual mandate) | **0** | **0.0%** |

CAHSP distribution: mean 46.17, median 45.5, min 15.0, max 78.17. No facility
in the country currently clears the full benchmark gate.

### Binding constraint by count

Which single index is the smallest and therefore the facility's blocker:

| Binding index | Facilities |
|---|---:|
| QI | 742 |
| FI | 506 |
| OI | 69 |
| WI | 59 |

FI binds even in 3 of the 15 High‑band facilities — margin fragility exists
across the entire band distribution.

### 2‑part mandate cohorts

`calculate_mandate_gap.py` partitions the 1,376 roster against the dual
gate. Results in `reports/mandate_gap_analysis.csv` and
`reports/mandate_cohort_summary.json`.

| Cohort | Count | % | Meaning |
|---|---:|---:|---|
| dual_solved | 762 | 55.4% | FI ≥ 0.50 AND QI ≥ 0.50 — mandate cleared, maintain |
| fi_only_blocker | 505 | 36.7% | Margin push to unlock mandate |
| qi_only_blocker | 66 | 4.8% | Quality push to unlock mandate |
| both_blockers | 43 | 3.1% | Dual push required |
| quick_wins (headroom 0.05) | 11 | 0.8% | Within 0.05 of both floors |

---

## 6. Three corrections the national data forces on the narrative

1. **FI, not QI, is the national bottleneck at the mandate gate.** The raw
   binding‑constraint count makes QI look like the dominant blocker (742 vs.
   506), but at the 2‑part mandate gate only 66 facilities are QI‑only blockers
   vs. 505 FI‑only. Margin interventions move more facilities across the gate
   than quality interventions do.
2. **"Dual mandate met" is not "Solved".** 762 facilities (55.4%) clear both
   floors; 0 clear CAHSP ≥ 85 with the dual mandate. The 2‑part mandate is
   the entry criterion; climbing to Solved requires OI + WI + CI progress on
   top.
3. **AK quick‑wins need a data audit first.** All 11 "quick wins" sit at
   FI = 0.4833 and QI = 0.50 exactly, concentrated in Alaska IHS/tribal
   facilities (SEARHC, Maniilaq, Norton Sound, Samuel Simmonds, Wrangell…).
   That narrow numerical stripe likely reflects an ownership‑bias default
   and a QI pinned at the neutral 0.50, not 11 independent measurements.
   Treat as audit‑then‑act, not a 60‑day field push.

---

## 7. Cohort‑specific action program

| Cohort | Primary tool | Field actions | Success metric |
|---|---|---|---|
| fi_only_blocker (505) | `CAHOptimizer.optimize()` per facility, Charnes‑Cooper | Revenue‑cycle diagnostic, swing‑bed expansion, payer‑mix renegotiation, cost‑based reimbursement audit | FI crosses 0.50 without QI slipping below 0.50 |
| qi_only_blocker (66) | Solver with θ shifted toward quality | HCAHPS rounding, 30‑day readmission bundle, ED‑2b throughput, opioid stewardship | QI crosses 0.50 without FI slipping below 0.50 |
| both_blockers (43) | `pareto.py` + `robust.py` | If front never crosses (0.50, 0.50), escalate to Flex Program / state rural grant / affiliation | Feasible point above both floors exists |
| dual_solved (762) | `robust.py` under uncertainty | Defend the floor, then attack OI and WI to climb toward CAHSP ≥ 85 | Band moves Developing → Moderate → High |
| quick_wins (11 AK) | Data audit | Reconcile IHS/tribal FI scoring and QI default before any field action | Scoring confirmed or corrected |

---

## 8. Stakeholder translation

**Administrators / board — own FI and overall CAHSP.**
Run `calculate_cahsp_baseline.py` and `calculate_mandate_gap.py`; read the
facility's cohort in `reports/mandate_gap_analysis.csv`. Use `pareto.py` to
commit to one θ point in writing; use `robust.py` worst‑case margin as the
lender‑covenant cushion and grant‑ask quantification. Track shadow prices
quarterly — they identify the one constraint most worth lobbying to relax.

**Clinical FTE — own QI and WI.**
Lock staffing at the solver's recommended `nursing_FTE` and `provider_FTE`;
`nurse / ADC ≥ 0.5` is the floor, not a target. Cap travel‑nurse ratio at
0.25 (`WorkforceParameters.travel_nurse_ratio`) — above that, WI collapses
and FI follows. File MBQIP data on time; late or missing data zeros out the
measure in QI.

**Patients & community.**
The math keeps the local ED open at a safe ratio, holds the CAHSP transfer
rate inside the 15% MBQIP corridor so that transfers happen when they should,
and makes the transfer economics survivable so they happen when they should.
The CAHSP band and dual‑mandate status are the plain‑English answer to
"is our hospital going to be here in five years?"

---

## 9. Known gaps (follow‑ups)

1. **Per‑facility prescription.** The baseline classifies and gaps; it does
   not yet recommend a solver tuple per facility. Next step: a
   `run_optimization_batch.py` that calls `CAHOptimizer.optimize()` across
   the 1,376‑row roster, parameterized by cohort, and publishes
   `reports/per_facility_prescription.csv` keyed on CCN.
2. **OI + WI layer in the national view.** The triage file shows 69 OI‑bound
   and 59 WI‑bound facilities. `workforce.py` has the math; wire it into
   `dashboard/national.html` so the path from dual‑mandate‑met to
   CAHSP ≥ 85 is visible rather than implicit.
3. **Quarterly re‑pull loop.** The data‑to‑score loop is not yet automated.
   A scheduled step1–6 → re‑calibrate → re‑score → re‑gap job is what turns
   this from a report into a program.

---

## 10. Verification

```
python calculate_cahsp_baseline.py      # writes reports/cahsp_national_baseline.csv
python calculate_mandate_gap.py         # writes reports/mandate_gap_analysis.csv
pytest tests/                           # parameter / constraint / solver tests
python validate_data_quality.py         # 3-way roster alignment check
python validate_comprehensive.py        # pipeline end-to-end
```

Spot‑check the numbers in this document against
`reports/mandate_cohort_summary.json` and `reports/cahsp_band_summary.json`
after each re‑pull; if the cohort counts drift materially, the three
corrections in §6 may need to be re‑stated.
