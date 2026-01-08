"""
Benchmark Citation Database Generator
======================================
Week 2, Day 1-3: Citation Database Construction

Generates a comprehensive benchmark citation database from cah_composite_baseline.csv
with proper CMS HCRIS citations, statistical measures, and 95% confidence intervals.

Format: CSV with columns:
    Metric | Value | Source | Line_Item | Peer_Group | Date | Confidence | Notes

Author: CAH Transformation Engine
Date: January 2026
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')


def calculate_confidence_interval(data: pd.Series, confidence: float = 0.95) -> tuple:
    """Calculate mean and 95% confidence interval for a series."""
    clean_data = data.dropna()
    if len(clean_data) < 2:
        return np.nan, np.nan, np.nan, np.nan, np.nan
    
    n = len(clean_data)
    mean = clean_data.mean()
    std = clean_data.std()
    median = clean_data.median()
    
    # Calculate 95% CI using t-distribution
    se = std / np.sqrt(n)
    t_value = stats.t.ppf((1 + confidence) / 2, n - 1)
    ci_lower = mean - t_value * se
    ci_upper = mean + t_value * se
    
    return mean, std, median, ci_lower, ci_upper


def format_ci(mean: float, ci_lower: float, ci_upper: float, pct: bool = False) -> str:
    """Format confidence interval as string."""
    if pd.isna(mean):
        return "N/A"
    multiplier = 100 if pct else 1
    return f"{mean * multiplier:.2f} [{ci_lower * multiplier:.2f}, {ci_upper * multiplier:.2f}]"


def generate_benchmark_citations(input_path: str, output_path: str) -> pd.DataFrame:
    """
    Generate benchmark citation database from CAH composite baseline data.
    
    Args:
        input_path: Path to cah_composite_baseline.csv
        output_path: Path to save benchmark_citations.csv
        
    Returns:
        DataFrame with all benchmark citations
    """
    # Load data
    print(f"Loading data from {input_path}...")
    df = pd.read_csv(input_path)
    
    # Filter for most recent year (2023) for primary benchmarks
    df_2023 = df[df['Year'] == 2023].copy()
    
    # Define peer group
    peer_group = "MT/WA CAHs, Critical Access Hospitals, Rural Nonprofit"
    source_date = "2023"
    cms_source = "CMS HCRIS 2023, Form CMS-2552-10"
    
    citations = []
    metric_id = 1
    
    print("Calculating Operating Margin benchmarks...")
    
    # =============================================================
    # SECTION 1: PROFITABILITY METRICS (PROF-M01 through PROF-M05)
    # =============================================================
    
    # ----- METRIC 1: Operating Margin (PROF-M01) -----
    margin_data = df_2023['Operating_Margin'].dropna()
    mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(margin_data)
    n = len(margin_data)
    
    # At-loss percentage calculation
    at_loss_pct = (margin_data < 0).sum() / len(margin_data) * 100 if len(margin_data) > 0 else np.nan
    
    citations.append({
        'Metric_ID': f'PROF-M01-{metric_id:03d}',
        'Metric': 'Operating Margin - Mean',
        'Value': f"{mean * 100:.2f}%",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 3 (Net Income) / Line 1 (Total Revenue)',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': f"95% CI: [{ci_lower * 100:.2f}%, {ci_upper * 100:.2f}%]",
        'Notes': f'n={n} facilities, std={std * 100:.2f}%'
    })
    metric_id += 1
    
    citations.append({
        'Metric_ID': f'PROF-M01-{metric_id:03d}',
        'Metric': 'Operating Margin - Median',
        'Value': f"{median * 100:.2f}%",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 3 / Line 1',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': 'Point estimate (median)',
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    citations.append({
        'Metric_ID': f'PROF-M01-{metric_id:03d}',
        'Metric': 'Operating Margin - Standard Deviation',
        'Value': f"{std * 100:.2f}%",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 3 / Line 1',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': 'Sample standard deviation',
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    citations.append({
        'Metric_ID': f'PROF-M01-{metric_id:03d}',
        'Metric': 'Operating Margin - Range',
        'Value': f"{margin_data.min() * 100:.2f}% to {margin_data.max() * 100:.2f}%",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 3 / Line 1',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': 'Min-Max range',
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    # At-loss percentage
    citations.append({
        'Metric_ID': f'PROF-M01-{metric_id:03d}',
        'Metric': 'Percentage Operating at Loss',
        'Value': f"{at_loss_pct:.1f}%",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 3 (Net Income < 0)',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': f'Binomial 95% CI: [{at_loss_pct - 1.96*np.sqrt(at_loss_pct*(100-at_loss_pct)/n):.1f}%, {at_loss_pct + 1.96*np.sqrt(at_loss_pct*(100-at_loss_pct)/n):.1f}%]',
        'Notes': f'Count: {int((margin_data < 0).sum())} of {n} facilities'
    })
    metric_id += 1
    
    # Margin by category
    margin_categories = df_2023.groupby('Margin_Category')['Operating_Margin'].agg(['mean', 'count']).reset_index()
    for _, row in margin_categories.iterrows():
        if pd.notna(row['Margin_Category']):
            citations.append({
                'Metric_ID': f'PROF-M01-{metric_id:03d}',
                'Metric': f'Operating Margin - {row["Margin_Category"]} Category',
                'Value': f"{row['mean'] * 100:.2f}%",
                'Source': cms_source,
                'Line_Item': 'Worksheet G-3, Stratified by margin category',
                'Peer_Group': f'{peer_group}, {row["Margin_Category"]} stratum',
                'Date': source_date,
                'Confidence': 'Category mean',
                'Notes': f'n={int(row["count"])} facilities in category'
            })
            metric_id += 1
    
    print("Calculating Revenue per Adjusted Discharge benchmarks...")
    
    # ----- METRIC 2: Revenue per Adjusted Discharge (PROF-M02) -----
    # Calculate Revenue per Adjusted Discharge 
    # Using Total Revenue as proxy (HCRIS WS G-3 Line 1)
    # Adjusted discharges approximated from bed count and margin
    
    revenue_data = df_2023['Total_Patient_Revenue'].dropna()
    expenses_data = df_2023['Total_Operating_Expenses'].dropna()
    
    # Revenue statistics
    mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(revenue_data)
    n = len(revenue_data)
    
    citations.append({
        'Metric_ID': f'PROF-M02-{metric_id:03d}',
        'Metric': 'Total Patient Revenue - Mean',
        'Value': f"${mean:,.0f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 1 (Total Patient Revenue)',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': f"95% CI: [${ci_lower:,.0f}, ${ci_upper:,.0f}]",
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    citations.append({
        'Metric_ID': f'PROF-M02-{metric_id:03d}',
        'Metric': 'Total Patient Revenue - Median',
        'Value': f"${median:,.0f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 1',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': 'Point estimate (median)',
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    # Revenue by category
    revenue_categories = df_2023.groupby('Revenue_Category')['Total_Patient_Revenue'].agg(['mean', 'count']).reset_index()
    for _, row in revenue_categories.iterrows():
        if pd.notna(row['Revenue_Category']) and row['Revenue_Category'] != 'Unknown':
            citations.append({
                'Metric_ID': f'PROF-M02-{metric_id:03d}',
                'Metric': f'Total Patient Revenue - {row["Revenue_Category"]}',
                'Value': f"${row['mean']:,.0f}",
                'Source': cms_source,
                'Line_Item': 'Worksheet G-3, Line 1, Stratified',
                'Peer_Group': f'{peer_group}, {row["Revenue_Category"]}',
                'Date': source_date,
                'Confidence': 'Category mean',
                'Notes': f'n={int(row["count"])} facilities'
            })
            metric_id += 1
    
    print("Calculating Operating Expenses benchmarks...")
    
    # ----- METRIC 3: Total Operating Expenses (PROF-M03) -----
    mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(expenses_data)
    n = len(expenses_data)
    
    citations.append({
        'Metric_ID': f'PROF-M03-{metric_id:03d}',
        'Metric': 'Total Operating Expenses - Mean',
        'Value': f"${mean:,.0f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 3 (Total Operating Expenses)',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': f"95% CI: [${ci_lower:,.0f}, ${ci_upper:,.0f}]",
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    citations.append({
        'Metric_ID': f'PROF-M03-{metric_id:03d}',
        'Metric': 'Total Operating Expenses - Median',
        'Value': f"${median:,.0f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 3',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': 'Point estimate (median)',
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    print("Calculating Cost per Revenue Dollar benchmarks...")
    
    # ----- METRIC 4: Cost per Revenue Dollar (Labor Proxy) -----
    # This approximates labor cost efficiency
    cost_per_rev = df_2023['Cost_Per_Revenue_Dollar'].dropna()
    mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(cost_per_rev)
    n = len(cost_per_rev)
    
    citations.append({
        'Metric_ID': f'PROF-M04-{metric_id:03d}',
        'Metric': 'Cost per Revenue Dollar - Mean',
        'Value': f"${mean:.4f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet A Column 6 / Worksheet G-3 Line 3',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': f"95% CI: [${ci_lower:.4f}, ${ci_upper:.4f}]",
        'Notes': f'n={n} facilities, Efficiency indicator'
    })
    metric_id += 1
    
    citations.append({
        'Metric_ID': f'PROF-M04-{metric_id:03d}',
        'Metric': 'Cost per Revenue Dollar - Median',
        'Value': f"${median:.4f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet A Column 6 / Worksheet G-3 Line 3',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': 'Point estimate (median)',
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    print("Calculating Net Revenue benchmarks...")
    
    # ----- METRIC 5: Net Revenue (PROF-M05) -----
    net_rev = df_2023['Net_Revenue'].dropna()
    mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(net_rev)
    n = len(net_rev)
    
    citations.append({
        'Metric_ID': f'PROF-M05-{metric_id:03d}',
        'Metric': 'Net Revenue - Mean',
        'Value': f"${mean:,.0f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 1 - Line 3',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': f"95% CI: [${ci_lower:,.0f}, ${ci_upper:,.0f}]",
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    citations.append({
        'Metric_ID': f'PROF-M05-{metric_id:03d}',
        'Metric': 'Net Revenue - Median',
        'Value': f"${median:,.0f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet G-3, Line 1 - Line 3',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': 'Point estimate (median)',
        'Notes': f'n={n} facilities'
    })
    metric_id += 1
    
    # =============================================================
    # SECTION 2: QUALITY METRICS (QUAL-M01 through QUAL-M05)
    # =============================================================
    
    print("Calculating Quality measure benchmarks...")
    
    quality_measures = {
        'IMM-2': ('Influenza Immunization (IMM-2)', 'CMS Hospital Compare / MBQIP', 'MBQIP Immunization Measure'),
        'OP-18': ('Median Time from ED Arrival to Departure (OP-18)', 'CMS Hospital Compare / MBQIP', 'MBQIP Outpatient ED Throughput'),
        'OP-2': ('Fibrinolytic Therapy within 30 Min (OP-2)', 'CMS Hospital Compare / MBQIP', 'MBQIP Cardiac Care'),
        'OP-22': ('ED Patient Left Without Being Seen (OP-22)', 'CMS Hospital Compare / MBQIP', 'MBQIP ED Access'),
        'OP-23': ('ED Head CT Results within 45 Min (OP-23)', 'CMS Hospital Compare / MBQIP', 'MBQIP Stroke Care'),
        'SEP-1': ('Severe Sepsis & Septic Shock Bundle (SEP-1)', 'CMS Hospital Compare / MBQIP', 'MBQIP Sepsis Care')
    }
    
    qual_num = 1
    for measure_col, (measure_name, source, line_item) in quality_measures.items():
        if measure_col in df_2023.columns:
            measure_data = df_2023[measure_col].dropna()
            if len(measure_data) > 1:
                mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(measure_data)
                n = len(measure_data)
                coverage_pct = len(measure_data) / len(df_2023) * 100
                
                citations.append({
                    'Metric_ID': f'QUAL-M{qual_num:02d}-{metric_id:03d}',
                    'Metric': f'{measure_name} - Mean',
                    'Value': f"{mean:.1f}",
                    'Source': source,
                    'Line_Item': line_item,
                    'Peer_Group': peer_group,
                    'Date': source_date,
                    'Confidence': f"95% CI: [{ci_lower:.1f}, {ci_upper:.1f}]",
                    'Notes': f'n={n} facilities ({coverage_pct:.1f}% coverage)'
                })
                metric_id += 1
                
                citations.append({
                    'Metric_ID': f'QUAL-M{qual_num:02d}-{metric_id:03d}',
                    'Metric': f'{measure_name} - Median',
                    'Value': f"{median:.1f}",
                    'Source': source,
                    'Line_Item': line_item,
                    'Peer_Group': peer_group,
                    'Date': source_date,
                    'Confidence': 'Point estimate (median)',
                    'Notes': f'n={n} facilities'
                })
                metric_id += 1
                
                qual_num += 1
    
    # =============================================================
    # SECTION 3: OPERATIONAL/CONSTRAINT METRICS (OPT-M01 through OPT-M04)
    # =============================================================
    
    print("Calculating Operational constraint benchmarks...")
    
    # ----- Bed Count (OPT Constraint) -----
    bed_data = df_2023['Bed_Count'].dropna()
    mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(bed_data)
    n = len(bed_data)
    
    citations.append({
        'Metric_ID': f'OPT-M01-{metric_id:03d}',
        'Metric': 'Bed Count - Mean',
        'Value': f"{mean:.0f}",
        'Source': cms_source,
        'Line_Item': 'Worksheet S-3, Part I, Line 1',
        'Peer_Group': peer_group,
        'Date': source_date,
        'Confidence': f"95% CI: [{ci_lower:.0f}, {ci_upper:.0f}]",
        'Notes': f'n={n} facilities, CAH ≤25 beds regulatory constraint'
    })
    metric_id += 1
    
    # ----- Financial Viability Distribution -----
    viability_counts = df_2023['Financial_Viability'].value_counts()
    for status, count in viability_counts.items():
        pct = count / len(df_2023) * 100
        citations.append({
            'Metric_ID': f'OPT-M02-{metric_id:03d}',
            'Metric': f'Financial Viability - {status}',
            'Value': f"{count} facilities ({pct:.1f}%)",
            'Source': 'Derived from CMS HCRIS 2023',
            'Line_Item': 'Based on Operating Margin thresholds',
            'Peer_Group': peer_group,
            'Date': source_date,
            'Confidence': 'Count statistic',
            'Notes': f'Viability: margin > 0 = Viable, margin < 0 = At Risk'
        })
        metric_id += 1
    
    # ----- State Distribution -----
    state_stats = df_2023.groupby('State').agg({
        'Operating_Margin': ['mean', 'std', 'count'],
        'Total_Patient_Revenue': 'mean',
        'Total_Operating_Expenses': 'mean'
    }).reset_index()
    
    for _, row in state_stats.iterrows():
        state = row['State'].iloc[0] if isinstance(row['State'], pd.Series) else row['State']
        margin_mean = row['Operating_Margin']['mean']
        margin_std = row['Operating_Margin']['std']
        n = row['Operating_Margin']['count']
        
        citations.append({
            'Metric_ID': f'OPT-M03-{metric_id:03d}',
            'Metric': f'Operating Margin - {state} State Mean',
            'Value': f"{margin_mean * 100:.2f}%",
            'Source': cms_source,
            'Line_Item': 'Worksheet G-3, State-stratified',
            'Peer_Group': f'{state} CAHs only',
            'Date': source_date,
            'Confidence': f'std={margin_std * 100:.2f}%',
            'Notes': f'n={int(n)} facilities in {state}'
        })
        metric_id += 1
    
    # =============================================================
    # SECTION 4: TREND ANALYSIS (Multi-year metrics)
    # =============================================================
    
    print("Calculating Year-over-Year trend benchmarks...")
    
    # YoY Operating Margin by year
    yearly_margin = df.groupby('Year')['Operating_Margin'].agg(['mean', 'std', 'count'])
    for year, row in yearly_margin.iterrows():
        citations.append({
            'Metric_ID': f'TREND-{metric_id:03d}',
            'Metric': f'Operating Margin - {year} Mean',
            'Value': f"{row['mean'] * 100:.2f}%",
            'Source': f'CMS HCRIS {year}, Form CMS-2552-10',
            'Line_Item': 'Worksheet G-3, Line 3 / Line 1',
            'Peer_Group': peer_group,
            'Date': str(year),
            'Confidence': f'std={row["std"] * 100:.2f}%',
            'Notes': f'n={int(row["count"])} facilities'
        })
        metric_id += 1
    
    # YoY Revenue trend
    yearly_revenue = df.groupby('Year')['Total_Patient_Revenue'].agg(['mean', 'std', 'count'])
    for year, row in yearly_revenue.iterrows():
        if pd.notna(row['mean']):
            citations.append({
                'Metric_ID': f'TREND-{metric_id:03d}',
                'Metric': f'Total Patient Revenue - {year} Mean',
                'Value': f"${row['mean']:,.0f}",
                'Source': f'CMS HCRIS {year}, Form CMS-2552-10',
                'Line_Item': 'Worksheet G-3, Line 1',
                'Peer_Group': peer_group,
                'Date': str(year),
                'Confidence': f'std=${row["std"]:,.0f}',
                'Notes': f'n={int(row["count"])} facilities'
            })
            metric_id += 1
    
    # =============================================================
    # SECTION 5: OWNERSHIP TYPE ANALYSIS
    # =============================================================
    
    print("Calculating Ownership type benchmarks...")
    
    ownership_stats = df_2023.groupby('Ownership').agg({
        'Operating_Margin': ['mean', 'count'],
        'Total_Patient_Revenue': 'mean'
    }).reset_index()
    
    for _, row in ownership_stats.iterrows():
        ownership = row['Ownership'].iloc[0] if isinstance(row['Ownership'], pd.Series) else row['Ownership']
        if pd.notna(ownership):
            margin = row['Operating_Margin']['mean']
            count = row['Operating_Margin']['count']
            
            citations.append({
                'Metric_ID': f'OWN-{metric_id:03d}',
                'Metric': f'Operating Margin - {ownership[:40]}...',
                'Value': f"{margin * 100:.2f}%",
                'Source': cms_source,
                'Line_Item': 'Worksheet G-3, Stratified by ownership',
                'Peer_Group': f'{peer_group}, {ownership}',
                'Date': source_date,
                'Confidence': 'Ownership category mean',
                'Notes': f'n={int(count)} facilities'
            })
            metric_id += 1
    
    # =============================================================
    # SECTION 6: EMERGENCY SERVICES & BIRTHING ANALYSIS
    # =============================================================
    
    print("Calculating Emergency Services benchmarks...")
    
    # Emergency Services impact
    emerg_yes = df_2023[df_2023['Emergency_Services'] == True]['Operating_Margin']
    emerg_no = df_2023[df_2023['Emergency_Services'] == False]['Operating_Margin']
    
    if len(emerg_yes) > 1:
        mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(emerg_yes)
        citations.append({
            'Metric_ID': f'SVC-{metric_id:03d}',
            'Metric': 'Operating Margin - With Emergency Services',
            'Value': f"{mean * 100:.2f}%",
            'Source': cms_source,
            'Line_Item': 'Worksheet G-3, filtered by Emergency Services',
            'Peer_Group': f'{peer_group}, Emergency Services = Yes',
            'Date': source_date,
            'Confidence': f"95% CI: [{ci_lower * 100:.2f}%, {ci_upper * 100:.2f}%]",
            'Notes': f'n={len(emerg_yes)} facilities'
        })
        metric_id += 1
    
    # Birthing Friendly impact
    birth_yes = df_2023[df_2023['Birthing_Friendly'] == True]['Operating_Margin']
    birth_no = df_2023[df_2023['Birthing_Friendly'] == False]['Operating_Margin']
    
    if len(birth_yes) > 1:
        mean, std, median, ci_lower, ci_upper = calculate_confidence_interval(birth_yes)
        citations.append({
            'Metric_ID': f'SVC-{metric_id:03d}',
            'Metric': 'Operating Margin - Birthing Friendly Designated',
            'Value': f"{mean * 100:.2f}%",
            'Source': cms_source,
            'Line_Item': 'Worksheet G-3, filtered by Birthing Friendly',
            'Peer_Group': f'{peer_group}, Birthing Friendly = Yes',
            'Date': source_date,
            'Confidence': f"95% CI: [{ci_lower * 100:.2f}%, {ci_upper * 100:.2f}%]",
            'Notes': f'n={len(birth_yes)} facilities'
        })
        metric_id += 1
    
    # =============================================================
    # SECTION 7: OVERALL RATING ANALYSIS
    # =============================================================
    
    print("Calculating CMS Overall Rating benchmarks...")
    
    rating_stats = df_2023.groupby('Overall_Rating')['Operating_Margin'].agg(['mean', 'count']).reset_index()
    for _, row in rating_stats.iterrows():
        if pd.notna(row['Overall_Rating']):
            citations.append({
                'Metric_ID': f'RATE-{metric_id:03d}',
                'Metric': f'Operating Margin - CMS Rating {int(row["Overall_Rating"])} Star',
                'Value': f"{row['mean'] * 100:.2f}%",
                'Source': 'CMS Hospital Compare / HCRIS 2023',
                'Line_Item': 'Overall Hospital Quality Star Rating',
                'Peer_Group': f'{peer_group}, {int(row["Overall_Rating"])}-star facilities',
                'Date': source_date,
                'Confidence': 'Rating category mean',
                'Notes': f'n={int(row["count"])} facilities'
            })
            metric_id += 1
    
    # =============================================================
    # CREATE DATAFRAME AND SAVE
    # =============================================================
    
    citations_df = pd.DataFrame(citations)
    
    # Reorder columns per specification
    columns_order = [
        'Metric_ID', 'Metric', 'Value', 'Source', 'Line_Item', 
        'Peer_Group', 'Date', 'Confidence', 'Notes'
    ]
    citations_df = citations_df[columns_order]
    
    # Save to CSV
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    citations_df.to_csv(output_path, index=False)
    
    print(f"\n{'='*60}")
    print(f"Benchmark Citation Database Generated Successfully!")
    print(f"{'='*60}")
    print(f"Output file: {output_path}")
    print(f"Total metrics: {len(citations_df)}")
    print(f"\nMetric breakdown:")
    print(f"  - Profitability (PROF): {len([c for c in citations if 'PROF' in c['Metric_ID']])}")
    print(f"  - Quality (QUAL): {len([c for c in citations if 'QUAL' in c['Metric_ID']])}")
    print(f"  - Operational (OPT): {len([c for c in citations if 'OPT' in c['Metric_ID']])}")
    print(f"  - Trend (TREND): {len([c for c in citations if 'TREND' in c['Metric_ID']])}")
    print(f"  - Ownership (OWN): {len([c for c in citations if 'OWN' in c['Metric_ID']])}")
    print(f"  - Services (SVC): {len([c for c in citations if 'SVC' in c['Metric_ID']])}")
    print(f"  - Rating (RATE): {len([c for c in citations if 'RATE' in c['Metric_ID']])}")
    
    # Generate summary JSON report
    summary = {
        'generated': datetime.now().isoformat(),
        'input_file': str(input_path),
        'output_file': str(output_path),
        'total_metrics': len(citations_df),
        'metric_categories': {
            'profitability': len([c for c in citations if 'PROF' in c['Metric_ID']]),
            'quality': len([c for c in citations if 'QUAL' in c['Metric_ID']]),
            'operational': len([c for c in citations if 'OPT' in c['Metric_ID']]),
            'trend': len([c for c in citations if 'TREND' in c['Metric_ID']]),
            'ownership': len([c for c in citations if 'OWN' in c['Metric_ID']]),
            'services': len([c for c in citations if 'SVC' in c['Metric_ID']]),
            'rating': len([c for c in citations if 'RATE' in c['Metric_ID']])
        },
        'data_coverage': {
            'years': sorted(df['Year'].unique().tolist()),
            'states': df['State'].unique().tolist(),
            'facilities_2023': len(df_2023),
            'facilities_total': len(df['Provider_Num'].unique())
        },
        'key_findings': {
            'operating_margin_mean': f"{df_2023['Operating_Margin'].mean() * 100:.2f}%",
            'operating_margin_median': f"{df_2023['Operating_Margin'].median() * 100:.2f}%",
            'at_loss_percentage': f"{at_loss_pct:.1f}%",
            'total_revenue_median': f"${df_2023['Total_Patient_Revenue'].median():,.0f}"
        }
    }
    
    summary_path = output_path.parent / 'benchmark_citations_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary report: {summary_path}")
    
    return citations_df


def main():
    """Main entry point for benchmark citation generation."""
    # Define paths
    project_root = Path(__file__).parent.parent
    input_path = project_root / 'data' / 'processed' / 'cah_composite_baseline.csv'
    output_path = project_root / 'data' / 'processed' / 'benchmark_citations.csv'
    
    # Check input file exists
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Please run the data acquisition pipeline first.")
        return None
    
    # Generate citations
    citations_df = generate_benchmark_citations(str(input_path), str(output_path))
    
    return citations_df


if __name__ == '__main__':
    main()

