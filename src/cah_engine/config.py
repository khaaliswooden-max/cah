"""
Configuration Management

Application configuration with environment and file-based overrides.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import json

import yaml


@dataclass
class DatabaseConfig:
    """Database configuration."""
    
    path: Path = field(default_factory=lambda: Path.home() / ".cah" / "cah_data.db")
    echo: bool = False
    timeout: float = 30.0


@dataclass
class AnalyticsConfig:
    """Analytics configuration."""
    
    # Model staleness limits (hours)
    census_model_max_staleness: int = 168  # 1 week
    transfer_model_max_staleness: int = 720  # 30 days
    denial_model_max_staleness: int = 720  # 30 days
    
    # Simulation settings
    monte_carlo_iterations: int = 10000
    random_seed: int = 42


@dataclass
class ComplianceConfig:
    """Compliance configuration."""
    
    # CAH regulatory limits
    max_beds: int = 25
    max_los_hours: int = 96
    min_distance_miles: float = 35.0
    
    # Alert thresholds
    los_warning_threshold: float = 80.0  # % of limit
    occupancy_warning_threshold: float = 90.0  # % of capacity


@dataclass
class IntegrationConfig:
    """Integration configuration."""
    
    # FHIR settings
    fhir_server_url: str = ""
    fhir_auth_token: str = ""
    
    # External data sources
    hrsa_api_key: str = ""
    
    # Sync settings
    sync_interval_minutes: int = 60
    sync_batch_size: int = 100


@dataclass
class Config:
    """Main application configuration."""
    
    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # Feature flags
    enable_analytics: bool = True
    enable_decision_support: bool = True
    enable_sync: bool = True
    
    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    integration: IntegrationConfig = field(default_factory=IntegrationConfig)
    
    # Facility settings
    facility_id: str = ""
    facility_name: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create config from dictionary."""
        config = cls()
        
        # Top-level settings
        config.environment = data.get("environment", config.environment)
        config.debug = data.get("debug", config.debug)
        config.log_level = data.get("log_level", config.log_level)
        config.enable_analytics = data.get("enable_analytics", config.enable_analytics)
        config.enable_decision_support = data.get("enable_decision_support", config.enable_decision_support)
        config.enable_sync = data.get("enable_sync", config.enable_sync)
        config.facility_id = data.get("facility_id", config.facility_id)
        config.facility_name = data.get("facility_name", config.facility_name)
        
        # Database config
        if "database" in data:
            db_data = data["database"]
            config.database.path = Path(db_data.get("path", config.database.path))
            config.database.echo = db_data.get("echo", config.database.echo)
            config.database.timeout = db_data.get("timeout", config.database.timeout)
        
        # Analytics config
        if "analytics" in data:
            analytics_data = data["analytics"]
            config.analytics.monte_carlo_iterations = analytics_data.get(
                "monte_carlo_iterations", config.analytics.monte_carlo_iterations
            )
            config.analytics.random_seed = analytics_data.get(
                "random_seed", config.analytics.random_seed
            )
        
        # Compliance config
        if "compliance" in data:
            comp_data = data["compliance"]
            config.compliance.max_beds = comp_data.get("max_beds", config.compliance.max_beds)
            config.compliance.max_los_hours = comp_data.get("max_los_hours", config.compliance.max_los_hours)
        
        # Integration config
        if "integration" in data:
            int_data = data["integration"]
            config.integration.fhir_server_url = int_data.get(
                "fhir_server_url", config.integration.fhir_server_url
            )
            config.integration.hrsa_api_key = int_data.get(
                "hrsa_api_key", config.integration.hrsa_api_key
            )
        
        return config
    
    @classmethod
    def from_file(cls, path: Path) -> "Config":
        """Load config from YAML or JSON file."""
        if not path.exists():
            return cls()
        
        with open(path, "r") as f:
            if path.suffix in (".yml", ".yaml"):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        return cls.from_dict(data or {})
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        config = cls()
        
        # Environment
        config.environment = os.getenv("CAH_ENVIRONMENT", config.environment)
        config.debug = os.getenv("CAH_DEBUG", "").lower() in ("true", "1", "yes")
        config.log_level = os.getenv("CAH_LOG_LEVEL", config.log_level)
        
        # Database
        if db_path := os.getenv("CAH_DB_PATH"):
            config.database.path = Path(db_path)
        
        # Facility
        config.facility_id = os.getenv("CAH_FACILITY_ID", config.facility_id)
        config.facility_name = os.getenv("CAH_FACILITY_NAME", config.facility_name)
        
        # Integration
        config.integration.fhir_server_url = os.getenv(
            "CAH_FHIR_URL", config.integration.fhir_server_url
        )
        config.integration.hrsa_api_key = os.getenv(
            "CAH_HRSA_API_KEY", config.integration.hrsa_api_key
        )
        
        return config
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "environment": self.environment,
            "debug": self.debug,
            "log_level": self.log_level,
            "enable_analytics": self.enable_analytics,
            "enable_decision_support": self.enable_decision_support,
            "enable_sync": self.enable_sync,
            "facility_id": self.facility_id,
            "facility_name": self.facility_name,
            "database": {
                "path": str(self.database.path),
                "echo": self.database.echo,
                "timeout": self.database.timeout,
            },
            "analytics": {
                "monte_carlo_iterations": self.analytics.monte_carlo_iterations,
                "random_seed": self.analytics.random_seed,
            },
            "compliance": {
                "max_beds": self.compliance.max_beds,
                "max_los_hours": self.compliance.max_los_hours,
            },
            "integration": {
                "fhir_server_url": self.integration.fhir_server_url,
            },
        }
    
    def save(self, path: Path) -> None:
        """Save config to file."""
        data = self.to_dict()
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            if path.suffix in (".yml", ".yaml"):
                yaml.dump(data, f, default_flow_style=False)
            else:
                json.dump(data, f, indent=2)


# Global configuration instance
_config: Optional[Config] = None


def get_config(
    config_file: Optional[Path] = None,
    reload: bool = False,
) -> Config:
    """
    Get or create global configuration.
    
    Priority:
    1. Environment variables
    2. Config file
    3. Defaults
    """
    global _config
    
    if _config is None or reload:
        # Start with defaults
        config = Config()
        
        # Load from file if provided
        if config_file and config_file.exists():
            config = Config.from_file(config_file)
        else:
            # Try default locations
            default_paths = [
                Path.cwd() / "cah.yaml",
                Path.cwd() / "cah.yml",
                Path.cwd() / "cah.json",
                Path.home() / ".cah" / "config.yaml",
            ]
            for path in default_paths:
                if path.exists():
                    config = Config.from_file(path)
                    break
        
        # Override with environment variables
        env_config = Config.from_env()
        
        # Merge (env takes precedence)
        if env_config.facility_id:
            config.facility_id = env_config.facility_id
        if env_config.facility_name:
            config.facility_name = env_config.facility_name
        if env_config.debug:
            config.debug = env_config.debug
        if env_config.integration.fhir_server_url:
            config.integration.fhir_server_url = env_config.integration.fhir_server_url
        if env_config.integration.hrsa_api_key:
            config.integration.hrsa_api_key = env_config.integration.hrsa_api_key
        
        _config = config
    
    return _config


def reset_config() -> None:
    """Reset global configuration."""
    global _config
    _config = None

