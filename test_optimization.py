"""
Test suite for CAH optimization module.

Test Categories:
1. Unit Tests — Individual function correctness
2. Integration Tests — Component interactions
3. Constraint Verification — Regulatory compliance
4. Convergence Tests — Solver behavior
5. Mathematical Property Tests — Theoretical guarantees

Run with: pytest tests/optimization/ -v
"""

import pytest
import numpy as np
from typing import Tuple

# Import module components
from cah.optimization.models import (
    CAHParameters,
    QualityBenchmarks,
    DecisionVariables,
    OptimizationResult,
    ParetoPoint,
    ConstraintStatus,
    OptimizationStatus,
)
from cah.optimization.objectives import CAHObjectiveFunctions
from cah.optimization.constraints import CAHConstraints, bed_cap, census_capacity, nursing_ratio
from cah.optimization.solver import CAHOptimizer
from cah.optimization.robust import RobustCAHOptimizer, UncertaintySet
from cah.optimization.pareto import ParetoFrontExplorer, ParetoFront


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def default_params() -> CAHParameters:
    """Default CAH financial parameters."""
    return CAHParameters()


@pytest.fixture
def default_benchmarks() -> QualityBenchmarks:
    """Default quality benchmarks."""
    return QualityBenchmarks()


@pytest.fixture
def default_variables() -> DecisionVariables:
    """Default decision variable definitions."""
    return DecisionVariables()


@pytest.fixture
def feasible_point() -> np.ndarray:
    """A known feasible point within all constraints."""
    return np.array([
        15.0,    # acute_beds
        5.0,     # swing_beds (total = 20 < 25)
        35.0,    # nursing_fte
        5.0,     # provider_fte
        8.0,     # avg_daily_census
        6000.0,  # ed_visits
        15000.0, # outpatient_visits
        1.0,     # cmi
    ])


@pytest.fixture
def infeasible_point_beds() -> np.ndarray:
    """Point violating bed cap constraint."""
    return np.array([
        20.0,    # acute_beds
        10.0,    # swing_beds (total = 30 > 25) VIOLATION
        35.0,    # nursing_fte
        5.0,     # provider_fte
        8.0,     # avg_daily_census
        6000.0,  # ed_visits
        15000.0, # outpatient_visits
        1.0,     # cmi
    ])


@pytest.fixture
def objectives(default_params, default_benchmarks) -> CAHObjectiveFunctions:
    """Objective function calculator."""
    return CAHObjectiveFunctions(default_params, default_benchmarks)


@pytest.fixture
def constraints() -> CAHConstraints:
    """Constraint manager."""
    return CAHConstraints(margin_floor=0.05)


@pytest.fixture
def optimizer() -> CAHOptimizer:
    """Default optimizer."""
    return CAHOptimizer(theta=0.6, margin_floor=0.05)


# =============================================================================
# UNIT TESTS: PARAMETERS
# =============================================================================

class TestCAHParameters:
    """Tests for CAHParameters dataclass."""
    
    def test_default_initialization(self, default_params):
        """Default parameters are initialized correctly."""
        assert default_params.alpha_1 == 12_847.0
        assert default_params.beta_1 == 78_500.0
        assert default_params.alos == 3.2
    
    def test_to_dict(self, default_params):
        """Parameters export to dictionary."""
        d = default_params.to_dict()
        assert "alpha_1" in d
        assert "beta_3" in d
        assert d["alos"] == 3.2
    
    def test_sample_returns_new_instance(self, default_params):
        """Sampling creates new parameter instance."""
        rng = np.random.default_rng(42)
        sampled = default_params.sample(rng)
        
        assert isinstance(sampled, CAHParameters)
        assert sampled.alpha_1 != default_params.alpha_1  # Sampled values differ
    
    def test_sample_reproducibility(self, default_params):
        """Sampling with same seed produces same results."""
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        
        sampled1 = default_params.sample(rng1)
        sampled2 = default_params.sample(rng2)
        
        assert sampled1.alpha_1 == sampled2.alpha_1


class TestQualityBenchmarks:
    """Tests for QualityBenchmarks dataclass."""
    
    def test_weights_sum_to_one(self, default_benchmarks):
        """Quality weights must sum to 1.0."""
        total = sum(default_benchmarks.weights.values())
        assert abs(total - 1.0) < 1e-6
    
    def test_all_measures_have_benchmarks(self, default_benchmarks):
        """All measures have corresponding benchmarks and directions."""
        for measure in default_benchmarks.weights.keys():
            assert measure in default_benchmarks.benchmarks
            assert measure in default_benchmarks.direction
    
    def test_invalid_weights_raise_error(self):
        """Non-normalized weights raise ValueError."""
        with pytest.raises(ValueError):
            QualityBenchmarks(weights={
                "ed_throughput": 0.5,
                "pain_management": 0.5,
                "hcahps_overall": 0.5,  # Sum = 1.5 > 1
                "opioid_concurrent": 0.0,
                "readmission_30d": 0.0,
                "falls_injury": 0.0,
                "cauti_rate": 0.0,
            })


class TestDecisionVariables:
    """Tests for DecisionVariables dataclass."""
    
    def test_bounds_count(self, default_variables):
        """Correct number of variable bounds."""
        assert len(default_variables.bounds) == 8
        assert default_variables.n_variables == 8
    
    def test_get_center(self, default_variables):
        """Center point is midpoint of bounds."""
        center = default_variables.get_center()
        assert len(center) == 8
        assert center[0] == (5 + 25) / 2  # acute_beds
    
    def test_is_feasible_valid_point(self, default_variables, feasible_point):
        """Valid point passes feasibility check."""
        assert default_variables.is_feasible(feasible_point)
    
    def test_is_feasible_out_of_bounds(self, default_variables):
        """Out-of-bounds point fails feasibility check."""
        invalid = np.array([100, 0, 0, 0, 0, 0, 0, 0])  # acute_beds > 25
        assert not default_variables.is_feasible(invalid)
    
    def test_project_clips_to_bounds(self, default_variables):
        """Projection clips values to bounds."""
        invalid = np.array([100, -5, 0, 0, 0, 0, 0, 0])
        projected = default_variables.project(invalid)
        
        assert projected[0] == 25  # Clipped to upper bound
        assert projected[1] == 0   # Clipped to lower bound


# =============================================================================
# UNIT TESTS: OBJECTIVES
# =============================================================================

class TestCAHObjectiveFunctions:
    """Tests for objective function calculations."""
    
    def test_revenue_positive(self, objectives, feasible_point):
        """Revenue is positive for feasible point."""
        revenue = objectives.revenue(feasible_point)
        assert revenue > 0
    
    def test_revenue_decomposition(self, objectives, feasible_point):
        """Revenue components sum to total."""
        decomposition = objectives.revenue_decomposition(feasible_point)
        
        component_sum = (
            decomposition["inpatient"] +
            decomposition["ed"] +
            decomposition["outpatient"] +
            decomposition["swing"]
        )
        
        assert abs(component_sum - decomposition["total"]) < 1e-6
    
    def test_cost_positive(self, objectives, feasible_point):
        """Cost is positive for feasible point."""
        cost = objectives.cost(feasible_point)
        assert cost > 0
    
    def test_profit_equals_revenue_minus_cost(self, objectives, feasible_point):
        """Profit = Revenue - Cost."""
        revenue = objectives.revenue(feasible_point)
        cost = objectives.cost(feasible_point)
        profit = objectives.profit(feasible_point)
        
        assert abs(profit - (revenue - cost)) < 1e-6
    
    def test_margin_range(self, objectives, feasible_point):
        """Margin is in reasonable range."""
        margin = objectives.margin(feasible_point)
        assert -1.0 <= margin <= 1.0
    
    def test_composite_quality_range(self, objectives, feasible_point):
        """Composite quality is in [0, 1]."""
        quality = objectives.composite_quality(feasible_point)
        assert 0.0 <= quality <= 1.0
    
    def test_quality_scores_all_measures(self, objectives, feasible_point):
        """Quality scores include all measures."""
        scores = objectives.quality_scores(feasible_point)
        
        expected_measures = [
            "ed_throughput", "pain_management", "hcahps_overall",
            "opioid_concurrent", "readmission_30d", "falls_injury", "cauti_rate"
        ]
        
        for measure in expected_measures:
            assert measure in scores
    
    def test_gradient_dimension(self, objectives, feasible_point):
        """Gradients have correct dimension."""
        rev_grad = objectives.revenue_gradient(feasible_point)
        cost_grad = objectives.cost_gradient(feasible_point)
        
        assert len(rev_grad) == 8
        assert len(cost_grad) == 8
    
    def test_gradient_numerical_agreement(self, objectives, feasible_point):
        """Analytical gradient agrees with numerical gradient."""
        x = feasible_point
        h = 1e-5
        
        # Numerical gradient for revenue
        numerical_grad = np.zeros(8)
        for i in range(8):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += h
            x_minus[i] -= h
            numerical_grad[i] = (objectives.revenue(x_plus) - objectives.revenue(x_minus)) / (2 * h)
        
        analytical_grad = objectives.revenue_gradient(x)
        
        # Check agreement (relaxed tolerance for finite differences)
        np.testing.assert_allclose(analytical_grad, numerical_grad, rtol=1e-3, atol=1e-2)


# =============================================================================
# UNIT TESTS: CONSTRAINTS
# =============================================================================

class TestCAHConstraints:
    """Tests for constraint definitions and checking."""
    
    def test_bed_cap_satisfied(self, constraints, feasible_point):
        """Bed cap satisfied for valid point."""
        residual = bed_cap(feasible_point)
        assert residual >= 0  # 25 - (15 + 5) = 5 ≥ 0
    
    def test_bed_cap_violated(self, constraints, infeasible_point_beds):
        """Bed cap violated for invalid point."""
        residual = bed_cap(infeasible_point_beds)
        assert residual < 0  # 25 - (20 + 10) = -5 < 0
    
    def test_census_capacity_satisfied(self, feasible_point):
        """Census capacity satisfied for valid point."""
        residual = census_capacity(feasible_point)
        assert residual >= 0  # 0.85 × 15 - 8 = 4.75 ≥ 0
    
    def test_nursing_ratio_satisfied(self, feasible_point):
        """Nursing ratio satisfied for valid point."""
        residual = nursing_ratio(feasible_point)
        assert residual >= 0  # 35 - 0.5 × 8 = 31 ≥ 0
    
    def test_check_all_returns_dict(self, constraints, feasible_point):
        """check_all returns dictionary of statuses."""
        status = constraints.check_all(feasible_point)
        
        assert isinstance(status, dict)
        assert all(isinstance(v, ConstraintStatus) for v in status.values())
    
    def test_is_feasible_valid_point(self, constraints, feasible_point):
        """Valid point is feasible."""
        assert constraints.is_feasible(feasible_point)
    
    def test_is_feasible_invalid_point(self, constraints, infeasible_point_beds):
        """Invalid point is infeasible."""
        assert not constraints.is_feasible(infeasible_point_beds)
    
    def test_get_violations_empty_for_feasible(self, constraints, feasible_point):
        """No violations for feasible point."""
        violations = constraints.get_violations(feasible_point)
        assert len(violations) == 0
    
    def test_get_violations_reports_violation(self, constraints, infeasible_point_beds):
        """Violations reported for infeasible point."""
        violations = constraints.get_violations(infeasible_point_beds)
        assert "bed_cap" in violations
        assert violations["bed_cap"] > 0
    
    def test_scipy_constraints_format(self, constraints):
        """Scipy constraints have correct format."""
        scipy_constraints = constraints.get_scipy_constraints()
        
        assert isinstance(scipy_constraints, list)
        for c in scipy_constraints:
            assert "type" in c
            assert "fun" in c
            assert c["type"] == "ineq"
    
    def test_licq_verification(self, constraints, feasible_point):
        """LICQ check returns boolean and explanation."""
        holds, explanation = constraints.check_licq(feasible_point)
        
        assert isinstance(holds, bool)
        assert isinstance(explanation, str)


# =============================================================================
# INTEGRATION TESTS: SOLVER
# =============================================================================

class TestCAHOptimizer:
    """Integration tests for the optimizer."""
    
    def test_optimize_returns_result(self, optimizer):
        """Optimization returns OptimizationResult."""
        result = optimizer.optimize(multi_start=3)
        
        assert isinstance(result, OptimizationResult)
        assert hasattr(result, "x")
        assert hasattr(result, "margin")
        assert hasattr(result, "quality")
    
    def test_optimize_finds_feasible_solution(self, optimizer):
        """Optimizer finds a feasible solution."""
        result = optimizer.optimize(multi_start=5)
        
        assert result.constraints_satisfied
        assert result.margin >= 0.05 - 1e-6  # Margin floor
    
    def test_optimize_respects_bed_cap(self, optimizer):
        """Solution respects 25-bed cap."""
        result = optimizer.optimize(multi_start=3)
        
        total_beds = result.x[0] + result.x[1]
        assert total_beds <= 25 + 1e-6
    
    def test_optimize_multi_start_improves(self, optimizer):
        """More starts generally find better solutions."""
        result_1 = optimizer.optimize(multi_start=1, seed=42)
        result_5 = optimizer.optimize(multi_start=5, seed=42)
        
        # With more starts, objective should be at least as good
        assert result_5.objective_value >= result_1.objective_value - 0.01
    
    def test_optimize_from_initial_point(self, optimizer, feasible_point):
        """Optimization from specified initial point."""
        result = optimizer.optimize(x0=feasible_point, multi_start=1)
        
        assert result.status != OptimizationStatus.INFEASIBLE
    
    def test_sensitivity_analysis_returns_dict(self, optimizer, feasible_point):
        """Sensitivity analysis returns dictionary."""
        sensitivities = optimizer.sensitivity_analysis(feasible_point)
        
        assert isinstance(sensitivities, dict)
        assert "acute_beds" in sensitivities
        assert "dMargin_dx" in sensitivities["acute_beds"]
    
    def test_monte_carlo_returns_statistics(self, optimizer, feasible_point):
        """Monte Carlo analysis returns statistical summaries."""
        mc_result = optimizer.monte_carlo_analysis(feasible_point, n_simulations=100)
        
        assert "margin" in mc_result
        assert "mean" in mc_result["margin"]
        assert "ci_5" in mc_result["margin"]
        assert "p_target_achieved" in mc_result["margin"]
    
    def test_dinkelbach_convergence(self, optimizer, feasible_point):
        """Dinkelbach algorithm converges."""
        result = optimizer.optimize_charnes_cooper(x0=feasible_point)
        
        assert result.status != OptimizationStatus.INFEASIBLE
        assert result.margin > -1.0


# =============================================================================
# MATHEMATICAL PROPERTY TESTS
# =============================================================================

class TestMathematicalProperties:
    """Tests for mathematical properties and theoretical guarantees."""
    
    def test_pareto_dominance_transitivity(self):
        """Pareto dominance is transitive."""
        p1 = ParetoPoint(x=np.zeros(8), margin=0.10, quality=0.80, epsilon=0)
        p2 = ParetoPoint(x=np.zeros(8), margin=0.08, quality=0.75, epsilon=0)
        p3 = ParetoPoint(x=np.zeros(8), margin=0.06, quality=0.70, epsilon=0)
        
        assert p1.dominates(p2)
        assert p2.dominates(p3)
        assert p1.dominates(p3)  # Transitivity
    
    def test_pareto_front_no_dominated_points(self):
        """Pareto front contains no dominated points."""
        front = ParetoFront()
        
        front.add(ParetoPoint(x=np.zeros(8), margin=0.10, quality=0.70, epsilon=0))
        front.add(ParetoPoint(x=np.zeros(8), margin=0.08, quality=0.80, epsilon=0))
        front.add(ParetoPoint(x=np.zeros(8), margin=0.06, quality=0.90, epsilon=0))
        front.add(ParetoPoint(x=np.zeros(8), margin=0.05, quality=0.75, epsilon=0))  # Dominated
        
        # Dominated point should be filtered
        assert len(front.points) == 3
        
        # No point dominates another
        for i, p1 in enumerate(front.points):
            for j, p2 in enumerate(front.points):
                if i != j:
                    assert not p1.dominates(p2)
    
    def test_quality_monotonicity_in_nursing(self, objectives):
        """Quality increases with nursing FTE (Aiken et al.)."""
        x_low = np.array([15, 5, 25, 5, 8, 6000, 15000, 1.0])
        x_high = np.array([15, 5, 45, 5, 8, 6000, 15000, 1.0])
        
        q_low = objectives.composite_quality(x_low)
        q_high = objectives.composite_quality(x_high)
        
        assert q_high > q_low
    
    def test_margin_sensitivity_to_revenue(self, objectives):
        """Margin increases with case mix (higher reimbursement)."""
        x_low_cmi = np.array([15, 5, 35, 5, 8, 6000, 15000, 0.9])
        x_high_cmi = np.array([15, 5, 35, 5, 8, 6000, 15000, 1.3])
        
        margin_low = objectives.margin(x_low_cmi)
        margin_high = objectives.margin(x_high_cmi)
        
        assert margin_high > margin_low
    
    def test_constraint_qualification_linear_constraints(self, constraints, feasible_point):
        """Linear constraints satisfy LICQ generically."""
        holds, _ = constraints.check_licq(feasible_point)
        
        # For a generic feasible point with few active constraints, LICQ should hold
        # (unless we're exactly at a vertex with many active constraints)
        assert holds or len(constraints.get_binding(feasible_point)) >= 8


# =============================================================================
# ROBUST OPTIMIZATION TESTS
# =============================================================================

class TestRobustOptimization:
    """Tests for robust optimization under uncertainty."""
    
    def test_uncertainty_set_initialization(self):
        """Uncertainty set initializes correctly."""
        uncertainty = UncertaintySet(gamma=3.0)
        
        assert uncertainty.gamma == 3.0
        assert uncertainty.violation_probability_bound() > 0
    
    def test_probability_bound_decreases_with_gamma(self):
        """Higher Γ gives lower violation probability."""
        u1 = UncertaintySet(gamma=2.0)
        u2 = UncertaintySet(gamma=4.0)
        
        assert u2.violation_probability_bound() < u1.violation_probability_bound()
    
    def test_recommended_gamma_inverts_probability(self):
        """recommended_gamma inverts violation probability."""
        u = UncertaintySet()
        target_prob = 0.05
        
        recommended = u.recommended_gamma(target_prob)
        u2 = UncertaintySet(gamma=recommended)
        
        assert abs(u2.violation_probability_bound() - target_prob) < 0.01
    
    def test_robust_optimizer_returns_result(self):
        """Robust optimizer returns valid result."""
        uncertainty = UncertaintySet(gamma=2.0)
        optimizer = RobustCAHOptimizer(uncertainty_set=uncertainty)
        
        result = optimizer.optimize(multi_start=3)
        
        assert isinstance(result, OptimizationResult)


# =============================================================================
# PARETO FRONT TESTS
# =============================================================================

class TestParetoFrontExplorer:
    """Tests for Pareto front exploration."""
    
    def test_explore_returns_pareto_front(self):
        """Explorer returns ParetoFront object."""
        explorer = ParetoFrontExplorer()
        front = explorer.explore(n_points=5, seed=42)
        
        assert isinstance(front, ParetoFront)
        assert len(front.points) > 0
    
    def test_explore_points_are_feasible(self):
        """All Pareto points are feasible."""
        explorer = ParetoFrontExplorer()
        front = explorer.explore(n_points=5, seed=42)
        
        variables = DecisionVariables()
        constraints = CAHConstraints()
        
        for point in front.points:
            assert variables.is_feasible(point.x)
            assert constraints.is_feasible(point.x)
    
    def test_pareto_front_ideal_nadir(self):
        """Ideal and nadir points are computed correctly."""
        front = ParetoFront()
        front.add(ParetoPoint(x=np.zeros(8), margin=0.10, quality=0.70, epsilon=0))
        front.add(ParetoPoint(x=np.zeros(8), margin=0.05, quality=0.90, epsilon=0))
        
        ideal = front.get_ideal_point()
        nadir = front.get_nadir_point()
        
        assert ideal == (0.10, 0.90)  # Max of each
        assert nadir == (0.05, 0.70)  # Min of each
    
    def test_hypervolume_positive(self):
        """Hypervolume is positive for non-empty front."""
        explorer = ParetoFrontExplorer()
        front = explorer.explore(n_points=5, seed=42)
        
        hv = explorer.hypervolume(front)
        assert hv > 0


# =============================================================================
# REGRESSION TESTS
# =============================================================================

class TestRegressionScenarios:
    """Regression tests for known scenarios."""
    
    def test_mvcahi_reference_case(self):
        """Test against MV-CAHI reference architecture."""
        # MV-CAHI: 25 beds, 10 acute/15 swing, $15-25M revenue, 65% Medicare
        x_mvcahi = np.array([
            10.0,    # acute_beds
            10.0,    # swing_beds
            32.0,    # nursing_fte
            4.0,     # provider_fte
            6.0,     # avg_daily_census
            5000.0,  # ed_visits
            12000.0, # outpatient_visits
            0.95,    # cmi
        ])
        
        objectives = CAHObjectiveFunctions()
        constraints = CAHConstraints()
        
        # Should be feasible
        assert constraints.is_feasible(x_mvcahi)
        
        # Revenue in expected range
        revenue = objectives.revenue(x_mvcahi)
        assert 10_000_000 < revenue < 30_000_000
    
    def test_high_acuity_scenario(self):
        """Test high-acuity scenario with elevated CMI."""
        x_high_acuity = np.array([
            18.0,    # acute_beds (more acute care)
            5.0,     # swing_beds
            45.0,    # nursing_fte (higher staffing)
            8.0,     # provider_fte (more providers)
            12.0,    # avg_daily_census
            8000.0,  # ed_visits
            20000.0, # outpatient_visits
            1.3,     # cmi (higher complexity)
        ])
        
        objectives = CAHObjectiveFunctions()
        
        # Higher CMI should yield higher per-case revenue
        x_low_cmi = x_high_acuity.copy()
        x_low_cmi[7] = 1.0
        
        revenue_high = objectives.revenue(x_high_acuity)
        revenue_low = objectives.revenue(x_low_cmi)
        
        assert revenue_high > revenue_low


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Performance and MV-CAHI compliance tests."""
    
    def test_optimization_time_limit(self, optimizer):
        """Optimization completes within MV-CAHI time limit (<5 seconds)."""
        import time
        
        start = time.time()
        optimizer.optimize(multi_start=10)
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Optimization took {elapsed:.2f}s, exceeds 5s limit"
    
    def test_monte_carlo_reasonable_time(self, optimizer, feasible_point):
        """Monte Carlo completes in reasonable time."""
        import time
        
        start = time.time()
        optimizer.monte_carlo_analysis(feasible_point, n_simulations=1000)
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Monte Carlo took {elapsed:.2f}s for 1000 simulations"


# =============================================================================
# RUN CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
