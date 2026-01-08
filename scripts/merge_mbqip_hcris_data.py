#!/usr/bin/env python3
"""
MBQIP Quality Measures + HCRIS Financial Data Merger
====================================================
Day 3-4: Merge MBQIP quality measures with HCRIS financial data

This script:
1. Downloads MBQIP quality measures from CMS Hospital Compare (Timely & Effective Care)
2. Filters for MT/WA Critical Access Hospitals
3. Extracts key measures: OP-18, OP-1 (OP-2), OP-3, IMM-2 (HCP)
4. Merges with HCRIS financial data on CCN (Provider Number)
5. Creates composite dataset with financial + quality metrics

Output: data/processed/cah_composite_baseline.csv
"""

import requests
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import logging
import time

# Configuration
BASE_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw" / "mbqip_quality"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / f"mbqip_merge_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# CMS API Endpoints
CMS_API_BASE = "https://data.cms.gov/provider-data/api/1/datastore/query"
TIMELY_EFFECTIVE_CARE_ID = "yv7e-xc69"  # Timely and Effective Care - Hospital
HOSPITAL_GENERAL_INFO_ID = "xubh-q36u"  # Hospital General Information

# Target states for CAH analysis
TARGET_STATES = ["MT", "WA"]

# MBQIP Quality Measures of Interest
# Note: CMS measure IDs may differ slightly from MBQIP naming
MBQIP_MEASURES = {
    "OP-18": {
        "cms_ids": ["OP_18", "OP-18", "OP_18a", "OP_18b", "OP_18c", "OP_18d"],
        "name": "Median Time from ED Arrival to ED Departure for Admitted ED Patients",
        "description": "Median time (in minutes) from ED arrival to ED departure for admitted patients",
        "target": "<=274 minutes",
        "lower_is_better": True
    },
    "OP-2": {
        "cms_ids": ["OP_2", "OP-2", "OP_29"],  # OP-29 is fibrinolytic in newer CMS
        "name": "Fibrinolytic Therapy Received Within 30 Minutes",
        "description": "AMI patients receiving fibrinolytic therapy during ED visit",
        "target": ">=75%",
        "lower_is_better": False
    },
    "IMM-2": {
        "cms_ids": ["IMM_2", "IMM-2", "IMM_3", "IMM-3"],  # IMM-3 is current CMS name
        "name": "Healthcare Personnel Influenza Vaccination",
        "description": "Percentage of healthcare personnel who received influenza vaccination",
        "target": ">=90%",
        "lower_is_better": False
    },
    "OP-22": {
        "cms_ids": ["OP_22", "OP-22"],
        "name": "ED Left Without Being Seen",
        "description": "Percentage of patients who left the ED without being seen",
        "target": "<=3%",
        "lower_is_better": True
    },
    "OP-23": {
        "cms_ids": ["OP_23", "OP-23"],
        "name": "Head CT Results Within 45 Minutes",
        "description": "ED stroke patients with head CT scan results within 45 minutes",
        "target": ">=75%",
        "lower_is_better": False
    },
    "SEP-1": {
        "cms_ids": ["SEP_1", "SEP-1"],
        "name": "Sepsis Early Management Bundle",
        "description": "Severe sepsis/septic shock patients receiving appropriate care",
        "target": ">=65%",
        "lower_is_better": False
    }
}


def download_cms_timely_effective_care(limit=500000, target_states=None):
    """
    Download Timely and Effective Care dataset from CMS Provider Data API
    Contains OP-18, OP-3, IMM-2, and other quality measures
    
    API Documentation: https://data.cms.gov/provider-data/api
    Dataset: yv7e-xc69 (Timely and Effective Care - Hospital)
    """
    logger.info("Downloading CMS Timely and Effective Care dataset...")
    
    if target_states is None:
        target_states = TARGET_STATES
    
    # CMS Provider Data API - uses conditions[] filter syntax
    api_url = f"{CMS_API_BASE}/{TIMELY_EFFECTIVE_CARE_ID}/0"
    
    all_results = []
    
    for state in target_states:
        logger.info(f"  Downloading data for state: {state}")
        
        offset = 0
        batch_size = 1000  # CMS API has max limit of ~1000
        state_records = []
        
        while True:
            try:
                # Use conditions[] filter syntax - this is the correct CMS API format
                params = {
                    "conditions[0][property]": "state",
                    "conditions[0][value]": state,
                    "conditions[0][operator]": "=",
                    "limit": batch_size,
                    "offset": offset
                }
                
                response = requests.get(api_url, params=params, timeout=120)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'results' in data and data['results']:
                        state_records.extend(data['results'])
                        logger.info(f"    Batch: {len(state_records)} records...")
                        
                        # Check if more pages
                        if len(data['results']) < batch_size:
                            break
                        offset += batch_size
                    else:
                        break
                else:
                    logger.warning(f"    API returned status {response.status_code}")
                    break
                    
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"    Error: {e}")
                break
        
        if state_records:
            all_results.extend(state_records)
            logger.info(f"    [OK] Total {len(state_records)} records for {state}")
        
        time.sleep(0.3)  # Rate limiting between states
    
    if all_results:
        df = pd.DataFrame(all_results)
        
        # Save raw data
        raw_path = RAW_DIR / "timely_effective_care_hospital.csv"
        df.to_csv(raw_path, index=False)
        logger.info(f"  [OK] Total {len(df)} MT/WA records saved to {raw_path.name}")
        
        # Show summary of measures found
        if 'measure_id' in df.columns:
            measures = df['measure_id'].unique()
            logger.info(f"  Measures found: {list(measures)}")
        
        return df
    else:
        logger.warning("No data downloaded from API")
        return None


def load_existing_timely_care_data():
    """Load existing CMS data if available"""
    raw_path = RAW_DIR / "timely_effective_care_hospital.csv"
    if raw_path.exists():
        df = pd.read_csv(raw_path)
        # Check if data has MT/WA records
        state_col = None
        for col in ['State', 'state', 'STATE']:
            if col in df.columns:
                state_col = col
                break
        
        if state_col:
            mt_wa = df[(df[state_col]=='MT') | (df[state_col]=='WA')]
            if len(mt_wa) > 0:
                logger.info(f"Loading existing data from {raw_path} ({len(mt_wa)} MT/WA records)")
                return df
        
        logger.info(f"Existing data has no MT/WA records, will download fresh")
    return None


def load_cah_provider_list():
    """Load list of MT/WA CAH providers"""
    cah_path = DATA_DIR / "cah_designation" / "cah_providers.csv"
    if cah_path.exists():
        df = pd.read_csv(cah_path)
        mt_wa = df[(df['State']=='MT') | (df['State']=='WA')]
        logger.info(f"Loaded {len(mt_wa)} MT/WA CAH providers from designation file")
        return mt_wa
    return None


def create_placeholder_quality_data(cah_providers):
    """
    Create placeholder quality data structure for MT/WA CAHs
    This is used when API download fails, can be populated with manual data later
    """
    logger.info("Creating placeholder quality data structure...")
    
    if cah_providers is None:
        return None
    
    # Get unique facility IDs
    facility_ids = cah_providers['Facility ID'].unique()
    
    # Create placeholder DataFrame
    records = []
    for fac_id in facility_ids:
        record = {
            'CCN': str(fac_id).zfill(6),
            'OP-18': np.nan,  # Median time ED arrival to departure
            'OP-2': np.nan,   # Fibrinolytic therapy
            'OP-3': np.nan,   # Median time to transfer - AMI
            'IMM-2': np.nan,  # Healthcare personnel flu vaccination
            'ED-1b': np.nan,  # ED throughput
            'ED-2b': np.nan,  # Admit decision to departure
            'OP-22': np.nan,  # Left without being seen
            'Quality_Data_Source': 'Placeholder - Manual Entry Required'
        }
        records.append(record)
    
    df = pd.DataFrame(records)
    logger.info(f"  Created placeholder for {len(df)} facilities")
    
    return df


def filter_mt_wa_cahs(df, ccn_column=None):
    """
    Filter dataset for Montana and Washington Critical Access Hospitals
    MT CCN prefix: 271xxx
    WA CCN prefix: 501xxx
    """
    logger.info("Filtering for MT/WA Critical Access Hospitals...")
    
    # Auto-detect CCN column name
    if ccn_column is None:
        for col in ['Facility ID', 'facility_id', 'Facility Id', 'FACILITY ID', 'CCN', 'Provider_Num']:
            if col in df.columns:
                ccn_column = col
                break
        if ccn_column is None:
            logger.error("Could not find facility ID column")
            return df
    
    logger.info(f"  Using CCN column: {ccn_column}")
    
    # Convert CCN to string for pattern matching
    df[ccn_column] = df[ccn_column].astype(str).str.zfill(6)
    
    # MT CAHs: 2713xx pattern, WA CAHs: 5013xx pattern
    mt_mask = df[ccn_column].str.match(r'^27\d{4}$')
    wa_mask = df[ccn_column].str.match(r'^50\d{4}$')
    
    filtered = df[mt_mask | wa_mask].copy()
    
    # Add state column based on CCN
    filtered['state_from_ccn'] = filtered[ccn_column].apply(
        lambda x: 'MT' if x.startswith('27') else 'WA' if x.startswith('50') else 'Unknown'
    )
    
    logger.info(f"  Found {len(filtered)} records for MT/WA facilities")
    return filtered


def extract_mbqip_measures(df):
    """
    Extract and pivot MBQIP quality measures from CMS data
    Returns one row per facility with measures as columns
    """
    logger.info("Extracting MBQIP quality measures...")
    
    # Standardize column names (CMS uses varying case)
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    
    # Identify measure column
    measure_col = None
    for col in ['measure_id', 'measureid', 'measure_name', 'condition']:
        if col in df.columns:
            measure_col = col
            break
    
    if measure_col is None:
        logger.warning("Could not find measure identifier column")
        return None
    
    # Identify facility ID column
    facility_col = None
    for col in ['facility_id', 'facilityid', 'provider_id', 'ccn']:
        if col in df.columns:
            facility_col = col
            break
    
    if facility_col is None:
        logger.warning("Could not find facility ID column")
        return None
    
    # Identify score column
    score_col = None
    for col in ['score', 'measure_score', 'value']:
        if col in df.columns:
            score_col = col
            break
    
    logger.info(f"  Using columns: facility={facility_col}, measure={measure_col}, score={score_col}")
    
    # Filter for measures of interest
    measure_patterns = []
    for measure, info in MBQIP_MEASURES.items():
        measure_patterns.extend(info['cms_ids'])
    
    # Create pattern for matching
    pattern = '|'.join([f"({m})" for m in measure_patterns])
    
    # Filter rows matching our measures (case-insensitive)
    if measure_col:
        df['measure_match'] = df[measure_col].astype(str).str.upper()
        filtered = df[df['measure_match'].str.contains(pattern, case=False, na=False)].copy()
        logger.info(f"  Found {len(filtered)} records matching MBQIP measures")
    else:
        filtered = df.copy()
    
    # Pivot to get one row per facility
    if score_col and facility_col:
        # Clean score values
        filtered[score_col] = pd.to_numeric(filtered[score_col], errors='coerce')
        
        # Map measure IDs to standardized names
        def standardize_measure(measure_id):
            measure_str = str(measure_id).upper()
            # First try exact match
            for standard_name, info in MBQIP_MEASURES.items():
                for cms_id in info['cms_ids']:
                    if cms_id.upper() == measure_str:
                        return standard_name
            # Then try contains match (longer IDs first to avoid OP_2 matching OP_22)
            for standard_name, info in sorted(MBQIP_MEASURES.items(), key=lambda x: -max(len(c) for c in x[1]['cms_ids'])):
                for cms_id in sorted(info['cms_ids'], key=len, reverse=True):
                    if cms_id.upper() in measure_str or measure_str in cms_id.upper():
                        return standard_name
            return measure_str
        
        filtered['standardized_measure'] = filtered[measure_col].apply(standardize_measure)
        
        # Pivot table
        pivot = filtered.pivot_table(
            index=facility_col,
            columns='standardized_measure',
            values=score_col,
            aggfunc='first'
        ).reset_index()
        
        pivot.columns.name = None
        pivot = pivot.rename(columns={facility_col: 'CCN'})
        
        logger.info(f"  Created pivot table with {len(pivot)} facilities")
        logger.info(f"  Measures found: {list(pivot.columns[1:])}")
        
        return pivot
    
    return None


def load_hcris_financial_data():
    """
    Load HCRIS financial data from existing baseline metrics
    """
    logger.info("Loading HCRIS financial data...")
    
    baseline_path = DATA_DIR / "processed" / "cah_baseline_metrics.csv"
    
    if not baseline_path.exists():
        logger.error(f"HCRIS baseline file not found: {baseline_path}")
        return None
    
    df = pd.read_csv(baseline_path)
    logger.info(f"  Loaded {len(df)} HCRIS records")
    
    # Standardize CCN column
    if 'Provider_Num' in df.columns:
        df['CCN'] = df['Provider_Num'].astype(str).str.zfill(6)
    elif 'provider_num' in df.columns:
        df['CCN'] = df['provider_num'].astype(str).str.zfill(6)
    
    return df


def load_facility_characteristics():
    """
    Load facility characteristics from state benchmark files
    """
    logger.info("Loading facility characteristics...")
    
    facilities = []
    
    for state_file in ['mt_cah_detailed.json', 'wa_cah_detailed.json']:
        filepath = DATA_DIR / "state_benchmarks" / state_file
        if filepath.exists():
            with open(filepath, 'r') as f:
                data = json.load(f)
                if 'facilities' in data:
                    for fac in data['facilities']:
                        facilities.append({
                            'CCN': str(fac.get('ccn', '')).zfill(6),
                            'Facility_Name': fac.get('name', ''),
                            'City': fac.get('city', ''),
                            'County': fac.get('county', ''),
                            'Ownership': fac.get('ownership', ''),
                            'Emergency_Services': fac.get('emergency_services', None),
                            'Birthing_Friendly': fac.get('birthing_friendly', None),
                            'Overall_Rating': fac.get('overall_rating', None)
                        })
    
    if facilities:
        df = pd.DataFrame(facilities)
        logger.info(f"  Loaded characteristics for {len(df)} facilities")
        return df
    
    return None


def create_composite_dataset(hcris_df, quality_df, characteristics_df):
    """
    Merge all datasets into composite baseline
    """
    logger.info("Creating composite dataset...")
    
    # Start with HCRIS financial data
    composite = hcris_df.copy()
    
    # Ensure CCN is string and zero-padded
    composite['CCN'] = composite['CCN'].astype(str).str.zfill(6)
    
    # Merge quality measures
    if quality_df is not None:
        quality_df['CCN'] = quality_df['CCN'].astype(str).str.zfill(6)
        composite = composite.merge(
            quality_df,
            on='CCN',
            how='left',
            suffixes=('', '_quality')
        )
        logger.info(f"  Merged quality measures: {len(composite)} records")
    
    # Merge facility characteristics
    if characteristics_df is not None:
        characteristics_df['CCN'] = characteristics_df['CCN'].astype(str).str.zfill(6)
        # Only merge columns not already present
        char_cols = ['CCN'] + [c for c in characteristics_df.columns if c not in composite.columns and c != 'CCN']
        composite = composite.merge(
            characteristics_df[char_cols],
            on='CCN',
            how='left'
        )
        logger.info(f"  Merged characteristics: {len(composite)} records")
    
    # Add derived metrics
    composite = add_derived_metrics(composite)
    
    return composite


def add_derived_metrics(df):
    """
    Add derived financial and quality metrics
    """
    logger.info("Adding derived metrics...")
    
    # Financial ratios (if not already present)
    if 'Total_Patient_Revenue' in df.columns and 'Total_Operating_Expenses' in df.columns:
        # Net margin percentage
        df['Net_Revenue'] = df['Total_Patient_Revenue'] - df['Total_Operating_Expenses']
        
        # Operating margin (already exists but ensure it's calculated correctly)
        if 'Operating_Margin' not in df.columns:
            df['Operating_Margin'] = np.where(
                df['Total_Patient_Revenue'] > 0,
                (df['Total_Patient_Revenue'] - df['Total_Operating_Expenses']) / df['Total_Patient_Revenue'],
                np.nan
            )
        
        # Cost per revenue dollar
        df['Cost_Per_Revenue_Dollar'] = np.where(
            df['Total_Patient_Revenue'] > 0,
            df['Total_Operating_Expenses'] / df['Total_Patient_Revenue'],
            np.nan
        )
    
    # Revenue categories
    if 'Total_Patient_Revenue' in df.columns:
        def categorize_revenue(rev):
            if pd.isna(rev):
                return 'Unknown'
            elif rev < 10_000_000:
                return 'Small (<$10M)'
            elif rev < 25_000_000:
                return 'Medium ($10-25M)'
            elif rev < 50_000_000:
                return 'Large ($25-50M)'
            else:
                return 'Very Large (>$50M)'
        
        df['Revenue_Category'] = df['Total_Patient_Revenue'].apply(categorize_revenue)
    
    # Margin categories
    if 'Operating_Margin' in df.columns:
        def categorize_margin(margin):
            if pd.isna(margin):
                return 'Unknown'
            elif margin < 0:
                return 'Negative'
            elif margin < 0.05:
                return 'Low (0-5%)'
            elif margin < 0.15:
                return 'Moderate (5-15%)'
            elif margin < 0.30:
                return 'Good (15-30%)'
            else:
                return 'Strong (>30%)'
        
        df['Margin_Category'] = df['Operating_Margin'].apply(categorize_margin)
    
    # Financial viability flag
    if 'Operating_Margin' in df.columns:
        df['Financial_Viability'] = np.where(
            df['Operating_Margin'] >= 0,
            'Viable',
            'At Risk'
        )
    
    # Quality composite score (if quality measures exist)
    quality_cols = [col for col in df.columns if col in MBQIP_MEASURES.keys()]
    if quality_cols:
        # Simple average of available quality scores (normalized)
        df['Quality_Measures_Available'] = df[quality_cols].notna().sum(axis=1)
    
    logger.info(f"  Added {len([c for c in df.columns if c.endswith('_Category') or c == 'Financial_Viability'])} derived columns")
    
    return df


def generate_summary_report(df, output_path):
    """
    Generate summary report for the composite dataset
    """
    logger.info("Generating summary report...")
    
    report = {
        "generated": datetime.now().isoformat(),
        "dataset_info": {
            "total_records": len(df),
            "unique_facilities": df['CCN'].nunique() if 'CCN' in df.columns else len(df),
            "years_covered": sorted(df['Year'].unique().tolist()) if 'Year' in df.columns else [],
            "columns": list(df.columns)
        },
        "state_distribution": {},
        "financial_summary": {},
        "quality_measures_summary": {}
    }
    
    # State distribution
    if 'State' in df.columns:
        state_dist = df['State'].value_counts().to_dict()
        report['state_distribution'] = state_dist
    
    # Financial summary
    for col in ['Total_Patient_Revenue', 'Total_Operating_Expenses', 'Operating_Margin']:
        if col in df.columns:
            report['financial_summary'][col] = {
                "mean": float(df[col].mean()) if df[col].notna().any() else None,
                "median": float(df[col].median()) if df[col].notna().any() else None,
                "min": float(df[col].min()) if df[col].notna().any() else None,
                "max": float(df[col].max()) if df[col].notna().any() else None,
                "missing": int(df[col].isna().sum())
            }
    
    # Quality measures coverage
    for measure in MBQIP_MEASURES.keys():
        if measure in df.columns:
            report['quality_measures_summary'][measure] = {
                "coverage_count": int(df[measure].notna().sum()),
                "coverage_pct": float(df[measure].notna().sum() / len(df) * 100),
                "mean": float(df[measure].mean()) if df[measure].notna().any() else None,
                "median": float(df[measure].median()) if df[measure].notna().any() else None
            }
    
    # Save report
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"  Saved summary report to {output_path}")
    
    return report


def main():
    """
    Main execution function
    """
    print("\n" + "=" * 70)
    print("MBQIP QUALITY MEASURES + HCRIS FINANCIAL DATA MERGER")
    print("Day 3-4: Creating CAH Composite Baseline Dataset")
    print("=" * 70 + "\n")
    
    # Step 1: Load CAH provider list
    logger.info("Step 1: Loading CAH Provider List")
    cah_providers = load_cah_provider_list()
    
    # Step 2: Load or download quality measures data
    logger.info("\nStep 2: Loading/Downloading Quality Measures Data")
    quality_raw = load_existing_timely_care_data()
    
    if quality_raw is None:
        logger.info("  No existing data found, downloading from CMS API...")
        quality_raw = download_cms_timely_effective_care()
    
    # Step 3: Filter for MT/WA and extract measures
    logger.info("\nStep 3: Processing Quality Measures")
    quality_measures = None
    
    if quality_raw is not None:
        mt_wa_quality = filter_mt_wa_cahs(quality_raw)
        if len(mt_wa_quality) > 0:
            quality_measures = extract_mbqip_measures(mt_wa_quality)
    
    # If no quality data available, create placeholder structure
    if quality_measures is None or len(quality_measures) == 0:
        logger.warning("  No quality measures data from API, creating placeholder structure")
        quality_measures = create_placeholder_quality_data(cah_providers)
    
    # Step 4: Load HCRIS financial data
    logger.info("\nStep 4: Loading HCRIS Financial Data")
    hcris_data = load_hcris_financial_data()
    
    if hcris_data is None:
        logger.error("Cannot proceed without HCRIS financial data")
        return
    
    # Step 5: Load facility characteristics
    logger.info("\nStep 5: Loading Facility Characteristics")
    characteristics = load_facility_characteristics()
    
    # Step 6: Create composite dataset
    logger.info("\nStep 6: Creating Composite Dataset")
    composite = create_composite_dataset(hcris_data, quality_measures, characteristics)
    
    # Step 7: Save outputs
    logger.info("\nStep 7: Saving Outputs")
    
    # Main composite file
    output_path = PROCESSED_DIR / "cah_composite_baseline.csv"
    composite.to_csv(output_path, index=False)
    logger.info(f"[OK] Saved composite dataset to {output_path}")
    logger.info(f"  Total records: {len(composite)}")
    logger.info(f"  Total columns: {len(composite.columns)}")
    
    # Summary report
    report_path = REPORTS_DIR / "composite_baseline_summary.json"
    report = generate_summary_report(composite, report_path)
    
    # Print summary
    print("\n" + "=" * 70)
    print("COMPOSITE DATASET SUMMARY")
    print("=" * 70)
    print(f"\nTotal Records: {len(composite)}")
    print(f"Unique Facilities: {composite['CCN'].nunique()}")
    
    if 'State' in composite.columns:
        print(f"\nState Distribution:")
        for state, count in composite['State'].value_counts().items():
            print(f"  {state}: {count} records")
    
    if 'Year' in composite.columns:
        print(f"\nYears Covered: {sorted(composite['Year'].unique())}")
    
    print(f"\nFinancial Columns:")
    financial_cols = ['Total_Patient_Revenue', 'Total_Operating_Expenses', 'Operating_Margin', 
                      'Net_Revenue', 'Margin_Category', 'Financial_Viability']
    for col in financial_cols:
        if col in composite.columns:
            print(f"  [OK] {col}")
    
    print(f"\nQuality Measure Columns:")
    for measure in MBQIP_MEASURES.keys():
        if measure in composite.columns:
            coverage = composite[measure].notna().sum()
            print(f"  [OK] {measure}: {coverage} values ({coverage/len(composite)*100:.1f}%)")
        else:
            print(f"  [ ] {measure}: Not available")
    
    print(f"\nFacility Characteristic Columns:")
    char_cols = ['Facility_Name', 'City', 'County', 'Ownership', 'Emergency_Services', 
                 'Birthing_Friendly', 'Overall_Rating', 'Bed_Count']
    for col in char_cols:
        if col in composite.columns:
            non_null = composite[col].notna().sum()
            print(f"  [OK] {col}: {non_null} values")
    
    print(f"\n{'=' * 70}")
    print(f"OUTPUT: {output_path}")
    print(f"REPORT: {report_path}")
    print("=" * 70 + "\n")
    
    return composite


if __name__ == "__main__":
    main()

