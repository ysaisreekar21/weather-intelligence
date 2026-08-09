"""Weather client for National Weather Service API.

Fetches weather alerts and forecasts from api.weather.gov and normalizes
them into documents for Lakebase ingestion.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# NWS API base URL
NWS_API_BASE = "https://api.weather.gov"

# User-Agent is required by NWS API
USER_AGENT = "WeatherIntelligenceApp/1.0 (Databricks Educational Project)"

# HTTP timeouts
REQUEST_TIMEOUT = 10  # seconds


class WeatherClientError(Exception):
    """Base exception for weather client errors."""
    pass


class LocationResolutionError(WeatherClientError):
    """Error resolving location to coordinates."""
    pass


class NWSAPIError(WeatherClientError):
    """Error calling NWS API."""
    pass


def _make_nws_request(url: str) -> Dict:
    """Make a request to NWS API with proper headers and error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise NWSAPIError(f"Request to {url} timed out after {REQUEST_TIMEOUT}s")
    except requests.exceptions.HTTPError as e:
        raise NWSAPIError(f"HTTP error from NWS API: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        raise NWSAPIError(f"Request failed: {str(e)}")
    except ValueError as e:
        raise NWSAPIError(f"Invalid JSON response: {str(e)}")


def _parse_location(location: str) -> Tuple[float, float]:
    """Parse location string into (latitude, longitude).
    
    Supports:
    - "lat,lon" format: "41.8781,-87.6298"
    - City, State format: "Chicago, IL" (uses simple geocoding)
    
    Returns:
        Tuple of (latitude, longitude)
    """
    location = location.strip()
    
    # Try to parse as lat,lon
    if "," in location:
        parts = location.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                # Validate ranges
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
            except ValueError:
                pass
    
    # Try to resolve as city, state using geocoding API
    # For simplicity, we'll use a free geocoding service
    try:
        geocode_url = f"https://nominatim.openstreetmap.org/search?q={quote(location)}&format=json&limit=1"
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(geocode_url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        results = response.json()
        
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            logger.info(f"Resolved '{location}' to ({lat}, {lon})")
            return (lat, lon)
    except Exception as e:
        logger.warning(f"Geocoding failed for '{location}': {str(e)}")
    
    raise LocationResolutionError(f"Could not resolve location: {location}")


def _get_grid_point(lat: float, lon: float) -> Dict:
    """Get NWS grid point for coordinates.
    
    Returns:
        Dict with gridId, gridX, gridY, and forecast/forecastHourly URLs
    """
    url = f"{NWS_API_BASE}/points/{lat},{lon}"
    data = _make_nws_request(url)
    
    properties = data.get("properties", {})
    return {
        "gridId": properties.get("gridId"),
        "gridX": properties.get("gridX"),
        "gridY": properties.get("gridY"),
        "forecast_url": properties.get("forecast"),
        "forecast_hourly_url": properties.get("forecastHourly"),
        "county": properties.get("relativeLocation", {}).get("properties", {}).get("city"),
        "state": properties.get("relativeLocation", {}).get("properties", {}).get("state")
    }


def fetch_alerts(lat: float, lon: float, location_name: str) -> List[Dict]:
    """Fetch active weather alerts for a location.
    
    Returns:
        List of normalized alert documents
    """
    url = f"{NWS_API_BASE}/alerts/active?point={lat},{lon}"
    
    try:
        data = _make_nws_request(url)
    except NWSAPIError as e:
        logger.warning(f"Failed to fetch alerts for {location_name}: {str(e)}")
        return []
    
    features = data.get("features", [])
    documents = []
    synced_at = datetime.now(timezone.utc).isoformat()
    
    for feature in features:
        props = feature.get("properties", {})
        
        # Generate stable ID based on alert ID from NWS
        alert_id = props.get("id", "")
        if not alert_id:
            continue
        
        # Use NWS alert ID as our document ID
        doc_id = f"alert_{hashlib.md5(alert_id.encode()).hexdigest()}"
        
        documents.append({
            "id": doc_id,
            "location": location_name,
            "source_type": "alert",
            "headline": props.get("headline", ""),
            "narrative_text": props.get("description", ""),
            "issued_at": props.get("sent"),
            "effective_at": props.get("effective"),
            "payload": feature,
            "synced_at": synced_at
        })
    
    return documents


def fetch_forecast(lat: float, lon: float, location_name: str) -> List[Dict]:
    """Fetch forecast data for a location.
    
    Returns:
        List of normalized forecast documents
    """
    try:
        grid_point = _get_grid_point(lat, lon)
        forecast_url = grid_point.get("forecast_url")
        
        if not forecast_url:
            logger.warning(f"No forecast URL for {location_name}")
            return []
        
        data = _make_nws_request(forecast_url)
    except (NWSAPIError, LocationResolutionError) as e:
        logger.warning(f"Failed to fetch forecast for {location_name}: {str(e)}")
        return []
    
    periods = data.get("properties", {}).get("periods", [])
    documents = []
    synced_at = datetime.now(timezone.utc).isoformat()
    
    for period in periods:
        # Generate stable ID based on location and period number/name
        period_name = period.get("name", "")
        period_num = period.get("number", "")
        
        # Create stable ID from location and period identifiers
        id_string = f"forecast_{location_name}_{period_num}_{period_name}"
        doc_id = f"forecast_{hashlib.md5(id_string.encode()).hexdigest()}"
        
        documents.append({
            "id": doc_id,
            "location": location_name,
            "source_type": "forecast",
            "headline": period.get("name", ""),
            "narrative_text": period.get("detailedForecast", ""),
            "issued_at": data.get("properties", {}).get("updateTime"),
            "effective_at": period.get("startTime"),
            "payload": period,
            "synced_at": synced_at
        })
    
    return documents


def fetch_weather_documents(locations: List[str], limit: Optional[int] = None) -> List[Dict]:
    """Fetch weather documents for multiple locations.
    
    Args:
        locations: List of location strings (city/state or lat/lon)
        limit: Optional limit on total documents returned
    
    Returns:
        List of normalized weather documents
    """
    all_documents = []
    
    for location in locations:
        try:
            lat, lon = _parse_location(location)
            logger.info(f"Fetching weather for {location} ({lat}, {lon})")
            
            # Fetch alerts
            alerts = fetch_alerts(lat, lon, location)
            all_documents.extend(alerts)
            logger.info(f"Fetched {len(alerts)} alerts for {location}")
            
            # Fetch forecast
            forecasts = fetch_forecast(lat, lon, location)
            all_documents.extend(forecasts)
            logger.info(f"Fetched {len(forecasts)} forecast periods for {location}")
            
            # Apply limit if specified
            if limit and len(all_documents) >= limit:
                all_documents = all_documents[:limit]
                break
        
        except LocationResolutionError as e:
            logger.error(f"Could not resolve location '{location}': {str(e)}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error fetching weather for '{location}': {str(e)}")
            continue
    
    return all_documents
