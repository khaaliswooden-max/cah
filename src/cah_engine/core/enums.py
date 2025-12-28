"""
Enumeration types for the CAH Transformation Engine.
"""

from enum import Enum, auto


class EncounterType(str, Enum):
    """Types of patient encounters in a CAH."""
    
    INPATIENT = "inpatient"
    OBSERVATION = "observation"
    EMERGENCY = "emergency"
    SWING_BED = "swing_bed"
    OUTPATIENT = "outpatient"
    
    def is_bed_occupying(self) -> bool:
        """Check if this encounter type occupies a bed."""
        return self in (
            EncounterType.INPATIENT,
            EncounterType.OBSERVATION,
            EncounterType.SWING_BED,
        )


class DispositionCode(str, Enum):
    """Patient discharge disposition codes."""
    
    HOME = "01"  # Discharged to home
    HOME_HEALTH = "06"  # Discharged to home health
    TRANSFER_ACUTE = "02"  # Transfer to acute care hospital
    TRANSFER_SNF = "03"  # Transfer to SNF
    TRANSFER_IRF = "62"  # Transfer to IRF
    TRANSFER_LTCH = "63"  # Transfer to LTCH
    AMA = "07"  # Left against medical advice
    EXPIRED = "20"  # Expired
    HOSPICE_HOME = "50"  # Hospice - home
    HOSPICE_FACILITY = "51"  # Hospice - facility
    OTHER = "99"  # Other
    
    def is_transfer(self) -> bool:
        """Check if this disposition represents a transfer."""
        return self in (
            DispositionCode.TRANSFER_ACUTE,
            DispositionCode.TRANSFER_SNF,
            DispositionCode.TRANSFER_IRF,
            DispositionCode.TRANSFER_LTCH,
        )


class Severity(str, Enum):
    """Severity levels for issues and alerts."""
    
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"
    BLOCKER = "blocker"
    
    def __lt__(self, other: "Severity") -> bool:
        order = [Severity.INFO, Severity.WARNING, Severity.HIGH, Severity.CRITICAL, Severity.BLOCKER]
        return order.index(self) < order.index(other)


class IssueCategory(str, Enum):
    """Categories for claim and compliance issues."""
    
    ELIGIBILITY = "eligibility"
    MEDICAL_NECESSITY = "medical_necessity"
    CODING = "coding"
    AUTHORIZATION = "authorization"
    TIMELY_FILING = "timely_filing"
    NON_COVERED = "non_covered"
    DOCUMENTATION = "documentation"
    COMPLIANCE = "compliance"


class ClaimStatus(str, Enum):
    """Status of a healthcare claim."""
    
    DRAFT = "draft"
    READY = "ready"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    PAID = "paid"
    DENIED = "denied"
    APPEALED = "appealed"


class ComplianceStatus(str, Enum):
    """Regulatory compliance status."""
    
    COMPLIANT = "compliant"
    WARNING = "warning"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"


class ModelStatus(str, Enum):
    """Status of predictive models."""
    
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    TRAINING = "training"
    FAILED = "failed"


class SyncStatus(str, Enum):
    """Data synchronization status."""
    
    SYNCED = "synced"
    PENDING = "pending"
    FAILED = "failed"
    OFFLINE = "offline"


class RiskTier(str, Enum):
    """Risk stratification tiers."""
    
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    
    @classmethod
    def from_score(cls, score: float) -> "RiskTier":
        """Convert a 0-100 risk score to a tier."""
        if score < 20:
            return cls.LOW
        elif score < 50:
            return cls.MODERATE
        elif score < 80:
            return cls.HIGH
        else:
            return cls.CRITICAL

