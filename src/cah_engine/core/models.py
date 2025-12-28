"""
Core data models for the CAH Transformation Engine.

These models represent the fundamental data structures used across all modules.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from enum import Enum

from cah_engine.core.enums import (
    EncounterType,
    DispositionCode,
    Severity,
    IssueCategory,
    ClaimStatus,
    ComplianceStatus,
    RiskTier,
)


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    
    valid: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def __bool__(self) -> bool:
        return self.valid
    
    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge two validation results."""
        return ValidationResult(
            valid=self.valid and other.valid,
            issues=self.issues + other.issues,
            warnings=self.warnings + other.warnings,
        )


@dataclass
class ComplianceResult:
    """Result of a regulatory compliance check."""
    
    compliant: bool
    citation: str = ""
    message: str = ""
    severity: Severity = Severity.INFO
    remediation: str = ""
    gaps: list[Any] = field(default_factory=list)
    
    def __bool__(self) -> bool:
        return self.compliant


@dataclass
class ClinicalEncounter:
    """
    Normalized encounter representation.
    
    This model normalizes clinical encounter data from various EHR systems
    into a common format for analysis and FHIR transformation.
    """
    
    encounter_id: str
    patient_id: str  # De-identified
    admit_datetime: datetime
    discharge_datetime: Optional[datetime]
    encounter_type: EncounterType
    principal_diagnosis: str  # ICD-10-CM
    secondary_diagnoses: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)  # ICD-10-PCS or CPT
    attending_provider: str = ""  # De-identified
    disposition: DispositionCode = DispositionCode.HOME
    los_hours: float = 0.0
    
    # Optional clinical details
    drg: Optional[str] = None
    admission_source: Optional[str] = None
    admission_type: Optional[str] = None
    
    # Computed fields
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Calculate LOS if discharge datetime is available."""
        if self.discharge_datetime and self.los_hours == 0.0:
            delta = self.discharge_datetime - self.admit_datetime
            self.los_hours = delta.total_seconds() / 3600
    
    def validate_cah_compliance(self) -> ValidationResult:
        """Check encounter against CAH constraints."""
        issues = []
        warnings = []
        
        # LOS constraint (96 hours for inpatient)
        if self.los_hours > 96 and self.encounter_type == EncounterType.INPATIENT:
            issues.append(
                f"LOS {self.los_hours:.1f}h exceeds 96h limit for inpatient"
            )
        elif self.los_hours > 72 and self.encounter_type == EncounterType.INPATIENT:
            warnings.append(
                f"LOS {self.los_hours:.1f}h approaching 96h limit"
            )
        
        # Validate diagnosis code format
        if self.principal_diagnosis and not self._is_valid_icd10(self.principal_diagnosis):
            warnings.append(
                f"Principal diagnosis '{self.principal_diagnosis}' may not be valid ICD-10"
            )
        
        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
        )
    
    def _is_valid_icd10(self, code: str) -> bool:
        """Basic ICD-10 format validation."""
        if not code or len(code) < 3:
            return False
        # ICD-10-CM starts with letter, followed by 2+ digits, optional decimal
        return code[0].isalpha() and code[1:3].isdigit()
    
    def is_transfer(self) -> bool:
        """Check if this encounter resulted in a transfer."""
        return self.disposition.is_transfer()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "encounter_id": self.encounter_id,
            "patient_id": self.patient_id,
            "admit_datetime": self.admit_datetime.isoformat(),
            "discharge_datetime": self.discharge_datetime.isoformat() if self.discharge_datetime else None,
            "encounter_type": self.encounter_type.value,
            "principal_diagnosis": self.principal_diagnosis,
            "secondary_diagnoses": self.secondary_diagnoses,
            "procedures": self.procedures,
            "attending_provider": self.attending_provider,
            "disposition": self.disposition.value,
            "los_hours": self.los_hours,
            "drg": self.drg,
            "admission_source": self.admission_source,
            "admission_type": self.admission_type,
        }


@dataclass
class CostReportMetrics:
    """
    Structured cost report data from CMS 2552-10.
    
    Extracts key financial and operational metrics from annual cost reports.
    """
    
    provider_id: str
    fiscal_year_end: date
    
    # Capacity
    total_beds: int = 0
    staffed_beds: int = 0
    patient_days: int = 0
    discharges: int = 0
    
    # Revenue
    net_patient_revenue: Decimal = Decimal("0")
    total_operating_revenue: Decimal = Decimal("0")
    
    # Expenses
    total_operating_expenses: Decimal = Decimal("0")
    salary_expenses: Decimal = Decimal("0")
    
    # Workforce
    fte_count: float = 0.0
    
    # Additional metrics
    ed_visits: int = 0
    swing_bed_days: int = 0
    observation_hours: float = 0.0
    
    @property
    def operating_margin(self) -> float:
        """Calculate operating margin percentage."""
        if self.total_operating_revenue == 0:
            return 0.0
        profit = self.total_operating_revenue - self.total_operating_expenses
        return float(profit / self.total_operating_revenue) * 100
    
    @property
    def occupancy_rate(self) -> float:
        """Calculate bed occupancy rate."""
        if self.staffed_beds == 0:
            return 0.0
        # Days in fiscal year approximation
        max_patient_days = self.staffed_beds * 365
        return (self.patient_days / max_patient_days) * 100
    
    @property
    def cost_per_discharge(self) -> Decimal:
        """Calculate average cost per discharge."""
        if self.discharges == 0:
            return Decimal("0")
        return self.total_operating_expenses / self.discharges
    
    @property
    def labor_cost_ratio(self) -> float:
        """Calculate labor cost as percentage of operating expenses."""
        if self.total_operating_expenses == 0:
            return 0.0
        return float(self.salary_expenses / self.total_operating_expenses)
    
    @property
    def revenue_per_fte(self) -> Decimal:
        """Calculate revenue per FTE."""
        if self.fte_count == 0:
            return Decimal("0")
        return self.net_patient_revenue / Decimal(str(self.fte_count))
    
    @property
    def average_los_hours(self) -> float:
        """Calculate average length of stay in hours."""
        if self.discharges == 0:
            return 0.0
        return (self.patient_days * 24) / self.discharges
    
    def validate_cah_compliance(self) -> ValidationResult:
        """Validate metrics against CAH requirements."""
        issues = []
        warnings = []
        
        if self.staffed_beds > 25:
            issues.append(
                f"Staffed beds ({self.staffed_beds}) exceeds CAH limit of 25"
            )
        
        if self.average_los_hours > 96:
            issues.append(
                f"Average LOS ({self.average_los_hours:.1f}h) exceeds 96h CAH limit"
            )
        elif self.average_los_hours > 80:
            warnings.append(
                f"Average LOS ({self.average_los_hours:.1f}h) approaching 96h limit"
            )
        
        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "provider_id": self.provider_id,
            "fiscal_year_end": self.fiscal_year_end.isoformat(),
            "total_beds": self.total_beds,
            "staffed_beds": self.staffed_beds,
            "patient_days": self.patient_days,
            "discharges": self.discharges,
            "net_patient_revenue": str(self.net_patient_revenue),
            "total_operating_revenue": str(self.total_operating_revenue),
            "total_operating_expenses": str(self.total_operating_expenses),
            "salary_expenses": str(self.salary_expenses),
            "fte_count": self.fte_count,
            "operating_margin": self.operating_margin,
            "occupancy_rate": self.occupancy_rate,
            "labor_cost_ratio": self.labor_cost_ratio,
        }


@dataclass
class FacilitySnapshot:
    """
    Point-in-time snapshot of facility status.
    
    Used for real-time monitoring and compliance checking.
    """
    
    facility_id: str
    timestamp: datetime
    
    # Current state
    staffed_beds: int = 0
    occupied_beds: int = 0
    ed_patients: int = 0
    pending_admissions: int = 0
    pending_discharges: int = 0
    
    # Staff on duty
    rn_count: int = 0
    physician_on_site: bool = False
    physician_on_call: bool = True
    
    # System status
    ehr_online: bool = True
    lab_online: bool = True
    imaging_online: bool = True
    
    @property
    def current_census(self) -> int:
        """Current patient census."""
        return self.occupied_beds
    
    @property
    def available_beds(self) -> int:
        """Number of available beds."""
        return max(0, self.staffed_beds - self.occupied_beds)
    
    @property
    def occupancy_rate(self) -> float:
        """Current occupancy percentage."""
        if self.staffed_beds == 0:
            return 0.0
        return (self.occupied_beds / self.staffed_beds) * 100
    
    @property
    def at_capacity(self) -> bool:
        """Check if facility is at capacity."""
        return self.available_beds == 0
    
    def validate_compliance(self) -> ValidationResult:
        """Validate current state against CAH requirements."""
        issues = []
        warnings = []
        
        if self.staffed_beds > 25:
            issues.append(f"Staffed beds ({self.staffed_beds}) exceeds 25")
        
        if not self.physician_on_site and not self.physician_on_call:
            issues.append("No physician coverage - violates 24/7 emergency requirement")
        
        if not self.physician_on_site:
            warnings.append("No physician on-site")
        
        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
        )


@dataclass
class StaffMember:
    """Staff member for scheduling optimization."""
    
    staff_id: str
    name: str
    role: str
    skills: set[str] = field(default_factory=set)
    hourly_cost: float = 0.0
    max_hours: float = 40.0  # Per week
    productivity_factor: float = 1.0
    
    # Preferences and constraints
    preferred_shifts: list[str] = field(default_factory=list)
    unavailable_dates: list[date] = field(default_factory=list)


@dataclass
class Claim:
    """Healthcare claim representation."""
    
    claim_id: str
    patient_id: str
    encounter_id: str
    payer_id: str
    service_date: date
    
    # Claim details
    claim_type: str  # "837I" or "837P"
    total_charges: Decimal = Decimal("0")
    diagnosis_codes: list[str] = field(default_factory=list)
    procedure_codes: list[str] = field(default_factory=list)
    
    # Status
    status: ClaimStatus = ClaimStatus.DRAFT
    submitted_date: Optional[date] = None
    
    # Payment info
    paid_amount: Optional[Decimal] = None
    adjustment_amount: Optional[Decimal] = None
    denial_codes: list[str] = field(default_factory=list)


@dataclass
class Issue:
    """Issue identified during scrubbing or validation."""
    
    severity: Severity
    category: IssueCategory
    message: str
    action: str = ""
    field: str = ""
    
    def __lt__(self, other: "Issue") -> bool:
        return self.severity < other.severity


@dataclass
class Factor:
    """Factor contributing to a performance gap."""
    
    name: str
    current: float
    benchmark: float
    impact_coefficient: float
    contribution: float = 0.0
    
    def __post_init__(self):
        if self.contribution == 0.0:
            self.contribution = (self.current - self.benchmark) * self.impact_coefficient


@dataclass
class GapDecomposition:
    """Decomposition of a performance gap into contributing factors."""
    
    total_gap: float
    factors: list[Factor]
    explained_gap: float = 0.0
    residual: float = 0.0
    
    def __post_init__(self):
        if self.explained_gap == 0.0:
            self.explained_gap = sum(f.contribution for f in self.factors)
        if self.residual == 0.0:
            self.residual = self.total_gap - self.explained_gap


@dataclass
class SimulationResult:
    """Result of a Monte Carlo simulation."""
    
    mean: float
    median: float
    std: float
    p5: float  # 5th percentile
    p95: float  # 95th percentile
    prob_positive: float  # Probability of positive outcome
    
    @property
    def confidence_interval_90(self) -> tuple[float, float]:
        """90% confidence interval."""
        return (self.p5, self.p95)


@dataclass
class TransferRecommendation:
    """Recommendation from the Transfer Advisor."""
    
    recommendation: str  # "admit", "transfer", "observe"
    confidence: float  # 0-1
    rationale: str
    alternatives: list[Any] = field(default_factory=list)
    emtala_compliant: bool = True
    risk_score: float = 0.0
    contributing_factors: list[str] = field(default_factory=list)


@dataclass
class ScrubResult:
    """Result of pre-bill claim scrubbing."""
    
    claim_id: str
    status: str  # "clean", "warning", "blocked"
    issues: list[Issue] = field(default_factory=list)
    clean_claim_probability: float = 1.0
    estimated_payment: Decimal = Decimal("0")
    
    @property
    def is_clean(self) -> bool:
        """Check if claim is clean with no blockers."""
        return not any(i.severity == Severity.BLOCKER for i in self.issues)


@dataclass
class Schedule:
    """Optimized staffing schedule."""
    
    assignments: Any  # numpy array or similar
    total_cost: float
    staff_pool: list[StaffMember]
    coverage_analysis: dict = field(default_factory=dict)
    
    def get_staff_hours(self, staff_id: str) -> float:
        """Get total hours assigned to a staff member."""
        for i, staff in enumerate(self.staff_pool):
            if staff.staff_id == staff_id:
                return float(self.assignments[i].sum())
        return 0.0

