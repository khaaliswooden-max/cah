"""
Regulatory Compliance Validator

Continuous validation against CAH Conditions of Participation.
Real-time monitoring with alerting capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from enum import Enum

from cah_engine.core.models import (
    ClinicalEncounter,
    CostReportMetrics,
    FacilitySnapshot,
    ComplianceResult,
    ValidationResult,
)
from cah_engine.core.enums import Severity, ComplianceStatus
from cah_engine.core.constraints import CAHConstraints, CAH_CONSTRAINTS


class ComplianceArea(str, Enum):
    """Areas of CAH compliance."""
    
    BED_COUNT = "bed_count"
    LENGTH_OF_STAY = "length_of_stay"
    DISTANCE = "distance"
    EMERGENCY_SERVICES = "emergency_services"
    STAFFING = "staffing"
    QUALITY = "quality"
    BILLING = "billing"


@dataclass
class ComplianceIssue:
    """A specific compliance issue."""
    
    area: ComplianceArea
    severity: Severity
    citation: str
    message: str
    detected_at: datetime = field(default_factory=datetime.now)
    remediation: str = ""
    current_value: Any = None
    threshold_value: Any = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "area": self.area.value,
            "severity": self.severity.value,
            "citation": self.citation,
            "message": self.message,
            "detected_at": self.detected_at.isoformat(),
            "remediation": self.remediation,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
        }


@dataclass
class ComplianceReport:
    """Comprehensive compliance report."""
    
    facility_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    overall_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    issues: list[ComplianceIssue] = field(default_factory=list)
    warnings: list[ComplianceIssue] = field(default_factory=list)
    
    # Metrics by area
    bed_count_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    los_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    emergency_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    
    # Summary metrics
    current_staffed_beds: int = 0
    average_los_hours: float = 0.0
    los_compliance_rate: float = 0.0
    emergency_coverage_rate: float = 0.0
    
    def add_issue(self, issue: ComplianceIssue) -> None:
        """Add a compliance issue."""
        if issue.severity in (Severity.CRITICAL, Severity.BLOCKER):
            self.issues.append(issue)
            self.overall_status = ComplianceStatus.NON_COMPLIANT
        elif issue.severity in (Severity.WARNING, Severity.HIGH):
            self.warnings.append(issue)
            if self.overall_status == ComplianceStatus.COMPLIANT:
                self.overall_status = ComplianceStatus.WARNING
    
    @property
    def is_compliant(self) -> bool:
        """Check if facility is compliant."""
        return self.overall_status == ComplianceStatus.COMPLIANT
    
    @property
    def critical_issues(self) -> list[ComplianceIssue]:
        """Get critical issues only."""
        return [i for i in self.issues if i.severity == Severity.CRITICAL]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "facility_id": self.facility_id,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "overall_status": self.overall_status.value,
            "issues": [i.to_dict() for i in self.issues],
            "warnings": [i.to_dict() for i in self.warnings],
            "summary": {
                "current_staffed_beds": self.current_staffed_beds,
                "average_los_hours": self.average_los_hours,
                "los_compliance_rate": self.los_compliance_rate,
                "emergency_coverage_rate": self.emergency_coverage_rate,
            },
        }


@dataclass
class StaffingLog:
    """Log of staffing coverage."""
    
    entries: list[dict] = field(default_factory=list)
    
    def add_entry(
        self,
        timestamp: datetime,
        physician_on_site: bool,
        physician_on_call: bool,
        rn_count: int,
    ) -> None:
        """Add a staffing entry."""
        self.entries.append({
            "timestamp": timestamp,
            "physician_on_site": physician_on_site,
            "physician_on_call": physician_on_call,
            "rn_count": rn_count,
        })
    
    def find_coverage_gaps(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict]:
        """Find periods without adequate coverage."""
        gaps = []
        
        for entry in self.entries:
            ts = entry["timestamp"]
            
            # Apply time filter
            if start and ts < start:
                continue
            if end and ts > end:
                continue
            
            # Check for coverage gaps
            if not entry["physician_on_site"] and not entry["physician_on_call"]:
                gaps.append({
                    "timestamp": ts,
                    "issue": "No physician coverage",
                    "severity": Severity.CRITICAL,
                })
            
            if entry["rn_count"] == 0:
                gaps.append({
                    "timestamp": ts,
                    "issue": "No RN coverage",
                    "severity": Severity.CRITICAL,
                })
        
        return gaps


@dataclass
class ReportingPeriod:
    """Period for calculating compliance metrics."""
    
    encounters: list[ClinicalEncounter] = field(default_factory=list)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    
    def add_encounter(self, encounter: ClinicalEncounter) -> None:
        """Add an encounter to the period."""
        self.encounters.append(encounter)
        
        # Update period bounds
        if self.start is None or encounter.admit_datetime < self.start:
            self.start = encounter.admit_datetime
        if encounter.discharge_datetime:
            if self.end is None or encounter.discharge_datetime > self.end:
                self.end = encounter.discharge_datetime
    
    def calculate_average_los(self) -> float:
        """Calculate average length of stay in hours."""
        completed = [e for e in self.encounters if e.discharge_datetime]
        
        if not completed:
            return 0.0
        
        total_hours = sum(e.los_hours for e in completed)
        return total_hours / len(completed)
    
    @property
    def total_discharges(self) -> int:
        """Count of completed encounters."""
        return len([e for e in self.encounters if e.discharge_datetime])
    
    @property
    def los_violations(self) -> list[ClinicalEncounter]:
        """Encounters exceeding 96-hour LOS limit."""
        return [
            e for e in self.encounters
            if e.los_hours > 96 and e.discharge_datetime
        ]
    
    @property
    def los_compliance_rate(self) -> float:
        """Percentage of encounters meeting LOS requirement."""
        completed = [e for e in self.encounters if e.discharge_datetime]
        if not completed:
            return 100.0
        
        compliant = len([e for e in completed if e.los_hours <= 96])
        return (compliant / len(completed)) * 100


class CAHComplianceValidator:
    """
    Real-time CAH compliance monitoring.
    
    Validates facility operations against 42 CFR § 485.610
    and related CAH Conditions of Participation.
    """
    
    def __init__(self, constraints: Optional[CAHConstraints] = None):
        self.constraints = constraints or CAH_CONSTRAINTS
        self.alert_handlers: list[Callable[[ComplianceIssue], None]] = []
    
    def register_alert_handler(
        self,
        handler: Callable[[ComplianceIssue], None],
    ) -> None:
        """Register a handler for compliance alerts."""
        self.alert_handlers.append(handler)
    
    def _alert(self, issue: ComplianceIssue) -> None:
        """Send alert for a compliance issue."""
        for handler in self.alert_handlers:
            try:
                handler(issue)
            except Exception:
                pass  # Don't let handler errors stop validation
    
    def validate_bed_count(self, snapshot: FacilitySnapshot) -> ComplianceResult:
        """42 CFR § 485.610(a): Maximum 25 beds."""
        result = self.constraints.validate_bed_count(snapshot.staffed_beds)
        
        if not result.compliant:
            issue = ComplianceIssue(
                area=ComplianceArea.BED_COUNT,
                severity=Severity.CRITICAL,
                citation=result.citation,
                message=result.message,
                remediation=result.remediation,
                current_value=snapshot.staffed_beds,
                threshold_value=self.constraints.max_beds,
            )
            self._alert(issue)
        
        return result
    
    def validate_los(self, period: ReportingPeriod) -> ComplianceResult:
        """42 CFR § 485.610(b): Annual average LOS ≤ 96 hours."""
        avg_los = period.calculate_average_los()
        result = self.constraints.validate_los(avg_los)
        
        if not result.compliant:
            issue = ComplianceIssue(
                area=ComplianceArea.LENGTH_OF_STAY,
                severity=Severity.CRITICAL,
                citation=result.citation,
                message=result.message,
                remediation=result.remediation,
                current_value=avg_los,
                threshold_value=self.constraints.max_los_hours,
            )
            self._alert(issue)
        
        return result
    
    def validate_emergency_services(self, log: StaffingLog) -> ComplianceResult:
        """42 CFR § 485.618: 24/7 emergency services."""
        gaps = log.find_coverage_gaps()
        
        if gaps:
            return ComplianceResult(
                compliant=False,
                citation="42 CFR § 485.618",
                message=f"{len(gaps)} coverage gap(s) detected",
                severity=Severity.CRITICAL,
                gaps=gaps,
            )
        
        return ComplianceResult(
            compliant=True,
            citation="42 CFR § 485.618",
        )
    
    def validate_snapshot(self, snapshot: FacilitySnapshot) -> list[ComplianceResult]:
        """Validate a facility snapshot against all constraints."""
        results = []
        
        # Bed count
        results.append(self.validate_bed_count(snapshot))
        
        # Emergency services (from snapshot)
        result = self.constraints.validate_emergency_services(
            snapshot.physician_on_site,
            snapshot.physician_on_call,
        )
        results.append(result)
        
        if not result.compliant:
            issue = ComplianceIssue(
                area=ComplianceArea.EMERGENCY_SERVICES,
                severity=Severity.CRITICAL,
                citation=result.citation,
                message=result.message,
                remediation=result.remediation,
            )
            self._alert(issue)
        
        return results
    
    def validate_encounter(
        self,
        encounter: ClinicalEncounter,
    ) -> ValidationResult:
        """Validate a single encounter for compliance issues."""
        return encounter.validate_cah_compliance()
    
    def generate_report(
        self,
        facility_id: str,
        snapshot: FacilitySnapshot,
        period: ReportingPeriod,
        staffing_log: Optional[StaffingLog] = None,
    ) -> ComplianceReport:
        """Generate comprehensive compliance report."""
        report = ComplianceReport(
            facility_id=facility_id,
            period_start=period.start,
            period_end=period.end,
            overall_status=ComplianceStatus.COMPLIANT,
        )
        
        # Bed count validation
        bed_result = self.validate_bed_count(snapshot)
        report.current_staffed_beds = snapshot.staffed_beds
        
        if not bed_result.compliant:
            report.bed_count_status = ComplianceStatus.NON_COMPLIANT
            report.add_issue(ComplianceIssue(
                area=ComplianceArea.BED_COUNT,
                severity=bed_result.severity,
                citation=bed_result.citation,
                message=bed_result.message,
                remediation=bed_result.remediation,
                current_value=snapshot.staffed_beds,
                threshold_value=self.constraints.max_beds,
            ))
        else:
            report.bed_count_status = ComplianceStatus.COMPLIANT
        
        # LOS validation
        avg_los = period.calculate_average_los()
        report.average_los_hours = avg_los
        report.los_compliance_rate = period.los_compliance_rate
        
        los_result = self.validate_los(period)
        if not los_result.compliant:
            report.los_status = ComplianceStatus.NON_COMPLIANT
            report.add_issue(ComplianceIssue(
                area=ComplianceArea.LENGTH_OF_STAY,
                severity=los_result.severity,
                citation=los_result.citation,
                message=los_result.message,
                remediation=los_result.remediation,
                current_value=avg_los,
                threshold_value=self.constraints.max_los_hours,
            ))
        elif avg_los > 80:  # Warning threshold
            report.los_status = ComplianceStatus.WARNING
            report.add_issue(ComplianceIssue(
                area=ComplianceArea.LENGTH_OF_STAY,
                severity=Severity.WARNING,
                citation="42 CFR § 485.610(b)",
                message=f"Average LOS ({avg_los:.1f}h) approaching 96h limit",
                remediation="Monitor discharge processes proactively",
                current_value=avg_los,
                threshold_value=self.constraints.max_los_hours,
            ))
        else:
            report.los_status = ComplianceStatus.COMPLIANT
        
        # Emergency services validation
        if staffing_log:
            gaps = staffing_log.find_coverage_gaps(period.start, period.end)
            
            if gaps:
                report.emergency_status = ComplianceStatus.NON_COMPLIANT
                report.emergency_coverage_rate = 0.0  # Calculate actual rate
                
                for gap in gaps:
                    report.add_issue(ComplianceIssue(
                        area=ComplianceArea.EMERGENCY_SERVICES,
                        severity=gap["severity"],
                        citation="42 CFR § 485.618",
                        message=f"{gap['issue']} at {gap['timestamp']}",
                        remediation="Ensure 24/7 physician and nursing coverage",
                    ))
            else:
                report.emergency_status = ComplianceStatus.COMPLIANT
                report.emergency_coverage_rate = 100.0
        else:
            # Validate from snapshot
            em_result = self.constraints.validate_emergency_services(
                snapshot.physician_on_site,
                snapshot.physician_on_call,
            )
            if not em_result.compliant:
                report.emergency_status = ComplianceStatus.NON_COMPLIANT
                report.add_issue(ComplianceIssue(
                    area=ComplianceArea.EMERGENCY_SERVICES,
                    severity=Severity.CRITICAL,
                    citation=em_result.citation,
                    message=em_result.message,
                    remediation=em_result.remediation,
                ))
            else:
                report.emergency_status = ComplianceStatus.COMPLIANT
        
        # Check for LOS violations in individual encounters
        for violation in period.los_violations[:10]:  # Limit to first 10
            report.add_issue(ComplianceIssue(
                area=ComplianceArea.LENGTH_OF_STAY,
                severity=Severity.HIGH,
                citation="42 CFR § 485.610(b)",
                message=f"Encounter {violation.encounter_id} exceeded 96h ({violation.los_hours:.1f}h)",
                remediation="Review case for discharge barriers",
                current_value=violation.los_hours,
                threshold_value=96,
            ))
        
        return report


class ComplianceMonitor:
    """
    Continuous compliance monitoring service.
    
    Tracks compliance state over time and provides alerting.
    """
    
    def __init__(self, facility_id: str):
        self.facility_id = facility_id
        self.validator = CAHComplianceValidator()
        self.history: list[ComplianceReport] = []
        self.current_period = ReportingPeriod()
        self.staffing_log = StaffingLog()
        self.last_snapshot: Optional[FacilitySnapshot] = None
    
    def update_snapshot(self, snapshot: FacilitySnapshot) -> list[ComplianceResult]:
        """Update with new facility snapshot."""
        self.last_snapshot = snapshot
        return self.validator.validate_snapshot(snapshot)
    
    def add_encounter(self, encounter: ClinicalEncounter) -> ValidationResult:
        """Add encounter to monitoring."""
        self.current_period.add_encounter(encounter)
        return self.validator.validate_encounter(encounter)
    
    def log_staffing(
        self,
        timestamp: datetime,
        physician_on_site: bool,
        physician_on_call: bool,
        rn_count: int,
    ) -> None:
        """Log staffing status."""
        self.staffing_log.add_entry(
            timestamp=timestamp,
            physician_on_site=physician_on_site,
            physician_on_call=physician_on_call,
            rn_count=rn_count,
        )
    
    def generate_current_report(self) -> ComplianceReport:
        """Generate report based on current data."""
        if not self.last_snapshot:
            # Create default snapshot
            self.last_snapshot = FacilitySnapshot(
                facility_id=self.facility_id,
                timestamp=datetime.now(),
            )
        
        report = self.validator.generate_report(
            facility_id=self.facility_id,
            snapshot=self.last_snapshot,
            period=self.current_period,
            staffing_log=self.staffing_log,
        )
        
        self.history.append(report)
        return report
    
    def get_trend(self, metric: str, periods: int = 12) -> list[dict]:
        """Get trend data for a compliance metric."""
        recent = self.history[-periods:] if len(self.history) > periods else self.history
        
        trend = []
        for report in recent:
            value = None
            
            if metric == "los":
                value = report.average_los_hours
            elif metric == "los_compliance":
                value = report.los_compliance_rate
            elif metric == "emergency_coverage":
                value = report.emergency_coverage_rate
            elif metric == "beds":
                value = report.current_staffed_beds
            
            if value is not None:
                trend.append({
                    "timestamp": report.generated_at.isoformat(),
                    "value": value,
                })
        
        return trend
    
    def reset_period(self) -> None:
        """Start a new reporting period."""
        self.current_period = ReportingPeriod()

