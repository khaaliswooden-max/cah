"""
Performance Gap Analyzer

Quantify gap between current state and target state for any metric.
Decompose gaps into addressable root causes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from cah_engine.core.models import (
    CostReportMetrics,
    Factor,
    GapDecomposition,
)


@dataclass
class Benchmark:
    """Benchmark value with source attribution."""
    
    value: float
    source: str = ""
    percentile: Optional[int] = None  # e.g., 50 for median, 75 for top quartile
    year: Optional[int] = None
    notes: str = ""


@dataclass
class PerformanceGap:
    """A single performance gap with analysis."""
    
    metric_name: str
    current_value: float
    target_value: float
    benchmark: Optional[Benchmark] = None
    
    # Decomposition
    contributing_factors: list[Factor] = field(default_factory=list)
    explained_portion: float = 0.0
    unexplained_portion: float = 0.0
    
    # Recommendations
    priority: int = 1  # 1 = highest
    estimated_effort: str = ""  # e.g., "low", "medium", "high"
    estimated_impact: float = 0.0  # Estimated improvement if addressed
    recommendations: list[str] = field(default_factory=list)
    
    @property
    def gap(self) -> float:
        """The raw gap value (target - current)."""
        return self.target_value - self.current_value
    
    @property
    def gap_percentage(self) -> float:
        """Gap as percentage of target."""
        if self.target_value == 0:
            return 0.0
        return (self.gap / abs(self.target_value)) * 100
    
    @property
    def is_positive_gap(self) -> bool:
        """Whether current exceeds target (could be good or bad depending on metric)."""
        return self.current_value >= self.target_value
    
    def add_factor(self, factor: Factor) -> None:
        """Add a contributing factor."""
        self.contributing_factors.append(factor)
        self._recalculate_portions()
    
    def _recalculate_portions(self) -> None:
        """Recalculate explained and unexplained portions."""
        self.explained_portion = sum(f.contribution for f in self.contributing_factors)
        self.unexplained_portion = self.gap - self.explained_portion


@dataclass
class GapReport:
    """Comprehensive gap analysis report."""
    
    facility_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    period: str = ""
    
    gaps: list[PerformanceGap] = field(default_factory=list)
    total_financial_gap: float = 0.0
    priority_actions: list[str] = field(default_factory=list)
    
    def add_gap(self, gap: PerformanceGap) -> None:
        """Add a gap to the report."""
        self.gaps.append(gap)
        # Re-sort by priority
        self.gaps.sort(key=lambda g: g.priority)
    
    @property
    def critical_gaps(self) -> list[PerformanceGap]:
        """Gaps with priority 1 (critical)."""
        return [g for g in self.gaps if g.priority == 1]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "facility_id": self.facility_id,
            "generated_at": self.generated_at.isoformat(),
            "period": self.period,
            "total_financial_gap": self.total_financial_gap,
            "gaps": [
                {
                    "metric": g.metric_name,
                    "current": g.current_value,
                    "target": g.target_value,
                    "gap": g.gap,
                    "gap_pct": g.gap_percentage,
                    "priority": g.priority,
                    "recommendations": g.recommendations,
                }
                for g in self.gaps
            ],
            "priority_actions": self.priority_actions,
        }


# Standard CAH benchmarks (based on CMS Cost Reports and industry data)
CAH_BENCHMARKS = {
    "operating_margin": Benchmark(
        value=0.5,
        source="CMS Cost Reports",
        percentile=50,
        year=2023,
        notes="Median CAH operating margin"
    ),
    "occupancy_rate": Benchmark(
        value=42.0,
        source="CMS Cost Reports",
        percentile=50,
        year=2023,
        notes="Median CAH occupancy"
    ),
    "denial_rate": Benchmark(
        value=5.0,
        source="Industry benchmark",
        percentile=75,
        year=2023,
        notes="Top quartile denial rate"
    ),
    "transfer_rate": Benchmark(
        value=8.0,
        source="HRSA data",
        percentile=50,
        year=2023,
        notes="Median CAH transfer rate"
    ),
    "labor_cost_ratio": Benchmark(
        value=52.0,
        source="CMS Cost Reports",
        percentile=50,
        year=2023,
        notes="Labor cost as % of operating expenses"
    ),
    "swing_bed_utilization": Benchmark(
        value=75.0,
        source="Industry benchmark",
        percentile=75,
        year=2023,
        notes="Swing bed utilization rate"
    ),
    "days_cash_on_hand": Benchmark(
        value=45.0,
        source="Industry benchmark",
        percentile=50,
        year=2023,
        notes="Days cash on hand"
    ),
    "average_los_hours": Benchmark(
        value=72.0,
        source="CMS Cost Reports",
        percentile=50,
        year=2023,
        notes="Average LOS in hours (well below 96h limit)"
    ),
}


class GapAnalyzer:
    """
    Analyze performance gaps and decompose into root causes.
    
    Gap Function: G(t) = S* - S(t)
    Decomposition: G = Σᵢ αᵢ·Cᵢ
    
    Where:
    - S* = Target state
    - S(t) = Current state
    - Cᵢ = Contributing cause i
    - αᵢ = Impact coefficient
    """
    
    def __init__(self, benchmarks: Optional[dict[str, Benchmark]] = None):
        self.benchmarks = benchmarks or CAH_BENCHMARKS
        
        # Impact coefficients (empirically derived)
        # These represent the estimated improvement in the target metric
        # per unit improvement in the contributing factor
        self.impact_coefficients = {
            # Margin improvement factors
            "denial_rate_to_margin": -0.8,  # 1% denial reduction = 0.8% margin improvement
            "labor_ratio_to_margin": -0.5,  # 1% labor reduction = 0.5% margin improvement
            "transfer_rate_to_margin": -0.3,  # 1% transfer reduction = 0.3% margin improvement
            "swing_util_to_margin": 0.2,  # 1% swing increase = 0.2% margin improvement
            
            # Other relationships
            "los_to_transfer": 0.05,  # Each hour LOS increase = 0.05% transfer increase
            "occupancy_to_margin": 0.1,  # 1% occupancy increase = 0.1% margin improvement
        }
    
    def analyze_metrics(
        self,
        metrics: CostReportMetrics,
        custom_targets: Optional[dict[str, float]] = None,
    ) -> GapReport:
        """
        Perform comprehensive gap analysis on cost report metrics.
        
        Args:
            metrics: Cost report metrics to analyze
            custom_targets: Optional custom target values (overrides benchmarks)
            
        Returns:
            GapReport with all identified gaps
        """
        report = GapReport(
            facility_id=metrics.provider_id,
            period=f"FY ending {metrics.fiscal_year_end}",
        )
        
        targets = {k: v.value for k, v in self.benchmarks.items()}
        if custom_targets:
            targets.update(custom_targets)
        
        # Operating Margin Gap
        margin_gap = self.analyze_margin_gap(
            current=metrics.operating_margin,
            target=targets.get("operating_margin", 0.5),
            denial_rate=10.0,  # Would come from actual data
            labor_ratio=metrics.labor_cost_ratio * 100,
            transfer_rate=10.0,  # Would come from actual data
            swing_utilization=50.0,  # Would come from actual data
        )
        report.add_gap(margin_gap)
        
        # Occupancy Gap
        if metrics.occupancy_rate < targets.get("occupancy_rate", 42.0):
            occupancy_gap = PerformanceGap(
                metric_name="Occupancy Rate (%)",
                current_value=metrics.occupancy_rate,
                target_value=targets.get("occupancy_rate", 42.0),
                benchmark=self.benchmarks.get("occupancy_rate"),
                priority=2,
                estimated_effort="medium",
                recommendations=[
                    "Review referral patterns and relationships",
                    "Optimize swing bed program marketing",
                    "Enhance discharge planning efficiency",
                ],
            )
            report.add_gap(occupancy_gap)
        
        # LOS Gap (if approaching limit)
        if metrics.average_los_hours > targets.get("average_los_hours", 72.0):
            los_gap = PerformanceGap(
                metric_name="Average LOS (hours)",
                current_value=metrics.average_los_hours,
                target_value=targets.get("average_los_hours", 72.0),
                benchmark=self.benchmarks.get("average_los_hours"),
                priority=1 if metrics.average_los_hours > 80 else 2,
                estimated_effort="medium",
                recommendations=[
                    "Implement daily discharge planning rounds",
                    "Review barriers to discharge",
                    "Consider care management intervention",
                ],
            )
            report.add_gap(los_gap)
        
        # Labor Cost Gap
        if metrics.labor_cost_ratio * 100 > targets.get("labor_cost_ratio", 52.0):
            labor_gap = PerformanceGap(
                metric_name="Labor Cost Ratio (%)",
                current_value=metrics.labor_cost_ratio * 100,
                target_value=targets.get("labor_cost_ratio", 52.0),
                benchmark=self.benchmarks.get("labor_cost_ratio"),
                priority=2,
                estimated_effort="high",
                recommendations=[
                    "Review staffing ratios against census",
                    "Optimize scheduling to reduce overtime",
                    "Evaluate traveler/agency utilization",
                    "Consider cross-training opportunities",
                ],
            )
            report.add_gap(labor_gap)
        
        # Calculate total financial gap
        if margin_gap.gap < 0:  # Negative margin gap = improvement needed
            annual_revenue = float(metrics.total_operating_revenue)
            report.total_financial_gap = annual_revenue * (abs(margin_gap.gap) / 100)
        
        # Generate priority actions
        report.priority_actions = self._generate_priority_actions(report.gaps)
        
        return report
    
    def analyze_margin_gap(
        self,
        current: float,
        target: float,
        denial_rate: float,
        labor_ratio: float,
        transfer_rate: float,
        swing_utilization: float,
    ) -> PerformanceGap:
        """
        Decompose operating margin gap into addressable factors.
        
        Args:
            current: Current operating margin (%)
            target: Target operating margin (%)
            denial_rate: Current denial rate (%)
            labor_ratio: Labor cost as % of expenses
            transfer_rate: Transfer rate (%)
            swing_utilization: Swing bed utilization (%)
            
        Returns:
            PerformanceGap with factor decomposition
        """
        gap = PerformanceGap(
            metric_name="Operating Margin (%)",
            current_value=current,
            target_value=target,
            benchmark=self.benchmarks.get("operating_margin"),
            priority=1,
            estimated_effort="high",
        )
        
        # Get benchmark values
        denial_benchmark = self.benchmarks.get("denial_rate", Benchmark(value=5.0)).value
        labor_benchmark = self.benchmarks.get("labor_cost_ratio", Benchmark(value=52.0)).value
        transfer_benchmark = self.benchmarks.get("transfer_rate", Benchmark(value=8.0)).value
        swing_benchmark = self.benchmarks.get("swing_bed_utilization", Benchmark(value=75.0)).value
        
        # Denial rate factor
        if denial_rate > denial_benchmark:
            denial_excess = denial_rate - denial_benchmark
            contribution = denial_excess * self.impact_coefficients["denial_rate_to_margin"]
            gap.add_factor(Factor(
                name="Denial Rate",
                current=denial_rate,
                benchmark=denial_benchmark,
                impact_coefficient=self.impact_coefficients["denial_rate_to_margin"],
                contribution=contribution,
            ))
        
        # Labor cost factor
        if labor_ratio > labor_benchmark:
            labor_excess = labor_ratio - labor_benchmark
            contribution = labor_excess * self.impact_coefficients["labor_ratio_to_margin"]
            gap.add_factor(Factor(
                name="Labor Cost Ratio",
                current=labor_ratio,
                benchmark=labor_benchmark,
                impact_coefficient=self.impact_coefficients["labor_ratio_to_margin"],
                contribution=contribution,
            ))
        
        # Transfer rate factor
        if transfer_rate > transfer_benchmark:
            transfer_excess = transfer_rate - transfer_benchmark
            contribution = transfer_excess * self.impact_coefficients["transfer_rate_to_margin"]
            gap.add_factor(Factor(
                name="Transfer Rate",
                current=transfer_rate,
                benchmark=transfer_benchmark,
                impact_coefficient=self.impact_coefficients["transfer_rate_to_margin"],
                contribution=contribution,
            ))
        
        # Swing bed utilization factor
        if swing_utilization < swing_benchmark:
            swing_gap = swing_benchmark - swing_utilization
            contribution = swing_gap * self.impact_coefficients["swing_util_to_margin"]
            gap.add_factor(Factor(
                name="Swing Bed Utilization",
                current=swing_utilization,
                benchmark=swing_benchmark,
                impact_coefficient=self.impact_coefficients["swing_util_to_margin"],
                contribution=-contribution,  # Negative because below benchmark
            ))
        
        # Generate recommendations based on factors
        gap.recommendations = self._generate_margin_recommendations(gap.contributing_factors)
        
        # Estimate total impact
        gap.estimated_impact = sum(
            abs(f.contribution) for f in gap.contributing_factors
        )
        
        return gap
    
    def _generate_margin_recommendations(
        self,
        factors: list[Factor],
    ) -> list[str]:
        """Generate recommendations based on contributing factors."""
        recommendations = []
        
        # Sort factors by absolute contribution
        sorted_factors = sorted(factors, key=lambda f: abs(f.contribution), reverse=True)
        
        for factor in sorted_factors[:3]:  # Top 3 factors
            if factor.name == "Denial Rate":
                recommendations.extend([
                    f"Reduce denial rate from {factor.current:.1f}% to {factor.benchmark:.1f}%",
                    "Implement pre-bill scrubbing process",
                    "Train staff on common denial causes",
                ])
            elif factor.name == "Labor Cost Ratio":
                recommendations.extend([
                    f"Reduce labor cost ratio from {factor.current:.1f}% to {factor.benchmark:.1f}%",
                    "Optimize scheduling based on census forecast",
                    "Review overtime and agency utilization",
                ])
            elif factor.name == "Transfer Rate":
                recommendations.extend([
                    f"Optimize transfer rate from {factor.current:.1f}% to {factor.benchmark:.1f}%",
                    "Enhance clinical capabilities where feasible",
                    "Improve specialist coverage arrangements",
                ])
            elif factor.name == "Swing Bed Utilization":
                recommendations.extend([
                    f"Increase swing bed utilization from {factor.current:.1f}% to {factor.benchmark:.1f}%",
                    "Market swing bed program to referral sources",
                    "Streamline admission process for swing patients",
                ])
        
        return recommendations
    
    def _generate_priority_actions(
        self,
        gaps: list[PerformanceGap],
    ) -> list[str]:
        """Generate prioritized action list from gaps."""
        actions = []
        
        for gap in gaps[:5]:  # Top 5 gaps by priority
            if gap.recommendations:
                # Take first actionable recommendation
                action = gap.recommendations[0]
                actions.append(f"[{gap.metric_name}] {action}")
        
        return actions
    
    def calculate_improvement_scenario(
        self,
        current_metrics: CostReportMetrics,
        improvements: dict[str, float],
    ) -> dict[str, float]:
        """
        Calculate projected metrics after improvements.
        
        Args:
            current_metrics: Current facility metrics
            improvements: Dict of factor improvements (e.g., {"denial_rate": -5})
            
        Returns:
            Dict of projected metric values
        """
        projected = {
            "operating_margin": current_metrics.operating_margin,
            "occupancy_rate": current_metrics.occupancy_rate,
            "labor_cost_ratio": current_metrics.labor_cost_ratio * 100,
        }
        
        # Apply improvements through impact coefficients
        for factor, change in improvements.items():
            if factor == "denial_rate":
                margin_impact = change * self.impact_coefficients["denial_rate_to_margin"]
                projected["operating_margin"] += margin_impact
            elif factor == "labor_ratio":
                margin_impact = change * self.impact_coefficients["labor_ratio_to_margin"]
                projected["operating_margin"] += margin_impact
                projected["labor_cost_ratio"] += change
            elif factor == "transfer_rate":
                margin_impact = change * self.impact_coefficients["transfer_rate_to_margin"]
                projected["operating_margin"] += margin_impact
            elif factor == "occupancy":
                margin_impact = change * self.impact_coefficients["occupancy_to_margin"]
                projected["operating_margin"] += margin_impact
                projected["occupancy_rate"] += change
        
        # Calculate financial impact
        annual_revenue = float(current_metrics.total_operating_revenue)
        margin_improvement = projected["operating_margin"] - current_metrics.operating_margin
        projected["additional_annual_income"] = annual_revenue * (margin_improvement / 100)
        
        return projected

