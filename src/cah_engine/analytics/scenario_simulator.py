"""
Scenario Simulator

Monte Carlo simulation for decision support under uncertainty.
Designed for MV-CAHI compliance with efficient computation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
import math

import numpy as np
from numpy.typing import NDArray

from cah_engine.core.models import SimulationResult, StaffMember


@dataclass
class SimulationConfig:
    """Configuration for Monte Carlo simulation."""
    
    n_iterations: int = 10000
    random_seed: Optional[int] = 42
    confidence_level: float = 0.90
    
    # Parameter distributions (mean, std)
    volume_elasticity: tuple[float, float] = (0.1, 0.03)
    productivity_gain: tuple[float, float] = (0.05, 0.02)
    quality_impact: tuple[float, float] = (0.05, 0.02)
    cost_variability: tuple[float, float] = (1.0, 0.05)
    
    def __post_init__(self):
        # Validate
        if self.n_iterations < 100:
            raise ValueError("n_iterations must be at least 100")
        if not 0.5 <= self.confidence_level <= 0.99:
            raise ValueError("confidence_level must be between 0.5 and 0.99")


@dataclass
class FacilityContext:
    """Context information for simulations."""
    
    baseline_volume: int = 500  # Annual discharges
    revenue_per_encounter: float = 15000.0
    quality_incentive_pool: float = 50000.0
    current_margin: float = 0.0
    staffed_beds: int = 25
    average_daily_census: float = 10.0
    
    # Staffing context
    avg_hourly_wage: float = 30.0
    benefits_multiplier: float = 1.3
    fte_count: float = 100.0


@dataclass
class ScenarioResult:
    """Result from a scenario simulation."""
    
    scenario_name: str
    simulation_result: SimulationResult
    decision_metrics: dict[str, float] = field(default_factory=dict)
    risk_metrics: dict[str, float] = field(default_factory=dict)
    recommendation: str = ""
    confidence: float = 0.0
    
    @property
    def expected_value(self) -> float:
        """Expected value from simulation."""
        return self.simulation_result.mean
    
    @property
    def value_at_risk_5(self) -> float:
        """5th percentile (worst case in 90% CI)."""
        return self.simulation_result.p5
    
    @property
    def probability_of_success(self) -> float:
        """Probability of positive outcome."""
        return self.simulation_result.prob_positive


class ScenarioSimulator:
    """
    Monte Carlo scenario analysis for CAH decisions.
    
    Simulation Framework:
    Outcome_n = f(X_n, θ, ε_n)
    
    Where:
    - X_n = Random draw from input distributions
    - θ = Fixed parameters (policy choices)
    - ε_n = Random noise term
    - n = Simulation iteration
    """
    
    def __init__(
        self,
        facility: FacilityContext,
        config: Optional[SimulationConfig] = None,
    ):
        self.facility = facility
        self.config = config or SimulationConfig()
        self.rng = np.random.default_rng(seed=self.config.random_seed)
    
    def simulate_staffing_change(
        self,
        fte_change: float,
        labor_cost_per_fte: float = 65000,
    ) -> ScenarioResult:
        """
        Simulate financial impact of staffing change.
        
        Args:
            fte_change: Change in FTE (positive = add staff, negative = reduce)
            labor_cost_per_fte: Annual labor cost per FTE (including benefits)
            
        Returns:
            ScenarioResult with financial projections
        """
        results = []
        
        for _ in range(self.config.n_iterations):
            # Sample uncertain parameters
            volume_elasticity = self.rng.normal(*self.config.volume_elasticity)
            productivity_gain = self.rng.uniform(0.02, 0.08)
            quality_impact = self.rng.normal(*self.config.quality_impact)
            
            # Calculate effects
            volume_change = fte_change * volume_elasticity * self.facility.baseline_volume
            revenue_change = volume_change * self.facility.revenue_per_encounter
            
            # Cost change with productivity adjustment
            cost_change = fte_change * labor_cost_per_fte * (1 - productivity_gain)
            
            # Quality incentive impact
            quality_revenue = quality_impact * self.facility.quality_incentive_pool
            
            # Net impact
            net_impact = revenue_change - cost_change + quality_revenue
            results.append(net_impact)
        
        results_array = np.array(results)
        
        sim_result = SimulationResult(
            mean=float(np.mean(results_array)),
            median=float(np.median(results_array)),
            std=float(np.std(results_array)),
            p5=float(np.percentile(results_array, 5)),
            p95=float(np.percentile(results_array, 95)),
            prob_positive=float(np.mean(results_array > 0)),
        )
        
        # Decision metrics
        decision_metrics = {
            "expected_annual_impact": sim_result.mean,
            "breakeven_probability": sim_result.prob_positive,
            "downside_risk": abs(sim_result.p5) if sim_result.p5 < 0 else 0,
            "upside_potential": sim_result.p95,
        }
        
        # Risk metrics
        risk_metrics = {
            "coefficient_of_variation": sim_result.std / abs(sim_result.mean) if sim_result.mean != 0 else float('inf'),
            "sharpe_ratio": sim_result.mean / sim_result.std if sim_result.std > 0 else 0,
        }
        
        # Generate recommendation
        if sim_result.prob_positive > 0.7 and sim_result.mean > 0:
            recommendation = "FAVORABLE: High probability of positive return"
        elif sim_result.prob_positive > 0.5:
            recommendation = "MARGINAL: Moderate probability of positive return"
        else:
            recommendation = "UNFAVORABLE: Low probability of positive return"
        
        return ScenarioResult(
            scenario_name=f"Staffing Change: {fte_change:+.1f} FTE",
            simulation_result=sim_result,
            decision_metrics=decision_metrics,
            risk_metrics=risk_metrics,
            recommendation=recommendation,
            confidence=self.config.confidence_level,
        )
    
    def simulate_service_expansion(
        self,
        service_name: str,
        implementation_cost: float,
        annual_volume_estimate: int,
        revenue_per_case: float,
        variable_cost_per_case: float,
        fixed_cost_increase: float = 0,
    ) -> ScenarioResult:
        """
        Simulate financial impact of adding a new service line.
        
        Args:
            service_name: Name of the service
            implementation_cost: One-time implementation cost
            annual_volume_estimate: Expected annual cases
            revenue_per_case: Expected revenue per case
            variable_cost_per_case: Variable cost per case
            fixed_cost_increase: Annual fixed cost increase
            
        Returns:
            ScenarioResult with NPV and payback analysis
        """
        results = []
        
        for _ in range(self.config.n_iterations):
            # Sample volume uncertainty (+/- 30%)
            volume_factor = self.rng.uniform(0.7, 1.3)
            actual_volume = int(annual_volume_estimate * volume_factor)
            
            # Sample revenue uncertainty (+/- 15%)
            revenue_factor = self.rng.uniform(0.85, 1.15)
            actual_revenue = revenue_per_case * revenue_factor
            
            # Sample cost uncertainty (+/- 20%)
            cost_factor = self.rng.uniform(0.80, 1.20)
            actual_variable_cost = variable_cost_per_case * cost_factor
            
            # Calculate annual profit
            gross_margin = actual_volume * (actual_revenue - actual_variable_cost)
            annual_profit = gross_margin - fixed_cost_increase
            
            # Calculate 5-year NPV (discount rate 8%)
            discount_rate = 0.08
            npv = -implementation_cost
            for year in range(1, 6):
                npv += annual_profit / ((1 + discount_rate) ** year)
            
            results.append(npv)
        
        results_array = np.array(results)
        
        sim_result = SimulationResult(
            mean=float(np.mean(results_array)),
            median=float(np.median(results_array)),
            std=float(np.std(results_array)),
            p5=float(np.percentile(results_array, 5)),
            p95=float(np.percentile(results_array, 95)),
            prob_positive=float(np.mean(results_array > 0)),
        )
        
        # Calculate payback period (simplified)
        expected_annual = (annual_volume_estimate * (revenue_per_case - variable_cost_per_case) 
                         - fixed_cost_increase)
        payback_years = implementation_cost / expected_annual if expected_annual > 0 else float('inf')
        
        decision_metrics = {
            "expected_npv": sim_result.mean,
            "payback_years": payback_years,
            "annual_profit_expected": expected_annual,
            "roi_5_year": (sim_result.mean / implementation_cost) * 100 if implementation_cost > 0 else 0,
        }
        
        # Generate recommendation
        if sim_result.prob_positive > 0.8 and payback_years < 3:
            recommendation = "STRONGLY FAVORABLE: High NPV probability with quick payback"
        elif sim_result.prob_positive > 0.6:
            recommendation = "FAVORABLE: Positive NPV expected, consider implementation"
        elif sim_result.prob_positive > 0.4:
            recommendation = "MARGINAL: Carefully evaluate before proceeding"
        else:
            recommendation = "UNFAVORABLE: High probability of negative NPV"
        
        return ScenarioResult(
            scenario_name=f"Service Expansion: {service_name}",
            simulation_result=sim_result,
            decision_metrics=decision_metrics,
            risk_metrics={
                "max_loss": abs(sim_result.p5) if sim_result.p5 < 0 else 0,
                "max_gain": sim_result.p95,
            },
            recommendation=recommendation,
            confidence=self.config.confidence_level,
        )
    
    def simulate_denial_reduction(
        self,
        current_denial_rate: float,
        target_denial_rate: float,
        annual_claims_volume: int,
        average_claim_value: float,
        intervention_cost: float = 0,
    ) -> ScenarioResult:
        """
        Simulate financial impact of denial rate reduction initiative.
        
        Args:
            current_denial_rate: Current denial rate (0-1)
            target_denial_rate: Target denial rate (0-1)
            annual_claims_volume: Number of claims per year
            average_claim_value: Average claim value
            intervention_cost: Cost of intervention (training, tools, etc.)
            
        Returns:
            ScenarioResult with revenue recovery projection
        """
        results = []
        denial_reduction = current_denial_rate - target_denial_rate
        
        for _ in range(self.config.n_iterations):
            # Sample achievement rate (how much of target reduction achieved)
            achievement_rate = self.rng.beta(3, 2)  # Skewed toward success
            actual_reduction = denial_reduction * achievement_rate
            
            # Sample recovery rate on prevented denials
            recovery_rate = self.rng.uniform(0.7, 0.95)
            
            # Calculate claims recovered
            claims_recovered = annual_claims_volume * actual_reduction
            
            # Sample claim value variation
            value_factor = self.rng.uniform(0.8, 1.2)
            actual_claim_value = average_claim_value * value_factor
            
            # Calculate revenue impact
            revenue_recovered = claims_recovered * actual_claim_value * recovery_rate
            net_impact = revenue_recovered - intervention_cost
            
            results.append(net_impact)
        
        results_array = np.array(results)
        
        sim_result = SimulationResult(
            mean=float(np.mean(results_array)),
            median=float(np.median(results_array)),
            std=float(np.std(results_array)),
            p5=float(np.percentile(results_array, 5)),
            p95=float(np.percentile(results_array, 95)),
            prob_positive=float(np.mean(results_array > 0)),
        )
        
        decision_metrics = {
            "expected_revenue_recovery": sim_result.mean + intervention_cost,
            "net_impact": sim_result.mean,
            "roi": (sim_result.mean / intervention_cost) * 100 if intervention_cost > 0 else float('inf'),
            "claims_potentially_saved": annual_claims_volume * denial_reduction,
        }
        
        recommendation = "FAVORABLE" if sim_result.prob_positive > 0.7 else "EVALUATE FURTHER"
        
        return ScenarioResult(
            scenario_name=f"Denial Reduction: {current_denial_rate:.1%} → {target_denial_rate:.1%}",
            simulation_result=sim_result,
            decision_metrics=decision_metrics,
            risk_metrics={},
            recommendation=recommendation,
            confidence=self.config.confidence_level,
        )
    
    def simulate_census_impact(
        self,
        census_change: float,
        duration_days: int = 365,
    ) -> ScenarioResult:
        """
        Simulate financial impact of census change.
        
        Args:
            census_change: Change in average daily census
            duration_days: Duration of analysis in days
            
        Returns:
            ScenarioResult with margin impact
        """
        results = []
        
        # Revenue per patient day (rough estimate)
        revenue_per_patient_day = self.facility.revenue_per_encounter / 3  # Assume 3-day LOS
        
        # Variable cost per patient day (rough estimate)
        variable_cost_ratio = 0.4
        variable_cost_per_day = revenue_per_patient_day * variable_cost_ratio
        
        for _ in range(self.config.n_iterations):
            # Sample actual census change variance
            actual_change = census_change * self.rng.uniform(0.8, 1.2)
            
            # Sample days at changed census
            actual_days = int(duration_days * self.rng.uniform(0.9, 1.0))
            
            # Calculate patient days change
            patient_days_change = actual_change * actual_days
            
            # Revenue change
            revenue_change = patient_days_change * revenue_per_patient_day
            
            # Cost change (only variable)
            cost_change = patient_days_change * variable_cost_per_day
            
            # Contribution margin
            margin_change = revenue_change - cost_change
            
            results.append(margin_change)
        
        results_array = np.array(results)
        
        sim_result = SimulationResult(
            mean=float(np.mean(results_array)),
            median=float(np.median(results_array)),
            std=float(np.std(results_array)),
            p5=float(np.percentile(results_array, 5)),
            p95=float(np.percentile(results_array, 95)),
            prob_positive=float(np.mean(results_array > 0)) if census_change > 0 else float(np.mean(results_array < 0)),
        )
        
        direction = "increase" if census_change > 0 else "decrease"
        
        return ScenarioResult(
            scenario_name=f"Census {direction}: {abs(census_change):.1f} patients/day",
            simulation_result=sim_result,
            decision_metrics={
                "patient_days_impact": census_change * duration_days,
                "revenue_per_patient_day": revenue_per_patient_day,
                "contribution_margin_per_day": revenue_per_patient_day - variable_cost_per_day,
            },
            risk_metrics={},
            recommendation="",
            confidence=self.config.confidence_level,
        )
    
    def compare_scenarios(
        self,
        scenarios: list[ScenarioResult],
    ) -> dict[str, Any]:
        """
        Compare multiple scenarios.
        
        Args:
            scenarios: List of scenario results to compare
            
        Returns:
            Comparison analysis
        """
        if not scenarios:
            return {"error": "No scenarios to compare"}
        
        # Sort by expected value
        sorted_scenarios = sorted(
            scenarios,
            key=lambda s: s.simulation_result.mean,
            reverse=True,
        )
        
        comparison = {
            "best_expected": sorted_scenarios[0].scenario_name,
            "worst_expected": sorted_scenarios[-1].scenario_name,
            "scenarios": [],
        }
        
        for scenario in sorted_scenarios:
            comparison["scenarios"].append({
                "name": scenario.scenario_name,
                "expected_value": scenario.simulation_result.mean,
                "probability_positive": scenario.simulation_result.prob_positive,
                "downside_risk": scenario.simulation_result.p5,
                "upside_potential": scenario.simulation_result.p95,
                "recommendation": scenario.recommendation,
            })
        
        # Identify dominant strategy (if any)
        best = sorted_scenarios[0]
        is_dominant = all(
            best.simulation_result.p5 > s.simulation_result.p5
            for s in sorted_scenarios[1:]
        )
        
        if is_dominant:
            comparison["dominant_strategy"] = best.scenario_name
            comparison["recommendation"] = f"'{best.scenario_name}' dominates all alternatives"
        else:
            comparison["dominant_strategy"] = None
            comparison["recommendation"] = "No dominant strategy - consider risk preferences"
        
        return comparison

