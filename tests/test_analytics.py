"""
Tests for analytics module.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from cah_engine.analytics.predictive import (
    CensusForecaster,
    TransferRiskModel,
    DenialProbabilityModel,
)
from cah_engine.analytics.gap_analyzer import GapAnalyzer, CAH_BENCHMARKS
from cah_engine.analytics.scenario_simulator import (
    ScenarioSimulator,
    SimulationConfig,
    FacilityContext,
)
from cah_engine.core.models import ClinicalEncounter, CostReportMetrics
from cah_engine.core.enums import EncounterType


class TestCensusForecaster:
    """Tests for census forecasting."""
    
    def test_train_requires_minimum_data(self):
        """Test that training requires minimum data."""
        forecaster = CensusForecaster()
        
        # Too little data
        with pytest.raises(ValueError, match="Minimum 30 days"):
            forecaster.train([(date(2024, 1, i), 10.0) for i in range(1, 20)])
    
    def test_train_and_predict(self):
        """Test training and prediction."""
        forecaster = CensusForecaster()
        
        # Generate synthetic data
        base_date = date(2024, 1, 1)
        history = [
            (base_date + timedelta(days=i), 10.0 + (i % 7))  # Weekly pattern
            for i in range(90)
        ]
        
        forecaster.train(history)
        
        assert forecaster.trained
        assert forecaster.training_samples == 90
        
        # Generate forecast
        result = forecaster.predict(horizon=7)
        
        assert len(result.point_forecast) == 7
        assert len(result.lower_bound) == 7
        assert len(result.upper_bound) == 7
        assert all(f >= 0 for f in result.point_forecast)  # Census can't be negative
    
    def test_prediction_requires_training(self):
        """Test that prediction requires training."""
        forecaster = CensusForecaster()
        
        with pytest.raises(ValueError, match="must be trained"):
            forecaster.predict(horizon=7)
    
    def test_incremental_update(self):
        """Test incremental model update."""
        forecaster = CensusForecaster()
        
        # Initial training
        base_date = date(2024, 1, 1)
        history = [(base_date + timedelta(days=i), 10.0) for i in range(60)]
        forecaster.train(history)
        
        initial_mean = forecaster.mean_census
        
        # Update with higher values
        forecaster.update_incremental((base_date + timedelta(days=61), 15.0))
        
        # Mean should have increased
        assert forecaster.mean_census > initial_mean


class TestTransferRiskModel:
    """Tests for transfer risk scoring."""
    
    def test_predict_low_risk(self):
        """Test prediction for low-risk patient."""
        model = TransferRiskModel()
        model.trained = True  # Skip training for unit test
        
        encounter = ClinicalEncounter(
            encounter_id="ENC001",
            patient_id="PAT001",
            admit_datetime=datetime.now(),
            discharge_datetime=None,
            encounter_type=EncounterType.INPATIENT,
            principal_diagnosis="J18.9",  # Pneumonia
        )
        
        score = model.predict(
            encounter=encounter,
            current_census=10,
            specialist_available=True,
        )
        
        assert 0 <= score.score <= 100
        assert score.tier is not None
    
    def test_predict_high_risk(self):
        """Test prediction for high-risk patient."""
        model = TransferRiskModel()
        model.trained = True
        
        encounter = ClinicalEncounter(
            encounter_id="ENC002",
            patient_id="PAT002",
            admit_datetime=datetime.now(),
            discharge_datetime=None,
            encounter_type=EncounterType.EMERGENCY,
            principal_diagnosis="I21.0",  # STEMI
        )
        
        score = model.predict(
            encounter=encounter,
            current_census=20,
            specialist_available=False,
        )
        
        # High-risk factors should increase score
        assert score.score > 20  # Not low risk
        assert len(score.factors) > 0


class TestDenialProbabilityModel:
    """Tests for denial probability model."""
    
    def test_predict_clean_claim(self):
        """Test prediction for clean claim."""
        model = DenialProbabilityModel()
        model.trained = True
        
        result = model.predict(
            payer_type="medicare",
            diagnosis_codes=["J18.9"],
            procedure_codes=["99223"],
            has_authorization=True,
            total_charges=5000.0,
        )
        
        assert "overall" in result
        assert 0 <= result["overall"] <= 1
    
    def test_predict_high_risk_claim(self):
        """Test prediction for high-risk claim."""
        model = DenialProbabilityModel()
        model.trained = True
        
        result = model.predict(
            payer_type="commercial",
            diagnosis_codes=[],  # Missing diagnoses
            procedure_codes=[],
            has_authorization=False,
            total_charges=60000.0,  # High charges
        )
        
        # Missing diagnoses and no auth should increase risk
        assert result["overall"] > 0.5


class TestGapAnalyzer:
    """Tests for gap analysis."""
    
    def test_analyze_metrics(self):
        """Test gap analysis on cost report metrics."""
        analyzer = GapAnalyzer()
        
        metrics = CostReportMetrics(
            provider_id="123456",
            fiscal_year_end=date(2023, 12, 31),
            total_beds=25,
            staffed_beds=20,
            patient_days=4380,  # ~60% occupancy
            discharges=500,
            net_patient_revenue=Decimal("20000000"),
            total_operating_revenue=Decimal("20000000"),
            total_operating_expenses=Decimal("20400000"),  # -2% margin
            salary_expenses=Decimal("11000000"),  # 55% labor cost
        )
        
        report = analyzer.analyze_metrics(metrics)
        
        assert report.facility_id == "123456"
        assert len(report.gaps) > 0
    
    def test_analyze_margin_gap(self):
        """Test margin gap decomposition."""
        analyzer = GapAnalyzer()
        
        gap = analyzer.analyze_margin_gap(
            current=-2.0,
            target=3.0,
            denial_rate=12.0,  # Above benchmark
            labor_ratio=58.0,  # Above benchmark
            transfer_rate=10.0,
            swing_utilization=50.0,
        )
        
        assert gap.gap == 5.0
        assert len(gap.contributing_factors) > 0
        assert gap.explained_portion != 0


class TestScenarioSimulator:
    """Tests for Monte Carlo simulation."""
    
    def test_simulate_staffing_change(self):
        """Test staffing change simulation."""
        facility = FacilityContext(
            baseline_volume=500,
            revenue_per_encounter=15000.0,
        )
        config = SimulationConfig(n_iterations=1000, random_seed=42)
        simulator = ScenarioSimulator(facility, config)
        
        result = simulator.simulate_staffing_change(
            fte_change=2.0,
            labor_cost_per_fte=65000,
        )
        
        assert result.scenario_name == "Staffing Change: +2.0 FTE"
        assert result.simulation_result.mean != 0
        assert 0 <= result.simulation_result.prob_positive <= 1
    
    def test_simulate_service_expansion(self):
        """Test service expansion simulation."""
        facility = FacilityContext()
        config = SimulationConfig(n_iterations=1000, random_seed=42)
        simulator = ScenarioSimulator(facility, config)
        
        result = simulator.simulate_service_expansion(
            service_name="Cardiac Rehab",
            implementation_cost=100000,
            annual_volume_estimate=100,
            revenue_per_case=2000,
            variable_cost_per_case=800,
            fixed_cost_increase=20000,
        )
        
        assert "Cardiac Rehab" in result.scenario_name
        assert "expected_npv" in result.decision_metrics
        assert "payback_years" in result.decision_metrics
    
    def test_compare_scenarios(self):
        """Test scenario comparison."""
        facility = FacilityContext()
        config = SimulationConfig(n_iterations=500, random_seed=42)
        simulator = ScenarioSimulator(facility, config)
        
        scenarios = [
            simulator.simulate_staffing_change(fte_change=1.0),
            simulator.simulate_staffing_change(fte_change=2.0),
            simulator.simulate_staffing_change(fte_change=-1.0),
        ]
        
        comparison = simulator.compare_scenarios(scenarios)
        
        assert "best_expected" in comparison
        assert "scenarios" in comparison
        assert len(comparison["scenarios"]) == 3

