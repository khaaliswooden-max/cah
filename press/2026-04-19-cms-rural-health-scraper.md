# Step 6 — end-to-end CMS rural-health and CAH data harvester goes live

**VISIONBLOX LLC × ZUUP INNOVATION LAB — FOR IMMEDIATE RELEASE**
April 19, 2026

The CAH Transformation Engine now ships an end-to-end harvester for every CMS rural-health and CAH-relevant dataset published through the two official catalogs — `data.cms.gov` and the Provider Data Catalog — resolving 41 datasets to pinned download URLs, streaming ~1 GB of raw data to disk with SHA-256 integrity hashes, and committing a reproducible manifest plus post-processed CAH/REH summaries.

## Operational Impact

- **CAH administrators** can refresh the entire upstream data surface with a single command — no more hunting across CMS portals to locate the latest HCAHPS, HRRP, HAC, HVBP, or POS/iQIES extracts.
- **WSHA, MHA, and regional partners** get a post-processed, deduplicated inventory: **1,376 Critical Access Hospitals** from Hospital General Information (top states: TX 92, IA 82, KS 82, MN 76, NE 62, WI 58, IL 55, **MT 50, WA 39**) and **39 Rural Emergency Hospitals** merged across three REH provider files.
- **HRSA and policy researchers** get rural-specific datasets (RHC, FQHC, REH) alongside post-acute (HHA, Hospice, SNF cost reports and enrollments) and geography/population datasets (Medicare geographic variation, monthly enrollment, market saturation, program statistics) in one harvest.

## Strategic Significance

- **Data provenance as a product feature.** Every file carries a SHA-256 hash and the entire harvest is captured in a single manifest — a direct input to the auto-citation engine shipped the week prior.
- **Reproducibility at scale.** Partners can reproduce any state-level analysis from the committed manifest without re-scraping CMS, lowering the cost of independent validation.
- **National roadmap unblocked.** Step 6 completes the upstream data acquisition needed to run the 1,377-CAH national pipeline end-to-end, after which the CAHSP composite scoring and transfer-optimization layers take over.

## Technical Details

- **Script:** `step6_scrape_cms_rural_health.py` (new).
- **Resolution:** 41 datasets identified via `data.cms.gov/data.json` and the Provider Data Catalog, resolved to pinned download URLs.
- **Transport:** streamed to disk with per-file SHA-256 hashes; full manifest committed.
- **Dataset groups harvested:**
  - **Rural-specific** — RHC, FQHC, REH.
  - **CAH & hospital** — CMS cost reports, HCAHPS, HRRP, HAC, HVBP, POS/iQIES, swing beds, MSBP, timely-effective care.
  - **Post-acute** — HHA, Hospice, SNF enrollments + cost reports.
  - **Geography & population** — Medicare geographic variation, monthly enrollment, market saturation, program statistics.
- **Post-processing:**
  - Hospital General Information filtered to **1,376 CAHs** via the `Hospital Type` column.
  - Three REH provider files (`reh_timely_effective_care_hospital.csv`, `reh_outpatient_imaging_hospital.csv`, `reh_unplanned_visits_hospital.csv`) merged into a deduplicated facility list of **39 REHs**.
- **Footprint:** ~1 GB of raw CSV/ZIP downloads stay local per `.gitignore`. Only the manifest and the CAH/REH summary artifacts are committed (`data/cms_rural_health/manifest.json`, `reports/step6_completion_report.json`).
- **Run completion (2026-04-19T14:04):** 41 ok / 0 error / 0 skipped; 1,003,889,153 bytes downloaded.

### Quick start

```bash
python3 step6_scrape_cms_rural_health.py
# Manifest: data/cms_rural_health/manifest.json
# Summary:  reports/step6_completion_report.json
```

## References

- PR: [#4](https://github.com/khaaliswooden-max/cah/pull/4) — `claude/scrape-cms-rural-health-7q9ss`
- Key commit: `aab1cc5` (`feat(step6): scrape CMS rural health & CAH datasets end-to-end`)
- Related files: `step6_scrape_cms_rural_health.py`, `reports/step6_completion_report.json`, `data/cms_rural_health/manifest.json`

---

**About VISIONBLOX × ZUUP.** The CAH Transformation Engine is a joint effort of VISIONBLOX LLC and ZUUP INNOVATION LAB to bring dual-objective optimization — a 5% operating-margin uplift alongside MBQIP/CAHSP quality benchmarks — to the 1,377 Critical Access Hospitals that make up the backbone of U.S. rural healthcare. Phase 1 empirical validation targets Washington (39 CAHs) and Montana (50 CAHs), leveraging WSHA and MHA benchmark networks. **Contact:** Aldrich K. Wooden — kwooden@visionblox.com
