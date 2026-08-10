"""Unit tests for travel tools without live network access."""

from __future__ import annotations

import json

import pytest
from loopbase import ToolRegistry
from travel_agent.providers import open_meteo, wikipedia
from travel_agent.tools import register_all
from travel_agent.tools.calculate_distance import impl as calculate_distance
from travel_agent.tools.calculate_trip_budget import impl as calculate_budget
from travel_agent.tools.get_weather import impl as get_weather
from travel_agent.tools.search_places import impl as search_places


def test_registers_the_travel_tool_set() -> None:
    registry = ToolRegistry()

    register_all(registry)

    assert registry.names() == [
        "get_weather_forecast",
        "search_travel_places",
        "calculate_location_distance",
        "calculate_trip_budget",
    ]


def test_budget_calculator_uses_only_supplied_amounts() -> None:
    result = json.loads(
        calculate_budget(
            budget=3000,
            transport=1200,
            accommodation=800,
            food=450,
            attractions=200,
            local_transport=150,
            other=50,
        )
    )

    assert result["total"] == 2850
    assert result["remaining"] == 150
    assert result["within_budget"] is True


def test_budget_calculator_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="transport"):
        calculate_budget(
            budget=3000,
            transport=-1,
            accommodation=0,
            food=0,
            attractions=0,
            local_transport=0,
        )


def test_distance_tool_marks_result_as_straight_line(monkeypatch) -> None:
    locations = {
        "深圳": {"name": "深圳", "latitude": 22.5431, "longitude": 114.0579},
        "北京": {"name": "北京", "latitude": 39.9042, "longitude": 116.4074},
    }
    monkeypatch.setattr(open_meteo, "geocode", lambda name: locations[name])

    result = json.loads(calculate_distance("深圳", "北京"))

    assert 1900 < result["straight_line_distance_km"] < 2000
    assert "直线距离" in result["notice"]


def test_weather_tool_returns_normalized_daily_forecast(monkeypatch) -> None:
    monkeypatch.setattr(
        open_meteo,
        "geocode",
        lambda city: {
            "name": city,
            "country": "中国",
            "latitude": 39.9,
            "longitude": 116.4,
            "timezone": "Asia/Shanghai",
        },
    )
    monkeypatch.setattr(
        open_meteo,
        "fetch_json",
        lambda url, params: {
            "timezone": "Asia/Shanghai",
            "daily": {
                "time": ["2026-08-11"],
                "weather_code": [61],
                "temperature_2m_max": [29.0],
                "temperature_2m_min": [21.0],
                "precipitation_probability_max": [70],
                "sunrise": ["2026-08-11T05:20"],
                "sunset": ["2026-08-11T19:15"],
            },
        },
    )

    result = json.loads(get_weather("北京", "2026-08-11", "2026-08-11"))

    assert result["source"] == "Open-Meteo"
    assert result["days"][0]["weather"] == "小雨"
    assert result["days"][0]["precipitation_probability_max"] == 70


def test_place_search_keeps_sources_and_realtime_warning(monkeypatch) -> None:
    monkeypatch.setattr(
        wikipedia,
        "search",
        lambda query, limit: [
            {
                "title": "故宫博物院",
                "summary": "位于北京中轴线。",
                "url": "https://zh.wikipedia.org/wiki/故宫博物院",
            }
        ],
    )

    result = json.loads(search_places("北京", "历史景点", 3))

    assert result["source"] == "中文维基百科"
    assert result["results"][0]["title"] == "故宫博物院"
    assert "开放时间" in result["notice"]
