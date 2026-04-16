"""
Workforce Optimization Module — CAHSP Class 4.

Models the four workforce targets for Critical Access Hospitals:
  1. Travel nurse dependency — reduce ratio while maintaining 24/7 coverage
     under the 80–120 FTE cap (MV-CAHI constraint)
  2. Tele-specialist coverage — specialty access hours without permanent hire
  3. Burn-out index — nursing workload proxy via hours-per-FTE calculation
  4. 5-year pipeline adequacy — HRSA NHSC scholar projection model

CAHSP Class 4 is the most complex problem class, analogous to protein
complex / oligomer prediction: multiple interacting agents with
interdependent constraints, no single "template" solution.

Sources:
    HRSA Area Health Resources Files (AHRF) — workforce supply data
    Flex Monitoring Team workforce reports — rural CAH staffing benchmarks
    Aiken et al. (2014) LANCET — nurse staffing and patient outcomes
    ACEP guidelines — emergency physician workload ceilings
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    from .models import CAHParameters, WorkforceParameters
except ImportError:
    try:
        from models import CAHParameters, WorkforceParameters
    except ImportError:
        # Fallback if models.py not yet updated
        from dataclasses import dataclass as _dc

        @_dc
        class WorkforceParameters:
            total_fte_cap: float = 100.0
            travel_nurse_ratio: float = 0.25
            tele_specialist_hours: float = 40.0
            hrsa_scholar_pipeline: int = 0
            burnout_hours_threshold: float = 48.0

        class CAHParameters:
            pass


# ─── Workforce benchmarks ─────────────────────────────────────────────────────

# CAH FTE range (MV-CAHI specification, MV-CAHI.md)
MV_CAHI_FTE_MIN: float = 80.0
MV_CAHI_FTE_MAX: float = 120.0

# Travel nurse ratios
TARGET_TRAVEL_RATIO: float = 0.15    # ≤ 15% — reduction target
BASELINE_TRAVEL_RATIO: float = 0.25  # ~25% — sector baseline (Flex Monitoring Team)
WORST_TRAVEL_RATIO: float = 0.40     # 40%+ — high-dependency threshold

# Tele-specialist coverage targets (hours / week by discipline)
# Source: HRSA rural health specialty access guidelines
TELE_COVERAGE_TARGETS: Dict[str, float] = {
    "telemedicine_general":   40.0,  # General tele-medicine
    "behavioral_health":      20.0,  # Tele-behavioral health
    "radiology":              40.0,  # Tele-radiology (24/7 read)
    "pharmacy_consultation":  20.0,  # Tele-pharmacy consultation
}
MIN_TOTAL_TELE_HOURS: float = 80.0   # Minimum acceptable weekly tele coverage

# Nursing workload
NHPPD_TARGET: float = 4.0            # Nursing hours per patient day (Aiken 2014)
WEEKLY_HOURS_STANDARD: float = 40.0  # Standard work week
BURNOUT_RISK_HOURS: float = 48.0     # Hours/week above which burnout risk rises sharply

# Pipeline
PIPELINE_HORIZON_YRS: int = 5
RURAL_ATTRITION_RATE: float = 0.12   # 12% annual RN attrition in rural CAHs (HRSA AHRF)
NATURAL_RECRUITMENT_FACTOR: float = 0.50  # Replace 50% of attrition via natural recruitment


# ─── Result type ──────────────────────────────────────────────────────────────

@dataclass
class WorkforceEvaluation:
    """
    Complete workforce evaluation from WorkforceOptimizer.evaluate().

    wi_score is the composite Workforce Index used in CAHSP scoring.
    Each component score is in [0, 1] with higher = better.
    """

    travel_dependency_score: float
    tele_coverage_score: float
    burnout_score: float            # 1 − burnout_index; higher is better
    burnout_index: float            # Raw burnout index in [0, 1]; lower is better
    pipeline_adequacy_5yr: float
    wi_score: float                 # Equal-weight composite of the four scores
    detail: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "wi_score": round(self.wi_score, 4),
            "components": {
                "travel_dependency": round(self.travel_dependency_score, 4),
                "tele_coverage": round(self.tele_coverage_score, 4),
                "burnout_score": round(self.burnout_score, 4),
                "burnout_index_raw": round(self.burnout_index, 4),
                "pipeline_adequacy_5yr": round(self.pipeline_adequacy_5yr, 4),
            },
            "detail": self.detail,
        }

    def __str__(self) -> str:
        lines = [
            "CAHSP Class 4 — Workforce & Staffing Architecture",
            "=" * 52,
            f"  Travel dependency score:    {self.travel_dependency_score:.3f}",
            f"  Tele-specialist coverage:   {self.tele_coverage_score:.3f}",
            f"  Burn-out score (1−idx):     {self.burnout_score:.3f}  (raw index: {self.burnout_index:.3f})",
            f"  5-year pipeline adequacy:   {self.pipeline_adequacy_5yr:.3f}",
            f"  {'─' * 44}",
            f"  Composite WI score:         {self.wi_score:.3f}",
        ]
        return "\n".join(lines)


# ─── Optimizer ────────────────────────────────────────────────────────────────

class WorkforceOptimizer:
    """
    Workforce feasibility and optimization for Critical Access Hospitals.

    Evaluates all four CAHSP Class 4 targets and computes the composite
    Workforce Index (WI) used in CAHSP scoring. Can also accept HRSA AHRF
    data loaded by step5_download_hrsa_workforce.py to ground the pipeline
    adequacy projection in actual county-level supply data.

    Args:
        params:           CAHParameters (operational context)
        workforce_params: WorkforceParameters (workforce configuration)
        hrsa_data:        Optional dict from step5 HRSA download, keyed by state/county

    Example:
        >>> wf = WorkforceOptimizer()
        >>> x = np.array([15, 5, 35, 5, 8, 6000, 15000, 1.0])
        >>> result = wf.evaluate(x)
        >>> print(result)
        CAHSP Class 4 — Workforce & Staffing Architecture
        ...
        Composite WI score: 0.612
    """

    def __init__(
        self,
        params: Optional[CAHParameters] = None,
        workforce_params: Optional[WorkforceParameters] = None,
        hrsa_data: Optional[Dict] = None,
    ):
        self.params = params or CAHParameters()
        self.wf = workforce_params or WorkforceParameters()
        self.hrsa_data = hrsa_data or {}

    # ─── Component evaluators ─────────────────────────────────────────────────

    def travel_dependency_score(self, x: np.ndarray) -> Tuple[float, Dict]:
        """
        Score 1: Travel nurse dependency (lower ratio = higher score).

        Target: reduce travel_nurse_ratio below 15% while maintaining
        24/7 acute coverage using permanent staff.

        Scoring:
            ratio ≥ 40%  → score = 0.0
            ratio = 25%  → score ≈ 0.60 (baseline)
            ratio ≤ 15%  → score = 1.0  (target)

        Returns:
            (score in [0, 1], detail dict)
        """
        nursing_fte = x[2]
        travel_ratio = self.wf.travel_nurse_ratio

        score = float(np.clip(
            (WORST_TRAVEL_RATIO - travel_ratio) / (WORST_TRAVEL_RATIO - TARGET_TRAVEL_RATIO),
            0.0, 1.0,
        ))

        permanent_fte = (1.0 - travel_ratio) * nursing_fte
        adc = max(x[4], 1.0)
        permanent_ratio = permanent_fte / adc
        coverage_maintained = permanent_ratio >= 0.30  # 24/7 floor

        return score, {
            "travel_nurse_ftes": round(travel_ratio * nursing_fte, 1),
            "travel_ratio": round(travel_ratio, 3),
            "permanent_nursing_fte": round(permanent_fte, 1),
            "permanent_ratio_to_adc": round(permanent_ratio, 3),
            "coverage_maintained_without_travel": coverage_maintained,
            "target_ratio": TARGET_TRAVEL_RATIO,
            "baseline_ratio": BASELINE_TRAVEL_RATIO,
            "score": round(score, 4),
        }

    def tele_coverage_score(self, x: np.ndarray) -> Tuple[float, Dict]:
        """
        Score 2: Tele-specialist coverage (higher hours = higher score).

        Models specialty access via tele-medicine without permanent hire.
        Uses self.wf.tele_specialist_hours as total weekly coverage hours.

        Disciplines modeled: telemedicine_general, behavioral_health,
        radiology, pharmacy_consultation.

        Returns:
            (score in [0, 1], detail dict)
        """
        total_hours = self.wf.tele_specialist_hours
        score = float(np.clip(total_hours / MIN_TOTAL_TELE_HOURS, 0.0, 1.0))

        total_target = sum(TELE_COVERAGE_TARGETS.values())
        per_discipline = {
            d: min(total_hours * (t / total_target), t)
            for d, t in TELE_COVERAGE_TARGETS.items()
        }
        disciplines_met = sum(
            1 for d, hrs in per_discipline.items()
            if hrs >= TELE_COVERAGE_TARGETS[d] * 0.75
        )

        return score, {
            "total_tele_hours_per_week": total_hours,
            "minimum_target_hours": MIN_TOTAL_TELE_HOURS,
            "disciplines_fully_met": disciplines_met,
            "total_disciplines": len(TELE_COVERAGE_TARGETS),
            "per_discipline_hours": {k: round(v, 1) for k, v in per_discipline.items()},
            "score": round(score, 4),
        }

    def burnout_index(self, x: np.ndarray) -> Tuple[float, Dict]:
        """
        Score 3: Burn-out index proxy (nursing workload estimation).

        Method: required annual nursing hours (ADC × 365 × NHPPD_TARGET)
        divided by available hours (nursing_FTE × 40 hrs × 52 weeks).
        Utilization > 1.0 indicates systematic overwork.

        Burn-out index rises from 0 at 40 hrs/week to 1 at 48+ hrs/week.

        Returns:
            (burnout_index in [0, 1], detail dict)
            Note: Score = 1 − burnout_index (higher score = less burned out)
        """
        nursing_fte = max(x[2], 1.0)
        adc = x[4]

        required_annual_hrs = adc * 365.0 * NHPPD_TARGET
        available_annual_hrs = nursing_fte * WEEKLY_HOURS_STANDARD * 52.0
        utilization = required_annual_hrs / max(available_annual_hrs, 1.0)

        est_weekly_hrs = utilization * WEEKLY_HOURS_STANDARD
        overwork = max(0.0, est_weekly_hrs - WEEKLY_HOURS_STANDARD)
        burnout_idx = float(np.clip(
            overwork / (BURNOUT_RISK_HOURS - WEEKLY_HOURS_STANDARD),
            0.0, 1.0,
        ))
        score = 1.0 - burnout_idx

        return burnout_idx, {
            "required_annual_nursing_hours": round(required_annual_hrs),
            "available_annual_nursing_hours": round(available_annual_hrs),
            "utilization_ratio": round(utilization, 3),
            "estimated_weekly_hrs_per_fte": round(est_weekly_hrs, 1),
            "nhppd_target": NHPPD_TARGET,
            "burnout_index": round(burnout_idx, 4),
            "score": round(score, 4),
        }

    def pipeline_adequacy_5yr(self, x: np.ndarray) -> Tuple[float, Dict]:
        """
        Score 4: 5-year staffing pipeline adequacy.

        Projects total FTE trajectory under:
        - Rural attrition rate (12% per year — HRSA AHRF)
        - Natural recruitment (replaces 50% of attrition)
        - HRSA NHSC scholars / rural health pipeline additions per year

        If HRSA data was loaded, pipeline_boost is augmented by county-level
        RN graduation and NHSC match data.

        Returns:
            (adequacy_probability in [0, 1], detail dict)
        """
        total_fte = x[2] + x[3]
        min_adequate = total_fte * 0.85  # Allow 15% reduction before degradation

        pipeline_boost = float(self.wf.hrsa_scholar_pipeline)

        # Augment with HRSA data if available
        if self.hrsa_data:
            county_rn_supply = self.hrsa_data.get("rn_graduates_per_year", 0)
            nhsc_matches = self.hrsa_data.get("nhsc_matches_annual", 0)
            pipeline_boost += county_rn_supply * 0.10 + nhsc_matches  # 10% retention estimate

        current_fte = total_fte
        year_outcomes: List[Dict] = []

        for yr in range(1, PIPELINE_HORIZON_YRS + 1):
            attrition = current_fte * RURAL_ATTRITION_RATE
            recruitment = attrition * NATURAL_RECRUITMENT_FACTOR + pipeline_boost
            current_fte = max(0.0, current_fte - attrition + recruitment)
            adequate = current_fte >= min_adequate
            year_outcomes.append({
                "year": yr,
                "projected_fte": round(current_fte, 1),
                "adequate": adequate,
            })

        adequate_years = sum(1 for yo in year_outcomes if yo["adequate"])
        adequacy_prob = float(adequate_years / PIPELINE_HORIZON_YRS)

        return adequacy_prob, {
            "current_total_fte": round(total_fte, 1),
            "minimum_fte_adequate_threshold": round(min_adequate, 1),
            "annual_attrition_rate": RURAL_ATTRITION_RATE,
            "hrsa_scholar_pipeline_annual": pipeline_boost,
            "year_by_year": year_outcomes,
            "adequate_years_of_5": adequate_years,
            "adequacy_probability": round(adequacy_prob, 4),
        }

    # ─── Composite evaluation ─────────────────────────────────────────────────

    def evaluate(self, x: np.ndarray) -> WorkforceEvaluation:
        """
        Evaluate all four CAHSP Class 4 targets and compute composite WI.

        Args:
            x: Decision variable vector (8-element, same as optimizer)

        Returns:
            WorkforceEvaluation with component scores, WI composite, and detail
        """
        travel_score, travel_detail = self.travel_dependency_score(x)
        tele_score, tele_detail = self.tele_coverage_score(x)
        burnout_idx, burnout_detail = self.burnout_index(x)
        burnout_score = burnout_detail["score"]
        pipeline_score, pipeline_detail = self.pipeline_adequacy_5yr(x)

        wi_score = float((travel_score + tele_score + burnout_score + pipeline_score) / 4.0)

        return WorkforceEvaluation(
            travel_dependency_score=travel_score,
            tele_coverage_score=tele_score,
            burnout_score=burnout_score,
            burnout_index=burnout_idx,
            pipeline_adequacy_5yr=pipeline_score,
            wi_score=wi_score,
            detail={
                "travel": travel_detail,
                "tele_coverage": tele_detail,
                "burnout": burnout_detail,
                "pipeline": pipeline_detail,
            },
        )
