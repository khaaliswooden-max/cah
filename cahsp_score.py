"""
CAHSP Composite Scoring Module.

Implements the CAHSP index formula:
    CAHSP(i, t) = 100 × Σⱼ [wⱼ × φⱼ(Δsⱼ(i,t))]

Weights:
    FI (Financial Index):          0.30
    QI (Clinical Quality Index):   0.30
    OI (Operational Efficiency):   0.20
    WI (Workforce Index):          0.10
    CI (Confidence Index):         0.10

The dual mandate requires BOTH FI ≥ 0.50 AND QI ≥ 0.50 before a
solution can be designated "Solved" (CAHSP ≥ 85).

CAHSP-C (Confidence Index) is the equivalent of AlphaFold's pLDDT score:
knowing where the solution is uncertain is as important as the prediction.

Reference: CAHSP v1.0 — Visionblox LLC · Zuup Innovation Lab
           visionblox.org/cahsp
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np

try:
    from .models import CAHParameters, QualityBenchmarks, OptimizationResult
    from .objectives import CAHObjectiveFunctions
    from .constraints import CAHConstraints
except ImportError:
    from models import CAHParameters, QualityBenchmarks, OptimizationResult
    from objectives import CAHObjectiveFunctions
    from constraints import CAHConstraints


# ─── Weights (must sum to 1.0) ────────────────────────────────────────────────

CAHSP_WEIGHTS: Dict[str, float] = {
    "fi": 0.30,  # Financial Index
    "qi": 0.30,  # Clinical Quality Index
    "oi": 0.20,  # Operational Efficiency Index
    "wi": 0.10,  # Workforce Index
    "ci": 0.10,  # Confidence Index (CAHSP-C)
}

assert abs(sum(CAHSP_WEIGHTS.values()) - 1.0) < 1e-9, "CAHSP weights must sum to 1.0"

# "Benchmark solved" threshold: CAHSP ≥ 85 on Type B targets, 24-month hold
BENCHMARK_THRESHOLD: float = 85.0

# Dual mandate floors — both FI and QI must clear these
FI_FLOOR: float = 0.50
QI_FLOOR: float = 0.50

SCORE_BANDS = [
    (90.0, 100.01, "Elite"),
    (85.0,  90.0,  "Solved"),
    (70.0,  85.0,  "High"),
    (50.0,  70.0,  "Moderate"),
    (0.0,   50.0,  "Developing"),
]


# ─── Component scorers ────────────────────────────────────────────────────────

def compute_fi(
    x: np.ndarray,
    params: CAHParameters,
    objectives: CAHObjectiveFunctions,
) -> float:
    """
    Financial Index (FI) — weight 0.30.

    Three equally-weighted sub-components:
      1. Operating margin: normalized [−5%, +10%] → [0, 1]
         Source: CMS HCRIS; sector baseline −2.3%, target ≥ +0.5%
      2. Labor-to-revenue ratio: normalized [65%, 45%] → [0, 1]
         Source: Flex Monitoring Team; baseline 58.2%, target 52.0%
      3. Revenue diversification: non-inpatient revenue fraction
         Higher ED + OP share = more resilient revenue base

    Returns:
        fi in [0, 1], higher is better
    """
    rev = objectives.revenue(x)
    if rev <= 0:
        return 0.0

    # 1. Operating margin (−5% → 0.0, +10% → 1.0)
    margin = objectives.margin(x)
    fi_margin = float(np.clip((margin + 0.05) / 0.15, 0.0, 1.0))

    # 2. Labor-to-revenue ratio (65% → 0.0, 45% → 1.0, lower is better)
    labor_ratio = objectives.cost_labor(x) / rev
    fi_labor = float(np.clip((0.65 - labor_ratio) / 0.20, 0.0, 1.0))

    # 3. Revenue diversification (ED + OP as share of total; higher = better)
    non_ip = objectives.revenue_ed(x) + objectives.revenue_outpatient(x)
    fi_diversification = float(np.clip(non_ip / rev, 0.0, 1.0))

    return (fi_margin + fi_labor + fi_diversification) / 3.0


def compute_qi(
    x: np.ndarray,
    objectives: CAHObjectiveFunctions,
) -> float:
    """
    Clinical Quality Index (QI) — weight 0.30.

    Uses the MBQIP composite quality score from objectives.py:
        Q(x) = Σᵢ wᵢ × qᵢ_normalized(x)
    across 7 evidence-based measures:
        ED throughput, pain management, HCAHPS overall rating,
        opioid concurrent prescribing, 30-day readmission,
        falls with injury, CAUTI rate.

    Literature: Aiken (2014), McHugh (2021), Needleman (2020)

    Returns:
        qi in [0, 1], higher is better
    """
    return float(objectives.composite_quality(x))


def compute_oi(
    x: np.ndarray,
    params: CAHParameters,
    objectives: CAHObjectiveFunctions,
) -> float:
    """
    Operational Efficiency Index (OI) — weight 0.20.

    Three equally-weighted sub-components:
      1. Bed occupancy: optimal band 70–85% of acute capacity
         (Score peaks at 77.5%, midpoint; tapers off on either side)
      2. ED throughput: from quality_scores() (minutes; lower = higher score)
         Normalized: 300 min → 0.0, 60 min → 1.0
      3. Outpatient density: OP visits per acute bed
         Target ≥ 1500 OP visits per bed per year (MV-CAHI benchmark)

    Returns:
        oi in [0, 1], higher is better
    """
    acute_beds = max(x[0], 1.0)
    adc = x[4]

    # 1. Occupancy (peaks at 77.5%, optimal band center)
    occupancy = adc / acute_beds
    oi_occupancy = float(max(0.0, 1.0 - abs(occupancy - 0.775) / 0.225))

    # 2. ED throughput (lower minutes = higher score)
    q_scores = objectives.quality_scores(x)
    ed_minutes = q_scores.get("ed_throughput", 200.0)
    oi_ed = float(np.clip((300.0 - ed_minutes) / 240.0, 0.0, 1.0))

    # 3. Outpatient density (OP visits per bed; 1500/bed = full credit)
    op_density = x[6] / acute_beds
    oi_op = float(np.clip(op_density / 1500.0, 0.0, 1.0))

    return (oi_occupancy + oi_ed + oi_op) / 3.0


def compute_wi(x: np.ndarray) -> float:
    """
    Workforce Index (WI) — weight 0.10.

    Two equally-weighted sub-components derived from staffing ratios.
    Detailed workforce modeling (travel nurse dependency, tele-specialist
    coverage, burn-out index, pipeline adequacy) is in workforce.py.

      1. Nursing adequacy: nursing_FTE / ADC vs. 0.5 minimum (Aiken 2014)
         Scores 0 at minimum, full credit at 2× minimum (1.0 ratio)
      2. Provider coverage: 1 − (ED visits / provider FTE) / 5000 ceiling
         Scores 0 at ACEP ceiling, full credit at half ceiling

    Returns:
        wi in [0, 1], higher is better
    """
    adc = max(x[4], 1.0)

    # 1. Nursing adequacy (above 0.5 minimum, up to 1.0 ratio)
    nurse_ratio = x[2] / adc
    wi_nurse = float(np.clip((nurse_ratio - 0.5) / 0.5, 0.0, 1.0))

    # 2. Provider workload (lower visits per FTE = better coverage quality)
    ed_per_provider = x[5] / max(x[3], 0.01)
    wi_provider = float(np.clip((5000.0 - ed_per_provider) / 2500.0, 0.0, 1.0))

    return (wi_nurse + wi_provider) / 2.0


def compute_ci(monte_carlo_result: Optional[Dict]) -> float:
    """
    Confidence Index (CI) — weight 0.10.

    CAHSP-C: the equivalent of AlphaFold's pLDDT residue-level confidence.
    A solution's CI score answers: "How confident are we that the predicted
    financial impact will materialize within ±15% of the actual result?"

    Two equally-weighted sub-components:
      1. P(margin ≥ 5% target) from Monte Carlo simulation
         Source: solver.py:monte_carlo_analysis() → margin.p_target_achieved
      2. Predictability: 1 − coefficient of variation of margin distribution
         Lower variance relative to mean = more predictable = more confident

    If no Monte Carlo result provided, returns 0.5 (conservative default).
    Run CAHOptimizer.monte_carlo_analysis() first for a meaningful CI.

    Returns:
        ci in [0, 1], higher is better (more confident)
    """
    if monte_carlo_result is None:
        return 0.5  # Conservative: unknown confidence

    margin_mc = monte_carlo_result.get("margin", {})

    # 1. Probability of achieving 5% margin target
    p_target = float(margin_mc.get("p_target_achieved", 0.5))

    # 2. Predictability via coefficient of variation
    mean_margin = abs(float(margin_mc.get("mean", 0.01)))
    std_margin = float(margin_mc.get("std", 0.05))
    if mean_margin > 1e-8:
        cv = std_margin / mean_margin
        ci_predictability = float(np.clip(1.0 - cv, 0.0, 1.0))
    else:
        ci_predictability = 0.0

    return (p_target + ci_predictability) / 2.0


# ─── Result container ─────────────────────────────────────────────────────────

@dataclass
class CAHSPResult:
    """
    Complete CAHSP scoring result.

    The dual mandate requires BOTH fi >= FI_FLOOR (0.50) AND qi >= QI_FLOOR (0.50)
    before a solution can be considered "Solved" regardless of total score.
    This mirrors CASP's requirement that GDT_TS must be achieved on the
    correct structural class — a high score on the wrong problem doesn't count.
    """

    total: float             # Composite score [0, 100]
    band: str                # "Elite" | "Solved" | "High" | "Moderate" | "Developing"
    fi: float                # Financial Index [0, 1]
    qi: float                # Clinical Quality Index [0, 1]
    oi: float                # Operational Efficiency Index [0, 1]
    wi: float                # Workforce Index [0, 1]
    ci: float                # Confidence Index [0, 1] (CAHSP-C)
    weights: Dict[str, float]
    dual_mandate_met: bool   # FI ≥ 0.50 AND QI ≥ 0.50

    def to_dict(self) -> Dict:
        """Export as JSON-serializable dict."""
        return {
            "cahsp_score": round(self.total, 2),
            "band": self.band,
            "benchmark_threshold": BENCHMARK_THRESHOLD,
            "benchmark_solved": self.total >= BENCHMARK_THRESHOLD and self.dual_mandate_met,
            "components": {
                "fi": round(self.fi, 4),
                "qi": round(self.qi, 4),
                "oi": round(self.oi, 4),
                "wi": round(self.wi, 4),
                "ci": round(self.ci, 4),
            },
            "weights": self.weights,
            "dual_mandate_met": self.dual_mandate_met,
            "floors": {"fi_floor": FI_FLOOR, "qi_floor": QI_FLOOR},
        }

    def __str__(self) -> str:
        solved = self.total >= BENCHMARK_THRESHOLD and self.dual_mandate_met
        lines = [
            f"CAHSP Score: {self.total:.1f} / 100  [{self.band}]{'  *** BENCHMARK SOLVED ***' if solved else ''}",
            f"  FI (Financial):   {self.fi:.3f} × 0.30  {'[OK]' if self.fi >= FI_FLOOR else '[BELOW FLOOR]'}",
            f"  QI (Quality):     {self.qi:.3f} × 0.30  {'[OK]' if self.qi >= QI_FLOOR else '[BELOW FLOOR]'}",
            f"  OI (Operations):  {self.oi:.3f} × 0.20",
            f"  WI (Workforce):   {self.wi:.3f} × 0.10",
            f"  CI (Confidence):  {self.ci:.3f} × 0.10",
            f"  Dual mandate (FI≥{FI_FLOOR} AND QI≥{QI_FLOOR}): {self.dual_mandate_met}",
        ]
        return "\n".join(lines)


# ─── Public API ───────────────────────────────────────────────────────────────

def score_band(score: float) -> str:
    """Map a CAHSP total score to its difficulty band label."""
    for lo, hi, label in SCORE_BANDS:
        if lo <= score < hi:
            return label
    return "Developing"


def cahsp_score(
    result: OptimizationResult,
    params: Optional[CAHParameters] = None,
    benchmarks: Optional[QualityBenchmarks] = None,
    monte_carlo_result: Optional[Dict] = None,
) -> CAHSPResult:
    """
    Compute the CAHSP composite index from a solved OptimizationResult.

    Formula:
        CAHSP(i, t) = 100 × [0.30·FI + 0.30·QI + 0.20·OI + 0.10·WI + 0.10·CI]

    Run CAHOptimizer.monte_carlo_analysis() before calling this to get a
    meaningful CI score (otherwise CI defaults to 0.50).

    Args:
        result:             Solved OptimizationResult from CAHOptimizer.optimize()
        params:             CAHParameters (default: standard CAH)
        benchmarks:         QualityBenchmarks (default: MBQIP 2024)
        monte_carlo_result: Output of CAHOptimizer.monte_carlo_analysis()

    Returns:
        CAHSPResult with total score, band, and full component breakdown

    Example:
        >>> optimizer = CAHOptimizer(theta=0.6)
        >>> result = optimizer.optimize()
        >>> mc = optimizer.monte_carlo_analysis(result.x)
        >>> score = cahsp_score(result, monte_carlo_result=mc)
        >>> print(score)
        CAHSP Score: 74.3 / 100  [High]
          FI (Financial):   0.612 × 0.30  [OK]
          QI (Quality):     0.783 × 0.30  [OK]
          OI (Operations):  0.541 × 0.20
          WI (Workforce):   0.448 × 0.10
          CI (Confidence):  0.821 × 0.10
          Dual mandate (FI≥0.50 AND QI≥0.50): True
    """
    params = params or CAHParameters()
    benchmarks = benchmarks or QualityBenchmarks()

    objectives = CAHObjectiveFunctions(params, benchmarks)
    x = result.x

    fi = compute_fi(x, params, objectives)
    qi = compute_qi(x, objectives)
    oi = compute_oi(x, params, objectives)
    wi = compute_wi(x)
    ci = compute_ci(monte_carlo_result)

    w = CAHSP_WEIGHTS
    raw = (
        w["fi"] * fi +
        w["qi"] * qi +
        w["oi"] * oi +
        w["wi"] * wi +
        w["ci"] * ci
    )
    total = float(np.clip(raw * 100.0, 0.0, 100.0))

    return CAHSPResult(
        total=total,
        band=score_band(total),
        fi=fi,
        qi=qi,
        oi=oi,
        wi=wi,
        ci=ci,
        weights=dict(w),
        dual_mandate_met=(fi >= FI_FLOOR and qi >= QI_FLOOR),
    )
