#!/usr/bin/env python3
"""
STEP 1: Download CMS Hospital Cost Reports (Form 2552-10)
Critical dataset for financial baseline and profit optimization

Usage:
    python step1_download_cms_cost_reports.py
    python step1_download_cms_cost_reports.py --states WA,MT
"""

import requests
import zipfile
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import sys
import time
import argparse

# Configuration - Use the current script's directory as base
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data" / "cms_cost_reports"
REPORTS_DIR = BASE_DIR / "reports"

# CMS Cost Report URLs - Primary and alternative sources
# Note: CMS periodically changes URL structures, these are best-effort URLs
CMS_COST_REPORT_URLS = {
    2023: "https://downloads.cms.gov/files/hcris/hosp10-2023-ALPHA.zip",
    2022: "https://downloads.cms.gov/files/hcris/hosp10-2022-ALPHA.zip", 
    2021: "https://downloads.cms.gov/files/hcris/hosp10-2021-ALPHA.zip"
}

# Alternative URL patterns that CMS has used
CMS_ALT_URLS = {
    2023: [
        "https://www.cms.gov/files/zip/hosp-2023-10-csv.zip",
        "https://downloads.cms.gov/files/hcris/HOSP10FY2023.zip",
    ],
    2022: [
        "https://www.cms.gov/files/zip/hosp-2022-10-csv.zip",
        "https://downloads.cms.gov/files/hcris/HOSP10FY2022.zip",
    ],
    2021: [
        "https://www.cms.gov/files/zip/hosp-2021-10-csv.zip",
        "https://downloads.cms.gov/files/hcris/HOSP10FY2021.zip",
    ]
}

# Alternative direct data access
CMS_DATA_API = "https://data.cms.gov/provider-compliance/cost-report/hospital-provider-cost-report"

# State abbreviation → FIPS code mapping (for provider number filtering)
STATE_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
    "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
    "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
    "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
    "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
}


def filter_providers_by_state(df, states):
    """
    Filter provider data to specific states.

    CMS provider numbers encode the state via the first two digits (FIPS code).
    If no 'state' column exists, falls back to FIPS-based PRVDR_NUM filtering.

    Args:
        df: DataFrame of provider data
        states: List of state abbreviations (e.g. ['WA', 'MT'])

    Returns:
        Filtered DataFrame (or original if no filter could be applied)
    """
    if not states:
        return df

    states_upper = [s.upper() for s in states]
    print(f"  Filtering to states: {', '.join(states_upper)}")

    # Try state column first
    state_cols = [c for c in df.columns if c.lower() in ("state", "state_cd", "state_code")]
    if state_cols:
        col = state_cols[0]
        filtered = df[df[col].astype(str).str.upper().isin(states_upper)]
        if len(filtered) > 0:
            print(f"  Filtered {len(df):,} -> {len(filtered):,} records via {col}")
            return filtered

    # Fallback: FIPS-based PRVDR_NUM prefix
    fips_codes = [STATE_TO_FIPS[s] for s in states_upper if s in STATE_TO_FIPS]
    if fips_codes and "PRVDR_NUM" in df.columns:
        mask = df["PRVDR_NUM"].astype(str).str[:2].isin(fips_codes)
        filtered = df[mask]
        if len(filtered) > 0:
            print(f"  Filtered {len(df):,} -> {len(filtered):,} records via PRVDR_NUM FIPS prefix")
            return filtered

    print(f"  Could not filter by state — returning all records")
    return df


def download_cost_report(year):
    """Download and extract CMS cost report for a specific year"""
    print(f"\n{'='*60}")
    print(f"DOWNLOADING CMS COST REPORTS - {year}")
    print(f"{'='*60}")
    
    year_dir = DATA_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    
    # Try primary URL first, then alternatives
    urls_to_try = [CMS_COST_REPORT_URLS.get(year)] + CMS_ALT_URLS.get(year, [])
    urls_to_try = [u for u in urls_to_try if u]  # Filter None values
    
    if not urls_to_try:
        print(f"  No URLs configured for year {year}")
        return False
    
    response = None
    working_url = None
    
    for url in urls_to_try:
        try:
            print(f"  Trying: {url}")
            response = requests.get(url, stream=True, timeout=600)
            if response.status_code == 200:
                working_url = url
                print(f"  URL working!")
                break
            else:
                print(f"   Status {response.status_code}, trying next...")
        except requests.exceptions.RequestException as e:
            print(f"   Failed: {e}, trying next...")
            continue
    
    if not working_url or not response:
        print(f"  All URLs failed for year {year}")
        print(f"  Manual download may be required from: https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports")
        # Create placeholder summary
        summary = {
            "year": year,
            "status": "download_failed",
            "manual_download_required": True,
            "cms_url": "https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports",
            "timestamp": datetime.now().isoformat()
        }
        summary_path = year_dir / f"download_status_{year}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        return False
    
    try:
        print(f"  This may take 5-10 minutes for ~500MB file...")
        
        total_size = int(response.headers.get('content-length', 0))
        zip_path = year_dir / f"hosp_{year}_10.zip"
        
        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r   Progress: {progress:.1f}% ({downloaded/(1024*1024):.1f}MB)", end='')
        
        print(f"\n  Download complete: {downloaded/(1024*1024):.1f}MB")
        
        # Extract ZIP file
        print(f"  Extracting files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(year_dir)
        
        # List extracted files
        extracted_files = list(year_dir.glob("*.csv"))
        print(f"  Extracted {len(extracted_files)} CSV files:")
        for f in extracted_files[:5]:  # Show first 5
            size_mb = f.stat().st_size / (1024*1024)
            print(f"   - {f.name} ({size_mb:.1f}MB)")
        if len(extracted_files) > 5:
            print(f"   ... and {len(extracted_files)-5} more files")
        
        # Cleanup ZIP
        zip_path.unlink()
        print(f"  Cleaned up ZIP file")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  Network error: {e}")
        return False
    except zipfile.BadZipFile as e:
        print(f"  ZIP extraction error: {e}")
        return False
    except Exception as e:
        print(f"  Unexpected error: {e}")
        return False

def identify_cah_providers(year, states=None):
    """Identify CAH providers from cost report data"""
    print(f"\n{'='*60}")
    print(f"IDENTIFYING CAH PROVIDERS - {year}")
    print(f"{'='*60}")
    
    year_dir = DATA_DIR / str(year)
    
    # Find the report file (contains provider metadata)
    report_files = list(year_dir.glob("*RPT*.csv")) + list(year_dir.glob("*rpt*.csv"))
    
    if not report_files:
        print(f"  Report file not found in {year_dir}")
        print(f"   Available files: {[f.name for f in year_dir.glob('*.csv')]}")
        return None
    
    report_file = report_files[0]
    print(f"  Analyzing: {report_file.name} ({report_file.stat().st_size/(1024*1024):.1f}MB)")
    
    try:
        # Load report file
        print(f"  Loading data (this may take 2-3 minutes)...")
        df = pd.read_csv(report_file, low_memory=False)
        
        print(f"  Loaded {len(df):,} records with {len(df.columns)} columns")
        print(f"\nSample columns: {list(df.columns[:10])}")
        
        # Apply state filter if specified
        if states:
            df = filter_providers_by_state(df, states)
        
        # CAH identification logic
        # Worksheet S-2, Line 105, Column 1 = 'Y' indicates CAH designation
        # Different files may have different column naming conventions
        
        cah_indicators = []
        for col in df.columns:
            if 'wksht' in col.lower() or 'worksheet' in col.lower():
                cah_indicators.append(col)
        
        print(f"\nPotential CAH indicator columns: {cah_indicators[:5]}")
        
        # Try multiple identification approaches
        cah_count = 0
        cah_providers = set()
        
        # Approach 1: Direct worksheet filtering
        if 'WKSHT_CD' in df.columns and 'LINE_NUM' in df.columns:
            cah_records = df[
                (df['WKSHT_CD'].astype(str).str.contains('S2', na=False)) &
                (df['LINE_NUM'].astype(str).str.contains('105', na=False))
            ]
            if len(cah_records) > 0:
                print(f"  Found {len(cah_records)} CAH indicator records")
                cah_count = len(cah_records)
                if 'PRVDR_NUM' in cah_records.columns:
                    cah_providers = set(cah_records['PRVDR_NUM'].unique())
        
        # Approach 2: Provider number analysis (CAH providers typically have certain patterns)
        if 'RPT_REC_NUM' in df.columns:
            provider_counts = df.groupby('RPT_REC_NUM').size()
            print(f"\n  Found {len(provider_counts)} unique provider report records")
            
            # Save all unique providers for manual CAH filtering
            providers_df = pd.DataFrame({
                'RPT_REC_NUM': provider_counts.index,
                'RECORD_COUNT': provider_counts.values
            })
            suffix = f"_{'_'.join(states)}" if states else ""
            providers_df.to_csv(year_dir / f"all_providers_{year}{suffix}.csv", index=False)
            print(f"  Saved provider list to all_providers_{year}{suffix}.csv")
        
        # Create CAH provider summary
        summary = {
            "year": year,
            "total_records": len(df),
            "identified_cah_count": cah_count,
            "cah_provider_ids": list(cah_providers)[:100],  # Save first 100
            "analysis_timestamp": datetime.now().isoformat(),
            "columns_available": list(df.columns),
            "state_filter": states,
        }
        
        summary_path = year_dir / f"cah_identification_summary_{year}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n  Saved analysis summary to {summary_path.name}")
        print(f"\nNEXT STEP: Manual verification of CAH designation flags")
        print(f"Review: {summary_path}")
        
        return summary
        
    except Exception as e:
        print(f"  Error analyzing report file: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_step1_report(results, states=None):
    """Generate comprehensive report for Step 1"""
    print(f"\n{'='*60}")
    print(f"STEP 1 COMPLETION REPORT")
    print(f"{'='*60}")
    
    report = {
        "step": "1_cms_cost_reports",
        "timestamp": datetime.now().isoformat(),
        "datasets_downloaded": [year for year, success in results.items() if success],
        "datasets_failed": [year for year, success in results.items() if not success],
        "total_size_estimate": f"{len([y for y in results if results[y]]) * 500}MB",
        "state_filter": states,
        "next_steps": [
            "Verify CAH identification in extracted data",
            "Extract financial baseline metrics",
            "Calculate profit margins for optimization baseline",
            "Proceed to Step 2: MBQIP Quality Measures"
        ]
    }
    
    report_path = REPORTS_DIR / "step1_completion_report.json"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n  SUMMARY:")
    print(f"   Downloaded: {len(report['datasets_downloaded'])} years")
    print(f"   Failed: {len(report['datasets_failed'])} years")
    print(f"   Estimated data size: {report['total_size_estimate']}")
    if states:
        print(f"   State filter: {', '.join(states)}")
    
    if report['datasets_failed']:
        print(f"\n  Failed years: {report['datasets_failed']}")
    
    print(f"\n  Report saved to: {report_path}")
    print(f"\n{'='*60}")
    
    return report

def main():
    """Execute Step 1: CMS Cost Reports acquisition"""
    parser = argparse.ArgumentParser(description="Step 1: CMS Cost Reports")
    parser.add_argument(
        "--states",
        type=str,
        default=None,
        help="Comma-separated state abbreviations to filter (e.g. WA,MT). Default: all states.",
    )
    args = parser.parse_args()

    states = [s.strip().upper() for s in args.states.split(",")] if args.states else None

    print("\n" + "="*60)
    print("CAH DATA ACQUISITION PIPELINE")
    print("STEP 1: CMS HOSPITAL COST REPORTS (FORM 2552-10)")
    print("="*60)
    
    print(f"\nTarget: 3 years of cost report data (2021-2023)")
    print(f"Purpose: Financial baseline for profit optimization")
    print(f"Estimated size: ~1.5GB total")
    print(f"Estimated time: 30-45 minutes")
    if states:
        print(f"State filter: {', '.join(states)}")
    
    # Auto-proceed (non-interactive mode)
    print("\n[AUTO-MODE] Proceeding with download...")
    
    # Download cost reports for each year
    results = {}
    for year in [2023, 2022, 2021]:
        success = download_cost_report(year)
        results[year] = success
        
        if success:
            # Identify CAH providers in this year's data
            identify_cah_providers(year, states=states)
        
        # Brief pause between downloads
        if year != 2021:
            time.sleep(2)
    
    # Generate completion report
    generate_step1_report(results, states=states)
    
    print(f"\n  STEP 1 COMPLETE")
    print(f"Next: Run step2_download_mbqip_quality.py")

if __name__ == "__main__":
    main()
