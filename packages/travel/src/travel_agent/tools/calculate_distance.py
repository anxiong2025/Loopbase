"""地点直线距离估算工具。"""

from __future__ import annotations

import json
import math

from loopbase import ToolSpec

from ..providers import open_meteo

SPEC = ToolSpec(
    name="calculate_location_distance",
    description=(
        "计算两个地点之间的直线距离，用于判断大致空间关系。"
        "这不是驾车、公交或步行路线距离，不能代替路线规划。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "origin": {"type": "string", "description": "起点名称"},
            "destination": {"type": "string", "description": "终点名称"},
        },
        "required": ["origin", "destination"],
    },
)


def impl(origin: str, destination: str) -> str:
    start = open_meteo.geocode(origin)
    end = open_meteo.geocode(destination)
    distance = _haversine_km(
        float(start["latitude"]),
        float(start["longitude"]),
        float(end["latitude"]),
        float(end["longitude"]),
    )
    return json.dumps(
        {
            "origin": start,
            "destination": end,
            "straight_line_distance_km": round(distance, 1),
            "notice": "直线距离，不是实际交通路线距离或耗时。",
            "source": "Open-Meteo Geocoding",
        },
        ensure_ascii=False,
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def register(registry) -> None:
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
