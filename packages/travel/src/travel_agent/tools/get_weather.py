"""目的地天气工具。"""

from __future__ import annotations

import json

from loopbase import ToolSpec

from ..providers import open_meteo

SPEC = ToolSpec(
    name="get_weather_forecast",
    description=(
        "查询城市的逐日天气预报，返回温度、降水概率和日出日落。"
        "只适用于 Open-Meteo 当前支持的预报日期范围。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称，如北京"},
            "start_date": {
                "type": "string",
                "description": "可选，开始日期，YYYY-MM-DD",
            },
            "end_date": {
                "type": "string",
                "description": "可选，结束日期，YYYY-MM-DD",
            },
        },
        "required": ["city"],
    },
)


def impl(
    city: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    result = open_meteo.forecast(
        city,
        start_date=start_date,
        end_date=end_date,
    )
    return json.dumps(result, ensure_ascii=False)


def register(registry) -> None:
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
