#!/usr/bin/env python3
"""
Add OP-3 (Median Time to Transfer for Acute Coronary Intervention) from 2022 CMS Archive

OP-3 was retired from MBQIP reporting in January 2023. This script downloads
historical data from the CMS archive to fill the gap.

Source: https://data.cms.gov/provider-data/archived-data/hospitals
Archive: October 2022 (last full year with OP-3 data)
"""

import os
import sys
import requests
import pandas as pd
import zipfile
import io
from pathlib import Path
from datetime import datetime

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "cms_archive_2022"
PROCESSED_DIR = DATA_DIR / "processed"

# CMS Archive URL for October 2022
# Direct link to the hospitals_10_2022.zip file
ARCHIVE_URL = "https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2022/hospitals_10_2022.zip"

def setup_directories():
    """Create necessary directories."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def download_2022_archive():
    """Download the October 2022 CMS hospital archive."""
    zip_path = RAW_DIR / "hospitals_10_2022.zip"
    
    if zip_path.exists():
        print(f"[OK] Archive already downloaded: {zip_path.name}")
        return zip_path
    
    print("Downloading 2022 CMS Hospital Archive...")
    print(f"  URL: {ARCHIVE_URL}")
    print("  This may take a few minutes (large file)...")
    
    try:
        response = requests.get(ARCHIVE_URL, stream=True, timeout=300)
        response.raise_for_status()
        
        # Get file size for progress
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        print(f"\r  Progress: {pct:.1f}% ({downloaded // 1024 // 1024} MB)", end="")
        
        print(f"\n[OK] Downloaded: {zip_path.name} ({downloaded // 1024 // 1024} MB)")
        return zip_path
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to download archive: {e}")
        return None

def extract_timely_effective_care(zip_path):
    """Extract the Timely and Effective Care CSV from the archive."""
    output_path = RAW_DIR / "Timely_and_Effective_Care-Hospital_2022.csv"
    
    if output_path.exists():
        print(f"[OK] Already extracted: {output_path.name}")
        return output_path
    
    print("Extracting Timely and Effective Care data...")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # List files in archive to find the right one
            file_list = zip_ref.namelist()
            
            # Look for timely and effective care file
            tec_file = None
            for f in file_list:
                if 'timely' in f.lower() and 'effective' in f.lower() and f.endswith('.csv'):
                    tec_file = f
                    break
            
            if not tec_file:
                # Try alternative naming
                for f in file_list:
                    if 'op_' in f.lower() or 'outpatient' in f.lower():
                        tec_file = f
                        break
            
            if not tec_file:
                print("  Available files in archive:")
                for f in file_list[:20]:
                    print(f"    - {f}")
                print("  Looking for any CSV with quality measures...")
                
                # Just list all CSVs
                csv_files = [f for f in file_list if f.endswith('.csv')]
                for f in csv_files[:10]:
                    print(f"    - {f}")
                
                # Try to find one that might have OP-3
                for f in csv_files:
                    if 'hospital' in f.lower():
                        tec_file = f
                        print(f"  Trying: {f}")
                        break
            
            if tec_file:
                print(f"  Extracting: {tec_file}")
                zip_ref.extract(tec_file, RAW_DIR)
                
                # Rename to standard name
                extracted_path = RAW_DIR / tec_file
                if extracted_path.exists():
                    # Handle nested directories
                    if extracted_path.is_file():
                        extracted_path.rename(output_path)
                    else:
                        # Find the actual CSV
                        for root, dirs, files in os.walk(extracted_path):
                            for f in files:
                                if f.endswith('.csv'):
                                    Path(root, f).rename(output_path)
                                    break
                
                print(f"[OK] Extracted: {output_path.name}")
                return output_path
            else:
                print("[ERROR] Could not find Timely and Effective Care data in archive")
                return None
                
    except zipfile.BadZipFile as e:
        print(f"[ERROR] Invalid zip file: {e}")
        return None

def extract_op3_data(csv_path, states=['MT', 'WA']):
    """Extract OP-3 measure data for specified states."""
    print(f"Extracting OP-3 data for states: {states}")
    
    try:
        # Read the CSV
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"  Total records in archive: {len(df)}")
        
        # Standardize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Print available columns
        print(f"  Columns: {list(df.columns)[:10]}...")
        
        # Find state column
        state_col = None
        for col in ['state', 'provider_state', 'hospital_state']:
            if col in df.columns:
                state_col = col
                break
        
        if not state_col:
            print(f"  [WARNING] No state column found. Available: {list(df.columns)}")
            return None
        
        # Find measure ID column
        measure_col = None
        for col in ['measure_id', 'measure_name', 'measureid']:
            if col in df.columns:
                measure_col = col
                break
        
        # Find facility/provider ID column
        facility_col = None
        for col in ['facility_id', 'provider_id', 'provider_number', 'ccn']:
            if col in df.columns:
                facility_col = col
                break
        
        # Find score column
        score_col = None
        for col in ['score', 'measure_score', 'value']:
            if col in df.columns:
                score_col = col
                break
        
        print(f"  State column: {state_col}")
        print(f"  Measure column: {measure_col}")
        print(f"  Facility column: {facility_col}")
        print(f"  Score column: {score_col}")
        
        # Filter for states
        df_states = df[df[state_col].isin(states)]
        print(f"  Records for {states}: {len(df_states)}")
        
        # Check what measures are available
        if measure_col:
            measures = df_states[measure_col].unique()
            op3_measures = [m for m in measures if 'op' in str(m).lower() and '3' in str(m)]
            print(f"  OP-3 related measures found: {op3_measures}")
            
            # Filter for OP-3
            op3_pattern = df_states[measure_col].astype(str).str.upper().str.contains('OP.?3', regex=True, na=False)
            # Exclude OP-31, OP-33, etc - we want exactly OP-3 or OP_3
            exact_op3 = df_states[measure_col].astype(str).str.upper().isin(['OP-3', 'OP_3', 'OP3'])
            
            df_op3 = df_states[exact_op3 | (op3_pattern & ~df_states[measure_col].astype(str).str.contains('OP.?3[0-9]', regex=True, na=False))]
            
            if len(df_op3) == 0:
                # Check all OP measures
                all_op = [m for m in measures if str(m).upper().startswith('OP')]
                print(f"  All OP measures in data: {sorted(all_op)[:20]}")
                
                print("[WARNING] No OP-3 records found in 2022 archive for these states")
                return None
            
            print(f"  OP-3 records found: {len(df_op3)}")
            
            # Create clean output
            result = df_op3[[facility_col, state_col, score_col]].copy()
            result.columns = ['CCN', 'State', 'OP-3']
            
            # Clean CCN format
            result['CCN'] = result['CCN'].astype(str).str.strip().str.zfill(6)
            
            # Clean score - convert to numeric
            result['OP-3'] = pd.to_numeric(result['OP-3'], errors='coerce')
            
            # Remove duplicates - take first value per facility
            result = result.drop_duplicates(subset=['CCN'], keep='first')
            
            print(f"  Unique facilities with OP-3: {len(result)}")
            print(f"  OP-3 value range: {result['OP-3'].min()} - {result['OP-3'].max()} minutes")
            
            return result
        
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to extract OP-3: {e}")
        import traceback
        traceback.print_exc()
        return None

def merge_op3_into_composite(op3_df):
    """Merge OP-3 data into the composite baseline dataset."""
    composite_path = PROCESSED_DIR / "cah_composite_baseline.csv"
    
    if not composite_path.exists():
        print(f"[ERROR] Composite dataset not found: {composite_path}")
        return False
    
    print("Merging OP-3 into composite dataset...")
    
    # Read composite
    composite = pd.read_csv(composite_path)
    print(f"  Composite records: {len(composite)}")
    
    # Ensure CCN format matches
    if 'CCN' in composite.columns:
        composite['CCN'] = composite['CCN'].astype(str).str.strip().str.zfill(6)
    elif 'Provider_Num' in composite.columns:
        composite['CCN'] = composite['Provider_Num'].astype(str).str.strip().str.zfill(6)
    
    # Remove existing OP-3 if present
    if 'OP-3' in composite.columns:
        composite = composite.drop(columns=['OP-3'])
    if 'OP3_Data_Year' in composite.columns:
        composite = composite.drop(columns=['OP3_Data_Year'])
    
    # Merge
    op3_for_merge = op3_df[['CCN', 'OP-3']].copy()
    merged = composite.merge(op3_for_merge, on='CCN', how='left')
    
    # Add data year metadata
    merged['OP3_Data_Year'] = merged['OP-3'].apply(lambda x: '2022' if pd.notna(x) else None)
    
    # Stats
    matched = merged['OP-3'].notna().sum()
    print(f"  Matched OP-3 values: {matched}/{len(merged)} ({100*matched/len(merged):.1f}%)")
    
    if matched > 0:
        print(f"  OP-3 range: {merged['OP-3'].min():.0f} - {merged['OP-3'].max():.0f} minutes")
        print(f"  OP-3 median: {merged['OP-3'].median():.0f} minutes")
    
    # Save
    merged.to_csv(composite_path, index=False)
    print(f"[OK] Updated: {composite_path.name}")
    
    # Also save a backup
    backup_path = PROCESSED_DIR / f"cah_composite_baseline_with_op3_{datetime.now().strftime('%Y%m%d')}.csv"
    merged.to_csv(backup_path, index=False)
    print(f"[OK] Backup: {backup_path.name}")
    
    return True

def try_direct_api_for_2022():
    """Try to get 2022 OP-3 data directly from CMS API."""
    print("Attempting direct API query for historical OP-3 data...")
    
    # CMS sometimes has historical data accessible via API with date filters
    api_url = "https://data.cms.gov/provider-data/api/1/datastore/query/yv7e-xc69/0"
    
    params = {
        "conditions[0][property]": "measure_id",
        "conditions[0][value]": "OP_3",
        "conditions[0][operator]": "=",
        "limit": 1000
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and len(data['results']) > 0:
                print(f"  Found {len(data['results'])} OP-3 records via API!")
                return pd.DataFrame(data['results'])
        print("  No OP-3 data in current API (measure retired)")
        return None
    except Exception as e:
        print(f"  API query failed: {e}")
        return None

def main():
    """Main function to add OP-3 from 2022 archive."""
    print("=" * 60)
    print("Adding OP-3 from CMS 2022 Archive")
    print("=" * 60)
    print()
    
    setup_directories()
    
    # First try direct API (faster if available)
    api_data = try_direct_api_for_2022()
    
    if api_data is not None and len(api_data) > 0:
        # Use API data
        op3_df = api_data
    else:
        # Download archive
        zip_path = download_2022_archive()
        if not zip_path:
            print("\n[FAILED] Could not download archive")
            sys.exit(1)
        
        # Extract data
        csv_path = extract_timely_effective_care(zip_path)
        if not csv_path:
            print("\n[FAILED] Could not extract data from archive")
            sys.exit(1)
        
        # Extract OP-3
        op3_df = extract_op3_data(csv_path, states=['MT', 'WA'])
    
    if op3_df is None or len(op3_df) == 0:
        print("\n[WARNING] No OP-3 data found in 2022 archive")
        print("This may indicate OP-3 was already being phased out in late 2022")
        print("\nAlternative: Creating placeholder with state averages from literature")
        
        # Create placeholder based on literature values
        # Typical OP-3 for rural hospitals: 60-120 minutes
        composite_path = PROCESSED_DIR / "cah_composite_baseline.csv"
        composite = pd.read_csv(composite_path)
        
        # Add OP-3 as NaN with documentation
        if 'OP-3' not in composite.columns:
            composite['OP-3'] = None
            composite['OP3_Data_Year'] = None
            composite['OP3_Note'] = 'Measure retired Jan 2023; historical data not available for these facilities'
            composite.to_csv(composite_path, index=False)
            print(f"[OK] Added OP-3 column (no data available) to {composite_path.name}")
        
        sys.exit(0)
    
    # Merge into composite
    success = merge_op3_into_composite(op3_df)
    
    if success:
        print("\n" + "=" * 60)
        print("SUCCESS: OP-3 data added to composite dataset")
        print("=" * 60)
        print("\nNote: OP-3 values are from October 2022 (last available)")
        print("The measure was retired from MBQIP in January 2023.")
    else:
        print("\n[FAILED] Could not merge OP-3 into composite")
        sys.exit(1)

if __name__ == "__main__":
    main()

