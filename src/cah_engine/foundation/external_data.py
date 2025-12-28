"""
External Data Integrations

Connect to external data sources for enrichment and benchmarking.
Designed for offline-first operation with caching.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import hashlib

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@dataclass
class CacheEntry:
    """Cached data entry with metadata."""
    
    data: Any
    fetched_at: datetime
    expires_at: datetime
    source: str
    cache_key: str
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > self.expires_at
    
    @property
    def age_hours(self) -> float:
        """Age of cache entry in hours."""
        delta = datetime.now() - self.fetched_at
        return delta.total_seconds() / 3600


@dataclass
class FacilityInfo:
    """External facility information."""
    
    provider_id: str
    facility_name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    county: str = ""
    
    # Classification
    facility_type: str = ""  # CAH, RHC, etc.
    certification_date: Optional[datetime] = None
    
    # Geographic
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rural_urban_code: str = ""
    
    # Characteristics
    bed_count: int = 0
    ownership_type: str = ""
    health_system: str = ""
    
    # Quality metrics (if available)
    star_rating: Optional[int] = None
    
    extra_data: dict = field(default_factory=dict)


class DataSource(ABC):
    """Abstract base class for external data sources."""
    
    def __init__(self, cache_dir: Optional[Path] = None, cache_ttl_hours: int = 24):
        self.cache_dir = cache_dir or Path.home() / ".cah_cache"
        self.cache_ttl_hours = cache_ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def fetch(self, identifier: str) -> Optional[Any]:
        """Fetch data for an identifier."""
        pass
    
    @abstractmethod
    def fetch_bulk(self, identifiers: list[str]) -> dict[str, Any]:
        """Fetch data for multiple identifiers."""
        pass
    
    def _get_cache_key(self, identifier: str) -> str:
        """Generate cache key for an identifier."""
        source_name = self.__class__.__name__
        key_str = f"{source_name}:{identifier}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached(self, identifier: str) -> Optional[CacheEntry]:
        """Get cached data if available and not expired."""
        cache_key = self._get_cache_key(identifier)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            
            entry = CacheEntry(
                data=data.get("data"),
                fetched_at=datetime.fromisoformat(data.get("fetched_at", "")),
                expires_at=datetime.fromisoformat(data.get("expires_at", "")),
                source=data.get("source", ""),
                cache_key=cache_key,
            )
            
            if not entry.is_expired:
                return entry
                
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        
        return None
    
    def _set_cached(self, identifier: str, data: Any) -> None:
        """Cache data for an identifier."""
        cache_key = self._get_cache_key(identifier)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        now = datetime.now()
        entry = {
            "data": data,
            "fetched_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=self.cache_ttl_hours)).isoformat(),
            "source": self.__class__.__name__,
            "identifier": identifier,
        }
        
        with open(cache_file, "w") as f:
            json.dump(entry, f)
    
    def clear_cache(self) -> int:
        """Clear all cached data. Returns number of entries cleared."""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        return count


class HRSADataSource(DataSource):
    """
    HRSA Data Warehouse integration.
    
    Provides access to:
    - Facility characteristics
    - Rural health information
    - Underserved area designations
    """
    
    BASE_URL = "https://data.hrsa.gov/api"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
    
    def fetch(self, identifier: str) -> Optional[FacilityInfo]:
        """Fetch facility info by provider ID."""
        # Check cache first
        cached = self._get_cached(identifier)
        if cached:
            return self._parse_facility(cached.data)
        
        # For demo/offline mode, return mock data
        if not HAS_HTTPX or not self.api_key:
            return self._get_mock_data(identifier)
        
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.BASE_URL}/facility/{identifier}",
                    headers={"X-API-Key": self.api_key},
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self._set_cached(identifier, data)
                    return self._parse_facility(data)
                    
        except Exception:
            pass
        
        return self._get_mock_data(identifier)
    
    def fetch_bulk(self, identifiers: list[str]) -> dict[str, FacilityInfo]:
        """Fetch multiple facilities."""
        results = {}
        for identifier in identifiers:
            result = self.fetch(identifier)
            if result:
                results[identifier] = result
        return results
    
    def _parse_facility(self, data: dict) -> FacilityInfo:
        """Parse API response into FacilityInfo."""
        return FacilityInfo(
            provider_id=data.get("provider_id", ""),
            facility_name=data.get("facility_name", ""),
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            zip_code=data.get("zip_code", ""),
            county=data.get("county", ""),
            facility_type=data.get("facility_type", ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            rural_urban_code=data.get("rural_urban_code", ""),
            bed_count=data.get("bed_count", 0),
            ownership_type=data.get("ownership_type", ""),
            extra_data=data,
        )
    
    def _get_mock_data(self, identifier: str) -> FacilityInfo:
        """Return mock data for offline/demo mode."""
        return FacilityInfo(
            provider_id=identifier,
            facility_name=f"CAH Facility {identifier}",
            state="XX",
            facility_type="CAH",
            rural_urban_code="R",
            bed_count=25,
        )


class CMSProviderSource(DataSource):
    """
    CMS Provider data integration.
    
    Provides access to:
    - Provider enrollment data
    - Certification status
    - Quality measures
    """
    
    BASE_URL = "https://data.cms.gov/provider-data/api"
    
    def fetch(self, identifier: str) -> Optional[dict]:
        """Fetch provider data by CMS Certification Number (CCN)."""
        cached = self._get_cached(identifier)
        if cached:
            return cached.data
        
        if not HAS_HTTPX:
            return self._get_mock_data(identifier)
        
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.BASE_URL}/1/providers/{identifier}",
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self._set_cached(identifier, data)
                    return data
                    
        except Exception:
            pass
        
        return self._get_mock_data(identifier)
    
    def fetch_bulk(self, identifiers: list[str]) -> dict[str, dict]:
        """Fetch multiple providers."""
        results = {}
        for identifier in identifiers:
            result = self.fetch(identifier)
            if result:
                results[identifier] = result
        return results
    
    def _get_mock_data(self, identifier: str) -> dict:
        """Return mock data for offline mode."""
        return {
            "ccn": identifier,
            "provider_type": "Critical Access Hospital",
            "participation_date": "2000-01-01",
            "certification_status": "Active",
        }


class WeatherDataSource(DataSource):
    """
    Weather data integration for demand correlation.
    
    Provides:
    - Current conditions
    - Forecasts
    - Historical data for analysis
    """
    
    def fetch(self, identifier: str) -> Optional[dict]:
        """Fetch weather data by location identifier (zip code or lat/lon)."""
        cached = self._get_cached(identifier)
        if cached:
            return cached.data
        
        # Return mock data for offline mode
        return {
            "location": identifier,
            "current": {
                "temperature": 55,
                "conditions": "Clear",
                "humidity": 45,
            },
            "forecast": [
                {"day": 1, "high": 60, "low": 40, "conditions": "Clear"},
                {"day": 2, "high": 58, "low": 38, "conditions": "Partly Cloudy"},
                {"day": 3, "high": 55, "low": 35, "conditions": "Rain"},
            ],
        }
    
    def fetch_bulk(self, identifiers: list[str]) -> dict[str, dict]:
        """Fetch weather for multiple locations."""
        return {identifier: self.fetch(identifier) for identifier in identifiers}


class ExternalDataClient:
    """
    Unified client for all external data sources.
    
    Provides caching, offline operation, and fallback handling.
    """
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        hrsa_api_key: Optional[str] = None,
    ):
        cache_dir = cache_dir or Path.home() / ".cah_cache"
        
        self.hrsa = HRSADataSource(api_key=hrsa_api_key, cache_dir=cache_dir)
        self.cms = CMSProviderSource(cache_dir=cache_dir)
        self.weather = WeatherDataSource(cache_dir=cache_dir, cache_ttl_hours=1)
    
    def get_facility_info(self, provider_id: str) -> Optional[FacilityInfo]:
        """Get comprehensive facility information."""
        return self.hrsa.fetch(provider_id)
    
    def get_provider_status(self, ccn: str) -> Optional[dict]:
        """Get CMS provider certification status."""
        return self.cms.fetch(ccn)
    
    def get_weather(self, location: str) -> Optional[dict]:
        """Get current weather and forecast."""
        return self.weather.fetch(location)
    
    def enrich_facility(
        self,
        provider_id: str,
        include_weather: bool = False,
        location: Optional[str] = None,
    ) -> dict:
        """
        Get enriched facility data from multiple sources.
        
        Args:
            provider_id: Provider ID / CCN
            include_weather: Whether to include weather data
            location: Location for weather (zip code), if different from facility
            
        Returns:
            Dictionary with combined data from all sources
        """
        result = {
            "provider_id": provider_id,
            "facility": None,
            "cms_status": None,
            "weather": None,
        }
        
        # Fetch facility info
        facility = self.hrsa.fetch(provider_id)
        if facility:
            result["facility"] = {
                "name": facility.facility_name,
                "address": facility.address,
                "city": facility.city,
                "state": facility.state,
                "zip_code": facility.zip_code,
                "facility_type": facility.facility_type,
                "bed_count": facility.bed_count,
                "rural_urban_code": facility.rural_urban_code,
            }
            
            # Use facility zip for weather if not provided
            if not location and facility.zip_code:
                location = facility.zip_code
        
        # Fetch CMS status
        cms_data = self.cms.fetch(provider_id)
        if cms_data:
            result["cms_status"] = cms_data
        
        # Fetch weather if requested
        if include_weather and location:
            weather = self.weather.fetch(location)
            if weather:
                result["weather"] = weather
        
        return result
    
    def clear_all_caches(self) -> dict[str, int]:
        """Clear all data source caches."""
        return {
            "hrsa": self.hrsa.clear_cache(),
            "cms": self.cms.clear_cache(),
            "weather": self.weather.clear_cache(),
        }

