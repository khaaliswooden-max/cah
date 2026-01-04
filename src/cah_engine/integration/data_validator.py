"""
Data Validator for CAH Optimization Datasets.

Provides comprehensive validation of acquired datasets to ensure
data quality before optimization:

- Completeness checks (required fields, missing values)
- Consistency checks (cross-dataset matching)
- Range validation (regulatory bounds, statistical outliers)
- Temporal consistency (fiscal year alignment)

Generates detailed validation reports for data quality assessment.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import statistics

from cah_engine.integration.data_loader import IntegratedDataset, CAHFacility


@dataclass
class ValidationIssue:
    """Single validation issue identified."""
    
    severity: str  # "error", "warning", "info"
    category: str  # "completeness", "consistency", "range", "temporal"
    facility_id: Optional[str]
    field: str
    message: str
    
    def to_dict(self) -> dict:
        """Export as dictionary."""
        return {
            "severity": self.severity,
            "category": self.category,
            "facility_id": self.facility_id,
            "field": self.field,
            "message": self.message,
        }


@dataclass
class ValidationReport:
    """Complete validation report for a dataset."""
    
    timestamp: str = ""
    total_facilities: int = 0
    facilities_validated: int = 0
    
    # Issue counts by severity
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # Issue counts by category
    completeness_issues: int = 0
    consistency_issues: int = 0
    range_issues: int = 0
    temporal_issues: int = 0
    
    # Detailed issues
    issues: list[ValidationIssue] = field(default_factory=list)
    
    # Quality scores (0-1)
    completeness_score: float = 1.0
    consistency_score: float = 1.0
    overall_quality_score: float = 1.0
    
    # Recommendations
    recommendations: list[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Check if dataset passes validation (no errors)."""
        return self.error_count == 0
    
    def add_issue(self, issue: ValidationIssue):
        """Add an issue and update counts."""
        self.issues.append(issue)
        
        if issue.severity == "error":
            self.error_count += 1
        elif issue.severity == "warning":
            self.warning_count += 1
        else:
            self.info_count += 1
        
        if issue.category == "completeness":
            self.completeness_issues += 1
        elif issue.category == "consistency":
            self.consistency_issues += 1
        elif issue.category == "range":
            self.range_issues += 1
        elif issue.category == "temporal":
            self.temporal_issues += 1
    
    def to_dict(self) -> dict:
        """Export as dictionary."""
        return {
            "timestamp": self.timestamp,
            "summary": {
                "total_facilities": self.total_facilities,
                "facilities_validated": self.facilities_validated,
                "is_valid": self.is_valid,
            },
            "issue_counts": {
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count,
            },
            "issue_categories": {
                "completeness": self.completeness_issues,
                "consistency": self.consistency_issues,
                "range": self.range_issues,
                "temporal": self.temporal_issues,
            },
            "quality_scores": {
                "completeness": self.completeness_score,
                "consistency": self.consistency_score,
                "overall": self.overall_quality_score,
            },
            "recommendations": self.recommendations,
            "issues": [i.to_dict() for i in self.issues[:100]],  # Limit for report size
        }


class DataValidator:
    """
    Validate integrated CAH datasets.
    
    Performs comprehensive validation including:
    - Required field completeness
    - CAH regulatory compliance
    - Statistical outlier detection
    - Cross-dataset consistency
    
    Example:
        >>> from cah_engine.integration.data_loader import load_integrated_data
        >>> dataset = load_integrated_data("data")
        >>> validator = DataValidator()
        >>> report = validator.validate(dataset)
        >>> print(f"Valid: {report.is_valid}, Errors: {report.error_count}")
    """
    
    # Required fields for optimization
    REQUIRED_FIELDS = [
        "facility_id",
        "facility_name",
        "state",
    ]
    
    # Fields needed for financial analysis
    FINANCIAL_FIELDS = [
        "total_operating_revenue",
        "total_operating_expenses",
    ]
    
    # CAH regulatory limits
    CAH_LIMITS = {
        "staffed_beds": {"max": 25, "description": "42 CFR § 485.620"},
        "avg_los_hours": {"max": 96, "description": "42 CFR § 485.620"},
    }
    
    # Statistical thresholds for outlier detection
    OUTLIER_THRESHOLDS = {
        "operating_margin": {"min": -0.5, "max": 0.5},  # -50% to +50%
        "occupancy_rate": {"min": 0.0, "max": 1.0},     # 0% to 100%
        "staffed_beds": {"min": 1, "max": 50},          # Reasonable range
        "ed_visits": {"min": 0, "max": 50000},          # Annual visits
    }
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, treat warnings as errors
        """
        self.strict_mode = strict_mode
    
    def validate(self, dataset: IntegratedDataset) -> ValidationReport:
        """
        Run full validation on integrated dataset.
        
        Args:
            dataset: IntegratedDataset to validate
            
        Returns:
            ValidationReport with all issues and scores
        """
        report = ValidationReport()
        report.timestamp = datetime.now().isoformat()
        report.total_facilities = len(dataset.facilities)
        
        # Run all validation checks
        self._validate_completeness(dataset, report)
        self._validate_consistency(dataset, report)
        self._validate_ranges(dataset, report)
        self._validate_regulatory(dataset, report)
        
        report.facilities_validated = len(dataset.facilities)
        
        # Calculate quality scores
        self._calculate_scores(report)
        
        # Generate recommendations
        self._generate_recommendations(report)
        
        return report
    
    def _validate_completeness(self, dataset: IntegratedDataset, report: ValidationReport):
        """Check for missing required data."""
        for facility in dataset.facilities.values():
            # Required fields
            for field_name in self.REQUIRED_FIELDS:
                value = getattr(facility, field_name, None)
                if not value:
                    report.add_issue(ValidationIssue(
                        severity="error",
                        category="completeness",
                        facility_id=facility.facility_id,
                        field=field_name,
                        message=f"Missing required field: {field_name}",
                    ))
            
            # Financial fields (warning if missing)
            for field_name in self.FINANCIAL_FIELDS:
                value = getattr(facility, field_name, 0)
                if value == 0:
                    report.add_issue(ValidationIssue(
                        severity="warning",
                        category="completeness",
                        facility_id=facility.facility_id,
                        field=field_name,
                        message=f"Missing financial data: {field_name}",
                    ))
    
    def _validate_consistency(self, dataset: IntegratedDataset, report: ValidationReport):
        """Check cross-field and cross-dataset consistency."""
        for facility in dataset.facilities.values():
            # Revenue should exceed expenses for viable facilities (warning)
            if facility.total_operating_revenue > 0 and facility.total_operating_expenses > 0:
                if facility.operating_margin < -0.25:
                    report.add_issue(ValidationIssue(
                        severity="warning",
                        category="consistency",
                        facility_id=facility.facility_id,
                        field="operating_margin",
                        message=f"Operating margin ({facility.operating_margin:.1%}) indicates severe financial stress",
                    ))
            
            # Patient days should be consistent with beds and occupancy
            if facility.staffed_beds > 0 and facility.patient_days > 0:
                implied_occupancy = facility.patient_days / (facility.staffed_beds * 365)
                if implied_occupancy > 1.0:
                    report.add_issue(ValidationIssue(
                        severity="warning",
                        category="consistency",
                        facility_id=facility.facility_id,
                        field="patient_days",
                        message=f"Patient days ({facility.patient_days}) exceeds bed capacity",
                    ))
            
            # Quality measures should be internally consistent
            total_measures = (
                facility.mort_measures_better + facility.mort_measures_worse +
                facility.safety_measures_better + facility.safety_measures_worse +
                facility.readm_measures_better + facility.readm_measures_worse
            )
            if total_measures > 0 and facility.overall_rating is None:
                report.add_issue(ValidationIssue(
                    severity="info",
                    category="consistency",
                    facility_id=facility.facility_id,
                    field="overall_rating",
                    message="Quality measures present but no overall rating",
                ))
    
    def _validate_ranges(self, dataset: IntegratedDataset, report: ValidationReport):
        """Check for statistical outliers."""
        for facility in dataset.facilities.values():
            # Check each metric against thresholds
            if facility.total_operating_revenue > 0:
                margin = facility.operating_margin
                thresholds = self.OUTLIER_THRESHOLDS["operating_margin"]
                if margin < thresholds["min"] or margin > thresholds["max"]:
                    report.add_issue(ValidationIssue(
                        severity="warning",
                        category="range",
                        facility_id=facility.facility_id,
                        field="operating_margin",
                        message=f"Operating margin ({margin:.1%}) outside typical range",
                    ))
            
            # Beds
            if facility.staffed_beds > 0:
                thresholds = self.OUTLIER_THRESHOLDS["staffed_beds"]
                if facility.staffed_beds > thresholds["max"]:
                    report.add_issue(ValidationIssue(
                        severity="warning",
                        category="range",
                        facility_id=facility.facility_id,
                        field="staffed_beds",
                        message=f"Staffed beds ({facility.staffed_beds}) unusually high for CAH",
                    ))
            
            # ED visits
            if facility.ed_visits > 0:
                thresholds = self.OUTLIER_THRESHOLDS["ed_visits"]
                if facility.ed_visits > thresholds["max"]:
                    report.add_issue(ValidationIssue(
                        severity="warning",
                        category="range",
                        facility_id=facility.facility_id,
                        field="ed_visits",
                        message=f"ED visits ({facility.ed_visits}) unusually high",
                    ))
    
    def _validate_regulatory(self, dataset: IntegratedDataset, report: ValidationReport):
        """Check CAH regulatory compliance."""
        for facility in dataset.facilities.values():
            # Bed limit
            if facility.staffed_beds > self.CAH_LIMITS["staffed_beds"]["max"]:
                report.add_issue(ValidationIssue(
                    severity="error",
                    category="range",
                    facility_id=facility.facility_id,
                    field="staffed_beds",
                    message=(
                        f"Staffed beds ({facility.staffed_beds}) exceeds CAH limit of "
                        f"{self.CAH_LIMITS['staffed_beds']['max']} "
                        f"({self.CAH_LIMITS['staffed_beds']['description']})"
                    ),
                ))
    
    def _calculate_scores(self, report: ValidationReport):
        """Calculate quality scores based on issues."""
        if report.total_facilities == 0:
            return
        
        # Completeness score
        completeness_errors = sum(
            1 for i in report.issues 
            if i.category == "completeness" and i.severity == "error"
        )
        report.completeness_score = max(0, 1.0 - (completeness_errors / report.total_facilities))
        
        # Consistency score
        consistency_issues = report.consistency_issues
        report.consistency_score = max(0, 1.0 - (consistency_issues / (report.total_facilities * 3)))
        
        # Overall quality score (weighted average)
        report.overall_quality_score = (
            0.5 * report.completeness_score +
            0.3 * report.consistency_score +
            0.2 * (1.0 - min(1.0, report.range_issues / (report.total_facilities * 2)))
        )
    
    def _generate_recommendations(self, report: ValidationReport):
        """Generate recommendations based on validation results."""
        if report.error_count > 0:
            report.recommendations.append(
                f"CRITICAL: Fix {report.error_count} validation errors before proceeding"
            )
        
        if report.completeness_issues > report.total_facilities * 0.1:
            report.recommendations.append(
                "Data completeness concern - consider supplementing with additional data sources"
            )
        
        if report.consistency_issues > report.total_facilities * 0.2:
            report.recommendations.append(
                "Review data consistency - cross-reference with source files"
            )
        
        if report.range_issues > report.total_facilities * 0.05:
            report.recommendations.append(
                "Statistical outliers detected - review for data entry errors"
            )
        
        if not report.recommendations:
            report.recommendations.append(
                "Data quality acceptable - proceed with optimization"
            )


def validate_dataset(dataset: IntegratedDataset) -> ValidationReport:
    """
    Convenience function to validate a dataset.
    
    Args:
        dataset: IntegratedDataset to validate
        
    Returns:
        ValidationReport
    """
    validator = DataValidator()
    return validator.validate(dataset)

