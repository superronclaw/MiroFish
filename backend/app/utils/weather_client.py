"""
Weather API Client
主要使用 Open-Meteo API（完全免費，無需 API Key）
備用: OpenWeatherMap API（需要 API Key）

Open-Meteo: https://open-meteo.com/ - 免費，無限制
OpenWeatherMap: https://openweathermap.org/ - 免費層 60 req/min
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import requests

logger = logging.getLogger('mirofish.weather')

# WMO Weather codes to condition mapping (Open-Meteo uses WMO codes)
WMO_CODE_MAP = {
    0: 'Clear', 1: 'Clear', 2: 'Clouds', 3: 'Clouds',
    45: 'Fog', 48: 'Fog',
    51: 'Drizzle', 53: 'Drizzle', 55: 'Drizzle',
    56: 'Drizzle', 57: 'Drizzle',
    61: 'Rain', 63: 'Rain', 65: 'Rain',
    66: 'Rain', 67: 'Rain',
    71: 'Snow', 73: 'Snow', 75: 'Snow',
    77: 'Snow',
    80: 'Rain', 81: 'Rain', 82: 'Rain',
    85: 'Snow', 86: 'Snow',
    95: 'Thunderstorm', 96: 'Thunderstorm', 99: 'Thunderstorm',
}


class WeatherClient:
    """Weather API Client - Open-Meteo (primary) + OpenWeatherMap (fallback)"""

    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
    OWM_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str = ''):
        self.owm_api_key = api_key
        self.session = requests.Session()

    def get_current_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get current weather using Open-Meteo (free, no key needed)."""
        try:
            return self._open_meteo_current(lat, lon)
        except Exception as e:
            logger.warning(f"Open-Meteo failed: {e}, trying OpenWeatherMap")
            if self.owm_api_key:
                return self._owm_current(lat, lon)
            raise

    def get_forecast(self, lat: float, lon: float, days: int = 5) -> list:
        """Get weather forecast using Open-Meteo."""
        try:
            return self._open_meteo_forecast(lat, lon, days)
        except Exception as e:
            logger.warning(f"Open-Meteo forecast failed: {e}")
            if self.owm_api_key:
                return self._owm_forecast(lat, lon)
            raise

    def get_weather_for_match(
        self, lat: float, lon: float, match_datetime: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get weather closest to match time."""
        try:
            forecasts = self.get_forecast(lat, lon)
            if not forecasts:
                return None
            closest = min(
                forecasts,
                key=lambda f: abs(
                    (f['datetime'] - match_datetime).total_seconds()
                ) if f.get('datetime') else float('inf'),
            )
            return closest
        except Exception as e:
            logger.warning(f"Failed to get match weather: {e}")
            return None

    # ============= Open-Meteo (Primary, Free) =============

    def _open_meteo_current(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get current weather from Open-Meteo."""
        params = {
            'latitude': lat,
            'longitude': lon,
            'current_weather': 'true',
            'hourly': 'relative_humidity_2m,pressure_msl,rain,snowfall,cloud_cover',
            'forecast_days': 1,
        }
        resp = self.session.get(self.OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        cw = data.get('current_weather', {})
        hourly = data.get('hourly', {})

        # Get humidity from the closest hourly data
        humidity = None
        pressure = None
        if hourly.get('relative_humidity_2m'):
            humidity = hourly['relative_humidity_2m'][0]
        if hourly.get('pressure_msl'):
            pressure = hourly['pressure_msl'][0]

        weather_code = cw.get('weathercode', 0)
        condition = WMO_CODE_MAP.get(weather_code, 'Unknown')

        return {
            'datetime': datetime.now(),
            'condition': condition,
            'description': f'WMO code {weather_code}',
            'temperature': cw.get('temperature'),
            'feels_like': cw.get('temperature'),  # Open-Meteo current doesn't have feels_like
            'humidity': humidity,
            'pressure': pressure,
            'wind_speed': cw.get('windspeed'),
            'wind_direction': cw.get('winddirection'),
            'clouds': hourly.get('cloud_cover', [None])[0] if hourly.get('cloud_cover') else None,
            'rain_1h': hourly.get('rain', [0])[0] if hourly.get('rain') else 0,
            'snow_1h': hourly.get('snowfall', [0])[0] if hourly.get('snowfall') else 0,
        }

    def _open_meteo_forecast(self, lat: float, lon: float, days: int = 5) -> list:
        """Get hourly forecast from Open-Meteo."""
        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'temperature_2m,relative_humidity_2m,weathercode,windspeed_10m,winddirection_10m,pressure_msl,rain,snowfall,cloudcover',
            'forecast_days': min(days, 16),
        }
        resp = self.session.get(self.OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        hourly = data.get('hourly', {})
        times = hourly.get('time', [])
        forecasts = []

        for i, time_str in enumerate(times):
            dt = datetime.fromisoformat(time_str)
            weather_code = (hourly.get('weathercode') or [0] * len(times))[i] if i < len(hourly.get('weathercode', [])) else 0
            condition = WMO_CODE_MAP.get(weather_code, 'Unknown')

            forecasts.append({
                'datetime': dt,
                'condition': condition,
                'description': f'WMO code {weather_code}',
                'temperature': hourly.get('temperature_2m', [None])[i] if i < len(hourly.get('temperature_2m', [])) else None,
                'feels_like': hourly.get('temperature_2m', [None])[i] if i < len(hourly.get('temperature_2m', [])) else None,
                'humidity': hourly.get('relative_humidity_2m', [None])[i] if i < len(hourly.get('relative_humidity_2m', [])) else None,
                'pressure': hourly.get('pressure_msl', [None])[i] if i < len(hourly.get('pressure_msl', [])) else None,
                'wind_speed': hourly.get('windspeed_10m', [None])[i] if i < len(hourly.get('windspeed_10m', [])) else None,
                'wind_direction': hourly.get('winddirection_10m', [None])[i] if i < len(hourly.get('winddirection_10m', [])) else None,
                'clouds': hourly.get('cloudcover', [None])[i] if i < len(hourly.get('cloudcover', [])) else None,
                'rain_1h': hourly.get('rain', [0])[i] if i < len(hourly.get('rain', [])) else 0,
                'snow_1h': hourly.get('snowfall', [0])[i] if i < len(hourly.get('snowfall', [])) else 0,
            })

        return forecasts

    # ============= OpenWeatherMap (Fallback) =============

    def _owm_current(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get current weather from OpenWeatherMap."""
        params = {'lat': lat, 'lon': lon, 'appid': self.owm_api_key, 'units': 'metric'}
        resp = self.session.get(f"{self.OWM_URL}/weather", params=params, timeout=15)
        resp.raise_for_status()
        return self._parse_owm(resp.json())

    def _owm_forecast(self, lat: float, lon: float) -> list:
        """Get forecast from OpenWeatherMap."""
        params = {'lat': lat, 'lon': lon, 'appid': self.owm_api_key, 'units': 'metric'}
        resp = self.session.get(f"{self.OWM_URL}/forecast", params=params, timeout=15)
        resp.raise_for_status()
        return [self._parse_owm(item) for item in resp.json().get('list', [])]

    @staticmethod
    def _parse_owm(data: Dict) -> Dict[str, Any]:
        """Parse OpenWeatherMap response."""
        main = data.get('main', {})
        weather = data.get('weather', [{}])[0]
        wind = data.get('wind', {})
        dt = data.get('dt')

        return {
            'datetime': datetime.fromtimestamp(dt) if dt else None,
            'condition': weather.get('main', 'Unknown'),
            'description': weather.get('description', ''),
            'temperature': main.get('temp'),
            'feels_like': main.get('feels_like'),
            'humidity': main.get('humidity'),
            'pressure': main.get('pressure'),
            'wind_speed': wind.get('speed'),
            'wind_direction': wind.get('deg'),
            'clouds': data.get('clouds', {}).get('all'),
            'rain_1h': data.get('rain', {}).get('1h', 0),
            'snow_1h': data.get('snow', {}).get('1h', 0),
        }

    # ============= Utility Methods =============

    @staticmethod
    def encode_weather_condition(condition: str) -> int:
        """Encode weather condition to numeric value for ML features."""
        encoding = {
            'Clear': 0, 'Clouds': 1, 'Drizzle': 2, 'Rain': 3,
            'Thunderstorm': 4, 'Snow': 5, 'Mist': 6, 'Fog': 6, 'Haze': 6,
        }
        return encoding.get(condition, 1)

    @staticmethod
    def weather_impact_score(weather_data: Dict) -> float:
        """Calculate weather impact score (0=no impact, 1=strong impact)."""
        score = 0.0

        condition = weather_data.get('condition', 'Clear')
        if condition in ('Rain', 'Thunderstorm'):
            score += 0.3
        elif condition == 'Snow':
            score += 0.5
        elif condition == 'Drizzle':
            score += 0.1

        wind = weather_data.get('wind_speed', 0) or 0
        if wind > 15:
            score += 0.3
        elif wind > 10:
            score += 0.2
        elif wind > 5:
            score += 0.1

        temp = weather_data.get('temperature', 20) or 20
        if temp < 0 or temp > 35:
            score += 0.2
        elif temp < 5 or temp > 30:
            score += 0.1

        humidity = weather_data.get('humidity', 50) or 50
        if humidity > 90:
            score += 0.1

        return min(score, 1.0)
