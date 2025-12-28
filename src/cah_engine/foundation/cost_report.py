"""
Cost Report Parser

Extract structured financial data from CMS 2552-10 cost reports.
Parses key worksheets to derive financial and operational metrics.
"""

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional
from enum import Enum

from cah_engine.core.models import CostReportMetrics, ValidationResult


class CostReportWorksheet(str, Enum):
    """CMS 2552-10 worksheet identifiers."""
    
    S2 = "S200000"      # Facility identification, bed counts
    S3_PART_I = "S300001"  # Revenue by payer (Medicare)
    S3_PART_II = "S300002"  # Revenue by payer (Medicaid)
    S3_PART_III = "S300003"  # Revenue by payer (other)
    G2 = "G200000"      # Salary and wage costs
    G3 = "G300000"      # Other costs
    E = "E00000"        # Cost allocation
    L = "L00000"        # Balance sheet


@dataclass
class WorksheetData:
    """Data extracted from a single worksheet."""
    
    worksheet_id: str
    rows: dict[int, dict[int, str]] = field(default_factory=dict)
    
    def get_value(self, row: int, column: int, default: str = "") -> str:
        """Get value at specific row and column."""
        return self.rows.get(row, {}).get(column, default)
    
    def get_numeric(self, row: int, column: int, default: Decimal = Decimal("0")) -> Decimal:
        """Get numeric value at specific row and column."""
        value = self.get_value(row, column)
        if not value:
            return default
        
        # Clean the value
        value = re.sub(r"[,$()%]", "", value.strip())
        
        # Handle parentheses for negative numbers
        if "(" in self.get_value(row, column):
            value = "-" + value
        
        try:
            return Decimal(value)
        except InvalidOperation:
            return default
    
    def get_int(self, row: int, column: int, default: int = 0) -> int:
        """Get integer value at specific row and column."""
        value = self.get_numeric(row, column, Decimal(default))
        return int(value)


@dataclass
class CostReportParseResult:
    """Result of parsing a cost report."""
    
    metrics: Optional[CostReportMetrics]
    worksheets: dict[str, WorksheetData] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_file: str = ""
    
    @property
    def success(self) -> bool:
        """Check if parsing was successful."""
        return self.metrics is not None and len(self.errors) == 0


class CostReportParser:
    """
    Parse CMS 2552-10 cost reports.
    
    Supports multiple input formats:
    - HCRIS CSV format (from CMS downloads)
    - Excel export format
    - JSON format
    
    Key worksheets extracted:
    - S-2: Facility identification, bed counts
    - S-3: Revenue by payer class
    - G-2: Salary and wage costs
    - G-3: Other costs
    - E: Cost allocation
    - L: Balance sheet
    """
    
    # Worksheet row/column mappings for key metrics
    # Format: (worksheet, row, column)
    FIELD_MAPPINGS = {
        # S-2 Worksheet - Facility Info
        "provider_id": ("S200000", 1, 1),
        "fiscal_year_begin": ("S200000", 2, 1),
        "fiscal_year_end": ("S200000", 2, 2),
        "total_beds": ("S200000", 7, 1),
        "staffed_beds_acute": ("S200000", 8, 1),
        "staffed_beds_swing": ("S200000", 8, 2),
        
        # S-3 Worksheet - Statistics
        "patient_days": ("S300001", 1, 6),
        "discharges": ("S300001", 14, 6),
        "ed_visits": ("S300001", 24, 6),
        "swing_bed_days": ("S300001", 200, 6),
        
        # G-2 Worksheet - Salaries
        "total_salaries": ("G200000", 100, 1),
        
        # G-3 Worksheet - Other Costs
        "total_other_costs": ("G300000", 100, 1),
        
        # Various - Financial
        "net_patient_revenue": ("G300000", 1, 3),
        "total_operating_revenue": ("G300000", 5, 3),
        "total_operating_expenses": ("G300000", 30, 3),
    }
    
    def __init__(self):
        self.current_year = datetime.now().year
    
    def parse(self, source: Path | str) -> CostReportParseResult:
        """
        Parse a cost report file.
        
        Args:
            source: Path to cost report file
            
        Returns:
            CostReportParseResult with extracted metrics
        """
        source_path = Path(source)
        
        if not source_path.exists():
            return CostReportParseResult(
                metrics=None,
                errors=[f"File not found: {source_path}"],
                source_file=str(source_path),
            )
        
        suffix = source_path.suffix.lower()
        
        if suffix == ".csv":
            return self._parse_csv(source_path)
        elif suffix == ".json":
            return self._parse_json(source_path)
        else:
            return CostReportParseResult(
                metrics=None,
                errors=[f"Unsupported file format: {suffix}"],
                source_file=str(source_path),
            )
    
    def _parse_csv(self, source: Path) -> CostReportParseResult:
        """Parse HCRIS CSV format cost report."""
        worksheets: dict[str, WorksheetData] = {}
        errors = []
        warnings = []
        
        try:
            with open(source, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    worksheet_id = row.get("WKSHT_CD", "").strip()
                    line_num = self._parse_int(row.get("LINE_NUM", "0"))
                    column = self._parse_int(row.get("CLMN_NUM", "0"))
                    value = row.get("ITM_VAL_NUM", "")
                    
                    if worksheet_id not in worksheets:
                        worksheets[worksheet_id] = WorksheetData(worksheet_id=worksheet_id)
                    
                    if line_num not in worksheets[worksheet_id].rows:
                        worksheets[worksheet_id].rows[line_num] = {}
                    
                    worksheets[worksheet_id].rows[line_num][column] = value
        
        except Exception as e:
            errors.append(f"Error reading CSV: {e}")
            return CostReportParseResult(
                metrics=None,
                worksheets=worksheets,
                errors=errors,
                source_file=str(source),
            )
        
        # Extract metrics from worksheets
        metrics = self._extract_metrics(worksheets, errors, warnings)
        
        return CostReportParseResult(
            metrics=metrics,
            worksheets=worksheets,
            errors=errors,
            warnings=warnings,
            source_file=str(source),
        )
    
    def _parse_json(self, source: Path) -> CostReportParseResult:
        """Parse JSON format cost report."""
        errors = []
        warnings = []
        
        try:
            with open(source, "r") as f:
                data = json.load(f)
        except Exception as e:
            return CostReportParseResult(
                metrics=None,
                errors=[f"Error reading JSON: {e}"],
                source_file=str(source),
            )
        
        # Convert JSON to worksheet format
        worksheets: dict[str, WorksheetData] = {}
        
        if isinstance(data, dict):
            # Assume direct metrics format
            if "provider_id" in data:
                metrics = self._metrics_from_dict(data, errors, warnings)
                return CostReportParseResult(
                    metrics=metrics,
                    worksheets=worksheets,
                    errors=errors,
                    warnings=warnings,
                    source_file=str(source),
                )
            
            # Assume worksheet format
            for ws_id, ws_data in data.items():
                if isinstance(ws_data, dict):
                    worksheet = WorksheetData(worksheet_id=ws_id)
                    for row_key, row_data in ws_data.items():
                        row_num = self._parse_int(row_key)
                        if isinstance(row_data, dict):
                            worksheet.rows[row_num] = {
                                self._parse_int(k): str(v)
                                for k, v in row_data.items()
                            }
                    worksheets[ws_id] = worksheet
        
        metrics = self._extract_metrics(worksheets, errors, warnings)
        
        return CostReportParseResult(
            metrics=metrics,
            worksheets=worksheets,
            errors=errors,
            warnings=warnings,
            source_file=str(source),
        )
    
    def _extract_metrics(
        self,
        worksheets: dict[str, WorksheetData],
        errors: list[str],
        warnings: list[str],
    ) -> Optional[CostReportMetrics]:
        """Extract metrics from parsed worksheets."""
        
        def get_value(field_name: str) -> str:
            if field_name not in self.FIELD_MAPPINGS:
                return ""
            ws_id, row, col = self.FIELD_MAPPINGS[field_name]
            if ws_id not in worksheets:
                return ""
            return worksheets[ws_id].get_value(row, col)
        
        def get_numeric(field_name: str) -> Decimal:
            if field_name not in self.FIELD_MAPPINGS:
                return Decimal("0")
            ws_id, row, col = self.FIELD_MAPPINGS[field_name]
            if ws_id not in worksheets:
                return Decimal("0")
            return worksheets[ws_id].get_numeric(row, col)
        
        def get_int(field_name: str) -> int:
            if field_name not in self.FIELD_MAPPINGS:
                return 0
            ws_id, row, col = self.FIELD_MAPPINGS[field_name]
            if ws_id not in worksheets:
                return 0
            return worksheets[ws_id].get_int(row, col)
        
        # Required field: provider_id
        provider_id = get_value("provider_id")
        if not provider_id:
            # Try to find it in S-2 worksheet
            if "S200000" in worksheets:
                for row_num, row_data in worksheets["S200000"].rows.items():
                    if row_data.get(1):
                        provider_id = row_data[1]
                        break
        
        if not provider_id:
            errors.append("Could not extract provider ID")
            return None
        
        # Parse fiscal year end
        fy_end_str = get_value("fiscal_year_end")
        try:
            if fy_end_str:
                fy_end = self._parse_date(fy_end_str)
            else:
                fy_end = date(self.current_year, 12, 31)
        except ValueError:
            fy_end = date(self.current_year, 12, 31)
            warnings.append(f"Could not parse fiscal year end: {fy_end_str}")
        
        # Extract bed counts
        total_beds = get_int("total_beds")
        staffed_beds_acute = get_int("staffed_beds_acute")
        staffed_beds_swing = get_int("staffed_beds_swing")
        staffed_beds = staffed_beds_acute + staffed_beds_swing
        
        if staffed_beds == 0 and total_beds > 0:
            staffed_beds = total_beds
            warnings.append("Using total beds as staffed beds")
        
        # Validate CAH bed limit
        if staffed_beds > 25:
            warnings.append(f"Staffed beds ({staffed_beds}) exceeds CAH limit of 25")
        
        # Extract statistics
        patient_days = get_int("patient_days")
        discharges = get_int("discharges")
        ed_visits = get_int("ed_visits")
        swing_bed_days = get_int("swing_bed_days")
        
        # Extract financial data
        net_patient_revenue = get_numeric("net_patient_revenue")
        total_operating_revenue = get_numeric("total_operating_revenue")
        total_operating_expenses = get_numeric("total_operating_expenses")
        salary_expenses = get_numeric("total_salaries")
        
        # If operating revenue is missing, use net patient revenue
        if total_operating_revenue == 0:
            total_operating_revenue = net_patient_revenue
        
        # Calculate FTE (from G-2 if available)
        fte_count = 0.0
        if "G200000" in worksheets:
            # FTE is often on line 1, column 2
            fte_count = float(worksheets["G200000"].get_numeric(1, 2, Decimal("0")))
        
        return CostReportMetrics(
            provider_id=provider_id,
            fiscal_year_end=fy_end,
            total_beds=total_beds,
            staffed_beds=staffed_beds,
            patient_days=patient_days,
            discharges=discharges,
            net_patient_revenue=net_patient_revenue,
            total_operating_revenue=total_operating_revenue,
            total_operating_expenses=total_operating_expenses,
            salary_expenses=salary_expenses,
            fte_count=fte_count,
            ed_visits=ed_visits,
            swing_bed_days=swing_bed_days,
        )
    
    def _metrics_from_dict(
        self,
        data: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> Optional[CostReportMetrics]:
        """Create metrics from a flat dictionary."""
        provider_id = data.get("provider_id", "")
        if not provider_id:
            errors.append("Missing provider_id")
            return None
        
        fy_end_str = data.get("fiscal_year_end", "")
        try:
            fy_end = self._parse_date(fy_end_str) if fy_end_str else date.today()
        except ValueError:
            fy_end = date.today()
        
        return CostReportMetrics(
            provider_id=provider_id,
            fiscal_year_end=fy_end,
            total_beds=data.get("total_beds", 0),
            staffed_beds=data.get("staffed_beds", 0),
            patient_days=data.get("patient_days", 0),
            discharges=data.get("discharges", 0),
            net_patient_revenue=Decimal(str(data.get("net_patient_revenue", 0))),
            total_operating_revenue=Decimal(str(data.get("total_operating_revenue", 0))),
            total_operating_expenses=Decimal(str(data.get("total_operating_expenses", 0))),
            salary_expenses=Decimal(str(data.get("salary_expenses", 0))),
            fte_count=float(data.get("fte_count", 0)),
            ed_visits=data.get("ed_visits", 0),
            swing_bed_days=data.get("swing_bed_days", 0),
        )
    
    def _parse_int(self, value: str) -> int:
        """Parse integer from string."""
        try:
            return int(float(value.strip()))
        except (ValueError, AttributeError):
            return 0
    
    def _parse_date(self, value: str) -> date:
        """Parse date from various formats."""
        value = value.strip()
        
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%Y%m%d",
            "%m-%d-%Y",
            "%d-%m-%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date: {value}")
    
    def validate(self, metrics: CostReportMetrics) -> ValidationResult:
        """Validate extracted metrics."""
        issues = []
        warnings = []
        
        # CAH-specific validations
        if metrics.staffed_beds > 25:
            issues.append(
                f"Staffed beds ({metrics.staffed_beds}) exceeds CAH maximum of 25"
            )
        
        if metrics.average_los_hours > 96:
            issues.append(
                f"Average LOS ({metrics.average_los_hours:.1f}h) exceeds 96h CAH limit"
            )
        
        # Financial validations
        if metrics.operating_margin < -10:
            warnings.append(
                f"Operating margin ({metrics.operating_margin:.1f}%) indicates severe financial stress"
            )
        
        if metrics.labor_cost_ratio > 0.70:
            warnings.append(
                f"Labor cost ratio ({metrics.labor_cost_ratio:.1%}) exceeds typical CAH range"
            )
        
        # Occupancy validation
        if metrics.occupancy_rate < 20:
            warnings.append(
                f"Occupancy rate ({metrics.occupancy_rate:.1f}%) is very low"
            )
        elif metrics.occupancy_rate > 80:
            warnings.append(
                f"Occupancy rate ({metrics.occupancy_rate:.1f}%) approaching capacity"
            )
        
        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
        )


def parse_hcris_bulk(directory: Path | str) -> list[CostReportParseResult]:
    """
    Parse all cost reports in a directory (HCRIS bulk download format).
    
    Args:
        directory: Path to directory containing cost report files
        
    Returns:
        List of parse results
    """
    dir_path = Path(directory)
    parser = CostReportParser()
    results = []
    
    for file_path in dir_path.glob("*.csv"):
        result = parser.parse(file_path)
        results.append(result)
    
    return results


def aggregate_metrics(results: list[CostReportParseResult]) -> dict[str, Any]:
    """
    Aggregate metrics across multiple cost reports.
    
    Args:
        results: List of parse results
        
    Returns:
        Dictionary with aggregated statistics
    """
    metrics_list = [r.metrics for r in results if r.metrics is not None]
    
    if not metrics_list:
        return {"count": 0}
    
    total_revenue = sum(m.total_operating_revenue for m in metrics_list)
    total_expenses = sum(m.total_operating_expenses for m in metrics_list)
    
    return {
        "count": len(metrics_list),
        "total_beds": sum(m.staffed_beds for m in metrics_list),
        "total_discharges": sum(m.discharges for m in metrics_list),
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses),
        "aggregate_margin": float((total_revenue - total_expenses) / total_revenue * 100)
        if total_revenue > 0 else 0,
        "avg_occupancy": sum(m.occupancy_rate for m in metrics_list) / len(metrics_list),
        "avg_los_hours": sum(m.average_los_hours for m in metrics_list) / len(metrics_list),
    }

