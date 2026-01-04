#!/usr/bin/env python3
"""
CAH MATHEMATICAL OPTIMIZATION RUNNER
=====================================
Executes dual-objective optimization for Critical Access Hospitals:
- Objective 1: Achieve >=5% operating margin (profitability)
- Objective 2: Maximize verified quality scores

This script integrates acquired data and runs the optimization engine.

Usage:
    python run_optimization.py [--theta 0.6] [--multi-start 10] [--pareto-points 20]

Output:
    - reports/optimization_results.json
    - reports/pareto_front.json
    - reports/sensitivity_analysis.json
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import argparse

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


def print_header():
    """Print optimization header."""
    print("\n" + "=" * 80)
    print(" " * 20 + "CAH MATHEMATICAL OPTIMIZATION")
    print(" " * 15 + "Dual-Objective: Profitability + Quality")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def load_acquired_data() -> Dict[str, Any]:
    """Load data from acquisition pipeline."""
    print("\n[DATA] LOADING ACQUIRED DATA")
    print("-" * 40)
    
    data = {
        "cost_reports": {},
        "quality_data": {},
        "cah_providers": {},
    }
    
    # Load CMS Cost Report summaries
    for year in [2021, 2022, 2023]:
        summary_path = DATA_DIR / "cms_cost_reports" / str(year) / f"cah_identification_summary_{year}.json"
        if summary_path.exists():
            with open(summary_path, 'r') as f:
                data["cost_reports"][year] = json.load(f)
            print(f"  [OK] CMS Cost Reports {year}: {data['cost_reports'][year].get('total_cahs', 'N/A')} CAHs")
    
    # Load MBQIP quality metadata
    for year in [2021, 2022, 2023]:
        quality_path = DATA_DIR / "mbqip_quality" / f"mbqip_report_{year}_metadata.json"
        if quality_path.exists():
            with open(quality_path, 'r') as f:
                data["quality_data"][year] = json.load(f)
            print(f"  [OK] MBQIP Quality {year}: Loaded")
    
    # Load CAH provider list
    cah_providers_path = DATA_DIR / "cah_designation" / "cah_providers.csv"
    if cah_providers_path.exists():
        import csv
        with open(cah_providers_path, 'r') as f:
            reader = csv.DictReader(f)
            providers = list(reader)
            data["cah_providers"]["count"] = len(providers)
            data["cah_providers"]["sample"] = providers[:5] if providers else []
        print(f"  [OK] CAH Providers: {data['cah_providers']['count']} hospitals")
    
    # Load regulatory constraints
    constraints_path = DATA_DIR / "cah_designation" / "cah_regulatory_constraints.json"
    if constraints_path.exists():
        with open(constraints_path, 'r') as f:
            data["regulatory_constraints"] = json.load(f)
        print(f"  [OK] Regulatory Constraints: Loaded")
    
    return data


def run_standard_optimization(
    theta: float = 0.6,
    margin_floor: float = 0.05,
    multi_start: int = 10,
) -> OptimizationResult:
    """Run standard weighted-sum optimization."""
    print(f"\n[OPT] RUNNING STANDARD OPTIMIZATION")
    print("-" * 40)
    print(f"  Quality weight (theta): {theta}")
    print(f"  Margin floor: {margin_floor:.1%}")
    print(f"  Multi-start restarts: {multi_start}")
    
    optimizer = CAHOptimizer(
        theta=theta,
        margin_floor=margin_floor,
    )
    
    start_time = time.time()
    result = optimizer.optimize(multi_start=multi_start, seed=42)
    elapsed = time.time() - start_time
    
    print(f"\n  [TIME] Optimization completed in {elapsed:.2f} seconds")
    print(f"  [STATUS] Status: {result.status.value}")
    
    return result


def run_pareto_exploration(n_points: int = 20) -> ParetoFront:
    """Generate complete Pareto front."""
    print(f"\n[PARETO] GENERATING PARETO FRONT")
    print("-" * 40)
    print(f"  Points to generate: {n_points}")
    
    explorer = ParetoFrontExplorer()
    
    start_time = time.time()
    front = explorer.explore(n_points=n_points, seed=42)
    elapsed = time.time() - start_time
    
    print(f"\n  [TIME] Pareto exploration completed in {elapsed:.2f} seconds")
    print(f"  [FOUND] Found {len(front.points)} Pareto optimal solutions")
    
    if front.points:
        ideal = front.get_ideal_point()
        nadir = front.get_nadir_point()
        print(f"\n  Ideal point: Margin={ideal[0]:.2%}, Quality={ideal[1]:.3f}")
        print(f"  Nadir point: Margin={nadir[0]:.2%}, Quality={nadir[1]:.3f}")
    
    return front


def run_robust_optimization(gamma: float = 3.0) -> OptimizationResult:
    """Run robust optimization with uncertainty handling."""
    print(f"\n[ROBUST] RUNNING ROBUST OPTIMIZATION")
    print("-" * 40)
    
    uncertainty = UncertaintySet(gamma=gamma)
    print(f"  Uncertainty budget (Gamma): {gamma}")
    print(f"  P(violation) bound: {uncertainty.violation_probability_bound():.2%}")
    
    optimizer = RobustCAHOptimizer(uncertainty_set=uncertainty)
    
    start_time = time.time()
    result = optimizer.optimize(multi_start=5)
    elapsed = time.time() - start_time
    
    print(f"\n  [TIME] Robust optimization completed in {elapsed:.2f} seconds")
    print(f"  [STATUS] Status: {result.status.value}")
    
    return result


def run_sensitivity_analysis(
    optimizer: CAHOptimizer,
    x: np.ndarray,
) -> Dict[str, Dict[str, float]]:
    """Run sensitivity analysis at optimal solution."""
    print(f"\n[SENS] RUNNING SENSITIVITY ANALYSIS")
    print("-" * 40)
    
    sensitivities = optimizer.sensitivity_analysis(x)
    
    print("\n  Variable Sensitivities (dMargin/dx):")
    for var_name, sens in sensitivities.items():
        print(f"    {var_name:20s}: {sens['dMargin_dx']:+.6f}")
    
    return sensitivities


def run_monte_carlo_analysis(
    optimizer: CAHOptimizer,
    x: np.ndarray,
    n_simulations: int = 10000,
) -> Dict:
    """Run Monte Carlo uncertainty quantification."""
    print(f"\n[MC] RUNNING MONTE CARLO ANALYSIS")
    print("-" * 40)
    print(f"  Simulations: {n_simulations:,}")
    
    start_time = time.time()
    mc_result = optimizer.monte_carlo_analysis(x, n_simulations=n_simulations, seed=42)
    elapsed = time.time() - start_time
    
    print(f"\n  [TIME] Monte Carlo completed in {elapsed:.2f} seconds")
    print(f"\n  Margin Distribution:")
    print(f"    Mean: {mc_result['margin']['mean']:.2%}")
    print(f"    Std:  {mc_result['margin']['std']:.2%}")
    print(f"    90% CI: [{mc_result['margin']['ci_5']:.2%}, {mc_result['margin']['ci_95']:.2%}]")
    print(f"    P(>=5%% margin): {mc_result['margin']['p_target_achieved']:.1%}")
    
    return mc_result


def format_result_summary(result: OptimizationResult) -> str:
    """Format optimization result for display."""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append(" " * 25 + "OPTIMIZATION RESULTS")
    lines.append("=" * 80)
    
    lines.append("\n[ALLOCATION] OPTIMAL RESOURCE ALLOCATION:")
    lines.append("-" * 40)
    for name, value in zip(result.variable_names, result.x):
        unit = get_variable_unit(name)
        lines.append(f"  {name:22s}: {value:10.2f} {unit}")
    
    lines.append("\n[FINANCIALS] FINANCIAL PROJECTIONS:")
    lines.append("-" * 40)
    lines.append(f"  Revenue:           ${result.revenue:>15,.0f}")
    lines.append(f"  Cost:              ${result.cost:>15,.0f}")
    lines.append(f"  Profit:            ${result.profit:>15,.0f}")
    lines.append(f"  Operating Margin:  {result.margin:>15.2%}")
    
    lines.append("\n[QUALITY] QUALITY METRICS:")
    lines.append("-" * 40)
    lines.append(f"  Composite Score:   {result.quality:>15.3f}")
    lines.append(f"  Benchmarks Met:    {result.benchmarks_met}")
    
    if result.quality_scores:
        lines.append("\n  Individual Scores:")
        for measure, score in result.quality_scores.items():
            lines.append(f"    {measure:20s}: {score:>8.2f}")
    
    lines.append("\n[CONSTRAINTS] CONSTRAINT STATUS:")
    lines.append("-" * 40)
    lines.append(f"  All Satisfied: {result.constraints_satisfied}")
    for name, status in result.constraint_status.items():
        lines.append(f"    {name:20s}: {status.value}")
    
    lines.append("\n[SOLVER] SOLVER DIAGNOSTICS:")
    lines.append("-" * 40)
    lines.append(f"  Status:             {result.status.value}")
    lines.append(f"  Iterations:         {result.iterations}")
    lines.append(f"  Function Evals:     {result.function_evaluations}")
    lines.append(f"  Objective Value:    {result.objective_value:.6f}")
    
    return "\n".join(lines)


def get_variable_unit(name: str) -> str:
    """Get unit for variable name."""
    units = {
        "acute_beds": "beds",
        "swing_beds": "beds",
        "nursing_fte": "FTE",
        "provider_fte": "FTE",
        "avg_daily_census": "patients",
        "ed_visits": "visits/yr",
        "outpatient_visits": "visits/yr",
        "cmi": "index",
    }
    return units.get(name, "")


def save_results(
    result: OptimizationResult,
    pareto_front: ParetoFront,
    sensitivities: Dict,
    mc_result: Dict,
    robust_result: OptimizationResult,
):
    """Save all results to files."""
    print("\n[SAVE] SAVING RESULTS")
    print("-" * 40)
    
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Main optimization results
    result_dict = result.to_dict()
    result_dict["optimization_timestamp"] = datetime.now().isoformat()
    result_path = REPORTS_DIR / "optimization_results.json"
    with open(result_path, 'w') as f:
        json.dump(result_dict, f, indent=2)
    print(f"  [OK] Optimization results: {result_path}")
    
    # Pareto front
    pareto_dict = {
        "points": [
            {
                "margin": p.margin,
                "quality": p.quality,
                "epsilon": p.epsilon,
                "x": p.x.tolist(),
            }
            for p in pareto_front.points
        ],
        "ideal_point": pareto_front.get_ideal_point(),
        "nadir_point": pareto_front.get_nadir_point(),
        "n_pareto_optimal": len(pareto_front.points),
    }
    pareto_path = REPORTS_DIR / "pareto_front.json"
    with open(pareto_path, 'w') as f:
        json.dump(pareto_dict, f, indent=2)
    print(f"  [OK] Pareto front: {pareto_path}")
    
    # Sensitivity analysis
    sens_path = REPORTS_DIR / "sensitivity_analysis.json"
    with open(sens_path, 'w') as f:
        json.dump(sensitivities, f, indent=2)
    print(f"  [OK] Sensitivity analysis: {sens_path}")
    
    # Monte Carlo results
    mc_path = REPORTS_DIR / "monte_carlo_results.json"
    with open(mc_path, 'w') as f:
        json.dump(mc_result, f, indent=2)
    print(f"  [OK] Monte Carlo results: {mc_path}")
    
    # Robust optimization results
    robust_dict = robust_result.to_dict()
    robust_dict["robust_timestamp"] = datetime.now().isoformat()
    robust_path = REPORTS_DIR / "robust_optimization_results.json"
    with open(robust_path, 'w') as f:
        json.dump(robust_dict, f, indent=2)
    print(f"  [OK] Robust optimization: {robust_path}")
    
    # Summary report
    summary = generate_summary_report(result, pareto_front, mc_result, robust_result)
    summary_path = REPORTS_DIR / "optimization_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"  [OK] Summary report: {summary_path}")


def generate_summary_report(
    result: OptimizationResult,
    pareto_front: ParetoFront,
    mc_result: Dict,
    robust_result: OptimizationResult,
) -> Dict:
    """Generate executive summary report."""
    return {
        "executive_summary": {
            "optimization_status": result.status.value,
            "target_margin_achieved": bool(result.margin >= 0.05),
            "quality_benchmarks_met": bool(result.benchmarks_met),
            "robust_solution_available": bool(robust_result.status.value != "infeasible"),
        },
        "optimal_solution": {
            "operating_margin": float(result.margin),
            "operating_margin_percent": float(result.margin * 100),
            "quality_score": float(result.quality),
            "annual_revenue": float(result.revenue),
            "annual_profit": float(result.profit),
        },
        "resource_allocation": {
            "acute_beds": float(result.x[0]),
            "swing_beds": float(result.x[1]),
            "total_beds": float(result.x[0] + result.x[1]),
            "nursing_fte": float(result.x[2]),
            "provider_fte": float(result.x[3]),
            "expected_daily_census": float(result.x[4]),
            "annual_ed_visits": float(result.x[5]),
            "annual_outpatient_visits": float(result.x[6]),
            "case_mix_index": float(result.x[7]),
        },
        "uncertainty_analysis": {
            "margin_90_ci_lower": float(mc_result["margin"]["ci_5"]),
            "margin_90_ci_upper": float(mc_result["margin"]["ci_95"]),
            "probability_target_achieved": float(mc_result["margin"]["p_target_achieved"]),
        },
        "pareto_analysis": {
            "n_pareto_optimal_solutions": len(pareto_front.points),
            "margin_range": [float(pareto_front.get_nadir_point()[0]), float(pareto_front.get_ideal_point()[0])],
            "quality_range": [float(pareto_front.get_nadir_point()[1]), float(pareto_front.get_ideal_point()[1])],
        },
        "recommendations": generate_recommendations(result, mc_result),
        "timestamp": datetime.now().isoformat(),
    }


def generate_recommendations(result: OptimizationResult, mc_result: Dict) -> list:
    """Generate actionable recommendations based on results."""
    recommendations = []
    
    # Margin assessment
    if result.margin >= 0.08:
        recommendations.append({
            "area": "Financial",
            "priority": "Low",
            "recommendation": f"Operating margin of {result.margin:.1%} exceeds 5% target with comfortable buffer.",
            "action": "Consider reinvesting excess margin in quality improvement initiatives.",
        })
    elif result.margin >= 0.05:
        recommendations.append({
            "area": "Financial",
            "priority": "Medium",
            "recommendation": f"Operating margin of {result.margin:.1%} meets 5% target but with limited buffer.",
            "action": "Monitor revenue streams closely and consider contingency planning.",
        })
    else:
        recommendations.append({
            "area": "Financial",
            "priority": "High",
            "recommendation": f"Operating margin of {result.margin:.1%} is below 5% target.",
            "action": "Implement immediate cost reduction or revenue enhancement strategies.",
        })
    
    # Quality assessment
    if result.quality >= 0.9:
        recommendations.append({
            "area": "Quality",
            "priority": "Low",
            "recommendation": f"Quality score of {result.quality:.3f} indicates excellent performance.",
            "action": "Maintain current staffing and protocols.",
        })
    elif result.quality >= 0.7:
        recommendations.append({
            "area": "Quality",
            "priority": "Medium",
            "recommendation": f"Quality score of {result.quality:.3f} meets MBQIP standards.",
            "action": "Target specific measures for improvement.",
        })
    else:
        recommendations.append({
            "area": "Quality",
            "priority": "High",
            "recommendation": f"Quality score of {result.quality:.3f} needs improvement.",
            "action": "Prioritize staffing increases and quality improvement programs.",
        })
    
    # Uncertainty assessment
    if mc_result["margin"]["p_target_achieved"] >= 0.95:
        recommendations.append({
            "area": "Risk Management",
            "priority": "Low",
            "recommendation": f"95%+ probability of achieving target margin under uncertainty.",
            "action": "Solution is robust to parameter variations.",
        })
    elif mc_result["margin"]["p_target_achieved"] >= 0.80:
        recommendations.append({
            "area": "Risk Management",
            "priority": "Medium",
            "recommendation": f"{mc_result['margin']['p_target_achieved']:.0%} probability of achieving target.",
            "action": "Consider conservative budgeting or robust solution.",
        })
    else:
        recommendations.append({
            "area": "Risk Management",
            "priority": "High",
            "recommendation": f"Only {mc_result['margin']['p_target_achieved']:.0%} probability of achieving target.",
            "action": "Use robust optimization solution or increase safety margins.",
        })
    
    # Bed utilization
    total_beds = result.x[0] + result.x[1]
    if total_beds >= 23:
        recommendations.append({
            "area": "Capacity",
            "priority": "Medium",
            "recommendation": f"Operating near 25-bed CAH cap ({total_beds:.0f} beds).",
            "action": "Optimize swing bed allocation for flexibility.",
        })
    
    return recommendations


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="CAH Mathematical Optimization")
    parser.add_argument("--theta", type=float, default=0.6, help="Quality weight (0-1)")
    parser.add_argument("--multi-start", type=int, default=10, help="Multi-start restarts")
    parser.add_argument("--pareto-points", type=int, default=20, help="Pareto front points")
    parser.add_argument("--mc-simulations", type=int, default=10000, help="Monte Carlo simulations")
    parser.add_argument("--robust-gamma", type=float, default=3.0, help="Robust uncertainty budget")
    args = parser.parse_args()
    
    print_header()
    
    # Step 1: Load acquired data
    acquired_data = load_acquired_data()
    
    # Step 2: Run standard optimization
    optimizer = CAHOptimizer(theta=args.theta, margin_floor=0.05)
    result = run_standard_optimization(
        theta=args.theta,
        margin_floor=0.05,
        multi_start=args.multi_start,
    )
    
    # Display results
    print(format_result_summary(result))
    
    # Step 3: Generate Pareto front
    pareto_front = run_pareto_exploration(n_points=args.pareto_points)
    
    # Step 4: Sensitivity analysis
    sensitivities = run_sensitivity_analysis(optimizer, result.x)
    
    # Step 5: Monte Carlo uncertainty quantification
    mc_result = run_monte_carlo_analysis(
        optimizer,
        result.x,
        n_simulations=args.mc_simulations,
    )
    
    # Step 6: Robust optimization
    robust_result = run_robust_optimization(gamma=args.robust_gamma)
    
    # Step 7: Save all results
    save_results(result, pareto_front, sensitivities, mc_result, robust_result)
    
    # Final summary
    print("\n" + "=" * 80)
    print(" " * 25 + "OPTIMIZATION COMPLETE")
    print("=" * 80)
    print(f"\n[FINAL] FINAL STATUS:")
    print(f"   Operating Margin: {result.margin:.2%} {'[OK]' if result.margin >= 0.05 else '[FAIL]'} (target: >=5%)")
    print(f"   Quality Score: {result.quality:.3f}")
    print(f"   Constraints Satisfied: {result.constraints_satisfied}")
    print(f"   Pareto Solutions: {len(pareto_front.points)}")
    print(f"   P(Target Achieved): {mc_result['margin']['p_target_achieved']:.1%}")
    
    print(f"\n[SAVED] Results saved to: {REPORTS_DIR}")
    print("\n[NEXT] NEXT STEPS:")
    print("   1. Review optimization_summary.json for recommendations")
    print("   2. Examine Pareto front for alternative solutions")
    print("   3. Consider robust solution if uncertainty is high")
    print("   4. Validate results with domain experts")
    print("=" * 80 + "\n")
    
    return result


if __name__ == "__main__":
    main()

