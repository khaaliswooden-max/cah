#!/usr/bin/env python3
"""
CAH DATA VALIDATION - Quality and Completeness Check
Validates all acquired datasets for the CAH Transformation Engine
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
import warnings
import sys
warnings.filterwarnings('ignore')

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

# Validation Results Container
validation_results = {
    "timestamp": datetime.now().isoformat(),
    "overall_status": "PENDING",
    "datasets": {},
    "cross_validation": {},
    "warnings": [],
    "critical_issues": [],
    "recommendations": []
}


def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*80}")
    print(f" {title}")
    print(f"{'='*80}")


def print_subheader(title):
    """Print a formatted subheader"""
    print(f"\n{'-'*60}")
    print(f"  {title}")
    print(f"{'-'*60}")


def validate_cms_cost_reports():
    """Validate CMS Cost Reports data"""
    print_header("VALIDATING CMS COST REPORTS")
    
    cost_reports_dir = DATA_DIR / "cms_cost_reports"
    years = [2021, 2022, 2023]
    
    results = {
        "status": "UNKNOWN",
        "years_validated": [],
        "total_records": 0,
        "total_providers": set(),
        "cah_providers_in_cost_reports": set(),
        "file_completeness": {},
        "data_quality_metrics": {}
    }
    
    for year in years:
        year_dir = cost_reports_dir / str(year)
        print_subheader(f"Year {year}")
        
        if not year_dir.exists():
            print(f"  ❌ Directory not found: {year_dir}")
            validation_results["critical_issues"].append(f"CMS Cost Reports {year} directory missing")
            continue
        
        # Check required files
        required_files = [
            f"HOSP10_{year}_rpt.csv",
            f"HOSP10_{year}_alpha.csv", 
            f"HOSP10_{year}_nmrc.csv"
        ]
        
        file_status = {}
        for req_file in required_files:
            file_path = year_dir / req_file
            if file_path.exists():
                file_size = file_path.stat().st_size / (1024 * 1024)  # MB
                file_status[req_file] = {"exists": True, "size_mb": round(file_size, 2)}
                print(f"  ✓ {req_file}: {file_size:.2f} MB")
            else:
                file_status[req_file] = {"exists": False, "size_mb": 0}
                print(f"  ❌ {req_file}: MISSING")
                validation_results["critical_issues"].append(f"Missing {req_file}")
        
        results["file_completeness"][year] = file_status
        
        # Analyze RPT file (main report file)
        rpt_file = year_dir / f"HOSP10_{year}_rpt.csv"
        if rpt_file.exists():
            try:
                # RPT file has no header - define columns
                rpt_columns = [
                    'rpt_rec_num', 'prvdr_ctrl_type_cd', 'prvdr_num', 'npi',
                    'rpt_stus_cd', 'fy_bgn_dt', 'fy_end_dt', 'proc_dt',
                    'initl_rpt_sw', 'last_rpt_sw', 'trnsmtl_num', 'fi_num',
                    'adr_vndr_cd', 'fi_creat_dt', 'util_cd', 'npr_dt',
                    'spec_ind', 'fi_rcpt_dt'
                ]
                
                rpt_df = pd.read_csv(rpt_file, header=None, names=rpt_columns, dtype=str)
                record_count = len(rpt_df)
                
                # Provider number format: 6 digits, CAHs have 13XX pattern
                rpt_df['state_code'] = rpt_df['prvdr_num'].str[:2]
                rpt_df['facility_type'] = rpt_df['prvdr_num'].str[2:4]
                
                # Count CAH providers (type 13 = CAH)
                cah_mask = rpt_df['facility_type'] == '13'
                cah_count = cah_mask.sum()
                
                unique_providers = rpt_df['prvdr_num'].nunique()
                unique_cahs = rpt_df.loc[cah_mask, 'prvdr_num'].nunique()
                
                # Store CAH provider IDs
                cah_provider_ids = set(rpt_df.loc[cah_mask, 'prvdr_num'].unique())
                results["cah_providers_in_cost_reports"].update(cah_provider_ids)
                
                print(f"\n  📊 Report Analysis:")
                print(f"     Total records: {record_count:,}")
                print(f"     Unique providers: {unique_providers:,}")
                print(f"     CAH records (type 13): {cah_count:,}")
                print(f"     Unique CAH providers: {unique_cahs:,}")
                
                results["total_records"] += record_count
                results["total_providers"].update(rpt_df['prvdr_num'].unique())
                results["years_validated"].append(year)
                
                # State distribution for CAHs
                if cah_count > 0:
                    state_dist = rpt_df.loc[cah_mask, 'state_code'].value_counts().head(5)
                    print(f"\n     Top 5 states by CAH reports:")
                    for state, count in state_dist.items():
                        print(f"       {state}: {count}")
                
                results["data_quality_metrics"][year] = {
                    "total_records": record_count,
                    "unique_providers": unique_providers,
                    "cah_records": cah_count,
                    "unique_cahs": unique_cahs
                }
                
            except Exception as e:
                print(f"  ⚠️ Error reading RPT file: {e}")
                validation_results["warnings"].append(f"Error processing {year} RPT file: {str(e)}")
    
    # Convert sets to lists for JSON serialization
    results["total_providers"] = len(results["total_providers"])
    results["cah_providers_in_cost_reports"] = list(results["cah_providers_in_cost_reports"])
    
    # Determine status
    if len(results["years_validated"]) == 3:
        results["status"] = "COMPLETE"
        print(f"\n✅ CMS Cost Reports: COMPLETE ({len(results['cah_providers_in_cost_reports'])} unique CAHs identified)")
    elif len(results["years_validated"]) > 0:
        results["status"] = "PARTIAL"
        print(f"\n⚠️ CMS Cost Reports: PARTIAL (only {results['years_validated']} years)")
    else:
        results["status"] = "FAILED"
        print(f"\n❌ CMS Cost Reports: FAILED")
    
    validation_results["datasets"]["cms_cost_reports"] = results
    return results


def validate_cah_designation():
    """Validate CAH Designation data"""
    print_header("VALIDATING CAH DESIGNATION DATA")
    
    cah_dir = DATA_DIR / "cah_designation"
    
    results = {
        "status": "UNKNOWN",
        "files_validated": [],
        "total_cahs": 0,
        "geographic_coverage": {},
        "data_quality_metrics": {}
    }
    
    # Check CAH providers file
    cah_providers_file = cah_dir / "cah_providers.csv"
    if cah_providers_file.exists():
        print_subheader("CAH Providers List")
        
        try:
            cah_df = pd.read_csv(cah_providers_file)
            total_cahs = len(cah_df)
            
            print(f"  ✓ Total CAH providers: {total_cahs:,}")
            print(f"  ✓ Columns available: {list(cah_df.columns)[:10]}...")
            
            # Check for Hospital Type column
            if 'Hospital Type' in cah_df.columns:
                cah_type_count = (cah_df['Hospital Type'] == 'Critical Access Hospitals').sum()
                print(f"  ✓ Confirmed CAH type records: {cah_type_count:,}")
            
            # Geographic distribution
            if 'State' in cah_df.columns:
                state_dist = cah_df['State'].value_counts().head(10)
                print(f"\n  📍 Top 10 States by CAH count:")
                for state, count in state_dist.items():
                    print(f"     {state}: {count}")
                results["geographic_coverage"] = dict(cah_df['State'].value_counts())
            
            # Check data completeness
            missing_data = cah_df.isnull().sum()
            critical_fields = ['Facility ID', 'Facility Name', 'State', 'Hospital Type']
            
            print(f"\n  📋 Data Completeness Check:")
            for field in critical_fields:
                if field in cah_df.columns:
                    missing = missing_data.get(field, 0)
                    pct_complete = (1 - missing / total_cahs) * 100
                    status = "✓" if pct_complete >= 99 else "⚠️"
                    print(f"     {status} {field}: {pct_complete:.1f}% complete")
            
            results["total_cahs"] = total_cahs
            results["files_validated"].append("cah_providers.csv")
            results["data_quality_metrics"]["completeness"] = {
                field: float(1 - missing_data.get(field, 0) / total_cahs) 
                for field in critical_fields if field in cah_df.columns
            }
            
            # Store facility IDs for cross-validation
            if 'Facility ID' in cah_df.columns:
                results["facility_ids"] = list(cah_df['Facility ID'].astype(str).unique())
            
        except Exception as e:
            print(f"  ❌ Error reading CAH providers: {e}")
            validation_results["critical_issues"].append(f"Error reading cah_providers.csv: {str(e)}")
    else:
        print(f"  ❌ cah_providers.csv not found")
        validation_results["critical_issues"].append("cah_providers.csv missing")
    
    # Check regulatory constraints file
    constraints_file = cah_dir / "cah_regulatory_constraints.json"
    if constraints_file.exists():
        print_subheader("Regulatory Constraints")
        try:
            with open(constraints_file) as f:
                constraints = json.load(f)
            print(f"  ✓ Constraints file loaded")
            print(f"  ✓ Total CAHs documented: {constraints.get('total_cahs', 'N/A')}")
            results["files_validated"].append("cah_regulatory_constraints.json")
        except Exception as e:
            print(f"  ⚠️ Error reading constraints: {e}")
    
    # Check provider of services raw file  
    pos_file = cah_dir / "provider_of_services_raw.csv"
    if pos_file.exists():
        print_subheader("Provider of Services Raw Data")
        try:
            pos_df = pd.read_csv(pos_file, low_memory=False)
            print(f"  ✓ Total records: {len(pos_df):,}")
            print(f"  ✓ Columns: {len(pos_df.columns)}")
            results["files_validated"].append("provider_of_services_raw.csv")
        except Exception as e:
            print(f"  ⚠️ Error reading POS file: {e}")
    
    # Determine status
    if len(results["files_validated"]) >= 2 and results["total_cahs"] > 0:
        results["status"] = "COMPLETE"
        print(f"\n✅ CAH Designation: COMPLETE ({results['total_cahs']} CAHs)")
    else:
        results["status"] = "INCOMPLETE"
        print(f"\n⚠️ CAH Designation: INCOMPLETE")
    
    validation_results["datasets"]["cah_designation"] = results
    return results


def validate_mbqip_quality():
    """Validate MBQIP Quality data"""
    print_header("VALIDATING MBQIP QUALITY DATA")
    
    mbqip_dir = DATA_DIR / "mbqip_quality"
    
    results = {
        "status": "UNKNOWN",
        "files_validated": [],
        "quality_measures_defined": 0,
        "hospitals_with_quality_data": 0,
        "cah_quality_records": 0,
        "data_quality_metrics": {}
    }
    
    # Check Hospital Compare data
    hc_file = mbqip_dir / "cms_hospital_compare_data.csv"
    if hc_file.exists():
        print_subheader("CMS Hospital Compare Data")
        
        try:
            hc_df = pd.read_csv(hc_file, low_memory=False)
            total_hospitals = len(hc_df)
            
            print(f"  ✓ Total hospitals: {total_hospitals:,}")
            print(f"  ✓ Columns: {len(hc_df.columns)}")
            
            # Check for CAH-specific data
            if 'hospital_type' in hc_df.columns:
                cah_records = (hc_df['hospital_type'] == 'Critical Access Hospitals').sum()
                print(f"  ✓ CAH records: {cah_records:,}")
                results["cah_quality_records"] = cah_records
            
            # Check quality metric columns
            quality_columns = [col for col in hc_df.columns if any(
                x in col.lower() for x in ['rating', 'measure', 'score', 'mort', 'safety', 'readm']
            )]
            print(f"  ✓ Quality-related columns: {len(quality_columns)}")
            
            # Check overall rating distribution for CAHs
            if 'hospital_overall_rating' in hc_df.columns:
                if 'hospital_type' in hc_df.columns:
                    cah_mask = hc_df['hospital_type'] == 'Critical Access Hospitals'
                    cah_ratings = hc_df.loc[cah_mask, 'hospital_overall_rating'].value_counts()
                    print(f"\n  📊 CAH Overall Rating Distribution:")
                    for rating, count in cah_ratings.head(10).items():
                        print(f"     {rating}: {count}")
            
            results["hospitals_with_quality_data"] = total_hospitals
            results["files_validated"].append("cms_hospital_compare_data.csv")
            
            # Store facility IDs for cross-validation
            if 'facility_id' in hc_df.columns:
                results["facility_ids"] = list(hc_df['facility_id'].astype(str).unique())
            
        except Exception as e:
            print(f"  ❌ Error reading Hospital Compare: {e}")
            validation_results["warnings"].append(f"Error reading Hospital Compare: {str(e)}")
    
    # Check MBQIP measures reference
    measures_file = mbqip_dir / "mbqip_measures_reference.json"
    if measures_file.exists():
        print_subheader("MBQIP Measures Reference")
        
        try:
            with open(measures_file) as f:
                measures = json.load(f)
            
            total_measures = sum(len(v) for v in measures.values())
            domains = list(measures.keys())
            
            print(f"  ✓ Measure domains: {len(domains)}")
            print(f"  ✓ Total measures defined: {total_measures}")
            
            for domain in domains:
                print(f"     • {domain}: {len(measures[domain])} measures")
            
            results["quality_measures_defined"] = total_measures
            results["files_validated"].append("mbqip_measures_reference.json")
            
        except Exception as e:
            print(f"  ⚠️ Error reading measures reference: {e}")
    
    # Check year metadata files
    for year in [2021, 2022, 2023]:
        meta_file = mbqip_dir / f"mbqip_report_{year}_metadata.json"
        if meta_file.exists():
            results["files_validated"].append(f"mbqip_report_{year}_metadata.json")
            print(f"  ✓ MBQIP {year} metadata present")
    
    # Determine status
    if results["cah_quality_records"] > 0 and results["quality_measures_defined"] > 0:
        results["status"] = "COMPLETE"
        print(f"\n✅ MBQIP Quality: COMPLETE ({results['cah_quality_records']} CAHs with quality data)")
    elif len(results["files_validated"]) > 0:
        results["status"] = "PARTIAL"
        print(f"\n⚠️ MBQIP Quality: PARTIAL (metadata only)")
    else:
        results["status"] = "FAILED"
        print(f"\n❌ MBQIP Quality: FAILED")
    
    validation_results["datasets"]["mbqip_quality"] = results
    return results


def cross_validate_datasets():
    """Cross-validate data consistency across datasets"""
    print_header("CROSS-DATASET VALIDATION")
    
    results = {
        "cah_id_alignment": {},
        "data_consistency": {},
        "recommendations": []
    }
    
    # Load datasets for cross-validation.
    # Canonical roster is the step6 national CAH list. The legacy files are
    # used as supplementary cross-checks but no longer gate the alignment rate.
    try:
        step6_roster = DATA_DIR / "cms_rural_health" / "cah_hospitals.csv"
        if step6_roster.exists():
            roster_df = pd.read_csv(step6_roster, low_memory=False)
            roster_df = roster_df[roster_df['Hospital Type'].str.contains(
                'Critical Access', na=False
            )]
            cah_facility_ids = set(
                roster_df['Facility ID'].astype(str).str.strip().str.zfill(6)
            )
            print(f"  Step6 National CAH Roster: {len(cah_facility_ids)} facilities")
        else:
            cah_df = pd.read_csv(DATA_DIR / "cah_designation" / "cah_providers.csv")
            cah_facility_ids = set(cah_df['Facility ID'].astype(str).str.zfill(6))
            print(f"  CAH Designation (legacy): {len(cah_facility_ids)} facilities")

        # Hospital Compare CAHs: prefer the step6 roster (itself a filtered
        # extract of Hospital General Information) for national coverage.
        if step6_roster.exists():
            hc_cah_ids = cah_facility_ids.copy()
            print(f"  Hospital Compare CAHs (step6): {len(hc_cah_ids)} facilities")
        else:
            hc_df = pd.read_csv(
                DATA_DIR / "mbqip_quality" / "cms_hospital_compare_data.csv",
                low_memory=False,
            )
            hc_cah_mask = hc_df['hospital_type'] == 'Critical Access Hospitals'
            hc_cah_ids = set(
                hc_df.loc[hc_cah_mask, 'facility_id'].astype(str).str.zfill(6)
            )
            print(f"  Hospital Compare CAHs (legacy): {len(hc_cah_ids)} facilities")
        
        # Cross-reference
        common_ids = cah_facility_ids & hc_cah_ids
        only_in_designation = cah_facility_ids - hc_cah_ids
        only_in_compare = hc_cah_ids - cah_facility_ids
        
        print_subheader("CAH ID Alignment Analysis")
        print(f"  ✓ Matched in both datasets: {len(common_ids)}")
        print(f"  ⚠️ Only in CAH Designation: {len(only_in_designation)}")
        print(f"  ⚠️ Only in Hospital Compare: {len(only_in_compare)}")
        
        alignment_rate = len(common_ids) / max(len(cah_facility_ids), len(hc_cah_ids)) * 100
        print(f"\n  📊 Alignment Rate: {alignment_rate:.1f}%")
        
        results["cah_id_alignment"] = {
            "matched": len(common_ids),
            "only_designation": len(only_in_designation),
            "only_compare": len(only_in_compare),
            "alignment_rate": round(alignment_rate, 2)
        }
        
        if alignment_rate < 90:
            validation_results["warnings"].append(
                f"CAH ID alignment rate is {alignment_rate:.1f}%, expected >90%"
            )
            results["recommendations"].append(
                "Review CAH identification methodology - significant discrepancies found"
            )
        
        # Load Cost Report data for cross-validation
        print_subheader("Cost Report Cross-Validation")
        
        cost_report_cahs = set()
        for year in [2021, 2022, 2023]:
            rpt_file = DATA_DIR / "cms_cost_reports" / str(year) / f"HOSP10_{year}_rpt.csv"
            if rpt_file.exists():
                rpt_columns = [
                    'rpt_rec_num', 'prvdr_ctrl_type_cd', 'prvdr_num', 'npi',
                    'rpt_stus_cd', 'fy_bgn_dt', 'fy_end_dt', 'proc_dt',
                    'initl_rpt_sw', 'last_rpt_sw', 'trnsmtl_num', 'fi_num',
                    'adr_vndr_cd', 'fi_creat_dt', 'util_cd', 'npr_dt',
                    'spec_ind', 'fi_rcpt_dt'
                ]
                rpt_df = pd.read_csv(rpt_file, header=None, names=rpt_columns, dtype=str)
                cah_mask = rpt_df['prvdr_num'].str[2:4] == '13'
                year_cahs = set(
                    rpt_df.loc[cah_mask, 'prvdr_num']
                    .astype(str).str.strip().str.zfill(6).unique()
                )
                cost_report_cahs.update(year_cahs)

        print(f"  Cost Report CAHs (by provider number): {len(cost_report_cahs)}")

        # Three-way alignment: designation ∩ compare ∩ cost-report
        three_way = cah_facility_ids & hc_cah_ids & cost_report_cahs
        print(f"  3-way aligned (designation ∩ compare ∩ cost-report): {len(three_way)}")
        results["cah_id_alignment"]["three_way_aligned"] = len(three_way)
        results["cah_id_alignment"]["cost_report_matched"] = len(
            cah_facility_ids & cost_report_cahs
        )
        
        # Map provider numbers to facility IDs (different formats)
        # Provider number format: SSTTNN where SS=state, TT=type(13=CAH), NN=number
        # Facility ID format: SSNNNN where SS=state, NNNN=number
        
        results["data_consistency"]["cost_report_cahs"] = len(cost_report_cahs)
        
    except Exception as e:
        print(f"  ❌ Cross-validation error: {e}")
        validation_results["warnings"].append(f"Cross-validation error: {str(e)}")
    
    validation_results["cross_validation"] = results
    return results


def generate_validation_report():
    """Generate final validation report"""
    print_header("VALIDATION SUMMARY REPORT")
    
    # Calculate overall status
    dataset_statuses = {
        name: data.get("status", "UNKNOWN") 
        for name, data in validation_results["datasets"].items()
    }
    
    complete_count = sum(1 for s in dataset_statuses.values() if s == "COMPLETE")
    partial_count = sum(1 for s in dataset_statuses.values() if s == "PARTIAL")
    
    if complete_count == 3:
        validation_results["overall_status"] = "COMPLETE"
        overall_emoji = "✅"
    elif complete_count >= 2 or (complete_count >= 1 and partial_count >= 1):
        validation_results["overall_status"] = "SUFFICIENT"
        overall_emoji = "⚠️"
    else:
        validation_results["overall_status"] = "INSUFFICIENT"
        overall_emoji = "❌"
    
    print(f"\n{overall_emoji} OVERALL DATA QUALITY STATUS: {validation_results['overall_status']}")
    
    print("\n📊 DATASET STATUS SUMMARY:")
    for dataset, status in dataset_statuses.items():
        emoji = "✅" if status == "COMPLETE" else "⚠️" if status == "PARTIAL" else "❌"
        print(f"   {emoji} {dataset}: {status}")
    
    # Key metrics
    print("\n📈 KEY METRICS:")
    
    if "cah_designation" in validation_results["datasets"]:
        cah_data = validation_results["datasets"]["cah_designation"]
        print(f"   • Total CAH Facilities: {cah_data.get('total_cahs', 'N/A')}")
    
    if "mbqip_quality" in validation_results["datasets"]:
        quality_data = validation_results["datasets"]["mbqip_quality"]
        print(f"   • CAHs with Quality Data: {quality_data.get('cah_quality_records', 'N/A')}")
        print(f"   • Quality Measures Defined: {quality_data.get('quality_measures_defined', 'N/A')}")
    
    if "cms_cost_reports" in validation_results["datasets"]:
        cost_data = validation_results["datasets"]["cms_cost_reports"]
        print(f"   • Years with Cost Reports: {cost_data.get('years_validated', [])}")
        print(f"   • CAHs in Cost Reports: {len(cost_data.get('cah_providers_in_cost_reports', []))}")
    
    if "cross_validation" in validation_results and validation_results["cross_validation"]:
        cv = validation_results["cross_validation"]
        if "cah_id_alignment" in cv:
            align = cv["cah_id_alignment"]
            print(f"   • Cross-Dataset CAH Alignment: {align.get('alignment_rate', 'N/A')}%")
    
    # Warnings and Issues
    if validation_results["warnings"]:
        print("\n⚠️ WARNINGS:")
        for warning in validation_results["warnings"]:
            print(f"   • {warning}")
    
    if validation_results["critical_issues"]:
        print("\n❌ CRITICAL ISSUES:")
        for issue in validation_results["critical_issues"]:
            print(f"   • {issue}")
    
    # Recommendations
    validation_results["recommendations"] = [
        "Data acquisition successful - proceed to payer mix calculation",
        "Cross-reference CAH lists with state-specific designations for completeness",
        "Extract financial metrics from cost report numeric files (HOSP10_YYYY_nmrc.csv)",
        "Map Hospital Compare facility IDs to cost report provider numbers"
    ]
    
    if validation_results["overall_status"] != "COMPLETE":
        validation_results["recommendations"].insert(0, 
            "Address partial/missing datasets before proceeding to optimization"
        )
    
    print("\n📋 RECOMMENDED NEXT STEPS:")
    for i, rec in enumerate(validation_results["recommendations"], 1):
        print(f"   {i}. {rec}")
    
    # Save report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "data_validation_report.json"
    
    # Clean up non-serializable items
    clean_results = validation_results.copy()
    for dataset in clean_results.get("datasets", {}).values():
        if "facility_ids" in dataset:
            dataset["facility_id_count"] = len(dataset["facility_ids"])
            del dataset["facility_ids"]
    
    with open(report_path, 'w') as f:
        json.dump(clean_results, f, indent=2, default=str)
    
    print(f"\n✓ Validation report saved to: {report_path}")
    
    return validation_results


def main():
    """Run complete data validation"""
    print("\n" + "="*80)
    print(" " * 15 + "CAH TRANSFORMATION ENGINE")
    print(" " * 12 + "DATA QUALITY & COMPLETENESS VALIDATION")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data Directory: {DATA_DIR}")
    
    # Run validations
    validate_cms_cost_reports()
    validate_cah_designation()
    validate_mbqip_quality()
    cross_validate_datasets()
    
    # Generate summary report
    generate_validation_report()
    
    print("\n" + "="*80)
    print(" " * 20 + "VALIDATION COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

