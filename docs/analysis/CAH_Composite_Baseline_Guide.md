# CAH Composite Baseline Dataset Guide

## Overview

The `cah_composite_baseline.csv` file is the primary integrated dataset for Critical Access Hospital (CAH) analysis, combining:

1. **HCRIS Financial Data** - Revenue, expenses, and operating margins
2. **MBQIP Quality Measures** - OP-18, OP-1, OP-3, IMM-2, and related measures
3. **Facility Characteristics** - Location, ownership, beds, and services

## Dataset Location

```
data/processed/cah_composite_baseline.csv
```

## Dataset Statistics

- **Total Records**: 264 (88 facilities × 3 years)
- **Unique Facilities**: 88 MT/WA Critical Access Hospitals
- **Years Covered**: 2021, 2022, 2023
- **State Distribution**: Montana (147 records), Washington (117 records)
- **Total Columns**: 32

## Column Reference

### Identification Columns
| Column | Description |
|--------|-------------|
| `Year` | Fiscal year |
| `Provider_Num` | CMS Provider Number (CCN) |
| `State` | State name |
| `Facility_Name` | Hospital name/address |
| `CCN` | Padded 6-digit provider number |

### Financial Metrics (from HCRIS)
| Column | Description |
|--------|-------------|
| `Total_Patient_Revenue` | Total patient revenue ($) |
| `Total_Operating_Expenses` | Total operating expenses ($) |
| `Operating_Margin` | (Revenue - Expenses) / Revenue |
| `Net_Revenue` | Revenue minus expenses ($) |
| `Cost_Per_Revenue_Dollar` | Expenses / Revenue ratio |
| `Revenue_Category` | Size category (Small/Medium/Large/Very Large) |
| `Margin_Category` | Profitability category (Negative/Low/Moderate/Good/Strong) |
| `Financial_Viability` | "Viable" or "At Risk" based on margin |
| `Bed_Count` | Licensed beds |

### Quality Measures (MBQIP)
| Column | Description | Target |
|--------|-------------|--------|
| `OP-18` | Median time ED arrival to departure (admitted patients) | ≤274 min |
| `OP-2` | Fibrinolytic therapy within 30 minutes | ≥75% |
| `OP-3` | Median time to transfer for AMI | ≤60 min |
| `IMM-2` | Healthcare personnel influenza vaccination | ≥90% |
| `ED-1b` | ED throughput - admitted patients | ≤274 min |
| `ED-2b` | Admit decision to ED departure | ≤100 min |
| `OP-22` | Patients left without being seen | ≤3% |
| `Quality_Data_Source` | Data origin indicator |
| `Quality_Measures_Available` | Count of non-null quality values |

### Facility Characteristics
| Column | Description |
|--------|-------------|
| `City` | City location |
| `County` | County location |
| `Ownership` | Ownership type |
| `Emergency_Services` | Has emergency services (True/False) |
| `Birthing_Friendly` | Birthing-friendly designation |
| `Overall_Rating` | CMS star rating (1-5) |

## Data Sources

1. **HCRIS Cost Reports** - CMS Healthcare Cost Report Information System
   - Source: `data/processed/cah_baseline_metrics.csv`
   
2. **MBQIP Quality Measures** - CMS Hospital Compare / Timely & Effective Care
   - Source: CMS Provider Data Catalog (https://data.cms.gov/provider-data/topics/hospitals)
   
3. **Facility Characteristics** - CMS Hospital General Information
   - Source: `data/state_benchmarks/mt_cah_detailed.json`, `wa_cah_detailed.json`

## Quality Data Note

**Important**: The quality measure columns (OP-18, OP-2, OP-3, IMM-2, etc.) are currently placeholders. The CMS API did not return state-filtered data during automated download.

To populate quality data:
1. Visit https://data.cms.gov/provider-data/topics/hospitals/timely-effective-care
2. Download "Timely and Effective Care - Hospital" dataset
3. Filter for MT and WA hospitals
4. Match on CCN (Facility ID)
5. Re-run the merge script

Or use the helper script:
```bash
python scripts/download_cms_quality_data.py
```

## Usage Examples

### Load the Dataset
```python
import pandas as pd
df = pd.read_csv('data/processed/cah_composite_baseline.csv')
```

### Filter by State
```python
mt_hospitals = df[df['State'] == 'Montana']
wa_hospitals = df[df['State'] == 'Washington']
```

### Identify At-Risk Facilities
```python
at_risk = df[df['Financial_Viability'] == 'At Risk']
print(f"At-risk facilities: {at_risk['CCN'].nunique()}")
```

### Financial Summary by Year
```python
yearly = df.groupby('Year').agg({
    'Total_Patient_Revenue': 'mean',
    'Operating_Margin': 'mean'
}).round(2)
print(yearly)
```

### Analyze by Ownership Type
```python
by_ownership = df.groupby('Ownership')['Operating_Margin'].mean()
print(by_ownership.sort_values(ascending=False))
```

## Related Files

- `scripts/merge_mbqip_hcris_data.py` - Main merge script
- `scripts/download_cms_quality_data.py` - Quality data downloader
- `reports/composite_baseline_summary.json` - Summary statistics
- `data/cah_designation/cah_providers.csv` - Full CAH provider list

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-08 | 1.0 | Initial composite dataset with financial + placeholder quality |

## Contact

For questions about this dataset, refer to the project documentation or CMS Provider Data Catalog resources.

