#!/usr/bin/env python3
"""Fix OP-3 merge with correct CCN formatting."""

import pandas as pd
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"

# Load archive OP-3 data
print("Loading 2022 archive data...")
archive = pd.read_csv(DATA_DIR / "raw/cms_archive_2022/Timely_and_Effective_Care-Hospital_2022.csv", low_memory=False)
archive.columns = archive.columns.str.strip().str.lower().str.replace(' ', '_')
mt_wa = archive[archive['state'].isin(['MT', 'WA'])]
op3 = mt_wa[mt_wa['measure_id'].str.upper().isin(['OP-3', 'OP_3', 'OP3', 'OP_3B'])]

# Clean OP-3 data
op3_clean = op3[['facility_id', 'score']].copy()
op3_clean['CCN'] = op3_clean['facility_id'].astype(str).str.strip()
op3_clean['OP-3'] = pd.to_numeric(op3_clean['score'], errors='coerce')
op3_clean = op3_clean[['CCN', 'OP-3']].drop_duplicates(subset=['CCN'], keep='first')

print(f"OP-3 data: {len(op3_clean)} facilities")
print(f"OP-3 range: {op3_clean['OP-3'].min():.0f} - {op3_clean['OP-3'].max():.0f} minutes")

# Load composite
print("\nLoading composite dataset...")
composite = pd.read_csv(DATA_DIR / "processed/cah_composite_baseline.csv")
composite['CCN'] = composite['CCN'].astype(str).str.strip()

# Remove old OP-3 columns
for col in ['OP-3', 'OP3_Data_Year', 'OP3_Note']:
    if col in composite.columns:
        composite = composite.drop(columns=[col])

# Merge
print("Merging OP-3 data...")
merged = composite.merge(op3_clean, on='CCN', how='left')
merged['OP3_Data_Year'] = merged['OP-3'].apply(lambda x: '2022' if pd.notna(x) else None)

# Stats
matched = merged['OP-3'].notna().sum()
total = len(merged)
print(f"\n=== RESULTS ===")
print(f"Matched: {matched}/{total} ({100*matched/total:.1f}%)")
if matched > 0:
    print(f"OP-3 median: {merged['OP-3'].median():.0f} minutes")
    print(f"OP-3 range: {merged['OP-3'].min():.0f} - {merged['OP-3'].max():.0f} minutes")

# Save
output_path = DATA_DIR / "processed/cah_composite_baseline.csv"
merged.to_csv(output_path, index=False)
print(f"\n[OK] Saved: {output_path}")

# Show final columns
print(f"\nFinal columns: {list(merged.columns)}")

