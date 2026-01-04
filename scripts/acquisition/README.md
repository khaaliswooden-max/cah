# CAH Data Acquisition Pipeline

## Quick Start

From repository root:

```bash
# Install dependencies
pip install requests pandas beautifulsoup4 openpyxl

# Run full pipeline
python scripts/acquisition/master_execution_guide.py

# Or run individual steps
python scripts/acquisition/step1_download_cms_cost_reports.py
python scripts/acquisition/step2_download_mbqip_quality.py
python scripts/acquisition/step3_download_cah_designation.py
python scripts/acquisition/step4_integrate_optimization.py
```

## Pipeline Steps

| Step | Script | Description | Est. Time | Est. Size |
|------|--------|-------------|-----------|-----------|
| 1 | `step1_download_cms_cost_reports.py` | Financial baseline data for profit optimization | 30-45 min | ~1.5GB |
| 2 | `step2_download_mbqip_quality.py` | Quality baseline for benchmark optimization | 10-15 min | ~50MB |
| 3 | `step3_download_cah_designation.py` | Regulatory constraints and CAH identification | 5-10 min | ~100MB |
| 4 | `step4_integrate_optimization.py` | Integrate datasets and run optimization model | 2-5 min | ~10MB |

## Data Location

All acquired data will be stored in:
- `data/raw/` - Raw downloaded data (gitignored)
- `data/processed/` - Processed/cleaned data (gitignored)

## Data Sources

- **CMS Cost Reports**: Hospital cost report data from CMS
- **MBQIP Quality**: Medicare Beneficiary Quality Improvement Project measures
- **CAH Designation**: Critical Access Hospital designation data
- **Payer Mix**: Derived from cost report data

## Reports

Execution reports are generated in `reports/acquisition/`

## Troubleshooting

If a step fails:
1. Check network connectivity
2. Verify CMS data source availability
3. Review error logs in console output
4. Try running the individual step script
5. Consider manual download if automated approach fails

## Dependencies

- Python 3.8+
- requests
- pandas
- beautifulsoup4
- openpyxl

