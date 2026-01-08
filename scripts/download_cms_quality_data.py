#!/usr/bin/env python3
"""
CMS Hospital Compare Quality Data Downloader
=============================================
This script downloads quality measures data from CMS Provider Data Catalog
for Montana and Washington Critical Access Hospitals.

Usage:
    python scripts/download_cms_quality_data.py

If automatic download fails, the script provides instructions for manual download.
"""

import requests
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import time

# Configuration
BASE_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "mbqip_quality"
REPORTS_DIR = BASE_DIR / "reports"

RAW_DIR.mkdir(parents=True, exist_ok=True)

TARGET_STATES = ["MT", "WA"]

# CMS Dataset IDs
DATASETS = {
    "timely_effective_care": {
        "id": "yv7e-xc69",
        "name": "Timely and Effective Care - Hospital",
        "description": "Contains OP-18, OP-3, IMM-2, and other quality measures",
        "download_url": "https://data.cms.gov/provider-data/dataset/yv7e-xc69"
    },
    "hospital_general_info": {
        "id": "xubh-q36u",
        "name": "Hospital General Information",
        "description": "Hospital characteristics and overall quality ratings",
        "download_url": "https://data.cms.gov/provider-data/dataset/xubh-q36u"
    }
}


def download_from_socrata_api(dataset_id, state_filter=None):
    """
    Try to download data using Socrata-style API
    """
    base_url = f"https://data.cms.gov/resource/{dataset_id}.json"
    
    all_records = []
    
    if state_filter:
        for state in state_filter:
            print(f"  Downloading {state} data...")
            params = {
                "$where": f"state='{state}'",
                "$limit": 50000
            }
            
            try:
                response = requests.get(base_url, params=params, timeout=120)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        all_records.extend(data)
                        print(f"    Downloaded {len(data)} records for {state}")
                else:
                    print(f"    API returned status {response.status_code}")
            except Exception as e:
                print(f"    Error: {e}")
            
            time.sleep(0.5)
    else:
        # Download all with pagination
        offset = 0
        limit = 50000
        
        while True:
            params = {"$limit": limit, "$offset": offset}
            try:
                response = requests.get(base_url, params=params, timeout=120)
                if response.status_code == 200:
                    data = response.json()
                    if not data:
                        break
                    all_records.extend(data)
                    print(f"    Downloaded {len(all_records)} records...")
                    if len(data) < limit:
                        break
                    offset += limit
                else:
                    break
            except Exception as e:
                print(f"    Error: {e}")
                break
            
            time.sleep(0.3)
    
    return all_records


def download_timely_effective_care():
    """
    Download Timely and Effective Care dataset
    """
    print("\n" + "=" * 60)
    print("DOWNLOADING: Timely and Effective Care - Hospital")
    print("=" * 60)
    
    dataset = DATASETS["timely_effective_care"]
    print(f"Dataset ID: {dataset['id']}")
    print(f"URL: {dataset['download_url']}")
    
    # Try Socrata API first
    print("\nAttempting Socrata API download...")
    records = download_from_socrata_api(dataset['id'], TARGET_STATES)
    
    if records:
        df = pd.DataFrame(records)
        output_path = RAW_DIR / "timely_effective_care_hospital.csv"
        df.to_csv(output_path, index=False)
        print(f"\n[SUCCESS] Saved {len(df)} records to {output_path.name}")
        return df
    
    print("\n[FAILED] Automatic download unsuccessful.")
    print_manual_instructions(dataset)
    return None


def download_hospital_general_info():
    """
    Download Hospital General Information dataset
    """
    print("\n" + "=" * 60)
    print("DOWNLOADING: Hospital General Information")
    print("=" * 60)
    
    dataset = DATASETS["hospital_general_info"]
    print(f"Dataset ID: {dataset['id']}")
    print(f"URL: {dataset['download_url']}")
    
    # Try Socrata API first
    print("\nAttempting Socrata API download...")
    records = download_from_socrata_api(dataset['id'], TARGET_STATES)
    
    if records:
        df = pd.DataFrame(records)
        output_path = RAW_DIR / "hospital_general_info.csv"
        df.to_csv(output_path, index=False)
        print(f"\n[SUCCESS] Saved {len(df)} records to {output_path.name}")
        return df
    
    print("\n[FAILED] Automatic download unsuccessful.")
    print_manual_instructions(dataset)
    return None


def print_manual_instructions(dataset):
    """
    Print instructions for manual download
    """
    print("\n" + "-" * 60)
    print("MANUAL DOWNLOAD INSTRUCTIONS")
    print("-" * 60)
    print(f"""
1. Open your browser and go to:
   {dataset['download_url']}

2. Click the "Download" button

3. Choose CSV format

4. Save the file to:
   {RAW_DIR}

5. Rename the file to match expected name:
   - Timely and Effective Care: timely_effective_care_hospital.csv
   - Hospital General Info: hospital_general_info.csv

6. Re-run the merge script:
   python scripts/merge_mbqip_hcris_data.py
""")


def filter_for_mt_wa_cahs(df):
    """
    Filter downloaded data for MT/WA Critical Access Hospitals
    """
    if df is None:
        return None
    
    # Find state column
    state_col = None
    for col in ['state', 'State', 'STATE']:
        if col in df.columns:
            state_col = col
            break
    
    if state_col is None:
        print("Could not find state column")
        return df
    
    # Filter for MT and WA
    filtered = df[df[state_col].isin(TARGET_STATES)].copy()
    print(f"Filtered to {len(filtered)} MT/WA records")
    
    return filtered


def main():
    """
    Main execution
    """
    print("\n" + "=" * 60)
    print("CMS HOSPITAL COMPARE QUALITY DATA DOWNLOADER")
    print("Target: Montana and Washington Critical Access Hospitals")
    print("=" * 60)
    
    # Download Timely and Effective Care
    tec_df = download_timely_effective_care()
    
    # Download Hospital General Info
    hgi_df = download_hospital_general_info()
    
    # Summary
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    
    if tec_df is not None:
        mt_wa_tec = filter_for_mt_wa_cahs(tec_df)
        print(f"Timely & Effective Care: {len(mt_wa_tec) if mt_wa_tec is not None else 0} MT/WA records")
    else:
        print("Timely & Effective Care: MANUAL DOWNLOAD REQUIRED")
    
    if hgi_df is not None:
        mt_wa_hgi = filter_for_mt_wa_cahs(hgi_df)
        print(f"Hospital General Info: {len(mt_wa_hgi) if mt_wa_hgi is not None else 0} MT/WA records")
    else:
        print("Hospital General Info: MANUAL DOWNLOAD REQUIRED")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("""
After downloading quality data, run:
    python scripts/merge_mbqip_hcris_data.py

This will merge quality measures with financial data.
""")


if __name__ == "__main__":
    main()

