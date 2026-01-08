#!/usr/bin/env python3
"""
CAH Baseline Metrics Extraction Script
Phase 1: Data Liberation - Week 1

Extracts key financial metrics from CMS HCRIS cost reports for 
Critical Access Hospitals (CAHs) in Montana (MT) and Washington (WA).

Data Sources:
- HOSP10_YYYY_rpt.csv: Report-level provider information
- HOSP10_YYYY_nmrc.csv: Numeric worksheet values
- HOSP10_YYYY_alpha.csv: Alphanumeric worksheet values

Output:
- data/processed/cah_baseline_metrics.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"data_acquisition_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Directory configuration
DATA_DIR = Path("data/cms_cost_reports")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Column definitions for HCRIS files (no headers in source files)
RPT_COLUMNS = [
    'RPT_REC_NUM',      # Unique report identifier
    'PRVDR_CTRL_TYPE_CD', # Provider control type
    'PRVDR_NUM',        # CMS Certification Number (CCN/Provider Number)
    'NPI',              # National Provider Identifier
    'RPT_STUS_CD',      # Report status code
    'FY_BGN_DT',        # Fiscal year begin date
    'FY_END_DT',        # Fiscal year end date
    'PROC_DT',          # Processing date
    'INITL_RPT_SW',     # Initial report switch
    'LAST_RPT_SW',      # Last report switch
    'TRNSMTL_NUM',      # Transmittal number
    'FI_NUM',           # Fiscal intermediary number
    'ADR_VNDR_CD',      # Vendor code
    'FI_CREAT_DT',      # FI creation date
    'UTIL_CD',          # Utilization code
    'NPR_DT',           # NPR date
    'SPEC_IND',         # Special indicator
    'FI_RCPT_DT'        # FI receipt date
]

NMRC_COLUMNS = [
    'RPT_REC_NUM',      # Links to RPT file
    'WKSHT_CD',         # Worksheet code (e.g., G300000)
    'LINE_NUM',         # Line number
    'CLMN_NUM',         # Column number
    'ITM_VAL_NUM'       # Numeric value
]

ALPHA_COLUMNS = [
    'RPT_REC_NUM',      # Links to RPT file  
    'WKSHT_CD',         # Worksheet code
    'LINE_NUM',         # Line number
    'CLMN_NUM',         # Column number
    'ITM_ALPHNMRC_ITM_TXT'  # Alphanumeric value
]

# Provider number ranges for MT and WA CAHs
# CCN format: SSPPPP where SS = state code, PPPP = provider number
# MT state code: 27, WA state code: 50
# CAH provider type: 1301-1399
MT_CAH_PREFIX = '27'
WA_CAH_PREFIX = '50'
CAH_TYPE_RANGE = range(1301, 1400)  # CAH designation


def is_cah(prvdr_num: str) -> bool:
    """Check if provider number indicates a Critical Access Hospital."""
    if pd.isna(prvdr_num) or not isinstance(prvdr_num, str):
        return False
    prvdr_num = prvdr_num.strip()
    if len(prvdr_num) < 6:
        return False
    
    state_code = prvdr_num[:2]
    try:
        provider_type = int(prvdr_num[2:6])
    except ValueError:
        return False
    
    # Check if it's a CAH in MT or WA
    is_mt_wa = state_code in [MT_CAH_PREFIX, WA_CAH_PREFIX]
    is_cah_type = provider_type in CAH_TYPE_RANGE
    
    return is_mt_wa and is_cah_type


def get_state_name(prvdr_num: str) -> str:
    """Get state name from provider number."""
    if pd.isna(prvdr_num) or not isinstance(prvdr_num, str):
        return 'Unknown'
    state_code = prvdr_num[:2]
    if state_code == MT_CAH_PREFIX:
        return 'Montana'
    elif state_code == WA_CAH_PREFIX:
        return 'Washington'
    return 'Unknown'


def load_hcris_data(year: int) -> tuple:
    """Load HCRIS data files for a given year."""
    year_dir = DATA_DIR / str(year)
    
    logger.info(f"Loading {year} HCRIS data from {year_dir}")
    
    # Load RPT file (provider information)
    rpt_file = year_dir / f"HOSP10_{year}_rpt.csv"
    rpt_df = pd.read_csv(rpt_file, names=RPT_COLUMNS, dtype=str, low_memory=False)
    logger.info(f"  Loaded {len(rpt_df):,} report records")
    
    # Load NMRC file (numeric data)
    nmrc_file = year_dir / f"HOSP10_{year}_nmrc.csv"
    nmrc_df = pd.read_csv(nmrc_file, names=NMRC_COLUMNS, dtype={
        'RPT_REC_NUM': str,
        'WKSHT_CD': str,
        'LINE_NUM': str,
        'CLMN_NUM': str,
        'ITM_VAL_NUM': float
    }, low_memory=False)
    logger.info(f"  Loaded {len(nmrc_df):,} numeric records")
    
    # Load ALPHA file (alphanumeric data)
    alpha_file = year_dir / f"HOSP10_{year}_alpha.csv"
    alpha_df = pd.read_csv(alpha_file, names=ALPHA_COLUMNS, dtype=str, low_memory=False)
    logger.info(f"  Loaded {len(alpha_df):,} alphanumeric records")
    
    return rpt_df, nmrc_df, alpha_df


def filter_mt_wa_cahs(rpt_df: pd.DataFrame) -> pd.DataFrame:
    """Filter RPT data for MT and WA CAHs."""
    # Apply CAH filter
    cah_mask = rpt_df['PRVDR_NUM'].apply(is_cah)
    cah_df = rpt_df[cah_mask].copy()
    
    # Add state information
    cah_df['State'] = cah_df['PRVDR_NUM'].apply(get_state_name)
    
    logger.info(f"  Found {len(cah_df)} MT/WA CAH reports")
    logger.info(f"    Montana: {len(cah_df[cah_df['State'] == 'Montana'])}")
    logger.info(f"    Washington: {len(cah_df[cah_df['State'] == 'Washington'])}")
    
    return cah_df


def extract_worksheet_value(nmrc_df: pd.DataFrame, rpt_rec_num: str, 
                           wksht_cd: str, line_num: str, clmn_num: str = None) -> float:
    """Extract a specific value from the numeric worksheet data."""
    mask = (nmrc_df['RPT_REC_NUM'] == rpt_rec_num) & \
           (nmrc_df['WKSHT_CD'] == wksht_cd) & \
           (nmrc_df['LINE_NUM'] == line_num)
    
    if clmn_num:
        mask = mask & (nmrc_df['CLMN_NUM'] == clmn_num)
    
    result = nmrc_df.loc[mask, 'ITM_VAL_NUM']
    
    if len(result) == 0:
        return np.nan
    return result.iloc[0]


def extract_financial_metrics(cah_rpt_df: pd.DataFrame, nmrc_df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Extract key financial metrics from Worksheet G-3 for CAHs.
    
    Worksheet G-3 contains:
    - Line 1: Total Patient Revenue (services to patients)
    - Line 3: Total Operating Expenses
    
    Note: HCRIS uses zero-padded line numbers, e.g., Line 1 = '00100', Line 3 = '00300'
    Worksheet G-3 code is 'G300000' (some systems use 'G3' prefix)
    """
    results = []
    
    # Get unique report record numbers for CAHs
    cah_rpt_nums = cah_rpt_df['RPT_REC_NUM'].unique()
    
    logger.info(f"  Extracting metrics for {len(cah_rpt_nums)} CAH reports")
    
    # Filter NMRC to only include CAH records for efficiency
    nmrc_cah = nmrc_df[nmrc_df['RPT_REC_NUM'].isin(cah_rpt_nums)].copy()
    
    # Worksheet G-3 codes - try different formats
    g3_codes = ['G300000', 'G3', 'G30000']
    
    # Line number formats to try
    line1_nums = ['00100', '0100', '100', '1']  # Total patient revenue
    line3_nums = ['00300', '0300', '300', '3']  # Total operating expenses
    
    # Column typically 0 or 1 for totals
    total_cols = ['00000', '0', '00001', '1', '00100', '100']
    
    # Find the actual worksheet code used
    available_wkshts = nmrc_cah['WKSHT_CD'].unique()
    g3_wksht = None
    for code in g3_codes:
        if code in available_wkshts:
            g3_wksht = code
            break
    
    if g3_wksht is None:
        # Try to find any G3 related worksheet
        g3_matches = [w for w in available_wkshts if 'G3' in str(w).upper()]
        if g3_matches:
            g3_wksht = g3_matches[0]
        else:
            logger.warning("  Could not find Worksheet G-3 in data")
            # List available worksheets for debugging
            logger.info(f"  Available worksheets: {sorted(available_wkshts)[:20]}...")
    
    logger.info(f"  Using worksheet code: {g3_wksht}")
    
    for _, row in cah_rpt_df.iterrows():
        rpt_rec_num = row['RPT_REC_NUM']
        prvdr_num = row['PRVDR_NUM']
        
        # Get facility data from NMRC
        facility_nmrc = nmrc_cah[nmrc_cah['RPT_REC_NUM'] == rpt_rec_num]
        
        # Try to extract total patient revenue (Line 1) and total operating expenses (Line 3)
        total_revenue = np.nan
        total_expenses = np.nan
        
        if g3_wksht:
            g3_data = facility_nmrc[facility_nmrc['WKSHT_CD'] == g3_wksht]
            
            # Try different line/column combinations for revenue
            for line_num in line1_nums:
                if pd.notna(total_revenue):
                    break
                for col_num in total_cols:
                    mask = (g3_data['LINE_NUM'] == line_num) & (g3_data['CLMN_NUM'] == col_num)
                    values = g3_data.loc[mask, 'ITM_VAL_NUM']
                    if len(values) > 0 and pd.notna(values.iloc[0]):
                        total_revenue = values.iloc[0]
                        break
            
            # Try different line/column combinations for expenses
            for line_num in line3_nums:
                if pd.notna(total_expenses):
                    break
                for col_num in total_cols:
                    mask = (g3_data['LINE_NUM'] == line_num) & (g3_data['CLMN_NUM'] == col_num)
                    values = g3_data.loc[mask, 'ITM_VAL_NUM']
                    if len(values) > 0 and pd.notna(values.iloc[0]):
                        total_expenses = values.iloc[0]
                        break
        
        # Calculate operating margin
        if pd.notna(total_revenue) and pd.notna(total_expenses) and total_revenue != 0:
            operating_margin = (total_revenue - total_expenses) / total_revenue
        else:
            operating_margin = np.nan
        
        results.append({
            'Year': year,
            'RPT_REC_NUM': rpt_rec_num,
            'Provider_Num': prvdr_num,
            'State': row['State'],
            'FY_Begin_Date': row['FY_BGN_DT'],
            'FY_End_Date': row['FY_END_DT'],
            'Total_Patient_Revenue': total_revenue,
            'Total_Operating_Expenses': total_expenses,
            'Operating_Margin': operating_margin
        })
    
    return pd.DataFrame(results)


def extract_additional_metrics(cah_rpt_df: pd.DataFrame, nmrc_df: pd.DataFrame, 
                               alpha_df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Extract additional metrics from various worksheets.
    
    This attempts to get more comprehensive data including:
    - Worksheet S-2: Provider characteristics
    - Worksheet S-3: Hospital statistics (beds, discharges, patient days)
    - Worksheet G-2: Cost allocation data
    """
    cah_rpt_nums = cah_rpt_df['RPT_REC_NUM'].unique()
    
    # Filter to CAH records
    nmrc_cah = nmrc_df[nmrc_df['RPT_REC_NUM'].isin(cah_rpt_nums)].copy()
    alpha_cah = alpha_df[alpha_df['RPT_REC_NUM'].isin(cah_rpt_nums)].copy()
    
    results = []
    
    for _, row in cah_rpt_df.iterrows():
        rpt_rec_num = row['RPT_REC_NUM']
        prvdr_num = row['PRVDR_NUM']
        
        facility_nmrc = nmrc_cah[nmrc_cah['RPT_REC_NUM'] == rpt_rec_num]
        facility_alpha = alpha_cah[alpha_cah['RPT_REC_NUM'] == rpt_rec_num]
        
        # Try to get facility name from Worksheet S-2 (often in alpha file)
        facility_name = np.nan
        s2_alpha = facility_alpha[facility_alpha['WKSHT_CD'].str.contains('S2', na=False, case=False)]
        if len(s2_alpha) > 0:
            # Usually line 1, column 1 has facility name
            name_mask = (s2_alpha['LINE_NUM'].isin(['00100', '100', '1'])) & \
                       (s2_alpha['CLMN_NUM'].isin(['00100', '100', '1', '00001', '1']))
            names = s2_alpha.loc[name_mask, 'ITM_ALPHNMRC_ITM_TXT']
            if len(names) > 0:
                facility_name = names.iloc[0]
        
        # Try to get bed count from Worksheet S-3 (typically line 1, col 1 or 2)
        bed_count = np.nan
        s3_nmrc = facility_nmrc[facility_nmrc['WKSHT_CD'].str.contains('S3', na=False, case=False)]
        if len(s3_nmrc) > 0:
            bed_mask = (s3_nmrc['LINE_NUM'].isin(['00100', '100', '1'])) & \
                      (s3_nmrc['CLMN_NUM'].isin(['00100', '100', '1', '00200', '200', '2']))
            beds = s3_nmrc.loc[bed_mask, 'ITM_VAL_NUM']
            if len(beds) > 0:
                bed_count = beds.iloc[0]
        
        results.append({
            'RPT_REC_NUM': rpt_rec_num,
            'Facility_Name': facility_name,
            'Bed_Count': bed_count
        })
    
    return pd.DataFrame(results)


def process_all_years() -> pd.DataFrame:
    """Process HCRIS data for all years and combine results."""
    years = [2021, 2022, 2023]
    all_results = []
    
    for year in years:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing FY {year}")
        logger.info(f"{'='*60}")
        
        try:
            # Load data
            rpt_df, nmrc_df, alpha_df = load_hcris_data(year)
            
            # Filter for MT/WA CAHs
            cah_rpt_df = filter_mt_wa_cahs(rpt_df)
            
            if len(cah_rpt_df) == 0:
                logger.warning(f"  No CAHs found for {year}")
                continue
            
            # Extract financial metrics
            metrics_df = extract_financial_metrics(cah_rpt_df, nmrc_df, year)
            
            # Extract additional metrics
            additional_df = extract_additional_metrics(cah_rpt_df, nmrc_df, alpha_df, year)
            
            # Merge additional metrics
            metrics_df = metrics_df.merge(additional_df, on='RPT_REC_NUM', how='left')
            
            all_results.append(metrics_df)
            
            logger.info(f"  Extracted {len(metrics_df)} CAH records for {year}")
            
        except FileNotFoundError as e:
            logger.error(f"  File not found for {year}: {e}")
        except Exception as e:
            logger.error(f"  Error processing {year}: {e}")
            raise
    
    if not all_results:
        logger.error("No data extracted!")
        return pd.DataFrame()
    
    # Combine all years
    combined_df = pd.concat(all_results, ignore_index=True)
    
    return combined_df


def generate_summary_statistics(df: pd.DataFrame) -> None:
    """Generate and log summary statistics."""
    logger.info("\n" + "="*60)
    logger.info("SUMMARY STATISTICS")
    logger.info("="*60)
    
    # Overall counts
    total_records = len(df)
    unique_facilities = df['Provider_Num'].nunique()
    
    logger.info(f"\nTotal Records: {total_records}")
    logger.info(f"Unique Facilities: {unique_facilities}")
    
    # By state
    logger.info("\nRecords by State:")
    state_counts = df.groupby('State').agg({
        'Provider_Num': 'count',
        'Operating_Margin': ['mean', 'median', 'std']
    })
    logger.info(f"\n{state_counts}")
    
    # By year
    logger.info("\nRecords by Year:")
    year_counts = df.groupby('Year').size()
    logger.info(f"\n{year_counts}")
    
    # Financial metrics summary
    logger.info("\nFinancial Metrics Summary:")
    
    valid_revenue = df['Total_Patient_Revenue'].dropna()
    valid_expenses = df['Total_Operating_Expenses'].dropna()
    valid_margin = df['Operating_Margin'].dropna()
    
    logger.info(f"\nTotal Patient Revenue:")
    logger.info(f"  Records with data: {len(valid_revenue)}")
    if len(valid_revenue) > 0:
        logger.info(f"  Mean: ${valid_revenue.mean():,.0f}")
        logger.info(f"  Median: ${valid_revenue.median():,.0f}")
        logger.info(f"  Min: ${valid_revenue.min():,.0f}")
        logger.info(f"  Max: ${valid_revenue.max():,.0f}")
    
    logger.info(f"\nTotal Operating Expenses:")
    logger.info(f"  Records with data: {len(valid_expenses)}")
    if len(valid_expenses) > 0:
        logger.info(f"  Mean: ${valid_expenses.mean():,.0f}")
        logger.info(f"  Median: ${valid_expenses.median():,.0f}")
    
    logger.info(f"\nOperating Margin:")
    logger.info(f"  Records with data: {len(valid_margin)}")
    if len(valid_margin) > 0:
        logger.info(f"  Mean: {valid_margin.mean():.2%}")
        logger.info(f"  Median: {valid_margin.median():.2%}")
        logger.info(f"  Min: {valid_margin.min():.2%}")
        logger.info(f"  Max: {valid_margin.max():.2%}")
        
        # Count positive/negative margins
        positive = (valid_margin > 0).sum()
        negative = (valid_margin < 0).sum()
        logger.info(f"  Positive margins: {positive} ({positive/len(valid_margin):.1%})")
        logger.info(f"  Negative margins: {negative} ({negative/len(valid_margin):.1%})")


def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("CAH Baseline Metrics Extraction")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # Process all years
    df = process_all_years()
    
    if len(df) == 0:
        logger.error("No data extracted. Exiting.")
        return
    
    # Reorder columns for output
    output_columns = [
        'Year',
        'Provider_Num',
        'State',
        'Facility_Name',
        'FY_Begin_Date',
        'FY_End_Date',
        'Total_Patient_Revenue',
        'Total_Operating_Expenses',
        'Operating_Margin',
        'Bed_Count',
        'RPT_REC_NUM'
    ]
    
    # Ensure all columns exist
    for col in output_columns:
        if col not in df.columns:
            df[col] = np.nan
    
    df = df[output_columns]
    
    # Sort by state, provider, year
    df = df.sort_values(['State', 'Provider_Num', 'Year'])
    
    # Generate summary statistics
    generate_summary_statistics(df)
    
    # Save output
    output_file = OUTPUT_DIR / "cah_baseline_metrics.csv"
    df.to_csv(output_file, index=False)
    logger.info(f"\nOutput saved to: {output_file}")
    
    logger.info("\n" + "="*60)
    logger.info(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    return df


if __name__ == "__main__":
    df = main()

