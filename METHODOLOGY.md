# Research Methodology

## Overview

The CAH Transformation Engine employs a **first-principles research methodology** that grounds all findings in mathematical rigor, empirical evidence, and regulatory reality. This document specifies the protocols for conducting reproducible, auditable research within this framework.

---

## Core Methodology

### First Principles Deconstruction

All research follows a five-step pattern:

1. **Axiom Identification** — Define foundational truths with physical/mathematical basis
2. **Component Decomposition** — Break system into irreducible elements
3. **Relationship Mapping** — Document dependencies and interactions
4. **Uncertainty Quantification** — Mark epistemic confidence levels
5. **Synthesis** — Reconstruct understanding from verified components

### Epistemic Marking Convention

Apply these markers consistently throughout all research outputs:

| Marker | Meaning | Evidentiary Standard |
|--------|---------|---------------------|
| ✓ | VERIFIED | Grounded in CMS data, HRSA reports, peer-reviewed literature, or established mathematics |
| ◐ | PLAUSIBLE | Supported by analogical reasoning from adjacent domains or expert consensus |
| ◯ | SPECULATIVE | Extrapolation requiring validation; theoretical prediction |

---

## Mathematical Foundations

### Constrained Optimization Framework

CAH operations are modeled as continuous optimization problems:

$$
\begin{aligned}
\text{maximize} \quad & f(x) = \sum_{i=1}^{n} w_i \cdot \text{Outcome}_i(x) \\
\text{subject to} \quad & g_1(x) \leq 25 \quad \text{[Bed capacity]} \\
& g_2(x) \leq 96 \quad \text{[Average LOS in hours]} \\
& g_3(x) \geq 35 \quad \text{[Distance requirement in miles]} \\
& g_4(x) \leq B \quad \text{[Budget constraint]} \\
& x \geq 0
\end{aligned}
$$

### Lagrangian Analysis

The Lagrangian function incorporates regulatory constraints:

$$
\mathcal{L}(x, \lambda) = f(x) + \sum_{j=1}^{m} \lambda_j \cdot g_j(x)
$$

Where $\lambda_j$ represents the **shadow price** of constraint $j$—the marginal value of relaxing that constraint by one unit.

### Sensitivity Analysis

Partial derivatives quantify operational sensitivities:

| Derivative | Interpretation |
|------------|----------------|
| $\frac{\partial R}{\partial V}$ | Marginal revenue per additional patient volume |
| $\frac{\partial C}{\partial X}$ | Cost sensitivity to case mix complexity |
| $\frac{\partial O}{\partial I}$ | Clinical outcome response to intervention intensity |

### Cumulative Effects

Integration captures longitudinal impacts:

$$
\text{TotalImpact}(T) = \int_0^T \text{Effect}(t) \cdot \text{Decay}(t) \, dt
$$

Where $\text{Decay}(t)$ models the diminishing relevance of historical effects.

---

## Hypothesis-to-Proof Protocol

All research claims must be structured as:

### 1. Conjecture

Plain-language statement of suspected relationship.

**Example**: "CAHs with higher ED utilization ratios experience greater financial instability."

### 2. Formalization

Mathematical expression with defined variables.

$$
\text{Conjecture}: \quad \frac{\partial \text{Margin}}{\partial \text{EDRatio}} < 0
$$

**Variable Definitions**:

| Variable | Name | Units | Range | Source |
|----------|------|-------|-------|--------|
| Margin | Operating margin | % | [-20, +20] | CMS 2552-10 |
| EDRatio | ED visits / Total encounters | ratio | [0, 1] | CMS 2552-10 |

### 3. Prior Art Grounding

Literature and patent evidence supporting or contradicting the hypothesis.

**Required Elements**:
- CPC Classification (if patent-related)
- Search String (exact query used)
- Key References (ranked by relevance, with confidence markers)

### 4. Test Design

Specific data or simulation that would confirm/refute.

| Element | Specification |
|---------|--------------|
| Data Source | CMS Cost Reports 2018-2023 |
| Sample | All CAH-designated facilities (n ≈ 1,300) |
| Method | Panel regression with facility fixed effects |
| Validation | 5-fold cross-validation |

### 5. Proof/Disproof

Documented outcome with confidence intervals.

**Result Format**:
- Point estimate
- 95% confidence interval
- p-value (where applicable)
- Effect size interpretation
- Limitations and caveats

### 6. Implications

What changes in the model if true/false.

| If True | If False |
|---------|----------|
| Update financial models to weight ED ratio | Remove ED ratio from financial risk factors |
| Prioritize ED efficiency interventions | Investigate alternative financial predictors |

---

## Performance Gap Analysis Protocol

For any CAH metric (financial, clinical, operational, technical):

### Step 1: Baseline State $S_0$

Current measured performance with variance.

```
S₀ = mean(observed values) ± σ
n = sample size
Data Source: [Specify]
Collection Period: [Date range]
```

### Step 2: Target State $S^*$

Evidence-based benchmark or regulatory requirement.

| Target Type | Source | Example |
|-------------|--------|---------|
| Regulatory Minimum | CMS CoP | 24/7 ER coverage |
| Peer Benchmark | HRSA data | 75th percentile performance |
| Evidence-Based | Literature | Meta-analysis optimal |
| Aspirational | Expert consensus | Best-in-class |

### Step 3: Gap Function

$$
G(t) = S^* - S(t)
$$

Decomposed into contributing factors using root cause analysis.

### Step 4: Root Cause Decomposition

Ishikawa (fishbone) diagram or fault tree to atomic causes.

```
Gap in Metric X
├── Category 1: People
│   ├── Staffing levels
│   └── Training gaps
├── Category 2: Process
│   ├── Workflow inefficiency
│   └── Communication breakdowns
├── Category 3: Technology
│   ├── System limitations
│   └── Integration gaps
├── Category 4: External
│   ├── Regulatory constraints
│   └── Payer policies
└── Category 5: Resources
    ├── Budget limitations
    └── Infrastructure constraints
```

### Step 5: Intervention Mapping

Which causes are addressable, at what cost, with what probability.

| Root Cause | Addressable | Intervention | Cost | P(Success) |
|------------|-------------|--------------|------|------------|
| Staffing | Yes | Recruitment program | $X | 0.7 |
| Regulation | No | Advocacy (long-term) | $Y | 0.2 |

### Step 6: Trajectory Modeling

$$
\frac{dS}{dt} = f(\text{Interventions}, \text{Constraints}, \text{Time})
$$

Model state evolution under intervention scenarios.

### Step 7: Time-to-Target

$$
T^* = \int_{S_0}^{S^*} \frac{1}{dS/dt} \, dS
$$

With resource constraints incorporated.

---

## Algorithm Development Standards

All proposed algorithms must specify:

### Input Specification

```python
"""
Data Sources: [List sources available to typical CAH]
    - EHR: [Specific data elements]
    - Claims: [837/835 elements]
    - Cost Reports: [Worksheet references]
    - HCAHPS: [Survey measures]

Input Schema:
    parameter_1: type  # Description, valid range
    parameter_2: type  # Description, valid range
"""
```

### Computational Complexity

Must run on CAH-realistic infrastructure:

| Constraint | MV-CAHI Limit |
|------------|---------------|
| CPU | 2-4 cores |
| RAM | 4-8 GB |
| Processing Time | < 1 hour for daily batch |
| Storage | < 1 GB per month growth |

**Complexity Requirements**:
- Specify Big-O notation
- Provide empirical benchmarks on sample data
- Document memory usage patterns

### Output Specification

```python
"""
Output: [Type and structure]

Actionable Insight:
    Decision Point: [Specific workflow or decision supported]
    Action Trigger: [Threshold or condition]
    Recommended Action: [What to do]

Validation Method:
    [How to verify with limited CAH data volumes]

Failure Modes:
    - [Condition]: [Behavior when this assumption breaks]
    - [Condition]: [Behavior when this assumption breaks]
"""
```

---

## Data Standards

### Variable Definitions

Every model must include a complete variable table:

| Symbol | Name | Units | Range | Source | Update Frequency |
|--------|------|-------|-------|--------|------------------|
| $V$ | Patient volume | patients/month | [50, 500] | EHR | Monthly |
| $M$ | Operating margin | % | [-20, +20] | CMS 2552-10 | Annual |
| $L$ | Average LOS | hours | [0, 96] | EHR | Daily |

### FHIR R4 Mapping

When KPIs involve clinical data:

```yaml
Metric: Emergency Department Length of Stay
FHIR Resource: Encounter
Element Path: Encounter.period
Calculation: period.end - period.start
Filter: Encounter.type.coding.code = "EMER"
Unit: minutes
Aggregation: median
```

### Data Quality Requirements

| Dimension | Minimum Standard | Validation Method |
|-----------|------------------|-------------------|
| Completeness | > 90% | Missing value analysis |
| Accuracy | Source-verified | Reconciliation with financial records |
| Timeliness | < 30 days lag | Timestamp validation |
| Consistency | Cross-system match | Entity resolution |

---

## Documentation Standards

### Mathematical Notation

Use LaTeX for all expressions. Inline: `$expression$`. Block:

```latex
$$
\mathcal{L}(x, \lambda) = f(x) + \sum_{j=1}^{m} \lambda_j g_j(x)
$$
```

### Research Outputs

All findings must be:

1. **Citable** — Reference data sources, search strings, analysis methods
2. **Reproducible** — Provide code, parameters, and data specifications
3. **Auditable** — Document decision trail from hypothesis to conclusion
4. **Versioned** — Track changes to models and findings over time

### Negative Results

Document failed hypotheses with equal rigor:

- What was tested
- Why it failed
- What was learned
- How it narrows the solution space

---

## Quality Assurance

### Pre-Submission Checklist

- [ ] All variables defined with units and ranges
- [ ] Data sources cited
- [ ] Computational complexity specified
- [ ] Validation method documented
- [ ] Failure modes identified
- [ ] MV-CAHI constraints verified
- [ ] Epistemic markers applied
- [ ] Reproducibility confirmed

### Peer Review Criteria

| Criterion | Question |
|-----------|----------|
| Rigor | Is the methodology sound? |
| Applicability | Does it work within CAH constraints? |
| Reproducibility | Can findings be replicated? |
| Impact | Does it address a meaningful gap? |
| Parsimony | Is it the simplest solution that works? |

---

## Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [MV-CAHI.md](MV-CAHI.md) — Reference infrastructure
- [CONTRIBUTING.md](../CONTRIBUTING.md) — How to contribute

---

*Methodology is the difference between knowledge and opinion.*
