"""
Storage Layer

SQLite-based storage with offline-first design.
Supports sync queue for connectivity recovery.
"""

from cah_engine.storage.database import (
    Database,
    get_database,
)
from cah_engine.storage.offline import (
    OfflineManager,
    SyncQueue,
    SyncStatus,
)
from cah_engine.storage.repositories import (
    EncounterRepository,
    MetricsRepository,
    ComplianceRepository,
)

__all__ = [
    "Database",
    "get_database",
    "OfflineManager",
    "SyncQueue",
    "SyncStatus",
    "EncounterRepository",
    "MetricsRepository",
    "ComplianceRepository",
]

