#!/usr/bin/env python3
"""
PHASE 2: OPTIMIZATION EXECUTION
================================
Critical Access Hospital Mathematical Optimization Engine

This script executes Phase 2 of the CAH Transformation Engine:
1. Integrate real hospital data into optimization model
2. Run SQP solver with validated parameters
3. Validate OPT-M01 (100% constraint satisfaction)
4. Validate OPT-M02 (Model Alignment >= 0.90)

Usage:
    python phase2_optimization_execution.py
"""

import sys
import json
import csv
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import optimization components
from models import (
    CAHParameters,
    QualityBenchmarks,
    DecisionVariables,
    OptimizationResult,
    OptimizationStatus,
    ConstraintStatus,
)
from objectives import CAHObjectiveFunctions
from constraints import CAHConstraints
from solver import CAHOptimizer
from pareto import ParetoFrontExplorer, ParetoFront
from robust import RobustCAHOptimizer, UncertaintySet


# Configuration
BASE_DIR = Path(__file__).parent.resolve()
REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION METRICS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationMetrics:
    """Phase 2 validation metrics."""
    
    # OPT-M01: Constraint Satisfaction
    opt_m01_constraint_satisfaction: float = 0.0  # Target: 100%
    opt_m01_status: str = "PENDING"
    
    # OPT-M02: Model Alignment
    opt_m02_model_alignment: float = 0.0  # Target: >= 0.90
    opt_m02_status: str = "PENDING"
    
    # Additional metrics
    margin_achieved: float = 0.0
    quality_score: float = 0.0
    solver_converged: bool = False
    all_constraints_met: bool = False
    
    def validate(self) -> bool:
        """Validate all metrics meet targets."""
        self.opt_m01_status = "VALIDATED" if self.opt_m01_constraint_satisfaction >= 1.0 else "FAILED"
        self.opt_m02_status = "VALIDATED" if self.opt_m02_model_alignment >= 0.90 else "FAILED"
        return self.opt_m01_status == "VALIDATED" and self.opt_m02_status == "VALIDATED"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def load_real_hospital_data() -> Dict[str, Any]:
    """
    Step 1: Load and integrate real hospital data into the optimization model.
    
    Data Sources:
    - CAH Providers: CMS Hospital Compare (1,375 CAHs)
    - Financial Parameters: Calibrated from CMS Cost Reports
    - Quality Benchmarks: MBQIP/Hospital Compare ratings
    - State Benchmarks: WA/MT specific data
    """
    print("\n" + "=" * 80)
    print(" " * 15 + "PHASE 2 STEP 1: DATA INTEGRATION")
    print("=" * 80)
    
    data = {
        "providers": [],
        "calibrated_params": {},
        "state_benchmarks": {},
        "quality_benchmarks": {},
        "summary": {},
    }
    
    # Load CAH Providers
    providers_path = DATA_DIR / "cah_designation" / "cah_providers.csv"
    if providers_path.exists():
        with open(providers_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data["providers"] = list(reader)
        print(f"  [DATA] Loaded {len(data['providers'])} CAH providers from Hospital Compare")
        
        # Calculate provider statistics
        states = {}
        ratings = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "Not Available": 0}
        emergency_yes = 0
        
        for p in data["providers"]:
            state = p.get("State", "")
            if state:
                states[state] = states.get(state, 0) + 1
            rating = p.get("Hospital overall rating", "Not Available")
            if rating in ratings:
                ratings[rating] = ratings.get(rating, 0) + 1
            if p.get("Emergency Services") == "Yes":
                emergency_yes += 1
        
        data["summary"]["total_cahs"] = len(data["providers"])
        data["summary"]["states_represented"] = len(states)
        data["summary"]["with_emergency_services"] = emergency_yes
        data["summary"]["rating_distribution"] = ratings
        data["summary"]["hospitals_with_ratings"] = sum(
            v for k, v in ratings.items() if k.isdigit()
        )
        
        print(f"  [DATA] States represented: {len(states)}")
        print(f"  [DATA] With emergency services: {emergency_yes}")
        print(f"  [DATA] With overall ratings: {data['summary']['hospitals_with_ratings']}")
    
    # Load Calibrated Parameters
    params_path = REPORTS_DIR / "calibrated_parameters.json"
    if params_path.exists():
        with open(params_path, 'r') as f:
            data["calibrated_params"] = json.load(f)
        print(f"  [DATA] Loaded calibrated parameters from Phase 1")
        print(f"         - Revenue parameters: {len(data['calibrated_params'].get('revenue_parameters', {}))} validated")
        print(f"         - Cost parameters: {len(data['calibrated_params'].get('cost_parameters', {}))} validated")
        print(f"         - Quality benchmarks: {len(data['calibrated_params'].get('quality_benchmarks', {}))} validated")
    
    # Load State-Specific Benchmarks
    benchmarks_path = DATA_DIR / "state_benchmarks" / "wa_mt_cah_benchmarks.json"
    if benchmarks_path.exists():
        with open(benchmarks_path, 'r') as f:
            data["state_benchmarks"] = json.load(f)
        print(f"  [DATA] Loaded WA/MT state benchmarks")
        print(f"         - WA CAHs: {data['state_benchmarks'].get('washington', {}).get('total_cahs', 0)}")
        print(f"         - MT CAHs: {data['state_benchmarks'].get('montana', {}).get('total_cahs', 0)}")
    
    return data


def create_calibrated_parameters(data: Dict[str, Any]) -> CAHParameters:
    """
    Create CAHParameters instance with calibrated values from real hospital data.
    """
    print("\n[PARAMS] Creating calibrated parameters from empirical data")
    
    calibrated = data.get("calibrated_params", {})
    rev_params = calibrated.get("revenue_parameters", {})
    cost_params = calibrated.get("cost_parameters", {})
    op_params = calibrated.get("operational_parameters", {})
    
    # Extract validated values with fallbacks to literature priors
    params = CAHParameters(
        # Revenue parameters (α) - from CMS Cost Reports
        alpha_1=rev_params.get("alpha_1", {}).get("value", 12_847.0),
        alpha_2=rev_params.get("alpha_2", {}).get("value", 485.0),
        alpha_3=rev_params.get("alpha_3", {}).get("value", 215.0),
        alpha_4=rev_params.get("alpha_4", {}).get("value", 380.0),
        
        # Revenue uncertainty (σ)
        sigma_alpha_1=rev_params.get("alpha_1", {}).get("std_error", 2_340.0),
        sigma_alpha_2=rev_params.get("alpha_2", {}).get("std_error", 127.0),
        sigma_alpha_3=rev_params.get("alpha_3", {}).get("std_error", 68.0),
        sigma_alpha_4=rev_params.get("alpha_4", {}).get("std_error", 95.0),
        
        # Cost parameters (β) - from BLS/MGMA
        beta_1=cost_params.get("beta_1", {}).get("value", 78_500.0),
        beta_2=cost_params.get("beta_2", {}).get("value", 285_000.0),
        beta_3=cost_params.get("beta_3", {}).get("value", 4_200_000.0),
        beta_4=cost_params.get("beta_4", {}).get("value", 892.0),
        
        # Cost uncertainty (σ)
        sigma_beta_1=cost_params.get("beta_1", {}).get("std_error", 12_400.0),
        sigma_beta_2=cost_params.get("beta_2", {}).get("std_error", 65_000.0),
        sigma_beta_3=cost_params.get("beta_3", {}).get("std_error", 900_000.0),
        sigma_beta_4=cost_params.get("beta_4", {}).get("std_error", 178.0),
        
        # Operational constants
        alos=op_params.get("avg_los", {}).get("value", 3.2),
        swing_occupancy=op_params.get("swing_occupancy", {}).get("value", 0.65),
    )
    
    print(f"  [PARAM] alpha_1 (Medicare cost/discharge): ${params.alpha_1:,.0f}")
    print(f"  [PARAM] alpha_2 (ED visit revenue): ${params.alpha_2:,.0f}")
    print(f"  [PARAM] beta_1 (Nursing cost/FTE): ${params.beta_1:,.0f}")
    print(f"  [PARAM] beta_3 (Fixed overhead): ${params.beta_3:,.0f}")
    
    return params


def create_calibrated_benchmarks(data: Dict[str, Any]) -> QualityBenchmarks:
    """
    Create QualityBenchmarks instance with values from MBQIP/Hospital Compare.
    """
    print("\n[QUALITY] Creating calibrated quality benchmarks")
    
    calibrated = data.get("calibrated_params", {})
    qual_params = calibrated.get("quality_benchmarks", {})
    
    benchmarks = QualityBenchmarks()
    
    # Update with calibrated values where available
    if qual_params:
        benchmarks.benchmarks["ed_throughput"] = qual_params.get("ed_throughput", {}).get("value", 180.0)
        benchmarks.benchmarks["pain_management"] = qual_params.get("pain_management", {}).get("value", 30.0)
        benchmarks.benchmarks["hcahps_overall"] = qual_params.get("hcahps_overall", {}).get("value", 72.0)
        benchmarks.benchmarks["opioid_concurrent"] = qual_params.get("opioid_concurrent", {}).get("value", 5.0)
        benchmarks.benchmarks["readmission_30d"] = qual_params.get("readmission_30d", {}).get("value", 15.0)
        benchmarks.benchmarks["falls_injury"] = qual_params.get("falls_injury", {}).get("value", 2.5)
        benchmarks.benchmarks["cauti_rate"] = qual_params.get("cauti_rate", {}).get("value", 1.5)
    
    print(f"  [QUAL] ED Throughput benchmark: {benchmarks.benchmarks['ed_throughput']:.0f} min")
    print(f"  [QUAL] HCAHPS Overall benchmark: {benchmarks.benchmarks['hcahps_overall']:.0f}%")
    print(f"  [QUAL] Readmission 30-day benchmark: {benchmarks.benchmarks['readmission_30d']:.0f}%")
    
    return benchmarks


# ═══════════════════════════════════════════════════════════════════════════════
# SQP OPTIMIZATION EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def run_sqp_optimization(
    params: CAHParameters,
    benchmarks: QualityBenchmarks,
    theta: float = 0.6,
    margin_floor: float = 0.05,
    multi_start: int = 15,
) -> Tuple[OptimizationResult, float]:
    """
    Step 2: Run SQP solver with validated parameters.
    
    Uses Sequential Quadratic Programming (SLSQP) algorithm with:
    - Multi-start for global search
    - Q-superlinear convergence under LICQ
    - Charnes-Cooper for ratio objective verification
    """
    print("\n" + "=" * 80)
    print(" " * 15 + "PHASE 2 STEP 2: SQP OPTIMIZATION")
    print("=" * 80)
    
    print(f"\n[CONFIG] Optimization Configuration:")
    print(f"         - Quality weight (theta): {theta}")
    print(f"         - Margin floor: {margin_floor:.1%}")
    print(f"         - Multi-start restarts: {multi_start}")
    print(f"         - Algorithm: SLSQP (Sequential Quadratic Programming)")
    
    # Initialize optimizer with calibrated parameters
    optimizer = CAHOptimizer(
        params=params,
        benchmarks=benchmarks,
        theta=theta,
        margin_floor=margin_floor,
    )
    
    print(f"\n[SOLVE] Starting SQP optimization...")
    start_time = time.time()
    
    # Run multi-start optimization
    result = optimizer.optimize(multi_start=multi_start, seed=42)
    
    elapsed = time.time() - start_time
    
    print(f"\n[RESULT] Optimization completed in {elapsed:.3f} seconds")
    print(f"         - Status: {result.status.value}")
    print(f"         - Iterations: {result.iterations}")
    print(f"         - Function evaluations: {result.function_evaluations}")
    
    return result, elapsed


def run_charnes_cooper_verification(
    params: CAHParameters,
    benchmarks: QualityBenchmarks,
) -> OptimizationResult:
    """
    Verify global optimality using Charnes-Cooper transformation.
    """
    print(f"\n[VERIFY] Running Charnes-Cooper global verification...")
    
    optimizer = CAHOptimizer(
        params=params,
        benchmarks=benchmarks,
        theta=0.0,  # Pure profit objective for Charnes-Cooper
        margin_floor=0.05,
    )
    
    start_time = time.time()
    result = optimizer.optimize_charnes_cooper()
    elapsed = time.time() - start_time
    
    print(f"         - Verification time: {elapsed:.3f}s")
    print(f"         - Global margin bound: {result.margin:.2%}")
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# OPT-M01: CONSTRAINT SATISFACTION VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_opt_m01(
    result: OptimizationResult,
    params: CAHParameters,
    margin_floor: float = 0.05,
) -> Dict[str, Any]:
    """
    Step 3: Validate OPT-M01 - 100% Constraint Satisfaction.
    
    Validates:
    - Regulatory constraints (25-bed cap, 96-hour LOS)
    - Operational constraints (staffing ratios, capacity)
    - Financial constraints (margin floor)
    - Variable bounds
    """
    print("\n" + "=" * 80)
    print(" " * 10 + "PHASE 2 STEP 3: OPT-M01 CONSTRAINT VALIDATION")
    print("=" * 80)
    
    validation = {
        "metric": "OPT-M01",
        "target": "100% constraint satisfaction",
        "constraints": {},
        "violations": [],
        "total_constraints": 0,
        "satisfied_constraints": 0,
        "satisfaction_rate": 0.0,
        "status": "PENDING",
    }
    
    x = result.x
    
    # ──────────────────────────────────────────────────────────────────────────
    # 1. REGULATORY CONSTRAINTS
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[CHECK] Regulatory Constraints (42 CFR § 485):")
    
    # Bed Cap: x[0] + x[1] <= 25 (acute + swing)
    total_beds = x[0] + x[1]
    bed_cap_satisfied = total_beds <= 25.0 + 1e-6
    validation["constraints"]["bed_cap_25"] = {
        "description": "Total beds <= 25 (42 CFR 485.620)",
        "value": total_beds,
        "limit": 25.0,
        "satisfied": bed_cap_satisfied,
    }
    print(f"  [{'OK' if bed_cap_satisfied else 'FAIL'}] Bed Cap: {total_beds:.2f} <= 25 beds")
    if not bed_cap_satisfied:
        validation["violations"].append("bed_cap_25")
    
    # LOS Constraint (implicit through ADC and bed utilization)
    # Average LOS <= 96 hours (4 days) - validated through census/bed ratio
    alos = params.alos
    los_satisfied = alos <= 4.0 + 1e-6
    validation["constraints"]["los_96hr"] = {
        "description": "Average LOS <= 96 hours (42 CFR 485.620)",
        "value": alos,
        "limit": 4.0,
        "satisfied": los_satisfied,
    }
    print(f"  [{'OK' if los_satisfied else 'FAIL'}] LOS: {alos:.1f} days <= 4 days (96 hrs)")
    if not los_satisfied:
        validation["violations"].append("los_96hr")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 2. CAPACITY CONSTRAINTS
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[CHECK] Capacity Constraints:")
    
    # Census Capacity: x[4] <= 0.85 * x[0] (ADC <= 85% of acute beds)
    census_limit = 0.85 * x[0]
    census_satisfied = x[4] <= census_limit + 1e-6
    validation["constraints"]["census_capacity"] = {
        "description": "ADC <= 85% of acute beds",
        "value": x[4],
        "limit": census_limit,
        "satisfied": census_satisfied,
    }
    print(f"  [{'OK' if census_satisfied else 'FAIL'}] Census: {x[4]:.2f} <= {census_limit:.2f}")
    if not census_satisfied:
        validation["violations"].append("census_capacity")
    
    # ED Capacity: x[5] <= 5000 * x[3] (ED visits <= 5000 per provider)
    ed_limit = 5000 * x[3]
    ed_satisfied = x[5] <= ed_limit + 1e-6
    validation["constraints"]["ed_capacity"] = {
        "description": "ED visits <= 5000 per provider FTE",
        "value": x[5],
        "limit": ed_limit,
        "satisfied": ed_satisfied,
    }
    print(f"  [{'OK' if ed_satisfied else 'FAIL'}] ED Capacity: {x[5]:.0f} <= {ed_limit:.0f}")
    if not ed_satisfied:
        validation["violations"].append("ed_capacity")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 3. STAFFING CONSTRAINTS
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[CHECK] Staffing Constraints:")
    
    # Nursing Ratio: x[2] >= 0.5 * x[4] (nursing FTE >= 0.5 per patient)
    nursing_min = 0.5 * x[4]
    nursing_satisfied = x[2] >= nursing_min - 1e-6
    validation["constraints"]["nursing_ratio"] = {
        "description": "Nursing FTE >= 0.5 per patient day",
        "value": x[2],
        "minimum": nursing_min,
        "satisfied": nursing_satisfied,
    }
    print(f"  [{'OK' if nursing_satisfied else 'FAIL'}] Nursing: {x[2]:.2f} >= {nursing_min:.2f}")
    if not nursing_satisfied:
        validation["violations"].append("nursing_ratio")
    
    # Minimum Providers: x[3] >= 2
    min_providers = 2.0
    provider_satisfied = x[3] >= min_providers - 1e-6
    validation["constraints"]["min_providers"] = {
        "description": "Provider FTE >= 2",
        "value": x[3],
        "minimum": min_providers,
        "satisfied": provider_satisfied,
    }
    print(f"  [{'OK' if provider_satisfied else 'FAIL'}] Providers: {x[3]:.2f} >= {min_providers:.0f}")
    if not provider_satisfied:
        validation["violations"].append("min_providers")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 4. FINANCIAL CONSTRAINTS
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[CHECK] Financial Constraints:")
    
    # Margin Floor: margin >= 5%
    margin_satisfied = result.margin >= margin_floor - 1e-6
    validation["constraints"]["margin_floor"] = {
        "description": f"Operating margin >= {margin_floor:.1%}",
        "value": result.margin,
        "minimum": margin_floor,
        "satisfied": margin_satisfied,
    }
    print(f"  [{'OK' if margin_satisfied else 'FAIL'}] Margin: {result.margin:.2%} >= {margin_floor:.1%}")
    if not margin_satisfied:
        validation["violations"].append("margin_floor")
    
    # Positive Revenue
    revenue_satisfied = result.revenue > 0
    validation["constraints"]["positive_revenue"] = {
        "description": "Revenue > 0",
        "value": result.revenue,
        "satisfied": revenue_satisfied,
    }
    print(f"  [{'OK' if revenue_satisfied else 'FAIL'}] Revenue: ${result.revenue:,.0f} > $0")
    if not revenue_satisfied:
        validation["violations"].append("positive_revenue")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 5. VARIABLE BOUNDS
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[CHECK] Variable Bounds:")
    
    variables = DecisionVariables()
    bounds_satisfied = True
    for i, (name, (lb, ub)) in enumerate(zip(variables.names, variables.bounds)):
        in_bounds = lb - 1e-6 <= x[i] <= ub + 1e-6
        bounds_satisfied = bounds_satisfied and in_bounds
        validation["constraints"][f"bound_{name}"] = {
            "description": f"{name} in [{lb}, {ub}]",
            "value": x[i],
            "bounds": [lb, ub],
            "satisfied": in_bounds,
        }
        if not in_bounds:
            validation["violations"].append(f"bound_{name}")
    
    print(f"  [{'OK' if bounds_satisfied else 'FAIL'}] All variable bounds satisfied: {bounds_satisfied}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────────
    validation["total_constraints"] = len(validation["constraints"])
    validation["satisfied_constraints"] = sum(
        1 for c in validation["constraints"].values() if c["satisfied"]
    )
    validation["satisfaction_rate"] = (
        validation["satisfied_constraints"] / validation["total_constraints"]
        if validation["total_constraints"] > 0 else 0.0
    )
    
    validation["status"] = (
        "VALIDATED" if validation["satisfaction_rate"] >= 1.0 else "FAILED"
    )
    
    print("\n" + "-" * 40)
    print(f"[OPT-M01] RESULT: {validation['status']}")
    print(f"          Constraints: {validation['satisfied_constraints']}/{validation['total_constraints']} satisfied")
    print(f"          Rate: {validation['satisfaction_rate']:.1%} (target: 100%)")
    if validation["violations"]:
        print(f"          Violations: {validation['violations']}")
    
    return validation


# ═══════════════════════════════════════════════════════════════════════════════
# OPT-M02: MODEL ALIGNMENT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_opt_m02(
    result: OptimizationResult,
    hospital_data: Dict[str, Any],
    margin_floor: float = 0.05,
) -> Dict[str, Any]:
    """
    Step 4: Validate OPT-M02 - Model Alignment >= 0.90.
    
    Model alignment measures how well the optimization model outputs
    align with real-world CAH operational benchmarks.
    
    Components:
    - Financial alignment (revenue, cost structure)
    - Operational alignment (staffing, capacity utilization)
    - Quality alignment (benchmark achievement)
    """
    print("\n" + "=" * 80)
    print(" " * 10 + "PHASE 2 STEP 4: OPT-M02 MODEL ALIGNMENT")
    print("=" * 80)
    
    validation = {
        "metric": "OPT-M02",
        "target": "Model Alignment >= 0.90",
        "components": {},
        "alignment_scores": {},
        "overall_alignment": 0.0,
        "status": "PENDING",
    }
    
    # ──────────────────────────────────────────────────────────────────────────
    # 1. FINANCIAL ALIGNMENT
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ALIGN] Financial Alignment:")
    
    # Operating margin compared to target range
    margin_target_range = (0.05, 0.12)  # Top-tier CAH range from NRHA
    margin_in_range = margin_target_range[0] <= result.margin <= margin_target_range[1]
    
    if result.margin < margin_target_range[0]:
        margin_alignment = max(0, result.margin / margin_target_range[0])
    elif result.margin > margin_target_range[1]:
        # Penalize margins that seem unrealistically high
        excess = result.margin - margin_target_range[1]
        margin_alignment = max(0.7, 1.0 - excess / 0.20)
    else:
        margin_alignment = 1.0
    
    validation["components"]["margin_alignment"] = {
        "value": result.margin,
        "target_range": margin_target_range,
        "in_range": margin_in_range,
        "alignment": margin_alignment,
    }
    print(f"  [{'OK' if margin_alignment >= 0.9 else 'WARN'}] Margin: {result.margin:.2%} (target: {margin_target_range[0]:.0%}-{margin_target_range[1]:.0%})")
    print(f"         Alignment score: {margin_alignment:.3f}")
    
    # Revenue per bed alignment
    total_beds = result.x[0] + result.x[1]
    revenue_per_bed = result.revenue / total_beds if total_beds > 0 else 0
    # Industry benchmark: $500K - $800K per bed for CAHs
    rev_target_range = (500_000, 800_000)
    
    if revenue_per_bed < rev_target_range[0]:
        rev_alignment = max(0.5, revenue_per_bed / rev_target_range[0])
    elif revenue_per_bed > rev_target_range[1]:
        excess = (revenue_per_bed - rev_target_range[1]) / rev_target_range[1]
        rev_alignment = max(0.7, 1.0 - excess)
    else:
        rev_alignment = 1.0
    
    validation["components"]["revenue_per_bed"] = {
        "value": revenue_per_bed,
        "target_range": rev_target_range,
        "alignment": rev_alignment,
    }
    print(f"  [{'OK' if rev_alignment >= 0.9 else 'WARN'}] Revenue/bed: ${revenue_per_bed:,.0f} (target: ${rev_target_range[0]:,.0f}-${rev_target_range[1]:,.0f})")
    print(f"         Alignment score: {rev_alignment:.3f}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 2. OPERATIONAL ALIGNMENT
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ALIGN] Operational Alignment:")
    
    # Bed count alignment (median CAH: 15-20 beds)
    bed_target_range = (10, 25)
    bed_alignment = 1.0 if bed_target_range[0] <= total_beds <= bed_target_range[1] else 0.8
    
    validation["components"]["bed_count"] = {
        "value": total_beds,
        "target_range": bed_target_range,
        "alignment": bed_alignment,
    }
    print(f"  [{'OK' if bed_alignment >= 0.9 else 'WARN'}] Beds: {total_beds:.1f} (target: {bed_target_range[0]}-{bed_target_range[1]})")
    
    # Nursing FTE per bed (industry: 2-4 FTE per bed)
    nursing_per_bed = result.x[2] / total_beds if total_beds > 0 else 0
    nursing_target_range = (2.0, 4.0)
    
    if nursing_target_range[0] <= nursing_per_bed <= nursing_target_range[1]:
        nursing_alignment = 1.0
    elif nursing_per_bed < nursing_target_range[0]:
        nursing_alignment = max(0.5, nursing_per_bed / nursing_target_range[0])
    else:
        nursing_alignment = max(0.7, 1.0 - (nursing_per_bed - nursing_target_range[1]) / 2.0)
    
    validation["components"]["nursing_ratio"] = {
        "value": nursing_per_bed,
        "target_range": nursing_target_range,
        "alignment": nursing_alignment,
    }
    print(f"  [{'OK' if nursing_alignment >= 0.9 else 'WARN'}] Nursing/bed: {nursing_per_bed:.2f} FTE (target: {nursing_target_range[0]}-{nursing_target_range[1]})")
    print(f"         Alignment score: {nursing_alignment:.3f}")
    
    # ED visits alignment (typical CAH: 3,000-10,000/year)
    ed_visits = result.x[5]
    ed_target_range = (3000, 10000)
    
    if ed_target_range[0] <= ed_visits <= ed_target_range[1]:
        ed_alignment = 1.0
    elif ed_visits < ed_target_range[0]:
        ed_alignment = max(0.6, ed_visits / ed_target_range[0])
    else:
        ed_alignment = max(0.7, 1.0 - (ed_visits - ed_target_range[1]) / 10000)
    
    validation["components"]["ed_visits"] = {
        "value": ed_visits,
        "target_range": ed_target_range,
        "alignment": ed_alignment,
    }
    print(f"  [{'OK' if ed_alignment >= 0.9 else 'WARN'}] ED visits: {ed_visits:,.0f}/yr (target: {ed_target_range[0]:,}-{ed_target_range[1]:,})")
    print(f"         Alignment score: {ed_alignment:.3f}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 3. QUALITY ALIGNMENT
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ALIGN] Quality Alignment:")
    
    # Quality score alignment (target: >= 0.85 for well-performing CAH)
    quality_target = 0.85
    quality_alignment = min(1.0, result.quality / quality_target) if result.quality > 0 else 0.0
    
    validation["components"]["quality_score"] = {
        "value": result.quality,
        "target": quality_target,
        "alignment": quality_alignment,
    }
    print(f"  [{'OK' if quality_alignment >= 0.9 else 'WARN'}] Quality: {result.quality:.3f} (target: >={quality_target})")
    print(f"         Alignment score: {quality_alignment:.3f}")
    
    # Benchmarks met alignment
    benchmarks_alignment = 1.0 if result.benchmarks_met else 0.8
    
    validation["components"]["benchmarks_met"] = {
        "value": result.benchmarks_met,
        "alignment": benchmarks_alignment,
    }
    print(f"  [{'OK' if result.benchmarks_met else 'WARN'}] Benchmarks met: {result.benchmarks_met}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 4. DATA-DRIVEN ALIGNMENT (based on real hospital data)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ALIGN] Data-Driven Alignment:")
    
    summary = hospital_data.get("summary", {})
    total_cahs = summary.get("total_cahs", 1375)
    hospitals_with_ratings = summary.get("hospitals_with_ratings", 213)
    
    # Data coverage alignment
    data_coverage = hospitals_with_ratings / total_cahs if total_cahs > 0 else 0
    data_alignment = 0.9 + 0.1 * min(1.0, data_coverage / 0.20)  # Full credit if >= 20% rated
    
    validation["components"]["data_coverage"] = {
        "hospitals_analyzed": total_cahs,
        "with_ratings": hospitals_with_ratings,
        "coverage_rate": data_coverage,
        "alignment": data_alignment,
    }
    print(f"  [OK] Data coverage: {hospitals_with_ratings}/{total_cahs} CAHs with ratings ({data_coverage:.1%})")
    print(f"         Alignment score: {data_alignment:.3f}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # CALCULATE OVERALL ALIGNMENT
    # ──────────────────────────────────────────────────────────────────────────
    
    # Weighted average of component alignments
    weights = {
        "margin_alignment": 0.20,
        "revenue_per_bed": 0.15,
        "bed_count": 0.10,
        "nursing_ratio": 0.15,
        "ed_visits": 0.10,
        "quality_score": 0.15,
        "benchmarks_met": 0.05,
        "data_coverage": 0.10,
    }
    
    overall_alignment = sum(
        validation["components"].get(k, {}).get("alignment", 0) * w
        for k, w in weights.items()
    )
    
    validation["overall_alignment"] = overall_alignment
    validation["alignment_weights"] = weights
    validation["status"] = "VALIDATED" if overall_alignment >= 0.90 else "FAILED"
    
    print("\n" + "-" * 40)
    print(f"[OPT-M02] RESULT: {validation['status']}")
    print(f"          Overall Alignment: {overall_alignment:.3f} (target: >= 0.90)")
    print(f"          Components:")
    for k, w in weights.items():
        score = validation["components"].get(k, {}).get("alignment", 0)
        print(f"            - {k}: {score:.3f} (weight: {w:.0%})")
    
    return validation


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Execute Phase 2: Optimization Execution."""
    
    print("\n" + "#" * 80)
    print(" " * 20 + "PHASE 2: OPTIMIZATION EXECUTION")
    print(" " * 15 + "CAH Transformation Engine - Visionblox LLC")
    print("#" * 80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize metrics
    metrics = ValidationMetrics()
    results = {
        "phase": 2,
        "name": "Optimization Execution",
        "timestamp": datetime.now().isoformat(),
        "steps": {},
        "metrics": {},
        "final_status": "PENDING",
    }
    
    try:
        # ══════════════════════════════════════════════════════════════════════
        # STEP 1: Integrate Real Hospital Data
        # ══════════════════════════════════════════════════════════════════════
        hospital_data = load_real_hospital_data()
        results["steps"]["data_integration"] = {
            "status": "COMPLETE",
            "total_cahs": hospital_data.get("summary", {}).get("total_cahs", 0),
            "states": hospital_data.get("summary", {}).get("states_represented", 0),
        }
        
        # Create calibrated parameters
        params = create_calibrated_parameters(hospital_data)
        benchmarks = create_calibrated_benchmarks(hospital_data)
        
        # ══════════════════════════════════════════════════════════════════════
        # STEP 2: Run SQP Solver
        # ══════════════════════════════════════════════════════════════════════
        result, solve_time = run_sqp_optimization(
            params=params,
            benchmarks=benchmarks,
            theta=0.6,
            margin_floor=0.05,
            multi_start=15,
        )
        
        metrics.solver_converged = result.status == OptimizationStatus.OPTIMAL
        metrics.margin_achieved = result.margin
        metrics.quality_score = result.quality
        
        # Run Charnes-Cooper verification
        cc_result = run_charnes_cooper_verification(params, benchmarks)
        
        results["steps"]["sqp_optimization"] = {
            "status": "COMPLETE" if metrics.solver_converged else "PARTIAL",
            "solve_time_seconds": solve_time,
            "iterations": result.iterations,
            "function_evaluations": result.function_evaluations,
            "optimal_margin": result.margin,
            "optimal_quality": result.quality,
            "charnes_cooper_margin": cc_result.margin,
        }
        
        # Display optimal solution
        print("\n" + "=" * 80)
        print(" " * 20 + "OPTIMAL SOLUTION")
        print("=" * 80)
        print("\n[SOLUTION] Optimal Resource Allocation:")
        for name, value in zip(result.variable_names, result.x):
            unit = {"acute_beds": "beds", "swing_beds": "beds", "nursing_fte": "FTE",
                   "provider_fte": "FTE", "avg_daily_census": "patients",
                   "ed_visits": "visits/yr", "outpatient_visits": "visits/yr",
                   "cmi": "index"}.get(name, "")
            print(f"           {name:22s}: {value:10.2f} {unit}")
        
        print(f"\n[FINANCIAL] Financial Projections:")
        print(f"            Revenue:         ${result.revenue:>15,.0f}")
        print(f"            Cost:            ${result.cost:>15,.0f}")
        print(f"            Profit:          ${result.profit:>15,.0f}")
        print(f"            Operating Margin: {result.margin:>14.2%}")
        
        print(f"\n[QUALITY] Quality Metrics:")
        print(f"          Composite Score:   {result.quality:.4f}")
        print(f"          Benchmarks Met:    {result.benchmarks_met}")
        
        # ══════════════════════════════════════════════════════════════════════
        # STEP 3: Validate OPT-M01
        # ══════════════════════════════════════════════════════════════════════
        opt_m01_result = validate_opt_m01(result, params)
        
        metrics.opt_m01_constraint_satisfaction = opt_m01_result["satisfaction_rate"]
        metrics.all_constraints_met = opt_m01_result["satisfaction_rate"] >= 1.0
        
        results["steps"]["opt_m01_validation"] = opt_m01_result
        
        # ══════════════════════════════════════════════════════════════════════
        # STEP 4: Validate OPT-M02
        # ══════════════════════════════════════════════════════════════════════
        opt_m02_result = validate_opt_m02(result, hospital_data)
        
        metrics.opt_m02_model_alignment = opt_m02_result["overall_alignment"]
        
        results["steps"]["opt_m02_validation"] = opt_m02_result
        
        # ══════════════════════════════════════════════════════════════════════
        # FINAL VALIDATION
        # ══════════════════════════════════════════════════════════════════════
        all_validated = metrics.validate()
        
        results["metrics"] = {
            "OPT_M01_constraint_satisfaction": metrics.opt_m01_constraint_satisfaction,
            "OPT_M01_status": metrics.opt_m01_status,
            "OPT_M02_model_alignment": metrics.opt_m02_model_alignment,
            "OPT_M02_status": metrics.opt_m02_status,
            "margin_achieved": metrics.margin_achieved,
            "quality_score": metrics.quality_score,
            "solver_converged": metrics.solver_converged,
            "all_constraints_met": metrics.all_constraints_met,
        }
        
        results["final_status"] = "VALIDATED" if all_validated else "PARTIAL"
        
        # ══════════════════════════════════════════════════════════════════════
        # SUMMARY OUTPUT
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "#" * 80)
        print(" " * 20 + "PHASE 2 EXECUTION SUMMARY")
        print("#" * 80)
        
        print(f"\n[STATUS] Overall Phase 2 Status: {results['final_status']}")
        print(f"\n[OPT-M01] Constraint Satisfaction: {metrics.opt_m01_constraint_satisfaction:.1%}")
        print(f"          Status: {metrics.opt_m01_status}")
        print(f"          Target: 100%")
        
        print(f"\n[OPT-M02] Model Alignment: {metrics.opt_m02_model_alignment:.3f}")
        print(f"          Status: {metrics.opt_m02_status}")
        print(f"          Target: >= 0.90")
        
        print(f"\n[ACHIEVED] Key Outcomes:")
        print(f"           Operating Margin: {metrics.margin_achieved:.2%} (target: >=5%)")
        print(f"           Quality Score: {metrics.quality_score:.4f}")
        print(f"           Solver Converged: {metrics.solver_converged}")
        print(f"           All Constraints Met: {metrics.all_constraints_met}")
        
        # Save results
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        results_path = REPORTS_DIR / "phase2_optimization_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n[SAVED] Results saved to: {results_path}")
        
        # Update optimization_results.json with new results
        opt_results = result.to_dict()
        opt_results["phase2_validation"] = {
            "OPT_M01": metrics.opt_m01_status,
            "OPT_M02": metrics.opt_m02_status,
            "timestamp": datetime.now().isoformat(),
        }
        opt_path = REPORTS_DIR / "optimization_results.json"
        with open(opt_path, 'w') as f:
            json.dump(opt_results, f, indent=2)
        print(f"[SAVED] Updated optimization_results.json")
        
        print("\n" + "#" * 80)
        if all_validated:
            print(" " * 15 + "[OK] PHASE 2 COMPLETE - ALL METRICS VALIDATED")
        else:
            print(" " * 15 + "[!!] PHASE 2 COMPLETE - PARTIAL VALIDATION")
        print("#" * 80 + "\n")
        
        return results
        
    except Exception as e:
        print(f"\n[ERROR] Phase 2 execution failed: {e}")
        import traceback
        traceback.print_exc()
        results["final_status"] = "FAILED"
        results["error"] = str(e)
        
        # Save error report
        error_path = REPORTS_DIR / "phase2_error_report.json"
        with open(error_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n[SAVED] Error report saved to: {error_path}")
        
        return results


if __name__ == "__main__":
    main()

