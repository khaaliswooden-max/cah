# Hypothesis: ED Utilization and Financial Instability

## Status
◐ PLAUSIBLE — Awaiting formal analysis

## Date
2025-12-28

## Authors
Aldrich K. Wooden

---

## 1. Conjecture

CAHs with higher emergency department utilization ratios experience greater financial instability, as measured by operating margin variance.

**Plain Language**: When a larger share of a CAH's patient encounters come through the emergency department rather than scheduled admissions, the hospital's financial performance becomes less predictable.

---

## 2. Formalization

### Variables

| Symbol | Name | Units | Range | Source |
|--------|------|-------|-------|--------|
| $M$ | Operating Margin | % | [-20, +20] | CMS 2552-10, Line 1 |
| $\sigma_M$ | Margin Volatility | % | [0, 15] | Calculated (3-year std dev) |
| $R_{ED}$ | ED Ratio | ratio | [0, 1] | CMS 2552-10, Worksheet S-3 |
| $V$ | Total Volume | encounters/year | [1000, 20000] | CMS 2552-10 |

### Hypothesis

$$
H_1: \frac{\partial \sigma_M}{\partial R_{ED}} > 0
$$

Higher ED ratio correlates with higher margin volatility.

### Control Variables

- Facility size (bed count)
- Payer mix
- Geographic region
- State Medicaid expansion status

---

## 3. Prior Art Grounding

### Literature Review

| Reference | Finding | Relevance | Confidence |
|-----------|---------|-----------|------------|
| Wishner et al. (2016) | Rural hospital closures associated with high ED dependence | Supports | ◐ |
| Kaufman et al. (2016) | Financial distress indicators in rural hospitals | Context | ✓ |
| GAO-18-634 | CMS payment policies affect CAH financial viability | Context | ✓ |

### Search Strategy

**PubMed Query**:
```
("Critical Access Hospital"[MeSH] OR "rural hospital"[tiab]) 
AND ("emergency department"[tiab] OR "emergency room"[tiab])
AND ("financial"[tiab] OR "margin"[tiab] OR "revenue"[tiab])
```
Results: 47 papers reviewed, 12 directly relevant

**CPC Classification** (if patent-related): N/A — Research hypothesis

---

## 4. Test Design

### Data Source
CMS Hospital Cost Reports (Form 2552-10), 2018-2023

### Sample
- All CAH-designated facilities reporting complete data
- Estimated n ≈ 1,200 per year
- Panel: ~6,000 facility-years

### Methodology

1. **ED Ratio Calculation**:
   $$R_{ED} = \frac{\text{ED Visits}}{\text{ED Visits} + \text{Scheduled Admissions}}$$

2. **Margin Volatility**:
   $$\sigma_M = \text{StdDev}(M_{t}, M_{t-1}, M_{t-2})$$
   Rolling 3-year standard deviation

3. **Model Specification**:
   $$\sigma_{M,i,t} = \alpha + \beta_1 R_{ED,i,t} + \beta_2 X_{i,t} + \gamma_i + \epsilon_{i,t}$$
   
   Where:
   - $\gamma_i$ = facility fixed effects
   - $X_{i,t}$ = control variables

### Validation
- 5-fold cross-validation
- Placebo test with randomized ED ratios
- Sensitivity analysis on outlier exclusion

### MV-CAHI Compliance
- Data: Public CMS cost reports ✓
- Compute: Panel regression, standard laptop ✓
- Generalizability: All CAHs represented ✓

---

## 5. Proof/Disproof

**Status**: Pending

### Expected Outcomes

| Outcome | Interpretation | Confidence Threshold |
|---------|---------------|---------------------|
| $\beta_1 > 0$, p < 0.05 | Hypothesis supported | Strong evidence |
| $\beta_1 > 0$, p ∈ [0.05, 0.10] | Weak support | Suggestive |
| $\beta_1 ≈ 0$ | No relationship | Null |
| $\beta_1 < 0$, p < 0.05 | Hypothesis refuted | Counter-evidence |

### Results

[To be completed after analysis]

---

## 6. Implications

### If Supported

| Domain | Implication | Action |
|--------|-------------|--------|
| Financial Models | Weight ED ratio in volatility predictions | Update financial risk algorithm |
| Interventions | Prioritize scheduled admission capture | Develop referral optimization |
| Policy | Consider ED-specific CAH support | Inform advocacy |

### If Refuted

| Domain | Implication | Action |
|--------|-------------|--------|
| Model Development | Remove ED ratio from volatility model | Simplify financial predictions |
| Research | Investigate alternative volatility drivers | Generate new hypotheses |

---

## Related

- [Financial Model Documentation](../models/financial/README.md)
- [MV-CAHI Specification](../../docs/MV-CAHI.md)

---

## Notes

This hypothesis emerged from qualitative observations during CAH site visits where administrators frequently cited unpredictable ED volumes as a source of financial stress. The mechanism may involve:

1. ED visits have lower margin per encounter than scheduled procedures
2. ED staffing requires fixed overhead regardless of volume
3. ED patients are more likely to be uninsured/underinsured
4. Transfer-out rates are higher for ED-originating cases

Alternative explanations to control for:
- Reverse causality (financial distress → service reduction → ED-only access)
- Confounding with community health status
- Seasonal effects (flu season, tourist areas)
