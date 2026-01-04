"""
Integrated CAH Optimizer.

Combines real data from acquired datasets with the optimization model
to provide evidence-based optimization for Critical Access Hospitals.

This module:
1. Loads and integrates CMS cost reports, quality data, and CAH designations
2. Calibrates optimization parameters from real data
3. Provides facility-specific and population-level optimization
4. Generates actionable recommendations grounded in evidence

Usage:
    >>> from cah_engine.integration.integrated_optimizer import IntegratedOptimizer
    >>> optimizer = IntegratedOptimizer("data")
    >>> result = optimizer.optimize_population()
    >>> print(f"Recommended margin target: {result.margin:.2%}")
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

# Import from parent package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from models import (
    CAHParameters,
    QualityBenchmarks,
    DecisionVariables,
    OptimizationResult,
    OptimizationStatus,
)
from objectives import CAHObjectiveFunctions
from constraints import CAHConstraints
from solver import CAHOptimizer

from cah_engine.integration.data_loader import (
    CAHDataLoader,
    IntegratedDataset,
    CAHFacility,
)
from cah_engine.integration.parameter_estimator import (
    ParameterEstimator,
    CalibratedParameters,
)


@dataclass
class FacilityOptimizationResult:
    """Optimization result for a specific facility."""
    
    facility_id: str
    facility_name: str
    state: str
    
    # Current state
    current_margin: float
    current_quality_score: float
    current_beds: int
    current_occupancy: float
    
    # Optimized targets
    target_margin: float
    target_quality_score: float
    recommended_actions: list[str] = field(default_factory=list)
    
    # Improvement potential
    margin_improvement: float = 0.0
    quality_improvement: float = 0.0
    revenue_opportunity: float = 0.0
    
    # Risk assessment
    margin_at_risk: bool = False
    compliance_risk: bool = False
    risk_factors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Export as dictionary."""
        return {
            "facility_id": self.facility_id,
            "facility_name": self.facility_name,
            "state": self.state,
            "current_state": {
                "margin": self.current_margin,
                "quality_score": self.current_quality_score,
                "beds": self.current_beds,
                "occupancy": self.current_occupancy,
            },
            "optimized_targets": {
                "margin": self.target_margin,
                "quality_score": self.target_quality_score,
            },
            "improvements": {
                "margin_improvement": self.margin_improvement,
                "quality_improvement": self.quality_improvement,
                "revenue_opportunity": self.revenue_opportunity,
            },
            "recommended_actions": self.recommended_actions,
            "risk_assessment": {
                "margin_at_risk": self.margin_at_risk,
                "compliance_risk": self.compliance_risk,
                "risk_factors": self.risk_factors,
            },
        }


@dataclass
class PopulationOptimizationResult:
    """Aggregated optimization results across CAH population."""
    
    # Summary statistics
    total_facilities: int = 0
    facilities_analyzed: int = 0
    facilities_at_risk: int = 0
    
    # Aggregate metrics
    population_median_margin: float = 0.0
    population_median_quality: float = 0.0
    
    # Optimization results
    target_margin: float = 0.0
    target_quality: float = 0.0
    total_revenue_opportunity: float = 0.0
    
    # Distributions
    margin_distribution: dict[str, float] = field(default_factory=dict)
    quality_distribution: dict[str, float] = field(default_factory=dict)
    
    # Top recommendations (aggregate)
    top_recommendations: list[str] = field(default_factory=list)
    
    # Individual facility results
    facility_results: list[FacilityOptimizationResult] = field(default_factory=list)
    
    # Calibrated parameters used
    parameters: Optional[CalibratedParameters] = None
    
    # Metadata
    optimization_timestamp: str = ""
    data_year: int = 2023
    
    def to_dict(self) -> dict:
        """Export as dictionary."""
        return {
            "summary": {
                "total_facilities": self.total_facilities,
                "facilities_analyzed": self.facilities_analyzed,
                "facilities_at_risk": self.facilities_at_risk,
            },
            "population_metrics": {
                "median_margin": self.population_median_margin,
                "median_quality": self.population_median_quality,
            },
            "optimization_targets": {
                "target_margin": self.target_margin,
                "target_quality": self.target_quality,
                "total_revenue_opportunity": self.total_revenue_opportunity,
            },
            "distributions": {
                "margin": self.margin_distribution,
                "quality": self.quality_distribution,
            },
            "top_recommendations": self.top_recommendations,
            "facility_results": [r.to_dict() for r in self.facility_results[:10]],  # Top 10
            "metadata": {
                "timestamp": self.optimization_timestamp,
                "data_year": self.data_year,
            },
        }


class IntegratedOptimizer:
    """
    Data-integrated CAH optimization engine.
    
    Combines real CMS data with mathematical optimization to provide
    evidence-based recommendations for CAH transformation.
    
    Key capabilities:
    - Population-level analysis and optimization
    - Facility-specific recommendations
    - Risk identification and mitigation
    - Benchmarking against peer facilities
    
    Example:
        >>> optimizer = IntegratedOptimizer("data")
        >>> pop_result = optimizer.optimize_population()
        >>> print(f"At-risk facilities: {pop_result.facilities_at_risk}")
        
        >>> facility_result = optimizer.optimize_facility("011300")
        >>> print(f"Target margin: {facility_result.target_margin:.2%}")
    """
    
    def __init__(
        self,
        data_dir: str | Path = "data",
        theta: float = 0.6,
        margin_floor: float = 0.05,
    ):
        """
        Initialize integrated optimizer.
        
        Args:
            data_dir: Path to data directory
            theta: Quality-profit tradeoff (0=profit only, 1=quality only)
            margin_floor: Minimum required operating margin
        """
        self.data_dir = Path(data_dir)
        self.theta = theta
        self.margin_floor = margin_floor
        
        # Load integrated dataset
        self.data_loader = CAHDataLoader(self.data_dir)
        self.dataset: Optional[IntegratedDataset] = None
        
        # Parameter estimator
        self.estimator = ParameterEstimator()
        self.calibrated_params: Optional[CalibratedParameters] = None
        
        # Core optimizer (initialized after calibration)
        self.core_optimizer: Optional[CAHOptimizer] = None
    
    def load_data(self, year: int = 2023) -> IntegratedDataset:
        """
        Load and integrate all datasets.
        
        Args:
            year: Cost report year to use
            
        Returns:
            IntegratedDataset with all facilities
        """
        self.dataset = self.data_loader.load_all(year)
        return self.dataset
    
    def calibrate_parameters(self) -> CalibratedParameters:
        """
        Calibrate optimization parameters from loaded data.
        
        Returns:
            CalibratedParameters with evidence-based estimates
        """
        if self.dataset is None:
            self.load_data()
        
        self.calibrated_params = self.estimator.estimate(self.dataset)
        
        # Initialize core optimizer with calibrated parameters
        model_params = self._convert_to_model_params(self.calibrated_params)
        model_benchmarks = self._convert_to_model_benchmarks(self.calibrated_params)
        
        self.core_optimizer = CAHOptimizer(
            params=model_params,
            benchmarks=model_benchmarks,
            theta=self.theta,
            margin_floor=self.margin_floor,
        )
        
        return self.calibrated_params
    
    def optimize_population(
        self,
        year: int = 2023,
        max_facilities: int = None,
    ) -> PopulationOptimizationResult:
        """
        Run optimization analysis across CAH population.
        
        Args:
            year: Cost report year
            max_facilities: Maximum facilities to analyze (None = all)
            
        Returns:
            PopulationOptimizationResult with aggregate analysis
        """
        # Ensure data is loaded and calibrated
        if self.dataset is None:
            self.load_data(year)
        if self.calibrated_params is None:
            self.calibrate_parameters()
        
        result = PopulationOptimizationResult()
        result.optimization_timestamp = datetime.now().isoformat()
        result.data_year = year
        result.total_facilities = len(self.dataset.facilities)
        result.parameters = self.calibrated_params
        
        # Analyze facilities
        facilities = list(self.dataset.facilities.values())
        if max_facilities:
            facilities = facilities[:max_facilities]
        
        margins = []
        qualities = []
        at_risk_count = 0
        
        for facility in facilities:
            facility_result = self._analyze_facility(facility)
            if facility_result:
                result.facility_results.append(facility_result)
                margins.append(facility_result.current_margin)
                qualities.append(facility_result.current_quality_score)
                
                if facility_result.margin_at_risk:
                    at_risk_count += 1
        
        result.facilities_analyzed = len(result.facility_results)
        result.facilities_at_risk = at_risk_count
        
        # Calculate distributions
        if margins:
            import statistics
            result.population_median_margin = statistics.median(margins)
            result.margin_distribution = self._calculate_distribution(margins)
        
        if qualities:
            import statistics
            result.population_median_quality = statistics.median(qualities)
            result.quality_distribution = self._calculate_distribution(qualities)
        
        # Run core optimization for population-level targets
        if self.core_optimizer:
            opt_result = self.core_optimizer.optimize(multi_start=5, seed=42)
            result.target_margin = opt_result.margin
            result.target_quality = opt_result.quality
        
        # Calculate total revenue opportunity
        result.total_revenue_opportunity = sum(
            r.revenue_opportunity for r in result.facility_results
        )
        
        # Generate population-level recommendations
        result.top_recommendations = self._generate_population_recommendations(result)
        
        # Sort facility results by margin improvement potential
        result.facility_results.sort(
            key=lambda r: r.margin_improvement,
            reverse=True
        )
        
        return result
    
    def optimize_facility(
        self,
        facility_id: str,
    ) -> Optional[FacilityOptimizationResult]:
        """
        Run optimization for a specific facility.
        
        Args:
            facility_id: CMS facility identifier
            
        Returns:
            FacilityOptimizationResult or None if facility not found
        """
        if self.dataset is None:
            self.load_data()
        
        facility = self.dataset.facilities.get(facility_id)
        if facility is None:
            return None
        
        if self.calibrated_params is None:
            self.calibrate_parameters()
        
        return self._analyze_facility(facility)
    
    def get_peer_comparison(
        self,
        facility_id: str,
        peer_group: str = "state",
    ) -> dict[str, Any]:
        """
        Compare facility to peer group.
        
        Args:
            facility_id: Facility to compare
            peer_group: Grouping method ("state", "size", "ownership")
            
        Returns:
            Dictionary with comparison metrics
        """
        if self.dataset is None:
            self.load_data()
        
        facility = self.dataset.facilities.get(facility_id)
        if facility is None:
            return {"error": "Facility not found"}
        
        # Get peer facilities
        if peer_group == "state":
            peers = [f for f in self.dataset.facilities.values() 
                     if f.state == facility.state and f.facility_id != facility_id]
        elif peer_group == "size":
            target_beds = facility.staffed_beds or 15
            peers = [f for f in self.dataset.facilities.values()
                     if abs((f.staffed_beds or 15) - target_beds) <= 5
                     and f.facility_id != facility_id]
        else:  # ownership
            peers = [f for f in self.dataset.facilities.values()
                     if f.ownership == facility.ownership
                     and f.facility_id != facility_id]
        
        if not peers:
            return {"error": "No peer facilities found"}
        
        # Calculate percentiles
        import statistics
        peer_margins = [p.operating_margin for p in peers if p.total_operating_revenue > 0]
        peer_qualities = [p.quality_score for p in peers]
        peer_occupancies = [p.occupancy_rate for p in peers if p.staffed_beds > 0]
        
        def percentile_rank(value: float, values: list[float]) -> float:
            if not values:
                return 50.0
            below = sum(1 for v in values if v < value)
            return (below / len(values)) * 100
        
        return {
            "facility_id": facility_id,
            "peer_group": peer_group,
            "peer_count": len(peers),
            "comparison": {
                "margin": {
                    "facility_value": facility.operating_margin,
                    "peer_median": statistics.median(peer_margins) if peer_margins else 0,
                    "percentile_rank": percentile_rank(facility.operating_margin, peer_margins),
                },
                "quality": {
                    "facility_value": facility.quality_score,
                    "peer_median": statistics.median(peer_qualities) if peer_qualities else 0,
                    "percentile_rank": percentile_rank(facility.quality_score, peer_qualities),
                },
                "occupancy": {
                    "facility_value": facility.occupancy_rate,
                    "peer_median": statistics.median(peer_occupancies) if peer_occupancies else 0,
                    "percentile_rank": percentile_rank(facility.occupancy_rate, peer_occupancies),
                },
            },
        }
    
    def export_results(
        self,
        result: PopulationOptimizationResult,
        output_path: str | Path,
    ) -> None:
        """
        Export optimization results to JSON file.
        
        Args:
            result: PopulationOptimizationResult to export
            output_path: Path for output file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        export_data = result.to_dict()
        
        # Add parameter estimates
        if result.parameters:
            export_data["calibrated_parameters"] = result.parameters.to_dict()
        
        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _convert_to_model_params(self, params: CalibratedParameters) -> CAHParameters:
        """Convert calibrated parameters to optimization model format."""
        return CAHParameters(
            alpha_1=params.alpha_1.value if params.alpha_1 else 12847.0,
            alpha_2=params.alpha_2.value if params.alpha_2 else 485.0,
            alpha_3=params.alpha_3.value if params.alpha_3 else 215.0,
            alpha_4=params.alpha_4.value if params.alpha_4 else 380.0,
            sigma_alpha_1=params.alpha_1.std_error if params.alpha_1 else 2340.0,
            sigma_alpha_2=params.alpha_2.std_error if params.alpha_2 else 127.0,
            sigma_alpha_3=params.alpha_3.std_error if params.alpha_3 else 68.0,
            sigma_alpha_4=params.alpha_4.std_error if params.alpha_4 else 95.0,
            beta_1=params.beta_1.value if params.beta_1 else 78500.0,
            beta_2=params.beta_2.value if params.beta_2 else 285000.0,
            beta_3=params.beta_3.value if params.beta_3 else 4200000.0,
            beta_4=params.beta_4.value if params.beta_4 else 892.0,
            sigma_beta_1=params.beta_1.std_error if params.beta_1 else 12400.0,
            sigma_beta_2=params.beta_2.std_error if params.beta_2 else 65000.0,
            sigma_beta_3=params.beta_3.std_error if params.beta_3 else 900000.0,
            sigma_beta_4=params.beta_4.std_error if params.beta_4 else 178.0,
            alos=params.avg_los.value if params.avg_los else 3.2,
            swing_occupancy=params.swing_occupancy.value if params.swing_occupancy else 0.65,
        )
    
    def _convert_to_model_benchmarks(self, params: CalibratedParameters) -> QualityBenchmarks:
        """Convert calibrated quality benchmarks to model format."""
        benchmarks = {}
        weights = {}
        direction = {}
        
        default_benchmarks = {
            "ed_throughput": (180.0, 0.15, False),
            "pain_management": (30.0, 0.10, False),
            "hcahps_overall": (72.0, 0.20, True),
            "opioid_concurrent": (5.0, 0.15, False),
            "readmission_30d": (15.0, 0.20, False),
            "falls_injury": (2.5, 0.10, False),
            "cauti_rate": (1.5, 0.10, False),
        }
        
        for measure, (default_val, weight, higher_better) in default_benchmarks.items():
            if params.quality_benchmarks and measure in params.quality_benchmarks:
                benchmarks[measure] = params.quality_benchmarks[measure].value
            else:
                benchmarks[measure] = default_val
            weights[measure] = weight
            direction[measure] = higher_better
        
        return QualityBenchmarks(
            benchmarks=benchmarks,
            weights=weights,
            direction=direction,
        )
    
    def _analyze_facility(self, facility: CAHFacility) -> Optional[FacilityOptimizationResult]:
        """Analyze a single facility and generate recommendations."""
        result = FacilityOptimizationResult(
            facility_id=facility.facility_id,
            facility_name=facility.facility_name,
            state=facility.state,
            current_margin=facility.operating_margin,
            current_quality_score=facility.quality_score,
            current_beds=facility.staffed_beds,
            current_occupancy=facility.occupancy_rate,
            target_margin=0.0,
            target_quality_score=0.0,
        )
        
        # Assess risk
        if facility.operating_margin < self.margin_floor:
            result.margin_at_risk = True
            result.risk_factors.append(
                f"Operating margin ({facility.operating_margin:.1%}) below {self.margin_floor:.0%} threshold"
            )
        
        if facility.staffed_beds > 25:
            result.compliance_risk = True
            result.risk_factors.append(
                f"Staffed beds ({facility.staffed_beds}) exceeds CAH limit of 25"
            )
        
        # Generate facility-specific targets
        # Use optimization model if available
        if self.core_optimizer:
            # Create initial point from facility data
            x0 = self._facility_to_decision_vector(facility)
            opt_result = self.core_optimizer.optimize_single(x0)
            
            result.target_margin = opt_result.margin
            result.target_quality_score = opt_result.quality
        else:
            # Use population benchmarks
            result.target_margin = max(self.margin_floor, 0.07)
            result.target_quality_score = 0.70
        
        # Calculate improvement potential
        result.margin_improvement = result.target_margin - facility.operating_margin
        result.quality_improvement = result.target_quality_score - facility.quality_score
        
        # Revenue opportunity (5% margin improvement on $8M typical CAH revenue)
        if facility.total_operating_revenue > 0:
            result.revenue_opportunity = float(
                facility.total_operating_revenue * max(0, result.margin_improvement)
            )
        else:
            # Estimate based on typical CAH
            result.revenue_opportunity = 8_000_000 * max(0, result.margin_improvement)
        
        # Generate recommendations
        result.recommended_actions = self._generate_facility_recommendations(
            facility, result
        )
        
        return result
    
    def _facility_to_decision_vector(self, facility: CAHFacility) -> np.ndarray:
        """Convert facility data to optimization decision vector."""
        # x = [acute_beds, swing_beds, nursing_fte, provider_fte, 
        #      avg_daily_census, ed_visits, outpatient_visits, cmi]
        
        # Use actual data where available, defaults otherwise
        acute_beds = min(facility.staffed_beds or 15, 25)
        swing_beds = max(0, min((facility.staffed_beds or 15) - acute_beds, 10))
        nursing_fte = facility.fte_count * 0.50 if facility.fte_count > 0 else 35.0
        provider_fte = facility.fte_count * 0.10 if facility.fte_count > 0 else 5.0
        adc = facility.avg_daily_census if facility.avg_daily_census > 0 else 8.0
        ed_visits = facility.ed_visits if facility.ed_visits > 0 else 5000.0
        op_visits = 15000.0  # Not in our data
        cmi = 1.0  # Not in our data
        
        return np.array([
            acute_beds,
            swing_beds,
            nursing_fte,
            provider_fte,
            adc,
            ed_visits,
            op_visits,
            cmi,
        ])
    
    def _generate_facility_recommendations(
        self,
        facility: CAHFacility,
        result: FacilityOptimizationResult,
    ) -> list[str]:
        """Generate actionable recommendations for a facility."""
        recommendations = []
        
        # Margin recommendations
        if result.margin_at_risk:
            recommendations.append(
                "CRITICAL: Review cost structure - operating margin below sustainability threshold"
            )
            
            if facility.occupancy_rate < 0.40:
                recommendations.append(
                    "Increase patient volume through community outreach and service expansion"
                )
            
            if facility.fte_count > 0:
                labor_ratio = float(facility.salary_expenses / facility.total_operating_expenses) if facility.total_operating_expenses > 0 else 0.5
                if labor_ratio > 0.55:
                    recommendations.append(
                        f"Evaluate staffing efficiency - labor costs at {labor_ratio:.0%} of expenses"
                    )
        
        # Quality recommendations
        if facility.quality_score < 0.50:
            recommendations.append(
                "Quality improvement priority - consider MBQIP technical assistance"
            )
            
            if facility.mort_measures_worse > facility.mort_measures_better:
                recommendations.append(
                    "Focus on mortality measures - review clinical protocols"
                )
            
            if facility.readm_measures_worse > facility.readm_measures_better:
                recommendations.append(
                    "Address readmission rates - enhance discharge planning and follow-up"
                )
        
        # Occupancy recommendations
        if facility.occupancy_rate < 0.30:
            recommendations.append(
                "Critically low occupancy - evaluate swing bed program expansion"
            )
        elif facility.occupancy_rate > 0.75:
            recommendations.append(
                "High occupancy - ensure adequate staffing and transfer protocols"
            )
        
        # Compliance recommendations
        if result.compliance_risk:
            recommendations.append(
                "COMPLIANCE ALERT: Bed count exceeds CAH regulatory limit"
            )
        
        if not recommendations:
            recommendations.append(
                "Facility performing well - continue monitoring key metrics"
            )
        
        return recommendations
    
    def _generate_population_recommendations(
        self,
        result: PopulationOptimizationResult,
    ) -> list[str]:
        """Generate population-level recommendations."""
        recommendations = []
        
        # At-risk analysis
        at_risk_pct = (result.facilities_at_risk / result.facilities_analyzed * 100) if result.facilities_analyzed > 0 else 0
        
        if at_risk_pct > 30:
            recommendations.append(
                f"ALERT: {at_risk_pct:.0f}% of CAHs below margin threshold - systemic intervention needed"
            )
        elif at_risk_pct > 15:
            recommendations.append(
                f"Elevated risk: {at_risk_pct:.0f}% of facilities below sustainability threshold"
            )
        
        # Revenue opportunity
        if result.total_revenue_opportunity > 100_000_000:
            recommendations.append(
                f"Total revenue opportunity: ${result.total_revenue_opportunity / 1e6:.0f}M through optimization"
            )
        
        # Quality recommendations
        if result.population_median_quality < 0.50:
            recommendations.append(
                "Population-wide quality initiative recommended - median score below benchmark"
            )
        
        # Regional focus
        if result.facility_results:
            # Find state with most at-risk facilities
            state_risks = {}
            for fr in result.facility_results:
                if fr.margin_at_risk:
                    state_risks[fr.state] = state_risks.get(fr.state, 0) + 1
            
            if state_risks:
                worst_state = max(state_risks.items(), key=lambda x: x[1])
                recommendations.append(
                    f"Regional focus: {worst_state[0]} has {worst_state[1]} at-risk facilities"
                )
        
        return recommendations
    
    def _calculate_distribution(self, values: list[float]) -> dict[str, float]:
        """Calculate distribution statistics."""
        import statistics
        
        if not values:
            return {}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "min": min(values),
            "p10": sorted_values[int(n * 0.10)] if n > 10 else min(values),
            "p25": sorted_values[int(n * 0.25)] if n > 4 else min(values),
            "median": statistics.median(values),
            "p75": sorted_values[int(n * 0.75)] if n > 4 else max(values),
            "p90": sorted_values[int(n * 0.90)] if n > 10 else max(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "std": statistics.stdev(values) if n > 1 else 0,
        }


def run_integrated_optimization(
    data_dir: str = "data",
    output_path: str = "reports/optimization_results.json",
    theta: float = 0.6,
    margin_floor: float = 0.05,
) -> PopulationOptimizationResult:
    """
    Convenience function to run full integrated optimization.
    
    Args:
        data_dir: Path to data directory
        output_path: Path for results output
        theta: Quality-profit tradeoff
        margin_floor: Minimum margin threshold
        
    Returns:
        PopulationOptimizationResult
    """
    optimizer = IntegratedOptimizer(
        data_dir=data_dir,
        theta=theta,
        margin_floor=margin_floor,
    )
    
    result = optimizer.optimize_population()
    optimizer.export_results(result, output_path)
    
    return result

