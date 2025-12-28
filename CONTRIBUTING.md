# Contributing to the CAH Transformation Engine

Thank you for your interest in contributing to the CAH Transformation Engine. This document provides guidelines for contributing to this computational research environment.

## Table of Contents

1. [Contribution Philosophy](#contribution-philosophy)
2. [Getting Started](#getting-started)
3. [Research Contributions](#research-contributions)
4. [Code Contributions](#code-contributions)
5. [Documentation Standards](#documentation-standards)
6. [Review Process](#review-process)

---

## Contribution Philosophy

This project applies **first-principles methodology** to Critical Access Hospital challenges. All contributions must:

- **Be grounded in evidence** — Every claim requires citation or derivation
- **Be mathematically rigorous** — Models must specify variables, units, constraints
- **Be reproducible** — Findings must be auditable with documented search strings and data sources
- **Address CAH constraints** — Solutions must work within MV-CAHI parameters

### Epistemic Marking Convention

Apply these markers consistently:

| Marker | Meaning | Standard |
|--------|---------|----------|
| ✓ | VERIFIED | Grounded in CMS data, peer-reviewed literature, or established mathematics |
| ◐ | PLAUSIBLE | Supported by analogical reasoning from adjacent domains |
| ◯ | SPECULATIVE | Extrapolation requiring validation |

---

## Getting Started

### Prerequisites

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment:

```bash
git clone https://github.com/YOUR-USERNAME/cah.git
cd cah
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Branch Naming

Use descriptive branch names following this pattern:

```
<type>/<brief-description>

Types:
- research/    New research hypothesis or experiment
- model/       Mathematical model development
- algorithm/   Algorithm implementation
- docs/        Documentation updates
- fix/         Bug fixes or corrections
```

Examples:
- `research/transfer-rate-optimization`
- `model/financial-sensitivity-analysis`
- `docs/mv-cahi-specification`

---

## Research Contributions

### Hypothesis Structure

All research contributions must follow the **Hypothesis-to-Proof Methodology**:

```markdown
## Hypothesis: [Descriptive Title]

### 1. Conjecture
[Plain-language statement of suspected relationship]

### 2. Formalization
```latex
[Mathematical expression with defined variables]
```

### 3. Prior Art Grounding
[Literature/patent evidence supporting or contradicting]
- CPC Classification: [if applicable]
- Search String: [exact query used]
- Key References: [ranked by relevance]

### 4. Test Design
[Specific data or simulation that would confirm/refute]
- Data Sources: [CMS cost reports, HRSA data, etc.]
- Sample Size: [n=]
- Validation Method: [cross-validation approach]

### 5. Proof/Disproof
[Documented outcome with confidence intervals]

### 6. Implications
[What changes in the model if true/false]
```

### Negative Results

Document negative findings with equal rigor. Failed hypotheses narrow the solution space and are valuable contributions.

---

## Code Contributions

### Algorithm Requirements

All proposed algorithms must specify:

```python
"""
Algorithm: [Name]
Purpose: [One sentence]

Input:
    - data_source: str — [Description, must be available to typical CAH]
    - parameters: dict — [Validated ranges]

Output:
    - result: [Type] — [Tied to specific decision or workflow]

Computational Complexity: O(n) / O(n log n) / O(n²)
    [Must run on CAH-realistic infrastructure: 1-2 IT FTE, rural broadband]

Validation Method:
    [How to verify with limited CAH data volumes]

Failure Modes:
    [What happens when assumptions break]
"""
```

### Code Style

- **Python**: Follow PEP 8, use Ruff for linting
- **Type Hints**: Required for all function signatures
- **Docstrings**: Google style, include examples
- **Tests**: Minimum 80% coverage for new code

```python
def calculate_gap_function(
    baseline: float,
    target: float,
    current: float,
    time: float
) -> GapResult:
    """
    Calculate the performance gap trajectory.
    
    Args:
        baseline: Initial measured performance S₀
        target: Evidence-based benchmark S*
        current: Current performance S(t)
        time: Time since baseline measurement
    
    Returns:
        GapResult containing gap magnitude, rate of change, and time-to-target
    
    Example:
        >>> result = calculate_gap_function(0.75, 0.95, 0.82, 6.0)
        >>> result.gap_magnitude
        0.13
    """
```

### Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=models --cov=algorithms --cov-report=term-missing

# Run specific test file
pytest tests/test_financial_models.py -v
```

---

## Documentation Standards

### Mathematical Notation

Use LaTeX for all mathematical expressions. Inline: `$expression$`. Block:

```latex
$$
\mathcal{L}(x, \lambda) = f(x) + \sum_{i=1}^{m} \lambda_i g_i(x)
$$
```

### Variable Definitions

Every model must include a variable table:

| Symbol | Name | Units | Range | Source |
|--------|------|-------|-------|--------|
| $S_0$ | Baseline State | ratio | [0, 1] | CMS Cost Report |
| $S^*$ | Target State | ratio | [0, 1] | HRSA benchmark |
| $\lambda$ | Bed Capacity Multiplier | $/bed | ≥ 0 | Optimization result |

### FHIR R4 Mapping

When KPIs involve clinical data, include FHIR R4 element mapping:

```yaml
Metric: Emergency Department Wait Time
FHIR Resource: Encounter
Element Path: Encounter.period.start
Calculation: period.end - period.start
Unit: minutes
```

---

## Review Process

### Pull Request Checklist

Before submitting:

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New code has ≥80% test coverage
- [ ] Documentation updated
- [ ] Mathematical models include variable definitions
- [ ] Algorithms specify computational complexity
- [ ] Solutions validated against MV-CAHI constraints
- [ ] Epistemic markers applied where appropriate

### Review Criteria

Reviewers will evaluate:

1. **Scientific Rigor** — Is the methodology sound?
2. **CAH Applicability** — Does it work within MV-CAHI constraints?
3. **Reproducibility** — Can findings be replicated?
4. **Documentation** — Is the contribution well-documented?
5. **Code Quality** — Does the implementation meet standards?

### Merge Requirements

- Two approving reviews
- All CI checks pass
- Documentation complete
- No unresolved discussions

---

## Questions?

Contact the maintainer:

**Khaalis Wooden**  
kwooden@visionblox.com

---

*Thank you for contributing to the transformation of rural healthcare.*
