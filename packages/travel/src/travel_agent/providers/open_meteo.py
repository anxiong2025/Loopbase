"""Open-Meteo 地理编码与天气预报适配器，无需 API key。"""

from __future__ import annotations

from typing import Any

from .http import fetch_json

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_WEATHER_CODES = {
    0: "晴",
    1: "大致晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "小阵雨",
    81: "阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}


def geocode(name: str, *, language: str = "zh") -> dict[str, Any]:
    location_name = name.strip()
    if not location_name:
        raise ValueError("地点名称不能为空")
    data = fetch_json(
        GEOCODING_URL,
        params={
            "name": location_name,
            "count": 1,
            "language": language,
            "format": "json",
        },
    )
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"没有找到地点：{location_name}")
    item = results[0]
    return {
        "name": item.get("name") or location_name,
        "country": item.get("country"),
        "admin1": item.get("admin1"),
        "latitude": item["latitude"],
        "longitude": item["longitude"],
        "timezone": item.get("timezone"),
    }


def forecast(
    city: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    location = geocode(city)
    params: dict[str, Any] = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,sunrise,sunset"
        ),
        "timezone": "auto",
    }
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    data = fetch_json(FORECAST_URL, params=params)
    daily = data.get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        reason = data.get("reason") or "没有可用天气预报"
        raise RuntimeError(str(reason))

    keys = {
        "weather_code": daily.get("weather_code") or [],
        "temperature_max_c": daily.get("temperature_2m_max") or [],
        "temperature_min_c": daily.get("temperature_2m_min") or [],
        "precipitation_probability_max": daily.get(
            "precipitation_probability_max"
        )
        or [],
        "sunrise": daily.get("sunrise") or [],
        "sunset": daily.get("sunset") or [],
    }
    days = []
    for index, value in enumerate(dates):
        code = _at(keys["weather_code"], index)
        days.append(
            {
                "date": value,
                "weather_code": code,
                "weather": _WEATHER_CODES.get(code, "未知") if code is not None else None,
                "temperature_max_c": _at(keys["temperature_max_c"], index),
                "temperature_min_c": _at(keys["temperature_min_c"], index),
                "precipitation_probability_max": _at(
                    keys["precipitation_probability_max"], index
                ),
                "sunrise": _at(keys["sunrise"], index),
                "sunset": _at(keys["sunset"], index),
            }
        )
    return {
        "source": "Open-Meteo",
        "location": location,
        "timezone": data.get("timezone"),
        "days": days,
    }


def _at(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None
