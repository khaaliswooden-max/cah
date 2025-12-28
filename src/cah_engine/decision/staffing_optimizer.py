"""
Staffing Optimizer

Optimize staff scheduling under demand uncertainty and budget constraints.
Uses linear programming for MV-CAHI compliant optimization.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Optional
import math

import numpy as np
from numpy.typing import NDArray

from cah_engine.core.models import StaffMember, Schedule


@dataclass
class StaffingConstraints:
    """Constraints for staffing optimization."""
    
    # Minimum staffing levels
    min_staff_per_period: int = 2
    min_rn_per_shift: int = 1
    min_by_skill: dict[str, int] = field(default_factory=dict)
    
    # Cost parameters
    understaffing_penalty: float = 1000.0  # Penalty per understaffed period
    overtime_multiplier: float = 1.5
    
    # Regulatory
    max_consecutive_shifts: int = 6
    min_rest_hours: int = 8
    max_hours_per_week: float = 40
    
    # Skill mix
    required_skills: set[str] = field(default_factory=set)
    
    def __post_init__(self):
        if not self.required_skills:
            self.required_skills = {"rn", "cna"}
        if not self.min_by_skill:
            self.min_by_skill = {"rn": 1}


@dataclass
class ShiftDefinition:
    """Definition of a work shift."""
    
    name: str
    start_hour: int
    duration_hours: int
    differential: float = 0.0  # Pay differential (e.g., 0.1 for night shift)
    
    @property
    def end_hour(self) -> int:
        """Calculate end hour (may wrap past midnight)."""
        return (self.start_hour + self.duration_hours) % 24
    
    @property
    def is_night_shift(self) -> bool:
        """Check if this is a night shift."""
        return self.start_hour >= 19 or self.start_hour < 7


@dataclass
class DemandForecast:
    """Demand forecast for scheduling."""
    
    dates: list[date]
    hourly_demand: NDArray  # Shape: (n_days * 24,) - demand per hour
    confidence: float = 0.8
    
    def get_demand_for_date(self, target_date: date) -> NDArray:
        """Get hourly demand for a specific date."""
        if target_date not in self.dates:
            return np.zeros(24)
        
        idx = self.dates.index(target_date)
        return self.hourly_demand[idx * 24:(idx + 1) * 24]
    
    def get_period_demand(self, start_idx: int, end_idx: int) -> float:
        """Get total demand for a period."""
        return float(np.sum(self.hourly_demand[start_idx:end_idx]))


@dataclass
class ScheduleAssignment:
    """Single staff assignment."""
    
    staff_id: str
    date: date
    shift: ShiftDefinition
    hours: float
    cost: float
    
    def overlaps(self, other: "ScheduleAssignment") -> bool:
        """Check if this assignment overlaps with another."""
        if self.date != other.date:
            return False
        
        self_start = self.shift.start_hour
        self_end = self.shift.end_hour
        other_start = other.shift.start_hour
        other_end = other.shift.end_hour
        
        # Handle overnight shifts
        if self_end < self_start:  # Wraps midnight
            self_end += 24
        if other_end < other_start:
            other_end += 24
        
        return not (self_end <= other_start or other_end <= self_start)


@dataclass
class CoverageAnalysis:
    """Analysis of schedule coverage."""
    
    total_hours_needed: float
    total_hours_scheduled: float
    coverage_rate: float
    understaffed_periods: list[dict]
    overstaffed_periods: list[dict]
    skill_coverage: dict[str, float]
    
    @property
    def is_adequately_covered(self) -> bool:
        """Check if coverage meets minimum requirements."""
        return self.coverage_rate >= 0.95 and len(self.understaffed_periods) == 0


class StaffingOptimizer:
    """
    Optimize CAH staffing schedules.
    
    Optimization Model:
    min_x Σ_{s,t} c_s · x_{s,t} + Σ_t λ · max(0, d_t - Σ_s p_s · x_{s,t})
    
    Subject to:
    - Σ_t x_{s,t} ≤ H_s  ∀s  (max hours per staff)
    - Σ_s x_{s,t} ≥ n_{min,t}  ∀t  (minimum staffing)
    - x_{s,t} ∈ {0, 1, ..., 12}  (valid shift hours)
    
    Uses a simplified greedy approach for MV-CAHI compliance
    (full MIP solver like cvxpy optional).
    """
    
    def __init__(self, constraints: Optional[StaffingConstraints] = None):
        self.constraints = constraints or StaffingConstraints()
        
        # Standard shift definitions
        self.shifts = [
            ShiftDefinition("day", 7, 12),
            ShiftDefinition("evening", 15, 8, differential=0.05),
            ShiftDefinition("night", 23, 8, differential=0.10),
            ShiftDefinition("day_short", 7, 8),
            ShiftDefinition("pm_short", 15, 8),
        ]
    
    def optimize_schedule(
        self,
        planning_horizon: int,
        demand_forecast: DemandForecast,
        staff_pool: list[StaffMember],
        start_date: Optional[date] = None,
    ) -> Schedule:
        """
        Generate optimal staffing schedule.
        
        Args:
            planning_horizon: Number of days to schedule
            demand_forecast: Forecasted demand
            staff_pool: Available staff members
            start_date: Start date for schedule
            
        Returns:
            Optimized Schedule
        """
        if start_date is None:
            start_date = date.today()
        
        n_staff = len(staff_pool)
        n_periods = planning_horizon * 24
        
        # Initialize assignments matrix
        assignments = np.zeros((n_staff, n_periods))
        
        # Track hours used by each staff member
        hours_used = {s.staff_id: 0.0 for s in staff_pool}
        
        # Greedy scheduling algorithm
        for day_offset in range(planning_horizon):
            current_date = start_date + timedelta(days=day_offset)
            
            # Get demand for this day
            day_demand = demand_forecast.get_demand_for_date(current_date)
            
            # Schedule each shift period
            for shift in self.shifts:
                period_start = day_offset * 24 + shift.start_hour
                period_end = period_start + shift.duration_hours
                
                # Calculate period demand
                if period_end <= n_periods:
                    period_demand = float(np.mean(day_demand[shift.start_hour:shift.start_hour + shift.duration_hours]))
                else:
                    period_demand = float(np.mean(day_demand[shift.start_hour:]))
                
                # Required staff for this shift
                required = max(
                    self.constraints.min_staff_per_period,
                    int(math.ceil(period_demand))
                )
                
                # Find available staff
                available = self._get_available_staff(
                    staff_pool,
                    hours_used,
                    current_date,
                    shift,
                )
                
                # Assign staff (greedy: cheapest first)
                assigned = 0
                for staff in sorted(available, key=lambda s: s.hourly_cost):
                    if assigned >= required:
                        break
                    
                    if hours_used[staff.staff_id] + shift.duration_hours <= staff.max_hours:
                        # Make assignment
                        staff_idx = staff_pool.index(staff)
                        for h in range(shift.duration_hours):
                            hour_idx = period_start + h
                            if hour_idx < n_periods:
                                assignments[staff_idx, hour_idx] = 1
                        
                        hours_used[staff.staff_id] += shift.duration_hours
                        assigned += 1
        
        # Calculate total cost
        total_cost = self._calculate_cost(assignments, staff_pool)
        
        # Analyze coverage
        coverage = self._analyze_coverage(assignments, demand_forecast, staff_pool)
        
        return Schedule(
            assignments=assignments,
            total_cost=total_cost,
            staff_pool=staff_pool,
            coverage_analysis={
                "coverage_rate": coverage.coverage_rate,
                "understaffed_periods": len(coverage.understaffed_periods),
                "total_hours": coverage.total_hours_scheduled,
            },
        )
    
    def _get_available_staff(
        self,
        staff_pool: list[StaffMember],
        hours_used: dict[str, float],
        target_date: date,
        shift: ShiftDefinition,
    ) -> list[StaffMember]:
        """Get staff available for a shift."""
        available = []
        
        for staff in staff_pool:
            # Check hours limit
            remaining_hours = staff.max_hours - hours_used[staff.staff_id]
            if remaining_hours < shift.duration_hours:
                continue
            
            # Check unavailable dates
            if target_date in staff.unavailable_dates:
                continue
            
            # Check shift preferences (optional)
            if staff.preferred_shifts and shift.name not in staff.preferred_shifts:
                # Still available, just not preferred
                pass
            
            available.append(staff)
        
        return available
    
    def _calculate_cost(
        self,
        assignments: NDArray,
        staff_pool: list[StaffMember],
    ) -> float:
        """Calculate total schedule cost."""
        total_cost = 0.0
        
        for staff_idx, staff in enumerate(staff_pool):
            hours = float(np.sum(assignments[staff_idx]))
            base_cost = hours * staff.hourly_cost
            
            # Add overtime premium if over 40 hours/week
            # (Simplified - assumes schedule is one week)
            if hours > self.constraints.max_hours_per_week:
                overtime_hours = hours - self.constraints.max_hours_per_week
                overtime_premium = overtime_hours * staff.hourly_cost * (self.constraints.overtime_multiplier - 1)
                base_cost += overtime_premium
            
            total_cost += base_cost
        
        return total_cost
    
    def _analyze_coverage(
        self,
        assignments: NDArray,
        demand_forecast: DemandForecast,
        staff_pool: list[StaffMember],
    ) -> CoverageAnalysis:
        """Analyze schedule coverage."""
        n_periods = assignments.shape[1]
        
        # Calculate coverage per period
        coverage_per_period = np.sum(assignments, axis=0)
        
        # Compare to demand
        demand = demand_forecast.hourly_demand[:n_periods]
        
        understaffed = []
        overstaffed = []
        
        for t in range(n_periods):
            if coverage_per_period[t] < demand[t]:
                understaffed.append({
                    "period": t,
                    "scheduled": coverage_per_period[t],
                    "needed": demand[t],
                    "gap": demand[t] - coverage_per_period[t],
                })
            elif coverage_per_period[t] > demand[t] * 1.5:  # 50% overstaffed
                overstaffed.append({
                    "period": t,
                    "scheduled": coverage_per_period[t],
                    "needed": demand[t],
                })
        
        total_hours_needed = float(np.sum(demand))
        total_hours_scheduled = float(np.sum(coverage_per_period))
        coverage_rate = min(1.0, total_hours_scheduled / total_hours_needed) if total_hours_needed > 0 else 1.0
        
        # Skill coverage analysis
        skill_coverage = {}
        for skill in self.constraints.required_skills:
            skill_staff = [i for i, s in enumerate(staff_pool) if skill in s.skills]
            skill_hours = float(np.sum(assignments[skill_staff])) if skill_staff else 0
            skill_coverage[skill] = skill_hours / total_hours_scheduled if total_hours_scheduled > 0 else 0
        
        return CoverageAnalysis(
            total_hours_needed=total_hours_needed,
            total_hours_scheduled=total_hours_scheduled,
            coverage_rate=coverage_rate,
            understaffed_periods=understaffed,
            overstaffed_periods=overstaffed,
            skill_coverage=skill_coverage,
        )
    
    def recommend_staffing_levels(
        self,
        demand_forecast: DemandForecast,
    ) -> dict[str, Any]:
        """
        Recommend staffing levels based on forecast.
        
        Args:
            demand_forecast: Demand forecast
            
        Returns:
            Staffing recommendations
        """
        # Analyze demand patterns
        hourly_demand = demand_forecast.hourly_demand
        
        # Peak and average by time of day
        n_days = len(hourly_demand) // 24
        daily_patterns = hourly_demand.reshape(n_days, 24) if n_days > 0 else hourly_demand.reshape(1, -1)
        
        avg_by_hour = np.mean(daily_patterns, axis=0)
        peak_by_hour = np.max(daily_patterns, axis=0)
        
        # Calculate FTE needs
        total_weekly_hours = float(np.sum(hourly_demand[:168])) if len(hourly_demand) >= 168 else float(np.sum(hourly_demand))
        fte_needed = total_weekly_hours / 40  # 40-hour work week
        
        # Add buffer for time off, training, etc.
        fte_recommended = fte_needed * 1.2
        
        return {
            "fte_needed_base": round(fte_needed, 1),
            "fte_recommended": round(fte_recommended, 1),
            "peak_staffing_hour": int(np.argmax(avg_by_hour)),
            "peak_staffing_level": float(peak_by_hour[np.argmax(peak_by_hour)]),
            "minimum_staffing": max(self.constraints.min_staff_per_period, int(np.min(avg_by_hour))),
            "average_demand": float(np.mean(hourly_demand)),
            "demand_variability": float(np.std(hourly_demand)),
            "by_shift": {
                "day": float(np.mean(avg_by_hour[7:19])),
                "evening": float(np.mean(avg_by_hour[15:23])),
                "night": float(np.mean(np.concatenate([avg_by_hour[23:], avg_by_hour[:7]]))),
            },
        }
    
    def evaluate_schedule_quality(
        self,
        schedule: Schedule,
        demand_forecast: DemandForecast,
    ) -> dict[str, Any]:
        """
        Evaluate quality of a schedule.
        
        Args:
            schedule: Schedule to evaluate
            demand_forecast: Demand forecast
            
        Returns:
            Quality metrics
        """
        coverage = self._analyze_coverage(
            schedule.assignments,
            demand_forecast,
            schedule.staff_pool,
        )
        
        # Calculate various quality metrics
        quality_score = 100.0
        
        # Penalize understaffing
        quality_score -= len(coverage.understaffed_periods) * 5
        
        # Penalize overstaffing (but less severely)
        quality_score -= len(coverage.overstaffed_periods) * 2
        
        # Bonus for skill coverage
        for skill, coverage_pct in coverage.skill_coverage.items():
            if coverage_pct < 0.9:
                quality_score -= 10
        
        quality_score = max(0, min(100, quality_score))
        
        return {
            "quality_score": quality_score,
            "coverage_rate": coverage.coverage_rate,
            "understaffed_periods": len(coverage.understaffed_periods),
            "overstaffed_periods": len(coverage.overstaffed_periods),
            "total_cost": schedule.total_cost,
            "cost_per_hour": schedule.total_cost / coverage.total_hours_scheduled if coverage.total_hours_scheduled > 0 else 0,
            "skill_coverage": coverage.skill_coverage,
            "recommendation": "Good" if quality_score >= 80 else "Needs Review" if quality_score >= 60 else "Poor",
        }


def create_sample_staff_pool(n_staff: int = 20) -> list[StaffMember]:
    """Create a sample staff pool for testing."""
    staff = []
    
    # RNs
    for i in range(int(n_staff * 0.5)):
        staff.append(StaffMember(
            staff_id=f"RN_{i+1:03d}",
            name=f"RN {i+1}",
            role="RN",
            skills={"rn", "assessment", "medication"},
            hourly_cost=35.0 + (i % 5) * 2,  # Experience-based variance
            max_hours=40.0,
            productivity_factor=1.0,
        ))
    
    # CNAs
    for i in range(int(n_staff * 0.3)):
        staff.append(StaffMember(
            staff_id=f"CNA_{i+1:03d}",
            name=f"CNA {i+1}",
            role="CNA",
            skills={"cna", "patient_care"},
            hourly_cost=18.0 + (i % 3) * 1,
            max_hours=40.0,
            productivity_factor=0.8,
        ))
    
    # LPNs
    for i in range(int(n_staff * 0.2)):
        staff.append(StaffMember(
            staff_id=f"LPN_{i+1:03d}",
            name=f"LPN {i+1}",
            role="LPN",
            skills={"lpn", "medication", "patient_care"},
            hourly_cost=25.0 + (i % 3) * 1,
            max_hours=40.0,
            productivity_factor=0.9,
        ))
    
    return staff

