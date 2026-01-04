"""
Phase 3: Priority Action Pilot - Pre-Bill Scrubbing
====================================================

This module executes the Priority Action Pilot for pre-bill scrubbing,
measuring actual vs. projected denial reduction and calculating realized ROI.

Pilot Structure:
- Duration: 90-day simulated pilot period
- Control Group: Claims processed without scrubbing intervention
- Intervention Group: Claims processed with pre-bill scrubbing

Key Metrics:
- Denial Rate Reduction (actual vs. projected)
- Clean Claim Rate improvement
- Recovery Time (days to payment)
- Revenue Protected
- ROI on pilot investment

Go/No-Go Thresholds:
- Minimum 15% denial rate reduction to proceed
- Minimum 1.5x ROI to justify full implementation
- Statistical significance (p < 0.05)
"""

import json
import random
import math
import numpy as np
from datetime import datetime, date, timedelta
from decimal import Decimal
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cah_engine.decision.revenue_protector import PreBillScrubber, RevenueProtector, ScrubStatus
from cah_engine.analytics.predictive import DenialProbabilityModel
from cah_engine.core.models import Claim, Issue
from cah_engine.core.enums import ClaimStatus, Severity, IssueCategory


# =============================================================================
# PILOT CONFIGURATION
# =============================================================================

@dataclass
class PilotConfig:
    """Configuration for the pre-bill scrubbing pilot."""
    
    # Pilot parameters
    pilot_duration_days: int = 90
    claims_per_day: int = 15  # Average claims per day for a CAH
    
    # Sample allocation
    control_ratio: float = 0.5  # 50% control, 50% intervention
    
    # Go/No-Go thresholds
    min_denial_reduction: float = 0.15  # 15% reduction required
    min_roi: float = 1.5  # 1.5x ROI required
    significance_level: float = 0.05  # p-value threshold
    
    # Cost assumptions
    avg_claim_value: Decimal = Decimal("4500")
    scrubbing_cost_per_claim: Decimal = Decimal("12")  # Software + labor
    denial_rework_cost: Decimal = Decimal("25")  # Cost to appeal denial
    implementation_cost: Decimal = Decimal("45000")  # One-time setup
    annual_license_cost: Decimal = Decimal("36000")  # Annual software cost
    
    # Baseline metrics (from Phase 2 data)
    baseline_denial_rate: float = 0.12  # 12% denial rate
    baseline_clean_claim_rate: float = 0.75  # 75% clean on first pass
    avg_denial_recovery_rate: float = 0.45  # 45% of denials recovered
    
    # Projected improvements
    projected_denial_reduction: float = 0.35  # 35% reduction expected
    projected_clean_claim_improvement: float = 0.15  # 15% improvement


@dataclass
class ClaimOutcome:
    """Outcome tracking for a single claim in the pilot."""
    
    claim_id: str
    group: str  # "control" or "intervention"
    payer_type: str
    service_date: date
    total_charges: Decimal
    
    # Pre-scrub state (for intervention)
    issues_found: int = 0
    issues_corrected: int = 0
    clean_probability_pre: float = 0.0
    clean_probability_post: float = 0.0
    
    # Outcomes
    submitted: bool = True
    denied: bool = False
    denial_reason: str = ""
    denial_amount: Decimal = Decimal("0")
    
    # Timing
    submission_date: Optional[date] = None
    payment_date: Optional[date] = None
    days_to_payment: int = 0
    
    # Financial
    paid_amount: Decimal = Decimal("0")
    intervention_cost: Decimal = Decimal("0")


@dataclass
class PilotMetrics:
    """Aggregated metrics from the pilot."""
    
    # Volume
    total_claims: int = 0
    control_claims: int = 0
    intervention_claims: int = 0
    
    # Denial metrics
    control_denials: int = 0
    intervention_denials: int = 0
    control_denial_rate: float = 0.0
    intervention_denial_rate: float = 0.0
    denial_rate_reduction: float = 0.0
    
    # Clean claim metrics
    control_clean_rate: float = 0.0
    intervention_clean_rate: float = 0.0
    clean_rate_improvement: float = 0.0
    
    # Financial metrics
    control_total_charges: Decimal = Decimal("0")
    intervention_total_charges: Decimal = Decimal("0")
    control_paid: Decimal = Decimal("0")
    intervention_paid: Decimal = Decimal("0")
    control_denied_amount: Decimal = Decimal("0")
    intervention_denied_amount: Decimal = Decimal("0")
    
    # Revenue protected
    revenue_protected: Decimal = Decimal("0")
    potential_annual_savings: Decimal = Decimal("0")
    
    # Cost analysis
    pilot_intervention_cost: Decimal = Decimal("0")
    prevented_rework_cost: Decimal = Decimal("0")
    
    # ROI
    pilot_roi: float = 0.0
    projected_annual_roi: float = 0.0
    payback_months: float = 0.0
    
    # Statistical
    p_value: float = 1.0
    confidence_interval: tuple = (0.0, 0.0)
    statistically_significant: bool = False
    
    # Time to payment
    control_avg_days_to_payment: float = 0.0
    intervention_avg_days_to_payment: float = 0.0
    days_improvement: float = 0.0


@dataclass
class GoNoGoDecision:
    """Final go/no-go decision for full implementation."""
    
    decision: str  # "GO", "NO_GO", "CONDITIONAL_GO"
    confidence: float  # 0-1
    
    # Criteria evaluation
    denial_reduction_met: bool = False
    roi_threshold_met: bool = False
    statistical_significance_met: bool = False
    
    # Recommendations
    recommendations: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    
    # Projected benefits (annual)
    projected_annual_savings: Decimal = Decimal("0")
    projected_roi: float = 0.0
    confidence_interval_savings: tuple = (Decimal("0"), Decimal("0"))


# =============================================================================
# PILOT DATA GENERATOR
# =============================================================================

class PilotDataGenerator:
    """Generate realistic claim data for the pilot simulation."""
    
    def __init__(self, config: PilotConfig, seed: int = 42):
        self.config = config
        self.rng = random.Random(seed)
        np.random.seed(seed)
        
        # Payer distribution (typical CAH)
        self.payer_weights = {
            "medicare": 0.55,
            "medicaid": 0.20,
            "commercial": 0.20,
            "self_pay": 0.05,
        }
        
        # Denial rates by payer (baseline)
        self.payer_denial_rates = {
            "medicare": 0.08,
            "medicaid": 0.14,
            "commercial": 0.18,
            "self_pay": 0.02,
        }
        
        # Common denial reasons with weights
        self.denial_reasons = {
            "Missing/Invalid diagnosis": 0.25,
            "Prior authorization required": 0.20,
            "Medical necessity not established": 0.15,
            "Duplicate claim": 0.10,
            "Timely filing exceeded": 0.08,
            "Invalid procedure code": 0.07,
            "Benefit not covered": 0.05,
            "Coordination of benefits": 0.05,
            "Patient not eligible": 0.05,
        }
        
        # Sample diagnosis codes (common CAH conditions)
        self.diagnosis_codes = [
            "J18.9",   # Pneumonia
            "I50.9",   # Heart failure
            "N17.9",   # AKI
            "I21.4",   # NSTEMI
            "J44.1",   # COPD
            "E11.9",   # Type 2 diabetes
            "K92.2",   # GI bleed
            "R55",     # Syncope
            "S72.001", # Hip fracture
            "N39.0",   # UTI
        ]
        
        # Sample procedure codes
        self.procedure_codes = [
            "99223", "99222", "99221",  # Inpatient E/M
            "99283", "99284", "99285",  # ED visits
            "71046", "71250", "70553",  # Imaging
            "36415", "80053", "85025",  # Labs
        ]
    
    def generate_pilot_claims(self) -> list[dict]:
        """Generate all claims for the pilot period."""
        claims = []
        start_date = date.today() - timedelta(days=self.config.pilot_duration_days)
        
        for day_offset in range(self.config.pilot_duration_days):
            current_date = start_date + timedelta(days=day_offset)
            
            # Vary claims per day (weekend effect)
            day_factor = 0.7 if current_date.weekday() >= 5 else 1.0
            num_claims = max(1, int(self.rng.gauss(
                self.config.claims_per_day * day_factor, 3
            )))
            
            for _ in range(num_claims):
                claim = self._generate_single_claim(current_date, len(claims))
                claims.append(claim)
        
        return claims
    
    def _generate_single_claim(self, service_date: date, claim_num: int) -> dict:
        """Generate a single claim with realistic attributes."""
        
        # Select payer
        payer = self.rng.choices(
            list(self.payer_weights.keys()),
            weights=list(self.payer_weights.values())
        )[0]
        
        # Generate charges (lognormal distribution)
        base_charge = float(self.config.avg_claim_value)
        charge_factor = np.random.lognormal(0, 0.5)
        total_charges = Decimal(str(round(base_charge * charge_factor, 2)))
        total_charges = max(Decimal("500"), min(Decimal("50000"), total_charges))
        
        # Generate diagnosis codes (1-5)
        num_dx = self.rng.randint(1, 5)
        dx_codes = self.rng.sample(self.diagnosis_codes, min(num_dx, len(self.diagnosis_codes)))
        
        # Generate procedure codes (1-8)
        num_proc = self.rng.randint(1, 8)
        proc_codes = self.rng.sample(self.procedure_codes, min(num_proc, len(self.procedure_codes)))
        
        # Add some problematic patterns that scrubbing would catch
        issues = self._generate_claim_issues(payer, dx_codes, proc_codes)
        
        return {
            "claim_id": f"CLM-{service_date.strftime('%Y%m')}-{claim_num:05d}",
            "service_date": service_date,
            "payer": payer,
            "total_charges": total_charges,
            "diagnosis_codes": dx_codes,
            "procedure_codes": proc_codes,
            "issues": issues,
            "base_denial_risk": self.payer_denial_rates[payer],
        }
    
    def _generate_claim_issues(
        self,
        payer: str,
        dx_codes: list[str],
        proc_codes: list[str]
    ) -> list[dict]:
        """Generate realistic issues that pre-bill scrubbing would catch."""
        issues = []
        
        # 15% chance of missing/truncated diagnosis
        if self.rng.random() < 0.15:
            issues.append({
                "type": "diagnosis",
                "severity": "high",
                "description": "Primary diagnosis may need additional specificity",
                "correctable": True,
            })
        
        # 10% chance of procedure code issue
        if self.rng.random() < 0.10:
            issues.append({
                "type": "coding",
                "severity": "medium",
                "description": "Procedure code modifier may be missing",
                "correctable": True,
            })
        
        # 8% chance of authorization issue (higher for commercial)
        auth_prob = 0.12 if payer == "commercial" else 0.05
        if self.rng.random() < auth_prob:
            issues.append({
                "type": "authorization",
                "severity": "blocker",
                "description": "Prior authorization may be required",
                "correctable": True,
            })
        
        # 5% chance of eligibility concern
        if self.rng.random() < 0.05:
            issues.append({
                "type": "eligibility",
                "severity": "high",
                "description": "Verify patient eligibility on date of service",
                "correctable": True,
            })
        
        # 3% chance of medical necessity flag (higher charges)
        if self.rng.random() < 0.03:
            issues.append({
                "type": "medical_necessity",
                "severity": "medium",
                "description": "Documentation may need to support medical necessity",
                "correctable": True,
            })
        
        return issues


# =============================================================================
# PILOT EXECUTION ENGINE
# =============================================================================

class PreBillPilotEngine:
    """Execute the pre-bill scrubbing pilot and measure outcomes."""
    
    def __init__(self, config: PilotConfig, seed: int = 42):
        self.config = config
        self.rng = random.Random(seed)
        np.random.seed(seed)
        
        # Initialize components
        self.scrubber = PreBillScrubber()
        self.denial_model = DenialProbabilityModel()
        self.revenue_protector = RevenueProtector()
        
        # Train denial model with baseline data
        self._initialize_models()
        
        # Results storage
        self.outcomes: list[ClaimOutcome] = []
    
    def _initialize_models(self):
        """Initialize models with baseline parameters."""
        # Train denial model with synthetic historical data
        historical = []
        for i in range(500):
            payer = self.rng.choice(["medicare", "medicaid", "commercial"])
            denied = self.rng.random() < {
                "medicare": 0.08,
                "medicaid": 0.14,
                "commercial": 0.18,
            }[payer]
            historical.append({
                "payer_type": payer,
                "denied": denied,
            })
        self.denial_model.train(historical)
    
    def run_pilot(self) -> list[ClaimOutcome]:
        """Execute the full pilot simulation."""
        print("\n" + "="*70)
        print("PHASE 3: PRE-BILL SCRUBBING PILOT")
        print("="*70)
        
        # Generate pilot data
        print("\n[DATA] Generating pilot claim data...")
        generator = PilotDataGenerator(self.config)
        claims = generator.generate_pilot_claims()
        print(f"   Generated {len(claims)} claims over {self.config.pilot_duration_days} days")
        
        # Assign to control/intervention groups
        print("\n[RANDOM] Randomizing to control/intervention groups...")
        self.rng.shuffle(claims)
        split_point = int(len(claims) * self.config.control_ratio)
        control_claims = claims[:split_point]
        intervention_claims = claims[split_point:]
        print(f"   Control group: {len(control_claims)} claims")
        print(f"   Intervention group: {len(intervention_claims)} claims")
        
        # Process control group (no intervention)
        print("\n[CONTROL] Processing control group (baseline)...")
        for claim in control_claims:
            outcome = self._process_control_claim(claim)
            self.outcomes.append(outcome)
        
        # Process intervention group (with scrubbing)
        print("[SCRUB] Processing intervention group (with scrubbing)...")
        for claim in intervention_claims:
            outcome = self._process_intervention_claim(claim)
            self.outcomes.append(outcome)
        
        print(f"\n[DONE] Pilot complete. {len(self.outcomes)} claims processed.")
        
        return self.outcomes
    
    def _process_control_claim(self, claim_data: dict) -> ClaimOutcome:
        """Process a claim without scrubbing intervention."""
        
        # Simulate denial based on baseline rates and issues
        base_denial_rate = claim_data["base_denial_risk"]
        issues = claim_data["issues"]
        
        # Issues increase denial probability
        denial_boost = sum(
            0.15 if i["severity"] == "blocker" else 
            0.08 if i["severity"] == "high" else 0.03
            for i in issues
        )
        
        final_denial_prob = min(0.8, base_denial_rate + denial_boost)
        denied = self.rng.random() < final_denial_prob
        
        # Simulate payment timing
        if denied:
            denial_reason = self._select_denial_reason(issues)
            payment_date = None
            days_to_payment = 0
            paid_amount = Decimal("0")
            denial_amount = claim_data["total_charges"] * Decimal("0.85")  # Avg denial is 85% of charge
        else:
            denial_reason = ""
            days_to_payment = int(self.rng.gauss(35, 10))  # Avg 35 days to payment
            days_to_payment = max(14, min(90, days_to_payment))
            payment_date = claim_data["service_date"] + timedelta(days=days_to_payment)
            # Payment is typically 40-80% of charges (contractual adjustments)
            paid_amount = claim_data["total_charges"] * Decimal(str(self.rng.uniform(0.4, 0.8)))
            denial_amount = Decimal("0")
        
        return ClaimOutcome(
            claim_id=claim_data["claim_id"],
            group="control",
            payer_type=claim_data["payer"],
            service_date=claim_data["service_date"],
            total_charges=claim_data["total_charges"],
            issues_found=len(issues),
            issues_corrected=0,
            clean_probability_pre=1.0 - final_denial_prob,
            clean_probability_post=1.0 - final_denial_prob,
            submitted=True,
            denied=denied,
            denial_reason=denial_reason,
            denial_amount=denial_amount,
            submission_date=claim_data["service_date"] + timedelta(days=self.rng.randint(1, 5)),
            payment_date=payment_date,
            days_to_payment=days_to_payment,
            paid_amount=paid_amount,
            intervention_cost=Decimal("0"),
        )
    
    def _process_intervention_claim(self, claim_data: dict) -> ClaimOutcome:
        """Process a claim with scrubbing intervention."""
        
        # Create Claim object for scrubbing
        claim = Claim(
            claim_id=claim_data["claim_id"],
            patient_id=f"PT-{self.rng.randint(10000, 99999)}",
            encounter_id=f"ENC-{self.rng.randint(10000, 99999)}",
            payer_id=claim_data["payer"],
            service_date=claim_data["service_date"],
            claim_type="837I",
            total_charges=claim_data["total_charges"],
            diagnosis_codes=claim_data["diagnosis_codes"],
            procedure_codes=claim_data["procedure_codes"],
        )
        
        # Run pre-bill scrubbing
        scrub_result = self.scrubber.scrub(claim)
        
        # Count issues found and corrected
        issues_found = len(claim_data["issues"])
        
        # Assume 85% of correctable issues are fixed through scrubbing
        correctable_issues = [i for i in claim_data["issues"] if i.get("correctable", True)]
        issues_corrected = int(len(correctable_issues) * 0.85)
        remaining_issues = issues_found - issues_corrected
        
        # Calculate post-scrubbing denial probability
        base_denial_rate = claim_data["base_denial_risk"]
        
        # Remaining issues still contribute to denial risk, but reduced
        remaining_boost = sum(
            0.08 if i["severity"] == "blocker" else 
            0.04 if i["severity"] == "high" else 0.015
            for i in claim_data["issues"][:remaining_issues]
        )
        
        # Scrubbing also adds a general reduction from better coding
        scrubbing_reduction = 0.03  # 3% reduction from general quality improvement
        
        final_denial_prob = max(0.02, base_denial_rate + remaining_boost - scrubbing_reduction)
        denied = self.rng.random() < final_denial_prob
        
        # Intervention cost
        intervention_cost = self.config.scrubbing_cost_per_claim
        
        # Simulate outcomes
        if denied:
            denial_reason = self._select_denial_reason(claim_data["issues"][:remaining_issues])
            payment_date = None
            days_to_payment = 0
            paid_amount = Decimal("0")
            denial_amount = claim_data["total_charges"] * Decimal("0.85")
        else:
            denial_reason = ""
            # Cleaner claims get paid faster
            days_to_payment = int(self.rng.gauss(28, 8))  # Faster than control
            days_to_payment = max(10, min(60, days_to_payment))
            payment_date = claim_data["service_date"] + timedelta(days=days_to_payment)
            paid_amount = claim_data["total_charges"] * Decimal(str(self.rng.uniform(0.4, 0.8)))
            denial_amount = Decimal("0")
        
        return ClaimOutcome(
            claim_id=claim_data["claim_id"],
            group="intervention",
            payer_type=claim_data["payer"],
            service_date=claim_data["service_date"],
            total_charges=claim_data["total_charges"],
            issues_found=issues_found,
            issues_corrected=issues_corrected,
            clean_probability_pre=1.0 - (base_denial_rate + remaining_boost + 0.1),
            clean_probability_post=1.0 - final_denial_prob,
            submitted=True,
            denied=denied,
            denial_reason=denial_reason,
            denial_amount=denial_amount,
            submission_date=claim_data["service_date"] + timedelta(days=self.rng.randint(1, 3)),
            payment_date=payment_date,
            days_to_payment=days_to_payment,
            paid_amount=paid_amount,
            intervention_cost=intervention_cost,
        )
    
    def _select_denial_reason(self, issues: list[dict]) -> str:
        """Select a denial reason based on claim issues."""
        if not issues:
            return self.rng.choice([
                "Duplicate claim",
                "Benefit not covered",
                "Patient not eligible",
            ])
        
        # Map issue types to denial reasons
        type_to_reason = {
            "diagnosis": "Missing/Invalid diagnosis",
            "authorization": "Prior authorization required",
            "medical_necessity": "Medical necessity not established",
            "coding": "Invalid procedure code",
            "eligibility": "Patient not eligible",
        }
        
        for issue in issues:
            if issue["type"] in type_to_reason:
                return type_to_reason[issue["type"]]
        
        return "Other denial reason"


# =============================================================================
# METRICS CALCULATOR
# =============================================================================

class PilotMetricsCalculator:
    """Calculate comprehensive metrics from pilot outcomes."""
    
    def __init__(self, config: PilotConfig):
        self.config = config
    
    def calculate_metrics(self, outcomes: list[ClaimOutcome]) -> PilotMetrics:
        """Calculate all pilot metrics."""
        
        # Separate groups
        control = [o for o in outcomes if o.group == "control"]
        intervention = [o for o in outcomes if o.group == "intervention"]
        
        # Basic counts
        metrics = PilotMetrics()
        metrics.total_claims = len(outcomes)
        metrics.control_claims = len(control)
        metrics.intervention_claims = len(intervention)
        
        # Denial metrics
        metrics.control_denials = sum(1 for o in control if o.denied)
        metrics.intervention_denials = sum(1 for o in intervention if o.denied)
        
        metrics.control_denial_rate = (
            metrics.control_denials / metrics.control_claims 
            if metrics.control_claims > 0 else 0
        )
        metrics.intervention_denial_rate = (
            metrics.intervention_denials / metrics.intervention_claims 
            if metrics.intervention_claims > 0 else 0
        )
        
        # Denial rate reduction (positive = improvement)
        if metrics.control_denial_rate > 0:
            metrics.denial_rate_reduction = (
                (metrics.control_denial_rate - metrics.intervention_denial_rate) /
                metrics.control_denial_rate
            )
        else:
            metrics.denial_rate_reduction = 0
        
        # Clean claim metrics
        metrics.control_clean_rate = 1 - metrics.control_denial_rate
        metrics.intervention_clean_rate = 1 - metrics.intervention_denial_rate
        metrics.clean_rate_improvement = (
            metrics.intervention_clean_rate - metrics.control_clean_rate
        )
        
        # Financial metrics
        metrics.control_total_charges = sum(o.total_charges for o in control)
        metrics.intervention_total_charges = sum(o.total_charges for o in intervention)
        metrics.control_paid = sum(o.paid_amount for o in control)
        metrics.intervention_paid = sum(o.paid_amount for o in intervention)
        metrics.control_denied_amount = sum(o.denial_amount for o in control)
        metrics.intervention_denied_amount = sum(o.denial_amount for o in intervention)
        
        # Revenue protected (difference in denied amounts)
        metrics.revenue_protected = (
            metrics.control_denied_amount - metrics.intervention_denied_amount
        )
        
        # Annualize
        days_in_year = 365
        annual_factor = days_in_year / self.config.pilot_duration_days
        metrics.potential_annual_savings = metrics.revenue_protected * Decimal(str(annual_factor))
        
        # Costs
        metrics.pilot_intervention_cost = sum(o.intervention_cost for o in intervention)
        denials_prevented = metrics.control_denials - metrics.intervention_denials
        metrics.prevented_rework_cost = Decimal(str(denials_prevented)) * self.config.denial_rework_cost
        
        # ROI calculations
        pilot_benefit = float(metrics.revenue_protected + metrics.prevented_rework_cost)
        pilot_cost = float(metrics.pilot_intervention_cost)
        
        if pilot_cost > 0:
            metrics.pilot_roi = pilot_benefit / pilot_cost
        else:
            metrics.pilot_roi = float("inf") if pilot_benefit > 0 else 0
        
        # Projected annual ROI
        annual_cost = float(self.config.annual_license_cost)
        annual_benefit = float(metrics.potential_annual_savings)
        
        if annual_cost > 0:
            metrics.projected_annual_roi = annual_benefit / annual_cost
        else:
            metrics.projected_annual_roi = 0
        
        # Payback period
        total_implementation = float(
            self.config.implementation_cost + self.config.annual_license_cost / 12
        )
        monthly_benefit = annual_benefit / 12
        
        if monthly_benefit > 0:
            metrics.payback_months = total_implementation / monthly_benefit
        else:
            metrics.payback_months = float("inf")
        
        # Time to payment
        control_paid_claims = [o for o in control if o.days_to_payment > 0]
        intervention_paid_claims = [o for o in intervention if o.days_to_payment > 0]
        
        if control_paid_claims:
            metrics.control_avg_days_to_payment = np.mean([o.days_to_payment for o in control_paid_claims])
        if intervention_paid_claims:
            metrics.intervention_avg_days_to_payment = np.mean([o.days_to_payment for o in intervention_paid_claims])
        
        metrics.days_improvement = (
            metrics.control_avg_days_to_payment - metrics.intervention_avg_days_to_payment
        )
        
        # Statistical significance (two-proportion z-test)
        metrics.p_value, metrics.confidence_interval = self._calculate_significance(
            metrics.control_claims, metrics.control_denials,
            metrics.intervention_claims, metrics.intervention_denials
        )
        metrics.statistically_significant = metrics.p_value < self.config.significance_level
        
        return metrics
    
    def _calculate_significance(
        self,
        n1: int, x1: int,
        n2: int, x2: int
    ) -> tuple[float, tuple[float, float]]:
        """Calculate statistical significance of denial rate difference."""
        if n1 == 0 or n2 == 0:
            return 1.0, (0.0, 0.0)
        
        p1 = x1 / n1  # Control denial rate
        p2 = x2 / n2  # Intervention denial rate
        
        # Pooled proportion
        p_pool = (x1 + x2) / (n1 + n2)
        
        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        
        if se == 0:
            return 1.0, (0.0, 0.0)
        
        # Z-score
        z = (p1 - p2) / se
        
        # Two-tailed p-value (approximation)
        p_value = 2 * (1 - self._norm_cdf(abs(z)))
        
        # 95% confidence interval for difference
        diff = p1 - p2
        se_diff = math.sqrt(p1*(1-p1)/n1 + p2*(1-p2)/n2)
        ci_lower = diff - 1.96 * se_diff
        ci_upper = diff + 1.96 * se_diff
        
        return p_value, (ci_lower, ci_upper)
    
    def _norm_cdf(self, x: float) -> float:
        """Standard normal CDF approximation."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# =============================================================================
# GO/NO-GO DECISION ENGINE
# =============================================================================

class GoNoGoDecisionEngine:
    """Evaluate pilot results and make go/no-go decision."""
    
    def __init__(self, config: PilotConfig):
        self.config = config
    
    def evaluate(self, metrics: PilotMetrics) -> GoNoGoDecision:
        """Evaluate metrics and produce go/no-go decision."""
        
        # Check thresholds
        denial_reduction_met = metrics.denial_rate_reduction >= self.config.min_denial_reduction
        roi_met = metrics.projected_annual_roi >= self.config.min_roi
        significance_met = metrics.statistically_significant
        
        # Calculate confidence
        criteria_met = sum([denial_reduction_met, roi_met, significance_met])
        
        # Determine decision
        if criteria_met == 3:
            decision = "GO"
            confidence = 0.95
        elif criteria_met == 2 and (denial_reduction_met or roi_met):
            decision = "CONDITIONAL_GO"
            confidence = 0.75
        else:
            decision = "NO_GO"
            confidence = 0.85  # High confidence in rejection
        
        # Generate recommendations
        recommendations = []
        risks = []
        next_steps = []
        
        if decision == "GO":
            recommendations = [
                "Proceed with full implementation across all claim types",
                "Target go-live within 60 days to capture projected savings",
                "Establish monthly ROI tracking dashboard",
                "Train billing staff on scrubbing workflow integration",
            ]
            next_steps = [
                "Finalize vendor contract/license agreement",
                "Schedule implementation kickoff meeting",
                "Define integration requirements with billing system",
                "Establish baseline metrics for post-implementation tracking",
            ]
            risks = [
                "Staff adoption may vary - plan for training",
                "ROI may fluctuate with payer mix changes",
            ]
            
        elif decision == "CONDITIONAL_GO":
            recommendations = [
                "Proceed with phased implementation",
                "Start with highest-impact payer types first",
                "Extend pilot by 30 days to improve statistical confidence" if not significance_met else None,
                "Focus on claim types showing highest improvement",
            ]
            recommendations = [r for r in recommendations if r]
            
            next_steps = [
                "Identify top 3 denial categories for focused intervention",
                "Develop phased rollout plan",
                "Set interim milestones for full go/no-go decision",
            ]
            
            if not denial_reduction_met:
                risks.append(f"Denial reduction ({metrics.denial_rate_reduction:.1%}) below target ({self.config.min_denial_reduction:.1%})")
            if not roi_met:
                risks.append(f"ROI ({metrics.projected_annual_roi:.1f}x) below threshold ({self.config.min_roi:.1f}x)")
            if not significance_met:
                risks.append(f"Results not statistically significant (p={metrics.p_value:.3f})")
                
        else:  # NO_GO
            recommendations = [
                "Do not proceed with full implementation at this time",
                "Investigate root causes of underperformance",
                "Consider alternative solutions or vendors",
                "Re-evaluate in 6 months if denial rates increase",
            ]
            
            next_steps = [
                "Document lessons learned from pilot",
                "Analyze specific denial categories that were not impacted",
                "Evaluate manual process improvements as alternative",
            ]
            
            risks = [
                "Continued revenue leakage from preventable denials",
                "Staff time spent on denial management could be reduced",
            ]
        
        # Calculate projected savings with confidence interval
        annual_savings = metrics.potential_annual_savings
        ci_factor = 0.25  # 25% uncertainty range
        ci_lower = annual_savings * Decimal(str(1 - ci_factor))
        ci_upper = annual_savings * Decimal(str(1 + ci_factor))
        
        return GoNoGoDecision(
            decision=decision,
            confidence=confidence,
            denial_reduction_met=denial_reduction_met,
            roi_threshold_met=roi_met,
            statistical_significance_met=significance_met,
            recommendations=recommendations,
            risks=risks,
            next_steps=next_steps,
            projected_annual_savings=annual_savings,
            projected_roi=metrics.projected_annual_roi,
            confidence_interval_savings=(ci_lower, ci_upper),
        )


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class PilotReportGenerator:
    """Generate comprehensive pilot reports."""
    
    def __init__(self, config: PilotConfig):
        self.config = config
    
    def generate_report(
        self,
        outcomes: list[ClaimOutcome],
        metrics: PilotMetrics,
        decision: GoNoGoDecision
    ) -> dict:
        """Generate full pilot report."""
        
        report = {
            "report_metadata": {
                "title": "Phase 3: Pre-Bill Scrubbing Pilot Results",
                "generated_at": datetime.now().isoformat(),
                "pilot_duration_days": self.config.pilot_duration_days,
                "total_claims_analyzed": len(outcomes),
            },
            
            "executive_summary": self._generate_executive_summary(metrics, decision),
            
            "pilot_configuration": {
                "duration_days": self.config.pilot_duration_days,
                "control_ratio": self.config.control_ratio,
                "avg_claim_value": float(self.config.avg_claim_value),
                "scrubbing_cost_per_claim": float(self.config.scrubbing_cost_per_claim),
                "baseline_denial_rate": self.config.baseline_denial_rate,
                "projected_denial_reduction": self.config.projected_denial_reduction,
            },
            
            "pilot_metrics": {
                "volume": {
                    "total_claims": metrics.total_claims,
                    "control_claims": metrics.control_claims,
                    "intervention_claims": metrics.intervention_claims,
                },
                "denial_analysis": {
                    "control_denials": metrics.control_denials,
                    "intervention_denials": metrics.intervention_denials,
                    "control_denial_rate": round(metrics.control_denial_rate, 4),
                    "intervention_denial_rate": round(metrics.intervention_denial_rate, 4),
                    "denial_rate_reduction": round(metrics.denial_rate_reduction, 4),
                    "denial_rate_reduction_percent": f"{metrics.denial_rate_reduction * 100:.1f}%",
                },
                "clean_claim_analysis": {
                    "control_clean_rate": round(metrics.control_clean_rate, 4),
                    "intervention_clean_rate": round(metrics.intervention_clean_rate, 4),
                    "clean_rate_improvement": round(metrics.clean_rate_improvement, 4),
                },
                "financial_impact": {
                    "control_total_charges": float(metrics.control_total_charges),
                    "intervention_total_charges": float(metrics.intervention_total_charges),
                    "control_paid": float(metrics.control_paid),
                    "intervention_paid": float(metrics.intervention_paid),
                    "control_denied_amount": float(metrics.control_denied_amount),
                    "intervention_denied_amount": float(metrics.intervention_denied_amount),
                    "revenue_protected": float(metrics.revenue_protected),
                    "potential_annual_savings": float(metrics.potential_annual_savings),
                },
                "cost_analysis": {
                    "pilot_intervention_cost": float(metrics.pilot_intervention_cost),
                    "prevented_rework_cost": float(metrics.prevented_rework_cost),
                    "implementation_cost": float(self.config.implementation_cost),
                    "annual_license_cost": float(self.config.annual_license_cost),
                },
                "roi_analysis": {
                    "pilot_roi": round(metrics.pilot_roi, 2),
                    "projected_annual_roi": round(metrics.projected_annual_roi, 2),
                    "payback_months": round(metrics.payback_months, 1),
                },
                "time_to_payment": {
                    "control_avg_days": round(metrics.control_avg_days_to_payment, 1),
                    "intervention_avg_days": round(metrics.intervention_avg_days_to_payment, 1),
                    "days_improvement": round(metrics.days_improvement, 1),
                },
                "statistical_analysis": {
                    "p_value": round(metrics.p_value, 4),
                    "confidence_interval_95": [
                        round(metrics.confidence_interval[0], 4),
                        round(metrics.confidence_interval[1], 4)
                    ],
                    "statistically_significant": metrics.statistically_significant,
                    "significance_level": self.config.significance_level,
                },
            },
            
            "actual_vs_projected": {
                "denial_reduction": {
                    "projected": self.config.projected_denial_reduction,
                    "actual": metrics.denial_rate_reduction,
                    "variance": metrics.denial_rate_reduction - self.config.projected_denial_reduction,
                    "status": "EXCEEDED" if metrics.denial_rate_reduction >= self.config.projected_denial_reduction else "BELOW_TARGET",
                },
                "clean_claim_improvement": {
                    "projected": self.config.projected_clean_claim_improvement,
                    "actual": metrics.clean_rate_improvement,
                    "variance": metrics.clean_rate_improvement - self.config.projected_clean_claim_improvement,
                    "status": "EXCEEDED" if metrics.clean_rate_improvement >= self.config.projected_clean_claim_improvement else "BELOW_TARGET",
                },
            },
            
            "go_no_go_decision": {
                "decision": decision.decision,
                "confidence": decision.confidence,
                "criteria_evaluation": {
                    "denial_reduction_met": decision.denial_reduction_met,
                    "denial_reduction_threshold": self.config.min_denial_reduction,
                    "roi_threshold_met": decision.roi_threshold_met,
                    "roi_threshold": self.config.min_roi,
                    "statistical_significance_met": decision.statistical_significance_met,
                },
                "recommendations": decision.recommendations,
                "risks": decision.risks,
                "next_steps": decision.next_steps,
                "projected_annual_savings": float(decision.projected_annual_savings),
                "projected_roi": decision.projected_roi,
                "savings_confidence_interval": [
                    float(decision.confidence_interval_savings[0]),
                    float(decision.confidence_interval_savings[1])
                ],
            },
            
            "denial_analysis_by_category": self._analyze_denials_by_category(outcomes),
            
            "payer_analysis": self._analyze_by_payer(outcomes),
        }
        
        return report
    
    def _generate_executive_summary(
        self,
        metrics: PilotMetrics,
        decision: GoNoGoDecision
    ) -> dict:
        """Generate executive summary section."""
        
        return {
            "headline": f"Pre-Bill Scrubbing Pilot: {decision.decision} Recommendation",
            "key_findings": [
                f"Denial rate reduced by {metrics.denial_rate_reduction * 100:.1f}% (target: {self.config.min_denial_reduction * 100:.0f}%)",
                f"Clean claim rate improved from {metrics.control_clean_rate * 100:.1f}% to {metrics.intervention_clean_rate * 100:.1f}%",
                f"Revenue protected during pilot: ${float(metrics.revenue_protected):,.2f}",
                f"Projected annual savings: ${float(metrics.potential_annual_savings):,.2f}",
                f"Projected ROI: {metrics.projected_annual_roi:.1f}x",
                f"Time to payment improved by {metrics.days_improvement:.1f} days",
            ],
            "bottom_line": self._get_bottom_line(decision),
            "confidence_level": f"{decision.confidence * 100:.0f}%",
        }
    
    def _get_bottom_line(self, decision: GoNoGoDecision) -> str:
        """Generate bottom line summary."""
        if decision.decision == "GO":
            return (
                "The pilot demonstrates clear value. Pre-bill scrubbing significantly "
                "reduces denial rates and improves revenue capture. Full implementation "
                "is recommended."
            )
        elif decision.decision == "CONDITIONAL_GO":
            return (
                "The pilot shows promising results but with some caveats. A phased "
                "implementation approach is recommended, starting with high-impact areas."
            )
        else:
            return (
                "The pilot did not meet the required thresholds for full implementation. "
                "Alternative approaches should be evaluated."
            )
    
    def _analyze_denials_by_category(self, outcomes: list[ClaimOutcome]) -> dict:
        """Analyze denials by reason category."""
        control = [o for o in outcomes if o.group == "control" and o.denied]
        intervention = [o for o in outcomes if o.group == "intervention" and o.denied]
        
        def count_by_reason(denials):
            counts = {}
            for d in denials:
                reason = d.denial_reason or "Unknown"
                counts[reason] = counts.get(reason, 0) + 1
            return counts
        
        control_reasons = count_by_reason(control)
        intervention_reasons = count_by_reason(intervention)
        
        all_reasons = set(control_reasons.keys()) | set(intervention_reasons.keys())
        
        analysis = {}
        for reason in all_reasons:
            control_count = control_reasons.get(reason, 0)
            intervention_count = intervention_reasons.get(reason, 0)
            reduction = ((control_count - intervention_count) / control_count * 100) if control_count > 0 else 0
            
            analysis[reason] = {
                "control_count": control_count,
                "intervention_count": intervention_count,
                "reduction_percent": round(reduction, 1),
            }
        
        return analysis
    
    def _analyze_by_payer(self, outcomes: list[ClaimOutcome]) -> dict:
        """Analyze results by payer type."""
        payers = set(o.payer_type for o in outcomes)
        
        analysis = {}
        for payer in payers:
            control = [o for o in outcomes if o.group == "control" and o.payer_type == payer]
            intervention = [o for o in outcomes if o.group == "intervention" and o.payer_type == payer]
            
            control_denial_rate = sum(1 for o in control if o.denied) / len(control) if control else 0
            intervention_denial_rate = sum(1 for o in intervention if o.denied) / len(intervention) if intervention else 0
            
            analysis[payer] = {
                "control_claims": len(control),
                "intervention_claims": len(intervention),
                "control_denial_rate": round(control_denial_rate, 4),
                "intervention_denial_rate": round(intervention_denial_rate, 4),
                "improvement": round(control_denial_rate - intervention_denial_rate, 4),
            }
        
        return analysis
    
    def print_summary(self, report: dict) -> None:
        """Print a formatted summary to console."""
        
        print("\n" + "="*70)
        print("[REPORT] PHASE 3 PILOT RESULTS: EXECUTIVE SUMMARY")
        print("="*70)
        
        summary = report["executive_summary"]
        print(f"\n[TARGET] {summary['headline']}")
        print(f"   Confidence: {summary['confidence_level']}")
        
        print("\n[FINDINGS] Key Findings:")
        for finding in summary["key_findings"]:
            print(f"   * {finding}")
        
        print(f"\n[INSIGHT] Bottom Line:")
        print(f"   {summary['bottom_line']}")
        
        decision = report["go_no_go_decision"]
        print("\n" + "-"*70)
        print(f"[DECISION] GO/NO-GO DECISION: {decision['decision']}")
        print("-"*70)
        
        criteria = decision["criteria_evaluation"]
        print("\n   Criteria Evaluation:")
        print(f"   > Denial Reduction >= {criteria['denial_reduction_threshold']*100:.0f}%: {'[PASS] MET' if criteria['denial_reduction_met'] else '[FAIL] NOT MET'}")
        print(f"   > ROI >= {criteria['roi_threshold']:.1f}x: {'[PASS] MET' if criteria['roi_threshold_met'] else '[FAIL] NOT MET'}")
        print(f"   > Statistical Significance: {'[PASS] MET' if criteria['statistical_significance_met'] else '[FAIL] NOT MET'}")
        
        print("\n[RECOMMEND] Recommendations:")
        for rec in decision["recommendations"]:
            print(f"   -> {rec}")
        
        print("\n[WARNING] Risks to Consider:")
        for risk in decision["risks"]:
            print(f"   !! {risk}")
        
        print("\n[ACTION] Next Steps:")
        for step in decision["next_steps"]:
            print(f"   [ ] {step}")
        
        print("\n" + "-"*70)
        print("[FINANCE] FINANCIAL SUMMARY")
        print("-"*70)
        
        financial = report["pilot_metrics"]["financial_impact"]
        roi = report["pilot_metrics"]["roi_analysis"]
        
        print(f"\n   Revenue Protected (Pilot): ${financial['revenue_protected']:,.2f}")
        print(f"   Projected Annual Savings:  ${financial['potential_annual_savings']:,.2f}")
        print(f"   Projected Annual ROI:      {roi['projected_annual_roi']:.1f}x")
        print(f"   Payback Period:            {roi['payback_months']:.1f} months")
        
        # Actual vs Projected
        avp = report["actual_vs_projected"]
        print("\n" + "-"*70)
        print("[DATA] ACTUAL VS PROJECTED")
        print("-"*70)
        
        dr = avp["denial_reduction"]
        print(f"\n   Denial Reduction:")
        print(f"      Projected: {dr['projected']*100:.1f}%")
        print(f"      Actual:    {dr['actual']*100:.1f}%")
        print(f"      Status:    {dr['status']}")
        
        print("\n" + "="*70)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Execute Phase 3 Priority Action Pilot."""
    
    print("\n" + "="*70)
    print("=" + " "*68 + "=")
    print("=" + "  PHASE 3: PRIORITY ACTION PILOT - PRE-BILL SCRUBBING".center(68) + "=")
    print("=" + " "*68 + "=")
    print("="*70)
    
    # Initialize configuration
    config = PilotConfig()
    
    print("\n[CONFIG] Pilot Configuration:")
    print(f"   * Duration: {config.pilot_duration_days} days")
    print(f"   * Claims/day: ~{config.claims_per_day}")
    print(f"   * Control/Intervention split: {config.control_ratio*100:.0f}%/{(1-config.control_ratio)*100:.0f}%")
    print(f"   * Go/No-Go Thresholds:")
    print(f"     - Minimum denial reduction: {config.min_denial_reduction*100:.0f}%")
    print(f"     - Minimum ROI: {config.min_roi:.1f}x")
    print(f"     - Significance level: alpha = {config.significance_level}")
    
    # Run pilot
    engine = PreBillPilotEngine(config)
    outcomes = engine.run_pilot()
    
    # Calculate metrics
    print("\n[CALC] Calculating pilot metrics...")
    calculator = PilotMetricsCalculator(config)
    metrics = calculator.calculate_metrics(outcomes)
    
    # Make go/no-go decision
    print("[EVAL] Evaluating go/no-go criteria...")
    decision_engine = GoNoGoDecisionEngine(config)
    decision = decision_engine.evaluate(metrics)
    
    # Generate report
    print("[GEN] Generating comprehensive report...")
    reporter = PilotReportGenerator(config)
    report = reporter.generate_report(outcomes, metrics, decision)
    
    # Save report
    report_path = Path("reports/phase3_pilot_results.json")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n[SAVED] Full report saved to: {report_path}")
    
    # Print summary
    reporter.print_summary(report)
    
    # Return for programmatic use
    return {
        "config": config,
        "outcomes": outcomes,
        "metrics": metrics,
        "decision": decision,
        "report": report,
    }


if __name__ == "__main__":
    results = main()

