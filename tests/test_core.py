"""
Tests for core module.
"""

import pytest
from datetime import datetime, date
from decimal import Decimal

from cah_engine.core.models import (
    ClinicalEncounter,
    CostReportMetrics,
    FacilitySnapshot,
    ValidationResult,
)
from cah_engine.core.enums import EncounterType, DispositionCode
from cah_engine.core.constraints import CAHConstraints, MVCAHIConstraints


class TestClinicalEncounter:
    """Tests for ClinicalEncounter model."""
    
    def test_create_encounter(self):
        """Test creating a basic encounter."""
        encounter = ClinicalEncounter(
            encounter_id="ENC001",
            patient_id="PAT001",
            admit_datetime=datetime(2024, 1, 15, 10, 0),
            discharge_datetime=datetime(2024, 1, 17, 14, 0),
            encounter_type=EncounterType.INPATIENT,
            principal_diagnosis="J18.9",
        )
        
        assert encounter.encounter_id == "ENC001"
        assert encounter.los_hours == 52.0  # Auto-calculated
    
    def test_los_calculation(self):
        """Test LOS calculation from dates."""
        encounter = ClinicalEncounter(
            encounter_id="ENC002",
            patient_id="PAT001",
            admit_datetime=datetime(2024, 1, 15, 10, 0),
            discharge_datetime=datetime(2024, 1, 16, 10, 0),
            encounter_type=EncounterType.INPATIENT,
            principal_diagnosis="J18.9",
        )
        
        assert encounter.los_hours == 24.0
    
    def test_validate_compliant_encounter(self):
        """Test validation of compliant encounter."""
        encounter = ClinicalEncounter(
            encounter_id="ENC003",
            patient_id="PAT001",
            admit_datetime=datetime(2024, 1, 15, 10, 0),
            discharge_datetime=datetime(2024, 1, 18, 10, 0),  # 72 hours
            encounter_type=EncounterType.INPATIENT,
            principal_diagnosis="J18.9",
        )
        
        result = encounter.validate_cah_compliance()
        assert result.valid
        assert len(result.issues) == 0
    
    def test_validate_los_violation(self):
        """Test validation catches LOS violation."""
        encounter = ClinicalEncounter(
            encounter_id="ENC004",
            patient_id="PAT001",
            admit_datetime=datetime(2024, 1, 15, 10, 0),
            discharge_datetime=datetime(2024, 1, 20, 10, 0),  # 120 hours
            encounter_type=EncounterType.INPATIENT,
            principal_diagnosis="J18.9",
        )
        
        result = encounter.validate_cah_compliance()
        assert not result.valid
        assert any("96h" in issue for issue in result.issues)
    
    def test_is_transfer(self):
        """Test transfer detection."""
        encounter = ClinicalEncounter(
            encounter_id="ENC005",
            patient_id="PAT001",
            admit_datetime=datetime.now(),
            discharge_datetime=None,
            encounter_type=EncounterType.INPATIENT,
            principal_diagnosis="J18.9",
            disposition=DispositionCode.TRANSFER_ACUTE,
        )
        
        assert encounter.is_transfer()


class TestCostReportMetrics:
    """Tests for CostReportMetrics model."""
    
    def test_create_metrics(self):
        """Test creating cost report metrics."""
        metrics = CostReportMetrics(
            provider_id="123456",
            fiscal_year_end=date(2023, 12, 31),
            total_beds=25,
            staffed_beds=20,
            patient_days=6000,
            discharges=500,
            net_patient_revenue=Decimal("20000000"),
            total_operating_revenue=Decimal("22000000"),
            total_operating_expenses=Decimal("21000000"),
            salary_expenses=Decimal("11000000"),
        )
        
        assert metrics.provider_id == "123456"
        assert metrics.staffed_beds == 20
    
    def test_operating_margin_calculation(self):
        """Test operating margin calculation."""
        metrics = CostReportMetrics(
            provider_id="123456",
            fiscal_year_end=date(2023, 12, 31),
            total_operating_revenue=Decimal("20000000"),
            total_operating_expenses=Decimal("19000000"),
        )
        
        assert metrics.operating_margin == pytest.approx(5.0, rel=0.01)
    
    def test_occupancy_rate_calculation(self):
        """Test occupancy rate calculation."""
        metrics = CostReportMetrics(
            provider_id="123456",
            fiscal_year_end=date(2023, 12, 31),
            staffed_beds=20,
            patient_days=3650,  # 10 patients/day average
        )
        
        # 3650 / (20 * 365) = 50%
        assert metrics.occupancy_rate == pytest.approx(50.0, rel=0.01)
    
    def test_labor_cost_ratio(self):
        """Test labor cost ratio calculation."""
        metrics = CostReportMetrics(
            provider_id="123456",
            fiscal_year_end=date(2023, 12, 31),
            total_operating_expenses=Decimal("20000000"),
            salary_expenses=Decimal("10000000"),
        )
        
        assert metrics.labor_cost_ratio == pytest.approx(0.5, rel=0.01)


class TestFacilitySnapshot:
    """Tests for FacilitySnapshot model."""
    
    def test_create_snapshot(self):
        """Test creating facility snapshot."""
        snapshot = FacilitySnapshot(
            facility_id="FAC001",
            timestamp=datetime.now(),
            staffed_beds=25,
            occupied_beds=15,
        )
        
        assert snapshot.current_census == 15
        assert snapshot.available_beds == 10
    
    def test_occupancy_rate(self):
        """Test occupancy rate calculation."""
        snapshot = FacilitySnapshot(
            facility_id="FAC001",
            timestamp=datetime.now(),
            staffed_beds=20,
            occupied_beds=16,
        )
        
        assert snapshot.occupancy_rate == pytest.approx(80.0, rel=0.01)
    
    def test_at_capacity(self):
        """Test at capacity detection."""
        snapshot = FacilitySnapshot(
            facility_id="FAC001",
            timestamp=datetime.now(),
            staffed_beds=25,
            occupied_beds=25,
        )
        
        assert snapshot.at_capacity


class TestCAHConstraints:
    """Tests for CAH constraints."""
    
    def test_validate_bed_count_compliant(self):
        """Test bed count validation - compliant."""
        constraints = CAHConstraints()
        result = constraints.validate_bed_count(20)
        
        assert result.compliant
    
    def test_validate_bed_count_violation(self):
        """Test bed count validation - violation."""
        constraints = CAHConstraints()
        result = constraints.validate_bed_count(30)
        
        assert not result.compliant
        assert "485.610(a)" in result.citation
    
    def test_validate_los_compliant(self):
        """Test LOS validation - compliant."""
        constraints = CAHConstraints()
        result = constraints.validate_los(72.0)
        
        assert result.compliant
    
    def test_validate_los_violation(self):
        """Test LOS validation - violation."""
        constraints = CAHConstraints()
        result = constraints.validate_los(100.0)
        
        assert not result.compliant
        assert "485.610(b)" in result.citation


class TestMVCAHIConstraints:
    """Tests for MV-CAHI constraints."""
    
    def test_validate_compute_compliant(self):
        """Test compute validation - compliant."""
        constraints = MVCAHIConstraints()
        result = constraints.validate_compute_requirements(
            cpu_cores=4,
            memory_gb=8,
            batch_runtime_hours=0.5,
        )
        
        assert result.valid
    
    def test_validate_compute_violation(self):
        """Test compute validation - violation."""
        constraints = MVCAHIConstraints()
        result = constraints.validate_compute_requirements(
            cpu_cores=8,
            memory_gb=16,
            batch_runtime_hours=2.0,
        )
        
        assert not result.valid
        assert len(result.issues) == 3
    
    def test_validate_financial_viability(self):
        """Test financial viability validation."""
        constraints = MVCAHIConstraints()
        result = constraints.validate_financial_viability(
            implementation_cost=40000,
            annual_operating_cost=8000,
            expected_annual_benefit=20000,
        )
        
        assert result.valid


class TestValidationResult:
    """Tests for ValidationResult."""
    
    def test_bool_conversion(self):
        """Test boolean conversion."""
        valid_result = ValidationResult(valid=True)
        invalid_result = ValidationResult(valid=False)
        
        assert bool(valid_result) is True
        assert bool(invalid_result) is False
    
    def test_merge_results(self):
        """Test merging validation results."""
        result1 = ValidationResult(valid=True, warnings=["warning1"])
        result2 = ValidationResult(valid=False, issues=["issue1"])
        
        merged = result1.merge(result2)
        
        assert not merged.valid
        assert "issue1" in merged.issues
        assert "warning1" in merged.warnings

