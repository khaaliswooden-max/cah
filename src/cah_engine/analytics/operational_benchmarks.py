"""
Operational Benchmarks for CAH Staff and Patient-Level Measurement.

Translates optimization goals into actionable daily/weekly/monthly KPIs:
1. PROFITABILITY → Revenue capture, cost control, throughput metrics
2. QUALITY CARE → Clinical outcomes, patient experience, safety events
3. OPTIMIZATION ALIGNMENT → Resource utilization tied to Lagrangian constraints

Each benchmark links directly to:
- Decision variables (x[0]-x[7])
- Objective functions (revenue, cost, quality)
- Constraint satisfaction (regulatory, operational)

Reference: CAH Transformation Engine Optimization Module
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
from datetime import date, datetime, timedelta
import numpy as np


class MeasurementCadence(Enum):
    """Measurement frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class StakeholderLevel(Enum):
    """Who is accountable for the metric."""
    STAFF = "staff"              # Individual nurse, provider, tech
    UNIT = "unit"                # ED, inpatient, outpatient department
    PATIENT = "patient"          # Patient-level outcome
    FACILITY = "facility"        # Hospital-wide aggregate
    EXECUTIVE = "executive"      # C-suite strategic


class OptimizationLink(Enum):
    """Link to optimization model component."""
    REVENUE = "revenue"          # R(x) components
    COST = "cost"                # C(x) components
    MARGIN = "margin"            # Π(x)/R(x)
    QUALITY = "quality"          # Q(x) composite
    CONSTRAINT = "constraint"    # g(x), h(x)
    DECISION_VAR = "decision_variable"  # x[i]


@dataclass
class BenchmarkThreshold:
    """Performance thresholds for a benchmark."""
    
    target: float               # Optimal/goal value
    floor: float                # Minimum acceptable
    ceiling: float              # Maximum (for "lower is better" metrics)
    direction: str = "higher"   # "higher" or "lower" is better
    
    def status(self, value: float) -> str:
        """Get performance status."""
        if self.direction == "higher":
            if value >= self.target:
                return "excellent"
            elif value >= self.floor:
                return "acceptable"
            else:
                return "critical"
        else:  # lower is better
            if value <= self.target:
                return "excellent"
            elif value <= self.ceiling:
                return "acceptable"
            else:
                return "critical"
    
    def gap_to_target(self, value: float) -> float:
        """Calculate gap to target (positive = improvement needed)."""
        if self.direction == "higher":
            return self.target - value
        else:
            return value - self.target


@dataclass
class OperationalBenchmark:
    """
    Single operational benchmark definition.
    
    Links high-level optimization to staff-level action.
    """
    
    id: str
    name: str
    description: str
    
    # Measurement properties
    cadence: MeasurementCadence
    stakeholder: StakeholderLevel
    unit: str                   # e.g., "minutes", "%", "per 1000 days"
    
    # Optimization linkage
    optimization_link: OptimizationLink
    decision_variable_index: Optional[int] = None  # x[i] if applicable
    quality_measure: Optional[str] = None          # MBQIP measure if applicable
    
    # Thresholds
    threshold: BenchmarkThreshold = None
    
    # Calculation
    formula: str = ""           # Human-readable formula
    
    # Data requirements
    data_sources: List[str] = field(default_factory=list)
    fhir_resources: List[str] = field(default_factory=list)
    
    # Evidence base
    evidence_citation: str = ""
    
    def calculate(self, numerator: float, denominator: float = 1.0) -> float:
        """Calculate benchmark value."""
        if denominator == 0:
            return 0.0
        return numerator / denominator
    
    def to_dict(self) -> Dict:
        """Export as dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "cadence": self.cadence.value,
            "stakeholder": self.stakeholder.value,
            "unit": self.unit,
            "optimization_link": self.optimization_link.value,
            "threshold": {
                "target": self.threshold.target,
                "floor": self.threshold.floor,
                "ceiling": self.threshold.ceiling,
                "direction": self.threshold.direction,
            } if self.threshold else None,
            "formula": self.formula,
            "data_sources": self.data_sources,
        }


# =============================================================================
# PROFITABILITY BENCHMARKS
# =============================================================================

PROFITABILITY_BENCHMARKS = [
    # --- DAILY METRICS ---
    OperationalBenchmark(
        id="PROF-D01",
        name="Daily Revenue per Patient Day",
        description="Total charges generated divided by occupied bed days",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.UNIT,
        unit="$/patient-day",
        optimization_link=OptimizationLink.REVENUE,
        decision_variable_index=4,  # x[4]: ADC
        threshold=BenchmarkThreshold(
            target=4200.0,      # Based on α₁/ALOS ~ $12,847/3.2
            floor=3500.0,
            ceiling=6000.0,
            direction="higher"
        ),
        formula="Daily Revenue / Occupied Bed Days",
        data_sources=["EHR charges", "ADT census"],
        fhir_resources=["Account", "Encounter"],
        evidence_citation="CMS Cost Report Form 2552-10, Worksheet S-3"
    ),
    
    OperationalBenchmark(
        id="PROF-D02",
        name="ED Revenue per Visit",
        description="ED facility + professional charges per ED encounter",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.UNIT,
        unit="$/visit",
        optimization_link=OptimizationLink.REVENUE,
        decision_variable_index=5,  # x[5]: ED visits
        threshold=BenchmarkThreshold(
            target=485.0,       # α₂ parameter
            floor=400.0,
            ceiling=800.0,
            direction="higher"
        ),
        formula="ED Total Charges / ED Visit Count",
        data_sources=["ED charges", "ED census"],
        fhir_resources=["Account", "Encounter"],
        evidence_citation="HCUP NIS 2022"
    ),
    
    OperationalBenchmark(
        id="PROF-D03",
        name="Daily Labor Cost per Patient Day",
        description="Nursing + provider labor cost divided by patient days",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="$/patient-day",
        optimization_link=OptimizationLink.COST,
        threshold=BenchmarkThreshold(
            target=2800.0,      # Target cost to maintain margin
            floor=2000.0,
            ceiling=3500.0,     # Ceiling - higher is worse
            direction="lower"
        ),
        formula="(Nursing Hours × Rate + Provider Hours × Rate) / Patient Days",
        data_sources=["Payroll", "ADT census"],
        fhir_resources=["PractitionerRole"],
        evidence_citation="BLS OES May 2024"
    ),
    
    OperationalBenchmark(
        id="PROF-D04",
        name="Daily Bed Utilization Rate",
        description="Occupied beds / staffed beds",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.UNIT,
        unit="%",
        optimization_link=OptimizationLink.CONSTRAINT,
        decision_variable_index=0,  # x[0]: acute beds
        threshold=BenchmarkThreshold(
            target=50.0,        # CAH typical ~40-60%
            floor=30.0,
            ceiling=85.0,       # Constraint: ADC ≤ 85% beds
            direction="higher"
        ),
        formula="(Midnight Census / Staffed Beds) × 100",
        data_sources=["ADT census", "Staffing grid"],
        fhir_resources=["Location", "Encounter"],
        evidence_citation="42 CFR § 485.620; Flex Monitoring Team"
    ),
    
    OperationalBenchmark(
        id="PROF-D05",
        name="Outpatient Encounters per Day",
        description="Total outpatient visits (clinic, lab, imaging, therapy)",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="visits/day",
        optimization_link=OptimizationLink.REVENUE,
        decision_variable_index=6,  # x[6]: OP visits
        threshold=BenchmarkThreshold(
            target=55.0,        # ~20,000/year ÷ 365
            floor=40.0,
            ceiling=150.0,
            direction="higher"
        ),
        formula="Count of Outpatient Encounters",
        data_sources=["Scheduling system", "EHR encounters"],
        fhir_resources=["Encounter"],
        evidence_citation="CMS Cost Report Worksheet S-3"
    ),
    
    # --- WEEKLY METRICS ---
    OperationalBenchmark(
        id="PROF-W01",
        name="Weekly Charge Capture Rate",
        description="Documented services with corresponding charges",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.STAFF,
        unit="%",
        optimization_link=OptimizationLink.REVENUE,
        threshold=BenchmarkThreshold(
            target=98.0,
            floor=95.0,
            ceiling=100.0,
            direction="higher"
        ),
        formula="(Services with Charges / Documented Services) × 100",
        data_sources=["CDM", "Documentation audit"],
        fhir_resources=["ChargeItem", "Procedure"],
        evidence_citation="MGMA benchmarks"
    ),
    
    OperationalBenchmark(
        id="PROF-W02",
        name="Weekly Overtime Hours per FTE",
        description="Overtime labor hours relative to budgeted FTEs",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.UNIT,
        unit="hours/FTE",
        optimization_link=OptimizationLink.COST,
        decision_variable_index=2,  # x[2]: Nursing FTE
        threshold=BenchmarkThreshold(
            target=2.0,
            floor=0.0,
            ceiling=6.0,
            direction="lower"
        ),
        formula="Total OT Hours / Budgeted FTE",
        data_sources=["Payroll", "Scheduling"],
        fhir_resources=["PractitionerRole"],
        evidence_citation="BLS labor statistics"
    ),
    
    OperationalBenchmark(
        id="PROF-W03",
        name="Case Mix Index - Weekly Average",
        description="Average DRG weight for inpatient discharges",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="index",
        optimization_link=OptimizationLink.REVENUE,
        decision_variable_index=7,  # x[7]: CMI
        threshold=BenchmarkThreshold(
            target=1.10,
            floor=0.85,
            ceiling=1.40,
            direction="higher"
        ),
        formula="Sum(DRG Weights) / Discharge Count",
        data_sources=["HIM coding", "Claims"],
        fhir_resources=["Encounter", "Claim"],
        evidence_citation="CMS MS-DRG"
    ),
    
    OperationalBenchmark(
        id="PROF-W04",
        name="Swing Bed Utilization",
        description="Swing bed days used vs allocated",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.UNIT,
        unit="%",
        optimization_link=OptimizationLink.REVENUE,
        decision_variable_index=1,  # x[1]: swing beds
        threshold=BenchmarkThreshold(
            target=65.0,        # swing_occupancy parameter
            floor=40.0,
            ceiling=90.0,
            direction="higher"
        ),
        formula="(Swing Bed Days Used / (Swing Beds × 7)) × 100",
        data_sources=["ADT", "Swing bed log"],
        fhir_resources=["Encounter", "Location"],
        evidence_citation="42 CFR § 485.645"
    ),
    
    OperationalBenchmark(
        id="PROF-W05",
        name="ED Provider Productivity",
        description="ED encounters per provider shift",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.STAFF,
        unit="encounters/shift",
        optimization_link=OptimizationLink.CONSTRAINT,
        decision_variable_index=3,  # x[3]: provider FTE
        threshold=BenchmarkThreshold(
            target=12.0,        # ~5000 visits/year ÷ 417 shifts
            floor=8.0,
            ceiling=20.0,
            direction="higher"
        ),
        formula="Weekly ED Visits / Provider Shifts Worked",
        data_sources=["ED log", "Scheduling"],
        fhir_resources=["Encounter", "PractitionerRole"],
        evidence_citation="ACEP workload guidelines"
    ),
    
    # --- MONTHLY METRICS ---
    OperationalBenchmark(
        id="PROF-M01",
        name="Operating Margin",
        description="Net operating income / total operating revenue",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.EXECUTIVE,
        unit="%",
        optimization_link=OptimizationLink.MARGIN,
        threshold=BenchmarkThreshold(
            target=5.0,         # margin_floor constraint
            floor=0.0,
            ceiling=15.0,
            direction="higher"
        ),
        formula="(Revenue - Expenses) / Revenue × 100",
        data_sources=["GL", "Financial statements"],
        fhir_resources=["Account"],
        evidence_citation="CMS Cost Report Worksheet G-3"
    ),
    
    OperationalBenchmark(
        id="PROF-M02",
        name="Days in A/R",
        description="Average collection period for patient accounts",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="days",
        optimization_link=OptimizationLink.REVENUE,
        threshold=BenchmarkThreshold(
            target=45.0,
            floor=30.0,
            ceiling=60.0,
            direction="lower"
        ),
        formula="(Ending A/R / Monthly Revenue) × 30",
        data_sources=["Billing system", "GL"],
        fhir_resources=["Account", "Claim"],
        evidence_citation="HFMA benchmarks"
    ),
    
    OperationalBenchmark(
        id="PROF-M03",
        name="Cost per Adjusted Patient Day",
        description="Total expenses / case-mix adjusted patient days",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.EXECUTIVE,
        unit="$/APD",
        optimization_link=OptimizationLink.COST,
        threshold=BenchmarkThreshold(
            target=3200.0,
            floor=2500.0,
            ceiling=4000.0,
            direction="lower"
        ),
        formula="Total Operating Expenses / (Patient Days × CMI)",
        data_sources=["GL", "ADT", "Coding"],
        fhir_resources=["Account", "Encounter"],
        evidence_citation="CMS Cost Report Worksheet D-1"
    ),
    
    OperationalBenchmark(
        id="PROF-M04",
        name="Medicare Cost-to-Charge Ratio",
        description="Allowable costs / billed charges for Medicare",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.EXECUTIVE,
        unit="ratio",
        optimization_link=OptimizationLink.REVENUE,
        threshold=BenchmarkThreshold(
            target=0.45,
            floor=0.35,
            ceiling=0.60,
            direction="lower"
        ),
        formula="Medicare Allowable Costs / Medicare Charges",
        data_sources=["Cost report", "Claims"],
        fhir_resources=["Claim", "Account"],
        evidence_citation="CMS Cost Report Worksheet C"
    ),
    
    OperationalBenchmark(
        id="PROF-M05",
        name="Net Patient Revenue per FTE",
        description="Revenue productivity per full-time equivalent",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="$/FTE",
        optimization_link=OptimizationLink.MARGIN,
        threshold=BenchmarkThreshold(
            target=22000.0,     # ~$15M revenue / 56 FTE monthly
            floor=18000.0,
            ceiling=30000.0,
            direction="higher"
        ),
        formula="Net Patient Revenue / Total FTEs",
        data_sources=["GL", "HR payroll"],
        fhir_resources=["Account", "PractitionerRole"],
        evidence_citation="Flex Monitoring Team"
    ),
]


# =============================================================================
# QUALITY CARE BENCHMARKS
# =============================================================================

QUALITY_BENCHMARKS = [
    # --- DAILY METRICS ---
    OperationalBenchmark(
        id="QUAL-D01",
        name="ED Door-to-Provider Time",
        description="Minutes from ED arrival to first provider contact",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.PATIENT,
        unit="minutes",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="ed_throughput",
        threshold=BenchmarkThreshold(
            target=25.0,
            floor=15.0,
            ceiling=45.0,
            direction="lower"
        ),
        formula="Median(Provider Contact Time - Arrival Time)",
        data_sources=["ED tracking board", "EHR timestamps"],
        fhir_resources=["Encounter"],
        evidence_citation="CMS ED-1b measure"
    ),
    
    OperationalBenchmark(
        id="QUAL-D02",
        name="Pain Assessment Compliance",
        description="Patients with pain score documented within 30 min",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.STAFF,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="pain_management",
        threshold=BenchmarkThreshold(
            target=95.0,
            floor=90.0,
            ceiling=100.0,
            direction="higher"
        ),
        formula="(Patients with Pain Score ≤30min / All Patients) × 100",
        data_sources=["EHR vital signs", "Documentation"],
        fhir_resources=["Observation"],
        evidence_citation="OP-18b measure"
    ),
    
    OperationalBenchmark(
        id="QUAL-D03",
        name="Nursing Hours per Patient Day",
        description="Direct nursing care hours per patient day",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.UNIT,
        unit="hours/patient-day",
        optimization_link=OptimizationLink.QUALITY,
        decision_variable_index=2,  # x[2]: Nursing FTE
        threshold=BenchmarkThreshold(
            target=8.0,         # Evidence-based safe staffing
            floor=6.0,
            ceiling=12.0,
            direction="higher"
        ),
        formula="(Nursing Hours Worked) / (Patient Days)",
        data_sources=["Payroll", "ADT"],
        fhir_resources=["PractitionerRole", "Encounter"],
        evidence_citation="Aiken et al. (2014) LANCET"
    ),
    
    OperationalBenchmark(
        id="QUAL-D04",
        name="Falls Risk Assessment Rate",
        description="Patients with falls risk assessment on admission",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.STAFF,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="falls_injury",
        threshold=BenchmarkThreshold(
            target=100.0,
            floor=95.0,
            ceiling=100.0,
            direction="higher"
        ),
        formula="(Admissions with Falls Assessment / Total Admissions) × 100",
        data_sources=["EHR assessments"],
        fhir_resources=["RiskAssessment", "Encounter"],
        evidence_citation="AHRQ Patient Safety Indicators"
    ),
    
    OperationalBenchmark(
        id="QUAL-D05",
        name="Hand Hygiene Compliance",
        description="Observed hand hygiene opportunities with compliance",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.STAFF,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="cauti_rate",
        threshold=BenchmarkThreshold(
            target=95.0,
            floor=85.0,
            ceiling=100.0,
            direction="higher"
        ),
        formula="(Compliant Observations / Total Observations) × 100",
        data_sources=["Infection control audit"],
        fhir_resources=["Observation"],
        evidence_citation="CDC NHSN"
    ),
    
    # --- WEEKLY METRICS ---
    OperationalBenchmark(
        id="QUAL-W01",
        name="ED Length of Stay",
        description="Time from arrival to departure (admit/discharge/transfer)",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.PATIENT,
        unit="minutes",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="ed_throughput",
        threshold=BenchmarkThreshold(
            target=180.0,       # 3 hours target
            floor=120.0,
            ceiling=240.0,      # 4 hours ceiling
            direction="lower"
        ),
        formula="Median(Departure Time - Arrival Time)",
        data_sources=["ED tracking board"],
        fhir_resources=["Encounter"],
        evidence_citation="CMS ED-2b measure"
    ),
    
    OperationalBenchmark(
        id="QUAL-W02",
        name="Medication Reconciliation Rate",
        description="Discharges with completed medication reconciliation",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.STAFF,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="readmission_30d",
        threshold=BenchmarkThreshold(
            target=98.0,
            floor=90.0,
            ceiling=100.0,
            direction="higher"
        ),
        formula="(Discharges with Med Rec / Total Discharges) × 100",
        data_sources=["EHR medication list"],
        fhir_resources=["MedicationStatement", "Encounter"],
        evidence_citation="Joint Commission NPSG"
    ),
    
    OperationalBenchmark(
        id="QUAL-W03",
        name="HCAHPS Responsiveness Score (Sampled)",
        description="Patients reporting staff always responsive",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.PATIENT,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="hcahps_overall",
        threshold=BenchmarkThreshold(
            target=75.0,
            floor=65.0,
            ceiling=90.0,
            direction="higher"
        ),
        formula="(Patients Rating 'Always' / Surveyed Patients) × 100",
        data_sources=["HCAHPS surveys", "Real-time feedback"],
        fhir_resources=["QuestionnaireResponse"],
        evidence_citation="CMS HCAHPS"
    ),
    
    OperationalBenchmark(
        id="QUAL-W04",
        name="Catheter Days per 100 Patient Days",
        description="Urinary catheter utilization rate",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.UNIT,
        unit="days/100 PD",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="cauti_rate",
        threshold=BenchmarkThreshold(
            target=15.0,
            floor=10.0,
            ceiling=25.0,
            direction="lower"
        ),
        formula="(Catheter Days / Patient Days) × 100",
        data_sources=["EHR device documentation"],
        fhir_resources=["DeviceUseStatement", "Encounter"],
        evidence_citation="CDC NHSN CAUTI"
    ),
    
    OperationalBenchmark(
        id="QUAL-W05",
        name="Opioid Prescribing Compliance",
        description="Opioid prescriptions meeting safe prescribing criteria",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.STAFF,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="opioid_concurrent",
        threshold=BenchmarkThreshold(
            target=95.0,
            floor=90.0,
            ceiling=100.0,
            direction="higher"
        ),
        formula="(Compliant Opioid Rx / Total Opioid Rx) × 100",
        data_sources=["PDMP", "EHR prescriptions"],
        fhir_resources=["MedicationRequest"],
        evidence_citation="CMS Safe Opioid measure"
    ),
    
    # --- MONTHLY METRICS ---
    OperationalBenchmark(
        id="QUAL-M01",
        name="30-Day All-Cause Readmission Rate",
        description="Patients readmitted within 30 days of discharge",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.PATIENT,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="readmission_30d",
        threshold=BenchmarkThreshold(
            target=12.0,
            floor=8.0,
            ceiling=18.0,
            direction="lower"
        ),
        formula="(Readmissions ≤30 days / Eligible Discharges) × 100",
        data_sources=["ADT", "Claims"],
        fhir_resources=["Encounter"],
        evidence_citation="CMS HRRP"
    ),
    
    OperationalBenchmark(
        id="QUAL-M02",
        name="Falls with Injury Rate",
        description="Patient falls resulting in injury per 1000 patient days",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.UNIT,
        unit="per 1000 PD",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="falls_injury",
        threshold=BenchmarkThreshold(
            target=1.5,
            floor=0.5,
            ceiling=3.0,
            direction="lower"
        ),
        formula="(Falls with Injury / Patient Days) × 1000",
        data_sources=["Incident reports", "ADT"],
        fhir_resources=["AdverseEvent", "Encounter"],
        evidence_citation="AHRQ PSI-08"
    ),
    
    OperationalBenchmark(
        id="QUAL-M03",
        name="CAUTI Rate",
        description="Catheter-associated UTIs per 1000 catheter days",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.UNIT,
        unit="per 1000 cath days",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="cauti_rate",
        threshold=BenchmarkThreshold(
            target=1.0,
            floor=0.5,
            ceiling=2.0,
            direction="lower"
        ),
        formula="(CAUTI Events / Catheter Days) × 1000",
        data_sources=["Infection control", "Lab"],
        fhir_resources=["Condition", "DeviceUseStatement"],
        evidence_citation="CDC NHSN CAUTI"
    ),
    
    OperationalBenchmark(
        id="QUAL-M04",
        name="HCAHPS Overall Rating",
        description="Patients rating hospital 9 or 10 on 0-10 scale",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.PATIENT,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        quality_measure="hcahps_overall",
        threshold=BenchmarkThreshold(
            target=72.0,        # Benchmark from QualityBenchmarks
            floor=65.0,
            ceiling=85.0,
            direction="higher"
        ),
        formula="(Patients Rating 9-10 / Surveyed Patients) × 100",
        data_sources=["HCAHPS vendor"],
        fhir_resources=["QuestionnaireResponse"],
        evidence_citation="CMS Hospital Compare"
    ),
    
    OperationalBenchmark(
        id="QUAL-M05",
        name="Sepsis Bundle Compliance",
        description="Sepsis patients receiving timely bundle care",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.STAFF,
        unit="%",
        optimization_link=OptimizationLink.QUALITY,
        threshold=BenchmarkThreshold(
            target=80.0,
            floor=60.0,
            ceiling=95.0,
            direction="higher"
        ),
        formula="(Compliant Sepsis Cases / All Sepsis Cases) × 100",
        data_sources=["EHR sepsis alerts", "Chart review"],
        fhir_resources=["Condition", "MedicationAdministration"],
        evidence_citation="CMS SEP-1"
    ),
]


# =============================================================================
# OPTIMIZATION ALIGNMENT BENCHMARKS (Constraint/Decision Variable Tracking)
# =============================================================================

OPTIMIZATION_BENCHMARKS = [
    # --- DAILY METRICS ---
    OperationalBenchmark(
        id="OPT-D01",
        name="Total Beds Occupied (Acute + Swing)",
        description="Census relative to 25-bed CAH cap",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="beds",
        optimization_link=OptimizationLink.CONSTRAINT,
        threshold=BenchmarkThreshold(
            target=18.0,        # ~72% utilization of 25
            floor=10.0,
            ceiling=25.0,       # HARD CONSTRAINT: 42 CFR § 485.620
            direction="higher"
        ),
        formula="Acute Census + Swing Census",
        data_sources=["ADT"],
        fhir_resources=["Encounter", "Location"],
        evidence_citation="42 CFR § 485.620"
    ),
    
    OperationalBenchmark(
        id="OPT-D02",
        name="Average Length of Stay (Rolling)",
        description="Rolling 7-day ALOS in hours",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="hours",
        optimization_link=OptimizationLink.CONSTRAINT,
        threshold=BenchmarkThreshold(
            target=72.0,        # 3 days × 24 hours
            floor=24.0,
            ceiling=96.0,       # HARD CONSTRAINT: 42 CFR § 485.620
            direction="lower"
        ),
        formula="Sum(Discharge Hour - Admit Hour) / Discharge Count",
        data_sources=["ADT"],
        fhir_resources=["Encounter"],
        evidence_citation="42 CFR § 485.620"
    ),
    
    OperationalBenchmark(
        id="OPT-D03",
        name="Nurse-to-Patient Ratio",
        description="Nursing staff per occupied bed (day shift)",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.UNIT,
        unit="ratio",
        optimization_link=OptimizationLink.CONSTRAINT,
        decision_variable_index=2,  # x[2]: Nursing FTE
        threshold=BenchmarkThreshold(
            target=0.50,        # Constraint: x[2] ≥ 0.5 × x[4]
            floor=0.40,
            ceiling=0.80,
            direction="higher"
        ),
        formula="Nursing Staff on Duty / Occupied Beds",
        data_sources=["Staffing grid", "ADT"],
        fhir_resources=["PractitionerRole", "Location"],
        evidence_citation="Aiken et al. (2014); Constraint h₂"
    ),
    
    OperationalBenchmark(
        id="OPT-D04",
        name="ED Coverage Hours",
        description="Hours with MD/PA/NP physically present in ED",
        cadence=MeasurementCadence.DAILY,
        stakeholder=StakeholderLevel.UNIT,
        unit="hours",
        optimization_link=OptimizationLink.CONSTRAINT,
        decision_variable_index=3,  # x[3]: Provider FTE
        threshold=BenchmarkThreshold(
            target=24.0,        # 24/7 coverage requirement
            floor=20.0,
            ceiling=24.0,
            direction="higher"
        ),
        formula="Sum of Provider On-Site Hours",
        data_sources=["Scheduling", "Time clock"],
        fhir_resources=["PractitionerRole", "Schedule"],
        evidence_citation="42 CFR § 485.618; Constraint g₄"
    ),
    
    # --- WEEKLY METRICS ---
    OperationalBenchmark(
        id="OPT-W01",
        name="ED Visits per Provider FTE",
        description="ED encounter volume relative to provider staffing",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="visits/FTE",
        optimization_link=OptimizationLink.CONSTRAINT,
        decision_variable_index=3,  # x[3]: Provider FTE
        threshold=BenchmarkThreshold(
            target=90.0,        # ~4,700 annual ÷ 52 weeks ÷ 5 FTE
            floor=60.0,
            ceiling=125.0,      # Near 5000/FTE annual ceiling
            direction="higher"
        ),
        formula="Weekly ED Visits / Provider FTEs",
        data_sources=["ED log", "HR"],
        fhir_resources=["Encounter", "PractitionerRole"],
        evidence_citation="ACEP workload; Constraint h₄"
    ),
    
    OperationalBenchmark(
        id="OPT-W02",
        name="Staffed vs. Budgeted FTE Variance",
        description="Actual FTEs worked vs. budgeted FTEs",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="%",
        optimization_link=OptimizationLink.COST,
        threshold=BenchmarkThreshold(
            target=0.0,
            floor=-5.0,
            ceiling=5.0,
            direction="lower"  # Closer to 0 is better
        ),
        formula="((Actual FTE - Budgeted FTE) / Budgeted FTE) × 100",
        data_sources=["Payroll", "Budget"],
        fhir_resources=["PractitionerRole"],
        evidence_citation="Internal operations"
    ),
    
    OperationalBenchmark(
        id="OPT-W03",
        name="Census Capacity Utilization",
        description="ADC relative to 85% of staffed acute beds",
        cadence=MeasurementCadence.WEEKLY,
        stakeholder=StakeholderLevel.FACILITY,
        unit="%",
        optimization_link=OptimizationLink.CONSTRAINT,
        decision_variable_index=4,  # x[4]: ADC
        threshold=BenchmarkThreshold(
            target=70.0,        # Target 70% of capacity
            floor=40.0,
            ceiling=100.0,      # 100% of 85% = at constraint
            direction="higher"
        ),
        formula="(Weekly Avg Census / (0.85 × Staffed Beds)) × 100",
        data_sources=["ADT", "Staffing"],
        fhir_resources=["Encounter", "Location"],
        evidence_citation="Constraint h₁"
    ),
    
    # --- MONTHLY METRICS ---
    OperationalBenchmark(
        id="OPT-M01",
        name="Constraint Satisfaction Score",
        description="Percentage of days all regulatory constraints met",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.EXECUTIVE,
        unit="%",
        optimization_link=OptimizationLink.CONSTRAINT,
        threshold=BenchmarkThreshold(
            target=100.0,
            floor=95.0,
            ceiling=100.0,
            direction="higher"
        ),
        formula="(Days with All Constraints Met / Days in Month) × 100",
        data_sources=["Compliance dashboard"],
        fhir_resources=["MeasureReport"],
        evidence_citation="42 CFR § 485"
    ),
    
    OperationalBenchmark(
        id="OPT-M02",
        name="Optimization Model Alignment",
        description="Correlation of actual operations to optimal solution",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.EXECUTIVE,
        unit="score",
        optimization_link=OptimizationLink.DECISION_VAR,
        threshold=BenchmarkThreshold(
            target=0.90,
            floor=0.75,
            ceiling=1.00,
            direction="higher"
        ),
        formula="1 - Mean(|Actual_x - Optimal_x| / Range_x)",
        data_sources=["All operational systems"],
        fhir_resources=["MeasureReport"],
        evidence_citation="CAH Optimization Module"
    ),
    
    OperationalBenchmark(
        id="OPT-M03",
        name="Pareto Efficiency Score",
        description="Distance from actual to Pareto front",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.EXECUTIVE,
        unit="score",
        optimization_link=OptimizationLink.MARGIN,
        threshold=BenchmarkThreshold(
            target=0.95,
            floor=0.80,
            ceiling=1.00,
            direction="higher"
        ),
        formula="1 - Distance(Actual, Pareto Front) / Max Distance",
        data_sources=["Financial", "Quality systems"],
        fhir_resources=["MeasureReport"],
        evidence_citation="CAH Pareto Module"
    ),
    
    OperationalBenchmark(
        id="OPT-M04",
        name="Shadow Price Value Captured",
        description="Value gained from binding constraint management",
        cadence=MeasurementCadence.MONTHLY,
        stakeholder=StakeholderLevel.EXECUTIVE,
        unit="$",
        optimization_link=OptimizationLink.CONSTRAINT,
        threshold=BenchmarkThreshold(
            target=0.0,         # Positive = value captured
            floor=-50000.0,
            ceiling=100000.0,
            direction="higher"
        ),
        formula="Sum(Shadow_Price_i × Constraint_Slack_i)",
        data_sources=["Optimization model output"],
        fhir_resources=["MeasureReport"],
        evidence_citation="Lagrangian analysis"
    ),
]


# =============================================================================
# BENCHMARK REGISTRY
# =============================================================================

class BenchmarkRegistry:
    """
    Registry of all operational benchmarks.
    
    Provides:
    - Lookup by ID, cadence, stakeholder, optimization link
    - Aggregation and rollup logic
    - Dashboard data generation
    """
    
    def __init__(self):
        self.benchmarks: Dict[str, OperationalBenchmark] = {}
        self._register_all()
    
    def _register_all(self):
        """Register all benchmark definitions."""
        all_benchmarks = (
            PROFITABILITY_BENCHMARKS +
            QUALITY_BENCHMARKS +
            OPTIMIZATION_BENCHMARKS
        )
        for benchmark in all_benchmarks:
            self.benchmarks[benchmark.id] = benchmark
    
    def get(self, benchmark_id: str) -> Optional[OperationalBenchmark]:
        """Get benchmark by ID."""
        return self.benchmarks.get(benchmark_id)
    
    def get_by_cadence(self, cadence: MeasurementCadence) -> List[OperationalBenchmark]:
        """Get all benchmarks for a specific cadence."""
        return [b for b in self.benchmarks.values() if b.cadence == cadence]
    
    def get_by_stakeholder(self, stakeholder: StakeholderLevel) -> List[OperationalBenchmark]:
        """Get all benchmarks for a specific stakeholder level."""
        return [b for b in self.benchmarks.values() if b.stakeholder == stakeholder]
    
    def get_by_optimization_link(self, link: OptimizationLink) -> List[OperationalBenchmark]:
        """Get all benchmarks linked to specific optimization component."""
        return [b for b in self.benchmarks.values() if b.optimization_link == link]
    
    def get_daily_staff_metrics(self) -> List[OperationalBenchmark]:
        """Get daily metrics measurable at staff level."""
        return [
            b for b in self.benchmarks.values()
            if b.cadence == MeasurementCadence.DAILY
            and b.stakeholder in [StakeholderLevel.STAFF, StakeholderLevel.PATIENT]
        ]
    
    def get_quality_linked(self, quality_measure: str) -> List[OperationalBenchmark]:
        """Get benchmarks linked to specific MBQIP quality measure."""
        return [
            b for b in self.benchmarks.values()
            if b.quality_measure == quality_measure
        ]
    
    def get_decision_variable_linked(self, var_index: int) -> List[OperationalBenchmark]:
        """Get benchmarks linked to specific decision variable x[i]."""
        return [
            b for b in self.benchmarks.values()
            if b.decision_variable_index == var_index
        ]
    
    def generate_dashboard_config(self) -> Dict:
        """Generate configuration for dashboard display."""
        return {
            "daily": {
                "profitability": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.DAILY)
                                  if b.optimization_link in [OptimizationLink.REVENUE, OptimizationLink.COST, OptimizationLink.MARGIN]],
                "quality": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.DAILY)
                           if b.optimization_link == OptimizationLink.QUALITY],
                "operational": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.DAILY)
                               if b.optimization_link in [OptimizationLink.CONSTRAINT, OptimizationLink.DECISION_VAR]],
            },
            "weekly": {
                "profitability": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.WEEKLY)
                                  if b.optimization_link in [OptimizationLink.REVENUE, OptimizationLink.COST, OptimizationLink.MARGIN]],
                "quality": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.WEEKLY)
                           if b.optimization_link == OptimizationLink.QUALITY],
                "operational": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.WEEKLY)
                               if b.optimization_link in [OptimizationLink.CONSTRAINT, OptimizationLink.DECISION_VAR]],
            },
            "monthly": {
                "profitability": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.MONTHLY)
                                  if b.optimization_link in [OptimizationLink.REVENUE, OptimizationLink.COST, OptimizationLink.MARGIN]],
                "quality": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.MONTHLY)
                           if b.optimization_link == OptimizationLink.QUALITY],
                "operational": [b.to_dict() for b in self.get_by_cadence(MeasurementCadence.MONTHLY)
                               if b.optimization_link in [OptimizationLink.CONSTRAINT, OptimizationLink.DECISION_VAR]],
            },
        }
    
    def to_dict(self) -> Dict:
        """Export all benchmarks."""
        return {b_id: b.to_dict() for b_id, b in self.benchmarks.items()}


# =============================================================================
# BENCHMARK CALCULATOR
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result of a benchmark calculation."""
    benchmark_id: str
    value: float
    status: str             # excellent, acceptable, critical
    gap_to_target: float
    trend: str = "stable"   # improving, stable, declining
    timestamp: datetime = field(default_factory=datetime.now)


class BenchmarkCalculator:
    """
    Calculate benchmark values from operational data.
    
    Bridges raw data to benchmark framework.
    """
    
    def __init__(self, registry: BenchmarkRegistry = None):
        self.registry = registry or BenchmarkRegistry()
    
    def calculate(
        self,
        benchmark_id: str,
        numerator: float,
        denominator: float = 1.0,
    ) -> BenchmarkResult:
        """Calculate a single benchmark result."""
        benchmark = self.registry.get(benchmark_id)
        if not benchmark:
            raise ValueError(f"Unknown benchmark: {benchmark_id}")
        
        value = benchmark.calculate(numerator, denominator)
        status = benchmark.threshold.status(value) if benchmark.threshold else "unknown"
        gap = benchmark.threshold.gap_to_target(value) if benchmark.threshold else 0.0
        
        return BenchmarkResult(
            benchmark_id=benchmark_id,
            value=value,
            status=status,
            gap_to_target=gap,
        )
    
    def calculate_daily_scorecard(
        self,
        data: Dict[str, Tuple[float, float]],
    ) -> List[BenchmarkResult]:
        """
        Calculate all daily benchmarks from data dict.
        
        Args:
            data: Dict mapping benchmark_id to (numerator, denominator)
            
        Returns:
            List of BenchmarkResult for all calculated metrics
        """
        results = []
        daily_benchmarks = self.registry.get_by_cadence(MeasurementCadence.DAILY)
        
        for benchmark in daily_benchmarks:
            if benchmark.id in data:
                num, denom = data[benchmark.id]
                result = self.calculate(benchmark.id, num, denom)
                results.append(result)
        
        return results
    
    def calculate_optimization_alignment(
        self,
        actual_x: np.ndarray,
        optimal_x: np.ndarray,
        bounds: List[Tuple[float, float]],
    ) -> float:
        """
        Calculate how closely operations align with optimal solution.
        
        Returns score in [0, 1] where 1 = perfectly aligned.
        """
        n = len(actual_x)
        deviations = []
        
        for i in range(n):
            range_i = bounds[i][1] - bounds[i][0]
            if range_i > 0:
                deviation = abs(actual_x[i] - optimal_x[i]) / range_i
                deviations.append(deviation)
        
        mean_deviation = np.mean(deviations)
        return 1.0 - mean_deviation


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_all_benchmarks() -> BenchmarkRegistry:
    """Get the complete benchmark registry."""
    return BenchmarkRegistry()


def get_staff_daily_checklist() -> List[Dict]:
    """Get simplified daily checklist for frontline staff."""
    registry = BenchmarkRegistry()
    staff_metrics = registry.get_daily_staff_metrics()
    
    return [
        {
            "id": b.id,
            "name": b.name,
            "target": b.threshold.target if b.threshold else None,
            "unit": b.unit,
            "how_to_measure": b.formula,
        }
        for b in staff_metrics
    ]


def get_executive_monthly_dashboard() -> List[Dict]:
    """Get executive-level monthly metrics."""
    registry = BenchmarkRegistry()
    executive_metrics = [
        b for b in registry.get_by_cadence(MeasurementCadence.MONTHLY)
        if b.stakeholder == StakeholderLevel.EXECUTIVE
    ]
    
    return [b.to_dict() for b in executive_metrics]


def validate_against_optimization(
    operational_data: Dict,
    optimization_result: "OptimizationResult",
) -> Dict:
    """
    Validate operational benchmarks against optimization model.
    
    Returns gap analysis between actual and optimal.
    """
    registry = BenchmarkRegistry()
    calculator = BenchmarkCalculator(registry)
    
    gaps = {}
    
    # Map decision variables to benchmarks
    var_to_benchmark = {
        0: "OPT-D01",  # Total beds
        2: "OPT-D03",  # Nurse ratio
        3: "OPT-D04",  # ED coverage
        4: "OPT-W03",  # Census capacity
    }
    
    for var_idx, benchmark_id in var_to_benchmark.items():
        if benchmark_id in operational_data:
            actual = operational_data[benchmark_id]
            optimal = optimization_result.x[var_idx]
            gaps[benchmark_id] = {
                "actual": actual,
                "optimal": optimal,
                "gap": actual - optimal,
                "gap_pct": ((actual - optimal) / optimal * 100) if optimal != 0 else 0,
            }
    
    return gaps

