"""
Constraint definitions for CAH operations.

These constraints are derived from:
- 42 CFR § 485.610 (CAH Conditions of Participation)
- MV-CAHI specification (Minimum Viable CAH Infrastructure)
"""

from dataclasses import dataclass
from typing import Protocol, Any

from cah_engine.core.models import ValidationResult, ComplianceResult, FacilitySnapshot
from cah_engine.core.enums import Severity


@dataclass
class CAHConstraints:
    """
    Regulatory constraints for Critical Access Hospitals.
    
    Based on 42 CFR § 485.610 and related CMS regulations.
    """
    
    # 42 CFR § 485.610(a) - Bed limit
    max_beds: int = 25
    
    # 42 CFR § 485.610(b) - Average LOS limit (hours)
    max_los_hours: int = 96
    
    # 42 CFR § 485.610(c) - Distance requirement (miles)
    min_distance_miles: float = 35
    
    # 42 CFR § 485.618 - Emergency services
    emergency_service_24_7: bool = True
    
    def validate_bed_count(self, staffed_beds: int) -> ComplianceResult:
        """42 CFR § 485.610(a): Maximum 25 beds."""
        if staffed_beds > self.max_beds:
            return ComplianceResult(
                compliant=False,
                citation="42 CFR § 485.610(a)",
                message=f"Staffed beds ({staffed_beds}) exceeds {self.max_beds}",
                severity=Severity.CRITICAL,
                remediation="Reduce staffed bed count or convert to PPS hospital",
            )
        return ComplianceResult(compliant=True, citation="42 CFR § 485.610(a)")
    
    def validate_los(self, average_los_hours: float) -> ComplianceResult:
        """42 CFR § 485.610(b): Annual average LOS ≤ 96 hours."""
        if average_los_hours > self.max_los_hours:
            return ComplianceResult(
                compliant=False,
                citation="42 CFR § 485.610(b)",
                message=f"Average LOS ({average_los_hours:.1f}h) exceeds {self.max_los_hours}h",
                severity=Severity.CRITICAL,
                remediation="Expedite discharges, review swing bed utilization, improve care coordination",
            )
        elif average_los_hours > self.max_los_hours * 0.85:  # Warning at 85%
            return ComplianceResult(
                compliant=True,
                citation="42 CFR § 485.610(b)",
                message=f"Average LOS ({average_los_hours:.1f}h) approaching limit",
                severity=Severity.WARNING,
                remediation="Monitor discharge processes proactively",
            )
        return ComplianceResult(compliant=True, citation="42 CFR § 485.610(b)")
    
    def validate_emergency_services(
        self,
        physician_on_site: bool,
        physician_on_call: bool,
    ) -> ComplianceResult:
        """42 CFR § 485.618: 24/7 emergency services."""
        if not physician_on_site and not physician_on_call:
            return ComplianceResult(
                compliant=False,
                citation="42 CFR § 485.618",
                message="No physician coverage available",
                severity=Severity.CRITICAL,
                remediation="Ensure 24/7 physician availability (on-site or on-call)",
            )
        return ComplianceResult(compliant=True, citation="42 CFR § 485.618")
    
    def validate_snapshot(self, snapshot: FacilitySnapshot) -> list[ComplianceResult]:
        """Validate a facility snapshot against all constraints."""
        results = []
        
        results.append(self.validate_bed_count(snapshot.staffed_beds))
        results.append(
            self.validate_emergency_services(
                snapshot.physician_on_site,
                snapshot.physician_on_call,
            )
        )
        
        return results


@dataclass
class MVCAHIConstraints:
    """
    MV-CAHI (Minimum Viable CAH Infrastructure) constraints.
    
    Computational and financial constraints for solution viability.
    """
    
    # Computational constraints
    max_cpu_cores: int = 4
    max_memory_gb: int = 8
    max_batch_runtime_hours: float = 1.0
    
    # Storage constraints
    max_monthly_growth_gb: float = 1.0
    max_total_storage_gb: float = 200
    
    # Network constraints
    max_bandwidth_mbps: float = 25
    max_latency_ms: float = 150
    assume_offline_hours_per_month: float = 10
    
    # Maintenance constraints
    max_monthly_maintenance_hours: float = 4
    
    # Financial constraints
    max_implementation_cost: int = 50_000
    max_annual_operating_cost: int = 10_000
    max_payback_period_months: int = 18
    min_annual_roi: float = 0.20
    
    # Workflow constraints
    max_training_hours_per_user: float = 4
    max_additional_clicks_per_task: int = 2
    max_workflow_time_increase_pct: float = 5
    
    def validate_compute_requirements(
        self,
        cpu_cores: int,
        memory_gb: float,
        batch_runtime_hours: float,
    ) -> ValidationResult:
        """Validate solution against compute constraints."""
        issues = []
        
        if cpu_cores > self.max_cpu_cores:
            issues.append(
                f"CPU requirement ({cpu_cores} cores) exceeds MV-CAHI limit ({self.max_cpu_cores})"
            )
        
        if memory_gb > self.max_memory_gb:
            issues.append(
                f"Memory requirement ({memory_gb} GB) exceeds MV-CAHI limit ({self.max_memory_gb})"
            )
        
        if batch_runtime_hours > self.max_batch_runtime_hours:
            issues.append(
                f"Batch runtime ({batch_runtime_hours}h) exceeds MV-CAHI limit ({self.max_batch_runtime_hours}h)"
            )
        
        return ValidationResult(valid=len(issues) == 0, issues=issues)
    
    def validate_financial_viability(
        self,
        implementation_cost: float,
        annual_operating_cost: float,
        expected_annual_benefit: float,
    ) -> ValidationResult:
        """Validate solution against financial constraints."""
        issues = []
        warnings = []
        
        if implementation_cost > self.max_implementation_cost:
            issues.append(
                f"Implementation cost (${implementation_cost:,.0f}) exceeds "
                f"MV-CAHI limit (${self.max_implementation_cost:,})"
            )
        
        if annual_operating_cost > self.max_annual_operating_cost:
            issues.append(
                f"Annual operating cost (${annual_operating_cost:,.0f}) exceeds "
                f"MV-CAHI limit (${self.max_annual_operating_cost:,})"
            )
        
        # ROI calculation
        if expected_annual_benefit > 0:
            roi = (expected_annual_benefit - annual_operating_cost) / implementation_cost
            if roi < self.min_annual_roi:
                warnings.append(
                    f"Expected ROI ({roi:.1%}) below MV-CAHI target ({self.min_annual_roi:.0%})"
                )
            
            # Payback period
            net_annual_benefit = expected_annual_benefit - annual_operating_cost
            if net_annual_benefit > 0:
                payback_months = (implementation_cost / net_annual_benefit) * 12
                if payback_months > self.max_payback_period_months:
                    warnings.append(
                        f"Payback period ({payback_months:.0f} months) exceeds "
                        f"MV-CAHI target ({self.max_payback_period_months} months)"
                    )
        
        return ValidationResult(valid=len(issues) == 0, issues=issues, warnings=warnings)
    
    def validate_offline_capability(
        self,
        requires_connectivity: bool,
        graceful_degradation: bool,
    ) -> ValidationResult:
        """Validate offline operation capability."""
        issues = []
        
        if requires_connectivity and not graceful_degradation:
            issues.append(
                "Solution requires constant connectivity without graceful degradation - "
                "incompatible with MV-CAHI rural network assumptions"
            )
        
        return ValidationResult(valid=len(issues) == 0, issues=issues)


# Singleton instances
CAH_CONSTRAINTS = CAHConstraints()
MVCAHI_CONSTRAINTS = MVCAHIConstraints()

