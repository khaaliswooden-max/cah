#!/usr/bin/env python3
"""
STEP 3: Download CAH Designation Data (Provider of Services File)
Critical dataset for regulatory constraints and CAH identification
"""

import requests
import pandas as pd
from pathlib import Path
import json
from datetime import datetime

# Configuration
BASE_DIR = Path("/home/claude/cah_data_acquisition")
DATA_DIR = BASE_DIR / "data" / "cah_designation"
REPORTS_DIR = BASE_DIR / "reports"

# Provider of Services URLs
POS_URLS = {
    "cms_data_portal": "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0/download",
    "cms_direct_csv": "https://data.cms.gov/provider-characteristics/api/1/datastore/query/89jj-35fg/0/download",
    "nber_backup": "https://www.nber.org/data/provider-of-services.html"
}

def download_provider_of_services():
    """Download CMS Provider of Services file"""
    print(f"\n{'='*60}")
    print(f"DOWNLOADING PROVIDER OF SERVICES FILE")
    print(f"{'='*60}")
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Try CMS direct CSV endpoint first
    try:
        print(f"📥 Fetching from CMS Provider Characteristics API...")
        print(f"⏱️  This may take 2-3 minutes for ~100MB file...")
        
        url = POS_URLS["cms_direct_csv"]
        response = requests.get(url, timeout=300, stream=True)
        response.raise_for_status()
        
        # Save raw CSV
        csv_path = DATA_DIR / "provider_of_services_raw.csv"
        total_size = 0
        
        with open(csv_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
                    print(f"\r   Downloaded: {total_size/(1024*1024):.1f}MB", end='')
        
        print(f"\n✓ Download complete: {total_size/(1024*1024):.1f}MB")
        
        # Load and analyze
        print(f"\n📊 Loading Provider of Services data...")
        df = pd.read_csv(csv_path, low_memory=False)
        
        print(f"✓ Loaded {len(df):,} provider records")
        print(f"   Columns: {len(df.columns)}")
        print(f"\nSample columns: {list(df.columns[:15])}")
        
        return df
        
    except Exception as e:
        print(f"✗ Error with primary source: {e}")
        print(f"\nTrying alternative approach...")
        return try_alternative_download()

def try_alternative_download():
    """Try alternative method to get Provider of Services data"""
    print(f"\n📥 Attempting alternative download method...")
    
    try:
        # Alternative: Use data.medicare.gov search
        alt_url = "https://data.medicare.gov/resource/89jj-35fg.json"
        
        print(f"   Fetching from: {alt_url}")
        response = requests.get(alt_url, timeout=60, params={"$limit": 50000})
        
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            
            csv_path = DATA_DIR / "provider_of_services_alternative.csv"
            df.to_csv(csv_path, index=False)
            
            print(f"✓ Alternative download successful: {len(df)} records")
            return df
        else:
            print(f"⚠️  Alternative method failed with status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"✗ Alternative download error: {e}")
        return None

def filter_cah_providers(df):
    """Filter and extract CAH-specific providers"""
    print(f"\n{'='*60}")
    print(f"FILTERING CAH PROVIDERS")
    print(f"{'='*60}")
    
    if df is None or len(df) == 0:
        print(f"⚠️  No data available to filter")
        return None
    
    try:
        # Look for CAH indicator columns
        cah_columns = [col for col in df.columns if 'cah' in col.lower() or 'critical' in col.lower() or 'access' in col.lower()]
        
        print(f"\nPotential CAH identifier columns:")
        for col in cah_columns[:10]:
            print(f"   • {col}")
        
        # Try different filtering approaches
        cah_df = None
        
        # Approach 1: Direct CAH column
        if 'cah' in ''.join(df.columns).lower():
            for col in df.columns:
                if 'cah' in col.lower() and df[col].dtype == 'object':
                    cah_df = df[df[col].astype(str).str.upper() == 'Y']
                    if len(cah_df) > 0:
                        print(f"\n✓ Found {len(cah_df)} CAHs using column: {col}")
                        break
        
        # Approach 2: Provider type or category
        if cah_df is None or len(cah_df) == 0:
            type_cols = [col for col in df.columns if 'type' in col.lower() or 'category' in col.lower()]
            for col in type_cols:
                if col in df.columns:
                    cah_df = df[df[col].astype(str).str.contains('Critical Access|CAH', case=False, na=False)]
                    if len(cah_df) > 0:
                        print(f"\n✓ Found {len(cah_df)} CAHs using column: {col}")
                        break
        
        if cah_df is None or len(cah_df) == 0:
            print(f"\n⚠️  Could not automatically identify CAHs")
            print(f"   Manual filtering may be required")
            print(f"   Review columns and data patterns")
            
            # Save full dataset for manual analysis
            analysis_path = DATA_DIR / "pos_full_for_manual_analysis.csv"
            df.to_csv(analysis_path, index=False)
            print(f"✓ Saved full dataset to: {analysis_path.name}")
            
            return None
        
        # Save CAH-specific data
        cah_path = DATA_DIR / "cah_providers.csv"
        cah_df.to_csv(cah_path, index=False)
        print(f"✓ Saved {len(cah_df)} CAH records to: {cah_path.name}")
        
        # Extract key constraint variables
        extract_cah_constraints(cah_df)
        
        return cah_df
        
    except Exception as e:
        print(f"✗ Error filtering CAHs: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_cah_constraints(cah_df):
    """Extract regulatory constraint parameters for optimization"""
    print(f"\n{'='*60}")
    print(f"EXTRACTING CAH REGULATORY CONSTRAINTS")
    print(f"{'='*60}")
    
    try:
        # Extract bed count constraints
        bed_cols = [col for col in cah_df.columns if 'bed' in col.lower()]
        constraints = {
            "total_cahs": len(cah_df),
            "extraction_timestamp": datetime.now().isoformat()
        }
        
        if bed_cols:
            bed_col = bed_cols[0]
            bed_data = pd.to_numeric(cah_df[bed_col], errors='coerce')
            constraints["bed_constraints"] = {
                "mean": float(bed_data.mean()) if len(bed_data) > 0 else None,
                "median": float(bed_data.median()) if len(bed_data) > 0 else None,
                "min": float(bed_data.min()) if len(bed_data) > 0 else None,
                "max": float(bed_data.max()) if len(bed_data) > 0 else None,
                "regulatory_limit": 25
            }
            print(f"\n✓ Bed Count Statistics:")
            print(f"   Mean: {constraints['bed_constraints']['mean']:.1f}")
            print(f"   Median: {constraints['bed_constraints']['median']:.1f}")
            print(f"   Range: {constraints['bed_constraints']['min']:.0f} - {constraints['bed_constraints']['max']:.0f}")
            print(f"   Regulatory Limit: 25 beds")
        
        # Geographic distribution
        state_cols = [col for col in cah_df.columns if 'state' in col.lower()]
        if state_cols:
            state_col = state_cols[0]
            geo_dist = cah_df[state_col].value_counts().to_dict()
            constraints["geographic_distribution"] = {k: int(v) for k, v in list(geo_dist.items())[:10]}
            print(f"\n✓ Geographic Distribution (Top 10 States):")
            for state, count in list(geo_dist.items())[:10]:
                print(f"   {state}: {count} CAHs")
        
        # Save constraints
        constraints_path = DATA_DIR / "cah_regulatory_constraints.json"
        with open(constraints_path, 'w') as f:
            json.dump(constraints, f, indent=2)
        
        print(f"\n✓ Saved regulatory constraints to: {constraints_path.name}")
        
        return constraints
        
    except Exception as e:
        print(f"✗ Error extracting constraints: {e}")
        return None

def generate_step3_report(df, cah_df):
    """Generate completion report for Step 3"""
    print(f"\n{'='*60}")
    print(f"STEP 3 COMPLETION REPORT")
    print(f"{'='*60}")
    
    report = {
        "step": "3_cah_designation_data",
        "timestamp": datetime.now().isoformat(),
        "total_providers": len(df) if df is not None else 0,
        "cah_providers_identified": len(cah_df) if cah_df is not None else 0,
        "status": "complete" if cah_df is not None else "manual_verification_required",
        "files_created": [f.name for f in DATA_DIR.glob("*")],
        "next_steps": [
            "Validate CAH designation accuracy",
            "Cross-reference with CMS cost report CAH flags",
            "Extract regulatory constraint boundaries",
            "Proceed to Step 4: Calculate Payer Mix Data"
        ]
    }
    
    report_path = REPORTS_DIR / "step3_completion_report.json"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total providers: {report['total_providers']:,}")
    print(f"   CAHs identified: {report['cah_providers_identified']:,}")
    print(f"   Status: {report['status']}")
    print(f"   Files created: {len(report['files_created'])}")
    
    print(f"\n✓ Report saved to: {report_path}")
    print(f"\n{'='*60}")
    
    return report

def main():
    """Execute Step 3: CAH Designation Data acquisition"""
    print("\n" + "="*60)
    print("CAH DATA ACQUISITION PIPELINE")
    print("STEP 3: CAH DESIGNATION DATA (PROVIDER OF SERVICES)")
    print("="*60)
    
    print(f"\nTarget: Current CAH designations + regulatory constraints")
    print(f"Purpose: Constraint boundary definition for optimization")
    print(f"Expected: ~1,300 CAH records")
    
    proceed = input("\nProceed with download? (yes/no): ").strip().lower()
    if proceed not in ['yes', 'y']:
        print("❌ Download cancelled")
        return
    
    # Download Provider of Services data
    df = download_provider_of_services()
    
    # Filter for CAH providers
    cah_df = filter_cah_providers(df)
    
    # Generate completion report
    generate_step3_report(df, cah_df)
    
    print(f"\n✅ STEP 3 COMPLETE")
    print(f"\nNext: Proceed to calculate payer mix from cost reports")

if __name__ == "__main__":
    main()
