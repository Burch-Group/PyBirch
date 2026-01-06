"""
PyBirch Weather Utilities
=========================
Fetch local weather conditions for fabrication run records.
Environmental conditions can affect experimental results.
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_weather_conditions(
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    api_key: Optional[str] = None,
    location_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch current weather conditions from OpenWeatherMap API.
    
    Args:
        latitude: Latitude coordinate (uses default if not provided)
        longitude: Longitude coordinate (uses default if not provided)
        api_key: OpenWeatherMap API key (uses env var OPENWEATHERMAP_API_KEY if not provided)
        location_name: Optional name for the location
        
    Returns:
        Dictionary with weather conditions, or None if fetch fails.
        
    Example:
        >>> weather = get_weather_conditions(lat=40.7128, lon=-74.0060)
        >>> print(weather)
        {
            'temperature_c': 22.5,
            'humidity_percent': 65,
            'pressure_hpa': 1013,
            'weather_description': 'Clear sky',
            'wind_speed_ms': 3.5,
            'location': 'New York, US',
            'recorded_at': '2026-01-05T14:30:00',
            'source': 'OpenWeatherMap'
        }
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests library not available for weather fetching")
        return None
    
    # Get API key from environment if not provided
    api_key = api_key or os.environ.get('OPENWEATHERMAP_API_KEY')
    if not api_key:
        logger.debug("No OpenWeatherMap API key available, skipping weather fetch")
        return None
    
    # Default coordinates (can be configured per installation)
    # These should be set in config or environment for each lab
    if latitude is None:
        latitude = float(os.environ.get('PYBIRCH_LAB_LATITUDE', '0'))
    if longitude is None:
        longitude = float(os.environ.get('PYBIRCH_LAB_LONGITUDE', '0'))
    
    if latitude == 0 and longitude == 0:
        logger.debug("No coordinates configured for weather fetch")
        return None
    
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': latitude,
            'lon': longitude,
            'appid': api_key,
            'units': 'metric'  # Use Celsius
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Extract relevant weather data
        weather = {
            'temperature_c': data.get('main', {}).get('temp'),
            'feels_like_c': data.get('main', {}).get('feels_like'),
            'humidity_percent': data.get('main', {}).get('humidity'),
            'pressure_hpa': data.get('main', {}).get('pressure'),
            'weather_description': data.get('weather', [{}])[0].get('description', '').title(),
            'weather_main': data.get('weather', [{}])[0].get('main'),
            'wind_speed_ms': data.get('wind', {}).get('speed'),
            'wind_direction_deg': data.get('wind', {}).get('deg'),
            'clouds_percent': data.get('clouds', {}).get('all'),
            'visibility_m': data.get('visibility'),
            'location': location_name or f"{data.get('name', '')}, {data.get('sys', {}).get('country', '')}".strip(', '),
            'coordinates': {'lat': latitude, 'lon': longitude},
            'recorded_at': datetime.utcnow().isoformat(),
            'source': 'OpenWeatherMap',
        }
        
        # Remove None values
        weather = {k: v for k, v in weather.items() if v is not None}
        
        logger.info(f"Weather fetched: {weather.get('temperature_c')}°C, {weather.get('humidity_percent')}% humidity")
        return weather
        
    except requests.exceptions.Timeout:
        logger.warning("Weather API request timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch weather data: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching weather: {e}")
        return None


def get_manual_weather_conditions(
    temperature_c: Optional[float] = None,
    humidity_percent: Optional[float] = None,
    pressure_hpa: Optional[float] = None,
    weather_description: Optional[str] = None,
    location: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a weather conditions dict from manual input.
    
    Use this when automatic weather fetching isn't available or
    when you want to record indoor/lab conditions.
    
    Args:
        temperature_c: Temperature in Celsius
        humidity_percent: Relative humidity percentage
        pressure_hpa: Atmospheric pressure in hectopascals
        weather_description: Free-form weather description
        location: Location description
        notes: Additional notes
        
    Returns:
        Dictionary with weather conditions.
    """
    weather = {
        'recorded_at': datetime.utcnow().isoformat(),
        'source': 'manual',
    }
    
    if temperature_c is not None:
        weather['temperature_c'] = temperature_c
    if humidity_percent is not None:
        weather['humidity_percent'] = humidity_percent
    if pressure_hpa is not None:
        weather['pressure_hpa'] = pressure_hpa
    if weather_description:
        weather['weather_description'] = weather_description
    if location:
        weather['location'] = location
    if notes:
        weather['notes'] = notes
    
    return weather


def get_indoor_conditions(
    temperature_c: Optional[float] = None,
    humidity_percent: Optional[float] = None,
    room_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record indoor/lab environmental conditions.
    
    Many labs have environmental monitors - use this to record
    the conditions inside the lab rather than outside weather.
    
    Args:
        temperature_c: Room temperature in Celsius
        humidity_percent: Room relative humidity
        room_name: Name of the room/lab
        
    Returns:
        Dictionary with indoor conditions.
    """
    conditions = {
        'recorded_at': datetime.utcnow().isoformat(),
        'source': 'indoor_sensor',
        'environment_type': 'indoor',
    }
    
    if temperature_c is not None:
        conditions['temperature_c'] = temperature_c
    if humidity_percent is not None:
        conditions['humidity_percent'] = humidity_percent
    if room_name:
        conditions['location'] = room_name
    
    return conditions
