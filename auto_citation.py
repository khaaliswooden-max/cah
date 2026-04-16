#!/usr/bin/env python3
"""
Auto-Citation Engine for CAH Benchmark Claims.

Converts raw CMS HCRIS cost report line items into auditable benchmark
claims — closing the translation gap between federal data and
facility-level intelligence.

Each claim carries:
  - The exact worksheet, line, and column from the CMS 2552-10 form
  - The source file name (e.g. HOSP10_2023_RPT.CSV)
  - A data-quality / confidence grade derived from calculate_payer_mix.py
  - A human-readable APA-style citation string

Usage:
    python auto_citation.py --year 2023 [--format json|bibtex] [--output citations.json]
"""

import csv
import json
import argparse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BenchmarkClaim:
    """An auditable benchmark claim derived from a HCRIS line item."""

    provider_id: str
    claim_type: str            # e.g. "payer_mix_medicare", "operating_margin"
    value: float
    unit: str                  # e.g. "%", "$", "ratio"
    source_worksheet: str      # e.g. "S-3 Part V, Line 1, Col 1"
    source_file: str           # e.g. "HOSP10_2023_RPT.CSV"
    report_period: str         # e.g. "FY2023"
    data_quality: str          # passthrough from calculate_payer_mix.py
    confidence: Optional[str]  # "high", "medium", "low", or None (excluded)
    citation_text: str         # human-readable APA-style citation


# ═══════════════════════════════════════════════════════════════════════════════
# CITATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


# Worksheet descriptions for CMS Form 2552-10
WORKSHEET_MAP = {
    "s3_part_v": "Worksheet S-3, Part V (Hospital Statistics by Payer)",
    "g3_worksheet": "Worksheet G-3 (Hospital Revenue and Adjustments)",
    "s3_part_iv": "Worksheet S-3, Part IV (Hospital Outpatient Statistics)",
    "days_estimated": "Estimated from available utilization data",
}

# Claim type metadata
CLAIM_TYPES = {
    "payer_mix_medicare": {
        "label": "Medicare payer mix share",
        "unit": "%",
        "worksheet": "S-3 Part V, Line 1",
    },
    "payer_mix_medicaid": {
        "label": "Medicaid payer mix share",
        "unit": "%",
        "worksheet": "S-3 Part V, Line 2",
    },
    "payer_mix_other": {
        "label": "Other payer mix share",
        "unit": "%",
        "worksheet": "S-3 Part V, Line 3",
    },
    "total_revenue": {
        "label": "Total facility revenue",
        "unit": "$",
        "worksheet": "Worksheet G-3, Line 1",
    },
    "total_cost": {
        "label": "Total facility cost",
        "unit": "$",
        "worksheet": "Worksheet B, Part I",
    },
    "operating_margin": {
        "label": "Operating margin",
        "unit": "ratio",
        "worksheet": "Derived from G-3 and B worksheets",
    },
}


class AutoCitationEngine:
    """
    Converts CMS HCRIS cost report data into auditable benchmark claims.

    Reads the CSV output produced by calculate_payer_mix.py and generates
    structured BenchmarkClaim objects with full provenance.
    """

    # Map data_quality flags to confidence grades
    QUALITY_CONFIDENCE = {
        "s3_part_v": "high",
        "g3_worksheet": "high",
        "s3_part_iv": "medium",
        "days_estimated": "low",
        "no_data": None,  # excluded from output
    }

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"

    # ─── Core citation logic ─────────────────────────────────────────────

    def _build_citation_text(
        self,
        provider_id: str,
        claim_type: str,
        value: float,
        year: int,
        source_worksheet: str,
    ) -> str:
        """Generate APA-style citation string."""
        meta = CLAIM_TYPES.get(claim_type, {})
        label = meta.get("label", claim_type)
        unit = meta.get("unit", "")
        fmt_value = f"{value:.1f}{unit}" if unit == "%" else f"{value:,.2f}"

        return (
            f"Centers for Medicare & Medicaid Services. "
            f"(FY{year}). Hospital Cost Report (Form CMS-2552-10), "
            f"{source_worksheet}. "
            f"Provider {provider_id}: {label} = {fmt_value}. "
            f"Retrieved from Healthcare Cost Report Information System (HCRIS)."
        )

    def cite_payer_mix_row(self, row: Dict[str, Any], year: int) -> List[BenchmarkClaim]:
        """
        Convert one payer-mix CSV row into a list of BenchmarkClaim objects.

        Args:
            row: Dictionary with keys from calculate_payer_mix.py CSV output
            year: Fiscal year for the cost report

        Returns:
            List of BenchmarkClaim instances (empty if data_quality == 'no_data')
        """
        dq = row.get("data_quality", "no_data")
        confidence = self.QUALITY_CONFIDENCE.get(dq)
        if confidence is None:
            return []

        provider_id = row.get("provider_id", row.get("provider_ccn", "UNKNOWN"))
        source_file = f"HOSP10_{year}_RPT.CSV"
        ws_desc = WORKSHEET_MAP.get(dq, dq)
        claims: List[BenchmarkClaim] = []

        # Medicare share
        medicare = row.get("medicare_pct") or row.get("medicare_share")
        if medicare is not None:
            medicare = float(medicare)
            ct = "payer_mix_medicare"
            claims.append(BenchmarkClaim(
                provider_id=provider_id,
                claim_type=ct,
                value=medicare,
                unit="%",
                source_worksheet=CLAIM_TYPES[ct]["worksheet"],
                source_file=source_file,
                report_period=f"FY{year}",
                data_quality=dq,
                confidence=confidence,
                citation_text=self._build_citation_text(
                    provider_id, ct, medicare, year,
                    CLAIM_TYPES[ct]["worksheet"],
                ),
            ))

        # Medicaid share
        medicaid = row.get("medicaid_pct") or row.get("medicaid_share")
        if medicaid is not None:
            medicaid = float(medicaid)
            ct = "payer_mix_medicaid"
            claims.append(BenchmarkClaim(
                provider_id=provider_id,
                claim_type=ct,
                value=medicaid,
                unit="%",
                source_worksheet=CLAIM_TYPES[ct]["worksheet"],
                source_file=source_file,
                report_period=f"FY{year}",
                data_quality=dq,
                confidence=confidence,
                citation_text=self._build_citation_text(
                    provider_id, ct, medicaid, year,
                    CLAIM_TYPES[ct]["worksheet"],
                ),
            ))

        # Other share
        other = row.get("other_pct") or row.get("other_share")
        if other is not None:
            other = float(other)
            ct = "payer_mix_other"
            claims.append(BenchmarkClaim(
                provider_id=provider_id,
                claim_type=ct,
                value=other,
                unit="%",
                source_worksheet=CLAIM_TYPES[ct]["worksheet"],
                source_file=source_file,
                report_period=f"FY{year}",
                data_quality=dq,
                confidence=confidence,
                citation_text=self._build_citation_text(
                    provider_id, ct, other, year,
                    CLAIM_TYPES[ct]["worksheet"],
                ),
            ))

        return claims

    # ─── Batch processing ────────────────────────────────────────────────

    def generate_benchmark_report(
        self,
        year: int,
        provider_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Load payer-mix CSV for a given year, generate citations for all rows.

        Args:
            year: Fiscal year (e.g. 2023)
            provider_ids: Optional filter — only cite these providers

        Returns:
            Report dict with keys: claims, total_claims, by_confidence, year
        """
        csv_path = self.data_dir / "processed" / f"payer_mix_{year}.csv"
        if not csv_path.exists():
            # Try alternate naming
            csv_path = self.data_dir / "cms_cost_reports" / str(year) / f"payer_mix_{year}.csv"

        all_claims: List[BenchmarkClaim] = []

        if csv_path.exists():
            with open(csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid = row.get("provider_id", row.get("provider_ccn", ""))
                    if provider_ids and pid not in provider_ids:
                        continue
                    all_claims.extend(self.cite_payer_mix_row(row, year))

        by_conf = {"high": 0, "medium": 0, "low": 0}
        for c in all_claims:
            if c.confidence in by_conf:
                by_conf[c.confidence] += 1

        return {
            "year": year,
            "total_claims": len(all_claims),
            "by_confidence": by_conf,
            "claims": all_claims,
        }

    # ─── Export ───────────────────────────────────────────────────────────

    def export_citations(
        self,
        claims: List[BenchmarkClaim],
        fmt: str = "json",
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Export claims as JSON or BibTeX.

        Args:
            claims: List of BenchmarkClaim objects
            fmt: "json" or "bibtex"
            output_path: Optional file to write (returns string if None)

        Returns:
            Serialized string
        """
        if fmt == "json":
            payload = [asdict(c) for c in claims]
            text = json.dumps(payload, indent=2)
        elif fmt == "bibtex":
            entries = []
            for i, c in enumerate(claims):
                key = f"hcris_{c.report_period}_{c.provider_id}_{c.claim_type}"
                entry = (
                    f"@misc{{{key},\n"
                    f"  title   = {{{c.citation_text}}},\n"
                    f"  author  = {{Centers for Medicare \\& Medicaid Services}},\n"
                    f"  year    = {{{c.report_period}}},\n"
                    f"  note    = {{Provider {c.provider_id}, {c.source_worksheet}, "
                    f"data quality: {c.data_quality}}}\n"
                    f"}}"
                )
                entries.append(entry)
            text = "\n\n".join(entries)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text)

        return text


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Auto-Citation Engine — generate auditable benchmark claims from CMS HCRIS data"
    )
    parser.add_argument("--year", type=int, default=2023, help="Fiscal year (default: 2023)")
    parser.add_argument("--format", choices=["json", "bibtex"], default="json", help="Output format")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else None
    engine = AutoCitationEngine(data_dir=data_dir)

    print(f"[CITE] Generating citations for FY{args.year}...")
    report = engine.generate_benchmark_report(year=args.year)

    print(f"  Total claims: {report['total_claims']}")
    print(f"  By confidence: {report['by_confidence']}")

    out_path = Path(args.output) if args.output else None
    text = engine.export_citations(report["claims"], fmt=args.format, output_path=out_path)

    if out_path:
        print(f"  Written to: {out_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
