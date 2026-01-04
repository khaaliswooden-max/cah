# Operational Benchmarks Reference

**CAH Transformation Engine — Staff & Patient-Level KPIs**

This document translates the mathematical optimization goals into actionable, measurable benchmarks for daily operations.

---

## 📊 Quick Reference: Benchmark Summary

| Cadence | Profitability | Quality | Optimization | Total |
|---------|---------------|---------|--------------|-------|
| **Daily** | 5 | 5 | 4 | **14** |
| **Weekly** | 5 | 5 | 2 | **12** |
| **Monthly** | 5 | 4 | 4 | **13** |
| **Total** | 15 | 14 | 10 | **39** |

---

## 🔗 How Benchmarks Link to Optimization Goals

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    OPTIMIZATION MODEL                                   │
│  maximize: θ × Quality(x) + (1-θ) × Margin(x)                          │
│  subject to: Regulatory Constraints, Margin ≥ 5%                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ PROFITABILITY │         │  QUALITY CARE   │         │  CONSTRAINTS    │
│    GOAL       │         │     GOAL        │         │   ALIGNMENT     │
│  Margin ≥ 5%  │         │  Q(x) maximized │         │  g(x) ≤ 0       │
└───────────────┘         └─────────────────┘         └─────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ PROF-D01-M05  │         │ QUAL-D01-M05    │         │ OPT-D01-M04     │
│ Revenue/Cost  │         │ MBQIP Measures  │         │ Regulatory      │
│ Benchmarks    │         │ Benchmarks      │         │ Benchmarks      │
└───────────────┘         └─────────────────┘         └─────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     STAFF/PATIENT LEVEL ACTIONS                        │
│  - Charge capture      - Pain assessment     - Census monitoring       │
│  - Productivity        - Falls prevention    - Staffing ratios         │
│  - CMI documentation   - Hand hygiene        - ALOS tracking           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📅 Daily Benchmarks

### Profitability (PROF-D)

| ID | Metric | Target | Floor/Ceiling | Unit | Who Measures |
|----|--------|--------|---------------|------|--------------|
| PROF-D01 | Revenue per Patient Day | **$4,200** | ≥$3,500 | $/PD | Revenue Cycle |
| PROF-D02 | ED Revenue per Visit | **$485** | ≥$400 | $/visit | ED Staff |
| PROF-D03 | Labor Cost per Patient Day | **$2,800** | ≤$3,500 | $/PD | Nurse Manager |
| PROF-D04 | Bed Utilization Rate | **50%** | 30-85% | % | Nursing Supervisor |
| PROF-D05 | Outpatient Encounters | **55** | ≥40 | visits/day | Clinic Manager |

### Quality (QUAL-D)

| ID | Metric | Target | Floor/Ceiling | Unit | Who Measures |
|----|--------|--------|---------------|------|--------------|
| QUAL-D01 | Door-to-Provider Time | **25** | ≤45 | minutes | ED Nurse/Provider |
| QUAL-D02 | Pain Assessment Rate | **95%** | ≥90% | % | Bedside Nurse |
| QUAL-D03 | Nursing Hours per PD | **8.0** | ≥6.0 | hrs/PD | Nurse Manager |
| QUAL-D04 | Falls Risk Assessment | **100%** | ≥95% | % | Admitting Nurse |
| QUAL-D05 | Hand Hygiene Compliance | **95%** | ≥85% | % | All Clinical Staff |

### Optimization Alignment (OPT-D)

| ID | Metric | Target | Floor/Ceiling | Unit | Constraint Link |
|----|--------|--------|---------------|------|-----------------|
| OPT-D01 | Total Beds Occupied | **18** | ≤**25** | beds | 42 CFR § 485.620 |
| OPT-D02 | Average LOS | **72** | ≤**96** | hours | 42 CFR § 485.620 |
| OPT-D03 | Nurse-to-Patient Ratio | **0.50** | ≥0.40 | ratio | Constraint h₂ |
| OPT-D04 | ED Coverage Hours | **24** | ≥20 | hours | Constraint g₄ |

> ⚠️ **HARD CONSTRAINTS** (red): OPT-D01 ≤ 25 beds and OPT-D02 ≤ 96 hours are regulatory requirements. Violation risks CAH designation loss.

---

## 📅 Weekly Benchmarks

### Profitability (PROF-W)

| ID | Metric | Target | Floor/Ceiling | Unit | Who Measures |
|----|--------|--------|---------------|------|--------------|
| PROF-W01 | Charge Capture Rate | **98%** | ≥95% | % | Revenue Cycle |
| PROF-W02 | Overtime per FTE | **2** | ≤6 | hrs/FTE | Dept Managers |
| PROF-W03 | Case Mix Index | **1.10** | ≥0.85 | index | HIM Director |
| PROF-W04 | Swing Bed Utilization | **65%** | ≥40% | % | SNF Coordinator |
| PROF-W05 | ED Provider Productivity | **12** | ≥8 | enc/shift | ED Medical Dir |

### Quality (QUAL-W)

| ID | Metric | Target | Floor/Ceiling | Unit | MBQIP Link |
|----|--------|--------|---------------|------|------------|
| QUAL-W01 | ED Length of Stay | **180** | ≤240 | minutes | ED-2b |
| QUAL-W02 | Med Reconciliation Rate | **98%** | ≥90% | % | Readmission |
| QUAL-W03 | HCAHPS Responsiveness | **75%** | ≥65% | % | HCAHPS |
| QUAL-W04 | Catheter Days/100 PD | **15** | ≤25 | days/100 | CAUTI |
| QUAL-W05 | Opioid Rx Compliance | **95%** | ≥90% | % | Safe Opioid |

### Optimization Alignment (OPT-W)

| ID | Metric | Target | Floor/Ceiling | Unit | Constraint Link |
|----|--------|--------|---------------|------|-----------------|
| OPT-W01 | ED Visits per Provider FTE | **90** | ≤125 | visits/FTE | Constraint h₄ |
| OPT-W03 | Census Capacity Utilization | **70%** | ≤100% | % | Constraint h₁ |

---

## 📅 Monthly Benchmarks

### Profitability (PROF-M)

| ID | Metric | Target | Floor/Ceiling | Unit | Who Reviews |
|----|--------|--------|---------------|------|-------------|
| **PROF-M01** | **Operating Margin** | **≥5%** | ≥0% | % | **CFO/Board** |
| PROF-M02 | Days in A/R | **45** | ≤60 | days | Rev Cycle Dir |
| PROF-M03 | Cost per Adjusted PD | **$3,200** | ≤$4,000 | $/APD | CFO |
| PROF-M04 | Medicare CCR | **0.45** | ≤0.60 | ratio | CFO |
| PROF-M05 | Revenue per FTE | **$22,000** | ≥$18,000 | $/FTE | CEO |

> 🎯 **PROF-M01 is the PRIMARY profitability goal** — validates the 5% margin hypothesis.

### Quality (QUAL-M)

| ID | Metric | Target | Floor/Ceiling | Unit | MBQIP Link |
|----|--------|--------|---------------|------|------------|
| QUAL-M01 | 30-Day Readmission | **12%** | ≤18% | % | HRRP |
| QUAL-M02 | Falls with Injury | **1.5** | ≤3.0 | per 1000 PD | PSI-08 |
| QUAL-M03 | CAUTI Rate | **1.0** | ≤2.0 | per 1000 cath | NHSN |
| **QUAL-M04** | **HCAHPS Overall** | **≥72%** | ≥65% | % | **HCAHPS** |

> 🎯 **QUAL-M04 is the PRIMARY quality goal** — validates the quality care hypothesis.

### Optimization Alignment (OPT-M)

| ID | Metric | Target | Floor/Ceiling | Unit | What It Validates |
|----|--------|--------|---------------|------|-------------------|
| **OPT-M01** | Constraint Satisfaction | **100%** | ≥95% | % | All constraints |
| **OPT-M02** | Model Alignment Score | **0.90** | ≥0.75 | score | Lagrangian correctness |
| OPT-M03 | Pareto Efficiency | **0.95** | ≥0.80 | score | Optimization quality |
| OPT-M04 | Shadow Price Value | **$0** | ≥-$50K | $ | Constraint economics |

> 🎯 **OPT-M01 + OPT-M02 validate the Lagrangian math/algorithm correctness.**

---

## 👩‍⚕️ Staff Daily Checklist

### Nursing Staff

| ☐ | Task | Benchmark | Evidence |
|---|------|-----------|----------|
| ☐ | Document pain score within **30 minutes** of arrival | QUAL-D02 | OP-18b |
| ☐ | Complete falls risk assessment on **every admission** | QUAL-D04 | AHRQ PSI |
| ☐ | Perform hand hygiene at **5 WHO moments** | QUAL-D05 | CDC NHSN |
| ☐ | Review catheter necessity **daily** (remove if not needed) | QUAL-W04 | CAUTI bundle |
| ☐ | Complete medication reconciliation **at discharge** | QUAL-W02 | Joint Commission |
| ☐ | Verify nurse-to-patient ratio **≥0.50** | OPT-D03 | Aiken 2014 |

### ED Staff

| ☐ | Task | Benchmark | Evidence |
|---|------|-----------|----------|
| ☐ | Provider contact within **25 minutes** of arrival | QUAL-D01 | ED-1b |
| ☐ | Track and report ED LOS (target: **180 min**) | QUAL-W01 | ED-2b |
| ☐ | Ensure **24/7** provider coverage | OPT-D04 | 42 CFR § 485.618 |
| ☐ | Document **all** ED charges completely | PROF-D02 | Revenue cycle |

### Providers

| ☐ | Task | Benchmark | Evidence |
|---|------|-----------|----------|
| ☐ | See ED patients within **25 minutes** | QUAL-D01 | ED-1b |
| ☐ | Check PDMP before opioid prescribing | QUAL-W05 | Safe Opioid |
| ☐ | Document diagnoses for accurate **CMI coding** | PROF-W03 | CMS MS-DRG |
| ☐ | Complete discharge summary **same day** | QUAL-M01 | Readmission |

### Charge Nurse / House Supervisor

| ☐ | Task | Benchmark | CRITICAL? |
|---|------|-----------|-----------|
| ☐ | Monitor total beds **< 25** | OPT-D01 | ⚠️ REGULATORY |
| ☐ | Review ALOS for patients approaching **96 hours** | OPT-D02 | ⚠️ REGULATORY |
| ☐ | Verify nurse-to-patient ratio **≥0.50** | OPT-D03 | Constraint |
| ☐ | Report charge capture completeness | PROF-W01 | Revenue |

---

## 📈 Hypothesis Validation Framework

### 1. Profitability Hypothesis

**Claim**: CAH can achieve ≥5% operating margin through optimized resource allocation.

| Validation Level | Metric | Frequency | Success Criteria |
|------------------|--------|-----------|------------------|
| Leading | PROF-D01, D02, D03 | Daily | Within target range |
| Intermediate | PROF-W01, W02, W03 | Weekly | Trends improving |
| **Lagging** | **PROF-M01** | Monthly | **≥5% for 3 months** |

### 2. Quality Hypothesis

**Claim**: Quality metrics improve with evidence-based staffing (per Aiken 2014).

| Validation Level | Metric | Frequency | Success Criteria |
|------------------|--------|-----------|------------------|
| Leading | QUAL-D01, D02, D03, D04, D05 | Daily | Compliance ≥95% |
| Intermediate | QUAL-W01, W02, W03, W04, W05 | Weekly | Meeting targets |
| **Lagging** | **QUAL-M01, M02, M03, M04** | Monthly | **All benchmarks met** |

### 3. Lagrangian/Algorithm Hypothesis

**Claim**: Operational KPIs align with optimization model decision variables.

| Validation Level | Metric | Frequency | Success Criteria |
|------------------|--------|-----------|------------------|
| Constraint | OPT-D01, D02, D03, D04 | Daily | 100% compliance |
| Alignment | OPT-W01, W03 | Weekly | Within bounds |
| **Validation** | **OPT-M01, M02** | Monthly | **100% + ≥0.85 score** |

---

## 🔢 Decision Variable to Benchmark Mapping

| Decision Variable | Symbol | Optimal Range | Related Benchmarks |
|-------------------|--------|---------------|-------------------|
| Acute beds staffed | x[0] | 5-25 | OPT-D01, PROF-D04 |
| Swing beds | x[1] | 0-15 | PROF-W04, OPT-D01 |
| Nursing FTE | x[2] | 20-60 | PROF-D03, QUAL-D03, OPT-D03 |
| Provider FTE | x[3] | 2-12 | PROF-W05, OPT-D04, OPT-W01 |
| Avg daily census | x[4] | 2-18 | PROF-D01, OPT-D02, OPT-W03 |
| ED visits/year | x[5] | 2K-15K | PROF-D02, OPT-W01 |
| OP visits/year | x[6] | 5K-40K | PROF-D05 |
| Case Mix Index | x[7] | 0.8-1.4 | PROF-W03 |

---

## 📋 Data Collection Quick Reference

| Data Source | Benchmarks Fed | Update Frequency |
|-------------|----------------|------------------|
| ADT/Census | OPT-D01, D02, PROF-D04, QUAL-D03 | Real-time |
| EHR Charges | PROF-D01, D02, W01 | Daily |
| ED Tracking | QUAL-D01, W01, PROF-D02 | Real-time |
| Payroll | PROF-D03, W02, QUAL-D03 | Pay period |
| Scheduling | OPT-D03, D04, PROF-W05 | Daily |
| Incident Reports | QUAL-M02 | Event-driven |
| Infection Control | QUAL-D05, W04, M03 | Weekly |
| HCAHPS | QUAL-W03, M04 | Monthly |
| GL/Financial | PROF-M01, M02, M03 | Monthly |

---

## 📊 Scorecard Color Coding

| Status | Color | Meaning |
|--------|-------|---------|
| 🟢 **Excellent** | Green | At or exceeding target |
| 🟡 **Acceptable** | Yellow | Between floor and target |
| 🔴 **Critical** | Red | Below floor or above ceiling |
| ⚫ **Constraint Violation** | Black | Regulatory requirement breached |

---

## References

- **42 CFR § 485.620** — CAH bed cap and ALOS requirements
- **Aiken et al. (2014)** — Nurse staffing and patient mortality, *Lancet*
- **MBQIP Dashboard 2024** — Quality measure benchmarks
- **CMS Cost Report Form 2552-10** — Financial parameters
- **CAH Optimization Module** — `solver.py`, `objectives.py`, `constraints.py`

---

*Document Version: 1.0 | Generated: 2026-01-03 | CAH Transformation Engine*

