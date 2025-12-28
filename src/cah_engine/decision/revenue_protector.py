"""
Revenue Protector

Maximize clean claim rate and minimize revenue leakage.
Pre-bill scrubbing and denial management.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional
from enum import Enum

from cah_engine.core.models import Claim, Issue, ScrubResult
from cah_engine.core.enums import Severity, IssueCategory, ClaimStatus


class ScrubStatus(str, Enum):
    """Status from scrubbing process."""
    
    CLEAN = "clean"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class EligibilityResult:
    """Result of eligibility verification."""
    
    active: bool
    payer_name: str = ""
    plan_name: str = ""
    effective_date: Optional[date] = None
    termination_date: Optional[date] = None
    copay: Decimal = Decimal("0")
    deductible_remaining: Decimal = Decimal("0")
    reason: str = ""


@dataclass
class MedicalNecessityResult:
    """Result of medical necessity check."""
    
    meets_criteria: bool
    risk_score: float = 0.0  # 0-1
    reason: str = ""
    suggested_documentation: str = ""
    lcd_ncd_reference: str = ""  # Local/National Coverage Determination


@dataclass
class CodingValidationResult:
    """Result of coding validation."""
    
    valid: bool
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    suggested_corrections: list[str] = field(default_factory=list)


@dataclass
class AuthorizationResult:
    """Result of authorization check."""
    
    required: bool
    obtained: bool
    auth_number: str = ""
    expiration_date: Optional[date] = None
    services_authorized: list[str] = field(default_factory=list)


@dataclass
class DenialWorkItem:
    """Work item for denial follow-up."""
    
    claim_id: str
    denial_date: date
    denial_reason: str
    carc_codes: list[str]
    denied_amount: Decimal
    
    # Priority and routing
    priority: int = 5  # 1 = highest
    assigned_to: str = ""
    due_date: Optional[date] = None
    
    # Status
    status: str = "new"  # new, in_progress, appealed, resolved, written_off
    resolution_amount: Decimal = Decimal("0")
    
    # Actions
    recommended_action: str = ""
    appeal_template: str = ""
    
    @property
    def recovery_potential(self) -> Decimal:
        """Estimated recovery potential."""
        # Based on denial type and historical recovery rates
        base_potential = self.denied_amount
        
        # Adjust based on denial reason
        if "timely" in self.denial_reason.lower():
            return base_potential * Decimal("0.2")
        elif "authorization" in self.denial_reason.lower():
            return base_potential * Decimal("0.5")
        elif "coding" in self.denial_reason.lower():
            return base_potential * Decimal("0.85")
        
        return base_potential * Decimal("0.5")


class PreBillScrubber:
    """
    Identify and prevent claim denials before submission.
    
    Checks:
    - Eligibility verification
    - Medical necessity
    - Coding accuracy
    - Authorization requirements
    """
    
    def __init__(self):
        # Payer-specific rules (simplified)
        self.payer_rules = {
            "medicare": {
                "timely_filing_days": 365,
                "auth_required_services": ["mri", "pet", "snf"],
            },
            "medicaid": {
                "timely_filing_days": 180,
                "auth_required_services": ["mri", "snf", "dme"],
            },
            "commercial": {
                "timely_filing_days": 90,
                "auth_required_services": ["surgery", "mri", "ct", "snf"],
            },
        }
        
        # LCD/NCD reference (simplified)
        self.medical_necessity_rules = {
            # CPT codes requiring specific diagnosis
            "99223": ["I21", "I50", "J18", "N17"],  # High-level inpatient E/M
            "71250": ["J18", "C34", "R91"],  # CT chest
        }
    
    def scrub(self, claim: Claim) -> ScrubResult:
        """
        Run all scrubbing rules on a claim.
        
        Args:
            claim: Claim to scrub
            
        Returns:
            ScrubResult with identified issues
        """
        issues = []
        
        # 1. Eligibility verification
        eligibility = self._verify_eligibility(claim)
        if not eligibility.active:
            issues.append(Issue(
                severity=Severity.BLOCKER,
                category=IssueCategory.ELIGIBILITY,
                message=f"Patient not eligible on DOS: {eligibility.reason}",
                action="Verify coverage, update demographics",
            ))
        
        # 2. Medical necessity check
        necessity = self._check_medical_necessity(claim)
        if necessity.risk_score > 0.7:
            issues.append(Issue(
                severity=Severity.HIGH,
                category=IssueCategory.MEDICAL_NECESSITY,
                message=f"High denial risk ({necessity.risk_score:.0%}): {necessity.reason}",
                action=necessity.suggested_documentation,
            ))
        elif necessity.risk_score > 0.4:
            issues.append(Issue(
                severity=Severity.WARNING,
                category=IssueCategory.MEDICAL_NECESSITY,
                message=f"Moderate denial risk ({necessity.risk_score:.0%})",
                action="Review documentation completeness",
            ))
        
        # 3. Coding validation
        coding = self._validate_coding(claim)
        for error in coding.errors:
            issues.append(error)
        for warning in coding.warnings:
            issues.append(warning)
        
        # 4. Authorization check
        auth = self._check_authorization(claim)
        if auth.required and not auth.obtained:
            issues.append(Issue(
                severity=Severity.BLOCKER,
                category=IssueCategory.AUTHORIZATION,
                message="Prior authorization required but not documented",
                action="Obtain retro-auth or append auth number",
            ))
        
        # 5. Timely filing check
        filing_issue = self._check_timely_filing(claim)
        if filing_issue:
            issues.append(filing_issue)
        
        # Determine overall status
        status = self._determine_status(issues)
        
        # Calculate clean claim probability
        clean_probability = self._calculate_clean_probability(issues)
        
        # Estimate payment
        estimated_payment = self._estimate_payment(claim, issues)
        
        return ScrubResult(
            claim_id=claim.claim_id,
            status=status,
            issues=issues,
            clean_claim_probability=clean_probability,
            estimated_payment=estimated_payment,
        )
    
    def _verify_eligibility(self, claim: Claim) -> EligibilityResult:
        """Verify patient eligibility."""
        # In production, would call payer eligibility API
        # For now, return mock active result
        return EligibilityResult(
            active=True,
            payer_name=claim.payer_id,
            reason="" if True else "Coverage terminated",
        )
    
    def _check_medical_necessity(self, claim: Claim) -> MedicalNecessityResult:
        """Check medical necessity against LCD/NCD."""
        risk_score = 0.0
        reason = ""
        suggested_doc = ""
        
        # Check procedure-diagnosis alignment
        for proc in claim.procedure_codes:
            if proc in self.medical_necessity_rules:
                required_dx = self.medical_necessity_rules[proc]
                has_supporting_dx = any(
                    dx.startswith(tuple(required_dx))
                    for dx in claim.diagnosis_codes
                )
                
                if not has_supporting_dx:
                    risk_score = max(risk_score, 0.75)
                    reason = f"Procedure {proc} may not be supported by diagnosis"
                    suggested_doc = "Add supporting diagnosis or document medical necessity"
        
        # Check for high-cost services without clear indication
        if not claim.diagnosis_codes:
            risk_score = max(risk_score, 0.9)
            reason = "No diagnosis codes to support services"
        
        return MedicalNecessityResult(
            meets_criteria=risk_score < 0.5,
            risk_score=risk_score,
            reason=reason,
            suggested_documentation=suggested_doc,
        )
    
    def _validate_coding(self, claim: Claim) -> CodingValidationResult:
        """Validate coding accuracy."""
        errors = []
        warnings = []
        suggestions = []
        
        # Check diagnosis codes
        for dx in claim.diagnosis_codes:
            if not self._is_valid_icd10(dx):
                errors.append(Issue(
                    severity=Severity.HIGH,
                    category=IssueCategory.CODING,
                    message=f"Invalid ICD-10 code format: {dx}",
                    action="Verify and correct diagnosis code",
                ))
        
        # Check procedure codes
        for proc in claim.procedure_codes:
            if not self._is_valid_cpt(proc) and not self._is_valid_icd10_pcs(proc):
                warnings.append(Issue(
                    severity=Severity.WARNING,
                    category=IssueCategory.CODING,
                    message=f"Procedure code {proc} format not recognized",
                    action="Verify procedure code",
                ))
        
        # Check for missing primary diagnosis
        if not claim.diagnosis_codes:
            errors.append(Issue(
                severity=Severity.BLOCKER,
                category=IssueCategory.CODING,
                message="No diagnosis codes on claim",
                action="Add appropriate diagnosis codes",
            ))
        
        return CodingValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggested_corrections=suggestions,
        )
    
    def _check_authorization(self, claim: Claim) -> AuthorizationResult:
        """Check if prior authorization is required."""
        payer_type = claim.payer_id.lower()
        rules = self.payer_rules.get(payer_type, self.payer_rules["commercial"])
        
        required_services = rules.get("auth_required_services", [])
        
        # Check if any service requires auth
        requires_auth = any(
            service in proc.lower()
            for proc in claim.procedure_codes
            for service in required_services
        )
        
        return AuthorizationResult(
            required=requires_auth,
            obtained=False,  # Would check in production
        )
    
    def _check_timely_filing(self, claim: Claim) -> Optional[Issue]:
        """Check timely filing deadline."""
        payer_type = claim.payer_id.lower()
        rules = self.payer_rules.get(payer_type, self.payer_rules["commercial"])
        filing_days = rules.get("timely_filing_days", 90)
        
        days_since_service = (date.today() - claim.service_date).days
        
        if days_since_service > filing_days:
            return Issue(
                severity=Severity.BLOCKER,
                category=IssueCategory.TIMELY_FILING,
                message=f"Timely filing deadline exceeded ({days_since_service} days > {filing_days} days)",
                action="Submit immediately, may need to appeal",
            )
        elif days_since_service > filing_days * 0.8:
            return Issue(
                severity=Severity.HIGH,
                category=IssueCategory.TIMELY_FILING,
                message=f"Approaching timely filing deadline ({days_since_service} of {filing_days} days)",
                action="Submit within 5 business days",
            )
        
        return None
    
    def _determine_status(self, issues: list[Issue]) -> str:
        """Determine overall claim status from issues."""
        if any(i.severity == Severity.BLOCKER for i in issues):
            return ScrubStatus.BLOCKED.value
        elif any(i.severity in (Severity.HIGH, Severity.WARNING) for i in issues):
            return ScrubStatus.WARNING.value
        return ScrubStatus.CLEAN.value
    
    def _calculate_clean_probability(self, issues: list[Issue]) -> float:
        """Calculate probability of clean claim."""
        probability = 1.0
        
        for issue in issues:
            if issue.severity == Severity.BLOCKER:
                probability *= 0.1
            elif issue.severity == Severity.HIGH:
                probability *= 0.6
            elif issue.severity == Severity.WARNING:
                probability *= 0.85
        
        return max(0.01, probability)
    
    def _estimate_payment(self, claim: Claim, issues: list[Issue]) -> Decimal:
        """Estimate expected payment."""
        clean_prob = self._calculate_clean_probability(issues)
        return claim.total_charges * Decimal(str(clean_prob))
    
    def _is_valid_icd10(self, code: str) -> bool:
        """Validate ICD-10 format."""
        if not code or len(code) < 3:
            return False
        return code[0].isalpha() and code[1:3].isdigit()
    
    def _is_valid_cpt(self, code: str) -> bool:
        """Validate CPT format."""
        if not code or len(code) != 5:
            return False
        return code.isdigit()
    
    def _is_valid_icd10_pcs(self, code: str) -> bool:
        """Validate ICD-10-PCS format."""
        if not code or len(code) != 7:
            return False
        return code.isalnum()


class DenialWorklistManager:
    """
    Manage denial worklist and recovery efforts.
    """
    
    def __init__(self):
        self.worklist: list[DenialWorkItem] = []
        self.appeal_templates = self._load_appeal_templates()
    
    def add_denial(
        self,
        claim_id: str,
        denial_date: date,
        denial_reason: str,
        carc_codes: list[str],
        denied_amount: Decimal,
    ) -> DenialWorkItem:
        """Add a denial to the worklist."""
        # Determine priority based on amount and denial type
        priority = self._calculate_priority(denied_amount, carc_codes)
        
        # Get recommended action
        action = self._get_recommended_action(carc_codes)
        
        # Select appeal template
        template = self._select_appeal_template(carc_codes)
        
        # Calculate due date (typically 60-180 days)
        due_date = denial_date + timedelta(days=60)
        
        work_item = DenialWorkItem(
            claim_id=claim_id,
            denial_date=denial_date,
            denial_reason=denial_reason,
            carc_codes=carc_codes,
            denied_amount=denied_amount,
            priority=priority,
            due_date=due_date,
            recommended_action=action,
            appeal_template=template,
        )
        
        self.worklist.append(work_item)
        self._sort_worklist()
        
        return work_item
    
    def get_worklist(
        self,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        assigned_to: Optional[str] = None,
    ) -> list[DenialWorkItem]:
        """Get filtered worklist."""
        items = self.worklist
        
        if status:
            items = [i for i in items if i.status == status]
        if priority:
            items = [i for i in items if i.priority <= priority]
        if assigned_to:
            items = [i for i in items if i.assigned_to == assigned_to]
        
        return items
    
    def get_summary(self) -> dict[str, Any]:
        """Get worklist summary statistics."""
        total_denied = sum(i.denied_amount for i in self.worklist)
        total_potential = sum(i.recovery_potential for i in self.worklist)
        
        by_status = {}
        for item in self.worklist:
            by_status[item.status] = by_status.get(item.status, 0) + 1
        
        by_priority = {}
        for item in self.worklist:
            by_priority[item.priority] = by_priority.get(item.priority, 0) + 1
        
        return {
            "total_items": len(self.worklist),
            "total_denied_amount": float(total_denied),
            "total_recovery_potential": float(total_potential),
            "by_status": by_status,
            "by_priority": by_priority,
            "overdue_count": len([i for i in self.worklist if i.due_date and i.due_date < date.today()]),
        }
    
    def update_status(
        self,
        claim_id: str,
        new_status: str,
        resolution_amount: Optional[Decimal] = None,
    ) -> Optional[DenialWorkItem]:
        """Update work item status."""
        for item in self.worklist:
            if item.claim_id == claim_id:
                item.status = new_status
                if resolution_amount is not None:
                    item.resolution_amount = resolution_amount
                return item
        return None
    
    def _calculate_priority(
        self,
        amount: Decimal,
        carc_codes: list[str],
    ) -> int:
        """Calculate work item priority (1=highest, 5=lowest)."""
        # High dollar = high priority
        if amount > Decimal("10000"):
            priority = 1
        elif amount > Decimal("5000"):
            priority = 2
        elif amount > Decimal("1000"):
            priority = 3
        else:
            priority = 4
        
        # Adjust for denial type
        recoverable_codes = ["4", "5", "6", "16", "18"]  # Coding errors
        if any(code in recoverable_codes for code in carc_codes):
            priority = max(1, priority - 1)  # Higher priority for recoverable
        
        return priority
    
    def _get_recommended_action(self, carc_codes: list[str]) -> str:
        """Get recommended action based on CARC codes."""
        actions = {
            "1": "Verify deductible applied correctly",
            "2": "Verify coinsurance calculation",
            "3": "Verify copay amount",
            "4": "Review coding, correct modifier",
            "5": "Review place of service coding",
            "15": "Obtain retro-authorization and appeal",
            "16": "Add missing documentation and resubmit",
            "18": "Verify not duplicate, appeal if not",
            "29": "Appeal with proof of timely submission",
        }
        
        for code in carc_codes:
            if code in actions:
                return actions[code]
        
        return "Review denial and determine appropriate action"
    
    def _select_appeal_template(self, carc_codes: list[str]) -> str:
        """Select appropriate appeal template."""
        if any(code in ["4", "5", "6"] for code in carc_codes):
            return "coding_correction_appeal"
        elif "15" in carc_codes:
            return "authorization_appeal"
        elif "16" in carc_codes:
            return "documentation_appeal"
        elif "29" in carc_codes:
            return "timely_filing_appeal"
        return "general_appeal"
    
    def _sort_worklist(self) -> None:
        """Sort worklist by priority and due date."""
        self.worklist.sort(key=lambda x: (x.priority, x.due_date or date.max))
    
    def _load_appeal_templates(self) -> dict[str, str]:
        """Load appeal letter templates."""
        return {
            "coding_correction_appeal": """
RE: Appeal for Claim {claim_id}

Dear Appeals Department,

We are writing to appeal the denial of the above-referenced claim. 
Upon review, we have identified and corrected the coding issue.

Original Code: {original_code}
Corrected Code: {corrected_code}
Supporting Documentation: Attached

We respectfully request reconsideration of this claim.

Sincerely,
{facility_name}
""",
            "authorization_appeal": """
RE: Appeal for Claim {claim_id} - Authorization Issue

Dear Appeals Department,

We are appealing the denial of the above claim for lack of prior authorization.

The service was provided on an emergent basis as documented in the attached 
clinical records. Per your emergency services policy, prior authorization 
was not required for this medical emergency.

Please find attached:
- Emergency department records
- Physician statement of medical necessity

We request reconsideration of this claim.

Sincerely,
{facility_name}
""",
            "general_appeal": """
RE: Appeal for Claim {claim_id}

Dear Appeals Department,

We are writing to appeal the denial of the above-referenced claim.

Denial Reason: {denial_reason}
Date of Service: {date_of_service}
Billed Amount: {billed_amount}

We believe this claim was denied in error for the following reasons:
{appeal_rationale}

Supporting documentation is attached.

We respectfully request reconsideration of this claim.

Sincerely,
{facility_name}
""",
        }


class RevenueProtector:
    """
    Main revenue protection coordinator.
    
    Combines pre-bill scrubbing with denial management.
    """
    
    def __init__(self):
        self.scrubber = PreBillScrubber()
        self.denial_manager = DenialWorklistManager()
    
    def scrub_claim(self, claim: Claim) -> ScrubResult:
        """Scrub a claim before submission."""
        return self.scrubber.scrub(claim)
    
    def scrub_batch(self, claims: list[Claim]) -> list[ScrubResult]:
        """Scrub multiple claims."""
        return [self.scrubber.scrub(claim) for claim in claims]
    
    def add_denial(
        self,
        claim_id: str,
        denial_date: date,
        denial_reason: str,
        carc_codes: list[str],
        denied_amount: Decimal,
    ) -> DenialWorkItem:
        """Add a denial for follow-up."""
        return self.denial_manager.add_denial(
            claim_id=claim_id,
            denial_date=denial_date,
            denial_reason=denial_reason,
            carc_codes=carc_codes,
            denied_amount=denied_amount,
        )
    
    def get_dashboard_data(self) -> dict[str, Any]:
        """Get data for revenue protection dashboard."""
        worklist_summary = self.denial_manager.get_summary()
        
        return {
            "worklist": worklist_summary,
            "action_items": [
                {
                    "claim_id": item.claim_id,
                    "denied_amount": float(item.denied_amount),
                    "recovery_potential": float(item.recovery_potential),
                    "action": item.recommended_action,
                    "due_date": item.due_date.isoformat() if item.due_date else None,
                }
                for item in self.denial_manager.get_worklist(status="new")[:10]
            ],
            "metrics": {
                "total_at_risk": worklist_summary["total_denied_amount"],
                "recovery_potential": worklist_summary["total_recovery_potential"],
                "items_overdue": worklist_summary["overdue_count"],
            },
        }


# Import timedelta
from datetime import timedelta

