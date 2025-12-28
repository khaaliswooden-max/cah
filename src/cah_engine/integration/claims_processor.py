"""
Claims Processor

Parse X12 837/835 transactions for revenue cycle analysis.
Provides denial categorization and revenue tracking.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Optional
from enum import Enum

from cah_engine.core.models import Claim, Issue, ValidationResult
from cah_engine.core.enums import ClaimStatus, IssueCategory, Severity


class DenialCategory(str, Enum):
    """Claim denial categories."""
    
    ELIGIBILITY = "eligibility"
    MEDICAL_NECESSITY = "medical_necessity"
    CODING = "coding"
    AUTHORIZATION = "authorization"
    TIMELY_FILING = "timely_filing"
    NON_COVERED = "non_covered"
    DUPLICATE = "duplicate"
    OTHER = "other"


@dataclass
class DenialInfo:
    """Information about a claim denial."""
    
    category: DenialCategory
    carc_code: str  # Claim Adjustment Reason Code
    rarc_code: str = ""  # Remittance Advice Remark Code
    amount: Decimal = Decimal("0")
    description: str = ""
    addressable: bool = True
    recommended_action: str = ""


@dataclass
class RemittanceInfo:
    """835 remittance information."""
    
    claim_id: str
    payer_claim_id: str
    status: str
    paid_amount: Decimal
    patient_responsibility: Decimal
    adjustments: list[DenialInfo] = field(default_factory=list)
    service_date: Optional[date] = None
    payment_date: Optional[date] = None
    
    @property
    def total_denied(self) -> Decimal:
        """Total denied amount."""
        return sum(adj.amount for adj in self.adjustments)


@dataclass
class ClaimAnalysis:
    """Analysis results for a claim."""
    
    claim: Claim
    denial_probability: float = 0.0
    denial_reasons: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    estimated_payment: Decimal = Decimal("0")
    risk_factors: dict[str, float] = field(default_factory=dict)


class X12Parser:
    """
    Parse X12 EDI transactions.
    
    Supports:
    - 837I: Institutional claims
    - 837P: Professional claims
    - 835: Remittance advice
    """
    
    def __init__(self):
        self.segment_terminator = "~"
        self.element_separator = "*"
        self.component_separator = ":"
    
    def parse_837(self, content: str) -> Iterator[Claim]:
        """Parse 837 claim file and yield claims."""
        segments = self._split_segments(content)
        
        # Determine claim type from GS segment
        claim_type = "837I"  # Default
        for seg in segments:
            if seg.startswith("GS"):
                elements = seg.split(self.element_separator)
                if len(elements) > 1:
                    if elements[1] == "HC":
                        claim_type = "837P"
                    elif elements[1] == "HB":
                        claim_type = "837I"
                break
        
        # Parse each claim (CLM segment starts a new claim)
        current_claim_data: dict = {}
        
        for seg in segments:
            seg_type = seg[:3] if len(seg) >= 3 else seg
            elements = seg.split(self.element_separator)
            
            if seg_type == "CLM":
                # Save previous claim if exists
                if current_claim_data.get("claim_id"):
                    yield self._build_claim(current_claim_data, claim_type)
                
                # Start new claim
                current_claim_data = {
                    "claim_id": elements[1] if len(elements) > 1 else "",
                    "total_charges": self._parse_decimal(elements[2]) if len(elements) > 2 else Decimal("0"),
                    "diagnosis_codes": [],
                    "procedure_codes": [],
                }
            
            elif seg_type == "NM1":
                # Name segment - identify patient, payer, etc.
                entity_type = elements[1] if len(elements) > 1 else ""
                
                if entity_type == "IL":  # Insured/subscriber
                    current_claim_data["patient_id"] = elements[9] if len(elements) > 9 else ""
                elif entity_type == "PR":  # Payer
                    current_claim_data["payer_id"] = elements[9] if len(elements) > 9 else ""
            
            elif seg_type == "DTP":
                # Date/time period
                date_qualifier = elements[1] if len(elements) > 1 else ""
                if date_qualifier == "472":  # Service date
                    date_str = elements[3] if len(elements) > 3 else ""
                    current_claim_data["service_date"] = self._parse_date(date_str)
            
            elif seg_type == "HI":
                # Health care diagnosis/procedure codes
                for i in range(1, len(elements)):
                    code_info = elements[i].split(self.component_separator)
                    if code_info:
                        code_type = code_info[0]
                        code_value = code_info[1] if len(code_info) > 1 else ""
                        
                        if code_type in ("ABK", "ABF"):  # ICD-10 diagnosis
                            current_claim_data["diagnosis_codes"].append(code_value)
                        elif code_type in ("BBR", "BBQ"):  # ICD-10 procedure
                            current_claim_data["procedure_codes"].append(code_value)
            
            elif seg_type == "SV1" or seg_type == "SV2":
                # Service line - extract procedure codes
                if len(elements) > 1:
                    proc_info = elements[1].split(self.component_separator)
                    if proc_info:
                        current_claim_data["procedure_codes"].append(proc_info[1] if len(proc_info) > 1 else proc_info[0])
        
        # Yield last claim
        if current_claim_data.get("claim_id"):
            yield self._build_claim(current_claim_data, claim_type)
    
    def parse_835(self, content: str) -> Iterator[RemittanceInfo]:
        """Parse 835 remittance advice and yield remittance info."""
        segments = self._split_segments(content)
        
        current_remit: dict = {}
        current_adjustments: list[DenialInfo] = []
        
        for seg in segments:
            seg_type = seg[:3] if len(seg) >= 3 else seg
            elements = seg.split(self.element_separator)
            
            if seg_type == "CLP":
                # Claim payment info - new remittance
                if current_remit.get("claim_id"):
                    yield self._build_remittance(current_remit, current_adjustments)
                
                current_remit = {
                    "claim_id": elements[1] if len(elements) > 1 else "",
                    "status": elements[2] if len(elements) > 2 else "",
                    "charged_amount": self._parse_decimal(elements[3]) if len(elements) > 3 else Decimal("0"),
                    "paid_amount": self._parse_decimal(elements[4]) if len(elements) > 4 else Decimal("0"),
                    "patient_responsibility": self._parse_decimal(elements[5]) if len(elements) > 5 else Decimal("0"),
                    "payer_claim_id": elements[7] if len(elements) > 7 else "",
                }
                current_adjustments = []
            
            elif seg_type == "CAS":
                # Claim adjustment
                group_code = elements[1] if len(elements) > 1 else ""
                
                # Parse adjustment pairs (reason code, amount)
                i = 2
                while i + 1 < len(elements):
                    reason_code = elements[i]
                    amount = self._parse_decimal(elements[i + 1]) if i + 1 < len(elements) else Decimal("0")
                    
                    if reason_code:
                        adjustment = self._build_adjustment(group_code, reason_code, amount)
                        current_adjustments.append(adjustment)
                    
                    i += 3  # Skip to next reason code pair
            
            elif seg_type == "DTM":
                # Date segment
                date_qualifier = elements[1] if len(elements) > 1 else ""
                date_str = elements[2] if len(elements) > 2 else ""
                
                if date_qualifier == "472":  # Service date
                    current_remit["service_date"] = self._parse_date(date_str)
                elif date_qualifier == "573":  # Payment date
                    current_remit["payment_date"] = self._parse_date(date_str)
        
        # Yield last remittance
        if current_remit.get("claim_id"):
            yield self._build_remittance(current_remit, current_adjustments)
    
    def _split_segments(self, content: str) -> list[str]:
        """Split X12 content into segments."""
        # Handle different line endings
        content = content.replace("\r\n", "").replace("\n", "").replace("\r", "")
        
        # Split by segment terminator
        segments = content.split(self.segment_terminator)
        
        return [s.strip() for s in segments if s.strip()]
    
    def _parse_decimal(self, value: str) -> Decimal:
        """Parse decimal value from X12 element."""
        try:
            return Decimal(value.strip())
        except Exception:
            return Decimal("0")
    
    def _parse_date(self, value: str) -> Optional[date]:
        """Parse date from X12 element (CCYYMMDD format)."""
        try:
            return datetime.strptime(value.strip(), "%Y%m%d").date()
        except Exception:
            return None
    
    def _build_claim(self, data: dict, claim_type: str) -> Claim:
        """Build Claim object from parsed data."""
        return Claim(
            claim_id=data.get("claim_id", ""),
            patient_id=data.get("patient_id", ""),
            encounter_id=data.get("encounter_id", ""),
            payer_id=data.get("payer_id", ""),
            service_date=data.get("service_date", date.today()),
            claim_type=claim_type,
            total_charges=data.get("total_charges", Decimal("0")),
            diagnosis_codes=data.get("diagnosis_codes", []),
            procedure_codes=data.get("procedure_codes", []),
            status=ClaimStatus.SUBMITTED,
        )
    
    def _build_remittance(
        self,
        data: dict,
        adjustments: list[DenialInfo],
    ) -> RemittanceInfo:
        """Build RemittanceInfo from parsed data."""
        return RemittanceInfo(
            claim_id=data.get("claim_id", ""),
            payer_claim_id=data.get("payer_claim_id", ""),
            status=data.get("status", ""),
            paid_amount=data.get("paid_amount", Decimal("0")),
            patient_responsibility=data.get("patient_responsibility", Decimal("0")),
            adjustments=adjustments,
            service_date=data.get("service_date"),
            payment_date=data.get("payment_date"),
        )
    
    def _build_adjustment(
        self,
        group_code: str,
        reason_code: str,
        amount: Decimal,
    ) -> DenialInfo:
        """Build DenialInfo from adjustment data."""
        category = self._categorize_denial(reason_code)
        description = self._get_carc_description(reason_code)
        
        return DenialInfo(
            category=category,
            carc_code=reason_code,
            amount=amount,
            description=description,
            addressable=category not in (DenialCategory.NON_COVERED,),
            recommended_action=self._get_recommended_action(category, reason_code),
        )
    
    def _categorize_denial(self, carc_code: str) -> DenialCategory:
        """Categorize denial by CARC code."""
        # Eligibility codes
        if carc_code in ("1", "2", "3", "27", "28", "29", "109", "180"):
            return DenialCategory.ELIGIBILITY
        
        # Medical necessity
        if carc_code in ("50", "55", "56", "57", "58", "96", "97", "167"):
            return DenialCategory.MEDICAL_NECESSITY
        
        # Coding errors
        if carc_code in ("4", "5", "6", "16", "18", "19", "151", "152"):
            return DenialCategory.CODING
        
        # Authorization
        if carc_code in ("15", "197", "198", "199"):
            return DenialCategory.AUTHORIZATION
        
        # Timely filing
        if carc_code in ("29"):
            return DenialCategory.TIMELY_FILING
        
        # Duplicate
        if carc_code in ("18", "B15"):
            return DenialCategory.DUPLICATE
        
        return DenialCategory.OTHER
    
    def _get_carc_description(self, carc_code: str) -> str:
        """Get description for CARC code."""
        descriptions = {
            "1": "Deductible Amount",
            "2": "Coinsurance Amount",
            "3": "Co-payment Amount",
            "4": "The procedure code is inconsistent with the modifier used",
            "5": "The procedure code/bill type is inconsistent with the place of service",
            "6": "The procedure code is inconsistent with the patient's age",
            "15": "Authorization/pre-certification absent",
            "16": "Claim/service lacks information",
            "18": "Exact duplicate claim/service",
            "27": "Expenses incurred after coverage terminated",
            "29": "The time limit for filing has expired",
            "50": "Non-covered services",
            "55": "Procedure/treatment is deemed experimental",
            "56": "Procedure/treatment has not been deemed 'proven to be effective'",
            "96": "Non-covered charge(s)",
            "97": "The benefit for this service is included in the payment for another service",
            "109": "Claim/service not covered by this payer/contractor",
        }
        return descriptions.get(carc_code, f"CARC {carc_code}")
    
    def _get_recommended_action(
        self,
        category: DenialCategory,
        carc_code: str,
    ) -> str:
        """Get recommended action for denial category."""
        actions = {
            DenialCategory.ELIGIBILITY: "Verify patient coverage, update demographics, resubmit",
            DenialCategory.MEDICAL_NECESSITY: "Obtain additional documentation, submit appeal with clinical notes",
            DenialCategory.CODING: "Review coding, correct and resubmit",
            DenialCategory.AUTHORIZATION: "Obtain retro-authorization if possible, or submit appeal",
            DenialCategory.TIMELY_FILING: "Submit appeal with proof of timely submission if applicable",
            DenialCategory.DUPLICATE: "Verify original claim status, do not resubmit",
            DenialCategory.NON_COVERED: "Patient responsibility, provide ABN if not already signed",
        }
        return actions.get(category, "Review denial and determine appropriate action")


class DenialAnalyzer:
    """
    Analyze claim denials for patterns and improvement opportunities.
    """
    
    def __init__(self):
        self.denial_history: list[DenialInfo] = []
    
    def add_denial(self, denial: DenialInfo) -> None:
        """Add a denial to the analysis history."""
        self.denial_history.append(denial)
    
    def add_remittance(self, remittance: RemittanceInfo) -> None:
        """Add all denials from a remittance."""
        for adj in remittance.adjustments:
            self.denial_history.append(adj)
    
    def get_denial_rate_by_category(self) -> dict[DenialCategory, float]:
        """Calculate denial rate by category."""
        if not self.denial_history:
            return {}
        
        counts: dict[DenialCategory, int] = {}
        for denial in self.denial_history:
            counts[denial.category] = counts.get(denial.category, 0) + 1
        
        total = len(self.denial_history)
        return {cat: count / total for cat, count in counts.items()}
    
    def get_total_denied_amount(self) -> Decimal:
        """Get total denied amount."""
        return sum(d.amount for d in self.denial_history)
    
    def get_addressable_amount(self) -> Decimal:
        """Get total addressable denied amount."""
        return sum(d.amount for d in self.denial_history if d.addressable)
    
    def get_top_denial_reasons(self, n: int = 5) -> list[tuple[str, int, Decimal]]:
        """Get top N denial reasons by count."""
        counts: dict[str, tuple[int, Decimal]] = {}
        
        for denial in self.denial_history:
            key = denial.carc_code
            current = counts.get(key, (0, Decimal("0")))
            counts[key] = (current[0] + 1, current[1] + denial.amount)
        
        sorted_reasons = sorted(counts.items(), key=lambda x: x[1][0], reverse=True)
        
        return [
            (reason, data[0], data[1])
            for reason, data in sorted_reasons[:n]
        ]
    
    def get_recovery_opportunities(self) -> list[dict]:
        """Identify recovery opportunities from addressable denials."""
        opportunities = []
        
        by_category: dict[DenialCategory, list[DenialInfo]] = {}
        for denial in self.denial_history:
            if denial.addressable:
                if denial.category not in by_category:
                    by_category[denial.category] = []
                by_category[denial.category].append(denial)
        
        for category, denials in by_category.items():
            total_amount = sum(d.amount for d in denials)
            opportunities.append({
                "category": category.value,
                "count": len(denials),
                "total_amount": total_amount,
                "recommended_action": denials[0].recommended_action if denials else "",
                "recovery_probability": self._estimate_recovery_probability(category),
                "estimated_recovery": total_amount * Decimal(str(self._estimate_recovery_probability(category))),
            })
        
        return sorted(opportunities, key=lambda x: x["estimated_recovery"], reverse=True)
    
    def _estimate_recovery_probability(self, category: DenialCategory) -> float:
        """Estimate probability of recovering denied amount by category."""
        probabilities = {
            DenialCategory.ELIGIBILITY: 0.7,
            DenialCategory.CODING: 0.85,
            DenialCategory.AUTHORIZATION: 0.5,
            DenialCategory.MEDICAL_NECESSITY: 0.4,
            DenialCategory.TIMELY_FILING: 0.2,
            DenialCategory.DUPLICATE: 0.0,
            DenialCategory.NON_COVERED: 0.1,
            DenialCategory.OTHER: 0.3,
        }
        return probabilities.get(category, 0.3)


class ClaimsProcessor:
    """
    Main claims processing coordinator.
    
    Handles claim parsing, validation, and analysis.
    """
    
    def __init__(self):
        self.parser = X12Parser()
        self.denial_analyzer = DenialAnalyzer()
    
    def process_claims_file(self, file_path: Path | str) -> list[Claim]:
        """Process an 837 claims file."""
        path = Path(file_path)
        
        with open(path, "r") as f:
            content = f.read()
        
        return list(self.parser.parse_837(content))
    
    def process_remittance_file(self, file_path: Path | str) -> list[RemittanceInfo]:
        """Process an 835 remittance file."""
        path = Path(file_path)
        
        with open(path, "r") as f:
            content = f.read()
        
        remittances = list(self.parser.parse_835(content))
        
        # Add to denial analyzer
        for remit in remittances:
            self.denial_analyzer.add_remittance(remit)
        
        return remittances
    
    def analyze_claim(self, claim: Claim) -> ClaimAnalysis:
        """Analyze a claim for potential issues and denial risk."""
        issues = []
        risk_factors = {}
        recommendations = []
        
        # Check for missing required fields
        if not claim.diagnosis_codes:
            issues.append(Issue(
                severity=Severity.HIGH,
                category=IssueCategory.CODING,
                message="No diagnosis codes present",
                action="Add appropriate diagnosis codes",
            ))
            risk_factors["missing_diagnosis"] = 0.9
        
        if not claim.procedure_codes:
            issues.append(Issue(
                severity=Severity.WARNING,
                category=IssueCategory.CODING,
                message="No procedure codes present",
                action="Verify if procedures were performed",
            ))
            risk_factors["missing_procedure"] = 0.3
        
        # Check for common coding issues
        for dx in claim.diagnosis_codes:
            if not self._is_valid_icd10(dx):
                issues.append(Issue(
                    severity=Severity.HIGH,
                    category=IssueCategory.CODING,
                    message=f"Invalid ICD-10 code format: {dx}",
                    action="Verify and correct diagnosis code",
                ))
                risk_factors["invalid_diagnosis"] = 0.8
        
        # Calculate denial probability
        base_probability = 0.10  # Base denial rate
        for factor, weight in risk_factors.items():
            base_probability += weight * 0.2
        
        denial_probability = min(base_probability, 0.95)
        
        # Generate recommendations
        if denial_probability > 0.5:
            recommendations.append("Review claim before submission - high denial risk")
        if "missing_diagnosis" in risk_factors:
            recommendations.append("Ensure complete diagnosis coding")
        if "invalid_diagnosis" in risk_factors:
            recommendations.append("Verify all diagnosis codes against ICD-10-CM")
        
        # Estimate payment
        estimated_payment = claim.total_charges * Decimal(str(1 - denial_probability))
        
        return ClaimAnalysis(
            claim=claim,
            denial_probability=denial_probability,
            denial_reasons=[i.message for i in issues],
            issues=issues,
            recommendations=recommendations,
            estimated_payment=estimated_payment,
            risk_factors=risk_factors,
        )
    
    def get_denial_summary(self) -> dict:
        """Get summary of denial analysis."""
        return {
            "total_denied": float(self.denial_analyzer.get_total_denied_amount()),
            "addressable_amount": float(self.denial_analyzer.get_addressable_amount()),
            "denial_rate_by_category": {
                k.value: v
                for k, v in self.denial_analyzer.get_denial_rate_by_category().items()
            },
            "top_reasons": [
                {"code": r[0], "count": r[1], "amount": float(r[2])}
                for r in self.denial_analyzer.get_top_denial_reasons()
            ],
            "recovery_opportunities": self.denial_analyzer.get_recovery_opportunities(),
        }
    
    def _is_valid_icd10(self, code: str) -> bool:
        """Basic ICD-10 format validation."""
        if not code or len(code) < 3:
            return False
        return code[0].isalpha() and code[1:3].isdigit()

