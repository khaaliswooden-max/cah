"""
Objective functions for CAH optimization.

Mathematical Framework:
- Revenue: R(x) = R_inpatient + R_ED + R_outpatient + R_swing
- Cost: C(x) = C_labor + C_fixed + C_variable
- Profit: Π(x) = R(x) - C(x)
- Margin: M(x) = Π(x) / R(x) — quasi-convex ratio objective
- Quality: Q(x) = Σᵢ wᵢ × qᵢ_normalized(x)

The margin objective requires Charnes-Cooper transformation for
guaranteed global optimality. See solver.py for implementation.
"""

from typing import Dict, Tuple
import numpy as np

try:
    from .models import CAHParameters, QualityBenchmarks
except ImportError:
    from models import CAHParameters, QualityBenchmarks


class CAHObjectiveFunctions:
    """
    Revenue, cost, and quality objective functions.
    
    All functions are grounded in CMS cost report structure and
    evidence-based quality-resource relationships.
    
    Attributes:
        params: Financial and operational parameters
        benchmarks: Quality benchmarks and weights
    """
    
    def __init__(
        self,
        params: CAHParameters = None,
        benchmarks: QualityBenchmarks = None,
    ):
        self.params = params or CAHParameters()
        self.benchmarks = benchmarks or QualityBenchmarks()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REVENUE FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def revenue_inpatient(self, x: np.ndarray) -> float:
        """
        Inpatient revenue from acute care discharges.
        
        R_inpatient = α₁ × CMI × (ADC × 365 / ALOS)
        
        Args:
            x: Decision variable vector
            
        Returns:
            Annual inpatient revenue ($)
        """
        p = self.params
        discharges = (x[4] * 365) / p.alos  # ADC × 365 / ALOS
        return p.alpha_1 * x[7] * discharges  # α₁ × CMI × discharges
    
    def revenue_ed(self, x: np.ndarray) -> float:
        """
        Emergency department revenue.
        
        R_ED = α₂ × ED_visits
        """
        return self.params.alpha_2 * x[5]
    
    def revenue_outpatient(self, x: np.ndarray) -> float:
        """
        Outpatient services revenue.
        
        R_outpatient = α₃ × OP_visits
        """
        return self.params.alpha_3 * x[6]
    
    def revenue_swing(self, x: np.ndarray) -> float:
        """
        Swing bed (skilled nursing) revenue.
        
        R_swing = α₄ × swing_beds × 365 × occupancy
        """
        p = self.params
        return p.alpha_4 * x[1] * 365 * p.swing_occupancy
    
    def revenue(self, x: np.ndarray) -> float:
        """
        Total revenue.
        
        R(x) = R_inpatient + R_ED + R_outpatient + R_swing
        """
        return (
            self.revenue_inpatient(x) +
            self.revenue_ed(x) +
            self.revenue_outpatient(x) +
            self.revenue_swing(x)
        )
    
    def revenue_decomposition(self, x: np.ndarray) -> Dict[str, float]:
        """Get revenue breakdown by service line."""
        return {
            "inpatient": self.revenue_inpatient(x),
            "ed": self.revenue_ed(x),
            "outpatient": self.revenue_outpatient(x),
            "swing": self.revenue_swing(x),
            "total": self.revenue(x),
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COST FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def cost_labor(self, x: np.ndarray) -> float:
        """
        Labor cost (nursing + providers).
        
        C_labor = β₁ × nursing_FTE + β₂ × provider_FTE
        """
        p = self.params
        return p.beta_1 * x[2] + p.beta_2 * x[3]
    
    def cost_fixed(self, x: np.ndarray) -> float:
        """
        Fixed overhead cost.
        
        C_fixed = β₃ (plant, administration, depreciation)
        """
        return self.params.beta_3
    
    def cost_variable(self, x: np.ndarray) -> float:
        """
        Variable cost tied to patient volume.
        
        C_variable = β₄ × ADC × 365
        """
        return self.params.beta_4 * x[4] * 365
    
    def cost(self, x: np.ndarray) -> float:
        """
        Total cost.
        
        C(x) = C_labor + C_fixed + C_variable
        """
        return (
            self.cost_labor(x) +
            self.cost_fixed(x) +
            self.cost_variable(x)
        )
    
    def cost_decomposition(self, x: np.ndarray) -> Dict[str, float]:
        """Get cost breakdown by category."""
        return {
            "labor": self.cost_labor(x),
            "fixed": self.cost_fixed(x),
            "variable": self.cost_variable(x),
            "total": self.cost(x),
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROFIT AND MARGIN
    # ═══════════════════════════════════════════════════════════════════════════
    
    def profit(self, x: np.ndarray) -> float:
        """
        Operating profit.
        
        Π(x) = R(x) - C(x)
        """
        return self.revenue(x) - self.cost(x)
    
    def margin(self, x: np.ndarray) -> float:
        """
        Operating margin (profit/revenue ratio).
        
        M(x) = Π(x) / R(x)
        
        Note: This is a quasi-convex function. For guaranteed global
        optimality, use Charnes-Cooper transformation in solver.
        """
        rev = self.revenue(x)
        if rev <= 0:
            return -1.0  # Infeasible
        return self.profit(x) / rev
    
    # ═══════════════════════════════════════════════════════════════════════════
    # QUALITY FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def quality_scores(self, x: np.ndarray) -> Dict[str, float]:
        """
        Individual quality measure scores based on resource allocation.
        
        Quality-resource linkages are derived from empirical literature:
        - Aiken et al. (2014) LANCET: Nurse staffing and mortality
        - McHugh et al. (2021) JAMA: Nurse-to-patient ratio legislation
        - Needleman et al. (2020) NEJM: Staffing and inpatient mortality
        
        Args:
            x: Decision variable vector
            
        Returns:
            Dictionary mapping measure names to predicted scores
        """
        p = self.params
        
        # Key staffing ratios
        nurse_ratio = x[2] / max(x[4], 1.0)  # Nursing FTE per ADC
        provider_ed_ratio = x[3] / (x[5] / 365)  # Providers per daily ED visits
        
        scores = {}
        
        # ED-2b: Throughput time (minutes) — inversely related to provider coverage
        base_ed_time = 200
        scores["ed_throughput"] = max(60, base_ed_time - 10 * provider_ed_ratio)
        
        # OP-18b: Pain management time — related to overall staffing
        scores["pain_management"] = max(15, 35 - nurse_ratio)
        
        # HCAHPS: Overall rating — strongly correlated with nurse staffing (Aiken 2014)
        base_hcahps = 60
        scores["hcahps_overall"] = min(95, base_hcahps + 3 * nurse_ratio)
        
        # Opioid concurrent prescribing — related to provider oversight
        scores["opioid_concurrent"] = max(1, 8 - 0.5 * x[3])
        
        # 30-day readmission — related to provider FTE and case complexity
        base_readmit = 20
        scores["readmission_30d"] = max(
            8,
            base_readmit + p.provider_readmit_coeff * x[3] * 100 - 2 * nurse_ratio
        )
        
        # Falls with injury — inversely related to nurse staffing (Needleman 2020)
        scores["falls_injury"] = max(0.5, 5 - 0.5 * nurse_ratio)
        
        # CAUTI rate — related to nursing care quality
        scores["cauti_rate"] = max(0.3, 3 - 0.3 * nurse_ratio)
        
        return scores
    
    def normalize_quality_score(
        self,
        measure: str,
        score: float,
    ) -> float:
        """
        Normalize quality score to [0, 1] scale.
        
        Higher normalized values always indicate better quality.
        
        Args:
            measure: Quality measure name
            score: Raw score value
            
        Returns:
            Normalized score in [0, 1]
        """
        b = self.benchmarks
        benchmark = b.benchmarks[measure]
        higher_better = b.direction[measure]
        
        if higher_better:
            # (actual - min) / (benchmark - min)
            min_val = benchmark * 0.5
            normalized = (score - min_val) / (benchmark - min_val)
        else:
            # (max - actual) / (max - benchmark)
            max_val = benchmark * 2.0
            normalized = (max_val - score) / (max_val - benchmark)
        
        return np.clip(normalized, 0.0, 1.0)
    
    def composite_quality(self, x: np.ndarray) -> float:
        """
        Composite quality score as weighted sum of normalized measures.
        
        Q(x) = Σᵢ wᵢ × qᵢ_normalized(x)
        
        Returns:
            Composite score in [0, 1], higher is better
        """
        scores = self.quality_scores(x)
        b = self.benchmarks
        
        total = 0.0
        for measure, score in scores.items():
            weight = b.weights[measure]
            normalized = self.normalize_quality_score(measure, score)
            total += weight * normalized
        
        return total
    
    def check_benchmarks_met(self, x: np.ndarray) -> Tuple[bool, Dict[str, bool]]:
        """
        Check if all quality benchmarks are met.
        
        Returns:
            Tuple of (all_met, individual_status)
        """
        scores = self.quality_scores(x)
        b = self.benchmarks
        
        status = {}
        for measure, score in scores.items():
            benchmark = b.benchmarks[measure]
            higher_better = b.direction[measure]
            
            if higher_better:
                status[measure] = score >= benchmark
            else:
                status[measure] = score <= benchmark
        
        all_met = all(status.values())
        return all_met, status
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GRADIENT COMPUTATION (for SQP)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def revenue_gradient(self, x: np.ndarray) -> np.ndarray:
        """
        Gradient of revenue function ∇R(x).
        
        Computed analytically for efficiency.
        """
        p = self.params
        grad = np.zeros(8)
        
        # ∂R/∂x[0] (acute_beds) = 0 (no direct revenue dependency)
        grad[0] = 0.0
        
        # ∂R/∂x[1] (swing_beds) = α₄ × 365 × occupancy
        grad[1] = p.alpha_4 * 365 * p.swing_occupancy
        
        # ∂R/∂x[2] (nursing_fte) = 0
        grad[2] = 0.0
        
        # ∂R/∂x[3] (provider_fte) = 0
        grad[3] = 0.0
        
        # ∂R/∂x[4] (ADC) = α₁ × CMI × 365 / ALOS
        grad[4] = p.alpha_1 * x[7] * 365 / p.alos
        
        # ∂R/∂x[5] (ED visits) = α₂
        grad[5] = p.alpha_2
        
        # ∂R/∂x[6] (OP visits) = α₃
        grad[6] = p.alpha_3
        
        # ∂R/∂x[7] (CMI) = α₁ × ADC × 365 / ALOS
        grad[7] = p.alpha_1 * x[4] * 365 / p.alos
        
        return grad
    
    def cost_gradient(self, x: np.ndarray) -> np.ndarray:
        """
        Gradient of cost function ∇C(x).
        """
        p = self.params
        grad = np.zeros(8)
        
        # ∂C/∂x[2] (nursing_fte) = β₁
        grad[2] = p.beta_1
        
        # ∂C/∂x[3] (provider_fte) = β₂
        grad[3] = p.beta_2
        
        # ∂C/∂x[4] (ADC) = β₄ × 365
        grad[4] = p.beta_4 * 365
        
        return grad
    
    def profit_gradient(self, x: np.ndarray) -> np.ndarray:
        """Gradient of profit function ∇Π(x) = ∇R(x) - ∇C(x)."""
        return self.revenue_gradient(x) - self.cost_gradient(x)
