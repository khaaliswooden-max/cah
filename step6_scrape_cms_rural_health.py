#!/usr/bin/env python3
"""
STEP 6: Scrape CMS Rural Health & Critical Access Hospital Data (Comprehensive)

Harvests every publicly available CMS dataset with direct relevance to Rural
Health and Critical Access Hospitals (CAHs). Uses the two official CMS data
catalogs as the source of truth for download URLs:

  1. CMS Data Catalog (data.json):
     https://data.cms.gov/data.json
  2. Provider Data Catalog (Hospital Compare / Care Compare):
     https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items

Datasets harvested (grouped):

  RURAL-SPECIFIC
    - Rural Health Clinic Enrollments  (CMS PECOS)
    - Rural Health Clinic All Owners   (CMS PECOS)
    - Rural Emergency Hospital (REH) — Timely & Effective Care (Hospital+National)
    - Rural Emergency Hospital (REH) — Outpatient Imaging Efficiency (Hospital+National)
    - Rural Emergency Hospital (REH) — Unplanned Hospital Visits (Hospital+National)
    - Federally Qualified Health Center Enrollments  (CMS PECOS)
    - Federally Qualified Health Center All Owners   (CMS PECOS)

  CAH / HOSPITAL
    - Hospital Provider Cost Report (HCRIS Form 2552-10 summary)
    - Hospital General Information (Hospital Compare — has 'Critical Access Hospitals' type)
    - Hospital Enrollments  (CMS PECOS)
    - Hospital All Owners   (CMS PECOS)
    - Hospital Change of Ownership
    - Hospital Service Area
    - Provider of Services File — iQIES (Hospital / other facilities — CAH flag)
    - Provider of Services File — Quality Improvement and Evaluation System
    - Skilled Nursing Facility Quality Reporting Program — Swing Beds (Provider Data)
    - Medicare Inpatient Hospitals — by Provider
    - Medicare Outpatient Hospitals — by Provider and Service
    - Timely and Effective Care — Hospital
    - Unplanned Hospital Visits — Hospital
    - Healthcare Associated Infections — Hospital
    - Complications and Deaths — Hospital
    - Patient Survey (HCAHPS) — Hospital
    - Hospital Readmissions Reduction Program
    - Hospital-Acquired Condition (HAC) Reduction Program
    - Hospital Value-Based Purchasing (HVBP) — Total Performance Score
    - Medicare Spending Per Beneficiary — Hospital

  RURAL-ADJACENT POST-ACUTE
    - Home Health Agency Enrollments / Cost Report
    - Hospice Enrollments / General Information
    - Skilled Nursing Facility Enrollments / Cost Report

  POPULATION / GEOGRAPHY
    - Medicare Geographic Variation — National, State & County
    - Medicare Monthly Enrollment
    - Market Saturation & Utilization — Core-Based Statistical Areas
    - CMS Program Statistics — Medicare Inpatient Hospital
    - CMS Program Statistics — Medicare Outpatient Facility
    - CMS Program Statistics — Medicare Providers

Usage:
    python step6_scrape_cms_rural_health.py                 # scrape all
    python step6_scrape_cms_rural_health.py --only rural    # rural-specific only
    python step6_scrape_cms_rural_health.py --only cah      # CAH/hospital only
    python step6_scrape_cms_rural_health.py --max-mb 250    # skip larger files
    python step6_scrape_cms_rural_health.py --dry-run       # write manifest only

Outputs:
    data/cms_rural_health/<group>/<dataset_slug>.csv
    data/cms_rural_health/manifest.json              (what was pulled, sizes, hashes)
    data/cms_rural_health/cah_hospitals.csv          (filtered from Hospital General)
    data/cms_rural_health/rural_emergency_hospitals.csv (filtered / merged REH facilities)
    reports/step6_completion_report.json
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

BASE_DIR = Path(__file__).parent.resolve()
DATA_ROOT = BASE_DIR / "data" / "cms_rural_health"
REPORTS_DIR = BASE_DIR / "reports"

CMS_CATALOG_URL = "https://data.cms.gov/data.json"
PROVIDER_CATALOG_URL = (
    "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items"
)

USER_AGENT = "cah-rural-health-scraper/1.0 (+research)"


# ----------------------------------------------------------------------------
# Dataset registry
# ----------------------------------------------------------------------------


@dataclass
class Dataset:
    """A CMS dataset to harvest."""

    slug: str
    title: str
    group: str  # 'rural', 'cah', 'post_acute', 'geography'
    catalog: str  # 'cms_catalog' | 'provider_data'
    identifier: str = ""  # catalog identifier (for resolution)
    direct_url: str = ""  # optional pinned URL (used when catalog lookup fails)
    notes: str = ""
    filter_cah: bool = False  # post-filter for CAHs where applicable


REGISTRY: list[Dataset] = [
    # ---- RURAL-SPECIFIC ---------------------------------------------------
    Dataset(
        slug="rhc_enrollments",
        title="Rural Health Clinic Enrollments",
        group="rural",
        catalog="cms_catalog",
        notes="Active RHC enrollments from PECOS",
    ),
    Dataset(
        slug="rhc_all_owners",
        title="Rural Health Clinic All Owners",
        group="rural",
        catalog="cms_catalog",
        notes="RHC ownership records",
    ),
    Dataset(
        slug="fqhc_enrollments",
        title="Federally Qualified Health Center Enrollments",
        group="rural",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="fqhc_all_owners",
        title="Federally Qualified Health Center All Owners",
        group="rural",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="reh_timely_effective_care_hospital",
        title="Rural Emergency Hospital Timely and Effective Care - Hospital",
        group="rural",
        catalog="provider_data",
        identifier="97xg-v3wv",
    ),
    Dataset(
        slug="reh_timely_effective_care_national",
        title="Rural Emergency Hospital Timely and Effective Care - National",
        group="rural",
        catalog="provider_data",
        identifier="d2k3-k3ac",
    ),
    Dataset(
        slug="reh_outpatient_imaging_hospital",
        title="Rural Emergency Hospital Outpatient Imaging Efficiency - Hospital",
        group="rural",
        catalog="provider_data",
        identifier="7peb-i4pi",
    ),
    Dataset(
        slug="reh_outpatient_imaging_national",
        title="Rural Emergency Hospital Outpatient Imaging Efficiency - National",
        group="rural",
        catalog="provider_data",
        identifier="zt3q-3e1z",
    ),
    Dataset(
        slug="reh_unplanned_visits_hospital",
        title="Rural Emergency Hospital Unplanned Hospital Visits - Hospital",
        group="rural",
        catalog="provider_data",
        identifier="zez1-ka2w",
    ),
    Dataset(
        slug="reh_unplanned_visits_national",
        title="Rural Emergency Hospital Unplanned Hospital Visits - National",
        group="rural",
        catalog="provider_data",
        identifier="uk3n-au7a",
    ),
    # ---- CAH / HOSPITAL ---------------------------------------------------
    Dataset(
        slug="hospital_provider_cost_report",
        title="Hospital Provider Cost Report",
        group="cah",
        catalog="cms_catalog",
        notes="HCRIS Form 2552-10 summary (most recent year)",
    ),
    Dataset(
        slug="hospital_general_information",
        title="Hospital General Information",
        group="cah",
        catalog="provider_data",
        filter_cah=True,
        notes="Includes Hospital Type = 'Critical Access Hospitals'",
    ),
    Dataset(
        slug="hospital_enrollments",
        title="Hospital Enrollments",
        group="cah",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="hospital_all_owners",
        title="Hospital All Owners",
        group="cah",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="hospital_change_of_ownership",
        title="Hospital Change of Ownership",
        group="cah",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="hospital_service_area",
        title="Hospital Service Area",
        group="cah",
        catalog="cms_catalog",
        notes="Hospital-zip utilization; used for CAH catchment analysis",
    ),
    Dataset(
        slug="pos_iqies",
        title="Provider of Services File - Internet Quality Improvement and Evaluation System",
        group="cah",
        catalog="cms_catalog",
        notes="POS iQIES file — contains CAH designation flag",
    ),
    Dataset(
        slug="pos_qies_hospital_other",
        title="Provider of Services File - Quality Improvement and Evaluation System",
        group="cah",
        catalog="cms_catalog",
        notes="Legacy QIES POS — hospital & other facilities",
    ),
    Dataset(
        slug="snf_swing_beds_qrp",
        title="Skilled Nursing Facility Quality Reporting Program - Swing Beds - Provider Data",
        group="cah",
        catalog="provider_data",
        identifier="6uyb-waub",
        notes="Swing bed facilities — most are CAHs",
    ),
    Dataset(
        slug="medicare_inpatient_by_provider",
        title="Medicare Inpatient Hospitals - by Provider",
        group="cah",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="medicare_outpatient_by_provider_service",
        title="Medicare Outpatient Hospitals - by Provider and Service",
        group="cah",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="timely_effective_care_hospital",
        title="Timely and Effective Care - Hospital",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="unplanned_visits_hospital",
        title="Unplanned Hospital Visits - Hospital",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="healthcare_associated_infections_hospital",
        title="Healthcare Associated Infections - Hospital",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="complications_deaths_hospital",
        title="Complications and Deaths - Hospital",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="hcahps_hospital",
        title="Patient survey (HCAHPS) - Hospital",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="hrrp",
        title="Hospital Readmissions Reduction Program",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="hac_reduction",
        title="Hospital-Acquired Condition (HAC) Reduction Program",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="hvbp_total_performance",
        title="Hospital Value-Based Purchasing (HVBP) - Total Performance Score",
        group="cah",
        catalog="provider_data",
    ),
    Dataset(
        slug="msbp_hospital",
        title="Medicare Spending Per Beneficiary - Hospital",
        group="cah",
        catalog="provider_data",
    ),
    # ---- POST-ACUTE -------------------------------------------------------
    Dataset(
        slug="home_health_enrollments",
        title="Home Health Agency Enrollments",
        group="post_acute",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="home_health_cost_report",
        title="Home Health Agency Cost Report",
        group="post_acute",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="hospice_enrollments",
        title="Hospice Enrollments",
        group="post_acute",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="snf_enrollments",
        title="Skilled Nursing Facility Enrollments",
        group="post_acute",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="snf_cost_report",
        title="Skilled Nursing Facility Cost Report",
        group="post_acute",
        catalog="cms_catalog",
    ),
    # ---- GEOGRAPHY / POPULATION ------------------------------------------
    Dataset(
        slug="medicare_geographic_variation_state_county",
        title="Medicare Geographic Variation - by National, State & County",
        group="geography",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="medicare_monthly_enrollment",
        title="Medicare Monthly Enrollment",
        group="geography",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="market_saturation_cbsa",
        title="Market Saturation & Utilization Core-Based Statistical Areas",
        group="geography",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="cms_ps_medicare_inpatient",
        title="CMS Program Statistics - Medicare Inpatient Hospital",
        group="geography",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="cms_ps_medicare_outpatient",
        title="CMS Program Statistics - Medicare Outpatient Facility",
        group="geography",
        catalog="cms_catalog",
    ),
    Dataset(
        slug="cms_ps_medicare_providers",
        title="CMS Program Statistics - Medicare Providers",
        group="geography",
        catalog="cms_catalog",
    ),
]


# ----------------------------------------------------------------------------
# Catalog resolution
# ----------------------------------------------------------------------------


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def fetch_catalog(session: requests.Session, url: str) -> Any:
    """Fetch a CMS catalog JSON document."""
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def resolve_download_url(
    ds: Dataset,
    cms_catalog: dict,
    provider_items: list[dict],
) -> tuple[str | None, dict]:
    """Resolve the best CSV (or ZIP) download URL for a dataset.

    Returns (url, metadata) — metadata is captured in the manifest.
    """
    if ds.direct_url:
        return ds.direct_url, {"source": "pinned", "title": ds.title}

    if ds.catalog == "cms_catalog":
        for d in cms_catalog.get("dataset", []):
            if d.get("title") == ds.title:
                best = _pick_best_distribution(d.get("distribution", []) or [])
                return best, {
                    "source": "cms_catalog",
                    "identifier": d.get("identifier", ""),
                    "modified": d.get("modified", ""),
                    "landingPage": d.get("landingPage", ""),
                    "title": d.get("title", ""),
                }
        return None, {"source": "cms_catalog", "error": "title_not_found"}

    if ds.catalog == "provider_data":
        for item in provider_items:
            if item.get("identifier") == ds.identifier or item.get("title") == ds.title:
                dist = item.get("distribution", []) or []
                best = _pick_best_distribution(dist)
                return best, {
                    "source": "provider_data",
                    "identifier": item.get("identifier", ""),
                    "modified": item.get("modified", ""),
                    "landingPage": item.get("landingPage", ""),
                    "title": item.get("title", ""),
                }
        return None, {"source": "provider_data", "error": "identifier_not_found"}

    return None, {"error": f"unknown_catalog:{ds.catalog}"}


def _pick_best_distribution(distributions: list[dict]) -> str | None:
    """Prefer a direct file URL (csv/zip) over the API endpoint."""
    api_url: str | None = None
    for dist in distributions:
        url = dist.get("accessURL") or dist.get("downloadURL") or ""
        if not url:
            continue
        lower = url.lower()
        if "data-api/v1" in lower:
            api_url = api_url or url
            continue
        if lower.endswith((".csv", ".zip", ".xlsx", ".xls")):
            return url
        # provider-data distributions often don't include extension — trust them
        if "data.cms.gov" in lower and "sites/default/files" in lower:
            return url
        if "data.cms.gov" in lower and lower.endswith("/download"):
            return url
    # Provider-data CSVs are often not in extension form but at
    # https://data.cms.gov/provider-data/sites/default/files/resources/...
    for dist in distributions:
        url = dist.get("accessURL") or dist.get("downloadURL") or ""
        if url and "data-api" not in url:
            return url
    return api_url


# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------


@dataclass
class DownloadResult:
    slug: str
    title: str
    group: str
    url: str = ""
    local_path: str = ""
    size_bytes: int = 0
    sha256: str = ""
    row_count: int | None = None
    status: str = "pending"  # 'ok' | 'skipped' | 'error'
    error: str = ""
    catalog_meta: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)


def download_file(
    session: requests.Session,
    url: str,
    out_path: Path,
    max_mb: int,
) -> tuple[int, str]:
    """Stream a file to disk. Returns (bytes_written, sha256)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else None
    hasher = hashlib.sha256()
    written = 0
    with session.get(url, stream=True, timeout=(30, 600)) as r:
        r.raise_for_status()
        content_len = int(r.headers.get("content-length", 0) or 0)
        if max_bytes and content_len and content_len > max_bytes:
            raise RuntimeError(
                f"file too large: {content_len / 1024 / 1024:.0f}MB > cap {max_mb}MB"
            )
        tmp = out_path.with_suffix(out_path.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                hasher.update(chunk)
                written += len(chunk)
                if max_bytes and written > max_bytes:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"file exceeded cap while streaming: {written / 1024 / 1024:.0f}MB"
                    )
        tmp.rename(out_path)
    return written, hasher.hexdigest()


def _decide_local_path(group: str, slug: str, url: str) -> Path:
    ext_match = re.search(r"\.(csv|CSV|zip|xlsx|xls|json)(?:\?|$)", url)
    ext = ext_match.group(1).lower() if ext_match else "csv"
    return DATA_ROOT / group / f"{slug}.{ext}"


# ----------------------------------------------------------------------------
# Post-processing: CAH filter & row counting
# ----------------------------------------------------------------------------


def _sample_read_csv(path: Path, nrows: int | None = None) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path, low_memory=False, nrows=nrows)
    except Exception:
        try:
            return pd.read_csv(path, low_memory=False, encoding="latin-1", nrows=nrows)
        except Exception:
            return None


def count_rows(path: Path) -> int | None:
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                return len(z.namelist())
        except Exception:
            return None
    if path.suffix.lower() not in {".csv"}:
        return None
    try:
        with open(path, "rb") as f:
            # count newlines — approximate but fast
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return None


def extract_cah_hospitals(general_info_path: Path, out_path: Path) -> dict:
    """Filter Hospital General Information for CAHs."""
    df = _sample_read_csv(general_info_path)
    if df is None:
        return {"error": "unreadable"}
    type_col = None
    for c in df.columns:
        if c.lower().replace("_", " ").strip() in {"hospital type", "facility type"}:
            type_col = c
            break
    if type_col is None:
        return {"error": "no_hospital_type_column", "columns": list(df.columns)[:20]}
    mask = df[type_col].astype(str).str.contains("Critical Access", case=False, na=False)
    cah = df[mask]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cah.to_csv(out_path, index=False)
    summary: dict[str, Any] = {
        "total_hospitals": int(len(df)),
        "critical_access_hospitals": int(len(cah)),
        "column_used": type_col,
    }
    # state distribution
    state_col = next(
        (c for c in df.columns if c.lower() in {"state", "state_cd", "state code"}),
        None,
    )
    if state_col is not None and len(cah):
        counts = cah[state_col].value_counts().head(15).to_dict()
        summary["top_states"] = {str(k): int(v) for k, v in counts.items()}
    return summary


def build_reh_facility_list(rural_dir: Path, out_path: Path) -> dict:
    """Merge REH provider-level files into a deduplicated facility list."""
    provider_files = [
        rural_dir / "reh_timely_effective_care_hospital.csv",
        rural_dir / "reh_outpatient_imaging_hospital.csv",
        rural_dir / "reh_unplanned_visits_hospital.csv",
    ]
    frames = []
    for p in provider_files:
        if not p.exists():
            continue
        df = _sample_read_csv(p)
        if df is None:
            continue
        keep = [
            c
            for c in df.columns
            if c.lower()
            in {
                "facility id",
                "facility_id",
                "provider_id",
                "ccn",
                "facility name",
                "hospital name",
                "address",
                "city",
                "state",
                "zip code",
                "county name",
            }
        ]
        if keep:
            frames.append(df[keep].drop_duplicates())
    if not frames:
        return {"error": "no_reh_files"}
    merged = pd.concat(frames, ignore_index=True).drop_duplicates()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    return {"reh_rows": int(len(merged)), "source_files": [p.name for p in provider_files if p.exists()]}


# ----------------------------------------------------------------------------
# Main orchestration
# ----------------------------------------------------------------------------


def scrape(only: str | None, max_mb: int, dry_run: bool) -> dict:
    session = _session()
    print(f"\n{'=' * 70}\nSTEP 6: CMS RURAL HEALTH & CAH DATA SCRAPE\n{'=' * 70}")
    print(f"Loading catalogs...")

    try:
        cms_catalog = fetch_catalog(session, CMS_CATALOG_URL)
    except Exception as e:
        print(f"  ! CMS data catalog fetch failed: {e}")
        cms_catalog = {"dataset": []}

    try:
        provider_items = fetch_catalog(session, PROVIDER_CATALOG_URL)
    except Exception as e:
        print(f"  ! Provider data catalog fetch failed: {e}")
        provider_items = []

    print(f"  CMS catalog datasets    : {len(cms_catalog.get('dataset', []))}")
    print(f"  Provider data datasets  : {len(provider_items)}")

    active = REGISTRY
    if only:
        active = [d for d in REGISTRY if d.group == only]
        print(f"  Filter --only={only}  (kept {len(active)} / {len(REGISTRY)})")

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    results: list[DownloadResult] = []

    for i, ds in enumerate(active, start=1):
        print(f"\n[{i}/{len(active)}] {ds.group.upper()}  {ds.title}")
        url, meta = resolve_download_url(ds, cms_catalog, provider_items)
        res = DownloadResult(
            slug=ds.slug,
            title=ds.title,
            group=ds.group,
            url=url or "",
            catalog_meta=meta,
        )
        if not url:
            print(f"    ! could not resolve download URL  ({meta})")
            res.status = "error"
            res.error = meta.get("error", "no_url")
            results.append(res)
            continue

        print(f"    url: {url[:110]}")
        if dry_run:
            res.status = "skipped"
            res.error = "dry_run"
            results.append(res)
            continue

        local = _decide_local_path(ds.group, ds.slug, url)
        res.local_path = str(local.relative_to(BASE_DIR))
        try:
            n, sha = download_file(session, url, local, max_mb)
            res.size_bytes = n
            res.sha256 = sha
            res.row_count = count_rows(local)
            res.status = "ok"
            print(f"    ok  {n / 1024 / 1024:.2f}MB  rows~{res.row_count}  sha={sha[:16]}")
        except Exception as e:
            res.status = "error"
            res.error = str(e)[:300]
            print(f"    ! download failed: {res.error}")

        results.append(res)
        time.sleep(0.5)  # gentle rate-limit

    # ---- Post-processing ----
    rural_dir = DATA_ROOT / "rural"
    cah_dir = DATA_ROOT / "cah"
    post_extras: dict[str, Any] = {}

    gen_info = cah_dir / "hospital_general_information.csv"
    if gen_info.exists():
        cah_file = DATA_ROOT / "cah_hospitals.csv"
        summary = extract_cah_hospitals(gen_info, cah_file)
        post_extras["cah_hospitals"] = summary
        print(f"\n  [post] CAH filter: {summary}")

    if (rural_dir / "reh_timely_effective_care_hospital.csv").exists():
        reh_file = DATA_ROOT / "rural_emergency_hospitals.csv"
        summary = build_reh_facility_list(rural_dir, reh_file)
        post_extras["rural_emergency_hospitals"] = summary
        print(f"  [post] REH facility list: {summary}")

    # ---- Manifest ----
    manifest = {
        "step": "6_cms_rural_health_scrape",
        "timestamp": datetime.now().isoformat(),
        "filter_group": only,
        "max_file_mb": max_mb,
        "dry_run": dry_run,
        "datasets": [r.__dict__ for r in results],
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r.status == "ok"),
            "error": sum(1 for r in results if r.status == "error"),
            "skipped": sum(1 for r in results if r.status == "skipped"),
            "bytes_downloaded": sum(r.size_bytes for r in results),
        },
        "post_processing": post_extras,
        "catalog_sources": {
            "cms_catalog": CMS_CATALOG_URL,
            "provider_data": PROVIDER_CATALOG_URL,
        },
    }

    manifest_path = DATA_ROOT / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"\n  manifest -> {manifest_path.relative_to(BASE_DIR)}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "step6_completion_report.json"
    with open(report_path, "w") as f:
        json.dump(
            {
                "step": "6_cms_rural_health_scrape",
                "timestamp": manifest["timestamp"],
                "summary": manifest["summary"],
                "manifest_path": str(manifest_path.relative_to(BASE_DIR)),
                "post_processing": post_extras,
            },
            f,
            indent=2,
        )
    print(f"  report   -> {report_path.relative_to(BASE_DIR)}")

    s = manifest["summary"]
    mb = s["bytes_downloaded"] / 1024 / 1024
    print(
        f"\nDONE  ok={s['ok']}  error={s['error']}  skipped={s['skipped']}"
        f"  data={mb:.1f}MB"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape CMS Rural Health & CAH data")
    parser.add_argument(
        "--only",
        choices=["rural", "cah", "post_acute", "geography"],
        default=None,
        help="Limit to one dataset group",
    )
    parser.add_argument(
        "--max-mb",
        type=int,
        default=500,
        help="Skip/abort downloads larger than this (MB). Use 0 for no cap.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve URLs and write manifest without downloading files.",
    )
    args = parser.parse_args()
    try:
        scrape(only=args.only, max_mb=args.max_mb, dry_run=args.dry_run)
        return 0
    except KeyboardInterrupt:
        print("\n[interrupted]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
