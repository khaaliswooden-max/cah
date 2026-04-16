# CAH Data Acquisition Pipeline - Quick Start Guide

## 🚀 Getting Started

This pipeline acquires all critical datasets needed for CAH dual-objective optimization (5% profit increase + quality benchmarks).

### Prerequisites

```bash
# Required Python packages
pip install requests pandas beautifulsoup4 openpyxl
```

### File Structure

```
cah_data_acquisition/
├── scripts/
│   ├── master_execution_guide.py          # Main orchestrator
│   ├── step1_download_cms_cost_reports.py # CMS financial data
│   ├── step2_download_mbqip_quality.py    # Quality measures  
│   └── step3_download_cah_designation.py  # CAH designation data
├── data/
│   ├── cms_cost_reports/                  # Financial baseline
│   ├── mbqip_quality/                     # Quality baseline
│   ├── cah_designation/                   # Regulatory constraints
│   └── processed/                         # Integrated datasets
└── reports/                                # Execution reports
```

## 📋 Execution Options

### Option 1: Full Automated Pipeline (Recommended)

Execute all steps automatically with validation and error handling:

```bash
cd cah_data_acquisition
python3 scripts/master_execution_guide.py
```

This will:
- Validate environment and dependencies
- Execute all 3 critical dataset acquisitions
- Generate progress reports
- Handle errors with retry options
- Create final execution report

**Estimated time: 45-60 minutes**
**Required disk space: ~2GB**

### Option 2: Step-by-Step Manual Execution

Execute each step individually for maximum control:

```bash
# Step 1: CMS Cost Reports (30-45 min, ~1.5GB)
python3 scripts/step1_download_cms_cost_reports.py

# Step 2: MBQIP Quality Measures (10-15 min, ~50MB)
python3 scripts/step2_download_mbqip_quality.py

# Step 3: CAH Designation Data (5-10 min, ~100MB)
python3 scripts/step3_download_cah_designation.py
```

## 📊 What Gets Downloaded

### Step 1: CMS Cost Reports (CRITICAL)
- **Source**: CMS Healthcare Cost Report Information System
- **Data**: Form 2552-10 for years 2021-2023
- **Size**: ~500MB per year
- **Purpose**: Financial baseline (revenue, costs, profit margins)
- **Use**: Objective Function 1 (5% profit increase)

### Step 2: MBQIP Quality Measures (CRITICAL)
- **Source**: HRSA + CMS Hospital Compare
- **Data**: Quality measures across 4 domains
- **Size**: ~50MB
- **Purpose**: Quality benchmarks and current performance
- **Use**: Objective Function 2 (quality optimization)

### Step 3: CAH Designation Data (CRITICAL)
- **Source**: CMS Provider of Services File
- **Data**: CAH designations and regulatory constraints
- **Size**: ~100MB
- **Purpose**: Constraint boundaries (25-bed limit, 96-hour LOS, etc.)
- **Use**: Regulatory constraints for optimization model

## ✅ Validation Checklist

After execution, verify:

- [ ] **Cost Reports**: 3 years of data for 1,377 CAHs
- [ ] **Quality Measures**: MBQIP data across all 4 domains
- [ ] **CAH Designations**: Current CAH list with constraints
- [ ] **Data Quality**: <5% missing values in critical fields
- [ ] **File Integrity**: All CSV files readable and properly formatted

Check reports in `reports/` directory:
- `step1_completion_report.json`
- `step2_completion_report.json`
- `step3_completion_report.json`
- `master_execution_report.json`

## 🔍 Troubleshooting

### Issue: Network timeout during download
**Solution**: Script includes automatic retry logic. If download fails, rerun the specific step script.

### Issue: File extraction errors
**Solution**: Check disk space (need ~2GB free). Delete corrupted ZIP files and retry.

### Issue: CAH identification fails
**Solution**: Manual verification may be needed. Check JSON metadata files for guidance.

### Issue: Missing Python packages
**Solution**: 
```bash
pip install requests pandas beautifulsoup4 openpyxl
```

## 📈 Next Steps After Data Acquisition

1. **Validate Data Quality**
   - Check completion reports in `reports/`
   - Verify CAH counts match expectations (~1,377 (per CMS POS FY2024))
   - Confirm financial and quality baselines established

2. **Data Integration**
   - Merge datasets on CAH provider ID
   - Create unified optimization input dataset
   - Validate variable ranges and constraints

3. **Mathematical Optimization**
   - Parameterize Lagrangian dual-objective function
   - Define regulatory constraint boundaries
   - Execute Sequential Quadratic Programming (SQP)
   - Generate Pareto frontier for profit vs. quality

## 📞 Support

For issues or questions:
1. Check execution reports in `reports/` directory
2. Review error logs from script output
3. Consult individual step scripts for detailed comments

## 🎯 Success Criteria

Pipeline is successful when:
- All 3 critical datasets downloaded and validated
- CAH financial baselines established (~1,377 (per CMS POS FY2024) hospitals)
- Quality benchmarks defined (MBQIP 4 domains)
- Regulatory constraints mathematically parameterized
- Master execution report shows "CRITICAL_DATASETS_ACQUIRED"

**You're ready for optimization when all 3 critical steps complete successfully.**
