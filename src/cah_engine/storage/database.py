"""
Database Layer

SQLite-based storage designed for MV-CAHI compliance.
Minimal footprint, offline-first operation.
"""

import sqlite3
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Optional

from cah_engine.core.models import ClinicalEncounter, CostReportMetrics, FacilitySnapshot
from cah_engine.core.enums import EncounterType, DispositionCode


@dataclass
class DatabaseConfig:
    """Database configuration."""
    
    db_path: Path
    echo: bool = False
    timeout: float = 30.0
    
    def __post_init__(self):
        if isinstance(self.db_path, str):
            self.db_path = Path(self.db_path)


# Schema version for migrations
SCHEMA_VERSION = 1

# SQL schema definitions
SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Clinical encounters
CREATE TABLE IF NOT EXISTS encounters (
    encounter_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    admit_datetime TEXT NOT NULL,
    discharge_datetime TEXT,
    encounter_type TEXT NOT NULL,
    principal_diagnosis TEXT,
    secondary_diagnoses TEXT,  -- JSON array
    procedures TEXT,  -- JSON array
    attending_provider TEXT,
    disposition TEXT,
    los_hours REAL,
    drg TEXT,
    admission_source TEXT,
    admission_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_status TEXT DEFAULT 'pending'
);

-- Cost report metrics
CREATE TABLE IF NOT EXISTS cost_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL,
    fiscal_year_end TEXT NOT NULL,
    total_beds INTEGER,
    staffed_beds INTEGER,
    patient_days INTEGER,
    discharges INTEGER,
    net_patient_revenue TEXT,  -- Decimal as string
    total_operating_revenue TEXT,
    total_operating_expenses TEXT,
    salary_expenses TEXT,
    fte_count REAL,
    ed_visits INTEGER,
    swing_bed_days INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(provider_id, fiscal_year_end)
);

-- Facility snapshots (time series)
CREATE TABLE IF NOT EXISTS facility_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    staffed_beds INTEGER,
    occupied_beds INTEGER,
    ed_patients INTEGER,
    pending_admissions INTEGER,
    pending_discharges INTEGER,
    rn_count INTEGER,
    physician_on_site INTEGER,
    physician_on_call INTEGER,
    ehr_online INTEGER,
    lab_online INTEGER,
    imaging_online INTEGER
);

-- Compliance reports
CREATE TABLE IF NOT EXISTS compliance_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    overall_status TEXT,
    report_data TEXT,  -- JSON
    created_at TEXT NOT NULL
);

-- Claims
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    encounter_id TEXT,
    payer_id TEXT NOT NULL,
    service_date TEXT NOT NULL,
    claim_type TEXT,
    total_charges TEXT,
    diagnosis_codes TEXT,  -- JSON array
    procedure_codes TEXT,  -- JSON array
    status TEXT,
    submitted_date TEXT,
    paid_amount TEXT,
    denial_codes TEXT,  -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Analytics metrics (time series)
CREATE TABLE IF NOT EXISTS metrics_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    timestamp TEXT NOT NULL,
    dimension TEXT,  -- Optional dimension (e.g., payer, department)
    dimension_value TEXT
);

-- Model artifacts
CREATE TABLE IF NOT EXISTS model_artifacts (
    model_name TEXT PRIMARY KEY,
    model_data BLOB,
    parameters TEXT,  -- JSON
    trained_at TEXT,
    training_samples INTEGER,
    metrics TEXT  -- JSON
);

-- Sync queue for offline operation
CREATE TABLE IF NOT EXISTS sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,  -- INSERT, UPDATE, DELETE
    data TEXT,  -- JSON
    priority INTEGER DEFAULT 5,
    created_at TEXT NOT NULL,
    synced_at TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);
CREATE INDEX IF NOT EXISTS idx_encounters_admit ON encounters(admit_datetime);
CREATE INDEX IF NOT EXISTS idx_encounters_type ON encounters(encounter_type);
CREATE INDEX IF NOT EXISTS idx_snapshots_facility ON facility_snapshots(facility_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics_history(metric_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_sync_queue_pending ON sync_queue(synced_at) WHERE synced_at IS NULL;
"""


class Database:
    """
    SQLite database manager for CAH data.
    
    Designed for:
    - Offline-first operation
    - Minimal resource usage (MV-CAHI compliant)
    - Simple backup/restore
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection: Optional[sqlite3.Connection] = None
        
        # Ensure directory exists
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.config.db_path),
                timeout=self.config.timeout,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")
            # Use WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection
    
    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
    
    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        conn = self.connection
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def initialize(self) -> None:
        """Initialize database schema."""
        with self.transaction() as conn:
            conn.executescript(SCHEMA_SQL)
            
            # Check/update schema version
            cursor = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            )
            current_version = cursor.fetchone()[0]
            
            if current_version is None:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.now().isoformat())
                )
    
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute SQL statement."""
        return self.connection.execute(sql, params)
    
    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute SQL statement with multiple parameter sets."""
        return self.connection.executemany(sql, params_list)
    
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute and fetch one row."""
        cursor = self.execute(sql, params)
        return cursor.fetchone()
    
    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute and fetch all rows."""
        cursor = self.execute(sql, params)
        return cursor.fetchall()
    
    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        """Count rows in table."""
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        cursor = self.execute(sql, params)
        return cursor.fetchone()[0]
    
    # Encounter operations
    def save_encounter(self, encounter: ClinicalEncounter) -> None:
        """Save or update an encounter."""
        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO encounters (
                    encounter_id, patient_id, admit_datetime, discharge_datetime,
                    encounter_type, principal_diagnosis, secondary_diagnoses,
                    procedures, attending_provider, disposition, los_hours,
                    drg, admission_source, admission_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                encounter.encounter_id,
                encounter.patient_id,
                encounter.admit_datetime.isoformat(),
                encounter.discharge_datetime.isoformat() if encounter.discharge_datetime else None,
                encounter.encounter_type.value,
                encounter.principal_diagnosis,
                json.dumps(encounter.secondary_diagnoses),
                json.dumps(encounter.procedures),
                encounter.attending_provider,
                encounter.disposition.value,
                encounter.los_hours,
                encounter.drg,
                encounter.admission_source,
                encounter.admission_type,
                encounter.created_at.isoformat(),
                datetime.now().isoformat(),
            ))
    
    def get_encounter(self, encounter_id: str) -> Optional[ClinicalEncounter]:
        """Get encounter by ID."""
        row = self.fetchone(
            "SELECT * FROM encounters WHERE encounter_id = ?",
            (encounter_id,)
        )
        if row is None:
            return None
        return self._row_to_encounter(row)
    
    def get_encounters(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        encounter_type: Optional[EncounterType] = None,
        limit: int = 1000,
    ) -> list[ClinicalEncounter]:
        """Get encounters with filters."""
        sql = "SELECT * FROM encounters WHERE 1=1"
        params = []
        
        if start_date:
            sql += " AND admit_datetime >= ?"
            params.append(start_date.isoformat())
        if end_date:
            sql += " AND admit_datetime <= ?"
            params.append(end_date.isoformat())
        if encounter_type:
            sql += " AND encounter_type = ?"
            params.append(encounter_type.value)
        
        sql += f" ORDER BY admit_datetime DESC LIMIT {limit}"
        
        rows = self.fetchall(sql, tuple(params))
        return [self._row_to_encounter(row) for row in rows]
    
    def _row_to_encounter(self, row: sqlite3.Row) -> ClinicalEncounter:
        """Convert database row to ClinicalEncounter."""
        return ClinicalEncounter(
            encounter_id=row["encounter_id"],
            patient_id=row["patient_id"],
            admit_datetime=datetime.fromisoformat(row["admit_datetime"]),
            discharge_datetime=datetime.fromisoformat(row["discharge_datetime"]) if row["discharge_datetime"] else None,
            encounter_type=EncounterType(row["encounter_type"]),
            principal_diagnosis=row["principal_diagnosis"] or "",
            secondary_diagnoses=json.loads(row["secondary_diagnoses"] or "[]"),
            procedures=json.loads(row["procedures"] or "[]"),
            attending_provider=row["attending_provider"] or "",
            disposition=DispositionCode(row["disposition"]) if row["disposition"] else DispositionCode.HOME,
            los_hours=row["los_hours"] or 0.0,
            drg=row["drg"],
            admission_source=row["admission_source"],
            admission_type=row["admission_type"],
        )
    
    # Cost report operations
    def save_cost_report(self, metrics: CostReportMetrics) -> None:
        """Save cost report metrics."""
        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cost_reports (
                    provider_id, fiscal_year_end, total_beds, staffed_beds,
                    patient_days, discharges, net_patient_revenue,
                    total_operating_revenue, total_operating_expenses,
                    salary_expenses, fte_count, ed_visits, swing_bed_days,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.provider_id,
                metrics.fiscal_year_end.isoformat(),
                metrics.total_beds,
                metrics.staffed_beds,
                metrics.patient_days,
                metrics.discharges,
                str(metrics.net_patient_revenue),
                str(metrics.total_operating_revenue),
                str(metrics.total_operating_expenses),
                str(metrics.salary_expenses),
                metrics.fte_count,
                metrics.ed_visits,
                metrics.swing_bed_days,
                datetime.now().isoformat(),
            ))
    
    def get_cost_report(
        self,
        provider_id: str,
        fiscal_year_end: Optional[date] = None,
    ) -> Optional[CostReportMetrics]:
        """Get cost report metrics."""
        if fiscal_year_end:
            row = self.fetchone(
                "SELECT * FROM cost_reports WHERE provider_id = ? AND fiscal_year_end = ?",
                (provider_id, fiscal_year_end.isoformat())
            )
        else:
            row = self.fetchone(
                "SELECT * FROM cost_reports WHERE provider_id = ? ORDER BY fiscal_year_end DESC LIMIT 1",
                (provider_id,)
            )
        
        if row is None:
            return None
        return self._row_to_cost_report(row)
    
    def _row_to_cost_report(self, row: sqlite3.Row) -> CostReportMetrics:
        """Convert database row to CostReportMetrics."""
        return CostReportMetrics(
            provider_id=row["provider_id"],
            fiscal_year_end=date.fromisoformat(row["fiscal_year_end"]),
            total_beds=row["total_beds"] or 0,
            staffed_beds=row["staffed_beds"] or 0,
            patient_days=row["patient_days"] or 0,
            discharges=row["discharges"] or 0,
            net_patient_revenue=Decimal(row["net_patient_revenue"] or "0"),
            total_operating_revenue=Decimal(row["total_operating_revenue"] or "0"),
            total_operating_expenses=Decimal(row["total_operating_expenses"] or "0"),
            salary_expenses=Decimal(row["salary_expenses"] or "0"),
            fte_count=row["fte_count"] or 0.0,
            ed_visits=row["ed_visits"] or 0,
            swing_bed_days=row["swing_bed_days"] or 0,
        )
    
    # Metrics operations
    def save_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        dimension: Optional[str] = None,
        dimension_value: Optional[str] = None,
    ) -> None:
        """Save a metric value."""
        if timestamp is None:
            timestamp = datetime.now()
        
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO metrics_history (
                    metric_name, metric_value, timestamp, dimension, dimension_value
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                metric_name,
                value,
                timestamp.isoformat(),
                dimension,
                dimension_value,
            ))
    
    def get_metric_history(
        self,
        metric_name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 365,
    ) -> list[tuple[datetime, float]]:
        """Get metric history."""
        sql = "SELECT timestamp, metric_value FROM metrics_history WHERE metric_name = ?"
        params = [metric_name]
        
        if start:
            sql += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND timestamp <= ?"
            params.append(end.isoformat())
        
        sql += f" ORDER BY timestamp DESC LIMIT {limit}"
        
        rows = self.fetchall(sql, tuple(params))
        return [
            (datetime.fromisoformat(row["timestamp"]), row["metric_value"])
            for row in rows
        ]
    
    # Backup and maintenance
    def backup(self, backup_path: Path) -> None:
        """Create database backup."""
        import shutil
        
        # Checkpoint WAL to main database
        self.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        # Copy database file
        shutil.copy2(self.config.db_path, backup_path)
    
    def vacuum(self) -> None:
        """Compact database."""
        self.execute("VACUUM")
    
    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        stats = {
            "path": str(self.config.db_path),
            "size_mb": self.config.db_path.stat().st_size / (1024 * 1024) if self.config.db_path.exists() else 0,
        }
        
        # Count records in each table
        tables = ["encounters", "cost_reports", "facility_snapshots", "claims", "metrics_history"]
        for table in tables:
            try:
                stats[f"{table}_count"] = self.count(table)
            except Exception:
                stats[f"{table}_count"] = 0
        
        return stats


# Global database instance
_database: Optional[Database] = None


def get_database(
    db_path: Optional[Path] = None,
    initialize: bool = True,
) -> Database:
    """Get or create global database instance."""
    global _database
    
    if _database is None:
        if db_path is None:
            db_path = Path.home() / ".cah" / "cah_data.db"
        
        config = DatabaseConfig(db_path=db_path)
        _database = Database(config)
        
        if initialize:
            _database.initialize()
    
    return _database


def close_database() -> None:
    """Close global database instance."""
    global _database
    
    if _database is not None:
        _database.close()
        _database = None

