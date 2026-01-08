# Whitepaper Claims Validation Report

**Generated**: 2026-01-08 14:44:56  
**Source Document**: "Reimagining Critical Access Hospitals: A First-Principles Approach to Rural Healthcare Sustainability"  
**Validation Data**: CMS HCRIS 2021-2023, MT/WA CAH Cohort (n=88 facilities)

---

## Executive Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ **Validated** | 3 | 11.5% |
| ⚠️ **Partially Validated** | 5 | 19.2% |
| ❌ **Refuted** | 4 | 15.4% |
| ❓ **Insufficient Data** | 14 | 53.8% |
| **Total Claims Reviewed** | 26 | 100% |

**Validation Rate**: 30.8% of claims validated or partially validated

---

## Key Findings

### Operating Margin Claims

**CLAIM-001**: Operating margins for CAHs are thin (0.3-3.1%)
- **Actual Value**: Mean: 32.31%, Median: 35.70%, Range: [-30.54%, 70.98%]
- **Status**: PARTIALLY_VALIDATED
- **Variance**: Range overlaps but median 35.70% outside expected range
- **Notes**: n=86 facilities (2023 data)

**CLAIM-002**: 44-48% of CAHs operate at a loss
- **Actual Value**: 2.3% (2 of 86 facilities)
- **Status**: REFUTED
- **Variance**: Actual 2.3% is LOWER than expected range (better performance)
- **Notes**: At-loss defined as Operating_Margin < 0, n=86 (2023)

**CLAIM-003**: Non-micropolitan CAH average margin is 1.8%
- **Actual Value**: Mean: 32.31%, Median: 35.70%, Range: [-30.54%, 70.98%]
- **Status**: REFUTED
- **Variance**: Actual mean 32.31% vs expected 1.80% (diff: 30.51%)
- **Notes**: n=86 facilities (2023 data)

---

## Detailed Validation Results

### ✅ Validated Claims

| Claim ID | Claim | Actual Value | Notes |
|----------|-------|--------------|-------|
| CLAIM-008 | Influenza immunization rates (IMM-2) vary significantly acro... | Std Dev: 20.6, CV: 0.35 | n=83 facilities |
| CLAIM-025 | Montana has approximately 50 CAHs | 49 unique Montana CAHs in 2023 data | Based on Provider_Num unique count in ca... |
| CLAIM-026 | Washington has approximately 39 CAHs | 39 unique Washington CAHs in 2023 data | Based on Provider_Num unique count in ca... |

### ⚠️ Partially Validated Claims

| Claim ID | Claim | Actual Value | Variance |
|----------|-------|--------------|----------|
| CLAIM-001 | Operating margins for CAHs are thin (0.3-3.1%) | Mean: 32.31%, Median: 35.70%, Range: [-3... | Range overlaps but median 35.70% outside... |
| CLAIM-005 | CAH revenues typically range $15-25M annually | Median: $44,005,435, Mean: $80,340,674 | Median $44,005,435 outside but within 2x... |
| CLAIM-007 | ED throughput times (OP-18) target median 180 minutes | Median: 120.5, Mean: 124.6 | Median 120.5 vs expected 180.0 (diff: 59... |
| CLAIM-011 | Labor costs represent approximately 50-60% of CAH total expe... | Cost ratio median: 0.64 (est. labor ~35%... | Direct labor cost % requires Worksheet A... |
| CLAIM-018 | Top quartile CAHs achieve 4-6% operating margins | Q3 (75th %ile): 46.25%, P90: 54.79% | Top quartile cutoff: 46.25% |

### ❌ Refuted Claims

| Claim ID | Claim | Actual Value | Variance |
|----------|-------|--------------|----------|
| CLAIM-002 | 44-48% of CAHs operate at a loss | 2.3% (2 of 86 facilities) | Actual 2.3% is LOWER than expected range... |
| CLAIM-003 | Non-micropolitan CAH average margin is 1.8% | Mean: 32.31%, Median: 35.70%, Range: [-3... | Actual mean 32.31% vs expected 1.80% (di... |
| CLAIM-010 | CAHs are capped at 25 beds by regulation | Max: 30, Mean: 30 beds | Some facilities exceed 25.0 beds (max ob... |
| CLAIM-019 | Top 20 NRHA CAHs achieve 5-12% operating margins | Top 20 range: [47.1%, 71.0%], Mean: 56.4... | Top 20 range outside expected bounds |

### ❓ Insufficient Data

| Claim ID | Claim | Required Data Source |
|----------|-------|---------------------|
| CLAIM-004 | Heavy payer-mix dependency on Medicare/Medicaid (63-70%) | Claim requires: CMS Cost Report Payer Mix Analysis |
| CLAIM-006 | Rural areas have 10-20% higher mortality for time-sensitive ... | Claim requires: JAMA/Lancet Rural Health Studies |
| CLAIM-009 | Occupancy rates below 50% are common in CAHs | Need Worksheet S-3 data for occupancy calculation ... |
| CLAIM-012 | Rural hospitals face significant staffing shortages | Claim requires: NRHA/AHA Surveys |
| CLAIM-013 | 300+ CAHs are at elevated closure risk nationally | Claim requires: Chartis/Navigant Vulnerable Hospit... |
| CLAIM-014 | 60 million Americans depend on CAHs for healthcare access | Claim requires: Census/HRSA Rural Health Data |
| CLAIM-015 | Surgical services add +1.5% margin per additional inpatient ... | Claim requires: Holmes et al. 2022, PMID: 35357095 |
| CLAIM-016 | +0.9% margin per 10% occupancy increase | Claim requires: Holmes et al. 2022, PMID: 35357095 |
| CLAIM-017 | +0.9% margin per 0.1 CMI increase | Claim requires: Holmes et al. 2022, PMID: 35357095 |
| CLAIM-020 | RHH conversion cost estimated at $15-20M per site | Claim requires: Whitepaper Estimate |
| CLAIM-021 | 96-hour average LOS limit applies to CAH inpatient stays | Claim requires: 42 CFR Â§ 485.620 |
| CLAIM-022 | 35-mile distance criterion for CAH designation | Claim requires: 42 CFR Â§ 485.610 |
| CLAIM-023 | 42% of rural areas have broadband speeds under 100 Mbps | Claim requires: FCC Broadband Data |
| CLAIM-024 | CAHs typically have 1-2 IT FTE capacity | Claim requires: HIMSS Rural IT Survey |

---

## Methodology

### Data Sources
1. **CMS HCRIS 2021-2023**: Cost report data from Form CMS-2552-10
2. **Benchmark Citations Database**: Generated from cah_composite_baseline.csv
3. **CMS Hospital Compare**: Quality measures (MBQIP domains)

### Peer Group Definition
- **States**: Montana (MT), Washington (WA)
- **Facility Type**: Critical Access Hospitals (CAH)
- **Ownership**: All ownership types (nonprofit, government, physician)
- **Time Period**: FY 2021-2023

### Validation Criteria
- **VALIDATED**: Actual value within expected range/threshold (±20%)
- **PARTIALLY_VALIDATED**: Actual value within extended tolerance (±50%) or overlapping ranges
- **REFUTED**: Actual value significantly outside expected range
- **INSUFFICIENT_DATA**: Required data not available in current dataset

### Limitations
1. MT/WA cohort may not be representative of national CAH population
2. Some metrics require worksheets not included in baseline dataset
3. Quality measure coverage varies significantly across facilities

---

## Recommendations

### High-Priority Data Gaps to Address
1. **Occupancy Rate**: Requires Worksheet S-3 patient days data
2. **Labor Cost %**: Requires Worksheet A salary/wage breakdown
3. **Payer Mix**: Requires Worksheet E-1 or S-10 payer data

### Claims Requiring Additional Validation
- CLAIM-004: Claim requires: CMS Cost Report Payer Mix Analysis
- CLAIM-006: Claim requires: JAMA/Lancet Rural Health Studies
- CLAIM-009: Need Worksheet S-3 data for occupancy calculation (patient days / bed days available)
- CLAIM-012: Claim requires: NRHA/AHA Surveys
- CLAIM-013: Claim requires: Chartis/Navigant Vulnerable Hospital Index

---

## Appendix: Complete Validation Details


### 1. CLAIM-001: Operating margins for CAHs are thin (0.3-3.1%)

| Field | Value |
|-------|-------|
| **Actual Value** | Mean: 32.31%, Median: 35.70%, Range: [-30.54%, 70.98%] |
| **Variance** | Range overlaps but median 35.70% outside expected range |
| **Status** | PARTIALLY_VALIDATED |
| **Notes** | n=86 facilities (2023 data) |


### 2. CLAIM-002: 44-48% of CAHs operate at a loss

| Field | Value |
|-------|-------|
| **Actual Value** | 2.3% (2 of 86 facilities) |
| **Variance** | Actual 2.3% is LOWER than expected range (better performance) |
| **Status** | REFUTED |
| **Notes** | At-loss defined as Operating_Margin < 0, n=86 (2023) |


### 3. CLAIM-003: Non-micropolitan CAH average margin is 1.8%

| Field | Value |
|-------|-------|
| **Actual Value** | Mean: 32.31%, Median: 35.70%, Range: [-30.54%, 70.98%] |
| **Variance** | Actual mean 32.31% vs expected 1.80% (diff: 30.51%) |
| **Status** | REFUTED |
| **Notes** | n=86 facilities (2023 data) |


### 4. CLAIM-004: Heavy payer-mix dependency on Medicare/Medicaid (63-70%)

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: CMS Cost Report Payer Mix Analysis |


### 5. CLAIM-005: CAH revenues typically range $15-25M annually

| Field | Value |
|-------|-------|
| **Actual Value** | Median: $44,005,435, Mean: $80,340,674 |
| **Variance** | Median $44,005,435 outside but within 2x of range |
| **Status** | PARTIALLY_VALIDATED |
| **Notes** | n=86 facilities, MT/WA cohort includes larger CAHs |


### 6. CLAIM-006: Rural areas have 10-20% higher mortality for time-sensitive conditions

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: JAMA/Lancet Rural Health Studies |


### 7. CLAIM-007: ED throughput times (OP-18) target median 180 minutes

| Field | Value |
|-------|-------|
| **Actual Value** | Median: 120.5, Mean: 124.6 |
| **Variance** | Median 120.5 vs expected 180.0 (diff: 59.5) |
| **Status** | PARTIALLY_VALIDATED |
| **Notes** | n=70 facilities (79.5% coverage) |


### 8. CLAIM-008: Influenza immunization rates (IMM-2) vary significantly across CAHs

| Field | Value |
|-------|-------|
| **Actual Value** | Std Dev: 20.6, CV: 0.35 |
| **Variance** | CV = 0.35 indicates high variance |
| **Status** | VALIDATED |
| **Notes** | n=83 facilities |


### 9. CLAIM-009: Occupancy rates below 50% are common in CAHs

| Field | Value |
|-------|-------|
| **Actual Value** | Cannot calculate directly |
| **Variance** | Occupancy requires patient days data not in current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Need Worksheet S-3 data for occupancy calculation (patient days / bed days available) |


### 10. CLAIM-010: CAHs are capped at 25 beds by regulation

| Field | Value |
|-------|-------|
| **Actual Value** | Max: 30, Mean: 30 beds |
| **Variance** | Some facilities exceed 25.0 beds (max observed: 30.0) |
| **Status** | REFUTED |
| **Notes** | n=88 facilities |


### 11. CLAIM-011: Labor costs represent approximately 50-60% of CAH total expenses

| Field | Value |
|-------|-------|
| **Actual Value** | Cost ratio median: 0.64 (est. labor ~35%) |
| **Variance** | Direct labor cost % requires Worksheet A salary data |
| **Status** | PARTIALLY_VALIDATED |
| **Notes** | Indirect validation - need salary data from WS A Column 1 for exact labor % |


### 12. CLAIM-012: Rural hospitals face significant staffing shortages

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: NRHA/AHA Surveys |


### 13. CLAIM-013: 300+ CAHs are at elevated closure risk nationally

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: Chartis/Navigant Vulnerable Hospital Index |


### 14. CLAIM-014: 60 million Americans depend on CAHs for healthcare access

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: Census/HRSA Rural Health Data |


### 15. CLAIM-015: Surgical services add +1.5% margin per additional inpatient service

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: Holmes et al. 2022, PMID: 35357095 |


### 16. CLAIM-016: +0.9% margin per 10% occupancy increase

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: Holmes et al. 2022, PMID: 35357095 |


### 17. CLAIM-017: +0.9% margin per 0.1 CMI increase

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: Holmes et al. 2022, PMID: 35357095 |


### 18. CLAIM-018: Top quartile CAHs achieve 4-6% operating margins

| Field | Value |
|-------|-------|
| **Actual Value** | Q3 (75th %ile): 46.25%, P90: 54.79% |
| **Variance** | Top quartile cutoff: 46.25% |
| **Status** | PARTIALLY_VALIDATED |
| **Notes** | n=86 facilities |


### 19. CLAIM-019: Top 20 NRHA CAHs achieve 5-12% operating margins

| Field | Value |
|-------|-------|
| **Actual Value** | Top 20 range: [47.1%, 71.0%], Mean: 56.4% |
| **Variance** | Top 20 range outside expected bounds |
| **Status** | REFUTED |
| **Notes** | Top 20 of n=86 facilities |


### 20. CLAIM-020: RHH conversion cost estimated at $15-20M per site

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: Whitepaper Estimate |


### 21. CLAIM-021: 96-hour average LOS limit applies to CAH inpatient stays

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: 42 CFR Â§ 485.620 |


### 22. CLAIM-022: 35-mile distance criterion for CAH designation

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: 42 CFR Â§ 485.610 |


### 23. CLAIM-023: 42% of rural areas have broadband speeds under 100 Mbps

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: FCC Broadband Data |


### 24. CLAIM-024: CAHs typically have 1-2 IT FTE capacity

| Field | Value |
|-------|-------|
| **Actual Value** | External data required |
| **Variance** | Cannot validate with current dataset |
| **Status** | INSUFFICIENT_DATA |
| **Notes** | Claim requires: HIMSS Rural IT Survey |


### 25. CLAIM-025: Montana has approximately 50 CAHs

| Field | Value |
|-------|-------|
| **Actual Value** | 49 unique Montana CAHs in 2023 data |
| **Variance** | Found 49 vs expected ~50 |
| **Status** | VALIDATED |
| **Notes** | Based on Provider_Num unique count in cah_composite_baseline.csv |


### 26. CLAIM-026: Washington has approximately 39 CAHs

| Field | Value |
|-------|-------|
| **Actual Value** | 39 unique Washington CAHs in 2023 data |
| **Variance** | Found 39 vs expected ~39 |
| **Status** | VALIDATED |
| **Notes** | Based on Provider_Num unique count in cah_composite_baseline.csv |


---

*Report generated by CAH Transformation Engine Validation Pipeline*  
*Phase 1 Empirical Validation - Week 2*
