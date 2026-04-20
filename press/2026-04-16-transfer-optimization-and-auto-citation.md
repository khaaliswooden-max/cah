# Transfer optimization and auto-citation engine add auditable, payer-aware throughput

**VISIONBLOX LLC × ZUUP INNOVATION LAB — FOR IMMEDIATE RELEASE**
April 16, 2026

The CAH Transformation Engine now optimizes patient-transfer volume as a first-class decision variable and generates APA-formatted, machine-readable citations for every benchmark claim the optimizer makes — closing scope Gaps 7 and 8 and bringing CAHSP Class 2 (Care Coordination) into the dual-objective model.

## Operational Impact

- **CAH administrators** can see, for each facility, how transfer volume interacts with revenue, cost, and the MBQIP 15% transfer-appropriateness threshold — instead of treating transfers as an uncontrolled leak.
- **State hospital associations and regional referral partners** get a min-cost flow subproblem + leakage analysis that quantifies where patients are being lost and how that maps to quality impact.
- **Compliance, grants, and policy teams** can export every benchmark the optimizer cites as an APA reference (or JSON / BibTeX) — auditable provenance without a manual bibliography pass.

## Strategic Significance

- **CAHSP Class 2 lights up.** Class 4 (Workforce) came online in PR #1; transfer optimization brings Care Coordination online, accelerating the march toward full CAHSP coverage.
- **Defensibility moat.** Auto-citation converts every quantitative claim the engine makes into a footnote a regulator, actuary, or auditor can trace — a differentiator vs. black-box consulting analyses.
- **Single source of truth for CAH count.** References to ~1,377 CAHs are reconciled across `README.md`, `METHODOLOGY.md`, and `MV-CAHI.md`, so partner and investor materials stay consistent with the code.

## Technical Details

- **Transfer optimization (Gap 7, CAHSP Class 2):**
  - **9th decision variable** `x[8] = transfer_volume` added in `models.py`.
  - Revenue/cost parameters `alpha_transfer` and `beta_transfer`, with `revenue_transfer()` and `cost_transfer()` (plus gradients) in `objectives.py`.
  - New `transfer_capacity` constraint in `constraints.py` anchored to the MBQIP 15% transfer-appropriateness threshold (`source="MBQIP transfer appropriateness; CMS Hospital Compare"`).
  - New module `transfer_network.py` — `TransferNetworkModel` class, min-cost flow subproblem, leakage analysis, quality impact scoring.
- **Auto-citation (Gap 8):**
  - `auto_citation.py` — `BenchmarkClaim` dataclass + `AutoCitationEngine` converting HCRIS line items into auditable benchmark claims.
  - Exports to APA text, JSON, and BibTeX.
  - Wired into `run_optimization.py` via the new `--auto-cite` flag: `parser.add_argument("--auto-cite", action="store_true", help="Generate auto-citation report from payer-mix data")` (see `run_optimization.py:498`).
- **Consistency pass.** CAH count references standardized to ~1,377 (CMS POS FY2024) across `README.md`, `METHODOLOGY.md`, `MV-CAHI.md`.

### Quick start

```bash
# Run the optimizer with an auto-citation report
python3 run_optimization.py --auto-cite
```

## References

- PR: [#3](https://github.com/khaaliswooden-max/cah/pull/3) — `claude/fix-dashboard-cah-gaps-3ZQgu`
- Key commit: `9ad7832` (`feat(gaps 7-8): add transfer optimization + auto-citation engine`)
- Related files: `transfer_network.py`, `auto_citation.py`, `objectives.py`, `constraints.py`, `models.py`, `run_optimization.py`

---

**About VISIONBLOX × ZUUP.** The CAH Transformation Engine is a joint effort of VISIONBLOX LLC and ZUUP INNOVATION LAB to bring dual-objective optimization — a 5% operating-margin uplift alongside MBQIP/CAHSP quality benchmarks — to the 1,377 Critical Access Hospitals that make up the backbone of U.S. rural healthcare. Phase 1 empirical validation targets Washington (39 CAHs) and Montana (50 CAHs), leveraging WSHA and MHA benchmark networks. **Contact:** Aldrich K. Wooden — kwooden@visionblox.com
