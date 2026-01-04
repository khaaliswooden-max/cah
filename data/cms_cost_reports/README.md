# CMS Hospital Cost Reports Data

## Source

**CMS Hospital Current Datasets (HCRIS)**  
https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports/hospital-current-datasets

The Hospital Cost Report Information System (HCRIS) contains cost report data submitted by hospitals to Medicare. These datasets are updated quarterly.

## Files Required

For each fiscal year (2021, 2022, 2023), download the **HOSP10** worksheet files:

| File | Description |
|------|-------------|
| `HOSP10_YYYY_rpt.csv` | Report-level data (provider info, fiscal year dates, status) |
| `HOSP10_YYYY_nmrc.csv` | Numeric worksheet data (costs, utilization, financial metrics) |
| `HOSP10_YYYY_alpha.csv` | Alphanumeric worksheet data (text fields, provider details) |

### Directory Structure

```
cms_cost_reports/
├── README.md
├── 2021/
│   ├── HOSP10_2021_rpt.csv
│   ├── HOSP10_2021_nmrc.csv
│   ├── HOSP10_2021_alpha.csv
│   └── cah_identification_summary_2021.json
├── 2022/
│   ├── HOSP10_2022_rpt.csv
│   ├── HOSP10_2022_nmrc.csv
│   ├── HOSP10_2022_alpha.csv
│   └── cah_identification_summary_2022.json
└── 2023/
    ├── HOSP10_2023_rpt.csv
    ├── HOSP10_2023_nmrc.csv
    ├── HOSP10_2023_alpha.csv
    └── cah_identification_summary_2023.json
```

## Download Instructions

### Manual Download (Recommended)

1. Navigate to the [CMS Hospital Current Datasets](https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports/hospital-current-datasets) page

2. Under **"Hospital 2010 Cost Report Data Files"** (HOSP10 format), locate the ZIP files for each year:
   - `hosp10_2021_HOSPITAL.zip`
   - `hosp10_2022_HOSPITAL.zip`
   - `hosp10_2023_HOSPITAL.zip`

3. Download and extract each ZIP file into the corresponding year folder

4. Each ZIP contains three CSV files:
   - `hosp10_YYYY_RPT.CSV` → rename to `HOSP10_YYYY_rpt.csv`
   - `hosp10_YYYY_NMRC.CSV` → rename to `HOSP10_YYYY_nmrc.csv`
   - `hosp10_YYYY_ALPHA.CSV` → rename to `HOSP10_YYYY_alpha.csv`

### Direct Download URLs

As of the last update, files can be downloaded directly:

```
https://downloads.cms.gov/files/hcris/hosp10-2021-HOSPITAL.zip
https://downloads.cms.gov/files/hcris/hosp10-2022-HOSPITAL.zip
https://downloads.cms.gov/files/hcris/hosp10-2023-HOSPITAL.zip
```

> **Note:** CMS may update URL structures. If links are broken, use the manual download method.

### PowerShell Download Script

```powershell
# Create directories if they don't exist
$years = @(2021, 2022, 2023)
foreach ($year in $years) {
    $dir = "data/cms_cost_reports/$year"
    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir }
    
    $url = "https://downloads.cms.gov/files/hcris/hosp10-$year-HOSPITAL.zip"
    $zip = "$dir/hosp10_$year.zip"
    
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $dir -Force
    Remove-Item $zip
}
```

## Data Dictionary

Key worksheets and fields used in this analysis:

### RPT File (Report-level)
- `RPT_REC_NUM` - Unique report identifier
- `PRVDR_NUM` - CMS Certification Number (CCN)
- `FY_BGN_DT` / `FY_END_DT` - Fiscal year dates
- `PROC_DT` - Processing date
- `STATUS` - Report status (e.g., "As Submitted", "Settled")

### NMRC File (Numeric data)
- `RPT_REC_NUM` - Links to RPT file
- `WKSHT_CD` - Worksheet code (e.g., "S200001" for Worksheet S-2)
- `LINE_NUM` / `CLMN_NUM` - Row and column identifiers
- `ITM_VAL_NUM` - Numeric value

### ALPHA File (Alphanumeric data)
- `RPT_REC_NUM` - Links to RPT file
- `WKSHT_CD` - Worksheet code
- `LINE_NUM` / `CLMN_NUM` - Row and column identifiers
- `ITM_ALPHNMRC_ITM_TXT` - Text value

## Key Worksheets for CAH Analysis

| Worksheet | Code | Description |
|-----------|------|-------------|
| S-2 | S200001 | Provider identification and characteristics |
| S-3 | S300001 | Hospital statistical data |
| G-2 | G200001 | Cost allocation statistics |
| G-3 | G300001 | Hospital ancillary costs |

## Notes

- **File sizes:** Each year's ZIP is approximately 100-200 MB; extracted CSVs total ~500 MB per year
- **Updates:** CMS updates these files quarterly. The analysis uses year-end snapshots
- **CAH identification:** The `cah_identification_summary_YYYY.json` files are generated outputs, not source data

## Related Documentation

- [CMS Cost Report Documentation](https://www.cms.gov/Regulations-and-Guidance/Guidance/Manuals/Paper-Based-Manuals-Items/CMS021935)
- [Provider of Services File](https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/provider-of-services-file-hospital-non-hospital-facilities)

