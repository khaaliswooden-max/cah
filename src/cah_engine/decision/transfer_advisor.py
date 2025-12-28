"""
Transfer Advisor

Real-time transfer decision support for admit/transfer/discharge decisions.
EMTALA-aware recommendations with clinical and financial considerations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from cah_engine.core.models import (
    ClinicalEncounter,
    FacilitySnapshot,
    TransferRecommendation,
)
from cah_engine.core.enums import EncounterType, Severity, RiskTier
from cah_engine.analytics.predictive import TransferRiskModel, RiskScore


class Disposition(str, Enum):
    """Possible patient dispositions."""
    
    ADMIT = "admit"
    TRANSFER = "transfer"
    OBSERVE = "observe"
    DISCHARGE = "discharge"


@dataclass
class PatientPresentation:
    """Patient presentation at ED or admission."""
    
    patient_id: str
    presentation_time: datetime
    chief_complaint: str
    
    # Clinical factors
    age: int = 0
    gender: str = ""
    vital_signs: dict = field(default_factory=dict)
    acuity_level: int = 3  # ESI 1-5
    
    # Diagnosis information
    principal_diagnosis: str = ""
    secondary_diagnoses: list[str] = field(default_factory=list)
    
    # Comorbidities
    charlson_score: int = 0
    
    # Arrival information
    arrival_mode: str = ""  # "ambulance", "walk-in", etc.
    referral_source: str = ""
    
    # Clinical needs
    anticipated_procedures: list[str] = field(default_factory=list)
    specialist_needs: list[str] = field(default_factory=list)
    icu_level_care: bool = False
    surgical_need: bool = False
    
    @property
    def is_high_acuity(self) -> bool:
        """Check if patient is high acuity."""
        return self.acuity_level <= 2


@dataclass
class CapabilityScore:
    """Assessment of facility capability to treat a patient."""
    
    can_treat: bool
    score: float = 0.0  # 0-100
    service_gaps: list[str] = field(default_factory=list)
    specialist_available: bool = True
    equipment_available: bool = True
    capacity_available: bool = True
    
    @property
    def gap_summary(self) -> str:
        """Summarize capability gaps."""
        if not self.service_gaps:
            return "No capability gaps identified"
        return f"Gaps: {', '.join(self.service_gaps)}"


@dataclass
class OutcomePrediction:
    """Predicted outcome for a disposition."""
    
    disposition: Disposition
    success_probability: float  # Probability of good outcome
    los_estimate_hours: float
    complication_risk: float
    mortality_risk: float
    readmission_risk: float
    financial_impact: float  # Estimated contribution margin


@dataclass
class Alternative:
    """Alternative disposition option."""
    
    disposition: Disposition
    utility_score: float
    outcome: OutcomePrediction
    rationale: str


@dataclass
class Facility:
    """Facility capabilities and current state."""
    
    facility_id: str
    staffed_beds: int = 25
    current_census: int = 10
    
    # Capabilities
    services_available: set[str] = field(default_factory=set)
    specialists_on_call: set[str] = field(default_factory=set)
    equipment_available: set[str] = field(default_factory=set)
    
    # Financial parameters
    revenue_per_encounter: float = 15000.0
    cost_per_patient_day: float = 3000.0
    transfer_cost: float = 2000.0
    
    def __post_init__(self):
        if not self.services_available:
            # Default CAH services
            self.services_available = {
                "emergency", "radiology", "laboratory",
                "basic_surgery", "swing_bed", "observation",
            }


class TransferAdvisor:
    """
    Real-time transfer decision support.
    
    Decision Framework:
    Decision = argmax_{d ∈ {admit, transfer, observe}} E[U(d | patient, facility)]
    
    Where utility U considers:
    - Patient outcome probability
    - Financial impact
    - Resource availability
    - Regulatory compliance (EMTALA)
    """
    
    def __init__(self, facility: Facility):
        self.facility = facility
        self.risk_model = TransferRiskModel()
        
        # Services requiring transfer
        self.transfer_required_services = {
            "cardiac_cath": ["I21", "I22"],  # MI
            "stroke_intervention": ["I63", "I64", "G45"],  # Stroke
            "trauma_surgery": ["S"],  # Trauma
            "nicu": [],  # Neonatal
            "picu": [],  # Pediatric ICU
        }
        
        # Utility weights (configurable)
        self.weights = {
            "outcome": 0.5,
            "financial": 0.2,
            "resource": 0.2,
            "compliance": 0.1,
        }
    
    def evaluate(self, patient: PatientPresentation) -> TransferRecommendation:
        """
        Generate transfer recommendation with evidence.
        
        Args:
            patient: Patient presentation data
            
        Returns:
            TransferRecommendation with rationale and alternatives
        """
        # Step 1: Assess capability to treat
        capability = self._assess_capability(patient)
        
        # Step 2: Predict outcomes by disposition
        outcomes = {
            Disposition.ADMIT: self._predict_outcome(patient, Disposition.ADMIT),
            Disposition.TRANSFER: self._predict_outcome(patient, Disposition.TRANSFER),
            Disposition.OBSERVE: self._predict_outcome(patient, Disposition.OBSERVE),
        }
        
        # Step 3: Check constraints (EMTALA, capacity, etc.)
        constraints = self._check_constraints(patient, capability)
        
        # Step 4: Calculate utility for each option
        utilities = {}
        for disposition, outcome in outcomes.items():
            if constraints.get(disposition, {}).get("feasible", True):
                utilities[disposition] = self._calculate_utility(
                    outcome=outcome,
                    capability=capability,
                    patient=patient,
                )
            else:
                utilities[disposition] = float("-inf")
        
        # Step 5: Select optimal disposition
        best = max(utilities, key=lambda d: utilities[d])
        
        # Generate risk score
        risk_score = self.risk_model.predict(
            encounter=ClinicalEncounter(
                encounter_id=f"eval_{datetime.now().timestamp()}",
                patient_id=patient.patient_id,
                admit_datetime=patient.presentation_time,
                discharge_datetime=None,
                encounter_type=EncounterType.EMERGENCY,
                principal_diagnosis=patient.principal_diagnosis,
                secondary_diagnoses=patient.secondary_diagnoses,
            ),
            current_census=self.facility.current_census,
            specialist_available=capability.specialist_available,
        )
        
        return TransferRecommendation(
            recommendation=best.value,
            confidence=self._calculate_confidence(utilities, best),
            rationale=self._generate_rationale(patient, best, outcomes, constraints, capability),
            alternatives=[
                Alternative(
                    disposition=d,
                    utility_score=utilities[d],
                    outcome=outcomes[d],
                    rationale=self._disposition_rationale(d, outcomes[d], constraints),
                )
                for d in utilities if d != best and utilities[d] > float("-inf")
            ],
            emtala_compliant=constraints.get("emtala_compliant", True),
            risk_score=risk_score.score,
            contributing_factors=[f[0] for f in risk_score.top_factors],
        )
    
    def _assess_capability(self, patient: PatientPresentation) -> CapabilityScore:
        """Assess facility capability to treat this patient."""
        service_gaps = []
        specialist_available = True
        equipment_available = True
        
        # Check for required services
        required_services = self._identify_required_services(patient)
        for service in required_services:
            if service not in self.facility.services_available:
                service_gaps.append(service)
        
        # Check specialist availability
        for specialist in patient.specialist_needs:
            if specialist not in self.facility.specialists_on_call:
                specialist_available = False
                service_gaps.append(f"{specialist}_coverage")
        
        # Check equipment
        required_equipment = self._identify_required_equipment(patient)
        for equipment in required_equipment:
            if equipment not in self.facility.equipment_available:
                equipment_available = False
                service_gaps.append(f"{equipment}_equipment")
        
        # Check capacity
        capacity_available = self.facility.current_census < self.facility.staffed_beds
        
        # Calculate overall capability score
        can_treat = len(service_gaps) == 0 and capacity_available
        score = 100.0
        score -= len(service_gaps) * 20
        if not specialist_available:
            score -= 30
        if not capacity_available:
            score -= 40
        score = max(0, score)
        
        return CapabilityScore(
            can_treat=can_treat,
            score=score,
            service_gaps=service_gaps,
            specialist_available=specialist_available,
            equipment_available=equipment_available,
            capacity_available=capacity_available,
        )
    
    def _identify_required_services(self, patient: PatientPresentation) -> set[str]:
        """Identify services required to treat this patient."""
        required = set()
        
        dx = patient.principal_diagnosis.upper()
        
        # Check against transfer-required services
        for service, prefixes in self.transfer_required_services.items():
            for prefix in prefixes:
                if dx.startswith(prefix):
                    required.add(service)
        
        # ICU need
        if patient.icu_level_care:
            required.add("icu")
        
        # Surgical need
        if patient.surgical_need:
            required.add("surgery")
        
        return required
    
    def _identify_required_equipment(self, patient: PatientPresentation) -> set[str]:
        """Identify equipment required for procedures."""
        required = set()
        
        for proc in patient.anticipated_procedures:
            # Map procedures to equipment (simplified)
            if proc.startswith("CT"):
                required.add("ct_scanner")
            elif proc.startswith("MRI"):
                required.add("mri")
            elif proc.startswith("ECHO"):
                required.add("echocardiography")
        
        return required
    
    def _predict_outcome(
        self,
        patient: PatientPresentation,
        disposition: Disposition,
    ) -> OutcomePrediction:
        """Predict outcomes for a given disposition."""
        # Base predictions (would be ML-driven in production)
        base_success = 0.95
        base_los = 72.0
        base_complication = 0.05
        base_mortality = 0.01
        base_readmission = 0.10
        
        # Adjust based on patient factors
        if patient.charlson_score > 3:
            base_success -= 0.10
            base_complication += 0.05
            base_mortality += 0.02
        
        if patient.is_high_acuity:
            base_complication += 0.05
            base_los += 24
        
        # Adjust based on disposition
        if disposition == Disposition.TRANSFER:
            # Transfer to higher level of care may improve outcomes for complex patients
            if patient.icu_level_care or patient.surgical_need:
                base_success += 0.05
                base_mortality -= 0.01
            else:
                # Unnecessary transfer adds risk
                base_complication += 0.02
            
            # Financial impact of transfer
            financial_impact = -self.facility.transfer_cost
        
        elif disposition == Disposition.ADMIT:
            # Local treatment
            financial_impact = (
                self.facility.revenue_per_encounter -
                (base_los / 24) * self.facility.cost_per_patient_day
            )
        
        elif disposition == Disposition.OBSERVE:
            # Observation (lower reimbursement, shorter stay)
            base_los = min(48, base_los)
            financial_impact = self.facility.revenue_per_encounter * 0.4
        
        else:
            financial_impact = 0
        
        return OutcomePrediction(
            disposition=disposition,
            success_probability=max(0, min(1, base_success)),
            los_estimate_hours=base_los,
            complication_risk=max(0, min(1, base_complication)),
            mortality_risk=max(0, min(1, base_mortality)),
            readmission_risk=max(0, min(1, base_readmission)),
            financial_impact=financial_impact,
        )
    
    def _check_constraints(
        self,
        patient: PatientPresentation,
        capability: CapabilityScore,
    ) -> dict[str, Any]:
        """Check constraints for each disposition."""
        constraints = {
            "emtala_compliant": True,
        }
        
        # EMTALA: Must stabilize before transfer
        if patient.is_high_acuity and patient.acuity_level == 1:
            constraints["emtala_warning"] = "Patient must be stabilized before transfer (EMTALA)"
        
        # Capacity constraint
        if not capability.capacity_available:
            constraints[Disposition.ADMIT] = {
                "feasible": False,
                "reason": "No available beds",
            }
            constraints[Disposition.OBSERVE] = {
                "feasible": False,
                "reason": "No available beds",
            }
        
        # Capability constraint
        if not capability.can_treat:
            constraints[Disposition.ADMIT] = {
                "feasible": False,
                "reason": f"Capability gaps: {capability.gap_summary}",
            }
        
        return constraints
    
    def _calculate_utility(
        self,
        outcome: OutcomePrediction,
        capability: CapabilityScore,
        patient: PatientPresentation,
    ) -> float:
        """Calculate utility score for a disposition."""
        # Outcome utility
        outcome_utility = (
            outcome.success_probability * 100 -
            outcome.complication_risk * 50 -
            outcome.mortality_risk * 500
        )
        
        # Financial utility (normalized)
        financial_utility = outcome.financial_impact / 1000
        
        # Resource utility (prefer admitting if capable)
        resource_utility = capability.score if outcome.disposition == Disposition.ADMIT else 50
        
        # Compliance utility
        compliance_utility = 100  # Start with full compliance
        
        # Weighted combination
        utility = (
            self.weights["outcome"] * outcome_utility +
            self.weights["financial"] * financial_utility +
            self.weights["resource"] * resource_utility +
            self.weights["compliance"] * compliance_utility
        )
        
        return utility
    
    def _calculate_confidence(
        self,
        utilities: dict[Disposition, float],
        best: Disposition,
    ) -> float:
        """Calculate confidence in recommendation."""
        if len(utilities) < 2:
            return 0.5
        
        sorted_utils = sorted(utilities.values(), reverse=True)
        best_utility = sorted_utils[0]
        second_utility = sorted_utils[1]
        
        if best_utility <= 0:
            return 0.5
        
        # Confidence based on gap between best and second-best
        gap = best_utility - second_utility
        confidence = min(0.95, 0.6 + (gap / best_utility) * 0.35)
        
        return confidence
    
    def _generate_rationale(
        self,
        patient: PatientPresentation,
        disposition: Disposition,
        outcomes: dict[Disposition, OutcomePrediction],
        constraints: dict,
        capability: CapabilityScore,
    ) -> str:
        """Generate human-readable rationale for recommendation."""
        parts = []
        
        if disposition == Disposition.ADMIT:
            parts.append(f"Recommend ADMISSION: Facility capable of managing this patient")
            if capability.specialist_available:
                parts.append("Specialist coverage available")
            parts.append(f"Expected LOS: {outcomes[disposition].los_estimate_hours:.0f} hours")
        
        elif disposition == Disposition.TRANSFER:
            parts.append("Recommend TRANSFER to higher level of care")
            if not capability.can_treat:
                parts.append(f"Reason: {capability.gap_summary}")
            if patient.icu_level_care:
                parts.append("Patient requires ICU-level care")
            if patient.surgical_need:
                parts.append("Patient requires surgical intervention")
        
        elif disposition == Disposition.OBSERVE:
            parts.append("Recommend OBSERVATION status")
            parts.append("Clinical presentation warrants monitoring without full admission")
        
        return ". ".join(parts)
    
    def _disposition_rationale(
        self,
        disposition: Disposition,
        outcome: OutcomePrediction,
        constraints: dict,
    ) -> str:
        """Generate rationale for an alternative disposition."""
        if disposition == Disposition.ADMIT:
            return f"Local admission: {outcome.success_probability:.0%} success rate"
        elif disposition == Disposition.TRANSFER:
            return f"Transfer for specialized care: {outcome.success_probability:.0%} success rate"
        elif disposition == Disposition.OBSERVE:
            return f"Observation: Lower intensity, {outcome.los_estimate_hours:.0f}h expected"
        return ""


def create_default_facility() -> Facility:
    """Create a default CAH facility configuration."""
    return Facility(
        facility_id="default_cah",
        staffed_beds=25,
        current_census=10,
        services_available={
            "emergency", "radiology", "laboratory",
            "basic_surgery", "swing_bed", "observation",
            "respiratory_therapy", "pharmacy",
        },
        specialists_on_call={"internal_medicine", "family_medicine"},
        equipment_available={"xray", "ct_scanner", "ultrasound", "ekg", "lab_basic"},
    )

