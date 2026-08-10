"""确定性旅行预算汇总工具，不自行估价。"""

from __future__ import annotations

import json
from typing import Any

from loopbase import ToolSpec

_CATEGORIES = (
    "transport",
    "accommodation",
    "food",
    "attractions",
    "local_transport",
    "other",
)

SPEC = ToolSpec(
    name="calculate_trip_budget",
    description=(
        "汇总一次旅行各类别的总金额并检查是否超预算。"
        "所有金额必须来自用户或其他工具，本工具不估算机票、酒店或门票价格。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "budget": {"type": "number", "minimum": 0, "description": "总预算"},
            "transport": {"type": "number", "minimum": 0, "description": "往返大交通总额"},
            "accommodation": {"type": "number", "minimum": 0, "description": "住宿总额"},
            "food": {"type": "number", "minimum": 0, "description": "餐饮总额"},
            "attractions": {"type": "number", "minimum": 0, "description": "景点门票和活动总额"},
            "local_transport": {"type": "number", "minimum": 0, "description": "市内交通总额"},
            "other": {"type": "number", "minimum": 0, "description": "其他费用，默认0"},
            "currency": {"type": "string", "description": "币种，默认CNY"},
        },
        "required": [
            "budget",
            "transport",
            "accommodation",
            "food",
            "attractions",
            "local_transport"
        ],
    },
)


def impl(
    budget: float,
    transport: float,
    accommodation: float,
    food: float,
    attractions: float,
    local_transport: float,
    other: float = 0,
    currency: str = "CNY",
) -> str:
    values = {
        "budget": budget,
        "transport": transport,
        "accommodation": accommodation,
        "food": food,
        "attractions": attractions,
        "local_transport": local_transport,
        "other": other,
    }
    normalized = {key: _amount(value, key) for key, value in values.items()}
    total = sum(normalized[key] for key in _CATEGORIES)
    remaining = normalized["budget"] - total
    result: dict[str, Any] = {
        "currency": currency.strip().upper() or "CNY",
        "budget": round(normalized["budget"], 2),
        "breakdown": {
            key: round(normalized[key], 2) for key in _CATEGORIES
        },
        "total": round(total, 2),
        "remaining": round(remaining, 2),
        "within_budget": remaining >= 0,
        "notice": "仅做确定性汇总，不代表任何项目的实时价格。",
    }
    return json.dumps(result, ensure_ascii=False)


def _amount(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} 必须是非负数字")
    return float(value)


def register(registry) -> None:
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
