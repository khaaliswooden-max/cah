"""
Offline Operation Support

Manage operations during connectivity loss.
Queue data for sync when connectivity returns.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from cah_engine.storage.database import Database, get_database


class SyncStatus(str, Enum):
    """Synchronization status."""
    
    SYNCED = "synced"
    PENDING = "pending"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass
class SyncQueueItem:
    """Item in the sync queue."""
    
    id: int
    entity_type: str
    entity_id: str
    operation: str  # INSERT, UPDATE, DELETE
    data: dict
    priority: int
    created_at: datetime
    synced_at: Optional[datetime] = None
    
    @property
    def is_synced(self) -> bool:
        """Check if item has been synced."""
        return self.synced_at is not None


@dataclass
class SyncResult:
    """Result of a sync operation."""
    
    items_synced: int = 0
    items_failed: int = 0
    errors: list[str] = field(default_factory=list)
    sync_time: datetime = field(default_factory=datetime.now)


class SyncQueue:
    """
    Queue for data pending synchronization.
    
    Stores operations locally when offline for later sync.
    """
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
    
    def enqueue(
        self,
        entity_type: str,
        entity_id: str,
        operation: str,
        data: dict,
        priority: int = 5,
    ) -> int:
        """
        Add item to sync queue.
        
        Args:
            entity_type: Type of entity (e.g., "encounter", "claim")
            entity_id: Entity identifier
            operation: Operation type (INSERT, UPDATE, DELETE)
            data: Entity data as dictionary
            priority: Priority (1=highest, 10=lowest)
            
        Returns:
            Queue item ID
        """
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO sync_queue (
                    entity_type, entity_id, operation, data, priority, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entity_type,
                entity_id,
                operation,
                json.dumps(data),
                priority,
                datetime.now().isoformat(),
            ))
            return cursor.lastrowid
    
    def dequeue(self) -> Optional[SyncQueueItem]:
        """
        Get next item to sync (highest priority, oldest first).
        
        Returns:
            Next SyncQueueItem or None if queue is empty
        """
        row = self.db.fetchone("""
            SELECT * FROM sync_queue
            WHERE synced_at IS NULL
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
        """)
        
        if row is None:
            return None
        
        return SyncQueueItem(
            id=row["id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            operation=row["operation"],
            data=json.loads(row["data"]),
            priority=row["priority"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
    
    def mark_synced(self, item_id: int) -> None:
        """Mark item as synced."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE sync_queue SET synced_at = ? WHERE id = ?",
                (datetime.now().isoformat(), item_id)
            )
    
    def mark_failed(self, item_id: int, error: str = "") -> None:
        """Mark item as failed (will be retried)."""
        # Just log the error, item remains in queue
        pass
    
    def get_pending(self, limit: int = 100) -> list[SyncQueueItem]:
        """Get all pending items."""
        rows = self.db.fetchall("""
            SELECT * FROM sync_queue
            WHERE synced_at IS NULL
            ORDER BY priority ASC, created_at ASC
            LIMIT ?
        """, (limit,))
        
        return [
            SyncQueueItem(
                id=row["id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                operation=row["operation"],
                data=json.loads(row["data"]),
                priority=row["priority"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
    
    def get_count(self) -> int:
        """Get count of pending items."""
        return self.db.count("sync_queue", "synced_at IS NULL")
    
    def clear_synced(self, older_than_days: int = 30) -> int:
        """Clear synced items older than specified days."""
        cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
        
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM sync_queue WHERE synced_at IS NOT NULL AND synced_at < ?",
                (cutoff,)
            )
            return cursor.rowcount
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self.get_count() == 0


@dataclass
class ModelStaleness:
    """Information about model staleness."""
    
    model_name: str
    trained_at: Optional[datetime]
    staleness_hours: float
    is_usable: bool
    max_staleness_hours: float


class OfflineManager:
    """
    Manage operations during connectivity loss.
    
    Features:
    - Track sync status
    - Queue operations for later sync
    - Manage model staleness
    - Handle reconnection
    """
    
    # Default staleness limits by model type (hours)
    DEFAULT_STALENESS_LIMITS = {
        "census_forecaster": 168,  # 1 week
        "transfer_risk": 720,  # 30 days
        "denial_probability": 720,  # 30 days
        "default": 168,  # 1 week
    }
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self.sync_queue = SyncQueue(self.db)
        self.last_sync: Optional[datetime] = None
        self._load_last_sync()
    
    def _load_last_sync(self) -> None:
        """Load last sync time from database."""
        row = self.db.fetchone("""
            SELECT MAX(synced_at) as last_sync FROM sync_queue
            WHERE synced_at IS NOT NULL
        """)
        if row and row["last_sync"]:
            self.last_sync = datetime.fromisoformat(row["last_sync"])
    
    @property
    def is_online(self) -> bool:
        """
        Check if system appears to be online.
        
        In production, would check actual connectivity.
        """
        # Simple heuristic: assume online if recent sync
        if self.last_sync is None:
            return True  # Assume online initially
        
        hours_since_sync = (datetime.now() - self.last_sync).total_seconds() / 3600
        return hours_since_sync < 24
    
    @property
    def offline_hours(self) -> float:
        """Hours since last successful sync."""
        if self.last_sync is None:
            return 0.0
        return (datetime.now() - self.last_sync).total_seconds() / 3600
    
    def get_model_staleness(self, model_name: str) -> ModelStaleness:
        """
        Calculate how stale a model's predictions are.
        
        Args:
            model_name: Name of the model
            
        Returns:
            ModelStaleness with staleness information
        """
        row = self.db.fetchone(
            "SELECT trained_at FROM model_artifacts WHERE model_name = ?",
            (model_name,)
        )
        
        max_staleness = self.DEFAULT_STALENESS_LIMITS.get(
            model_name,
            self.DEFAULT_STALENESS_LIMITS["default"]
        )
        
        if row is None or row["trained_at"] is None:
            return ModelStaleness(
                model_name=model_name,
                trained_at=None,
                staleness_hours=float("inf"),
                is_usable=False,
                max_staleness_hours=max_staleness,
            )
        
        trained_at = datetime.fromisoformat(row["trained_at"])
        staleness_hours = (datetime.now() - trained_at).total_seconds() / 3600
        
        return ModelStaleness(
            model_name=model_name,
            trained_at=trained_at,
            staleness_hours=staleness_hours,
            is_usable=staleness_hours <= max_staleness,
            max_staleness_hours=max_staleness,
        )
    
    def can_use_model(
        self,
        model_name: str,
        max_staleness_hours: Optional[float] = None,
    ) -> bool:
        """
        Determine if model is fresh enough for use.
        
        Args:
            model_name: Name of the model
            max_staleness_hours: Override default max staleness
            
        Returns:
            True if model can be used
        """
        staleness = self.get_model_staleness(model_name)
        
        if max_staleness_hours is not None:
            return staleness.staleness_hours <= max_staleness_hours
        
        return staleness.is_usable
    
    def queue_for_sync(
        self,
        entity_type: str,
        entity_id: str,
        operation: str,
        data: dict,
        priority: int = 5,
    ) -> int:
        """
        Queue data for sync when connectivity returns.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            operation: Operation type
            data: Entity data
            priority: Sync priority (1=highest)
            
        Returns:
            Queue item ID
        """
        return self.sync_queue.enqueue(
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            data=data,
            priority=priority,
        )
    
    def on_reconnect(self, sync_handler: Optional[callable] = None) -> SyncResult:
        """
        Handle reconnection: sync queued data.
        
        Args:
            sync_handler: Optional callback to handle sync for each item
            
        Returns:
            SyncResult with sync statistics
        """
        result = SyncResult()
        
        # Process queue
        while True:
            item = self.sync_queue.dequeue()
            if item is None:
                break
            
            try:
                if sync_handler:
                    sync_handler(item)
                
                self.sync_queue.mark_synced(item.id)
                result.items_synced += 1
                
            except Exception as e:
                result.items_failed += 1
                result.errors.append(f"{item.entity_type}/{item.entity_id}: {str(e)}")
        
        # Update last sync time
        self.last_sync = datetime.now()
        
        return result
    
    def save_model_artifact(
        self,
        model_name: str,
        model_data: bytes,
        parameters: dict,
        training_samples: int,
        metrics: Optional[dict] = None,
    ) -> None:
        """
        Save trained model artifact.
        
        Args:
            model_name: Name of the model
            model_data: Serialized model data
            parameters: Model parameters
            training_samples: Number of training samples
            metrics: Model performance metrics
        """
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO model_artifacts (
                    model_name, model_data, parameters, trained_at,
                    training_samples, metrics
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                model_name,
                model_data,
                json.dumps(parameters),
                datetime.now().isoformat(),
                training_samples,
                json.dumps(metrics or {}),
            ))
    
    def load_model_artifact(self, model_name: str) -> Optional[dict]:
        """
        Load model artifact.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with model data, parameters, and metadata
        """
        row = self.db.fetchone(
            "SELECT * FROM model_artifacts WHERE model_name = ?",
            (model_name,)
        )
        
        if row is None:
            return None
        
        return {
            "model_name": row["model_name"],
            "model_data": row["model_data"],
            "parameters": json.loads(row["parameters"] or "{}"),
            "trained_at": datetime.fromisoformat(row["trained_at"]) if row["trained_at"] else None,
            "training_samples": row["training_samples"],
            "metrics": json.loads(row["metrics"] or "{}"),
        }
    
    def get_sync_status(self) -> dict[str, Any]:
        """Get overall sync status."""
        pending_count = self.sync_queue.get_count()
        
        return {
            "is_online": self.is_online,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "offline_hours": self.offline_hours,
            "pending_items": pending_count,
            "status": "synced" if pending_count == 0 else "pending",
        }
    
    def get_data_freshness(self) -> dict[str, Any]:
        """Get freshness of various data types."""
        freshness = {}
        
        # Check encounters
        row = self.db.fetchone(
            "SELECT MAX(updated_at) as latest FROM encounters"
        )
        if row and row["latest"]:
            latest = datetime.fromisoformat(row["latest"])
            freshness["encounters"] = {
                "latest_update": latest.isoformat(),
                "hours_old": (datetime.now() - latest).total_seconds() / 3600,
            }
        
        # Check cost reports
        row = self.db.fetchone(
            "SELECT MAX(created_at) as latest FROM cost_reports"
        )
        if row and row["latest"]:
            latest = datetime.fromisoformat(row["latest"])
            freshness["cost_reports"] = {
                "latest_update": latest.isoformat(),
                "hours_old": (datetime.now() - latest).total_seconds() / 3600,
            }
        
        # Check models
        for model_name in self.DEFAULT_STALENESS_LIMITS.keys():
            if model_name != "default":
                staleness = self.get_model_staleness(model_name)
                freshness[f"model_{model_name}"] = {
                    "trained_at": staleness.trained_at.isoformat() if staleness.trained_at else None,
                    "staleness_hours": staleness.staleness_hours,
                    "is_usable": staleness.is_usable,
                }
        
        return freshness

