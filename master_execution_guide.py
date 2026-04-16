#!/usr/bin/env python3
"""
CAH DATA ACQUISITION PIPELINE - MASTER EXECUTION GUIDE
Step-by-step execution with progress tracking and validation
"""

import subprocess
import sys
from pathlib import Path
import json
from datetime import datetime
import time

# Configuration - Use the current script's directory as base
BASE_DIR = Path(__file__).parent.resolve()
SCRIPTS_DIR = BASE_DIR  # Scripts are in the same directory
REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"

# Acquisition Pipeline Steps
PIPELINE_STEPS = [
    {
        "step": 1,
        "name": "CMS Cost Reports",
        "script": "step1_download_cms_cost_reports.py",
        "description": "Financial baseline data for profit optimization",
        "estimated_time": "30-45 minutes",
        "estimated_size": "~1.5GB",
        "critical": True
    },
    {
        "step": 2,
        "name": "MBQIP Quality Measures",
        "script": "step2_download_mbqip_quality.py",
        "description": "Quality baseline for benchmark optimization",
        "estimated_time": "10-15 minutes",
        "estimated_size": "~50MB",
        "critical": True
    },
    {
        "step": 3,
        "name": "CAH Designation Data",
        "script": "step3_download_cah_designation.py",
        "description": "Regulatory constraints and CAH identification",
        "estimated_time": "5-10 minutes",
        "estimated_size": "~100MB",
        "critical": True
    },
    {
        "step": 4,
        "name": "Dataset Integration & Optimization",
        "script": "step4_integrate_optimization.py",
        "description": "Integrate datasets and run optimization model",
        "estimated_time": "2-5 minutes",
        "estimated_size": "~10MB (reports)",
        "critical": True
    },
    {
        "step": 5,
        "name": "HRSA Workforce Data",
        "script": "step5_download_hrsa_workforce.py",
        "description": "Workforce supply data for CAHSP Class 4 pipeline adequacy (HRSA AHRF)",
        "estimated_time": "5-10 minutes",
        "estimated_size": "~50MB",
        "critical": False
    }
]

def print_header():
    """Print pipeline header"""
    print("\n" + "="*80)
    print(" " * 15 + "CAH TRANSFORMATION ENGINE")
    print(" " * 10 + "DATA ACQUISITION PIPELINE - MASTER EXECUTION")
    print("="*80)

def print_step_header(step_info):
    """Print step header"""
    print(f"\n{'='*80}")
    print(f"STEP {step_info['step']}: {step_info['name'].upper()}")
    print(f"{'='*80}")
    print(f"Description: {step_info['description']}")
    print(f"Estimated time: {step_info['estimated_time']}")
    print(f"Estimated size: {step_info['estimated_size']}")
    print(f"Critical: {'YES' if step_info['critical'] else 'NO'}")
    print(f"{'='*80}")

def execute_step(step_info):
    """Execute a single pipeline step"""
    print_step_header(step_info)
    
    script_path = SCRIPTS_DIR / step_info['script']
    
    if not script_path.exists():
        print(f"\n  ERROR: Script not found: {script_path}")
        return False
    
    print(f"\n  Executing: {script_path.name}")
    print(f"  Start time: {datetime.now().strftime('%H:%M:%S')}")
    
    start_time = time.time()
    
    try:
        # Execute the script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(BASE_DIR),
            capture_output=False,  # Show output in real-time
            text=True
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n  STEP {step_info['step']} COMPLETED SUCCESSFULLY")
            print(f"  Duration: {duration/60:.1f} minutes")
            return True
        else:
            print(f"\n  STEP {step_info['step']} FAILED")
            print(f"Return code: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"\n  ERROR executing step: {e}")
        import traceback
        traceback.print_exc()
        return False

def validate_pipeline_readiness():
    """Validate that the pipeline is ready to execute"""
    print(f"\n{'='*80}")
    print("PIPELINE READINESS VALIDATION")
    print(f"{'='*80}")
    
    checks = []
    
    # Check 1: Base directory exists
    base_exists = BASE_DIR.exists()
    checks.append(("Base directory exists", base_exists))
    print(f"  Base directory: {BASE_DIR}" if base_exists else f"  Base directory missing")
    
    # Check 2: Scripts directory exists
    scripts_exists = SCRIPTS_DIR.exists()
    checks.append(("Scripts directory exists", scripts_exists))
    print(f"  Scripts directory: {SCRIPTS_DIR}" if scripts_exists else f"  Scripts directory missing")
    
    # Check 3: All step scripts exist
    all_scripts_exist = True
    for step in PIPELINE_STEPS:
        script_path = SCRIPTS_DIR / step['script']
        exists = script_path.exists()
        all_scripts_exist = all_scripts_exist and exists
        if not exists:
            print(f"  Missing script: {step['script']}")
        else:
            print(f"  Script ready: {step['script']}")
    checks.append(("All scripts exist", all_scripts_exist))
    
    # Check 4: Python dependencies
    required_packages = [
        ('requests', 'requests'),
        ('pandas', 'pandas'),
        ('bs4', 'beautifulsoup4'),  # bs4 is the import name for beautifulsoup4
    ]
    packages_installed = True
    print(f"\nChecking Python dependencies...")
    for import_name, pip_name in required_packages:
        try:
            __import__(import_name)
            print(f"  {pip_name} installed")
        except ImportError:
            print(f"  {pip_name} missing - install with: pip install {pip_name}")
            packages_installed = False
    checks.append(("Dependencies installed", packages_installed))
    
    # Overall readiness
    all_ready = all(check[1] for check in checks)
    
    print(f"\n{'='*80}")
    if all_ready:
        print("  PIPELINE READY TO EXECUTE")
    else:
        print("  PIPELINE NOT READY - Fix issues above")
    print(f"{'='*80}\n")
    
    return all_ready

def generate_master_report(execution_results):
    """Generate master execution report"""
    print(f"\n{'='*80}")
    print("MASTER EXECUTION REPORT")
    print(f"{'='*80}")
    
    successful_steps = [step for step, success in execution_results.items() if success]
    failed_steps = [step for step, success in execution_results.items() if not success]
    
    report = {
        "pipeline_execution_timestamp": datetime.now().isoformat(),
        "total_steps": len(execution_results),
        "successful_steps": len(successful_steps),
        "failed_steps": len(failed_steps),
        "step_results": execution_results,
        "critical_datasets_acquired": len([s for s in successful_steps if s <= 4]),
        "workforce_data_acquired": 5 in successful_steps,
        "next_actions": []
    }
    
    if len(successful_steps) >= 3:
        report["status"] = "CRITICAL_DATASETS_ACQUIRED"
        report["next_actions"] = [
            "Validate data quality and completeness",
            "Calculate payer mix from cost reports",
            "Integrate datasets for optimization model",
            "Proceed to mathematical optimization",
            "Run CAHSP scoring (cahsp_score.py) after optimization",
        ]
        if 5 in successful_steps:
            report["next_actions"].append(
                "Load HRSA workforce data into WorkforceOptimizer for grounded Class 4 scoring"
            )
    elif len(successful_steps) > 0:
        report["status"] = "PARTIAL_ACQUISITION"
        report["next_actions"] = [
            f"Retry failed steps: {failed_steps}",
            "Investigate failure causes",
            "Manual download alternatives if needed"
        ]
    else:
        report["status"] = "ACQUISITION_FAILED"
        report["next_actions"] = [
            "Check network connectivity",
            "Verify CMS data availability",
            "Review error logs",
            "Consider manual download process"
        ]
    
    # Save report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "master_execution_report.json"
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"\n  EXECUTION SUMMARY:")
    print(f"   Total steps: {report['total_steps']}")
    print(f"   Successful: {report['successful_steps']}")
    print(f"   Failed: {report['failed_steps']}")
    print(f"   Status: {report['status']}")
    
    if failed_steps:
        print(f"\n  Failed steps: {failed_steps}")
    
    print(f"\n  NEXT ACTIONS:")
    for action in report['next_actions']:
        print(f"   - {action}")
    
    print(f"\n  Report saved to: {report_path}")
    print(f"\n{'='*80}")
    
    return report

def main():
    """Main execution function"""
    print_header()
    
    print(f"\n  PIPELINE OVERVIEW:")
    print(f"   Total steps: {len(PIPELINE_STEPS)}")
    print(f"   Critical datasets: {len([s for s in PIPELINE_STEPS if s['critical']])}")
    total_time = sum([int(s['estimated_time'].split('-')[0]) for s in PIPELINE_STEPS])
    print(f"   Estimated total time: ~{total_time} minutes")
    
    # Validate readiness
    if not validate_pipeline_readiness():
        print(f"\n  Pipeline not ready. Please fix issues above.")
        return
    
    # Confirm execution
    print(f"\n{'='*80}")
    print("READY TO BEGIN DATA ACQUISITION")
    print(f"{'='*80}")
    
    # Auto-proceed (non-interactive mode)
    print("\n[AUTO-MODE] Executing full pipeline...")
    
    # Execute pipeline
    execution_results = {}
    
    for step_info in PIPELINE_STEPS:
        success = execute_step(step_info)
        execution_results[step_info['step']] = success
        
        if not success and step_info['critical']:
            print(f"\n  CRITICAL STEP FAILED")
            # Auto-retry once in non-interactive mode
            print(f"[AUTO-MODE] Retrying step {step_info['step']}...")
            success = execute_step(step_info)
            execution_results[step_info['step']] = success
            
            if not success:
                # Continue to next step in non-interactive mode
                print(f"[AUTO-MODE] Continuing to next step...")
    
    # Generate master report
    generate_master_report(execution_results)
    
    print(f"\n{'='*80}")
    print("PIPELINE EXECUTION COMPLETE")
    print(f"{'='*80}")
    print(f"\nReview reports in: {REPORTS_DIR}")
    print(f"Data stored in: {BASE_DIR / 'data'}")

if __name__ == "__main__":
    main()
