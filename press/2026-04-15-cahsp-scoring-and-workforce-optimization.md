# CAHSP composite scoring and workforce (Class 4) optimization shipped

**VISIONBLOX LLC × ZUUP INNOVATION LAB — FOR IMMEDIATE RELEASE**
April 15, 2026

The CAH Transformation Engine now includes a CAHSP (Critical Access Hospital Sustainability & Performance) composite scoring module and a workforce-constrained optimization path aligned with CAHSP Class 4, closing four long-standing scope gaps (Gaps 1, 3, 6, 9) and bringing the pilot engine to feature-parity with the whitepaper specification.

## Operational Impact

- **CAH administrators** receive a single CAHSP composite score per facility, combining financial, quality, access, and workforce dimensions — usable for board-level reporting without hand-assembling dashboards.
- **WSHA and MHA** can now run the Phase 1 pilot (WA 39 + MT 50 = 89 CAHs) with a workforce cap (`total_fte_cap`) enforced, so recommendations no longer ignore the hiring realities that dominate rural staffing decisions.
- **HRSA stakeholders** get a first-class data downloader for the HRSA workforce datasets (Step 5), eliminating the brittle manual export step that previously blocked end-to-end reproduction.
- A `--states` filter on the CMS cost-report download lets a state association pull only its cohort (e.g., `--states WA,MT`) instead of staging the full 1.5 GB national dump.

## Strategic Significance

- **Closes CAHSP Class 4 (Workforce)** — the first non-financial CAHSP class wired into the optimizer, establishing the template for Classes 1–3 and 5.
- **Corrects the operating-margin benchmark** from 0.5% to 5.0%, aligning commercial framing with the realistic improvement target cited in partner conversations and the Phase 1 whitepaper.
- **Moves the whitepaper and the code into lockstep** — Phases 1, 1.2, and 1.3 of the whitepaper realignment land in the same window, so investor materials and the executing code reference the same numbers, scopes, and assumptions.
- **National scalability unblocked** — the CAH count is now a single source of truth (`get_cah_count()`), resolving an ambiguity that had propagated through prior investor decks.

## Technical Details

- **CAHSP composite scoring (Gap 3):** `cahsp_score.py` — composite rollup across CAHSP classes.
- **Workforce optimization (Gap 1, CAHSP Class 4):** `workforce.py` module; `WorkforceParameters` and `WorkforceResult` dataclasses in `models.py`; new `total_fte_cap` constraint wired in `constraints.py`.
- **HRSA data pipeline (Gap 1):** `step5_download_hrsa_workforce.py` adds Step 5 to the master execution guide.
- **CAH count reconciliation (Gap 6):** `get_cah_count()` utility replaces scattered hard-coded counts; national total converges on 1,377 (CMS POS FY2024).
- **State filtering (Gap 9):** `step1_download_cms_cost_reports.py` now accepts `--states`.
- **Whitepaper realignment:** Phases 1 → 1.3; docs reorganized under `docs/analysis`, `docs/baseline`, `docs/validation`.
- **Benchmark correction:** operating-margin target updated 0.5% → 5.0% across benchmarks.

### Quick start

```bash
# Pull WA + MT cost reports only
python3 step1_download_cms_cost_reports.py --states WA,MT

# Run Step 5 (HRSA workforce)
python3 step5_download_hrsa_workforce.py

# Score a facility set
python3 -c "from cahsp_score import *  # see module for API"
```

## References

- PR: [#1](https://github.com/khaaliswooden-max/cah/pull/1) — `claude/analyze-cah-cahsp-gaps-x633L`
- Key commits: `b2f5b7d` (CAHSP composite), `e5b2a07` (workforce optimization), `ca75903` (workforce dataclasses), `2f7726e` (HRSA downloader), `fdf1295` (total_fte_cap), `e7b6602` (Step 5 wiring), `2884fe4` (CAH count reconciliation), `948fcf4` (--states filter), `c0e6a0f` (margin 0.5% → 5.0%)
- Related docs: `docs/analysis/`, `docs/baseline/`, `docs/validation/`, `PHASE1_EMPIRICAL_VALIDATION.md`, `MV-CAHI.md`

---

**About VISIONBLOX × ZUUP.** The CAH Transformation Engine is a joint effort of VISIONBLOX LLC and ZUUP INNOVATION LAB to bring dual-objective optimization — a 5% operating-margin uplift alongside MBQIP/CAHSP quality benchmarks — to the 1,377 Critical Access Hospitals that make up the backbone of U.S. rural healthcare. Phase 1 empirical validation targets Washington (39 CAHs) and Montana (50 CAHs), leveraging WSHA and MHA benchmark networks. **Contact:** Aldrich K. Wooden — kwooden@visionblox.com
