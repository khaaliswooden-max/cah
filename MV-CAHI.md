# Minimum Viable CAH Infrastructure (MV-CAHI)

## Overview

The Minimum Viable CAH Infrastructure (MV-CAHI) specification defines a reference architecture representing the **median capabilities** of America's 1,300+ Critical Access Hospitals. All solutions developed within the CAH Transformation Engine must demonstrate viability against this baseline before scaling assumptions are introduced.

---

## Design Philosophy

> *Solutions must work for the facility with 1.5 IT staff, not the one with a dedicated informatics team.*

MV-CAHI represents the **50th percentile CAH**—half of all CAHs have fewer resources than this baseline. This ensures solutions are broadly applicable rather than limited to well-resourced outliers.

---

## Specification

### Clinical Infrastructure

| Component | Specification | Source |
|-----------|---------------|--------|
| Licensed Beds | 25 maximum (regulatory) | 42 CFR § 485.610 |
| Active Beds | 10 acute care, 15 swing | HRSA median |
| Average Daily Census | 8-12 patients | CMS Cost Reports |
| Annual Admissions | 400-600 | CMS Cost Reports |
| Average LOS | 3.2 days (76.8 hours) | CMS Cost Reports |
| ED Visits/Year | 4,000-8,000 | HRSA data |
| Emergency Department | 24/7, 4-6 beds | 42 CFR § 485.618 |
| Imaging | X-ray, basic ultrasound, CT (shared) | Survey data |
| Laboratory | Basic panels, send-out for specialty | Survey data |
| Pharmacy | Limited formulary, pharmacist 0.5-1.0 FTE | Survey data |
| Surgical | Minor procedures only, transfer for major | Survey data |

### Financial Profile

| Metric | Range | Benchmark |
|--------|-------|-----------|
| Annual Revenue | $15-25M | $20M median |
| Operating Margin | -2% to +3% | 0.5% median |
| Medicare Payer Mix | 55-75% | 65% median |
| Medicaid Payer Mix | 10-25% | 15% median |
| Commercial Payer Mix | 5-15% | 10% median |
| Self-Pay/Charity | 5-15% | 10% median |
| Bad Debt Rate | 3-8% | 5% median |
| Denial Rate | 5-15% | 10% median |
| Days Cash on Hand | 30-90 | 45 median |
| Net Patient Revenue per FTE | $80-120K | $100K median |

**Cost-Based Reimbursement Note**: CAHs receive Medicare cost-based reimbursement (101% of allowable costs), which fundamentally changes financial dynamics compared to PPS hospitals.

### Technical Infrastructure

| Component | Specification | Notes |
|-----------|---------------|-------|
| IT FTE | 1-2 | Often shared with other duties |
| EHR System | Single vendor, basic tier | MEDITECH, Cerner, Epic Community Connect, Athena |
| EHR Customization | Minimal | Standard configurations |
| Interoperability | Limited | Basic HL7 v2, minimal FHIR |
| HIE Participation | 40% | Often receive-only |
| Broadband | 25/3 Mbps (rural) | FCC minimum definition |
| Latency | 50-150 ms | Rural infrastructure |
| Uptime | 95-99% | Single ISP, limited redundancy |
| Server Room | Small closet or shared space | Environmental controls limited |
| Backup Power | Generator for clinical, battery for IT | 4-8 hours runtime |
| Disaster Recovery | Basic backup, limited testing | Often tape or external drives |

### Workforce Profile

| Role Category | FTE Range | Notes |
|---------------|-----------|-------|
| Total FTE | 80-120 | All staff |
| Nursing (RN) | 20-35 | High travel nurse dependency (20-40%) |
| Nursing (LPN/CNA) | 15-25 | Local hire, lower turnover |
| Physicians | 2-4 | Often locum tenens or part-time |
| Mid-Levels (NP/PA) | 2-5 | Growing share of coverage |
| Lab/Imaging | 5-10 | Cross-trained common |
| Pharmacy | 0.5-1 | Pharmacist may be remote |
| Therapy (PT/OT/ST) | 2-5 | Swing bed program support |
| Administration | 8-15 | Many wear multiple hats |
| IT | 1-2 | Often HIM, compliance, or admin combo |
| Housekeeping/Dietary | 10-20 | High local employment |

**Workforce Challenges**:
- Travel nurse dependency: 20-40% of nursing staff
- Physician recruitment average time: 12-18 months
- Annual turnover rate: 15-25%
- Training budget per employee: $200-500/year

### Regulatory Context

| Requirement | Citation | Operational Impact |
|-------------|----------|-------------------|
| Bed Limit | 42 CFR § 485.610(a) | Cannot expand acute capacity |
| LOS Limit | 42 CFR § 485.610(b) | Average ≤96 hours |
| Distance Requirement | 42 CFR § 485.610(c) | ≥35 miles or state waiver |
| Emergency Services | 42 CFR § 485.618 | 24/7 with on-call physician |
| Quality Reporting | CMS CAH Quality Reporting | 4 measures required |
| Cost Reporting | CMS 2552-10 | Annual submission |
| Survey Frequency | State-dependent | Every 2-4 years |

---

## Derived Constraints

### Computational Constraints

Solutions must operate within:

```python
class MVCAHICompute:
    """Computational constraints for MV-CAHI compliance."""
    
    # Processing
    max_cpu_cores: int = 4
    max_memory_gb: int = 8
    max_batch_runtime_hours: float = 1.0
    
    # Storage
    max_monthly_growth_gb: float = 1.0
    max_total_storage_gb: float = 200
    
    # Network
    max_bandwidth_mbps: float = 25  # Upload
    max_latency_ms: float = 150
    assume_offline_hours_per_month: float = 10
    
    # Maintenance
    max_monthly_maintenance_hours: float = 4
    assume_it_skill_level: str = "generalist"  # Not specialist
```

### Financial Constraints

ROI must be demonstrated within:

```python
class MVCAHIFinancial:
    """Financial constraints for solution viability."""
    
    max_implementation_cost: int = 50_000  # Total, not annual
    max_annual_operating_cost: int = 10_000
    max_payback_period_months: int = 18
    min_annual_roi: float = 0.20  # 20%
    
    # Hidden costs to include
    include_training_time: bool = True
    include_workflow_disruption: bool = True
    include_it_maintenance: bool = True
```

### Workflow Constraints

Adoption requires:

```python
class MVCAHIWorkflow:
    """Workflow constraints for user adoption."""
    
    max_training_hours_per_user: float = 4
    max_additional_clicks_per_task: int = 2
    max_workflow_time_increase_pct: float = 5  # 5% maximum
    
    # Integration
    require_ehr_integration: bool = False  # Nice-to-have, not required
    accept_manual_data_entry: bool = True
    support_offline_operation: bool = True
```

---

## Validation Protocol

### Solution Viability Checklist

Before proposing any solution, validate against MV-CAHI:

| Category | Checkpoint | Pass Criteria |
|----------|------------|---------------|
| Compute | CPU requirement | ≤ 4 cores |
| Compute | Memory requirement | ≤ 8 GB |
| Compute | Processing time | ≤ 1 hour batch |
| Compute | Offline capability | Functional without connectivity |
| Financial | Implementation cost | ≤ $50K total |
| Financial | Operating cost | ≤ $10K/year |
| Financial | Payback period | ≤ 18 months |
| Workflow | Training time | ≤ 4 hours/user |
| Workflow | Maintenance burden | ≤ 4 hours/month IT |
| Workforce | Specialist required | No |

### Testing Requirements

1. **Synthetic Load Testing**
   - Generate synthetic data matching CAH volumes
   - Verify performance within computational constraints
   - Test graceful degradation under resource pressure

2. **Disconnected Operation**
   - Simulate 25/3 Mbps bandwidth
   - Simulate periodic connectivity loss
   - Verify local functionality

3. **Usability Testing**
   - Test with non-specialist users
   - Measure task completion time
   - Evaluate error rates

---

## Representative Scenarios

### Scenario A: "Heartland Community Hospital"

A representative CAH for baseline testing:

| Attribute | Value |
|-----------|-------|
| Location | Rural Midwest, 45 miles from nearest PPS hospital |
| Beds | 25 licensed, 18 staffed |
| Census | 10 patients average |
| ED Volume | 6,000 visits/year |
| Revenue | $22M annual |
| Margin | +1.2% |
| IT Staff | 1.5 FTE (shared with HIM) |
| EHR | MEDITECH Expanse |
| Broadband | 50/10 Mbps fiber |

### Scenario B: "Pine Ridge Regional"

A stressed CAH at the lower end of viability:

| Attribute | Value |
|-----------|-------|
| Location | Remote mountain, 72 miles from nearest PPS hospital |
| Beds | 25 licensed, 12 staffed |
| Census | 6 patients average |
| ED Volume | 3,500 visits/year |
| Revenue | $14M annual |
| Margin | -3.5% |
| IT Staff | 0.5 FTE (admin wears IT hat) |
| EHR | Legacy vendor, considering switch |
| Broadband | 25/3 Mbps DSL |

### Scenario C: "Valley Health Center"

A thriving CAH at the upper end:

| Attribute | Value |
|-----------|-------|
| Location | Suburban-rural interface, 38 miles from PPS hospital |
| Beds | 25 licensed, 25 staffed |
| Census | 18 patients average |
| ED Volume | 12,000 visits/year |
| Revenue | $32M annual |
| Margin | +4.2% |
| IT Staff | 3 FTE (dedicated) |
| EHR | Epic Community Connect |
| Broadband | 100/50 Mbps fiber |

---

## Data Sources

### Primary Sources

| Source | Data | Access |
|--------|------|--------|
| CMS Cost Reports (2552-10) | Financial, operational | Public |
| HRSA Data Warehouse | Facility characteristics | Public |
| AHA Annual Survey | Detailed hospital data | Licensed |
| Flex Monitoring Team | CAH-specific research | Public |
| HCAHPS | Patient experience | Public |

### Derived Benchmarks

| Metric | 25th %ile | Median | 75th %ile | Source |
|--------|-----------|--------|-----------|--------|
| Operating Margin | -4.2% | +0.5% | +3.8% | CMS 2552-10 |
| Occupancy Rate | 28% | 42% | 58% | CMS 2552-10 |
| FTE per Bed | 3.2 | 4.0 | 5.2 | HRSA |
| ED Visits/Year | 3,800 | 6,200 | 9,500 | HRSA |

---

## Updates and Maintenance

MV-CAHI is reviewed annually to reflect:

- Updated CMS Cost Report data
- Changes in technology availability
- Regulatory modifications
- Feedback from pilot implementations

**Current Version**: 1.0 (December 2025)  
**Next Review**: December 2026

---

## Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [METHODOLOGY.md](METHODOLOGY.md) — Research protocols
- [GLOSSARY.md](GLOSSARY.md) — Terminology reference

---

*Solutions for the median, not the outliers.*
