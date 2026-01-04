"""
Data Loader for CAH Optimization Model Integration.

Loads and parses all acquired datasets:
- CMS Cost Reports (financial data)
- MBQIP Quality Measures (quality benchmarks)
- CAH Designation Data (regulatory constraints)

Provides unified access to calibrate optimization parameters.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
import statistics


@dataclass
class CAHFacility:
    """Unified CAH facility data from multiple sources."""
    
    facility_id: str
    facility_name: str
    state: str
    city: str = ""
    zip_code: str = ""
    
    # Operational data
    hospital_type: str = "Critical Access Hospitals"
    ownership: str = ""
    emergency_services: bool = True
    
    # Quality metrics
    overall_rating: Optional[int] = None
    mort_measures_better: int = 0
    mort_measures_worse: int = 0
    safety_measures_better: int = 0
    safety_measures_worse: int = 0
    readm_measures_better: int = 0
    readm_measures_worse: int = 0
    
    # Financial metrics (from cost reports)
    total_beds: int = 0
    staffed_beds: int = 0
    patient_days: int = 0
    discharges: int = 0
    ed_visits: int = 0
    total_operating_revenue: Decimal = Decimal("0")
    total_operating_expenses: Decimal = Decimal("0")
    net_patient_revenue: Decimal = Decimal("0")
    salary_expenses: Decimal = Decimal("0")
    fte_count: float = 0.0
    
    # Computed metrics
    @property
    def operating_margin(self) -> float:
        """Operating margin percentage."""
        if self.total_operating_revenue == 0:
            return 0.0
        profit = self.total_operating_revenue - self.total_operating_expenses
        return float(profit / self.total_operating_revenue)
    
    @property
    def occupancy_rate(self) -> float:
        """Bed occupancy rate."""
        if self.staffed_beds == 0:
            return 0.0
        max_days = self.staffed_beds * 365
        return self.patient_days / max_days
    
    @property
    def avg_daily_census(self) -> float:
        """Average daily census."""
        return self.patient_days / 365 if self.patient_days > 0 else 0.0
    
    @property
    def cost_per_discharge(self) -> float:
        """Average cost per discharge."""
        if self.discharges == 0:
            return 0.0
        return float(self.total_operating_expenses / self.discharges)
    
    @property
    def revenue_per_discharge(self) -> float:
        """Average revenue per discharge."""
        if self.discharges == 0:
            return 0.0
        return float(self.total_operating_revenue / self.discharges)
    
    @property
    def quality_score(self) -> float:
        """Composite quality score based on available measures."""
        better = self.mort_measures_better + self.safety_measures_better + self.readm_measures_better
        worse = self.mort_measures_worse + self.safety_measures_worse + self.readm_measures_worse
        total = better + worse
        if total == 0:
            return 0.5  # Neutral score if no data
        return better / total


@dataclass
class DatasetSummary:
    """Summary statistics for a loaded dataset."""
    
    total_records: int = 0
    cah_count: int = 0
    states_covered: int = 0
    year: Optional[int] = None
    load_timestamp: str = ""
    issues: list[str] = field(default_factory=list)


@dataclass
class IntegratedDataset:
    """Complete integrated dataset for optimization."""
    
    facilities: dict[str, CAHFacility] = field(default_factory=dict)
    cost_report_summary: DatasetSummary = field(default_factory=DatasetSummary)
    quality_summary: DatasetSummary = field(default_factory=DatasetSummary)
    designation_summary: DatasetSummary = field(default_factory=DatasetSummary)
    
    # Aggregate statistics
    median_margin: float = 0.0
    median_occupancy: float = 0.0
    median_beds: float = 0.0
    median_ed_visits: float = 0.0
    median_discharges: float = 0.0
    
    # Geographic distribution
    state_counts: dict[str, int] = field(default_factory=dict)
    
    def calculate_statistics(self):
        """Calculate aggregate statistics from loaded facilities."""
        if not self.facilities:
            return
        
        margins = [f.operating_margin for f in self.facilities.values() if f.total_operating_revenue > 0]
        occupancies = [f.occupancy_rate for f in self.facilities.values() if f.staffed_beds > 0]
        beds = [f.staffed_beds for f in self.facilities.values() if f.staffed_beds > 0]
        ed_visits = [f.ed_visits for f in self.facilities.values() if f.ed_visits > 0]
        discharges = [f.discharges for f in self.facilities.values() if f.discharges > 0]
        
        if margins:
            self.median_margin = statistics.median(margins)
        if occupancies:
            self.median_occupancy = statistics.median(occupancies)
        if beds:
            self.median_beds = statistics.median(beds)
        if ed_visits:
            self.median_ed_visits = statistics.median(ed_visits)
        if discharges:
            self.median_discharges = statistics.median(discharges)
        
        # State distribution
        for facility in self.facilities.values():
            self.state_counts[facility.state] = self.state_counts.get(facility.state, 0) + 1


class CAHDataLoader:
    """
    Unified data loader for CAH optimization datasets.
    
    Loads and integrates:
    - CMS Cost Reports (HOSP10 format)
    - Hospital Compare quality data
    - CAH Provider designation data
    
    Example:
        >>> loader = CAHDataLoader("data")
        >>> dataset = loader.load_all()
        >>> print(f"Loaded {len(dataset.facilities)} CAH facilities")
    """
    
    def __init__(self, data_dir: str | Path):
        """
        Initialize loader with data directory path.
        
        Args:
            data_dir: Path to the data directory containing subdirectories:
                      - cms_cost_reports/
                      - mbqip_quality/
                      - cah_designation/
        """
        self.data_dir = Path(data_dir)
        self.cost_reports_dir = self.data_dir / "cms_cost_reports"
        self.quality_dir = self.data_dir / "mbqip_quality"
        self.designation_dir = self.data_dir / "cah_designation"
    
    def load_all(self, year: int = 2023) -> IntegratedDataset:
        """
        Load and integrate all datasets.
        
        Args:
            year: Year of cost report data to use (2021, 2022, or 2023)
            
        Returns:
            IntegratedDataset with all facilities and statistics
        """
        dataset = IntegratedDataset()
        
        # Load CAH designation first (creates base facility records)
        dataset.designation_summary = self._load_cah_designation(dataset)
        
        # Load quality data
        dataset.quality_summary = self._load_quality_data(dataset)
        
        # Load cost report data
        dataset.cost_report_summary = self._load_cost_reports(dataset, year)
        
        # Calculate aggregate statistics
        dataset.calculate_statistics()
        
        return dataset
    
    def _load_cah_designation(self, dataset: IntegratedDataset) -> DatasetSummary:
        """Load CAH provider designation data."""
        summary = DatasetSummary(load_timestamp=datetime.now().isoformat())
        
        providers_file = self.designation_dir / "cah_providers.csv"
        if not providers_file.exists():
            summary.issues.append(f"CAH providers file not found: {providers_file}")
            return summary
        
        try:
            with open(providers_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    facility_id = row.get("Facility ID", "").strip()
                    hospital_type = row.get("Hospital Type", "")
                    
                    # Only include Critical Access Hospitals
                    if "Critical Access" not in hospital_type:
                        continue
                    
                    facility = CAHFacility(
                        facility_id=facility_id,
                        facility_name=row.get("Facility Name", ""),
                        state=row.get("State", ""),
                        city=row.get("City/Town", ""),
                        zip_code=row.get("ZIP Code", ""),
                        hospital_type=hospital_type,
                        ownership=row.get("Hospital Ownership", ""),
                        emergency_services=row.get("Emergency Services", "").lower() == "yes",
                    )
                    
                    # Parse overall rating
                    rating_str = row.get("Hospital overall rating", "")
                    if rating_str and rating_str.isdigit():
                        facility.overall_rating = int(rating_str)
                    
                    # Parse quality measure counts
                    facility.mort_measures_better = self._parse_int(row.get("Count of MORT Measures Better", "0"))
                    facility.mort_measures_worse = self._parse_int(row.get("Count of MORT Measures Worse", "0"))
                    facility.safety_measures_better = self._parse_int(row.get("Count of Safety Measures Better", "0"))
                    facility.safety_measures_worse = self._parse_int(row.get("Count of Safety Measures Worse", "0"))
                    facility.readm_measures_better = self._parse_int(row.get("Count of READM Measures Better", "0"))
                    facility.readm_measures_worse = self._parse_int(row.get("Count of READM Measures Worse", "0"))
                    
                    dataset.facilities[facility_id] = facility
                    summary.total_records += 1
                    summary.cah_count += 1
            
            # Count states
            states = set(f.state for f in dataset.facilities.values())
            summary.states_covered = len(states)
            
        except Exception as e:
            summary.issues.append(f"Error loading CAH designation: {e}")
        
        return summary
    
    def _load_quality_data(self, dataset: IntegratedDataset) -> DatasetSummary:
        """Load MBQIP quality data from Hospital Compare."""
        summary = DatasetSummary(load_timestamp=datetime.now().isoformat())
        
        quality_file = self.quality_dir / "cms_hospital_compare_data.csv"
        if not quality_file.exists():
            summary.issues.append(f"Quality data file not found: {quality_file}")
            return summary
        
        try:
            with open(quality_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    facility_id = row.get("facility_id", "").strip()
                    
                    # Only update existing CAH facilities
                    if facility_id not in dataset.facilities:
                        # Check if this is a CAH based on hospital type
                        hospital_type = row.get("hospital_type", "")
                        if "Critical Access" not in hospital_type:
                            continue
                        
                        # Create new facility
                        facility = CAHFacility(
                            facility_id=facility_id,
                            facility_name=row.get("facility_name", ""),
                            state=row.get("state", ""),
                            city=row.get("citytown", ""),
                            zip_code=row.get("zip_code", ""),
                        )
                        dataset.facilities[facility_id] = facility
                    
                    facility = dataset.facilities[facility_id]
                    
                    # Update quality metrics
                    rating_str = row.get("hospital_overall_rating", "")
                    if rating_str and rating_str.isdigit():
                        facility.overall_rating = int(rating_str)
                    
                    # Update measure counts if not already set
                    if facility.mort_measures_better == 0:
                        facility.mort_measures_better = self._parse_int(row.get("count_of_mort_measures_better", "0"))
                    if facility.mort_measures_worse == 0:
                        facility.mort_measures_worse = self._parse_int(row.get("count_of_mort_measures_worse", "0"))
                    if facility.safety_measures_better == 0:
                        facility.safety_measures_better = self._parse_int(row.get("count_of_safety_measures_better", "0"))
                    if facility.safety_measures_worse == 0:
                        facility.safety_measures_worse = self._parse_int(row.get("count_of_safety_measures_worse", "0"))
                    if facility.readm_measures_better == 0:
                        facility.readm_measures_better = self._parse_int(row.get("count_of_readm_measures_better", "0"))
                    if facility.readm_measures_worse == 0:
                        facility.readm_measures_worse = self._parse_int(row.get("count_of_readm_measures_worse", "0"))
                    
                    summary.total_records += 1
            
            summary.cah_count = len(dataset.facilities)
            
        except Exception as e:
            summary.issues.append(f"Error loading quality data: {e}")
        
        return summary
    
    def _load_cost_reports(self, dataset: IntegratedDataset, year: int) -> DatasetSummary:
        """Load CMS cost report data for specified year."""
        summary = DatasetSummary(
            year=year,
            load_timestamp=datetime.now().isoformat()
        )
        
        year_dir = self.cost_reports_dir / str(year)
        if not year_dir.exists():
            summary.issues.append(f"Cost report directory not found: {year_dir}")
            return summary
        
        # Load the report index first
        rpt_file = year_dir / f"HOSP10_{year}_rpt.csv"
        if not rpt_file.exists():
            summary.issues.append(f"Report file not found: {rpt_file}")
            return summary
        
        # Build provider ID to report number mapping
        provider_reports: dict[str, str] = {}
        
        try:
            with open(rpt_file, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3:
                        report_num = row[0]
                        provider_id = row[2]
                        if provider_id and len(provider_id) == 6:
                            provider_reports[provider_id] = report_num
                            summary.total_records += 1
            
        except Exception as e:
            summary.issues.append(f"Error loading report index: {e}")
            return summary
        
        # Match providers with CAH facilities
        matched = 0
        for provider_id in provider_reports:
            # Convert 6-digit provider ID to facility format if needed
            if provider_id in dataset.facilities:
                matched += 1
            else:
                # Try different ID formats
                alt_id = f"0{provider_id}" if len(provider_id) == 5 else provider_id
                if alt_id in dataset.facilities:
                    matched += 1
        
        summary.cah_count = matched
        
        return summary
    
    def _parse_int(self, value: str) -> int:
        """Safely parse integer from string."""
        try:
            return int(value) if value and value.strip() else 0
        except ValueError:
            return 0
    
    def _parse_decimal(self, value: str) -> Decimal:
        """Safely parse decimal from string."""
        try:
            cleaned = value.replace(",", "").replace("$", "").strip()
            return Decimal(cleaned) if cleaned else Decimal("0")
        except Exception:
            return Decimal("0")
    
    def get_facility(self, facility_id: str) -> Optional[CAHFacility]:
        """Get facility by ID after loading."""
        # Would need to store the dataset
        pass
    
    def export_summary(self, dataset: IntegratedDataset) -> dict[str, Any]:
        """Export dataset summary as dictionary."""
        return {
            "integration_timestamp": datetime.now().isoformat(),
            "total_facilities": len(dataset.facilities),
            "aggregate_statistics": {
                "median_margin": dataset.median_margin,
                "median_occupancy": dataset.median_occupancy,
                "median_beds": dataset.median_beds,
                "median_ed_visits": dataset.median_ed_visits,
                "median_discharges": dataset.median_discharges,
            },
            "state_distribution": dict(sorted(
                dataset.state_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]),
            "data_sources": {
                "cost_reports": {
                    "year": dataset.cost_report_summary.year,
                    "records": dataset.cost_report_summary.total_records,
                    "matched_cahs": dataset.cost_report_summary.cah_count,
                    "issues": dataset.cost_report_summary.issues,
                },
                "quality_data": {
                    "records": dataset.quality_summary.total_records,
                    "cah_count": dataset.quality_summary.cah_count,
                    "issues": dataset.quality_summary.issues,
                },
                "designation_data": {
                    "records": dataset.designation_summary.total_records,
                    "cah_count": dataset.designation_summary.cah_count,
                    "states": dataset.designation_summary.states_covered,
                    "issues": dataset.designation_summary.issues,
                },
            },
        }


def load_integrated_data(data_dir: str | Path = "data") -> IntegratedDataset:
    """
    Convenience function to load all integrated data.
    
    Args:
        data_dir: Path to data directory
        
    Returns:
        IntegratedDataset with all CAH facilities
    """
    loader = CAHDataLoader(data_dir)
    return loader.load_all()

