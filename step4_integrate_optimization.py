#!/usr/bin/env python3
"""
STEP 4: Integrate Datasets for Optimization Model

This script integrates the acquired datasets (CMS cost reports, MBQIP quality
data, and CAH designation data) to calibrate and run the optimization model.

Execution Flow:
1. Load all acquired datasets from data/
2. Validate data quality and completeness
3. Calibrate optimization parameters from real data
4. Run population-level optimization analysis
5. Generate actionable recommendations
6. Export results to reports/

Usage:
    python step4_integrate_optimization.py

Output:
    - reports/step4_integration_report.json
    - reports/optimization_results.json
    - reports/calibrated_parameters.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

# Add source to path
sys.path.insert(0, str(BASE_DIR / "src"))


def print_header():
    """Print step header."""
    print("\n" + "=" * 80)
    print(" " * 20 + "CAH TRANSFORMATION ENGINE")
    print(" " * 10 + "STEP 4: INTEGRATE DATASETS FOR OPTIMIZATION")
    print("=" * 80)


def validate_data_availability():
    """Validate that required data files exist."""
    print("\n[*] Validating data availability...")
    
    required_files = [
        DATA_DIR / "cah_designation" / "cah_providers.csv",
        DATA_DIR / "mbqip_quality" / "cms_hospital_compare_data.csv",
        DATA_DIR / "cms_cost_reports" / "2023" / "HOSP10_2023_rpt.csv",
    ]
    
    all_present = True
    for file_path in required_files:
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print(f"  [+] {file_path.name} ({size_kb:.1f} KB)")
        else:
            print(f"  [-] Missing: {file_path}")
            all_present = False
    
    return all_present


def load_and_integrate_data():
    """Load and integrate all datasets."""
    print("\n[*] Loading and integrating datasets...")
    
    from cah_engine.integration.data_loader import CAHDataLoader
    
    loader = CAHDataLoader(DATA_DIR)
    dataset = loader.load_all(year=2023)
    
    print(f"  [+] Loaded {len(dataset.facilities)} CAH facilities")
    print(f"  [+] States covered: {len(dataset.state_counts)}")
    
    # Print data source summaries
    if dataset.designation_summary.total_records > 0:
        print(f"  [+] CAH designation records: {dataset.designation_summary.total_records}")
    
    if dataset.quality_summary.total_records > 0:
        print(f"  [+] Quality measure records: {dataset.quality_summary.total_records}")
    
    if dataset.cost_report_summary.total_records > 0:
        print(f"  [+] Cost report records: {dataset.cost_report_summary.total_records}")
    
    # Report any issues
    all_issues = (
        dataset.designation_summary.issues +
        dataset.quality_summary.issues +
        dataset.cost_report_summary.issues
    )
    if all_issues:
        print(f"\n  [!] Data loading issues:")
        for issue in all_issues[:5]:  # Limit to first 5
            print(f"     - {issue}")
    
    return dataset


def calibrate_parameters(dataset):
    """Calibrate optimization parameters from data."""
    print("\n[*] Calibrating optimization parameters...")
    
    from cah_engine.integration.parameter_estimator import ParameterEstimator
    
    estimator = ParameterEstimator()
    params = estimator.estimate(dataset)
    
    print(f"  [+] Parameters calibrated from {params.total_facilities_analyzed} facilities")
    
    # Print key parameter estimates
    print("\n  Revenue Parameters (alpha):")
    if params.alpha_1:
        print(f"     a1 (per discharge): ${params.alpha_1.value:,.0f} +/- ${params.alpha_1.std_error:,.0f}")
    if params.alpha_2:
        print(f"     a2 (ED visit): ${params.alpha_2.value:,.0f} +/- ${params.alpha_2.std_error:,.0f}")
    
    print("\n  Cost Parameters (beta):")
    if params.beta_1:
        print(f"     b1 (nursing FTE): ${params.beta_1.value:,.0f} +/- ${params.beta_1.std_error:,.0f}")
    if params.beta_3:
        print(f"     b3 (fixed overhead): ${params.beta_3.value/1e6:.1f}M +/- ${params.beta_3.std_error/1e6:.1f}M")
    
    print("\n  Operational Parameters:")
    if params.avg_los:
        print(f"     ALOS: {params.avg_los.value:.1f} days")
    
    return params


def run_optimization(dataset, params):
    """Run population-level optimization."""
    print("\n[*] Running optimization analysis...")
    
    from cah_engine.integration.integrated_optimizer import IntegratedOptimizer
    
    optimizer = IntegratedOptimizer(
        data_dir=DATA_DIR,
        theta=0.6,  # Balance quality and margin
        margin_floor=0.05,  # 5% minimum margin
    )
    
    # Set pre-loaded data
    optimizer.dataset = dataset
    optimizer.calibrated_params = params
    optimizer.calibrate_parameters()  # Initialize core optimizer
    
    # Run optimization on sample (for speed)
    result = optimizer.optimize_population(max_facilities=200)
    
    print(f"\n  Population Analysis:")
    print(f"     Facilities analyzed: {result.facilities_analyzed}")
    print(f"     Facilities at risk: {result.facilities_at_risk}")
    print(f"     Median margin: {result.population_median_margin:.1%}")
    print(f"     Median quality: {result.population_median_quality:.2f}")
    
    if result.total_revenue_opportunity > 0:
        print(f"     Revenue opportunity: ${result.total_revenue_opportunity/1e6:.1f}M")
    
    print(f"\n  Optimization Targets:")
    print(f"     Target margin: {result.target_margin:.1%}")
    print(f"     Target quality: {result.target_quality:.2f}")
    
    return result


def generate_reports(dataset, params, opt_result):
    """Generate output reports."""
    print("\n[*] Generating reports...")
    
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Integration report
    integration_report = {
        "step": 4,
        "name": "Dataset Integration for Optimization",
        "timestamp": datetime.now().isoformat(),
        "status": "COMPLETED",
        "data_summary": {
            "total_cah_facilities": len(dataset.facilities),
            "states_covered": len(dataset.state_counts),
            "top_states": dict(list(sorted(
                dataset.state_counts.items(),
                key=lambda x: x[1],
                reverse=True
            ))[:10]),
        },
        "aggregate_statistics": {
            "median_margin": dataset.median_margin,
            "median_occupancy": dataset.median_occupancy,
            "median_beds": dataset.median_beds,
            "median_ed_visits": dataset.median_ed_visits,
        },
        "optimization_summary": {
            "facilities_analyzed": opt_result.facilities_analyzed,
            "facilities_at_risk": opt_result.facilities_at_risk,
            "at_risk_percentage": (
                opt_result.facilities_at_risk / opt_result.facilities_analyzed * 100
                if opt_result.facilities_analyzed > 0 else 0
            ),
            "target_margin": opt_result.target_margin,
            "target_quality": opt_result.target_quality,
            "total_revenue_opportunity": opt_result.total_revenue_opportunity,
        },
        "recommendations": opt_result.top_recommendations,
        "next_steps": [
            "Review facility-specific recommendations",
            "Prioritize at-risk facilities for intervention",
            "Implement margin improvement strategies",
            "Monitor quality metrics through MBQIP",
        ],
    }
    
    report_path = REPORTS_DIR / "step4_integration_report.json"
    with open(report_path, "w") as f:
        json.dump(integration_report, f, indent=2)
    print(f"  [+] Integration report: {report_path.name}")
    
    # Calibrated parameters
    params_path = REPORTS_DIR / "calibrated_parameters.json"
    with open(params_path, "w") as f:
        json.dump(params.to_dict(), f, indent=2)
    print(f"  [+] Calibrated parameters: {params_path.name}")
    
    # Full optimization results
    opt_path = REPORTS_DIR / "optimization_results.json"
    with open(opt_path, "w") as f:
        json.dump(opt_result.to_dict(), f, indent=2)
    print(f"  [+] Optimization results: {opt_path.name}")
    
    return integration_report


def print_recommendations(opt_result):
    """Print key recommendations."""
    print("\n" + "=" * 80)
    print(" " * 25 + "KEY RECOMMENDATIONS")
    print("=" * 80)
    
    for i, rec in enumerate(opt_result.top_recommendations, 1):
        print(f"\n  {i}. {rec}")
    
    # Top at-risk facilities
    at_risk = [f for f in opt_result.facility_results if f.margin_at_risk][:5]
    if at_risk:
        print("\n\n  [!] TOP AT-RISK FACILITIES:")
        for facility in at_risk:
            print(f"     * {facility.facility_name} ({facility.state})")
            print(f"       Current margin: {facility.current_margin:.1%}")
            if facility.recommended_actions:
                print(f"       Action: {facility.recommended_actions[0]}")


def main():
    """Main execution function."""
    print_header()
    
    start_time = datetime.now()
    print(f"\nStart time: {start_time.strftime('%H:%M:%S')}")
    
    # Step 1: Validate data
    if not validate_data_availability():
        print("\n[ERROR] Required data files missing. Run Steps 1-3 first.")
        print("   Execute: python master_execution_guide.py")
        return False
    
    try:
        # Step 2: Load and integrate
        dataset = load_and_integrate_data()
        
        # Step 3: Calibrate parameters
        params = calibrate_parameters(dataset)
        
        # Step 4: Run optimization
        opt_result = run_optimization(dataset, params)
        
        # Step 5: Generate reports
        generate_reports(dataset, params, opt_result)
        
        # Step 6: Print recommendations
        print_recommendations(opt_result)
        
        # Completion summary
        duration = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print(" " * 25 + "INTEGRATION COMPLETE")
        print("=" * 80)
        print(f"\n  Duration: {duration:.1f} seconds")
        print(f"  Facilities integrated: {len(dataset.facilities)}")
        print(f"  Optimization targets generated")
        print(f"  Reports saved to: {REPORTS_DIR}")
        
        print("\n  [OK] STEP 4 COMPLETED SUCCESSFULLY")
        print("\n" + "=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

