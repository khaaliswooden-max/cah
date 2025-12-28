"""
Repository Layer

High-level data access patterns for domain objects.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Iterator, Optional

from cah_engine.core.models import ClinicalEncounter, CostReportMetrics, FacilitySnapshot
from cah_engine.core.enums import EncounterType, ComplianceStatus
from cah_engine.storage.database import Database, get_database


class EncounterRepository:
    """Repository for clinical encounter data."""
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
    
    def save(self, encounter: ClinicalEncounter) -> None:
        """Save an encounter."""
        self.db.save_encounter(encounter)
    
    def save_batch(self, encounters: list[ClinicalEncounter]) -> int:
        """Save multiple encounters."""
        count = 0
        for encounter in encounters:
            self.save(encounter)
            count += 1
        return count
    
    def get_by_id(self, encounter_id: str) -> Optional[ClinicalEncounter]:
        """Get encounter by ID."""
        return self.db.get_encounter(encounter_id)
    
    def get_by_patient(
        self,
        patient_id: str,
        limit: int = 100,
    ) -> list[ClinicalEncounter]:
        """Get encounters for a patient."""
        rows = self.db.fetchall(
            "SELECT * FROM encounters WHERE patient_id = ? ORDER BY admit_datetime DESC LIMIT ?",
            (patient_id, limit)
        )
        return [self.db._row_to_encounter(row) for row in rows]
    
    def get_active(self) -> list[ClinicalEncounter]:
        """Get currently active encounters (not discharged)."""
        rows = self.db.fetchall(
            "SELECT * FROM encounters WHERE discharge_datetime IS NULL ORDER BY admit_datetime"
        )
        return [self.db._row_to_encounter(row) for row in rows]
    
    def get_by_date_range(
        self,
        start: datetime,
        end: datetime,
        encounter_type: Optional[EncounterType] = None,
    ) -> list[ClinicalEncounter]:
        """Get encounters within date range."""
        return self.db.get_encounters(
            start_date=start,
            end_date=end,
            encounter_type=encounter_type,
        )
    
    def get_recent(
        self,
        days: int = 30,
        encounter_type: Optional[EncounterType] = None,
    ) -> list[ClinicalEncounter]:
        """Get recent encounters."""
        start = datetime.now() - timedelta(days=days)
        return self.get_by_date_range(start, datetime.now(), encounter_type)
    
    def count_by_type(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> dict[EncounterType, int]:
        """Count encounters by type."""
        sql = "SELECT encounter_type, COUNT(*) as count FROM encounters WHERE 1=1"
        params = []
        
        if start:
            sql += " AND admit_datetime >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND admit_datetime <= ?"
            params.append(end.isoformat())
        
        sql += " GROUP BY encounter_type"
        
        rows = self.db.fetchall(sql, tuple(params))
        return {
            EncounterType(row["encounter_type"]): row["count"]
            for row in rows
        }
    
    def get_los_statistics(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> dict[str, float]:
        """Get length of stay statistics."""
        sql = """
            SELECT 
                AVG(los_hours) as avg_los,
                MIN(los_hours) as min_los,
                MAX(los_hours) as max_los,
                COUNT(*) as count
            FROM encounters
            WHERE discharge_datetime IS NOT NULL
        """
        params = []
        
        if start:
            sql += " AND admit_datetime >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND admit_datetime <= ?"
            params.append(end.isoformat())
        
        row = self.db.fetchone(sql, tuple(params))
        
        return {
            "average": row["avg_los"] or 0.0,
            "minimum": row["min_los"] or 0.0,
            "maximum": row["max_los"] or 0.0,
            "count": row["count"] or 0,
        }
    
    def get_transfer_rate(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> float:
        """Calculate transfer rate."""
        sql_total = "SELECT COUNT(*) FROM encounters WHERE discharge_datetime IS NOT NULL"
        sql_transfers = """
            SELECT COUNT(*) FROM encounters 
            WHERE discharge_datetime IS NOT NULL
            AND disposition IN ('02', '03', '62', '63')
        """
        params = []
        
        if start:
            sql_total += " AND admit_datetime >= ?"
            sql_transfers += " AND admit_datetime >= ?"
            params.append(start.isoformat())
        if end:
            sql_total += " AND admit_datetime <= ?"
            sql_transfers += " AND admit_datetime <= ?"
            params.append(end.isoformat())
        
        total = self.db.fetchone(sql_total, tuple(params))[0]
        transfers = self.db.fetchone(sql_transfers, tuple(params))[0]
        
        if total == 0:
            return 0.0
        return (transfers / total) * 100


class MetricsRepository:
    """Repository for metrics and time series data."""
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
    
    def save_metric(
        self,
        name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        dimension: Optional[str] = None,
        dimension_value: Optional[str] = None,
    ) -> None:
        """Save a metric value."""
        self.db.save_metric(
            metric_name=name,
            value=value,
            timestamp=timestamp,
            dimension=dimension,
            dimension_value=dimension_value,
        )
    
    def get_history(
        self,
        name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 365,
    ) -> list[tuple[datetime, float]]:
        """Get metric history."""
        return self.db.get_metric_history(name, start, end, limit)
    
    def get_latest(self, name: str) -> Optional[tuple[datetime, float]]:
        """Get latest value for a metric."""
        history = self.get_history(name, limit=1)
        return history[0] if history else None
    
    def get_average(
        self,
        name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[float]:
        """Get average value for a metric."""
        sql = "SELECT AVG(metric_value) FROM metrics_history WHERE metric_name = ?"
        params = [name]
        
        if start:
            sql += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND timestamp <= ?"
            params.append(end.isoformat())
        
        row = self.db.fetchone(sql, tuple(params))
        return row[0] if row else None
    
    def save_daily_census(self, census: int, target_date: Optional[date] = None) -> None:
        """Save daily census."""
        if target_date is None:
            target_date = date.today()
        
        self.save_metric(
            name="daily_census",
            value=float(census),
            timestamp=datetime.combine(target_date, datetime.min.time()),
        )
    
    def get_census_history(self, days: int = 30) -> list[tuple[date, int]]:
        """Get census history."""
        start = datetime.now() - timedelta(days=days)
        history = self.get_history("daily_census", start=start)
        return [(dt.date(), int(val)) for dt, val in history]


class ComplianceRepository:
    """Repository for compliance reports and status."""
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
    
    def save_report(
        self,
        facility_id: str,
        report_data: dict,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> int:
        """Save compliance report."""
        import json
        
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO compliance_reports (
                    facility_id, generated_at, period_start, period_end,
                    overall_status, report_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                facility_id,
                datetime.now().isoformat(),
                period_start.isoformat() if period_start else None,
                period_end.isoformat() if period_end else None,
                report_data.get("overall_status", "unknown"),
                json.dumps(report_data),
                datetime.now().isoformat(),
            ))
            return cursor.lastrowid
    
    def get_latest_report(self, facility_id: str) -> Optional[dict]:
        """Get latest compliance report."""
        import json
        
        row = self.db.fetchone("""
            SELECT * FROM compliance_reports
            WHERE facility_id = ?
            ORDER BY generated_at DESC
            LIMIT 1
        """, (facility_id,))
        
        if row is None:
            return None
        
        return {
            "id": row["id"],
            "facility_id": row["facility_id"],
            "generated_at": row["generated_at"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "overall_status": row["overall_status"],
            "data": json.loads(row["report_data"]),
        }
    
    def get_report_history(
        self,
        facility_id: str,
        limit: int = 12,
    ) -> list[dict]:
        """Get compliance report history."""
        import json
        
        rows = self.db.fetchall("""
            SELECT id, facility_id, generated_at, overall_status
            FROM compliance_reports
            WHERE facility_id = ?
            ORDER BY generated_at DESC
            LIMIT ?
        """, (facility_id, limit))
        
        return [
            {
                "id": row["id"],
                "generated_at": row["generated_at"],
                "status": row["overall_status"],
            }
            for row in rows
        ]
    
    def get_compliance_trend(
        self,
        facility_id: str,
        months: int = 12,
    ) -> list[dict]:
        """Get compliance status trend."""
        import json
        
        rows = self.db.fetchall("""
            SELECT generated_at, overall_status, report_data
            FROM compliance_reports
            WHERE facility_id = ?
            ORDER BY generated_at DESC
            LIMIT ?
        """, (facility_id, months))
        
        trend = []
        for row in rows:
            data = json.loads(row["report_data"])
            trend.append({
                "date": row["generated_at"],
                "status": row["overall_status"],
                "los_hours": data.get("summary", {}).get("average_los_hours"),
                "staffed_beds": data.get("summary", {}).get("current_staffed_beds"),
            })
        
        return trend


class CostReportRepository:
    """Repository for cost report data."""
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
    
    def save(self, metrics: CostReportMetrics) -> None:
        """Save cost report metrics."""
        self.db.save_cost_report(metrics)
    
    def get_by_provider(
        self,
        provider_id: str,
        fiscal_year: Optional[date] = None,
    ) -> Optional[CostReportMetrics]:
        """Get cost report by provider."""
        return self.db.get_cost_report(provider_id, fiscal_year)
    
    def get_all_years(self, provider_id: str) -> list[CostReportMetrics]:
        """Get all cost reports for a provider."""
        rows = self.db.fetchall(
            "SELECT * FROM cost_reports WHERE provider_id = ? ORDER BY fiscal_year_end DESC",
            (provider_id,)
        )
        return [self.db._row_to_cost_report(row) for row in rows]
    
    def get_trend(
        self,
        provider_id: str,
        metric: str,
        years: int = 5,
    ) -> list[dict]:
        """Get trend for a specific metric."""
        reports = self.get_all_years(provider_id)[:years]
        
        trend = []
        for report in reports:
            value = None
            if metric == "operating_margin":
                value = report.operating_margin
            elif metric == "occupancy_rate":
                value = report.occupancy_rate
            elif metric == "labor_cost_ratio":
                value = report.labor_cost_ratio * 100
            elif metric == "average_los":
                value = report.average_los_hours
            elif metric == "discharges":
                value = report.discharges
            
            if value is not None:
                trend.append({
                    "fiscal_year": report.fiscal_year_end.isoformat(),
                    "value": value,
                })
        
        return trend

