"""
Module 2: Data Integration

Transform raw data into interoperable formats and validate against regulatory requirements.
Includes dataset integration for optimization model calibration.
"""

from cah_engine.integration.fhir_mapper import (
    FHIRMapper,
    EncounterMapper,
    PatientMapper,
    ConditionMapper,
    ClaimMapper,
)
from cah_engine.integration.claims_processor import (
    ClaimsProcessor,
    X12Parser,
    DenialAnalyzer,
)
from cah_engine.integration.compliance_validator import (
    CAHComplianceValidator,
    ComplianceReport,
    ComplianceMonitor,
)
from cah_engine.integration.data_loader import (
    CAHDataLoader,
    CAHFacility,
    IntegratedDataset,
    load_integrated_data,
)
from cah_engine.integration.parameter_estimator import (
    ParameterEstimator,
    CalibratedParameters,
    ParameterEstimate,
    estimate_parameters_from_data,
)
from cah_engine.integration.integrated_optimizer import (
    IntegratedOptimizer,
    PopulationOptimizationResult,
    FacilityOptimizationResult,
    run_integrated_optimization,
)
from cah_engine.integration.data_validator import (
    DataValidator,
    ValidationReport,
    ValidationIssue,
    validate_dataset,
)

__all__ = [
    # FHIR Mapping
    "FHIRMapper",
    "EncounterMapper",
    "PatientMapper",
    "ConditionMapper",
    "ClaimMapper",
    # Claims Processing
    "ClaimsProcessor",
    "X12Parser",
    "DenialAnalyzer",
    # Compliance Validation
    "CAHComplianceValidator",
    "ComplianceReport",
    "ComplianceMonitor",
    # Data Integration
    "CAHDataLoader",
    "CAHFacility",
    "IntegratedDataset",
    "load_integrated_data",
    # Parameter Estimation
    "ParameterEstimator",
    "CalibratedParameters",
    "ParameterEstimate",
    "estimate_parameters_from_data",
    # Integrated Optimization
    "IntegratedOptimizer",
    "PopulationOptimizationResult",
    "FacilityOptimizationResult",
    "run_integrated_optimization",
    # Data Validation
    "DataValidator",
    "ValidationReport",
    "ValidationIssue",
    "validate_dataset",
]

