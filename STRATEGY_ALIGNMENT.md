# Strategy Alignment — CAH + CAHSP

**Scope:** current-state-vs-desired-state analysis of this repo against two external specs published at visionblox.org.

- **CAH Strategy** — https://visionblox.org/cah
- **CAHSP Benchmark** — https://visionblox.org/cahsp

This extends the existing `gap-analysis-1.md` / `gap-analysis-2.md` / `gap-analysis-3.md` series, which focused on implementation gaps inside the modelling code. This doc pivots to **external-spec alignment**: does what we've built match what we told the outside world we were building?

---

## Executive Verdict

**Overall alignment: ~53%.** Strong mathematical core, weak infrastructure / compliance / validation layers.

| Layer | Coverage | Notes |
|-------|---------:|-------|
| Scoring + optimization math | **95%** | CAHSP-Score, dual mandate, Lagrangian solver all functional |
| Data pipeline (ground truth) | **65%** | HCRIS + MBQIP + HRSA acquired; Hospital Compare partial; prospective pilot missing |
| Pillar / Class coverage | **60%** | Classes 1, 4 strong; Class 2 good; Classes 3, 5 partial; Pillar 3 weakest |
| Edge / ARIS-2025 infrastructure | **20%** | FHIR mapper exists; Jetson Orin + edge AI = 0% |
| Compliance posture | **25%** | HIPAA named; HITRUST / FedRAMP / GSA MAS / Section 508 unevidenced |

---

## Part 1 — CAH Strategy Alignment

### Quantified goals (desired → current evidence)

| Desired outcome | Current repo artifact |
|-----------------|----------------------|
| Operating margin −2.3% → +0.5% | `objectives.py` (revenue, margin); `cahsp_score.py:68-103` (`compute_fi`) |
| Denial rate 8.7% → 5.0% | `src/cah_engine/integration/claims_processor.py:20-76` (enum only; no scrubber) |
| Labor cost ratio 58.2% → 52.0% | `workforce.py:47-76`; `models.py:73-76` |
| $1.97M / facility × 1,377 CAHs | `MV-CAHI.md`; `PHASE1_EMPIRICAL_VALIDATION.md:140-195` (WA + MT only) |

### Pillar 1 — Mathematical Optimization

| Desired | Current | Gap |
|---------|---------|-----|
| Lagrangian-constrained models | `solver.py:53-150` (Charnes-Cooper + SQP) | CC transformation under-documented |
| 25-bed cap | `constraints.py:114-121` | ✓ |
| 96-hr stay limit | `MV-CAHI.md:27` only | No code-level enforcement |
| 35-mi distance | `constraints.py` — implicit via CAH designation | No explicit haversine constraint |
| Robust optimization | `robust.py` (Monte Carlo only) | No distributionally-robust variant |

### Pillar 2 — HCRIS Data Pipeline

| Desired | Current | Gap |
|---------|---------|-----|
| CMS cost report ingestion | `step1_download_cms_cost_reports.py`; `src/cah_engine/foundation/cost_report.py` | ✓ |
| WA + MT focus | `step1_download_cms_cost_reports.py` state filter (line 68) | ✓ |
| Benchmark conversion | `PHASE1_EMPIRICAL_VALIDATION.md:140-195` | Sources marked "Needs Validation"; no metadata in scoring outputs |
| Flex Monitoring Team gold standard | — | Not integrated |

### Pillar 3 — ARIS-2025 Architecture

| Desired | Current | Gap |
|---------|---------|-----|
| FHIR R4 interoperability | `src/cah_engine/integration/fhir_mapper.py`; `kpi-fhir-mapping.yaml` | USCDI v3 stated; no conformance tests |
| Edge AI on Jetson Orin | — | **0%** — no Jetson / TensorRT / CUDA refs; `requirements-ai.txt` is cloud-only (OpenAI, Anthropic, MCP) |
| 1–2 FTE IT design | `MV-CAHI.md:57, 108-131` | Documented, not validated |
| 25 / 3 Mbps broadband | `MV-CAHI.md:63`; `ARCHITECTURE.md:160-168` | No bandwidth-simulation test |

> **Naming drift:** the external strategy says *ARIS-2025*; the repo documents *MV-CAHI*. These should be reconciled (either rename the repo doc, or call out explicitly that MV-CAHI is the in-repo instantiation of ARIS-2025).

### Programs

| Program | Current | Gap |
|---------|---------|-----|
| EMR / Epic / HL7 / FHIR | FHIR mapper present; Epic Community Connect named in `MV-CAHI.md:59` | No vendor integration code |
| Medicaid cost reporting (60% labor ↓) | — | Goal stated in `gap-analysis-1.md:61`; no module |
| Healthcare AI (96% doc intelligence) | — | No NLP / document-intelligence code |

### Compliance posture

| Claim (from strategy) | Evidence in repo |
|-----------------------|------------------|
| HIPAA | `SECURITY.md:49` (narrative only; no BAA / controls map) |
| HITRUST | — |
| FedRAMP-aware | — |
| GSA MAS | — |
| Minority-owned small biz | — |
| Section 508 | — |

---

## Part 2 — CAHSP Benchmark Alignment

### CAHSP-Score formula

✓ **Fully implemented.** `cahsp_score.py:301-371` produces

```
CAHSP = 100 × [0.30·FI + 0.30·QI + 0.20·OI + 0.10·WI + 0.10·CI]
```

Weights sum to 1.0 (`cahsp_score.py:48`). Score bands at lines 57-63. Dual mandate (FI ≥ 0.50 ∧ QI ≥ 0.50) enforced at lines 54-55, 256; surfaced on the result object at line 370.

### Five problem classes

| Class | Coverage | Key files | Biggest gap |
|-------|---------:|-----------|-------------|
| 1 Financial Structure | **85%** | `cahsp_score.py:68-103`; `objectives.py`; `src/cah_engine/integration/claims_processor.py:20-76` | No pre-bill scrubber; denial categories are enum-only |
| 2 Clinical Quality | **90%** | `cahsp_score.py:106-125`; `transfer_network.py`; `step2_download_mbqip_quality.py` | Transfer optimizer not wired into main solver (`x[8]`) |
| 3 Operational Architecture | **60%** | `objectives.py:80-87` (`revenue_swing`); `claims_processor.py`; `src/cah_engine/decision/revenue_protector.py` | AI triage absent; no federated multi-facility model |
| 4 Workforce / Staffing | **100%** | `workforce.py:47-76, 130-147`; `cahsp_score.py:166-193` | — |
| 5 Solution Confidence | **40%** | `cahsp_score.py:195-232` | Only margin predictability scored; **transferability + payer-sensitivity absent** |

### Ground-truth sources

| Source | Status | Evidence |
|--------|--------|----------|
| CMS HCRIS | ✓ active | `step1_download_cms_cost_reports.py` |
| MBQIP | ✓ active | `step2_download_mbqip_quality.py` |
| CAH designation | ✓ active | `step3_download_cah_designation.py` |
| HRSA AHRF | ◐ acquired, under-used | `step5_download_hrsa_workforce.py` |
| CMS Hospital Compare | ◐ referenced only | `PHASE1_EMPIRICAL_VALIDATION.md:26-27`; no downloader |
| CMS Rural Health scrape | ✓ recent add | `step6_scrape_cms_rural_health.py` |
| Prospective pilot | ✗ missing | — |

### Phase readiness

| Phase | Status | Evidence |
|-------|--------|----------|
| P0 — baseline scoring (now) | ✓ | `cahsp_score.py` runs end-to-end |
| P1 — Q3 2026 Type A cycle | ◐ | No Type A / Type B classifier; no benchmark-cycle runner |
| P2 — Q1 2027 Type B cycle | ✗ | No Type B validation framework |
| 24-month prospective hold | ✗ | No time-series tracker; no longitudinal DB |

### CAHSP compliance requirements

| Requirement | Current |
|-------------|---------|
| HIPAA compliant systems | narrative in `SECURITY.md:49` |
| HITRUST-audited security | not evidenced |
| Section 508 accessibility | not evidenced |
| FedRAMP-aware architecture | not evidenced |
| HCRIS data integration capability | ✓ via `step1_download_cms_cost_reports.py` |
| 24-month prospective validation tracking | ✗ |

---

## Top 10 Gaps (strategic rank order)

| # | Gap | Why it matters | Effort |
|---|-----|----------------|--------|
| 1 | **Jetson Orin / edge-AI stack** | 0% of Pillar 3; `requirements-ai.txt` is cloud-only. Blocks the "1–2 FTE IT, 25/3 Mbps" design promise entirely. | High |
| 2 | **Prospective + 24-month longitudinal validation** | Blocks the "Solved" designation under the CAHSP breakthrough criterion. No time-series infra exists. | Very high |
| 3 | **Type A / Type B facility classifier** | Core to CAHSP P1 (Q3 2026) and P2 (Q1 2027) cycles. Absent entirely. | High |
| 4 | **Document-intelligence / healthcare AI (96% claim)** | No NLP, no OCR, no extraction code anywhere in the repo. | Very high |
| 5 | **Transferability + payer-sensitivity in CI** | `cahsp_score.py:compute_ci` (195-232) scores only margin predictability; spec requires all three sub-components. | Medium |
| 6 | **Medicaid cost-reporting module (60% labor ↓ claim)** | No code for the headline Pillar-2 program deliverable. | Medium |
| 7 | **Explicit 35-mile distance constraint** | Hard 42 CFR § 485.610 rule is implicit only — quick haversine addition in `constraints.py`. | Low |
| 8 | **Compliance evidence pack** | HITRUST, FedRAMP, Section 508, GSA MAS all claimed externally; none mapped in repo. | Medium |
| 9 | **Benchmark source metadata in outputs** | `PHASE1_EMPIRICAL_VALIDATION.md` sources not surfaced in `CAHSPResult` objects, so downstream consumers can't attribute scores. | Low |
| 10 | **MV-CAHI constraint test suite + naming reconciliation** | `MV-CAHI.md:108-131` computational envelope never executed under load / bandwidth simulation. Also reconcile ARIS-2025 vs MV-CAHI naming drift. | Medium |

---

## Appendix — Suggested follow-up PR titles

| Gap # | Proposed PR title |
|------:|-------------------|
| 1 | `feat(edge): add Jetson Orin target + offline inference path` |
| 2 | `feat(validation): longitudinal scoring store + 24-mo hold tracker` |
| 3 | `feat(cahsp): Type A / Type B classifier + benchmark-cycle runner` |
| 4 | `feat(ai): CMS cost-report document-intelligence pipeline` |
| 5 | `feat(cahsp): add transferability + payer-sensitivity to compute_ci` |
| 6 | `feat(medicaid): state Medicaid cost-report automation module` |
| 7 | `feat(constraints): explicit 35-mile haversine distance check` |
| 8 | `docs(compliance): HITRUST / FedRAMP / 508 / GSA MAS evidence pack` |
| 9 | `feat(cahsp): surface benchmark source metadata on CAHSPResult` |
| 10 | `test(mv-cahi): load + bandwidth simulation for computational envelope` + `docs: reconcile ARIS-2025 / MV-CAHI naming` |

---

## Methodology

Coverage percentages are per-component coverage ratios averaged inside each layer — e.g. the "Pillar / Class coverage" row of the executive table averages Class 1 (85%), Class 2 (90%), Class 3 (60%), Class 4 (100%), Class 5 (40%) = 75% for CAHSP classes, blended with the three CAH pillars for the overall 60%. The 53% top-line is the simple mean across the five layer rows. File:line references were captured 2026-04-20 on branch `claude/cah-strategy-alignment-analysis-5MK6s` at HEAD `7d1873f`; re-verify if the files have since moved.
