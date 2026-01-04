#!/usr/bin/env python3
"""
STEP 2: Download MBQIP Quality Measures
Critical dataset for quality benchmark optimization
"""

import requests
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
from bs4 import BeautifulSoup
import time

# Configuration - Use the current script's directory as base
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data" / "mbqip_quality"
REPORTS_DIR = BASE_DIR / "reports"

# MBQIP Data Sources
MBQIP_SOURCES = {
    "annual_reports": {
        "2023": "https://www.flexmonitoring.org/publication/mbqip-quality-measures-national-annual-report-2023",
        "2022": "https://www.flexmonitoring.org/publication/mbqip-quality-measures-national-annual-report-2022",
        "2021": "https://www.flexmonitoring.org/publication/mbqip-quality-measures-national-annual-report-2021"
    },
    "cah_reports_portal": "https://mbqip.com/",
    "cms_hospital_compare": "https://data.medicare.gov/provider-data/dataset/xubh-q36u"
}

# MBQIP Measure Domains
MBQIP_DOMAINS = {
    "patient_safety": ["HCP-IMM-3", "Antibiotic Stewardship"],
    "outpatient": ["OP-2", "OP-3", "OP-5", "OP-18", "OP-22", "OP-23"],
    "patient_engagement": ["HCAHPS"],
    "care_transitions": ["EDTC"]
}

def download_mbqip_annual_report(year):
    """Download MBQIP annual report for a specific year"""
    print(f"\n{'='*60}")
    print(f"DOWNLOADING MBQIP ANNUAL REPORT - {year}")
    print(f"{'='*60}")
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    report_url = MBQIP_SOURCES["annual_reports"].get(str(year))
    if not report_url:
        print(f"⚠️  URL not configured for year {year}")
        return False
    
    try:
        print(f"📥 Accessing: {report_url}")
        
        # Note: These are HTML pages with downloadable PDFs/Excel files
        # We'll document the process and provide manual download guidance
        
        response = requests.get(report_url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML to find download links
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find PDF or Excel download links
        download_links = []
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if any(ext in href.lower() for ext in ['.pdf', '.xlsx', '.csv']):
                download_links.append(href)
        
        if download_links:
            print(f"✓ Found {len(download_links)} downloadable files:")
            for link in download_links[:5]:
                print(f"   - {link}")
        else:
            print(f"⚠️  No direct download links found on page")
            print(f"   Manual download may be required")
        
        # Save page metadata
        metadata = {
            "year": year,
            "url": report_url,
            "download_links": download_links,
            "access_timestamp": datetime.now().isoformat(),
            "status": "links_identified" if download_links else "manual_download_required"
        }
        
        metadata_path = DATA_DIR / f"mbqip_report_{year}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✓ Saved metadata to {metadata_path.name}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error accessing report: {e}")
        return False

def download_cms_hospital_compare_data():
    """Download CMS Hospital Compare dataset (includes CAH quality data)"""
    print(f"\n{'='*60}")
    print(f"DOWNLOADING CMS HOSPITAL COMPARE DATA")
    print(f"{'='*60}")
    
    try:
        # CMS Hospital Compare API endpoint
        api_url = "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
        
        print(f"📥 Fetching from CMS Hospital Compare API...")
        print(f"⏱️  This includes quality measures for all hospitals including CAHs...")
        
        # Note: This is a large dataset, we'll need to handle pagination
        response = requests.get(api_url, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API response received")
            
            # Save raw response for analysis
            raw_path = DATA_DIR / "cms_hospital_compare_raw.json"
            with open(raw_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✓ Saved raw data to {raw_path.name}")
            
            # Try to convert to DataFrame if data structure allows
            if 'results' in data:
                df = pd.DataFrame(data['results'])
                csv_path = DATA_DIR / "cms_hospital_compare_data.csv"
                df.to_csv(csv_path, index=False)
                print(f"✓ Saved {len(df)} records to CSV")
                print(f"   Columns: {list(df.columns[:10])}")
            
            return True
        else:
            print(f"⚠️  API returned status code: {response.status_code}")
            print(f"   Direct download may be required from: {MBQIP_SOURCES['cms_hospital_compare']}")
            return False
        
    except Exception as e:
        print(f"✗ Error downloading Hospital Compare data: {e}")
        print(f"\nAlternative: Manual download from data.medicare.gov")
        return False

def create_mbqip_measures_reference():
    """Create reference guide for MBQIP measures"""
    print(f"\n{'='*60}")
    print(f"CREATING MBQIP MEASURES REFERENCE")
    print(f"{'='*60}")
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    measures_reference = {
        "Patient Safety / Inpatient Care": {
            "HCP-IMM-3": {
                "name": "Healthcare Personnel Influenza Vaccination",
                "description": "Percentage of healthcare personnel who receive influenza vaccination",
                "target": ">=90%",
                "data_source": "NHSN (National Healthcare Safety Network)"
            },
            "Antibiotic Stewardship": {
                "name": "Antibiotic Stewardship",
                "description": "Assessment of antibiotic stewardship program elements",
                "target": "100% of elements implemented",
                "data_source": "CAH self-assessment"
            }
        },
        "Outpatient Care": {
            "OP-2": {
                "name": "Fibrinolytic Therapy Received Within 30 Minutes",
                "description": "AMI patients receiving fibrinolytic therapy during ED visit",
                "target": ">=75%",
                "data_source": "CMS QualityNet"
            },
            "OP-3": {
                "name": "Median Time to Transfer to Another Facility - AMI",
                "description": "Median time from ED arrival to departure for AMI patients",
                "target": "<=60 minutes",
                "data_source": "CMS QualityNet"
            },
            "OP-18": {
                "name": "Median Time from ED Arrival to Departure",
                "description": "For admitted ED patients",
                "target": "<=274 minutes",
                "data_source": "CMS QualityNet"
            },
            "OP-22": {
                "name": "ED Left Without Being Seen",
                "description": "Percentage who left before treatment",
                "target": "<=3%",
                "data_source": "CMS QualityNet"
            }
        },
        "Patient Engagement": {
            "HCAHPS": {
                "name": "Hospital Consumer Assessment of Healthcare Providers and Systems",
                "description": "Patient experience survey",
                "target": "Top-box performance on all domains",
                "data_source": "CMS Hospital Compare"
            }
        },
        "Care Transitions": {
            "EDTC": {
                "name": "Emergency Department Transfer Communication",
                "description": "Communication during interfacility transfers",
                "target": "100% compliance",
                "data_source": "CAH chart abstraction"
            }
        }
    }
    
    reference_path = DATA_DIR / "mbqip_measures_reference.json"
    with open(reference_path, 'w') as f:
        json.dump(measures_reference, f, indent=2)
    
    print(f"✓ Created MBQIP measures reference guide")
    print(f"   Saved to: {reference_path.name}")
    print(f"\n📋 MBQIP Quality Domains:")
    for domain, measures in measures_reference.items():
        print(f"   • {domain}: {len(measures)} measures")
    
    return reference_path

def generate_step2_report():
    """Generate completion report for Step 2"""
    print(f"\n{'='*60}")
    print(f"STEP 2 COMPLETION REPORT")
    print(f"{'='*60}")
    
    # Check what we successfully acquired
    acquired_files = list(DATA_DIR.glob("*"))
    
    report = {
        "step": "2_mbqip_quality_measures",
        "timestamp": datetime.now().isoformat(),
        "files_created": [f.name for f in acquired_files],
        "data_sources_documented": list(MBQIP_SOURCES.keys()),
        "measure_domains": list(MBQIP_DOMAINS.keys()),
        "status": "metadata_acquired",
        "next_steps": [
            "Manual download of MBQIP annual reports if needed",
            "Extract CAH-specific quality data from Hospital Compare",
            "Map quality measures to optimization benchmarks",
            "Proceed to Step 3: CAH Designation Data"
        ]
    }
    
    report_path = REPORTS_DIR / "step2_completion_report.json"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Files created: {len(acquired_files)}")
    print(f"   Domains covered: {len(MBQIP_DOMAINS)}")
    print(f"   Status: {report['status']}")
    
    print(f"\n✓ Report saved to: {report_path}")
    print(f"\n{'='*60}")
    
    return report

def main():
    """Execute Step 2: MBQIP Quality Measures acquisition"""
    print("\n" + "="*60)
    print("CAH DATA ACQUISITION PIPELINE")
    print("STEP 2: MBQIP QUALITY MEASURES")
    print("="*60)
    
    print(f"\nTarget: Quality baseline data for 1300+ CAHs")
    print(f"Purpose: Quality benchmark optimization")
    print(f"Domains: Patient Safety, Outpatient, Engagement, Care Transitions")
    
    # Auto-proceed (non-interactive mode)
    print("\n[AUTO-MODE] Proceeding with data acquisition...")
    
    # Create MBQIP measures reference
    create_mbqip_measures_reference()
    
    # Attempt to download annual reports (may require manual download)
    for year in [2023, 2022, 2021]:
        download_mbqip_annual_report(year)
        time.sleep(1)
    
    # Download CMS Hospital Compare data
    download_cms_hospital_compare_data()
    
    # Generate completion report
    generate_step2_report()
    
    print(f"\n✅ STEP 2 COMPLETE")
    print(f"\n📌 IMPORTANT:")
    print(f"   Some MBQIP data may require manual download")
    print(f"   Check metadata files in {DATA_DIR}")
    print(f"\nNext: Run step3_download_cah_designation.py")

if __name__ == "__main__":
    main()
